"""API security: authentication and rate limiting.

Provides API key authentication and rate limiting for JuniperCanopy.
Configuration is read from environment variables:
    CANOPY_API_KEY: Single API key for authentication (disabled when unset).
    CANOPY_RATE_LIMIT_ENABLED: Enable rate limiting (default: false).
    CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE: Rate limit (default: 60).
"""

import hmac
import ipaddress
import secrets
import sys
import time
from collections import defaultdict
from threading import Lock
from typing import TYPE_CHECKING, cast

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader

from secrets_util import get_secret

if TYPE_CHECKING:
    from settings import Settings

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


# ── SEC-F22 / D2: startup loopback bind-guard ──────────────────────────────
#
# The canopy browser training-control gate (Origin + CSRF) is bypassable by any
# in-network NON-browser client (audit HO-6): its Origin check is a spoofable
# string compare and its CSRF token is anonymously mintable, so the *only*
# effective control is the loopback bind -- an in-network foothold cannot reach
# a 127.0.0.0/8 port. Today that loopback bind is an implicit default
# (``server.host`` / the compose publish), not an enforced invariant: flipping
# ``BIND_HOST=0.0.0.0`` silently turns SEC-F22 from same-host-only into
# in-network- (or internet-) reachable. This guard converts the design's
# load-bearing precondition into an enforced, fail-closed startup check.
# Implemented inline in canopy (no juniper-service-core dependency for this).
# Design-of-record: juniper-ml
# notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md §4 / §8 D2.


class NonLoopbackBindError(RuntimeError):
    """Raised at startup when canopy is configured to bind a non-loopback
    interface without any bind-posture attestation (SEC-F22 / D2).

    Fail-closed: raising here aborts application startup (the FastAPI lifespan
    propagates it, uvicorn exits) so canopy never serves a single request on an
    unattested non-loopback bind.
    """


def is_loopback_host(host: str) -> bool:
    """Return True when ``host`` binds a loopback-only interface (SEC-F22 / D2).

    Loopback is defined exactly as the design does: an address in 127.0.0.0/8,
    the IPv6 ``::1``, or the literal hostname ``localhost`` (case-insensitive).
    Everything else -- including the ``0.0.0.0`` / ``::`` all-interfaces
    wildcards, any routable address, and any unparseable / empty value -- is
    treated as NON-loopback (fail-closed toward requiring attestation): if we
    cannot prove the bind is loopback-only, we do not assume it is.
    """
    if not host:
        return False
    candidate = host.strip()
    if not candidate:
        return False
    # Accept a bracketed IPv6 literal form (e.g. "[::1]") before parsing.
    if candidate.startswith("[") and candidate.endswith("]"):
        candidate = candidate[1:-1]
    if candidate.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def enforce_loopback_bind_guard(
    host: str,
    *,
    loopback_publish_attested: bool,
    auth_proxy_attested: bool,
    logger=None,
) -> None:
    """Refuse to start on an unattested non-loopback bind (SEC-F22 / D2).

    Two-flag bind-posture attestation (the owner-ratified refinement of the
    original single ``fronting_auth_attested`` flag; design OQ-1):

    - Loopback ``host`` -> always allowed (no-op); canopy starts normally.
    - Non-loopback ``host`` + EITHER attestation True -> allowed, with a loud
      WARNING recording WHICH attestation permitted the non-loopback bind.
    - Non-loopback ``host`` + BOTH attestations False -> CRITICAL log + raise
      :class:`NonLoopbackBindError` (fail-closed; startup aborts).

    ``loopback_publish_attested`` (env
    ``JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED``) attests the service is reachable
    ONLY via a loopback-only host publish -- the containerized default, and the
    one attestation a deploy-layer preflight can verify. ``auth_proxy_attested``
    (env ``JUNIPER_CANOPY_AUTH_PROXY_ATTESTED``) attests a fronting
    authenticating reverse proxy terminates access (Phase 4; attestation only).
    Each is an operator *attestation*, NOT a verification, so the non-loopback
    path is loud by design. The refusal is a uniform hard fail -- there is no
    warning-only mode that lets an unattested non-loopback bind proceed.
    """
    if is_loopback_host(host):
        return
    if loopback_publish_attested or auth_proxy_attested:
        if logger is not None:
            permitting = " + ".join(
                name
                for name, is_set in (
                    ("JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED", loopback_publish_attested),
                    ("JUNIPER_CANOPY_AUTH_PROXY_ATTESTED", auth_proxy_attested),
                )
                if is_set
            )
            logger.warning(
                "canopy bound to non-loopback host %r permitted by %s -- the operator attests the control-surface " "perimeter (a loopback-only host publish and/or a fronting authenticating proxy). This is an operator " "attestation, NOT a verification: the browser-control gate (Origin+CSRF) is bypassable by any in-network " "non-browser client, so the attested perimeter MUST actually be in place (SEC-F22/D2).",
                host,
                permitting,
            )
        return
    message = (
        f"REFUSING TO START: canopy is configured to bind a non-loopback interface (server.host={host!r}) with neither "
        "bind-posture attestation set. The browser training-control surface (/api/train/*, /ws/control) is bypassable "
        "from any in-network foothold (SEC-F22): its Origin check is spoofable and its CSRF token is anonymously "
        "mintable, so the loopback boundary is the only effective control. Bind a loopback host "
        "(127.0.0.1 / ::1 / localhost), OR set JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true (the service is reachable "
        "only via a loopback-only host publish -- the containerized default) OR JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true "
        "(a fronting authenticating proxy terminates access -- Phase 4). See juniper-ml "
        "notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md §4 / §8 (D2)."
    )
    if logger is not None:
        logger.critical(message)
    raise NonLoopbackBindError(message)


def _cli_option_value(argv: list[str], option: str) -> str | None:
    """Return a CLI option value from ``--name value`` or ``--name=value``."""
    prefix = f"{option}="
    for index, arg in enumerate(argv):
        if arg.startswith(prefix):
            return arg[len(prefix) :]
        if arg == option and index + 1 < len(argv):
            return argv[index + 1]
    return None


def settings_with_uvicorn_cli_bind(settings: "Settings", argv: list[str] | None = None) -> "Settings":
    """Overlay a uvicorn CLI ``--host`` / ``--port`` onto settings for bind-guard parity.

    ``uvicorn main:app --host 0.0.0.0`` is a supported launch path. uvicorn consumes
    ``--host`` itself and never sets ``JUNIPER_CANOPY_SERVER__HOST``, so the SEC-F22
    guard -- which reads ``settings.server.host`` -- would see the loopback default
    while uvicorn binds a public socket (the SEC-F23 / SEC-F27 bypass class). Mirror
    the CLI bind host/port into a transient settings copy before ``main.lifespan`` runs
    :func:`enforce_loopback_bind_guard`, so the guard evaluates the *real* bind on the
    ``uvicorn main:app`` path too -- the parity juniper-cascor already has via its
    ``_settings_with_uvicorn_cli_bind``.

    A ``python main.py`` launch carries no uvicorn CLI bind args, so this is a no-op
    there (host/port stay settings-driven). Design-of-record: juniper-ml
    ``notes/JUNIPER_2026-07-06_JUNIPER-ECOSYSTEM_LAUNCH-PATH-BIND-AUDIT.md`` (SEC-F27).
    """
    args = list(sys.argv if argv is None else argv)
    if not any("uvicorn" in arg for arg in args[:2]) and "main:app" not in args:
        return settings

    updates: dict[str, object] = {}
    host = _cli_option_value(args, "--host")
    if host:
        updates["host"] = host

    port = _cli_option_value(args, "--port")
    if port is not None:
        try:
            updates["port"] = int(port)
        except ValueError:
            # Non-integer --port: uvicorn itself would reject it; leave port
            # settings-driven rather than crash the guard-parity path.
            pass

    if not updates:
        return settings
    # pydantic is treated as untyped here, so model_copy() is Any -> cast for mypy.
    return cast("Settings", settings.model_copy(update={"server": settings.server.model_copy(update=updates)}))
