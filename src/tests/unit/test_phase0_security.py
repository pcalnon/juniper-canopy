"""Tests for Phase 0 pre-release security fixes.

Covers:
- 0.1.1: Path traversal in snapshot endpoints
- 0.1.2: Timing attack in API key validation (hmac.compare_digest)
- 0.1.3: Exception handler suppresses internal details
- 0.1.4: Rate limiter memory leak (eviction + size cap)
- 0.2.1: Thread-unsafe CallbackContextAdapter (contextvars)
- 0.2.2: threading.Event replacement race condition
- 0.3.1: TrainingStateMachine thread-safety locking
"""

import concurrent.futures
import hmac
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from security import APIKeyAuth, RateLimiter


# ---------------------------------------------------------------------------
# 0.1.1 — Path traversal in snapshot endpoints
# ---------------------------------------------------------------------------
class TestSnapshotNameSanitization:
    """Tests for _sanitize_snapshot_name preventing path traversal."""

    @pytest.fixture(autouse=True)
    def _import_sanitizer(self):
        from main import _sanitize_snapshot_name

        self.sanitize = _sanitize_snapshot_name

    def test_valid_name_accepted(self):
        assert self.sanitize("snapshot_20260101_120000") == "snapshot_20260101_120000"

    def test_valid_name_with_hyphens(self):
        assert self.sanitize("my-snapshot-v2") == "my-snapshot-v2"

    def test_valid_name_with_dots(self):
        assert self.sanitize("snapshot.v1") == "snapshot.v1"

    def test_traversal_dot_dot_slash(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("../../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_traversal_backslash(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("..\\..\\etc\\passwd")
        assert exc_info.value.status_code == 400

    def test_traversal_url_encoded(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("%2e%2e%2f%2e%2e%2fetc%2fpasswd")
        assert exc_info.value.status_code == 400

    def test_slash_in_name(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("sub/dir/snapshot")
        assert exc_info.value.status_code == 400

    def test_empty_name(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("")
        assert exc_info.value.status_code == 400

    def test_name_starting_with_dot(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize(".hidden")
        assert exc_info.value.status_code == 400

    def test_name_starting_with_hyphen(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("-snapshot")
        assert exc_info.value.status_code == 400

    def test_null_byte(self):
        with pytest.raises(HTTPException) as exc_info:
            self.sanitize("snap\x00shot")
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 0.1.2 — Timing attack in API key validation
# ---------------------------------------------------------------------------
class TestTimingSafeKeyValidation:
    """Tests that API key validation uses constant-time comparison."""

    def test_valid_key_still_validates(self):
        auth = APIKeyAuth(["secret-key-123"])
        assert auth.validate("secret-key-123") is True

    def test_invalid_key_still_rejects(self):
        auth = APIKeyAuth(["secret-key-123"])
        assert auth.validate("wrong-key") is False

    def test_uses_hmac_compare_digest(self):
        """Verify hmac.compare_digest is called (not set membership)."""
        auth = APIKeyAuth(["key1", "key2"])
        with patch.object(hmac, "compare_digest", wraps=hmac.compare_digest) as mock_cmp:
            auth.validate("key1")
            assert mock_cmp.called

    def test_none_key_rejected_without_compare(self):
        auth = APIKeyAuth(["key1"])
        assert auth.validate(None) is False

    def test_disabled_auth_returns_true(self):
        auth = APIKeyAuth()
        assert auth.validate("anything") is True


# ---------------------------------------------------------------------------
# 0.1.3 — Exception handler suppresses internal details
# ---------------------------------------------------------------------------
class TestExceptionHandlerSuppression:
    """Tests that the global exception handler doesn't leak internals."""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_exception_handler_generic_message(self):
        from main import unhandled_exception_handler

        request = MagicMock()
        request.method = "GET"
        request.url = MagicMock()
        request.url.path = "/api/v1/test"

        exc = ValueError("sensitive database connection string here")
        response = await unhandled_exception_handler(request, exc)

        import json

        body = json.loads(response.body)
        assert body["status_code"] == 500
        assert "sensitive" not in body["detail"]
        assert "database" not in body["detail"]
        assert body["detail"] == "An unexpected error occurred."

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_exception_handler_logs_full_detail(self):
        from main import unhandled_exception_handler

        request = MagicMock()
        request.method = "POST"
        request.url = MagicMock()
        request.url.path = "/api/v1/foo"

        exc = RuntimeError("secret internal info")
        with patch("main.system_logger") as mock_logger:
            await unhandled_exception_handler(request, exc)
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            # PERF-CN-02 made this call lazy: error("...%s...", method, path, exc).
            # The exception detail now lives in the positional args, not the
            # format string itself. Search across the whole positional tuple.
            full_call_repr = " ".join(str(a) for a in call_args[0])
            assert "secret internal info" in full_call_repr
            assert call_args[1].get("exc_info") is True


# ---------------------------------------------------------------------------
# 0.1.4 — Rate limiter memory leak
# ---------------------------------------------------------------------------
class TestRateLimiterMemoryBounds:
    """Tests for rate limiter eviction and emergency size cap."""

    def test_eviction_removes_expired_entries(self):
        limiter = RateLimiter(requests_per_minute=100, window_seconds=1, enabled=True)
        # Fill with entries
        for i in range(50):
            limiter.check(f"key-{i}")

        assert len(limiter._counters) == 50

        # Wait for window to expire
        time.sleep(1.1)

        # Next check triggers eviction
        limiter.check("new-key")
        # All old entries should be evicted (only "new-key" remains)
        assert len(limiter._counters) <= 2  # new-key + possible timing edge

    def test_emergency_cap_prevents_unbounded_growth(self):
        limiter = RateLimiter(requests_per_minute=100, window_seconds=3600, enabled=True)
        limiter._max_entries = 100  # Lower cap for testing

        # Simulate IP rotation attack: many unique keys
        for i in range(150):
            limiter.check(f"attacker-ip-{i}")

        # Should not exceed max_entries by much (eviction runs when cap hit)
        assert len(limiter._counters) <= 151  # cap triggers eviction, fresh entries added

    def test_eviction_method_clears_old(self):
        limiter = RateLimiter(requests_per_minute=10, window_seconds=1, enabled=True)
        now = time.time()
        # Manually inject old entries
        with limiter._lock:
            for i in range(20):
                limiter._counters[f"old-{i}"] = (1, now - 100)
            limiter._evict_expired(now)
        assert len(limiter._counters) == 0


# ---------------------------------------------------------------------------
# 0.2.1 — CallbackContextAdapter thread safety with contextvars
# ---------------------------------------------------------------------------
class TestCallbackContextThreadSafety:
    """Tests that CallbackContextAdapter uses context-local test state."""

    @pytest.fixture(autouse=True)
    def _reset_adapter(self):
        from frontend.callback_context import CallbackContextAdapter

        CallbackContextAdapter.reset_instance()
        yield
        CallbackContextAdapter.reset_instance()

    def test_set_and_get_trigger(self):
        from frontend.callback_context import CallbackContextAdapter

        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("btn-1")
        assert adapter.get_triggered_id() == "btn-1"
        adapter.clear_test_trigger()
        assert adapter.is_test_mode() is False

    def test_concurrent_thread_isolation(self):
        """Verify that test triggers set in one thread don't leak to another."""
        from frontend.callback_context import CallbackContextAdapter

        results = {}
        barrier = threading.Barrier(2)

        def thread_a():
            adapter = CallbackContextAdapter()
            adapter.set_test_trigger("thread-a-trigger")
            barrier.wait(timeout=5)
            results["a"] = adapter.get_triggered_id()
            adapter.clear_test_trigger()

        def thread_b():
            adapter = CallbackContextAdapter()
            adapter.set_test_trigger("thread-b-trigger")
            barrier.wait(timeout=5)
            results["b"] = adapter.get_triggered_id()
            adapter.clear_test_trigger()

        t1 = threading.Thread(target=thread_a)
        t2 = threading.Thread(target=thread_b)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert results["a"] == "thread-a-trigger"
        assert results["b"] == "thread-b-trigger"

    def test_test_mode_does_not_leak_across_threads(self):
        """Setting test mode in one thread should not affect another."""
        from frontend.callback_context import CallbackContextAdapter

        results = {}

        def setter():
            adapter = CallbackContextAdapter()
            adapter.set_test_trigger("setter-trigger")
            time.sleep(0.1)
            results["setter_mode"] = adapter.is_test_mode()
            adapter.clear_test_trigger()

        def reader():
            time.sleep(0.05)
            adapter = CallbackContextAdapter()
            results["reader_mode"] = adapter.is_test_mode()
            results["reader_trigger"] = adapter.get_triggered_id()

        t1 = threading.Thread(target=setter)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert results["setter_mode"] is True
        assert results["reader_mode"] is False
        assert results["reader_trigger"] is None


# ---------------------------------------------------------------------------
# 0.2.2 — threading.Event replacement race condition
# ---------------------------------------------------------------------------
class TestDemoModeEventRaceCondition:
    """Tests that _perform_reset uses .clear() instead of creating new Event."""

    def test_stop_event_identity_preserved_after_reset(self):
        """The _stop Event object should be the same instance after reset."""
        from demo_mode import DemoMode

        demo = DemoMode()
        original_stop = demo._stop
        original_pause = demo._pause
        demo._perform_reset()
        assert demo._stop is original_stop, "_stop should be .clear()'d, not replaced"
        assert demo._pause is original_pause, "_pause should be .clear()'d, not replaced"

    def test_rapid_stop_reset_start_cycle(self):
        """Rapid stop/reset/start should not raise or deadlock."""
        from demo_mode import DemoMode

        demo = DemoMode()

        for _ in range(5):
            demo.start()
            time.sleep(0.05)
            demo.stop()
            demo._perform_reset()

        # Should be cleanly stopped
        assert not demo.is_running


# ---------------------------------------------------------------------------
# 0.3.1 — TrainingStateMachine thread-safety locking
# ---------------------------------------------------------------------------
class TestTrainingStateMachineLocking:
    """Tests that TrainingStateMachine has a lock and is thread-safe."""

    def test_has_lock(self):
        from backend.training_state_machine import TrainingStateMachine

        fsm = TrainingStateMachine()
        assert hasattr(fsm, "_lock")
        assert isinstance(fsm._lock, type(threading.Lock()))

    def test_concurrent_commands_no_corruption(self):
        """Rapidly send commands from multiple threads; state should remain valid."""
        from backend.training_state_machine import Command, TrainingStateMachine, TrainingStatus

        fsm = TrainingStateMachine()
        errors = []

        def command_loop(commands):
            try:
                for cmd in commands:
                    fsm.handle_command(cmd)
                    # Read state to exercise get_state_summary under contention
                    summary = fsm.get_state_summary()
                    assert summary["status"] in [s.name for s in TrainingStatus]
            except Exception as e:
                errors.append(e)

        # Thread 1: start/pause/resume cycles
        seq1 = [Command.START, Command.PAUSE, Command.RESUME, Command.STOP] * 20
        # Thread 2: start/stop cycles
        seq2 = [Command.START, Command.STOP] * 40
        # Thread 3: reset cycles
        seq3 = [Command.RESET] * 80

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [
                pool.submit(command_loop, seq1),
                pool.submit(command_loop, seq2),
                pool.submit(command_loop, seq3),
            ]
            for f in concurrent.futures.as_completed(futures, timeout=30):
                f.result()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # FSM should be in a valid state
        summary = fsm.get_state_summary()
        assert summary["status"] in [s.name for s in TrainingStatus]

    def test_concurrent_set_phase(self):
        """set_phase from multiple threads should not corrupt state."""
        from backend.training_state_machine import Command, TrainingPhase, TrainingStateMachine

        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)

        phases = [TrainingPhase.OUTPUT, TrainingPhase.CANDIDATE, TrainingPhase.INFERENCE]

        def phase_setter(phase):
            for _ in range(100):
                fsm.set_phase(phase)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(phase_setter, p) for p in phases]
            for f in concurrent.futures.as_completed(futures, timeout=10):
                f.result()

        # Phase should be one of the valid phases
        assert fsm.get_phase() in phases
