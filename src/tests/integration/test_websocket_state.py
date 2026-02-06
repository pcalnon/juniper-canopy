#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_websocket_state.py
# Author:        Paul Calnon
# Version:       1.1.0
#
# Date:          2025-11-16
# Last Modified: 2026-02-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Integration tests for WebSocket state message broadcasts.
#    Tests verify the state message sent on /ws/training connect.
#
#####################################################################################################################################################################################################
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from main import app

    return TestClient(app)


def _receive_state_message(websocket):
    """Receive the state message from the /ws/training connect sequence.

    The connect sequence sends 3 messages:
    1. connection_established (from websocket_manager.connect)
    2. initial_status (from handler)
    3. state (from handler, TrainingState format)

    Returns the state message (message #3).
    """
    # Message 1: connection_established
    msg1 = websocket.receive_json()
    assert msg1["type"] == "connection_established"

    # Message 2: initial_status
    msg2 = websocket.receive_json()
    assert msg2["type"] == "initial_status"

    # Message 3: state (the one we want)
    msg3 = websocket.receive_json()
    assert msg3["type"] == "state"

    return msg3


@pytest.mark.integration
class TestWebSocketStateMessages:
    """Test WebSocket state message broadcasts."""

    def test_websocket_receives_state_messages(self, test_client):
        """Test WebSocket receives state messages on connect."""
        with test_client.websocket_connect("/ws/training") as websocket:
            state_msg = _receive_state_message(websocket)

            assert "timestamp" in state_msg
            assert "data" in state_msg
            assert isinstance(state_msg["timestamp"], (int, float))
            assert isinstance(state_msg["data"], dict)

    def test_state_message_format(self, test_client):
        """Test state message has correct format."""
        with test_client.websocket_connect("/ws/training") as websocket:
            state_msg = _receive_state_message(websocket)

            assert state_msg["type"] == "state"
            assert "timestamp" in state_msg
            assert "data" in state_msg

            data = state_msg["data"]
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

    def test_state_message_field_types(self, test_client):
        """Test state message fields have correct types."""
        with test_client.websocket_connect("/ws/training") as websocket:
            state_msg = _receive_state_message(websocket)
            data = state_msg["data"]

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

    def test_multiple_clients_receive_state_on_connect(self, test_client):
        """Test multiple WebSocket clients each receive state on connect."""
        with test_client.websocket_connect("/ws/training") as ws1:
            with test_client.websocket_connect("/ws/training") as ws2:
                state1 = _receive_state_message(ws1)
                state2 = _receive_state_message(ws2)

                # Both clients should have received state messages
                assert state1["type"] == "state"
                assert state2["type"] == "state"
                assert isinstance(state1["data"], dict)
                assert isinstance(state2["data"], dict)


class TestWebSocketStateMessageContent:
    """Test WebSocket state message content."""

    def test_state_message_status_values(self, test_client):
        """Test state message status field has valid values."""
        with test_client.websocket_connect("/ws/training") as websocket:
            state_msg = _receive_state_message(websocket)
            status = state_msg["data"]["status"].lower()
            assert status in ["stopped", "started", "paused"]

    def test_state_message_phase_values(self, test_client):
        """Test state message phase field has valid values."""
        with test_client.websocket_connect("/ws/training") as websocket:
            state_msg = _receive_state_message(websocket)
            phase = state_msg["data"]["phase"].lower()
            assert phase in ["idle", "output", "candidate", "inference"]

    def test_state_message_timestamp_is_recent(self, test_client):
        """Test state message timestamp is recent."""
        with test_client.websocket_connect("/ws/training") as websocket:
            state_msg = _receive_state_message(websocket)
            msg_timestamp = state_msg["timestamp"]
            data_timestamp = state_msg["data"]["timestamp"]
            current_time = time.time()

            # Both timestamps should be recent
            assert abs(msg_timestamp - current_time) < 10.0
            assert abs(data_timestamp - current_time) < 10.0
