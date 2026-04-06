"""Security validation tests: auth bypass, injection, CORS.

Tests for authentication bypass attempts, injection vectors in API
headers, CORS origin validation, and WebSocket auth rejection.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

from middleware import SecurityMiddleware
from security import APIKeyAuth, RateLimiter


def _make_secured_app(api_keys=None, cors_origins=None, cors_methods=None):
    """Create a FastAPI app with security middleware and optional CORS."""
    app = FastAPI()

    if cors_origins:
        allow_credentials = "*" not in cors_origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=allow_credentials,
            allow_methods=cors_methods or ["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["X-API-Key", "Content-Type", "Accept"],
        )

    if api_keys:
        app.add_middleware(
            SecurityMiddleware,
            api_key_auth=APIKeyAuth(api_keys),
            rate_limiter=RateLimiter(enabled=False),
        )

    @app.get("/api/data")
    def get_data():
        return {"secret": "value"}

    @app.post("/api/data")
    def post_data():
        return {"created": True}

    @app.get("/")
    def root():
        return {"public": True}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


@pytest.mark.unit
class TestAuthBypass:
    """Tests for authentication bypass attempts."""

    def test_missing_api_key_header(self):
        """Request without X-API-Key header returns 401."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data")
        assert resp.status_code == 401

    def test_empty_api_key_header(self):
        """Empty X-API-Key header returns 401."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": ""})
        assert resp.status_code == 401

    def test_whitespace_api_key(self):
        """Whitespace-only API key returns 401."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": "   "})
        assert resp.status_code == 401

    def test_api_key_with_leading_trailing_spaces(self):
        """Key with surrounding spaces does not match (no implicit strip)."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": " valid-key "})
        assert resp.status_code == 401

    def test_case_sensitive_api_key(self):
        """API key matching is case-sensitive."""
        client = TestClient(_make_secured_app(api_keys=["Valid-Key"]))
        resp = client.get("/api/data", headers={"X-API-Key": "valid-key"})
        assert resp.status_code == 401

    def test_partial_key_match_rejected(self):
        """Partial key match is rejected."""
        client = TestClient(_make_secured_app(api_keys=["valid-key-123"]))
        resp = client.get("/api/data", headers={"X-API-Key": "valid-key"})
        assert resp.status_code == 401

    def test_wrong_header_name_ignored(self):
        """Key in wrong header name is not used for auth."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"Authorization": "Bearer valid-key"})
        assert resp.status_code == 401

    def test_valid_key_from_multiple_configured(self):
        """Any valid key from a set of configured keys works."""
        client = TestClient(_make_secured_app(api_keys=["key-1", "key-2", "key-3"]))
        assert client.get("/api/data", headers={"X-API-Key": "key-1"}).status_code == 200
        assert client.get("/api/data", headers={"X-API-Key": "key-2"}).status_code == 200
        assert client.get("/api/data", headers={"X-API-Key": "key-3"}).status_code == 200

    def test_exempt_paths_bypass_auth(self):
        """Exempt paths do not require authentication."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        assert client.get("/").status_code == 200
        assert client.get("/api/health").status_code == 200

    def test_401_response_is_json(self):
        """401 responses contain JSON detail."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data")
        assert resp.status_code == 401
        body = resp.json()
        assert "detail" in body


@pytest.mark.unit
class TestInjectionAttempts:
    """Tests for injection vectors in security headers."""

    def test_sql_injection_in_api_key(self):
        """SQL injection string in API key is rejected."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": "' OR '1'='1"})
        assert resp.status_code == 401

    def test_nosql_injection_in_api_key(self):
        """NoSQL injection payload in API key is rejected."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": '{"$ne": null}'})
        assert resp.status_code == 401

    def test_null_byte_in_api_key(self):
        """Null byte in API key is rejected."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": "valid\x00-key"})
        assert resp.status_code == 401

    def test_very_long_api_key(self):
        """Extremely long API key does not cause server error."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        long_key = "x" * 100_000
        resp = client.get("/api/data", headers={"X-API-Key": long_key})
        assert resp.status_code == 401

    def test_special_characters_in_api_key(self):
        """Special ASCII characters in API key are rejected."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": "!@#$%^&*(){}[]|\\/<>"})
        assert resp.status_code == 401

    def test_newline_in_api_key(self):
        """Newline injection in API key is rejected."""
        client = TestClient(_make_secured_app(api_keys=["valid-key"]))
        resp = client.get("/api/data", headers={"X-API-Key": "valid-key\r\nX-Injected: true"})
        assert resp.status_code == 401


@pytest.mark.unit
class TestCORSValidation:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_configured_origin(self):
        """Configured origin receives CORS headers."""
        app = _make_secured_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app)
        resp = client.options(
            "/api/data",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_cors_rejects_unconfigured_origin(self):
        """Unconfigured origin does not receive Access-Control-Allow-Origin."""
        app = _make_secured_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app)
        resp = client.options(
            "/api/data",
            headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "GET"},
        )
        assert resp.headers.get("access-control-allow-origin") != "http://evil.com"

    def test_cors_credentials_disabled_with_wildcard(self):
        """Wildcard origin disables credentials."""
        app = _make_secured_app(cors_origins=["*"])
        client = TestClient(app)
        resp = client.get("/api/data", headers={"Origin": "http://any.com"})
        assert resp.headers.get("access-control-allow-credentials") != "true"

    def test_cors_credentials_enabled_with_specific_origin(self):
        """Specific origin enables credentials."""
        app = _make_secured_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app)
        resp = client.options(
            "/api/data",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_cors_allows_x_api_key_header(self):
        """CORS preflight allows X-API-Key as a request header."""
        app = _make_secured_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app)
        resp = client.options(
            "/api/data",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        allowed_headers = resp.headers.get("access-control-allow-headers", "").lower()
        assert "x-api-key" in allowed_headers

    def test_cors_restricts_methods(self):
        """CORS does not allow PUT or PATCH by default."""
        app = _make_secured_app(cors_origins=["http://localhost:3000"], cors_methods=["GET", "POST", "DELETE", "OPTIONS"])
        client = TestClient(app)
        resp = client.options(
            "/api/data",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PUT",
            },
        )
        allowed_methods = resp.headers.get("access-control-allow-methods", "")
        assert "PUT" not in allowed_methods

    def test_no_cors_headers_when_not_configured(self):
        """No CORS headers when cors_origins not set."""
        app = _make_secured_app()  # No CORS
        client = TestClient(app)
        resp = client.get("/api/data", headers={"Origin": "http://localhost:3000"})
        assert "access-control-allow-origin" not in resp.headers


@pytest.mark.unit
class TestAPIKeyAuthUnit:
    """Unit tests for APIKeyAuth class directly."""

    def test_disabled_when_no_keys(self):
        auth = APIKeyAuth(None)
        assert auth.enabled is False

    def test_disabled_when_empty_list(self):
        auth = APIKeyAuth([])
        assert auth.enabled is False

    def test_enabled_with_keys(self):
        auth = APIKeyAuth(["key1"])
        assert auth.enabled is True

    def test_validate_returns_true_when_disabled(self):
        auth = APIKeyAuth(None)
        assert auth.validate(None) is True
        assert auth.validate("any-key") is True

    def test_validate_returns_false_for_none_when_enabled(self):
        auth = APIKeyAuth(["key1"])
        assert auth.validate(None) is False

    def test_validate_uses_constant_time_comparison(self):
        """Verify hmac.compare_digest is used (not simple ==)."""
        auth = APIKeyAuth(["test-key"])
        # This verifies functional behavior; timing attack test is in test_phase0_security.py
        assert auth.validate("test-key") is True
        assert auth.validate("wrong-key") is False

    def test_validate_against_multiple_keys(self):
        auth = APIKeyAuth(["alpha", "beta", "gamma"])
        assert auth.validate("alpha") is True
        assert auth.validate("beta") is True
        assert auth.validate("gamma") is True
        assert auth.validate("delta") is False


@pytest.mark.unit
class TestRateLimiterUnit:
    """Unit tests for RateLimiter class directly."""

    def test_disabled_always_allows(self):
        rl = RateLimiter(requests_per_minute=1, enabled=False)
        allowed, remaining, reset = rl.check("key")
        assert allowed is True

    def test_allows_up_to_limit(self):
        rl = RateLimiter(requests_per_minute=3, enabled=True)
        for i in range(3):
            allowed, remaining, _ = rl.check("key")
            assert allowed is True
            assert remaining == 3 - i - 1

    def test_blocks_over_limit(self):
        rl = RateLimiter(requests_per_minute=2, enabled=True)
        rl.check("key")
        rl.check("key")
        allowed, remaining, _ = rl.check("key")
        assert allowed is False
        assert remaining == 0

    def test_separate_keys_tracked_independently(self):
        rl = RateLimiter(requests_per_minute=1, enabled=True)
        allowed1, _, _ = rl.check("key-a")
        allowed2, _, _ = rl.check("key-b")
        assert allowed1 is True
        assert allowed2 is True

    def test_reset_clears_all_counters(self):
        rl = RateLimiter(requests_per_minute=1, enabled=True)
        rl.check("key")
        allowed, _, _ = rl.check("key")
        assert allowed is False
        rl.reset()
        allowed, _, _ = rl.check("key")
        assert allowed is True

    def test_properties_return_configured_values(self):
        rl = RateLimiter(requests_per_minute=100, window_seconds=30, enabled=True)
        assert rl.limit == 100
        assert rl.window == 30
        assert rl.enabled is True
