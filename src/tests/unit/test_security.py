"""Tests for API security: APIKeyAuth, RateLimiter, and module-level functions."""

import time
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from security import (
    INTERNAL_REQUEST_HEADER,
    INTERNAL_REQUEST_TOKEN,
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

    # APD-ECO-008: parity with the three sibling copies (juniper-service-core,
    # juniper-data, juniper-cascor) -- the blank-key filter and the
    # non-short-circuiting compare.

    def test_blank_and_whitespace_keys_are_filtered(self):
        auth = APIKeyAuth(["", "   ", "\t\n", "key1"])
        assert auth.enabled is True
        assert auth._api_keys == {"key1"}
        assert auth.validate("key1") is True
        # Unfiltered, a configured "" accepted an empty presented key.
        assert auth.validate("") is False
        assert auth.validate("   ") is False

    def test_only_blank_keys_leave_auth_disabled(self):
        auth = APIKeyAuth(["", "   ", "\t"])
        assert auth.enabled is False
        assert auth._api_keys == set()

    def test_non_str_entries_are_dropped_without_raising(self):
        # The unhashable entries made the old ``set(api_keys)`` raise TypeError;
        # the isinstance guard runs before anything is hashed.
        auth = APIKeyAuth([None, 123, b"key1", {"a": 1}, ["x"], "key1"])  # type: ignore[list-item]
        assert auth._api_keys == {"key1"}
        assert auth.enabled is True
        assert auth.validate("key1") is True

    @pytest.mark.parametrize("keys", [None, [], [""], ["   "], ["\t", ""], ["k"], [" k "], ["", "k"]])
    def test_enabled_agrees_with_the_boot_posture_check(self, keys):
        """``enforce_auth_posture`` classifies keys with ``real_keys``; APIKeyAuth must agree.

        Before APD-ECO-008 the two disagreed on every blank-only input: the boot
        check logged "running OPEN" while APIKeyAuth enabled itself on the blank.
        """
        from juniper_service_core.auth_posture import auth_is_configured

        assert APIKeyAuth(keys).enabled is auth_is_configured(keys)

    def test_validate_compares_every_key_even_when_the_first_matches(self, monkeypatch):
        """``any()`` stopped at the first match, so the comparison count leaked its position."""
        from types import SimpleNamespace

        auth = APIKeyAuth(["key1", "key2", "key3"])
        compared = []
        real_compare = auth.validate.__globals__["hmac"].compare_digest

        def counting_compare(a, b):
            compared.append(b)
            return real_compare(a, b)

        # Patch the globals validate() actually resolves ``hmac`` from, so a module
        # re-import elsewhere in the session cannot leave this test patching a copy.
        monkeypatch.setitem(auth.validate.__globals__, "hmac", SimpleNamespace(compare_digest=counting_compare))
        first = next(iter(auth._api_keys))  # the key validate() compares first
        assert auth.validate(first) is True
        assert sorted(compared) == ["key1", "key2", "key3"]

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

    def test_get_key_prefers_api_key_over_client_ip(self):
        limiter = RateLimiter(enabled=True)
        request = MagicMock()
        request.client.host = "10.1.2.3"
        # An authenticated key is the rate-limit identity; the client IP is
        # only the anonymous fallback.
        assert limiter._get_key(request, "secret-key") == "key:secret-key"
        assert limiter._get_key(request, None) == "ip:10.1.2.3"


class TestInternalRequestRateLimitExemption:
    """#2a: canopy's own server-side self-calls carry a per-process token that
    exempts them from rate limiting; external clients cannot forge it."""

    @staticmethod
    def _request(headers):
        request = MagicMock()
        request.headers = headers
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.state = MagicMock()
        return request

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_internal_token_exempts_from_rate_limit(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = self._request({INTERNAL_REQUEST_HEADER: INTERNAL_REQUEST_TOKEN})
        # Far exceed the limit; the valid internal token keeps every call exempt.
        for _ in range(5):
            await limiter(request)  # must not raise

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_forged_internal_token_is_not_exempt(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = self._request({INTERNAL_REQUEST_HEADER: "not-the-real-token"})
        await limiter(request)
        with pytest.raises(HTTPException) as exc:
            await limiter(request)
        assert exc.value.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_missing_internal_token_is_not_exempt(self):
        limiter = RateLimiter(requests_per_minute=1, enabled=True)
        request = self._request({})
        await limiter(request)
        with pytest.raises(HTTPException) as exc:
            await limiter(request)
        assert exc.value.status_code == 429

    @pytest.mark.unit
    def test_internal_api_headers_carries_exemption_token(self):
        """Round-trip: the headers the dashboard attaches to its self-calls
        carry exactly the token the limiter exempts."""
        from frontend.internal_api import internal_api_headers

        headers = internal_api_headers()
        assert headers.get(INTERNAL_REQUEST_HEADER) == INTERNAL_REQUEST_TOKEN


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

    def test_whitespace_only_env_key_leaves_auth_disabled(self, monkeypatch):
        """APD-ECO-008: the one blank shape that reached APIKeyAuth in production.

        ``get_secret`` strips a secret FILE but returns the env var raw, and
        ``get_api_key_auth`` maps only a falsy key to None -- so a whitespace-only
        ``CANOPY_API_KEY`` arrived unfiltered and enabled auth on it.
        """
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        monkeypatch.setenv("CANOPY_API_KEY", "   ")
        auth = get_api_key_auth()
        assert auth.enabled is False

    @pytest.mark.parametrize("source", ["env", "file"])
    def test_set_but_blank_key_logs_a_distinct_warning(self, monkeypatch, caplog, tmp_path, source):
        """APD-ECO-008: SET-but-blank gets its own WARNING, naming the variable and never the value.

        The boot posture check words a blank key exactly like an unset one, so
        without this an operator whose key went blank gets no new signal.
        """
        blank = " \t  "  # distinctive whitespace: none of it may reach the log
        if source == "env":
            monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
            monkeypatch.setenv("CANOPY_API_KEY", blank)
        else:
            secret_file = tmp_path / "canopy_api_key"
            secret_file.write_text(blank + "\n")
            monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
            monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        with caplog.at_level("WARNING", logger="juniper_canopy.security"):
            auth = get_api_key_auth()
        assert auth.enabled is False
        warnings = [r for r in caplog.records if r.name == "juniper_canopy.security" and r.levelname == "WARNING"]
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "CANOPY_API_KEY" in message
        assert "blank" in message and "DISABLED" in message
        assert "\t" not in message and " " not in message

    @pytest.mark.parametrize("value", [None, "real-key"])
    def test_no_blank_key_warning_when_unset_or_real(self, monkeypatch, caplog, value):
        """Over-correction guard: UNSET and a real key are not the blank case."""
        monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
        if value is None:
            monkeypatch.delenv("CANOPY_API_KEY", raising=False)
        else:
            monkeypatch.setenv("CANOPY_API_KEY", value)
        with caplog.at_level("WARNING", logger="juniper_canopy.security"):
            get_api_key_auth()
        assert [r for r in caplog.records if r.name == "juniper_canopy.security"] == []

    def test_get_rate_limiter_reads_settings(self):
        from unittest.mock import MagicMock, patch

        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 100
        with patch("settings.get_settings", return_value=mock_settings):
            limiter = get_rate_limiter()
        assert limiter.enabled is True
        assert limiter.limit == 100
