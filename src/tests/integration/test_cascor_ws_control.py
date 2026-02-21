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
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/tests/integration/
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

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main as main_module
from main import app


@pytest.fixture
def mock_cascor():
    """Create a mock CascorIntegration with sensible defaults."""
    mock = MagicMock()
    mock.network = MagicMock()
    mock.is_training_in_progress.return_value = False
    mock.start_training_background.return_value = True
    mock.request_training_stop.return_value = True
    mock.get_training_status.return_value = {
        "is_training": False,
        "network_connected": True,
    }
    mock.restore_original_methods.return_value = None
    mock.create_network.return_value = None
    mock.install_monitoring_hooks.return_value = True
    return mock


@pytest.fixture
def cascor_client(mock_cascor):
    """
    TestClient with globals patched to simulate real CasCor backend mode.

    Disables demo_mode_instance and demo_mode_active, injects mock_cascor
    as the active cascor_integration.
    """
    original_demo_instance = main_module.demo_mode_instance
    original_demo_active = main_module.demo_mode_active
    original_cascor = main_module.backend

    main_module.demo_mode_instance = None
    main_module.demo_mode_active = False
    main_module.backend = mock_cascor

    with TestClient(app) as client:
        yield client

    main_module.demo_mode_instance = original_demo_instance
    main_module.demo_mode_active = original_demo_active
    main_module.backend = original_cascor


def _send_ws_command(client, command, **extra):
    """Send a command over /ws/control and return the response dict."""
    with client.websocket_connect("/ws/control") as ws:
        ws.receive_json()
        payload = {"command": command, **extra}
        ws.send_text(json.dumps(payload))
        return ws.receive_json()


class TestCascorWsControl:
    """Integration tests for CasCor backend WebSocket control commands (RC-3)."""

    @pytest.mark.integration
    def test_cascor_start_command_starts_training(self, cascor_client, mock_cascor):
        """'start' command calls start_training_background() and returns ok."""
        response = _send_ws_command(cascor_client, "start")

        assert response["ok"] is True
        assert response["command"] == "start"
        mock_cascor.start_training_background.assert_called_once()

    @pytest.mark.integration
    def test_cascor_start_no_network_returns_error(self, cascor_client, mock_cascor):
        """'start' with no network configured returns an error."""
        mock_cascor.network = None

        response = _send_ws_command(cascor_client, "start")

        assert response["ok"] is False
        assert "No network configured" in response["error"]
        mock_cascor.start_training_background.assert_not_called()

    @pytest.mark.integration
    def test_cascor_start_while_training_returns_busy(self, cascor_client, mock_cascor):
        """'start' during active training returns an error."""
        mock_cascor.is_training_in_progress.return_value = True

        response = _send_ws_command(cascor_client, "start")

        assert response["ok"] is False
        assert "already in progress" in response["error"]
        mock_cascor.start_training_background.assert_not_called()

    @pytest.mark.integration
    def test_cascor_stop_command_requests_stop(self, cascor_client, mock_cascor):
        """'stop' command calls request_training_stop() when training is active."""
        mock_cascor.is_training_in_progress.return_value = True

        response = _send_ws_command(cascor_client, "stop")

        assert response["ok"] is True
        assert response["command"] == "stop"
        mock_cascor.request_training_stop.assert_called_once()

    @pytest.mark.integration
    def test_cascor_stop_when_not_training(self, cascor_client, mock_cascor):
        """'stop' when no training is active returns ok without calling stop."""
        mock_cascor.is_training_in_progress.return_value = False

        response = _send_ws_command(cascor_client, "stop")

        assert response["ok"] is True
        assert response["command"] == "stop"
        mock_cascor.request_training_stop.assert_not_called()

    @pytest.mark.integration
    def test_cascor_pause_returns_unsupported(self, cascor_client, mock_cascor):
        """'pause' returns an error indicating it is not supported."""
        response = _send_ws_command(cascor_client, "pause")

        assert response["ok"] is False
        assert response["command"] == "pause"
        assert "not supported" in response["error"].lower() or "Pause not supported" in response["error"]

    @pytest.mark.integration
    def test_cascor_resume_returns_unsupported(self, cascor_client, mock_cascor):
        """'resume' returns an error indicating it is not supported."""
        response = _send_ws_command(cascor_client, "resume")

        assert response["ok"] is False
        assert response["command"] == "resume"
        assert "not supported" in response["error"].lower() or "Resume not supported" in response["error"]

    @pytest.mark.integration
    def test_cascor_reset_recreates_network(self, cascor_client, mock_cascor):
        """'reset' calls restore_original_methods(), create_network(), and install_monitoring_hooks()."""
        mock_cascor.restore_original_methods.reset_mock()
        mock_cascor.create_network.reset_mock()
        mock_cascor.install_monitoring_hooks.reset_mock()

        response = _send_ws_command(cascor_client, "reset")

        assert response["ok"] is True
        assert response["command"] == "reset"
        mock_cascor.restore_original_methods.assert_called_once()
        mock_cascor.create_network.assert_called_once()
        mock_cascor.install_monitoring_hooks.assert_called_once()

    @pytest.mark.integration
    def test_cascor_unknown_command_returns_error(self, cascor_client, mock_cascor):
        """Unknown command returns an error response."""
        response = _send_ws_command(cascor_client, "explode")

        assert response["ok"] is False
        assert "Unknown command" in response.get("error", "")
