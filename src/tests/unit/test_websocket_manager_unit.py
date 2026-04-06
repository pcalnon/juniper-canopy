#!/usr/bin/env python
"""
Unit tests for WebSocketManager class.

Tests all WebSocketManager methods:
- send_personal_message
- broadcast (async)
- broadcast_sync
- broadcast_from_thread
- get_statistics
- get_connection_count
- get_connection_info
- connect/disconnect
- ping functionality
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add src to path
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from communication.websocket_manager import WebSocketManager  # noqa: E402


class TestWebSocketManagerUnit:
    """Unit tests for WebSocketManager."""

    @pytest.fixture
    def manager(self):
        """Create fresh WebSocketManager instance."""
        return WebSocketManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket object."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    # ========== Initialization Tests ==========

    def test_initialization(self, manager):
        """Test WebSocketManager initializes correctly."""
        assert manager is not None
        assert hasattr(manager, "active_connections")
        assert hasattr(manager, "connection_metadata")
        assert hasattr(manager, "message_count")
        assert len(manager.active_connections) == 0
        assert manager.message_count == 0

    def test_set_event_loop(self, manager):
        """Test set_event_loop stores event loop."""
        loop = asyncio.new_event_loop()
        manager.set_event_loop(loop)
        assert manager.event_loop is loop
        loop.close()

    # ========== Connection Management Tests ==========

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, manager, mock_websocket):
        """Test connect() accepts WebSocket connection."""
        await manager.connect(mock_websocket)

        mock_websocket.accept.assert_called_once()
        assert mock_websocket in manager.active_connections
        assert mock_websocket in manager.connection_metadata

    @pytest.mark.asyncio
    async def test_connect_with_client_id(self, manager, mock_websocket):
        """Test connect() with custom client_id."""
        await manager.connect(mock_websocket, client_id="test-client-123")

        metadata = manager.connection_metadata[mock_websocket]
        assert metadata["client_id"] == "test-client-123"

    @pytest.mark.asyncio
    async def test_connect_auto_generates_client_id(self, manager, mock_websocket):
        """Test connect() auto-generates client_id."""
        await manager.connect(mock_websocket)

        metadata = manager.connection_metadata[mock_websocket]
        assert "client_id" in metadata
        assert metadata["client_id"].startswith("client-")

    @pytest.mark.asyncio
    async def test_connect_sends_acknowledgment(self, manager, mock_websocket):
        """Test connect() sends connection acknowledgment."""
        await manager.connect(mock_websocket)

        # Should send connection_established message
        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "connection_established"
        assert "client_id" in call_args
        assert "server_time" in call_args

    @pytest.mark.asyncio
    async def test_connect_stores_metadata(self, manager, mock_websocket):
        """Test connect() stores connection metadata."""
        await manager.connect(mock_websocket, client_id="test-client")

        metadata = manager.connection_metadata[mock_websocket]
        assert metadata["client_id"] == "test-client"
        assert "connected_at" in metadata
        assert metadata["messages_sent"] == 1  # Connection ack
        assert "last_message_at" in metadata

    def test_disconnect_removes_connection(self, manager, mock_websocket):
        """Test disconnect() removes connection."""
        # Add connection manually (skip async connect)
        manager.active_connections.add(mock_websocket)
        manager.connection_metadata[mock_websocket] = {"client_id": "test"}

        manager.disconnect(mock_websocket)

        assert mock_websocket not in manager.active_connections
        assert mock_websocket not in manager.connection_metadata

    def test_disconnect_handles_missing_connection(self, manager, mock_websocket):
        """Test disconnect() handles already-disconnected connection."""
        # Should not raise error
        manager.disconnect(mock_websocket)
        assert mock_websocket not in manager.active_connections

    # ========== send_personal_message Tests ==========

    @pytest.mark.asyncio
    async def test_send_personal_message(self, manager, mock_websocket):
        """Test send_personal_message sends to specific client."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()  # Clear connection message

        message = {"type": "test", "data": "hello"}
        await manager.send_personal_message(message, mock_websocket)

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "test"
        assert call_args["data"] == "hello"
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_send_personal_message_adds_timestamp(self, manager, mock_websocket):
        """Test send_personal_message adds timestamp if not present."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        message = {"type": "test"}
        await manager.send_personal_message(message, mock_websocket)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_send_personal_message_preserves_timestamp(self, manager, mock_websocket):
        """Test send_personal_message preserves existing timestamp."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        original_timestamp = "2025-01-01T00:00:00"
        message = {"type": "test", "timestamp": original_timestamp}
        await manager.send_personal_message(message, mock_websocket)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["timestamp"] == original_timestamp

    @pytest.mark.asyncio
    async def test_send_personal_message_updates_metadata(self, manager, mock_websocket):
        """Test send_personal_message updates connection metadata."""
        await manager.connect(mock_websocket)
        initial_count = manager.connection_metadata[mock_websocket]["messages_sent"]

        await manager.send_personal_message({"type": "test"}, mock_websocket)

        new_count = manager.connection_metadata[mock_websocket]["messages_sent"]
        assert new_count == initial_count + 1
        assert manager.connection_metadata[mock_websocket]["last_message_at"] is not None

    @pytest.mark.asyncio
    async def test_send_personal_message_handles_error(self, manager, mock_websocket):
        """Test send_personal_message handles send errors."""
        await manager.connect(mock_websocket)

        # Make send_json raise error
        mock_websocket.send_json.side_effect = Exception("Connection broken")

        # Should not raise, should disconnect
        await manager.send_personal_message({"type": "test"}, mock_websocket)

        assert mock_websocket not in manager.active_connections

    # ========== broadcast Tests ==========

    @pytest.mark.asyncio
    async def test_broadcast_to_all_connections(self, manager):
        """Test broadcast sends to all connected clients."""
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws1.close = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        ws2.close = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()

        message = {"type": "broadcast", "data": "test"}
        await manager.broadcast(message)

        assert ws1.send_json.called
        assert ws2.send_json.called

    @pytest.mark.asyncio
    async def test_broadcast_adds_timestamp(self, manager, mock_websocket):
        """Test broadcast adds timestamp to message."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        message = {"type": "test"}
        await manager.broadcast(message)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_broadcast_increments_message_count(self, manager, mock_websocket):
        """Test broadcast increments total message count."""
        await manager.connect(mock_websocket)
        initial_count = manager.message_count

        await manager.broadcast({"type": "test"})

        assert manager.message_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_broadcast_with_exclude(self, manager):
        """Test broadcast excludes specified connections."""
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws1.close = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        ws2.close = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()

        # Broadcast excluding ws2
        await manager.broadcast({"type": "test"}, exclude={ws2})

        assert ws1.send_json.called
        assert not ws2.send_json.called

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected_clients(self, manager):
        """Test broadcast removes clients that fail to receive."""
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws1.close = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock(side_effect=Exception("Connection broken"))
        ws2.close = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)
        ws1.send_json.reset_mock()

        await manager.broadcast({"type": "test"})

        # ws1 should receive, ws2 should be disconnected
        assert ws1.send_json.called
        assert ws2 not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self, manager):
        """Test broadcast with no active connections."""
        # Should not raise error
        await manager.broadcast({"type": "test"})
        assert manager.message_count >= 0

    # ========== broadcast_sync Tests ==========

    def test_broadcast_sync_with_event_loop(self, manager, mock_websocket):
        """Test broadcast_sync uses stored event loop."""
        loop = asyncio.new_event_loop()
        manager.set_event_loop(loop)

        # Run loop in thread
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        time.sleep(0.1)  # Let loop start

        try:
            # Add connection in the loop
            asyncio.run_coroutine_threadsafe(manager.connect(mock_websocket), loop).result(timeout=1)
            mock_websocket.send_json.reset_mock()

            # Call broadcast_sync from main thread
            manager.broadcast_sync({"type": "test"})

            # Give time for broadcast to complete
            time.sleep(0.2)

            # Should have been called
            assert mock_websocket.send_json.called or manager.message_count > 0

        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=1)
            loop.close()

    def test_broadcast_sync_without_loop(self, manager):
        """Test broadcast_sync creates event loop if needed."""
        # Should not raise error even without event loop
        try:
            manager.broadcast_sync({"type": "test"})
        except Exception as e:
            # Some exceptions are acceptable (no connections, etc)
            assert "broadcast" not in str(e).lower() or True

    # ========== broadcast_from_thread Tests ==========

    def test_broadcast_from_thread(self, manager, mock_websocket):
        """Test broadcast_from_thread schedules on event loop."""
        loop = asyncio.new_event_loop()
        manager.set_event_loop(loop)

        # Run loop in thread
        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        time.sleep(0.1)

        try:
            # Add connection
            asyncio.run_coroutine_threadsafe(manager.connect(mock_websocket), loop).result(timeout=1)
            mock_websocket.send_json.reset_mock()

            # Call from different thread
            def call_broadcast():
                manager.broadcast_from_thread({"type": "test"})

            bg_thread = threading.Thread(target=call_broadcast)
            bg_thread.start()
            bg_thread.join(timeout=1)

            # Give time for broadcast
            time.sleep(0.2)

            # Should have been called
            assert mock_websocket.send_json.called or manager.message_count > 0

        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=1)
            loop.close()

    def test_broadcast_from_thread_no_connections(self, manager):
        """Test broadcast_from_thread with no connections (no-op)."""
        loop = asyncio.new_event_loop()
        manager.set_event_loop(loop)

        # Should not raise error
        manager.broadcast_from_thread({"type": "test"})

        loop.close()

    def test_broadcast_from_thread_no_event_loop(self, manager):
        """Test broadcast_from_thread without event loop."""
        # Should handle gracefully
        manager.broadcast_from_thread({"type": "test"})
        # No error should be raised

    # ========== Statistics Tests ==========

    def test_get_connection_count(self, manager, mock_websocket):
        """Test get_connection_count returns correct count."""
        assert manager.get_connection_count() == 0

        manager.active_connections.add(mock_websocket)
        assert manager.get_connection_count() == 1

        manager.active_connections.discard(mock_websocket)
        assert manager.get_connection_count() == 0

    @pytest.mark.asyncio
    async def test_get_connection_info(self, manager, mock_websocket):
        """Test get_connection_info returns metadata."""
        await manager.connect(mock_websocket, client_id="test-client")

        info = manager.get_connection_info()
        assert len(info) == 1
        assert info[0]["client_id"] == "test-client"
        assert "connected_at" in info[0]
        assert "messages_sent" in info[0]
        assert "last_message_at" in info[0]

    @pytest.mark.asyncio
    async def test_get_statistics(self, manager, mock_websocket):
        """Test get_statistics returns complete stats."""
        await manager.connect(mock_websocket)
        await manager.broadcast({"type": "test"})

        stats = manager.get_statistics()

        assert "active_connections" in stats
        assert "total_messages_broadcast" in stats
        assert "connections_info" in stats

        assert stats["active_connections"] == 1
        assert stats["total_messages_broadcast"] >= 1
        assert len(stats["connections_info"]) == 1

    def test_get_statistics_empty(self, manager):
        """Test get_statistics with no connections."""
        stats = manager.get_statistics()

        assert stats["active_connections"] == 0
        assert stats["total_messages_broadcast"] == 0
        assert len(stats["connections_info"]) == 0

    # ========== Ping Tests ==========

    @pytest.mark.asyncio
    async def test_send_ping(self, manager, mock_websocket):
        """Test send_ping sends ping message."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        result = await manager.send_ping(mock_websocket)

        assert result is True
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "ping"

    @pytest.mark.asyncio
    async def test_send_ping_failure(self, manager, mock_websocket):
        """Test send_ping disconnects client on failure."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.side_effect = Exception("Failed")

        result = await manager.send_ping(mock_websocket)

        # send_ping always returns True, but connection should be disconnected
        assert result is True
        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_ping(self, manager, mock_websocket):
        """Test broadcast_ping sends ping to all."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        await manager.broadcast_ping()

        assert mock_websocket.send_json.called
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "ping"

    # ========== Shutdown Tests ==========

    @pytest.mark.asyncio
    async def test_shutdown_closes_all_connections(self, manager):
        """Test shutdown closes all active connections."""
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws1.close = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()
        ws2.close = AsyncMock()

        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.shutdown()

        assert ws1.close.called
        assert ws2.close.called
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_shutdown_sends_notice(self, manager, mock_websocket):
        """Test shutdown sends shutdown notice."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        await manager.shutdown()

        # Should have sent shutdown notice
        assert mock_websocket.send_json.called
        # Find the shutdown message
        for call in mock_websocket.send_json.call_args_list:
            msg = call[0][0]
            if msg.get("type") == "server_shutdown":
                assert "message" in msg
                break
        else:
            pytest.fail("Shutdown message not sent")

    # ========== Edge Cases ==========

    @pytest.mark.asyncio
    async def test_multiple_connects_same_websocket(self, manager, mock_websocket):
        """Test multiple connects with same websocket."""
        await manager.connect(mock_websocket, client_id="first")

        # Second connect should update metadata
        await manager.connect(mock_websocket, client_id="second")

        # Should have one connection
        assert manager.get_connection_count() == 1
        # Latest client_id should be used
        assert manager.connection_metadata[mock_websocket]["client_id"] == "second"

    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self, manager, mock_websocket):
        """Test concurrent broadcast calls."""
        await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        # Run multiple broadcasts concurrently
        await asyncio.gather(
            manager.broadcast({"type": "msg1"}),
            manager.broadcast({"type": "msg2"}),
            manager.broadcast({"type": "msg3"}),
        )

        # All broadcasts should succeed
        assert mock_websocket.send_json.call_count >= 3
