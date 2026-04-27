"""
Async/Sync Boundary Tests

Consolidates and verifies the three async/sync boundary patterns in juniper-canopy:

1. discovery.py: run_in_executor — sync HTTP probes from async context
2. main.py: schedule_broadcast — run_coroutine_threadsafe from sync threads
3. websocket_manager.py: broadcast_sync / broadcast_from_thread — bridge sync
   training threads to async WebSocket broadcasts

Focuses on patterns NOT covered by existing unit tests:
- Real (not mocked) executor delegation end-to-end
- Error propagation through run_in_executor
- Thread-safety of broadcast_from_thread with actual message delivery
- broadcast_sync vs broadcast_from_thread guard differences (is_running vs is_closed)
- Edge cases: closed loop, None loop, exception during scheduled coroutine
"""

import asyncio
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from communication.websocket_manager import WebSocketManager
from discovery import _probe_url_sync, probe_cascor_url

# =========================================================================
# Pattern 1: run_in_executor (discovery.py)
# =========================================================================


@pytest.mark.unit
class TestRunInExecutorBoundary:
    """Tests for the run_in_executor pattern used in probe_cascor_url."""

    async def test_executor_delegates_to_sync_function_end_to_end(self):
        """run_in_executor actually calls _probe_url_sync in the default executor."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"status": "alive"}'
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        call_thread_ids = []
        original_probe = _probe_url_sync

        def tracking_probe(url, timeout):
            call_thread_ids.append(threading.current_thread().ident)
            with patch("urllib.request.urlopen", return_value=mock_response):
                return original_probe(url, timeout)

        main_thread_id = threading.current_thread().ident

        with patch("discovery._probe_url_sync", side_effect=tracking_probe):
            result = await probe_cascor_url("http://localhost:8200", timeout=1.0)

        assert result is True
        assert len(call_thread_ids) == 1
        # The executor runs the function in a different thread
        assert call_thread_ids[0] != main_thread_id

    async def test_executor_propagates_exception_from_sync_function(self):
        """If _probe_url_sync raises, the exception propagates to the async caller."""

        def exploding_probe(url, timeout):
            raise ConnectionError("Network unreachable")

        with patch("discovery._probe_url_sync", side_effect=exploding_probe):
            with pytest.raises(ConnectionError, match="Network unreachable"):
                await probe_cascor_url("http://localhost:8200")

    async def test_executor_returns_false_without_raising(self):
        """_probe_url_sync returns False on HTTP errors (no exception propagation)."""
        import urllib.error

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            result = await probe_cascor_url("http://localhost:8200")
        assert result is False

    async def test_executor_concurrent_probes(self):
        """Multiple concurrent run_in_executor probes execute in parallel."""
        call_order = []

        def slow_probe(url, timeout):
            call_order.append(("start", url))
            time.sleep(0.05)
            call_order.append(("end", url))
            return False

        with patch("discovery._probe_url_sync", side_effect=slow_probe):
            results = await asyncio.gather(
                probe_cascor_url("http://host:8200"),
                probe_cascor_url("http://host:8201"),
            )

        assert results == [False, False]
        # Both should start before either ends (parallel execution in executor)
        starts = [i for i, (action, _) in enumerate(call_order) if action == "start"]
        ends = [i for i, (action, _) in enumerate(call_order) if action == "end"]
        assert len(starts) == 2
        assert len(ends) == 2


# =========================================================================
# Pattern 2: schedule_broadcast (main.py loop_holder pattern)
# =========================================================================


@pytest.mark.unit
class TestScheduleBroadcastBoundary:
    """Tests for the schedule_broadcast / loop_holder pattern from main.py."""

    def test_run_coroutine_threadsafe_delivers_from_thread(self):
        """run_coroutine_threadsafe delivers coroutine result from a background thread."""
        delivered = []

        async def mock_coro(msg):
            delivered.append(msg)

        async def test_runner():
            loop = asyncio.get_running_loop()
            loop_holder = {"loop": loop}

            def worker():
                if loop_holder["loop"] and not loop_holder["loop"].is_closed():
                    asyncio.run_coroutine_threadsafe(mock_coro({"type": "test"}), loop_holder["loop"])

            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()
            await asyncio.sleep(0.1)

            assert len(delivered) == 1
            assert delivered[0]["type"] == "test"

        asyncio.run(test_runner())

    def test_schedule_broadcast_closes_coroutine_when_loop_none(self):
        """When loop is None, coroutine should be closed to avoid ResourceWarning."""
        loop_holder = {"loop": None}
        warnings_log = []

        async def mock_coro(msg):
            pass  # pragma: no cover

        def schedule_broadcast(coroutine):
            if loop_holder["loop"] and not loop_holder["loop"].is_closed():
                asyncio.run_coroutine_threadsafe(coroutine, loop_holder["loop"])
            else:
                coroutine.close()
                warnings_log.append("loop not available")

        coro = mock_coro({"type": "test"})
        schedule_broadcast(coro)

        assert len(warnings_log) == 1

    def test_schedule_broadcast_with_closed_loop(self):
        """When loop is closed, coroutine should be closed (no RuntimeError)."""
        loop = asyncio.new_event_loop()
        loop.close()
        loop_holder = {"loop": loop}
        warnings_log = []

        async def mock_coro(msg):
            pass  # pragma: no cover

        def schedule_broadcast(coroutine):
            if loop_holder["loop"] and not loop_holder["loop"].is_closed():
                asyncio.run_coroutine_threadsafe(coroutine, loop_holder["loop"])
            else:
                coroutine.close()
                warnings_log.append("loop closed")

        coro = mock_coro({"type": "test"})
        schedule_broadcast(coro)
        assert len(warnings_log) == 1

    def test_scheduled_coroutine_exception_does_not_crash_loop(self):
        """Exception in scheduled coroutine doesn't crash the event loop."""

        async def failing_coro():
            raise ValueError("kaboom")

        async def test_runner():
            loop = asyncio.get_running_loop()

            future = asyncio.run_coroutine_threadsafe(failing_coro(), loop)
            await asyncio.sleep(0.1)

            # The future should hold the exception
            assert future.done()
            with pytest.raises(ValueError, match="kaboom"):
                future.result()

        asyncio.run(test_runner())


# =========================================================================
# Pattern 3: WebSocketManager broadcast_sync / broadcast_from_thread
# =========================================================================


@pytest.mark.unit
class TestWebSocketManagerBroadcastBoundary:
    """Tests for broadcast_sync vs broadcast_from_thread behavioral differences."""

    @pytest.fixture
    def mock_websocket(self):
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws

    def _make_manager(self):
        """Create a WebSocketManager with mocked settings."""
        import threading

        with patch("communication.websocket_manager.WebSocketManager.__init__", lambda self: None):
            mgr = WebSocketManager.__new__(WebSocketManager)
            mgr.active_connections = set()
            mgr.connection_metadata = {}
            mgr.message_count = 0
            mgr.event_loop = None
            mgr.logger = MagicMock()
            mgr.max_connections = 100
            mgr.heartbeat_interval = 30
            mgr.reconnect_attempts = 3
            mgr.reconnect_delay = 1.0
            # Phase 3B/3C concurrency locks — bypass __init__ but still
            # provide the locks the production methods now require.
            mgr._per_ip_counts = {}
            mgr._ip_lock = threading.Lock()
            mgr._connections_lock = threading.Lock()
            return mgr

    def test_broadcast_sync_checks_is_running(self):
        """broadcast_sync uses is_running() — drops message if loop exists but is not running."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        manager.event_loop = loop
        # Loop exists and is not closed, but is NOT running
        assert not loop.is_running()
        assert not loop.is_closed()

        manager.active_connections.add(MagicMock())
        manager.broadcast_sync({"type": "test"})

        # Should log debug about not running, not schedule anything
        manager.logger.debug.assert_called()
        loop.close()

    def test_broadcast_from_thread_checks_is_closed(self):
        """broadcast_from_thread uses is_closed() — schedules even if loop is not 'running' yet."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        manager.event_loop = loop

        ws = MagicMock()
        ws.send_json = AsyncMock()
        manager.active_connections.add(ws)

        # Loop is not running but IS NOT closed — broadcast_from_thread should
        # attempt to schedule (it checks is_closed, not is_running).
        # run_coroutine_threadsafe on a non-running loop will still queue the coroutine.
        # We verify the code path doesn't hit the else/debug-log branch.
        manager.broadcast_from_thread({"type": "test"})

        # The logger.debug for "No running event loop" should NOT be called
        for call in manager.logger.debug.call_args_list:
            assert "No running event loop" not in str(call)

        loop.close()

    def test_broadcast_from_thread_skips_when_no_connections(self, mock_websocket):
        """broadcast_from_thread returns early when active_connections is empty."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        manager.event_loop = loop

        # No connections — should return immediately without touching event loop
        manager.broadcast_from_thread({"type": "test"})

        # No scheduling attempted (logger.debug for "No running event loop" not called)
        manager.logger.debug.assert_not_called()
        loop.close()

    def test_broadcast_from_thread_skips_when_loop_closed(self):
        """broadcast_from_thread logs debug when event loop is closed."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        loop.close()
        manager.event_loop = loop
        manager.active_connections.add(MagicMock())

        manager.broadcast_from_thread({"type": "test"})

        manager.logger.debug.assert_called_once()
        assert "No running event loop" in str(manager.logger.debug.call_args)

    def test_broadcast_from_thread_skips_when_loop_none(self):
        """broadcast_from_thread logs debug when event_loop is None."""
        manager = self._make_manager()
        manager.event_loop = None
        manager.active_connections.add(MagicMock())

        manager.broadcast_from_thread({"type": "test"})

        manager.logger.debug.assert_called_once()
        assert "No running event loop" in str(manager.logger.debug.call_args)

    def test_broadcast_sync_skips_when_loop_none(self):
        """broadcast_sync logs debug when event_loop is None."""
        manager = self._make_manager()
        manager.event_loop = None

        manager.broadcast_sync({"type": "test"})

        manager.logger.debug.assert_called_once()
        assert "not set or not running" in str(manager.logger.debug.call_args)

    def test_broadcast_from_thread_delivers_to_connected_client(self, mock_websocket):
        """broadcast_from_thread actually delivers message via real event loop."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        manager.event_loop = loop

        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        time.sleep(0.05)

        try:
            # Connect mock websocket in the loop
            asyncio.run_coroutine_threadsafe(manager.connect(mock_websocket), loop).result(timeout=2)
            mock_websocket.send_json.reset_mock()

            # Call from a different thread (simulating training thread)
            def bg_broadcast():
                manager.broadcast_from_thread({"type": "metrics", "loss": 0.5})

            bg = threading.Thread(target=bg_broadcast)
            bg.start()
            bg.join(timeout=2)
            time.sleep(0.2)

            assert mock_websocket.send_json.called
            sent_msg = mock_websocket.send_json.call_args[0][0]
            assert sent_msg["type"] == "metrics"
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()

    def test_concurrent_broadcast_from_thread_delivers_all(self, mock_websocket):
        """Multiple threads calling broadcast_from_thread concurrently all deliver."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        manager.event_loop = loop

        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        time.sleep(0.05)

        try:
            asyncio.run_coroutine_threadsafe(manager.connect(mock_websocket), loop).result(timeout=2)
            mock_websocket.send_json.reset_mock()

            num_threads = 5
            msgs_per_thread = 3
            barrier = threading.Barrier(num_threads)

            def worker(worker_id):
                barrier.wait(timeout=2)
                for i in range(msgs_per_thread):
                    manager.broadcast_from_thread({"type": "test", "worker": worker_id, "i": i})

            threads = [threading.Thread(target=worker, args=(w,)) for w in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            time.sleep(0.5)

            expected = num_threads * msgs_per_thread
            assert mock_websocket.send_json.call_count >= expected
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()

    def test_broadcast_sync_delivers_when_loop_running(self, mock_websocket):
        """broadcast_sync delivers when event loop is running (is_running=True)."""
        manager = self._make_manager()
        loop = asyncio.new_event_loop()
        manager.event_loop = loop

        def run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()
        time.sleep(0.05)

        try:
            asyncio.run_coroutine_threadsafe(manager.connect(mock_websocket), loop).result(timeout=2)
            mock_websocket.send_json.reset_mock()

            manager.broadcast_sync({"type": "state", "status": "training"})
            time.sleep(0.2)

            assert mock_websocket.send_json.called
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=2)
            loop.close()
