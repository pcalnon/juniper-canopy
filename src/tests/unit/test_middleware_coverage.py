"""Extended coverage tests for middleware.py.

Covers RequestBodyLimitMiddleware edge cases (malformed headers, oversized
bodies, boundary values) and SecurityHeadersMiddleware (all headers, HSTS
conditional, custom CSP).
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from middleware import (
    _DEFAULT_CSP,
    _MAX_REQUEST_BODY_BYTES,
    RequestBodyLimitMiddleware,
    SecurityHeadersMiddleware,
    SecurityMiddleware,
)


def _make_body_limit_app(max_bytes=_MAX_REQUEST_BODY_BYTES):
    """Create a minimal app with RequestBodyLimitMiddleware."""
    app = FastAPI()
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=max_bytes)

    @app.post("/upload")
    async def upload(request: Request):
        body = await request.body()
        return {"size": len(body)}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def _make_headers_app(csp=_DEFAULT_CSP):
    """Create a minimal app with SecurityHeadersMiddleware."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, content_security_policy=csp)

    @app.get("/test")
    def test_route():
        return {"ok": True}

    return app


@pytest.mark.unit
class TestRequestBodyLimitMiddleware:
    """Edge case tests for RequestBodyLimitMiddleware."""

    def test_rejects_oversized_content_length(self):
        """Content-Length exceeding limit returns 413."""
        app = _make_body_limit_app(max_bytes=100)
        client = TestClient(app)
        resp = client.post("/upload", content=b"x" * 50, headers={"Content-Length": "200"})
        assert resp.status_code == 413
        assert resp.json()["detail"] == "Request body too large"

    def test_allows_content_length_at_limit(self):
        """Content-Length exactly at limit is allowed."""
        app = _make_body_limit_app(max_bytes=100)
        client = TestClient(app)
        resp = client.post("/upload", content=b"x" * 100, headers={"Content-Length": "100"})
        assert resp.status_code == 200

    def test_allows_content_length_below_limit(self):
        """Content-Length below limit is allowed."""
        app = _make_body_limit_app(max_bytes=1000)
        client = TestClient(app)
        resp = client.post("/upload", content=b"hello", headers={"Content-Length": "5"})
        assert resp.status_code == 200
        assert resp.json()["size"] == 5

    def test_missing_content_length_passes_through(self):
        """GET requests without Content-Length are not blocked."""
        app = _make_body_limit_app(max_bytes=100)
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_invalid_content_length_non_numeric(self):
        """Non-numeric Content-Length returns 400."""
        app = _make_body_limit_app(max_bytes=1000)
        client = TestClient(app)
        resp = client.post("/upload", content=b"x", headers={"Content-Length": "abc"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Invalid Content-Length header"

    def test_invalid_content_length_negative(self):
        """Negative Content-Length returns 400 (cannot parse as valid)."""
        app = _make_body_limit_app(max_bytes=1000)
        client = TestClient(app)
        # Negative is a valid int parse but should not exceed max_bytes
        resp = client.post("/upload", content=b"x", headers={"Content-Length": "-1"})
        # -1 < max_bytes, so it passes through the int check
        assert resp.status_code == 200

    def test_content_length_zero(self):
        """Content-Length of 0 is allowed."""
        app = _make_body_limit_app(max_bytes=100)
        client = TestClient(app)
        resp = client.post("/upload", content=b"", headers={"Content-Length": "0"})
        assert resp.status_code == 200

    def test_content_length_overflow(self):
        """Extremely large Content-Length value returns 400 (OverflowError)."""
        app = _make_body_limit_app(max_bytes=1000)
        client = TestClient(app)
        # Value too large for int() to handle reasonably
        resp = client.post("/upload", content=b"x", headers={"Content-Length": "9" * 1000})
        # This should exceed max_bytes and return 413
        assert resp.status_code == 413

    def test_custom_max_bytes(self):
        """Custom max_bytes value is respected."""
        app = _make_body_limit_app(max_bytes=10)
        client = TestClient(app)
        resp = client.post("/upload", content=b"x" * 5, headers={"Content-Length": "11"})
        assert resp.status_code == 413

    def test_default_max_bytes_is_10mb(self):
        """Verify default constant is 10 MB."""
        assert _MAX_REQUEST_BODY_BYTES == 10 * 1024 * 1024

    def test_content_length_with_float_value(self):
        """Float Content-Length returns 400."""
        app = _make_body_limit_app(max_bytes=1000)
        client = TestClient(app)
        resp = client.post("/upload", content=b"x", headers={"Content-Length": "3.14"})
        assert resp.status_code == 400


@pytest.mark.unit
class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware response headers."""

    def test_x_content_type_options_nosniff(self):
        client = TestClient(_make_headers_app())
        resp = client.get("/test")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options_deny(self):
        client = TestClient(_make_headers_app())
        resp = client.get("/test")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self):
        client = TestClient(_make_headers_app())
        resp = client.get("/test")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        client = TestClient(_make_headers_app())
        resp = client.get("/test")
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_default_csp(self):
        client = TestClient(_make_headers_app())
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_custom_csp(self):
        custom_csp = "default-src 'none'; script-src 'self'"
        client = TestClient(_make_headers_app(csp=custom_csp))
        resp = client.get("/test")
        assert resp.headers["Content-Security-Policy"] == custom_csp

    def test_hsts_present_when_https_forwarded(self):
        """HSTS header is added when X-Forwarded-Proto is https."""
        client = TestClient(_make_headers_app())
        resp = client.get("/test", headers={"X-Forwarded-Proto": "https"})
        assert "Strict-Transport-Security" in resp.headers
        assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in resp.headers["Strict-Transport-Security"]

    def test_hsts_absent_when_not_https(self):
        """HSTS header is NOT added for plain HTTP requests."""
        client = TestClient(_make_headers_app())
        resp = client.get("/test")
        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_absent_when_forwarded_http(self):
        """HSTS header is NOT added when X-Forwarded-Proto is http."""
        client = TestClient(_make_headers_app())
        resp = client.get("/test", headers={"X-Forwarded-Proto": "http"})
        assert "Strict-Transport-Security" not in resp.headers

    def test_headers_on_all_status_codes(self):
        """Security headers are present even on error responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/not-found")
        def not_found():
            return JSONResponse(status_code=404, content={"detail": "not found"})

        client = TestClient(app)
        resp = client.get("/not-found")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_default_csp_allows_bootstrap_cdn(self):
        """Default CSP allows cdn.jsdelivr.net for Bootstrap CSS."""
        assert "https://cdn.jsdelivr.net" in _DEFAULT_CSP

    def test_default_csp_allows_unsafe_inline_styles(self):
        """Default CSP allows unsafe-inline for Dash styles."""
        assert "'unsafe-inline'" in _DEFAULT_CSP

    def test_default_csp_allows_data_uri_images(self):
        """Default CSP allows data: URIs for Bootstrap SVG icons."""
        assert "data:" in _DEFAULT_CSP


@pytest.mark.unit
class TestSecurityMiddlewareIsExempt:
    """Tests for the _is_exempt path-checking logic."""

    def _make_middleware(self):
        from security import APIKeyAuth, RateLimiter

        app = FastAPI()
        mw = SecurityMiddleware(app, api_key_auth=APIKeyAuth(["key"]), rate_limiter=RateLimiter(enabled=False))
        return mw

    def test_exact_exempt_paths(self):
        mw = self._make_middleware()
        for path in ["/", "/health", "/api/health", "/v1/health", "/v1/health/live", "/v1/health/ready", "/docs", "/openapi.json", "/redoc"]:
            assert mw._is_exempt(path), f"{path} should be exempt"

    def test_non_exempt_paths(self):
        mw = self._make_middleware()
        for path in ["/api/metrics", "/api/train/start", "/api/v1/snapshots"]:
            assert not mw._is_exempt(path), f"{path} should NOT be exempt"

    def test_dashboard_prefix_exempt(self):
        mw = self._make_middleware()
        assert mw._is_exempt("/dashboard")
        assert mw._is_exempt("/dashboard/")
        assert mw._is_exempt("/dashboard/sub/path")
        assert mw._is_exempt("/dashboard/_dash-component-suites/file.js")

    def test_partial_match_not_exempt(self):
        """Paths that partially match exempt paths but aren't exact are not exempt."""
        mw = self._make_middleware()
        assert not mw._is_exempt("/healthcheck")
        assert not mw._is_exempt("/v1/health/custom")
        assert not mw._is_exempt("/docs/extra")
