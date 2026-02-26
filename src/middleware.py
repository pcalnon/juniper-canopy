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
