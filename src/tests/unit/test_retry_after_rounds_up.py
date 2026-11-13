"""``Retry-After`` and ``X-RateLimit-Reset`` round UP (APD-ECO-016).

``RateLimiter.check`` reported ``int(window - elapsed)``, which truncates toward zero. A rejection in
a window's last second therefore said ``Retry-After: 0``, an instruction to retry immediately into a
limiter that rejects again, and every other fractional remainder was under-reported (9.4s left said
9). juniper-service-core's copy rounds up (``APD-SVCCORE-004``); these tests pin the same direction
here.

The clock is frozen, so every remainder is exact.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import SecurityMiddleware
from security import APIKeyAuth, RateLimiter

pytestmark = pytest.mark.unit

_START = 1_000.0

# Seconds into a 10 s window -> the whole seconds left, rounded up. 9.4 s left is the plain case. The other three sit
# just above a whole number, where a rounding that agrees with ``ceil`` only near the half (add 0.7 and truncate,
# round to nearest) answers a second short.
_FRACTIONAL = [(0.6, 10), (0.99, 10), (0.999, 10), (8.999, 2)]
# Exact remainders are not bumped. 7 and 5 are ODD on purpose: ``round(x + 0.5)`` rounds a half to even, so it bumps
# an odd remainder and leaves an even one (6) alone.
_EXACT = [(4.0, 6), (3.0, 7), (5.0, 5)]


class _Clock:
    """A stand-in for ``time.time`` that a test moves by assignment."""

    def __init__(self, now: float) -> None:
        self.now = now

    def time(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    """Freeze the clock the security module reads, at ``_START``."""
    frozen = _Clock(_START)
    monkeypatch.setattr("security.time.time", frozen.time)
    return frozen


def _app(limiter: RateLimiter) -> FastAPI:
    app = FastAPI()

    @app.get("/api/metrics")
    def api_metrics():
        return {"data": {"epoch": 1}}

    app.add_middleware(SecurityMiddleware, api_key_auth=APIKeyAuth(None), rate_limiter=limiter)
    return app


class TestRateLimiterResetRoundsUp:
    """``RateLimiter.check``'s third value, on the rejection path and the allowed path."""

    @pytest.mark.parametrize("elapsed", [9.01, 9.30, 9.60, 9.90, 9.99])
    def test_a_rejection_in_the_last_second_says_one_never_zero(self, clock: _Clock, elapsed: float) -> None:
        """The defect: ``int()`` truncated each of these remainders to 0."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10)
        assert limiter.check("k") == (True, 0, 10)

        clock.now = _START + elapsed

        assert limiter.check("k") == (False, 0, 1)

    @pytest.mark.parametrize(("elapsed", "expected"), _FRACTIONAL)
    def test_a_rejection_rounds_any_fraction_up(self, clock: _Clock, elapsed: float, expected: int) -> None:
        """9.4s left is 10. Truncation says 9, and so does a floor of 1 laid over truncation."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10)
        limiter.check("k")

        clock.now = _START + elapsed

        assert limiter.check("k") == (False, 0, expected)

    @pytest.mark.parametrize(("elapsed", "expected"), _EXACT)
    def test_an_exact_remainder_is_not_bumped(self, clock: _Clock, elapsed: float, expected: int) -> None:
        """6.0s left stays 6. A repair that always adds one second fails here; one that rounds a half to even fails on 7 and 5."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10)
        limiter.check("k")

        clock.now = _START + elapsed

        assert limiter.check("k") == (False, 0, expected)

    def test_a_fresh_rejection_reports_the_whole_window(self, clock: _Clock) -> None:
        """The floor of 1 must not flatten every answer to 1."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=60)
        limiter.check("k")

        assert limiter.check("k") == (False, 0, 60)

    def test_the_allowed_path_rounds_up_too(self, clock: _Clock) -> None:
        """The allowed path feeds ``X-RateLimit-Reset`` and carried the same truncation."""
        limiter = RateLimiter(requests_per_minute=5, window_seconds=10)
        assert limiter.check("k") == (True, 4, 10)

        clock.now = _START + 0.6
        assert limiter.check("k") == (True, 3, 10)

        clock.now = _START + 9.7
        assert limiter.check("k") == (True, 2, 1)

    @pytest.mark.parametrize(("elapsed", "expected"), _FRACTIONAL + _EXACT)
    def test_the_allowed_path_rounds_the_same_way(self, clock: _Clock, elapsed: float, expected: int) -> None:
        """Both ``check`` returns go through one helper. This holds the allowed one to every point the rejection meets."""
        limiter = RateLimiter(requests_per_minute=5, window_seconds=10)
        limiter.check("k")

        clock.now = _START + elapsed

        assert limiter.check("k") == (True, 3, expected)

    def test_a_window_longer_than_a_minute_is_not_capped(self, clock: _Clock) -> None:
        """Every other test uses a 10 s or a 60 s window, so a wait capped at 60 passes them all."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=120)
        limiter.check("k")

        clock.now = _START + 0.5

        assert limiter.check("k") == (False, 0, 120)

    def test_the_request_that_spends_the_last_slot_rounds_up_too(self, clock: _Clock) -> None:
        """The allowed path with nothing left: 6.6s left says 7, not the whole window."""
        limiter = RateLimiter(requests_per_minute=2, window_seconds=10)
        limiter.check("k")

        clock.now = _START + 3.4

        assert limiter.check("k") == (True, 0, 7)

    def test_check_itself_rolls_the_window_over_at_the_boundary(self, clock: _Clock) -> None:
        """The roll-over comparison in ``check``, without the eviction sweep's help.

        With one key, the sweep (``_evict_expired``) runs at the very instant the key's window ends, deletes the
        entry, and the request starts a new window whatever ``check``'s own comparison says. Here key ``k``'s window
        starts half a sweep period late, so at its boundary no sweep runs and only ``check`` can roll it over.
        """
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10)
        limiter.check("a")  # t=0: the sweep stamps itself here

        clock.now = _START + 5.0
        assert limiter.check("k") == (True, 0, 10)  # k's window starts at 5; no sweep (5 < 10)

        clock.now = _START + 10.0
        limiter.check("a")  # the sweep runs (and restamps); k is 5 s old and stays

        clock.now = _START + 15.0  # k's exact boundary; no sweep (5 < 10)
        assert limiter.check("k") == (True, 0, 10)

    def test_the_window_still_rolls_over_at_the_boundary(self, clock: _Clock) -> None:
        """One millisecond before the boundary is still a 1-second wait; the boundary itself is a new window."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10)
        limiter.check("k")

        clock.now = _START + 9.999
        assert limiter.check("k") == (False, 0, 1)

        clock.now = _START + 10.0
        assert limiter.check("k") == (True, 0, 10)

    def test_the_floor_holds_at_the_exact_boundary(self) -> None:
        """``ceil`` returns 0 at the boundary. ``check`` rolls the window over there, so only a direct call reaches the floor."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10)

        assert limiter._seconds_until_reset(_START + 10.0, _START) == 1

    def test_the_429_carries_the_rounded_wait_in_both_headers(self, clock: _Clock) -> None:
        """End to end: the headers and the message a caller receives, not ``check``'s tuple."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10, enabled=True)
        client = TestClient(_app(limiter))
        first = client.get("/api/metrics")
        assert first.status_code == 200
        assert first.headers["X-RateLimit-Reset"] == "10"

        clock.now = _START + 9.7
        response = client.get("/api/metrics")

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "1"
        assert response.headers["X-RateLimit-Reset"] == "1"
        assert response.json()["detail"] == "Rate limit exceeded. Try again in 1 seconds."

    def test_the_429_names_the_rounded_wait_not_just_a_nonzero_one(self, clock: _Clock) -> None:
        """9.4s left: both headers and the message say 10. Truncation says 9, and a constant 1 passes the test above."""
        limiter = RateLimiter(requests_per_minute=1, window_seconds=10, enabled=True)
        client = TestClient(_app(limiter))
        client.get("/api/metrics")

        clock.now = _START + 0.6
        response = client.get("/api/metrics")

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "10"
        assert response.headers["X-RateLimit-Reset"] == "10"
        assert response.json()["detail"] == "Rate limit exceeded. Try again in 10 seconds."

    def test_an_allowed_response_carries_the_rounded_reset(self, clock: _Clock) -> None:
        """The allowed path's value reaches ``X-RateLimit-Reset`` through the middleware: 10 with 9.4s left, and 1, never 0, in the last second."""
        limiter = RateLimiter(requests_per_minute=5, window_seconds=10, enabled=True)
        client = TestClient(_app(limiter))
        client.get("/api/metrics")

        clock.now = _START + 0.6
        response = client.get("/api/metrics")

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Reset"] == "10"

        clock.now = _START + 9.7
        last_second = client.get("/api/metrics")

        assert last_second.status_code == 200
        assert last_second.headers["X-RateLimit-Reset"] == "1"

    def test_the_wire_carries_what_is_left_of_the_budget(self, clock: _Clock) -> None:
        """``X-RateLimit-Remaining`` on an allowed response and on the 429 (``docs/api/API_REFERENCE.md`` states the 0)."""
        limiter = RateLimiter(requests_per_minute=2, window_seconds=10, enabled=True)
        client = TestClient(_app(limiter))

        assert client.get("/api/metrics").headers["X-RateLimit-Remaining"] == "1"
        assert client.get("/api/metrics").headers["X-RateLimit-Remaining"] == "0"
        rejected = client.get("/api/metrics")
        assert rejected.status_code == 429
        assert rejected.headers["X-RateLimit-Remaining"] == "0"
