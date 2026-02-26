"""Tests for SecurityMiddleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import EXEMPT_PATH_PREFIXES, EXEMPT_PATHS, SecurityMiddleware
from security import APIKeyAuth, RateLimiter


def _make_app(api_keys=None, rate_limit_enabled=False, rate_limit_rpm=60):
    """Create a minimal FastAPI app with SecurityMiddleware for testing."""
    app = FastAPI()
    api_key_auth = APIKeyAuth(api_keys)
    rate_limiter = RateLimiter(requests_per_minute=rate_limit_rpm, enabled=rate_limit_enabled)
    app.add_middleware(SecurityMiddleware, api_key_auth=api_key_auth, rate_limiter=rate_limiter)

    @app.get("/v1/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/health/live")
    def health_live():
        return {"status": "alive"}

    @app.get("/v1/health/ready")
    def health_ready():
        return {"status": "ready"}

    @app.get("/")
    def root():
        return {"status": "root"}

    @app.get("/api/health")
    def api_health():
        return {"status": "ok"}

    @app.get("/api/metrics")
    def api_metrics():
        return {"data": {"epoch": 1}}

    @app.get("/dashboard/test")
    def dashboard_test():
        return {"dashboard": True}

    return app


class TestSecurityMiddleware:
    """Tests for SecurityMiddleware integration."""

    @pytest.mark.unit
    def test_exempt_health_paths(self):
        app = _make_app(api_keys=["test-key"])
        client = TestClient(app)
        assert client.get("/v1/health").status_code == 200
        assert client.get("/v1/health/live").status_code == 200
        assert client.get("/v1/health/ready").status_code == 200

    @pytest.mark.unit
    def test_exempt_root_and_api_health(self):
        app = _make_app(api_keys=["test-key"])
        client = TestClient(app)
        assert client.get("/").status_code == 200
        assert client.get("/api/health").status_code == 200

    @pytest.mark.unit
    def test_exempt_dashboard_prefix(self):
        app = _make_app(api_keys=["test-key"])
        client = TestClient(app)
        assert client.get("/dashboard/test").status_code == 200

    @pytest.mark.unit
    def test_auth_required_returns_401(self):
        app = _make_app(api_keys=["test-key"])
        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 401

    @pytest.mark.unit
    def test_invalid_key_returns_401(self):
        app = _make_app(api_keys=["test-key"])
        client = TestClient(app)
        resp = client.get("/api/metrics", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    @pytest.mark.unit
    def test_valid_key_passes(self):
        app = _make_app(api_keys=["test-key"])
        client = TestClient(app)
        resp = client.get("/api/metrics", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert resp.json()["data"]["epoch"] == 1

    @pytest.mark.unit
    def test_rate_limit_exceeded_returns_429(self):
        app = _make_app(rate_limit_enabled=True, rate_limit_rpm=2)
        client = TestClient(app)
        client.get("/api/metrics")
        client.get("/api/metrics")
        resp = client.get("/api/metrics")
        assert resp.status_code == 429

    @pytest.mark.unit
    def test_rate_limit_headers_included(self):
        app = _make_app(rate_limit_enabled=True, rate_limit_rpm=100)
        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    @pytest.mark.unit
    def test_no_auth_when_disabled(self):
        app = _make_app()  # No api_keys = disabled
        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_exempt_paths_set(self):
        """Verify the exempt paths contain expected entries."""
        assert "/v1/health" in EXEMPT_PATHS
        assert "/v1/health/live" in EXEMPT_PATHS
        assert "/v1/health/ready" in EXEMPT_PATHS
        assert "/" in EXEMPT_PATHS
        assert "/api/health" in EXEMPT_PATHS
        assert "/docs" in EXEMPT_PATHS
        assert "/openapi.json" in EXEMPT_PATHS
        assert "/redoc" in EXEMPT_PATHS

    @pytest.mark.unit
    def test_exempt_path_prefixes(self):
        """Verify the exempt path prefixes contain expected entries."""
        assert "/dashboard" in EXEMPT_PATH_PREFIXES
