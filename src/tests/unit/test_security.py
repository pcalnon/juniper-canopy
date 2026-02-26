"""Tests for API security: APIKeyAuth, RateLimiter, and module-level functions."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from security import (
    APIKeyAuth,
    RateLimiter,
    get_api_key_auth,
    get_rate_limiter,
    reset_security_state,
)


class TestAPIKeyAuth:
    """Tests for APIKeyAuth class."""

    def test_disabled_when_no_keys(self):
        auth = APIKeyAuth()
        assert auth.enabled is False

    def test_disabled_when_empty_list(self):
        auth = APIKeyAuth([])
        assert auth.enabled is False

    def test_disabled_when_none(self):
        auth = APIKeyAuth(None)
        assert auth.enabled is False

    def test_enabled_with_keys(self):
        auth = APIKeyAuth(["key1"])
        assert auth.enabled is True

    def test_validate_when_disabled(self):
        auth = APIKeyAuth()
        assert auth.validate(None) is True
        assert auth.validate("anything") is True

    def test_validate_valid_key(self):
        auth = APIKeyAuth(["key1", "key2"])
        assert auth.validate("key1") is True
        assert auth.validate("key2") is True

    def test_validate_invalid_key(self):
        auth = APIKeyAuth(["key1"])
        assert auth.validate("wrong") is False

    def test_validate_none_when_enabled(self):
        auth = APIKeyAuth(["key1"])
        assert auth.validate(None) is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_returns_none_when_disabled(self):
        auth = APIKeyAuth()
        request = MagicMock()
        request.headers = {}
        result = await auth(request)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_raises_401_missing_key(self):
        auth = APIKeyAuth(["key1"])
        request = MagicMock()
        request.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_raises_401_invalid_key(self):
        auth = APIKeyAuth(["key1"])
        request = MagicMock()
        request.headers = {"X-API-Key": "wrong"}
        with pytest.raises(HTTPException) as exc_info:
            await auth(request)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_returns_key_when_valid(self):
        auth = APIKeyAuth(["key1"])
        request = MagicMock()
        request.headers = {"X-API-Key": "key1"}
        result = await auth(request)
        assert result == "key1"


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_disabled_by_default_false(self):
        limiter = RateLimiter(enabled=False)
        assert limiter.enabled is False

    def test_enabled(self):
        limiter = RateLimiter(enabled=True)
        assert limiter.enabled is True

    def test_properties(self):
        limiter = RateLimiter(requests_per_minute=100, window_seconds=30, enabled=True)
        assert limiter.limit == 100
        assert limiter.window == 30
        assert limiter.enabled is True

    def test_check_when_disabled(self):
        limiter = RateLimiter(enabled=False)
        allowed, remaining, reset = limiter.check("test-key")
        assert allowed is True

    def test_check_within_limit(self):
        limiter = RateLimiter(requests_per_minute=5, enabled=True)
        allowed, remaining, _ = limiter.check("test-key")
        assert allowed is True
        assert remaining == 4

    def test_check_over_limit(self):
        limiter = RateLimiter(requests_per_minute=2, enabled=True)
        limiter.check("key1")
        limiter.check("key1")
        allowed, remaining, _ = limiter.check("key1")
        assert allowed is False
        assert remaining == 0

    def test_separate_keys(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        limiter.check("key1")
        allowed, _, _ = limiter.check("key2")
        assert allowed is True

    def test_window_reset(self):
        limiter = RateLimiter(requests_per_minute=1, window_seconds=1, enabled=True)
        limiter.check("key1")
        allowed, _, _ = limiter.check("key1")
        assert allowed is False
        time.sleep(1.1)
        allowed, _, _ = limiter.check("key1")
        assert allowed is True

    def test_reset(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        limiter.check("key1")
        limiter.reset()
        allowed, _, _ = limiter.check("key1")
        assert allowed is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_raises_429_when_exceeded(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        await limiter(request)
        with pytest.raises(HTTPException) as exc_info:
            await limiter(request)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_call_does_nothing_when_disabled(self):
        limiter = RateLimiter(enabled=False)
        request = MagicMock()
        await limiter(request)  # Should not raise


class TestSecurityModuleFunctions:
    """Tests for module-level singleton functions."""

    def setup_method(self):
        reset_security_state()

    def teardown_method(self):
        reset_security_state()

    def test_get_api_key_auth_returns_singleton(self):
        auth1 = get_api_key_auth()
        auth2 = get_api_key_auth()
        assert auth1 is auth2

    def test_get_rate_limiter_returns_singleton(self):
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_reset_clears_singletons(self):
        auth1 = get_api_key_auth()
        reset_security_state()
        auth2 = get_api_key_auth()
        assert auth1 is not auth2

    def test_get_api_key_auth_reads_env(self, monkeypatch):
        monkeypatch.setenv("CANOPY_API_KEY", "test-key")
        auth = get_api_key_auth()
        assert auth.enabled is True
        assert auth.validate("test-key") is True

    def test_get_rate_limiter_reads_env(self, monkeypatch):
        monkeypatch.setenv("CANOPY_RATE_LIMIT_ENABLED", "true")
        monkeypatch.setenv("CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE", "100")
        limiter = get_rate_limiter()
        assert limiter.enabled is True
        assert limiter.limit == 100
