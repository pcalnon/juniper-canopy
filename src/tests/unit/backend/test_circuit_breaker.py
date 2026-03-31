"""Tests for the circuit breaker module."""

import time

import pytest

from backend.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


@pytest.mark.unit
class TestCircuitBreaker:
    """Tests for CircuitBreaker state transitions and behavior."""

    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_successful_calls_stay_closed(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_failures_increment_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.failure_count == 3
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_open_circuit_returns_fallback(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitState.OPEN
        result = cb.call(lambda: 42, fallback=lambda: -1)
        assert result == -1

    def test_open_circuit_raises_without_fallback(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        with pytest.raises(CircuitOpenError, match="test"):
            cb.call(lambda: 42)

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("still down")))
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=5)
        for _ in range(4):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.failure_count == 4
        cb.call(lambda: "ok")
        assert cb.failure_count == 0

    def test_manual_reset(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_fallback_on_transition_to_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        result = cb.call(
            lambda: (_ for _ in ()).throw(ValueError("fail2")),
            fallback=lambda: "fallback_value",
        )
        assert result == "fallback_value"

    def test_passes_args_and_kwargs(self):
        def add(a, b, extra=0):
            return a + b + extra

        cb = CircuitBreaker(name="test")
        result = cb.call(add, 1, 2, extra=10)
        assert result == 13
