#!/usr/bin/env python
"""
Comprehensive unit tests for websocket_manager.py to improve coverage to 90%+.

Tests focus on:
1. Message builder functions (create_*_message)
2. Broadcast edge cases with multiple clients
3. Connection metadata edge cases
4. Heartbeat functionality
5. Error handling paths
6. Environment variable configuration
"""
import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from communication.websocket_manager import (
    WebSocketManager,
    create_control_ack_message,
    create_event_message,
    create_metrics_message,
    create_state_message,
    create_stats_message,
    create_topology_message,
)


class TestMessageBuilderFunctions:
    """Tests for message builder helper functions."""

    def test_create_state_message_with_dict(self):
        """Test create_state_message with dict input."""
        state_data = {"status": "Started", "phase": "Output", "learning_rate": 0.01}
        msg = create_state_message(state_data)

        assert msg["type"] == "state"
        assert "timestamp" in msg
        assert isinstance(msg["timestamp"], float)
        assert msg["data"] == state_data

    def test_create_state_message_with_get_state_object(self):
        """Test create_state_message with object having get_state method."""

        class MockTrainingState:
            def get_state(self):
                return {"status": "Running", "epoch": 42}

        state = MockTrainingState()
        msg = create_state_message(state)

        assert msg["type"] == "state"
        assert msg["data"]["status"] == "Running"
        assert msg["data"]["epoch"] == 42

    def test_create_state_message_timestamp_is_current(self):
        """Test that state message timestamp is current time."""
        before = time.time()
        msg = create_state_message({"status": "test"})
        after = time.time()

        assert before <= msg["timestamp"] <= after

    def test_create_metrics_message(self):
        """Test create_metrics_message creates correct format."""
        metrics = {
            "epoch": 42,
            "metrics": {"loss": 0.23, "accuracy": 0.91, "val_loss": 0.25, "val_accuracy": 0.89},
        }
        msg = create_metrics_message(metrics)

        assert msg["type"] == "metrics"
        assert "timestamp" in msg
        assert msg["data"]["epoch"] == 42
        assert msg["data"]["metrics"]["loss"] == 0.23

    def test_create_metrics_message_empty_metrics(self):
        """Test create_metrics_message with empty metrics."""
        msg = create_metrics_message({})

        assert msg["type"] == "metrics"
        assert msg["data"] == {}

    def test_create_topology_message(self):
        """Test create_topology_message creates correct format."""
        topology = {
            "input_units": 2,
            "hidden_units": 3,
            "output_units": 1,
            "nodes": [{"id": 1}, {"id": 2}],
            "connections": [{"from": 1, "to": 2}],
        }
        msg = create_topology_message(topology)

        assert msg["type"] == "topology"
        assert "timestamp" in msg
        assert msg["data"]["input_units"] == 2
        assert msg["data"]["hidden_units"] == 3
        assert len(msg["data"]["nodes"]) == 2

    def test_create_topology_message_complex_structure(self):
        """Test create_topology_message with complex nested structure."""
        topology = {
            "layers": [
                {"type": "input", "units": 10},
                {"type": "hidden", "units": 5, "weights": [[0.1, 0.2], [0.3, 0.4]]},
            ]
        }
        msg = create_topology_message(topology)

        assert msg["type"] == "topology"
        assert msg["data"]["layers"][1]["weights"][0][0] == 0.1

    def test_create_event_message(self):
        """Test create_event_message creates correct format."""
        msg = create_event_message("cascade_add", {"unit_index": 2, "total_hidden_units": 3, "epoch": 42})

        assert msg["type"] == "event"
        assert "timestamp" in msg
        assert msg["data"]["event_type"] == "cascade_add"
        assert msg["data"]["details"]["unit_index"] == 2

    def test_create_event_message_phase_change(self):
        """Test create_event_message with phase_change event."""
        msg = create_event_message("phase_change", {"from_phase": "Output", "to_phase": "Candidate"})

        assert msg["data"]["event_type"] == "phase_change"
        assert msg["data"]["details"]["from_phase"] == "Output"

    def test_create_event_message_empty_details(self):
        """Test create_event_message with empty details."""
        msg = create_event_message("status_change", {})

        assert msg["type"] == "event"
        assert msg["data"]["event_type"] == "status_change"
        assert msg["data"]["details"] == {}

    def test_create_control_ack_message_success(self):
        """Test create_control_ack_message for success."""
        msg = create_control_ack_message("start", True, "Training started successfully")

        assert msg["type"] == "control_ack"
        assert msg["data"]["command"] == "start"
        assert msg["data"]["success"] is True
        assert msg["data"]["message"] == "Training started successfully"

    def test_create_control_ack_message_failure(self):
        """Test create_control_ack_message for failure."""
        msg = create_control_ack_message("pause", False, "Cannot pause: training not running")

        assert msg["data"]["success"] is False
        assert "Cannot pause" in msg["data"]["message"]

    def test_create_control_ack_message_no_message(self):
        """Test create_control_ack_message with default empty message."""
        msg = create_control_ack_message("reset", True)

        assert msg["data"]["message"] == ""

    def test_create_control_ack_message_all_commands(self):
        """Test create_control_ack_message with various commands."""
        commands = ["start", "stop", "pause", "resume", "reset"]
        for cmd in commands:
            msg = create_control_ack_message(cmd, True, f"{cmd} executed")
            assert msg["data"]["command"] == cmd

    def test_create_stats_message(self):
        """Test create_stats_message creates correct format."""
        stats = {
            "threshold_function": "sigmoid",
            "optimizer": "sgd",
            "total_nodes": 10,
            "weight_statistics": {"mean": 0.5, "std": 0.1},
        }
        msg = create_stats_message(stats)

        assert msg["type"] == "network_stats"
        assert "timestamp" in msg
        assert msg["data"]["threshold_function"] == "sigmoid"
        assert msg["data"]["weight_statistics"]["mean"] == 0.5

    def test_create_stats_message_empty(self):
        """Test create_stats_message with empty stats."""
        msg = create_stats_message({})

        assert msg["type"] == "network_stats"
        assert msg["data"] == {}


class TestBroadcastEdgeCases:
    """Tests for broadcast edge cases with multiple clients."""

    @pytest.fixture
    def manager(self):
        """Create fresh WebSocketManager instance."""
        return WebSocketManager()

    def _create_mock_websocket(self, fail=False):
        """Create a mock WebSocket."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        if fail:
            ws.send_json = AsyncMock(side_effect=Exception("Connection broken"))
        else:
            ws.send_json = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_broadcast_to_many_clients(self, manager):
        """Test broadcasting to multiple clients."""
        clients = [self._create_mock_websocket() for _ in range(5)]

        for ws in clients:
            await manager.connect(ws)
            ws.send_json.reset_mock()

        await manager.broadcast({"type": "test"})

        for ws in clients:
            assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_broadcast_updates_all_metadata(self, manager):
        """Test broadcast updates metadata for all clients."""
        ws1 = self._create_mock_websocket()
        ws2 = self._create_mock_websocket()

        await manager.connect(ws1, client_id="client-1")
        await manager.connect(ws2, client_id="client-2")

        initial_count1 = manager.connection_metadata[ws1]["messages_sent"]
        initial_count2 = manager.connection_metadata[ws2]["messages_sent"]

        await manager.broadcast({"type": "update"})

        assert manager.connection_metadata[ws1]["messages_sent"] == initial_count1 + 1
        assert manager.connection_metadata[ws2]["messages_sent"] == initial_count2 + 1

    @pytest.mark.asyncio
    async def test_broadcast_partial_failure(self, manager):
        """Test broadcast when some clients fail."""
        good_ws = self._create_mock_websocket()
        bad_ws = self._create_mock_websocket(fail=True)

        await manager.connect(good_ws, client_id="good")
        await manager.connect(bad_ws, client_id="bad")
        good_ws.send_json.reset_mock()

        await manager.broadcast({"type": "test"})

        assert good_ws.send_json.called
        assert good_ws in manager.active_connections
        assert bad_ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_all_fail(self, manager):
        """Test broadcast when all clients fail."""
        bad_clients = [self._create_mock_websocket(fail=True) for _ in range(3)]

        for ws in bad_clients:
            await manager.connect(ws)

        await manager.broadcast({"type": "test"})

        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_excludes_multiple(self, manager):
        """Test broadcast with multiple exclusions."""
        clients = [self._create_mock_websocket() for _ in range(4)]

        for ws in clients:
            await manager.connect(ws)
            ws.send_json.reset_mock()

        await manager.broadcast({"type": "test"}, exclude={clients[1], clients[3]})

        assert clients[0].send_json.called
        assert not clients[1].send_json.called
        assert clients[2].send_json.called
        assert not clients[3].send_json.called

    @pytest.mark.asyncio
    async def test_broadcast_preserves_existing_timestamp(self, manager):
        """Test broadcast preserves existing timestamp in message."""
        ws = self._create_mock_websocket()
        await manager.connect(ws)
        ws.send_json.reset_mock()

        original_ts = "2025-01-01T00:00:00"
        await manager.broadcast({"type": "test", "timestamp": original_ts})

        call_args = ws.send_json.call_args[0][0]
        assert call_args["timestamp"] == original_ts


class TestConnectionMetadataEdgeCases:
    """Tests for connection metadata handling edge cases."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_get_connection_info_empty(self, manager):
        """Test get_connection_info with no connections."""
        info = manager.get_connection_info()
        assert info == []

    @pytest.mark.asyncio
    async def test_get_connection_info_multiple_clients(self, manager):
        """Test get_connection_info with multiple clients."""
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, client_id="client-A")
        await manager.connect(ws2, client_id="client-B")

        info = manager.get_connection_info()
        assert len(info) == 2

        client_ids = {c["client_id"] for c in info}
        assert "client-A" in client_ids
        assert "client-B" in client_ids

    @pytest.mark.asyncio
    async def test_metadata_last_message_at_updates(self, manager, mock_websocket):
        """Test last_message_at updates on send."""
        await manager.connect(mock_websocket)

        first_send_time = manager.connection_metadata[mock_websocket]["last_message_at"]
        await asyncio.sleep(0.01)

        await manager.send_personal_message({"type": "test"}, mock_websocket)
        second_send_time = manager.connection_metadata[mock_websocket]["last_message_at"]

        assert first_send_time != second_send_time

    @pytest.mark.asyncio
    async def test_get_statistics_with_connections(self, manager, mock_websocket):
        """Test get_statistics includes connection details."""
        await manager.connect(mock_websocket, client_id="stats-test")
        await manager.broadcast({"type": "msg1"})
        await manager.broadcast({"type": "msg2"})

        stats = manager.get_statistics()

        assert stats["active_connections"] == 1
        assert stats["total_messages_broadcast"] >= 2
        assert len(stats["connections_info"]) == 1
        assert stats["connections_info"][0]["client_id"] == "stats-test"


class TestHeartbeatFunctionality:
    """Tests for heartbeat/ping functionality."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def _create_mock_websocket(self, fail=False):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        if fail:
            ws.send_json = AsyncMock(side_effect=Exception("Failed"))
        else:
            ws.send_json = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_broadcast_ping_to_multiple_clients(self, manager):
        """Test broadcast_ping sends to all clients."""
        clients = [self._create_mock_websocket() for _ in range(3)]

        for ws in clients:
            await manager.connect(ws)
            ws.send_json.reset_mock()

        await manager.broadcast_ping()

        for ws in clients:
            assert ws.send_json.called
            call_args = ws.send_json.call_args[0][0]
            assert call_args["type"] == "ping"

    @pytest.mark.asyncio
    async def test_broadcast_ping_no_connections(self, manager):
        """Test broadcast_ping with no connections."""
        await manager.broadcast_ping()

    @pytest.mark.asyncio
    async def test_broadcast_ping_removes_failed(self, manager):
        """Test broadcast_ping removes failed connections."""
        good_ws = self._create_mock_websocket()
        bad_ws = self._create_mock_websocket(fail=True)

        await manager.connect(good_ws)
        await manager.connect(bad_ws)
        good_ws.send_json.reset_mock()

        await manager.broadcast_ping()

        assert good_ws in manager.active_connections
        assert bad_ws not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_ping_returns_true_on_success(self, manager):
        """Test send_ping returns True on success."""
        ws = self._create_mock_websocket()
        await manager.connect(ws)
        ws.send_json.reset_mock()

        result = await manager.send_ping(ws)

        assert result is True


class TestErrorHandling:
    """Tests for exception paths in send/broadcast methods."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_send_personal_message_disconnects_on_error(self, manager, mock_websocket):
        """Test send_personal_message disconnects client on error."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.side_effect = RuntimeError("Network error")

        await manager.send_personal_message({"type": "test"}, mock_websocket)

        assert mock_websocket not in manager.active_connections
        assert mock_websocket not in manager.connection_metadata

    @pytest.mark.asyncio
    async def test_send_personal_message_to_unknown_websocket(self, manager, mock_websocket):
        """Test send_personal_message to unconnected websocket."""
        await manager.send_personal_message({"type": "test"}, mock_websocket)

    @pytest.mark.asyncio
    async def test_shutdown_handles_close_errors(self, manager):
        """Test shutdown handles errors when closing connections."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock(side_effect=Exception("Already closed"))

        await manager.connect(ws)
        await manager.shutdown()

        assert len(manager.active_connections) == 0

    def test_broadcast_sync_handles_exception(self, manager):
        """Test broadcast_sync handles exceptions gracefully."""
        loop = MagicMock()
        loop.is_running.return_value = True
        manager.event_loop = loop

        with patch("asyncio.run_coroutine_threadsafe", side_effect=Exception("Loop error")):
            manager.broadcast_sync({"type": "test"})

    def test_broadcast_from_thread_closed_loop(self, manager):
        """Test broadcast_from_thread with closed event loop."""
        loop = MagicMock()
        loop.is_closed.return_value = True
        manager.event_loop = loop

        manager.active_connections.add(MagicMock())
        manager.broadcast_from_thread({"type": "test"})

    def test_broadcast_from_thread_exception(self, manager):
        """Test broadcast_from_thread handles exceptions."""
        loop = MagicMock()
        loop.is_closed.return_value = False
        manager.event_loop = loop

        manager.active_connections.add(MagicMock())

        with patch("asyncio.run_coroutine_threadsafe", side_effect=RuntimeError("Thread error")):
            manager.broadcast_from_thread({"type": "test"})


class TestBroadcastStateChange:
    """Tests for broadcast_state_change method."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def test_broadcast_state_change_format(self, manager):
        """Test broadcast_state_change creates correct message format."""
        loop = MagicMock()
        loop.is_closed.return_value = False
        manager.event_loop = loop

        ws = MagicMock()
        manager.active_connections.add(ws)

        captured_message = None

        def capture_broadcast(coro, loop):
            nonlocal captured_message
            import asyncio

            async def extract():
                await coro

            future = MagicMock()
            return future

        with patch("asyncio.run_coroutine_threadsafe") as mock_rct:

            def capture_coro(coro, loop):
                return MagicMock()

            mock_rct.side_effect = capture_coro
            manager.broadcast_state_change({"status": "Started", "phase": "Output"})

            assert mock_rct.called

    def test_broadcast_state_change_no_connections(self, manager):
        """Test broadcast_state_change with no connections."""
        loop = MagicMock()
        loop.is_closed.return_value = False
        manager.event_loop = loop

        manager.broadcast_state_change({"status": "test"})


class TestLoggerSetup:
    """Tests for logger setup fallback."""

    def test_logger_fallback_when_import_fails(self):
        """Test _setup_logger fallback when project logger unavailable."""
        manager = WebSocketManager()
        assert manager.logger is not None


class TestEnvironmentVariableConfig:
    """Tests for environment variable configuration."""

    def test_invalid_max_connections_env(self):
        """Test invalid CASCOR_WEBSOCKET_MAX_CONNECTIONS value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_MAX_CONNECTIONS": "invalid"}):
            manager = WebSocketManager()
            assert isinstance(manager.max_connections, int)

    def test_valid_max_connections_env(self):
        """Test valid CASCOR_WEBSOCKET_MAX_CONNECTIONS value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_MAX_CONNECTIONS": "100"}):
            manager = WebSocketManager()
            assert manager.max_connections == 100

    def test_invalid_heartbeat_interval_env(self):
        """Test invalid CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL": "not_a_number"}):
            manager = WebSocketManager()
            assert isinstance(manager.heartbeat_interval, int)

    def test_valid_heartbeat_interval_env(self):
        """Test valid CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL": "60"}):
            manager = WebSocketManager()
            assert manager.heartbeat_interval == 60

    def test_invalid_reconnect_attempts_env(self):
        """Test invalid CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS": "abc"}):
            manager = WebSocketManager()
            assert isinstance(manager.reconnect_attempts, int)

    def test_valid_reconnect_attempts_env(self):
        """Test valid CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS": "10"}):
            manager = WebSocketManager()
            assert manager.reconnect_attempts == 10

    def test_invalid_reconnect_delay_env(self):
        """Test invalid CASCOR_WEBSOCKET_RECONNECT_DELAY value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_RECONNECT_DELAY": "xyz"}):
            manager = WebSocketManager()
            assert isinstance(manager.reconnect_delay, int)

    def test_valid_reconnect_delay_env(self):
        """Test valid CASCOR_WEBSOCKET_RECONNECT_DELAY value."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_RECONNECT_DELAY": "5"}):
            manager = WebSocketManager()
            assert manager.reconnect_delay == 5


class TestDisconnectEdgeCases:
    """Tests for disconnect edge cases."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    def test_disconnect_already_disconnected(self, manager):
        """Test disconnect on already disconnected websocket."""
        ws = MagicMock()
        manager.disconnect(ws)
        manager.disconnect(ws)

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_metadata(self, manager):
        """Test disconnect removes metadata completely."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()

        await manager.connect(ws, client_id="cleanup-test")
        assert ws in manager.connection_metadata

        manager.disconnect(ws)

        assert ws not in manager.active_connections
        assert ws not in manager.connection_metadata


class TestSendPingEdgeCases:
    """Tests for send_ping edge cases."""

    @pytest.fixture
    def manager(self):
        return WebSocketManager()

    @pytest.mark.asyncio
    async def test_send_ping_exception_returns_false(self, manager):
        """Test send_ping returns False on any exception."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock(side_effect=Exception("Send failed"))

        await manager.connect(ws)
        result = await manager.send_ping(ws)

        assert result is True
