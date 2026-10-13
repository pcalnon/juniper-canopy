"""FastAPI middleware for security and request processing.

Applies API key authentication and rate limiting to non-exempt paths.
WebSocket upgrade requests are not intercepted by BaseHTTPMiddleware,
so /ws/* paths are inherently exempt.
"""

from typing import Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from canopy_constants import BackendConstants, SecurityConstants
from security import APIKeyAuth, RateLimiter

# Module-level aliases preserved for tests that import these names directly
# (test_middleware.py, test_middleware_coverage.py, test_csp_bootstrap_cdn.py).
# The canonical source of truth is :class:`canopy_constants.SecurityConstants`.
EXEMPT_PATH_PREFIXES = SecurityConstants.EXEMPT_PATH_PREFIXES
EXEMPT_PATHS = SecurityConstants.EXEMPT_PATHS
# PR-1 (Start-Training 401 fix): the key-exempt tier — auth-exempt but STILL
# rate-limited (the same-origin browser control surface). Exposed as module
# aliases for parity with the fully-exempt names above.
KEY_EXEMPT_PATH_PREFIXES = SecurityConstants.KEY_EXEMPT_PATH_PREFIXES
KEY_EXEMPT_PATHS = SecurityConstants.KEY_EXEMPT_PATHS
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

        # PR-1: a key-exempt path skips the API-key gate but is STILL
        # rate-limited. The same-origin browser control surface (/api/csrf,
        # /api/train/*) lives here; /api/train/* then owns its real authn via
        # the require_browser_control_auth dependency (Origin + CSRF).
        key_exempt = self._is_key_exempt(path)

        api_key = None
        try:
            if self._api_key_auth.enabled and not key_exempt:
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

    def _is_key_exempt(self, path: str) -> bool:
        """Check if a path is key-exempt (auth-exempt but still rate-limited).

        PR-1 (Start-Training 401 fix): the same-origin browser control surface
        (``/api/csrf`` exact, ``/api/train/`` prefix) skips the API-key gate —
        the browser cannot hold the server key — but stays under the rate
        limiter, unlike the fully-exempt :meth:`_is_exempt` set. ``/api/train/*``
        is then authenticated per-route by ``require_browser_control_auth``
        (Origin + CSRF); ``/api/csrf`` is hardened in its own handler.

        Args:
            path: The request path.

        Returns:
            True if the path is key-exempt, False otherwise.
        """
        if path in KEY_EXEMPT_PATHS:
            return True
        return any(path.startswith(prefix) for prefix in KEY_EXEMPT_PATH_PREFIXES)


class CallerBudgetMiddleware:
    """Record each request's caller budget as a deadline (X7 slice 1d, C10).

    **Pure ASGI, not ``BaseHTTPMiddleware``, and that is the point.**
    ``BaseHTTPMiddleware`` runs the rest of the application in a *separate anyio task*. A
    ``ContextVar`` set before ``call_next`` is copied into that task at creation, so it
    would probably work — but "probably", across Starlette versions, for the mechanism
    that decides whether an upstream call is issued, is not a foundation. A plain ASGI
    callable runs the endpoint in the *same* task, so the deadline reaches
    ``asyncio.to_thread``'s context copy by construction rather than by version.

    Budget resolution, in order:

    1. the ``X-Canopy-Budget-Seconds`` header, when the caller declares one (clamped);
    2. the measured per-route table, matched exactly then by longest path prefix;
    3. ``None`` — bounded by the gate, but never declined.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            # WebSocket and lifespan carry no caller budget: a WS connection is not a
            # request/response pair with a client-side timeout to honour.
            await self.app(scope, receive, send)
            return

        from backend.admission import set_deadline

        set_deadline(self._resolve_budget(scope))
        await self.app(scope, receive, send)

    @staticmethod
    def _resolve_budget(scope) -> Optional[float]:
        declared = CallerBudgetMiddleware._declared_budget(scope)
        if declared is not None:
            return declared

        path = scope.get("path", "")
        table = BackendConstants.CALLER_BUDGET_SECONDS
        if path in table:
            return float(table[path])
        # Prefix match for templated routes. Longest first, so a specific entry wins over
        # a shorter one that merely prefixes it.
        for route in sorted(table, key=len, reverse=True):
            if path.startswith(route + "/"):
                return float(table[route])
        return None

    @staticmethod
    def _declared_budget(scope) -> Optional[float]:
        wanted = BackendConstants.CALLER_BUDGET_HEADER.lower().encode()
        for key, value in scope.get("headers") or []:
            if key.lower() != wanted:
                continue
            try:
                seconds = float(value.decode())
            except ValueError:  # UnicodeDecodeError is a ValueError subclass
                # A malformed budget is not a reason to refuse the request; fall through
                # to the table. Trusting it would let a typo pin or starve a gate slot.
                return None
            if seconds <= 0:
                return None
            return max(
                BackendConstants.CALLER_BUDGET_MIN_SECONDS,
                min(seconds, BackendConstants.CALLER_BUDGET_MAX_SECONDS),
            )
        return None
