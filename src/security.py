"""API security: authentication and rate limiting.

Provides API key authentication and rate limiting for JuniperCanopy.
Configuration is read from environment variables:
    CANOPY_API_KEY: Single API key for authentication (disabled when unset).
    CANOPY_RATE_LIMIT_ENABLED: Enable rate limiting (default: false).
    CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE: Rate limit (default: 60).
"""

import hmac
import secrets
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader

from secrets_util import get_secret

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# #2a: per-process token marking canopy's OWN server-side self-calls — the Dash
# dashboard polling its own /api/* routes from callback handlers (localhost →
# localhost, same process). Generated fresh each process start, so external
# clients cannot forge it. Requests bearing it skip rate limiting: the
# dashboard's own high-frequency polling must not drain the shared
# per-IP/per-API-key bucket that real user actions depend on.
# ``frontend.internal_api.internal_api_headers()`` attaches it to every self-call.
INTERNAL_REQUEST_HEADER = "X-Canopy-Internal"
INTERNAL_REQUEST_TOKEN = secrets.token_urlsafe(32)


class APIKeyAuth:
    """API key authentication handler.

    Validates requests against configured API keys. When no API keys are
    configured, authentication is disabled (open access mode for development).
    """

    def __init__(self, api_keys: list[str] | None = None) -> None:
        """Initialize with optional list of valid API keys.

        Args:
            api_keys: List of valid API keys. If None or empty, auth is disabled.
        """
        self._api_keys: set[str] = set(api_keys) if api_keys else set()
        self._enabled = len(self._api_keys) > 0

    @property
    def enabled(self) -> bool:
        """Check if authentication is enabled."""
        return self._enabled

    def validate(self, api_key: str | None) -> bool:
        """Validate an API key.

        Args:
            api_key: The API key to validate.

        Returns:
            True if auth is disabled or key is valid, False otherwise.
        """
        if not self._enabled:
            return True
        if api_key is None:
            return False
        return any(hmac.compare_digest(api_key, k) for k in self._api_keys)

    async def __call__(self, request: Request) -> str | None:
        """FastAPI dependency for API key validation.

        Args:
            request: The incoming request.

        Returns:
            The validated API key, or None if auth is disabled.

        Raises:
            HTTPException: 401 if auth is enabled and key is invalid/missing.
        """
        api_key = request.headers.get("X-API-Key")

        if not self._enabled:
            return None

        if api_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key. Provide X-API-Key header.",
            )

        if not self.validate(api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key.",
            )

        return str(api_key)


class RateLimiter:
    """In-memory fixed-window rate limiter.

    Tracks request counts per key within fixed time windows. Thread-safe
    implementation suitable for single-process deployments.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
        enabled: bool = True,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per window.
            window_seconds: Window duration in seconds.
            enabled: Whether rate limiting is enabled.
        """
        self._limit = requests_per_minute
        self._window = window_seconds
        self._enabled = enabled
        self._counters: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
        self._lock = Lock()
        self._max_entries = 10_000
        self._last_eviction = 0.0

    @property
    def enabled(self) -> bool:
        """Check if rate limiting is enabled."""
        return self._enabled

    @property
    def limit(self) -> int:
        """Get the rate limit."""
        return self._limit

    @property
    def window(self) -> int:
        """Get the window duration in seconds."""
        return self._window

    def _get_key(self, request: Request, api_key: str | None) -> str:
        """Generate a rate limit key for the request.

        Uses API key if available, otherwise falls back to client IP.

        Args:
            request: The incoming request.
            api_key: The authenticated API key, if any.

        Returns:
            A string key for rate limiting.
        """
        if api_key:
            return f"key:{api_key}"
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _evict_expired(self, now: float) -> None:
        """Remove expired entries from counters. Must be called with _lock held."""
        expired = [k for k, (_, ws) in self._counters.items() if now - ws >= self._window]
        for k in expired:
            del self._counters[k]
        self._last_eviction = now

    def check(self, key: str) -> tuple[bool, int, int]:
        """Check if a request is allowed under rate limit.

        Args:
            key: The rate limit key.

        Returns:
            Tuple of (allowed, remaining, reset_seconds).
        """
        if not self._enabled:
            return (True, self._limit, self._window)

        now = time.time()

        with self._lock:
            # Periodic eviction: run at most once per window period
            if now - self._last_eviction >= self._window:
                self._evict_expired(now)

            # Emergency cap: evict if too many entries
            if len(self._counters) >= self._max_entries:
                self._evict_expired(now)

            count, window_start = self._counters[key]

            if now - window_start >= self._window:
                self._counters[key] = (1, now)
                return (True, self._limit - 1, self._window)

            if count >= self._limit:
                reset_in = int(self._window - (now - window_start))
                return (False, 0, reset_in)

            self._counters[key] = (count + 1, window_start)
            return (True, self._limit - count - 1, int(self._window - (now - window_start)))

    async def __call__(self, request: Request, api_key: str | None = None) -> None:
        """FastAPI dependency for rate limit checking.

        Args:
            request: The incoming request.
            api_key: The authenticated API key, if any.

        Raises:
            HTTPException: 429 if rate limit exceeded.
        """
        if not self._enabled:
            return

        # #2a: exempt canopy's own server-side self-calls (the dashboard polling
        # its own /api/* routes). They carry the per-process internal token;
        # external clients cannot forge it. Constant-time compare. Without this
        # the dashboard's own polling drains the shared bucket and 429s real
        # user actions (and surfaces as the "Error" status — see #3).
        internal = request.headers.get(INTERNAL_REQUEST_HEADER)
        if isinstance(internal, str) and hmac.compare_digest(internal, INTERNAL_REQUEST_TOKEN):
            return

        key = self._get_key(request, api_key)
        allowed, remaining, reset_in = self.check(key)

        request.state.rate_limit_remaining = remaining
        request.state.rate_limit_reset = reset_in

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {reset_in} seconds.",
                headers={
                    "X-RateLimit-Limit": str(self._limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                    "Retry-After": str(reset_in),
                },
            )

    def reset(self) -> None:
        """Reset all rate limit counters. Useful for testing."""
        with self._lock:
            self._counters.clear()


_api_key_auth: APIKeyAuth | None = None
_rate_limiter: RateLimiter | None = None


def get_api_key_auth() -> APIKeyAuth:
    """Get the global API key auth handler, creating if needed."""
    global _api_key_auth
    if _api_key_auth is None:
        api_key = get_secret("CANOPY_API_KEY")
        api_keys = [api_key] if api_key else None
        _api_key_auth = APIKeyAuth(api_keys)
    return _api_key_auth


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter, creating if needed."""
    global _rate_limiter
    if _rate_limiter is None:
        from settings import get_settings

        _settings = get_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=_settings.rate_limit_requests_per_minute,
            enabled=_settings.rate_limit_enabled,
        )
    return _rate_limiter


def reset_security_state() -> None:
    """Reset global security state. Useful for testing."""
    global _api_key_auth, _rate_limiter
    _api_key_auth = None
    _rate_limiter = None


def browser_origin_allowed(request: Request) -> bool:
    """Return True if the request's Origin header is an allowlisted same-origin.

    PR-1 (Start-Training 401 fix): the REST counterpart of
    ``ws_security.validate_origin`` — reuses the WebSocket Origin allowlist
    (``settings.websocket.allowed_origins``) and the same comparison semantics
    so the browser control surface enforces one Origin policy across HTTP and
    WebSocket. Fail-closed: a missing/disallowed Origin returns False.

    Args:
        request: The incoming HTTP request.

    Returns:
        True if the ``Origin`` header matches the allowlist, else False.
    """
    from settings import get_settings
    from ws_security import is_origin_allowed

    origin = request.headers.get("origin")
    return is_origin_allowed(origin, get_settings().websocket.allowed_origins)


async def require_browser_control_auth(request: Request) -> None:
    """Authenticate the same-origin browser control surface (PR-1).

    FastAPI dependency for the ``/api/train/*`` routes. The browser structurally
    cannot hold the per-process server ``X-API-Key`` (this module mints
    ``INTERNAL_REQUEST_TOKEN`` fresh each start, and browsers cannot set custom
    WebSocket headers), so the same-origin browser is authenticated by
    **Origin + CSRF token + session cookie** — the controls ``/ws/control``
    already trusts — while keyed callers keep working unchanged.

    Acceptance rule (see
    ``notes/JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md`` §8.2):

    1. A valid ``X-API-Key`` always passes (server-side self-calls, programmatic
       or otherwise keyed callers). A present-but-invalid key is a hard 401.
    2. When API-key auth is globally disabled (no key configured) the surface is
       open (dev/demo parity with :class:`APIKeyAuth`).
    3. Otherwise (keyless, auth enabled) the browser path applies:

       - flag OFF -> preserve pre-fix behaviour: the key is still required (401);
       - the Origin must be allowlisted (403, fail-closed on missing);
       - the CSRF token must validate, unless CSRF is disabled (Origin-only,
         design OQ-6).

    ``/v1/*`` and every non-browser surface keep the middleware key gate.

    Raises:
        HTTPException: 401 on a bad/required key; 403 on a bad Origin/CSRF.
    """
    auth = get_api_key_auth()
    key = request.headers.get("X-API-Key")

    # 1. Keyed callers always work; a present-but-invalid key is rejected.
    if auth.enabled and key is not None:
        if auth.validate(key):
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    # 2. Auth globally disabled -> open access (dev/demo).
    if not auth.enabled:
        return

    # 3. Browser path: key absent, auth enabled.
    from settings import get_settings

    _settings = get_settings()
    if not _settings.browser_control_auth_enabled:
        # Flag off: preserve pre-fix behaviour — the key is still required.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key. Provide X-API-Key header.")

    # 3a. Origin allowlist (fail-closed on missing/disallowed).
    if not browser_origin_allowed(request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed.")

    # 3b. CSRF token — skipped only when CSRF is disabled (Origin-only, OQ-6).
    if _settings.csrf_enabled:
        from csrf import get_csrf_store

        token = request.headers.get("X-CSRF-Token")
        if not token or not get_csrf_store().validate(token):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing CSRF token.")
