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
"""Integration tests for WebSocket state message broadcasts on /ws/training connect."""

import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for FastAPI app.

    Enters the TestClient as a context manager so FastAPI's lifespan runs and
    initializes the module-level `backend` global in main.py. Without the
    context-manager entry, the /ws/training handler's `backend.get_status()`
    call hits a None and every test in this file fails with
    `AttributeError: 'NoneType' object has no attribute 'get_status'`.
    """
    from main import app

    with TestClient(app) as client:
        yield client


def _receive_state_message(websocket, max_messages: int = 10):
    """Receive the first ``state`` message from the /ws/training connect sequence.

    The connect handler unicasts three messages in order
    (connection_established → initial_status → state), but the demo backend's
    broadcast loop runs concurrently and can interleave ``metrics`` and
    ``state`` broadcasts at any ``await`` boundary in the handler. We therefore
    drain messages until we see both ``connection_established`` and
    ``initial_status`` and then return the next ``state`` message — silently
    skipping any interleaved ``metrics`` broadcasts. The required-message set
    is still asserted so a regression that drops one of them is surfaced.
    """
    saw_connection_established = False
    saw_initial_status = False
    for _ in range(max_messages):
        msg = websocket.receive_json()
        msg_type = msg.get("type")
        if msg_type == "connection_established":
            saw_connection_established = True
            continue
        if msg_type == "initial_status":
            saw_initial_status = True
            continue
        if msg_type == "state":
            assert saw_connection_established, "connection_established was not received before state"
            assert saw_initial_status, "initial_status was not received before state"
            return msg
        # Other types (e.g. demo broadcast 'metrics') are tolerated — keep draining.
    raise AssertionError(f"No 'state' message received within {max_messages} messages on /ws/training connect")


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


class TestReceiveStateMessageHelper:
    """Regression coverage for the ``_receive_state_message`` drain logic.

    The helper used to require the connect-time messages to land in a strict
    1-2-3 sequence (``connection_established`` → ``initial_status`` → ``state``).
    Demo broadcasts (``metrics``, periodic ``state``) interleave at the
    handler's ``await`` boundaries and would arrive in slot 2 or 3, which
    surfaced as flaky failures under load. The helper now drains intervening
    types until it sees the connect-time ``state`` message; these tests pin
    that contract.
    """

    def _make_fake_ws(self, scripted_messages):
        class _FakeWS:
            def __init__(self, msgs):
                self._msgs = list(msgs)

            def receive_json(self):
                if not self._msgs:
                    raise AssertionError("Test ran out of scripted messages")
                return self._msgs.pop(0)

        return _FakeWS(scripted_messages)

    def test_helper_returns_state_when_messages_arrive_in_order(self):
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "initial_status", "data": {}},
                {"type": "state", "data": {"status": "Stopped"}},
            ]
        )
        msg = _receive_state_message(ws)
        assert msg["type"] == "state"

    def test_helper_skips_interleaved_metrics_broadcast(self):
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "metrics", "data": {}},  # broadcast lands in slot 2
                {"type": "initial_status", "data": {}},
                {"type": "state", "data": {"status": "Started"}},
            ]
        )
        msg = _receive_state_message(ws)
        assert msg["type"] == "state"
        assert msg["data"]["status"] == "Started"

    def test_helper_skips_metrics_broadcast_in_slot_3(self):
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "initial_status", "data": {}},
                {"type": "metrics", "data": {}},  # broadcast preempts the connect-time state
                {"type": "state", "data": {"status": "Started"}},
            ]
        )
        msg = _receive_state_message(ws)
        assert msg["type"] == "state"

    def test_helper_raises_when_state_never_arrives(self):
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "initial_status", "data": {}},
                {"type": "metrics", "data": {}},
                {"type": "metrics", "data": {}},
            ]
        )
        with pytest.raises(AssertionError, match="No 'state' message received"):
            _receive_state_message(ws, max_messages=4)

    def test_helper_asserts_connect_message_was_seen(self):
        ws = self._make_fake_ws(
            [
                # connection_established is missing — the helper should still
                # raise rather than silently returning the state message,
                # because that would mask a real handler regression.
                {"type": "initial_status", "data": {}},
                {"type": "state", "data": {"status": "Stopped"}},
            ]
        )
        with pytest.raises(AssertionError, match="connection_established"):
            _receive_state_message(ws)
