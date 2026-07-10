#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     test_cascor_ws_control.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/tests/integration/
#
# Date Created:  2026-02-11
# Last Modified: 2026-02-11
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Integration tests for Fix 3 (RC-3) — WebSocket control commands for real
#    CasCor backend mode. Verifies that the /ws/control endpoint correctly
#    dispatches start, stop, pause, resume, and reset commands to the
#    CascorIntegration instance when demo mode is inactive.
#
#    Because conftest.py forces CASCOR_DEMO_MODE=1, these tests mock the
#    main module globals (demo_mode_instance, demo_mode_active,
#    cascor_integration) to simulate real backend mode.
#
#####################################################################################################################################################################################################
# Notes:
#    Tests use FastAPI TestClient.websocket_connect for WebSocket tests.
#    The connect message (first received message) is consumed before
#    sending commands.
#
#####################################################################################################################################################################################################
# References:
#    - Fix 3 (RC-3): WebSocket control commands for real CasCor backend
#    - src/main.py websocket_control_endpoint (lines 412-537)
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
"""Integration tests for WebSocket control command dispatch to CascorIntegration in real backend mode."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main as main_module
from main import app


@pytest.fixture
def mock_service_backend():
    """Create a mock BackendProtocol with service-mode defaults."""
    mock = MagicMock()
    mock.backend_type = "service"
    mock.start_training.return_value = {"ok": True, "is_training": True}
    mock.stop_training.return_value = {"ok": True}
    mock.pause_training.return_value = {"ok": False, "error": "Pause not yet supported in service mode"}
    mock.resume_training.return_value = {"ok": False, "error": "Resume not yet supported in service mode"}
    mock.reset_training.return_value = {"ok": False, "error": "Reset not yet supported in service mode"}
    mock.get_status.return_value = {"is_training": False, "network_connected": True}
    mock.is_training_active.return_value = False
    return mock


@pytest.fixture
def cascor_client(mock_service_backend):
    """
    TestClient with backend patched to simulate service mode.
    """
    with TestClient(app) as client:
        # Set mock AFTER lifespan runs (lifespan creates the real backend)
        original_backend = main_module.backend
        main_module.backend = mock_service_backend
        yield client
        main_module.backend = original_backend


def _send_ws_command(client, command, **extra):
    """Send a command over /ws/control and return the response dict.

    CSRF auth is handled automatically by the conftest.py monkeypatch which
    injects `{"type": "auth", "csrf_token": ...}` as the first frame on every
    /ws/control connection. Do NOT re-send it here — a duplicate auth frame
    would be parsed as a command with no "command" key, producing an
    `{"ok": False, "error": "Unknown command: "}` response that the test's
    first receive_json() would pick up instead of the real command response.

    Drains any broadcast messages (metrics/state) that may arrive between
    the connection acknowledgment and the command response.
    """
    with client.websocket_connect("/ws/control") as ws:
        ws.receive_json()  # consume connection_established ack
        payload = {"command": command, **extra}
        ws.send_text(json.dumps(payload))
        # The demo backend training thread may broadcast metrics/state messages
        # between connect and the command response. Drain until we find the
        # command response (which contains an "ok" key).
        for _ in range(10):
            msg = ws.receive_json()
            if "ok" in msg:
                return msg
        raise AssertionError("No command response received after 10 messages")


class TestCascorWsControl:
    """Integration tests for service-mode WebSocket control commands via BackendProtocol."""

    @pytest.mark.integration
    def test_service_start_command_calls_protocol(self, cascor_client, mock_service_backend):
        """'start' command calls backend.start_training() and returns ok."""
        response = _send_ws_command(cascor_client, "start")

        assert response["ok"] is True
        assert response["command"] == "start"
        mock_service_backend.start_training.assert_called_once_with(reset=True)

    @pytest.mark.integration
    def test_service_start_with_reset_false(self, cascor_client, mock_service_backend):
        """'start' with reset=false passes reset param to protocol."""
        response = _send_ws_command(cascor_client, "start", reset=False)

        assert response["ok"] is True
        mock_service_backend.start_training.assert_called_once_with(reset=False)

    @pytest.mark.integration
    def test_service_stop_command_calls_protocol(self, cascor_client, mock_service_backend):
        """'stop' command calls backend.stop_training()."""
        response = _send_ws_command(cascor_client, "stop")

        assert response["ok"] is True
        assert response["command"] == "stop"
        mock_service_backend.stop_training.assert_called_once()

    @pytest.mark.integration
    def test_service_pause_command_calls_protocol(self, cascor_client, mock_service_backend):
        """'pause' command calls backend.pause_training(); its ok=False result
        surfaces as an error envelope (2026-07-09 PR-A — previously wrapped
        in a success envelope, the §S10 dead-button class)."""
        response = _send_ws_command(cascor_client, "pause")

        assert response["ok"] is False
        assert "not yet supported" in response["error"]
        assert response["command"] == "pause"
        mock_service_backend.pause_training.assert_called_once()

    @pytest.mark.integration
    def test_service_resume_command_calls_protocol(self, cascor_client, mock_service_backend):
        """'resume' command calls backend.resume_training(); its ok=False result
        surfaces as an error envelope (2026-07-09 PR-A — previously wrapped
        in a success envelope, the §S10 dead-button class)."""
        response = _send_ws_command(cascor_client, "resume")

        assert response["ok"] is False
        assert "not yet supported" in response["error"]
        assert response["command"] == "resume"
        mock_service_backend.resume_training.assert_called_once()

    @pytest.mark.integration
    def test_service_reset_command_calls_protocol(self, cascor_client, mock_service_backend):
        """'reset' command calls backend.reset_training(); its ok=False result
        surfaces as an error envelope (2026-07-09 PR-A — previously wrapped
        in a success envelope, the §S10 dead-button class)."""
        response = _send_ws_command(cascor_client, "reset")

        assert response["ok"] is False
        assert "not yet supported" in response["error"]
        assert response["command"] == "reset"
        mock_service_backend.reset_training.assert_called_once()

    @pytest.mark.integration
    def test_service_unknown_command_returns_error(self, cascor_client, mock_service_backend):
        """Unknown command returns an error response."""
        response = _send_ws_command(cascor_client, "explode")

        assert response["ok"] is False
        assert "Unknown command" in response.get("error", "")

    @pytest.mark.integration
    def test_service_command_exception_returns_error(self, cascor_client, mock_service_backend):
        """Exception in command handler returns error to client."""
        mock_service_backend.start_training.side_effect = RuntimeError("Test error")

        response = _send_ws_command(cascor_client, "start")

        assert response["ok"] is False
        assert "Command execution failed" in response.get("error", "")
