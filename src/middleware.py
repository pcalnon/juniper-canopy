"""FastAPI middleware for security and request processing.

Applies API key authentication and rate limiting to non-exempt paths.
WebSocket upgrade requests are not intercepted by BaseHTTPMiddleware,
so /ws/* paths are inherently exempt.
"""

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from security import APIKeyAuth, RateLimiter

EXEMPT_PATH_PREFIXES = ("/dashboard",)

EXEMPT_PATHS = {
    "/",
    "/health",
    "/api/health",
    "/v1/health",
    "/v1/health/live",
    "/v1/health/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Default Content-Security-Policy for Canopy (Dash requires unsafe-inline for styles).
_DEFAULT_CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Injects standard security headers (X-Content-Type-Options, X-Frame-Options,
    Referrer-Policy, Permissions-Policy, CSP, and conditional HSTS) into every
    HTTP response.
    """

    def __init__(self, app: ASGIApp, content_security_policy: str = _DEFAULT_CSP) -> None:
        super().__init__(app)
        self._csp = content_security_policy

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = self._csp

        if request.headers.get("X-Forwarded-Proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


_MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds a configurable limit."""

    def __init__(self, app: ASGIApp, max_bytes: int = _MAX_REQUEST_BODY_BYTES) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > self._max_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        return await call_next(request)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication and rate limiting.

    Applies authentication and rate limiting to all requests except
    explicitly exempt paths (health checks, docs, dashboard).
    """

    def __init__(
        self,
        app: ASGIApp,
        api_key_auth: APIKeyAuth,
        rate_limiter: RateLimiter,
    ) -> None:
        """Initialize the security middleware.

        Args:
            app: The ASGI application.
            api_key_auth: API key authentication handler.
            rate_limiter: Rate limiter instance.
        """
        super().__init__(app)
        self._api_key_auth = api_key_auth
        self._rate_limiter = rate_limiter

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process the request through security checks.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response from the application.
        """
        path = request.url.path

        if self._is_exempt(path):
            return await call_next(request)

        api_key = None
        try:
            if self._api_key_auth.enabled:
                api_key = await self._api_key_auth(request)

            if self._rate_limiter.enabled:
                await self._rate_limiter(request, api_key)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )

        response = await call_next(request)

        if self._rate_limiter.enabled and hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Limit"] = str(self._rate_limiter.limit)
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
            response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if a path is exempt from security checks.

        Exempt paths include exact matches (health, docs) and prefix
        matches (/dashboard/* for Dash app and its static assets).

        Args:
            path: The request path.

        Returns:
            True if the path is exempt, False otherwise.
        """
        if path in EXEMPT_PATHS:
            return True
        return any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)
