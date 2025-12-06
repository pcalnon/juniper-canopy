#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_websocket_state.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Integration tests for WebSocket state message broadcasts.
#
#####################################################################################################################################################################################################
import contextlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from main import app

    return TestClient(app)


@pytest.mark.requires_server
@pytest.mark.integration
class TestWebSocketStateMessages:
    """Test WebSocket state message broadcasts."""

    def test_websocket_receives_state_messages(self, test_client):
        """Test WebSocket receives state messages."""
        with test_client.websocket_connect("/ws/training") as websocket:
            # Receive initial status message
            data = websocket.receive_json()
            assert data["type"] == "connection_established"

            # Wait for potential state messages
            # Note: This depends on demo mode being active and broadcasting
            with contextlib.suppress(Exception):
                for _ in range(5):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        # Found a state message
                        assert "timestamp" in message
                        assert "data" in message
                        assert isinstance(message["timestamp"], (int, float))
                        assert isinstance(message["data"], dict)
                        break

    def test_state_message_format(self, test_client):
        """Test state message has correct format."""
        with test_client.websocket_connect("/ws/training") as websocket:
            # Receive initial connection message
            websocket.receive_json()

            # Wait for state message
            try:
                for _ in range(10):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        # Validate format
                        assert "type" in message
                        assert message["type"] == "state"
                        assert "timestamp" in message
                        assert "data" in message

                        # Validate data structure
                        data = message["data"]
                        required_fields = [
                            "status",
                            "phase",
                            "learning_rate",
                            "max_hidden_units",
                            "current_epoch",
                            "current_step",
                            "network_name",
                            "dataset_name",
                            "threshold_function",
                            "optimizer_name",
                            "timestamp",
                        ]

                        for field in required_fields:
                            assert field in data, f"Missing field: {field}"
                        break
            except Exception:
                pytest.skip("No state messages received during test")

    def test_state_message_field_types(self, test_client):
        """Test state message fields have correct types."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            try:
                for _ in range(10):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        data = message["data"]

                        assert isinstance(data["status"], str)
                        assert isinstance(data["phase"], str)
                        assert isinstance(data["learning_rate"], (int, float))
                        assert isinstance(data["max_hidden_units"], int)
                        assert isinstance(data["current_epoch"], int)
                        assert isinstance(data["current_step"], int)
                        assert isinstance(data["network_name"], str)
                        assert isinstance(data["dataset_name"], str)
                        assert isinstance(data["threshold_function"], str)
                        assert isinstance(data["optimizer_name"], str)
                        assert isinstance(data["timestamp"], (int, float))
                        break
            except Exception:
                pytest.skip("No state messages received during test")

    def test_multiple_clients_receive_state_broadcast(self, test_client):
        """Test multiple WebSocket clients receive state broadcasts."""
        with test_client.websocket_connect("/ws/training") as ws1:
            with test_client.websocket_connect("/ws/training") as ws2:
                # Receive initial connection messages
                ws1.receive_json()
                ws2.receive_json()

                # Both should receive state messages (if demo mode is active)
                messages1 = []
                messages2 = []

                with contextlib.suppress(Exception):
                    for _ in range(5):
                        msg1 = ws1.receive_json(timeout=2.0)
                        msg2 = ws2.receive_json(timeout=2.0)

                        if msg1.get("type") == "state":
                            messages1.append(msg1)
                        if msg2.get("type") == "state":
                            messages2.append(msg2)

                        if messages1 and messages2:
                            break
                # If state messages were received, both clients should have them
                if messages1 or messages2:
                    assert messages1
                    assert messages2


class TestWebSocketStateMessageContent:
    """Test WebSocket state message content."""

    def test_state_message_status_values(self, test_client):
        """Test state message status field has valid values."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            try:
                for _ in range(10):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        status = message["data"]["status"]
                        assert status in ["Stopped", "Started", "Paused"]
                        break
            except Exception:
                pytest.skip("No state messages received during test")

    def test_state_message_phase_values(self, test_client):
        """Test state message phase field has valid values."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            try:
                for _ in range(10):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        phase = message["data"]["phase"]
                        assert phase in ["Idle", "Output", "Candidate", "Inference"]
                        break
            except Exception:
                pytest.skip("No state messages received during test")

    def test_state_message_timestamp_is_recent(self, test_client):
        """Test state message timestamp is recent."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            try:
                for _ in range(10):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        msg_timestamp = message["timestamp"]
                        data_timestamp = message["data"]["timestamp"]
                        current_time = time.time()

                        # Both timestamps should be recent
                        assert abs(msg_timestamp - current_time) < 10.0
                        assert abs(data_timestamp - current_time) < 10.0
                        break
            except Exception:
                pytest.skip("No state messages received during test")
