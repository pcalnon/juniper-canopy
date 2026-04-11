"""FastAPI middleware for security and request processing.

Applies API key authentication and rate limiting to non-exempt paths.
WebSocket upgrade requests are not intercepted by BaseHTTPMiddleware,
so /ws/* paths are inherently exempt.
"""

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from canopy_constants import SecurityConstants
from security import APIKeyAuth, RateLimiter

# Module-level aliases preserved for tests that import these names directly
# (test_middleware.py, test_middleware_coverage.py, test_csp_bootstrap_cdn.py).
# The canonical source of truth is :class:`canopy_constants.SecurityConstants`.
EXEMPT_PATH_PREFIXES = SecurityConstants.EXEMPT_PATH_PREFIXES
EXEMPT_PATHS = SecurityConstants.EXEMPT_PATHS
_DEFAULT_CSP = SecurityConstants.DEFAULT_CSP_POLICY
_MAX_REQUEST_BODY_BYTES = SecurityConstants.MAX_REQUEST_BODY_BYTES


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

        response.headers[SecurityConstants.HEADER_X_CONTENT_TYPE_OPTIONS] = SecurityConstants.NOSNIFF_VALUE
        response.headers[SecurityConstants.HEADER_X_FRAME_OPTIONS] = SecurityConstants.FRAME_OPTIONS_DENY
        response.headers[SecurityConstants.HEADER_REFERRER_POLICY] = SecurityConstants.REFERRER_POLICY_VALUE
        response.headers[SecurityConstants.HEADER_PERMISSIONS_POLICY] = SecurityConstants.PERMISSIONS_POLICY_VALUE
        response.headers[SecurityConstants.HEADER_CONTENT_SECURITY_POLICY] = self._csp

        if request.headers.get(SecurityConstants.HEADER_X_FORWARDED_PROTO) == SecurityConstants.HTTPS_SCHEME:
            response.headers[SecurityConstants.HEADER_STRICT_TRANSPORT_SECURITY] = SecurityConstants.HSTS_VALUE

        return response


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds a configurable limit."""

    def __init__(self, app: ASGIApp, max_bytes: int = _MAX_REQUEST_BODY_BYTES) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get(SecurityConstants.HEADER_CONTENT_LENGTH)
        if content_length is not None:
            try:
                if int(content_length) > self._max_bytes:
                    return JSONResponse(status_code=SecurityConstants.HTTP_PAYLOAD_TOO_LARGE, content={"detail": SecurityConstants.ERROR_BODY_TOO_LARGE})
            except (ValueError, OverflowError):
                return JSONResponse(status_code=SecurityConstants.HTTP_BAD_REQUEST, content={"detail": SecurityConstants.ERROR_INVALID_CONTENT_LENGTH})
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
            response.headers[SecurityConstants.HEADER_RATE_LIMIT] = str(self._rate_limiter.limit)
            response.headers[SecurityConstants.HEADER_RATE_LIMIT_REMAINING] = str(request.state.rate_limit_remaining)
            response.headers[SecurityConstants.HEADER_RATE_LIMIT_RESET] = str(request.state.rate_limit_reset)

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
