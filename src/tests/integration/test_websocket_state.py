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

# Stamped by the ``test_client`` fixture on every frame that leaves through
# ``WebSocketManager.broadcast``. The /ws/training connect handler's own frames are
# unicasts (``send_personal_message``) and never carry it, so a test can tell the
# connect-time ``state`` from a demo-loop ``state`` broadcast that merely arrived
# first. Test-only: production payloads are untouched.
_BROADCAST_MARKER = "_test_via_broadcast"

# The frames the connect handler unicasts, in the order it sends them.
_CONNECT_SEQUENCE = ["connection_established", "initial_status", "state"]


@pytest.fixture
def test_client(monkeypatch):
    """Create test client for FastAPI app.

    Enters the TestClient as a context manager so FastAPI's lifespan runs and
    initializes the module-level `backend` global in main.py. Without the
    context-manager entry, the /ws/training handler's `backend.get_status()`
    call hits a None and every test in this file fails with
    `AttributeError: 'NoneType' object has no attribute 'get_status'`.

    Also tags every broadcast frame with ``_BROADCAST_MARKER``; see
    ``_receive_state_message`` for why the helper has to tell a broadcast from a
    connect-time unicast. Patched on the class, so the demo thread's
    ``broadcast_from_thread`` -> ``self.broadcast`` path is tagged too, and
    ``monkeypatch`` restores the original after the lifespan has shut down.
    """
    from communication.websocket_manager import WebSocketManager
    from main import app

    real_broadcast = WebSocketManager.broadcast

    async def _tagged_broadcast(self, message, *args, **kwargs):
        return await real_broadcast(self, {**message, _BROADCAST_MARKER: True}, *args, **kwargs)

    monkeypatch.setattr(WebSocketManager, "broadcast", _tagged_broadcast)

    with TestClient(app) as client:
        yield client


def _receive_state_message(websocket, max_messages: int = 20):
    """Return the connect-time ``state`` frame from the /ws/training connect sequence.

    The connect handler (``main.websocket_training_endpoint``) unicasts three frames,
    strictly in this order on the socket: ``connection_established`` (inside
    ``websocket_manager.connect()``), ``initial_status``, then ``state``. That order
    is what this helper asserts, exactly.

    It asserts nothing about broadcasts, because the server does not order them
    against the connect sequence. ``connect()`` adds the socket to the broadcast set
    *before* the handler awaits ``offload(backend.get_status)`` -- a thread hop since
    X7 slice 1a (#567) -- and every demo broadcast queued during that hop is
    delivered first, so a complete ``metrics`` + ``state`` broadcast pair can precede
    ``initial_status``. That is the scheduled-lane failure of 2026-09-22 (run
    35694265700): the previous helper took the first ``state`` it saw for the
    connect-time one and failed there, at roughly 7% of runs locally.

    Broadcasts are recognised by ``_BROADCAST_MARKER`` and skipped, so the check is
    exact rather than heuristic: a broadcast ``state`` can neither fail it (by arriving
    early) nor satisfy it (by standing in for a connect-time ``state`` the handler
    never sent). Unmarked frames outside the connect sequence are ignored.
    ``max_messages`` is only a liveness bound; marked frames count toward it.
    """
    unicast = []
    skipped = []
    for _ in range(max_messages):
        msg = websocket.receive_json()
        msg_type = msg.get("type")
        if msg.get(_BROADCAST_MARKER) or msg_type not in _CONNECT_SEQUENCE:
            skipped.append(msg_type)
            continue
        unicast.append(msg_type)
        if msg_type == "state":
            assert unicast[0] == "connection_established", f"connection_established was not received before state (connect-time unicast order: {unicast})"
            assert "initial_status" in unicast, f"initial_status was not received before the connect-time state (unicast order: {unicast}; skipped broadcast/other frames: {skipped})"
            assert unicast == _CONNECT_SEQUENCE, f"connect-time unicasts out of order: {unicast}, expected {_CONNECT_SEQUENCE}"
            return msg
    raise AssertionError(f"No 'state' message received within {max_messages} messages on /ws/training connect (connect-time unicasts seen: {unicast}; skipped broadcast/other frames: {skipped})")


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

    def test_fixture_tags_broadcast_frames_and_not_connect_unicasts(self, test_client):
        """Instrument guard: the broadcast tag must reach the wire, and only on broadcasts.

        ``_receive_state_message`` is exact only while every broadcast carries
        ``_BROADCAST_MARKER``. If the tagging stopped taking effect (the demo loop
        moving off ``WebSocketManager.broadcast``, say), broadcast frames would pass
        as connect-time unicasts and the 2026-09-22 flake would come back silently.
        The demo loop broadcasts continuously, so a tagged frame must turn up.
        """
        with test_client.websocket_connect("/ws/training") as websocket:
            seen = []
            for _ in range(40):
                msg = websocket.receive_json()
                seen.append((msg.get("type"), bool(msg.get(_BROADCAST_MARKER))))
                if msg.get(_BROADCAST_MARKER):
                    break

        assert any(tagged for _, tagged in seen), f"no broadcast frame carried {_BROADCAST_MARKER!r}; frames seen: {seen}"
        assert not any(tagged for msg_type, tagged in seen if msg_type in ("connection_established", "initial_status")), f"a connect-time unicast carried the broadcast tag: {seen}"


# Marked so the CI integration lane (``-m "integration and ..."``) selects this class;
# unmarked, it was deselected by every lane and never ran in CI.
@pytest.mark.integration
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


# Marked for the same reason as ``TestWebSocketStateMessageContent``: these pin the
# helper's contract and must run in the integration lane, not only locally.
@pytest.mark.integration
class TestReceiveStateMessageHelper:
    """Regression coverage for the ``_receive_state_message`` drain logic.

    The helper first required a strict 1-2-3 sequence (``connection_established`` ->
    ``initial_status`` -> ``state``) and flaked when a demo ``metrics`` broadcast took
    slot 2 or 3. It then drained intervening types but still took the FIRST ``state``
    for the connect-time one, so a demo ``state`` broadcast landing before
    ``initial_status`` failed it (the 2026-09-22 scheduled-lane failure) -- while a
    broadcast ``state`` arriving after ``initial_status`` could stand in for a
    connect-time ``state`` the handler never sent. It now skips frames tagged
    ``_BROADCAST_MARKER`` and asserts the exact connect-time unicast order.
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

    def test_helper_skips_broadcast_state_that_precedes_initial_status(self):
        """The 2026-09-22 scheduled-lane shape: a whole demo broadcast pair lands before initial_status."""
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "metrics", "data": {}, _BROADCAST_MARKER: True},
                {"type": "state", "data": {"status": "from-broadcast"}, _BROADCAST_MARKER: True},
                {"type": "initial_status", "data": {}},
                {"type": "state", "data": {"status": "Started"}},
            ]
        )
        msg = _receive_state_message(ws)
        assert msg["data"]["status"] == "Started"  # the connect-time unicast, not the broadcast

    def test_helper_rejects_a_connect_time_state_sent_before_initial_status(self):
        """The handler sending its OWN state before initial_status is a real ordering defect and must fail."""
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "state", "data": {"status": "Started"}},
                {"type": "initial_status", "data": {}},
            ]
        )
        with pytest.raises(AssertionError, match="initial_status was not received before the connect-time state"):
            _receive_state_message(ws)

    def test_helper_does_not_accept_a_broadcast_state_in_place_of_the_connect_time_state(self):
        """If the handler never sends its connect-time state, a later broadcast state must not stand in for it."""
        ws = self._make_fake_ws(
            [
                {"type": "connection_established"},
                {"type": "initial_status", "data": {}},
                {"type": "metrics", "data": {}, _BROADCAST_MARKER: True},
                {"type": "state", "data": {"status": "Started"}, _BROADCAST_MARKER: True},
            ]
        )
        with pytest.raises(AssertionError, match="No 'state' message received"):
            _receive_state_message(ws, max_messages=4)
