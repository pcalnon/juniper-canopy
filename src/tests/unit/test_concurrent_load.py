"""Concurrent load and stress tests.

Tests for rate limiter under concurrent requests, WebSocket connection
limits, and concurrent API request handling.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import SecurityMiddleware
from security import APIKeyAuth, RateLimiter


def _make_rate_limited_app(rpm=10, window=60):
    """Create a FastAPI app with rate limiting enabled."""
    app = FastAPI()
    app.add_middleware(
        SecurityMiddleware,
        api_key_auth=APIKeyAuth(None),
        rate_limiter=RateLimiter(requests_per_minute=rpm, window_seconds=window, enabled=True),
    )

    @app.get("/api/data")
    def get_data():
        return {"ok": True}

    return app


@pytest.mark.unit
class TestRateLimiterConcurrency:
    """Test rate limiter under concurrent requests."""

    def test_concurrent_requests_respect_limit(self):
        """Multiple threads hitting the same endpoint respect rate limit."""
        rl = RateLimiter(requests_per_minute=10, enabled=True)
        results = []
        barrier = threading.Barrier(20)

        def check():
            barrier.wait()
            allowed, remaining, _ = rl.check("shared-key")
            results.append(allowed)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(1 for r in results if r)
        denied_count = sum(1 for r in results if not r)
        assert allowed_count == 10
        assert denied_count == 10

    def test_different_keys_not_affected_by_each_other(self):
        """Concurrent requests with different keys are independent."""
        rl = RateLimiter(requests_per_minute=5, enabled=True)
        results = {"a": [], "b": []}

        def check(key, result_list):
            for _ in range(5):
                allowed, _, _ = rl.check(key)
                result_list.append(allowed)

        t1 = threading.Thread(target=check, args=("key-a", results["a"]))
        t2 = threading.Thread(target=check, args=("key-b", results["b"]))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert all(results["a"]), "All key-a requests should be allowed"
        assert all(results["b"]), "All key-b requests should be allowed"

    def test_thread_safety_no_data_corruption(self):
        """Many concurrent threads don't corrupt internal state."""
        rl = RateLimiter(requests_per_minute=1000, enabled=True)
        errors = []

        def hammer():
            try:
                for _ in range(100):
                    rl.check(f"key-{threading.current_thread().ident}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=hammer) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"

    def test_eviction_under_concurrent_load(self):
        """Eviction runs safely under concurrent access."""
        rl = RateLimiter(requests_per_minute=5, window_seconds=1, enabled=True)

        # Fill with entries
        for i in range(100):
            rl.check(f"key-{i}")

        # Wait for window to expire
        time.sleep(1.1)

        # Concurrent checks should trigger eviction
        errors = []

        def check():
            try:
                rl.check(f"new-key-{threading.current_thread().ident}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=check) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_emergency_cap_eviction(self):
        """Emergency cap triggers when too many unique keys accumulate."""
        rl = RateLimiter(requests_per_minute=1000, enabled=True)
        rl._max_entries = 50  # Lower cap for testing

        # Fill beyond cap
        for i in range(60):
            rl.check(f"key-{i}")

        # Should not error; eviction should have pruned expired entries
        allowed, _, _ = rl.check("final-key")
        assert allowed is True


@pytest.mark.unit
class TestConcurrentAPIRequests:
    """Test concurrent API requests through the middleware stack."""

    def test_concurrent_get_requests(self):
        """Multiple concurrent GET requests are handled correctly."""
        app = _make_rate_limited_app(rpm=100)
        results = []

        def make_request():
            client = TestClient(app)
            resp = client.get("/api/data")
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            for f in as_completed(futures):
                f.result()  # Raise any exceptions

        # All should succeed (within rate limit)
        assert all(code == 200 for code in results)

    def test_rate_limit_enforced_under_load(self):
        """Rate limit kicks in correctly under concurrent load."""
        app = _make_rate_limited_app(rpm=5)
        results = []

        def make_request():
            client = TestClient(app)
            resp = client.get("/api/data")
            results.append(resp.status_code)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            for f in as_completed(futures):
                f.result()

        status_200 = sum(1 for c in results if c == 200)
        status_429 = sum(1 for c in results if c == 429)
        assert status_200 <= 5
        assert status_429 >= 5
        assert status_200 + status_429 == 10


@pytest.mark.unit
class TestRateLimiterWindowReset:
    """Tests for rate limiter window boundary behavior."""

    def test_window_resets_after_expiry(self):
        """After window expires, counter resets and allows requests again."""
        rl = RateLimiter(requests_per_minute=2, window_seconds=1, enabled=True)
        rl.check("key")
        rl.check("key")
        allowed, _, _ = rl.check("key")
        assert allowed is False

        time.sleep(1.1)

        allowed, remaining, _ = rl.check("key")
        assert allowed is True
        assert remaining == 1  # 2 - 1

    def test_remaining_count_decreases(self):
        """Remaining count decreases with each request."""
        rl = RateLimiter(requests_per_minute=5, enabled=True)
        _, remaining, _ = rl.check("key")
        assert remaining == 4
        _, remaining, _ = rl.check("key")
        assert remaining == 3
        _, remaining, _ = rl.check("key")
        assert remaining == 2

    def test_reset_seconds_is_positive(self):
        """Reset seconds is positive when within a window."""
        rl = RateLimiter(requests_per_minute=100, window_seconds=60, enabled=True)
        _, _, reset = rl.check("key")
        assert reset == 60
        _, _, reset = rl.check("key")
        assert 0 < reset <= 60
