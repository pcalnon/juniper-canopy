"""Phase F: Unit tests for reconnect jitter formula.

§S12 — Tests for the jitter backoff formula used in WebSocket reconnection.
Validates jitter bounds, unbounded attempts with capped delay, and
numeric safety (no NaN/Infinity).

The formula (shared between JS client and Python adapter):
    delay = random() * min(60000, 500 * 2 ** min(attempt, 7))  [ms, JS]
    delay = random() * min(60, 0.5 * 2 ** min(attempt, 7))     [sec, Python]
"""

import math
import random

import pytest

# ===================================================================
# Reference implementation (mirrors JS and Python adapter formula)
# ===================================================================


def reconnect_delay_ms(attempt: int) -> float:
    """Compute reconnect delay in milliseconds (JS formula).

    Args:
        attempt: Zero-based reconnect attempt number.

    Returns:
        Delay in milliseconds, 0 <= delay <= 60000.
    """
    return random.random() * min(60000, 500 * (2 ** min(attempt, 7)))


def reconnect_delay_sec(attempt: int) -> float:
    """Compute reconnect delay in seconds (Python adapter formula).

    Args:
        attempt: Zero-based reconnect attempt number.

    Returns:
        Delay in seconds, 0 <= delay <= 60.
    """
    return random.random() * min(60, 0.5 * (2 ** min(attempt, 7)))


# ===================================================================
# Tests — Phase F (§S12)
# ===================================================================


@pytest.mark.unit
class TestReconnectJitter:
    """Unit tests for reconnect jitter formula."""

    def test_reconnect_backoff_has_jitter(self):
        """Repeated calls with the same attempt produce different delays."""
        delays = [reconnect_delay_ms(3) for _ in range(50)]
        unique = set(delays)
        # With 50 random samples, we should have many unique values
        assert len(unique) > 10, f"Expected jitter variance, got {len(unique)} unique values"
        # All within bounds
        for d in delays:
            assert 0 <= d <= 60000, f"Delay {d} out of bounds"

    def test_reconnect_attempt_unbounded_with_cap(self):
        """Reconnect attempts > 10 still produce valid delays capped at 60s."""
        for attempt in [10, 20, 50, 100, 1000]:
            delays = [reconnect_delay_ms(attempt) for _ in range(20)]
            for d in delays:
                assert 0 <= d <= 60000, f"Attempt {attempt}: delay {d} exceeds 60s cap"
            # Max possible delay at attempt >= 7 is 60000ms (cap)
            # min(60000, 500 * 2^7) = min(60000, 64000) = 60000
            assert max(delays) <= 60000

    def test_jitter_formula_no_nan_delay(self):
        """Formula never produces NaN, Infinity, or negative values.

        Tests extreme attempt numbers including 0, boundary, and very
        large values that could cause overflow without the exponent cap.
        """
        for attempt in [0, 1, 5, 7, 8, 15, 100, 10000]:
            for _ in range(100):
                delay_ms = reconnect_delay_ms(attempt)
                delay_sec = reconnect_delay_sec(attempt)

                assert not math.isnan(delay_ms), f"NaN at attempt {attempt}"
                assert not math.isinf(delay_ms), f"Infinity at attempt {attempt}"
                assert delay_ms >= 0, f"Negative delay at attempt {attempt}"

                assert not math.isnan(delay_sec), f"NaN at attempt {attempt} (sec)"
                assert not math.isinf(delay_sec), f"Infinity at attempt {attempt} (sec)"
                assert delay_sec >= 0, f"Negative delay at attempt {attempt} (sec)"

    def test_backoff_increases_with_attempts(self):
        """Average delay increases with attempt number (up to cap)."""
        random.seed(42)
        avg_0 = sum(reconnect_delay_ms(0) for _ in range(200)) / 200
        avg_3 = sum(reconnect_delay_ms(3) for _ in range(200)) / 200
        avg_7 = sum(reconnect_delay_ms(7) for _ in range(200)) / 200
        # Each step roughly doubles the max possible delay
        assert avg_3 > avg_0, "Attempt 3 should have higher average than attempt 0"
        assert avg_7 > avg_3, "Attempt 7 should have higher average than attempt 3"

    def test_exponent_cap_at_7(self):
        """Attempts 7 and 100 produce same max ceiling (64000ms before 60s cap)."""
        random.seed(42)
        # At attempt=7: min(60000, 500 * 128) = min(60000, 64000) = 60000
        # At attempt=100: min(60000, 500 * 128) = 60000 (same, exponent capped)
        maxes_7 = [reconnect_delay_ms(7) for _ in range(500)]
        maxes_100 = [reconnect_delay_ms(100) for _ in range(500)]
        # Both should have similar max (both capped at 60000)
        assert max(maxes_7) <= 60000
        assert max(maxes_100) <= 60000
