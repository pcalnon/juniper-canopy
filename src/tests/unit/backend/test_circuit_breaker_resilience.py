"""Resilience tests for the circuit breaker module.

Covers concurrent calls during state transitions, rapid open/close
cycling, multiple independent breakers, and thread safety under load.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from backend.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


@pytest.mark.unit
class TestCircuitBreakerConcurrency:
    """Thread safety tests for CircuitBreaker."""

    def test_concurrent_success_calls(self):
        """Many concurrent successful calls don't corrupt state."""
        cb = CircuitBreaker(name="concurrent-ok", failure_threshold=5)
        errors = []

        def call():
            try:
                result = cb.call(lambda: 42)
                assert result == 42
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(call) for _ in range(100)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_concurrent_failures_trip_circuit(self):
        """Concurrent failures correctly trip the circuit."""
        cb = CircuitBreaker(name="concurrent-fail", failure_threshold=5)

        def fail():
            try:
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
            except (ValueError, CircuitOpenError):
                pass

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(fail) for _ in range(20)]
            for f in as_completed(futures):
                f.result()

        assert cb.state == CircuitState.OPEN

    def test_concurrent_mixed_calls(self):
        """Mix of successes and failures don't corrupt state."""
        cb = CircuitBreaker(name="mixed", failure_threshold=100)
        errors = []

        def mixed_call(should_fail):
            try:
                if should_fail:
                    cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
                else:
                    cb.call(lambda: "ok")
            except (ValueError, CircuitOpenError):
                pass
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(mixed_call, i % 2 == 0) for i in range(50)]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0

    def test_concurrent_reset_during_calls(self):
        """Reset during active calls doesn't cause exceptions."""
        cb = CircuitBreaker(name="reset-race", failure_threshold=3)
        errors = []

        def call_loop():
            for _ in range(50):
                try:
                    cb.call(lambda: "ok")
                except CircuitOpenError:
                    pass
                except Exception as e:
                    errors.append(e)

        def reset_loop():
            for _ in range(10):
                cb.reset()
                time.sleep(0.001)

        threads = [
            threading.Thread(target=call_loop),
            threading.Thread(target=call_loop),
            threading.Thread(target=reset_loop),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


@pytest.mark.unit
class TestCircuitBreakerRapidCycling:
    """Tests for rapid state cycling behavior."""

    def test_rapid_open_close_cycle(self):
        """Circuit can rapidly cycle between open and closed states."""
        cb = CircuitBreaker(name="rapid", failure_threshold=1, recovery_timeout=0.05)

        for _ in range(5):
            # Trip it
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
            assert cb.state == CircuitState.OPEN

            # Wait for half-open
            time.sleep(0.06)
            assert cb.state == CircuitState.HALF_OPEN

            # Recover
            result = cb.call(lambda: "recovered")
            assert result == "recovered"
            assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_immediately(self):
        """Failed probe in half-open state reopens the circuit."""
        cb = CircuitBreaker(name="reopen", failure_threshold=1, recovery_timeout=0.05)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("trip")))

        time.sleep(0.06)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("still down")))

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count >= 1

    def test_multiple_failures_during_closed_state(self):
        """Failures below threshold keep circuit closed."""
        cb = CircuitBreaker(name="below-threshold", failure_threshold=10)

        for _ in range(9):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
            assert cb.state == CircuitState.CLOSED

        assert cb.failure_count == 9


@pytest.mark.unit
class TestMultipleCircuitBreakers:
    """Tests for independent circuit breaker instances."""

    def test_independent_state(self):
        """Separate breakers maintain independent state."""
        cb_a = CircuitBreaker(name="service-a", failure_threshold=2)
        cb_b = CircuitBreaker(name="service-b", failure_threshold=2)

        # Trip breaker A
        for _ in range(2):
            with pytest.raises(ValueError):
                cb_a.call(lambda: (_ for _ in ()).throw(ValueError("a-fail")))

        assert cb_a.state == CircuitState.OPEN
        assert cb_b.state == CircuitState.CLOSED

        # Breaker B still works
        result = cb_b.call(lambda: "b-ok")
        assert result == "b-ok"

    def test_independent_failure_counts(self):
        """Failure counts are independent between breakers."""
        cb_a = CircuitBreaker(name="a", failure_threshold=5)
        cb_b = CircuitBreaker(name="b", failure_threshold=5)

        for _ in range(3):
            with pytest.raises(ValueError):
                cb_a.call(lambda: (_ for _ in ()).throw(ValueError("a")))

        assert cb_a.failure_count == 3
        assert cb_b.failure_count == 0

    def test_independent_reset(self):
        """Resetting one breaker doesn't affect another."""
        cb_a = CircuitBreaker(name="a", failure_threshold=1)
        cb_b = CircuitBreaker(name="b", failure_threshold=1)

        # Trip both
        with pytest.raises(ValueError):
            cb_a.call(lambda: (_ for _ in ()).throw(ValueError("a")))
        with pytest.raises(ValueError):
            cb_b.call(lambda: (_ for _ in ()).throw(ValueError("b")))

        assert cb_a.state == CircuitState.OPEN
        assert cb_b.state == CircuitState.OPEN

        # Reset only A
        cb_a.reset()
        assert cb_a.state == CircuitState.CLOSED
        assert cb_b.state == CircuitState.OPEN

    def test_concurrent_independent_breakers(self):
        """Multiple breakers used concurrently from different threads."""
        breakers = [CircuitBreaker(name=f"svc-{i}", failure_threshold=3) for i in range(5)]
        errors = []

        def use_breaker(cb):
            try:
                for _ in range(10):
                    cb.call(lambda: "ok")
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(use_breaker, cb) for cb in breakers]
            for f in as_completed(futures):
                f.result()

        assert len(errors) == 0
        for cb in breakers:
            assert cb.state == CircuitState.CLOSED


@pytest.mark.unit
class TestCircuitBreakerFallbackEdgeCases:
    """Edge cases for fallback behavior."""

    def test_fallback_called_when_open(self):
        """Fallback is called immediately when circuit is open."""
        cb = CircuitBreaker(name="fallback", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("trip")))

        call_count = 0

        def counting_fallback():
            nonlocal call_count
            call_count += 1
            return "fallback"

        result = cb.call(lambda: "should not run", fallback=counting_fallback)
        assert result == "fallback"
        assert call_count == 1

    def test_fallback_not_called_when_closed(self):
        """Fallback is not called when circuit is closed and call succeeds."""
        cb = CircuitBreaker(name="no-fallback", failure_threshold=5)
        fallback_called = False

        def failing_fallback():
            nonlocal fallback_called
            fallback_called = True
            return "fallback"

        result = cb.call(lambda: "success", fallback=failing_fallback)
        assert result == "success"
        assert not fallback_called

    def test_fallback_on_threshold_crossing_failure(self):
        """Fallback kicks in when the threshold-crossing failure opens the circuit."""
        cb = CircuitBreaker(name="threshold-cross", failure_threshold=2)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("first")))

        # Second failure crosses threshold; fallback should be used
        result = cb.call(
            lambda: (_ for _ in ()).throw(ValueError("second")),
            fallback=lambda: "caught",
        )
        assert result == "caught"

    def test_no_fallback_raises_original_exception_type(self):
        """Without fallback, the original exception type is preserved."""
        cb = CircuitBreaker(name="orig-exc", failure_threshold=10)
        with pytest.raises(TypeError, match="bad type"):
            cb.call(lambda: (_ for _ in ()).throw(TypeError("bad type")))

    def test_fallback_can_return_none(self):
        """Fallback returning None is valid."""
        cb = CircuitBreaker(name="none-fb", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("trip")))

        result = cb.call(lambda: "unreachable", fallback=lambda: None)
        assert result is None
