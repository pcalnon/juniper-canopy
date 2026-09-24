"""API security: authentication and rate limiting.

Provides API key authentication and rate limiting for JuniperCanopy.
Configuration is read from environment variables:
    CANOPY_API_KEY: Single API key for authentication. CANOPY_API_KEY_FILE, when it
        names an existing file, takes precedence (``secrets_util.resolve_secret``).
        Disabled when unset, empty or whitespace-only.
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
from typing import TYPE_CHECKING, Any, cast

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader

from secrets_util import resolve_secret_detail

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
                Blank / whitespace-only (and non-str) entries are ignored -- the
                same rule as ``juniper_service_core.auth_posture.real_keys`` -- so
                a key that is only whitespace cannot enable authentication.
        """
        # APD-ECO-008: filter blanks before enabling, as juniper-service-core's
        # APIKeyAuth (security.py) and the juniper-data / juniper-cascor forks do.
        # ``get_api_key_auth`` already maps an empty key to None, so what reaches
        # here unfiltered is a whitespace-only CANOPY_API_KEY from the env var
        # (``resolve_secret`` strips a secret FILE, not the env var). Unfiltered, such a
        # key ENABLED auth on a key no caller could present, so every key-gated route
        # refused every caller, while the boot-time posture check, which filters with
        # this same rule, reported the service OPEN. "No caller could present it" holds
        # for every ``str.strip()`` character except U+00A0 and U+0085, and, under h11
        # only, U+001C..U+001F. Measured on uvicorn 0.49.0 with raw socket bytes: h11
        # and httptools both strip an all-space or all-tab ``X-API-Key`` to empty; both
        # refuse U+000B and U+000C with a 400, and httptools -- canopy's default parser
        # -- refuses U+001C..U+001F too; nothing above U+00FF can arrive, because
        # Starlette decodes header bytes as latin-1; and CR/LF end the header line.
        # U+00A0 and U+0085 pass both parsers, but ``hmac.compare_digest`` rejects
        # non-ASCII text (``TypeError``: a 500, never a match). U+001C..U+001F pass h11,
        # and under h11 a key of those was a working key. The WebSocket ``?api_key=``
        # parameter could carry a whitespace key, but every WS route admits a keyless
        # connection anyway (``allow_browser_auth=True``), so that was never an
        # exposure. Now this class and the posture check agree: a blank key is no key
        # and auth is off -- the posture canopy documents for no key at all -- and
        # ``enforce_auth_posture`` fails the boot when ``require_auth`` is set. The
        # key's two other readers apply the same rule (#678 follow-up): ``main.py``'s
        # ``_docs_enabled`` serves the docs, and ``frontend/internal_api.py`` sends no
        # ``X-API-Key`` on a self-call, exactly as with no key configured.
        self._api_keys: set[str] = {k for k in (api_keys or []) if isinstance(k, str) and k.strip()}
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
        # Constant-time comparison against every configured key (APD-ECO-008).
        # ``any()`` would short-circuit on the first match, so the NUMBER of
        # comparisons would depend on where the matching key falls in the
        # iteration; hmac.compare_digest itself already runs in time proportional
        # to the input length regardless of where a mismatching byte appears, so
        # walking the whole key set preserves that property per key while still
        # accepting on a match. Mirrors juniper-data's reference implementation
        # (juniper_data/api/security.py), as the juniper-cascor and
        # juniper-service-core copies do on their main branches.
        matched = False
        for candidate in self._api_keys:
            if hmac.compare_digest(api_key, candidate):
                matched = True
        return matched

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

# APD-ECO-008: a SET-but-blank key is a different operator mistake from an UNSET one,
# and ``enforce_auth_posture`` words the two identically ("running OPEN"). When the
# key's source is set but blank, ``get_api_key_auth`` records the NAME of the variable
# that supplied it -- never the value -- from its one secret read, and
# ``main.lifespan`` reports it (:func:`report_api_key_configuration`, which calls
# :func:`report_blank_api_key`) once logging is configured. It cannot be logged where
# it is read: the singleton is first built at import (``main.api_key_auth``), before
# ``configure_logging`` runs -- and only while ``main`` builds its handler through
# ``get_api_key_auth()``: a handler built any other way records nothing, and the report
# has nothing to say (pinned in a fresh interpreter by
# ``tests/regression/test_blank_api_key_warning_boot.py``). #660 logged it
# there, through a module logger with no handler, so it reached only Python's
# last-resort handler -- no level, no JSON, no Sentry, and never ``logs/system.log``.
# Guarded by ``_blank_key_lock``, which guards every finding recorded from that read.
_blank_key_source: str | None = None
_blank_key_reported = False
_blank_key_lock = Lock()

# #678 follow-up: two more things the same read can find, reported beside the blank key
# by :func:`report_api_key_configuration`, for the same reason. A key with leading or
# trailing whitespace, or a line break, ENABLES auth with the key exactly as set, and
# HTTP does not carry it reliably (``_PADDED_KEY_WARNING``); the dashboard's self-calls
# omit such a key when ``requests`` refuses to send it (``frontend/internal_api.py``),
# because the refusal's message quoted the key into the logs. A CANOPY_API_KEY_FILE that
# names no existing file is otherwise ignored silently, exactly as if it were unset.
# Recorded as variable NAMES only: never the key, nor the path the ``_FILE`` variable
# holds, because an operator who confuses the two variables puts the key itself there.
_padded_key_source: str | None = None
_missing_key_file_var: str | None = None
_key_findings_reported = False

# One wording per source, because the advice differs: while CANOPY_API_KEY_FILE names
# an existing file it takes precedence and CANOPY_API_KEY is not read at all
# (``secrets_util.resolve_secret``), so "unset CANOPY_API_KEY" would be wrong advice
# to an operator whose file is blank and whose CANOPY_API_KEY holds the real key.
_BLANK_KEY_OPENS = "so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured."
_BLANK_KEY_ENV_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), " + _BLANK_KEY_OPENS + " Set a real key, or unset CANOPY_API_KEY for an intentional open profile."
_BLANK_KEY_FILE_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), " + _BLANK_KEY_OPENS + " While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."

# The same two sources when the posture check refuses to start
# (JUNIPER_CANOPY_REQUIRE_AUTH=true): nothing serves, so "authentication is DISABLED ...
# serves without a key" would be false. These follow the posture check's CRITICAL, which
# says NO API key is configured, and name the key it counted as none.
_BLANK_KEY_REFUSES = "so it counts as no key: it is the key the auth-posture check reports as not configured, and because JUNIPER_CANOPY_REQUIRE_AUTH is true, canopy refuses to start."
_BLANK_KEY_ENV_REFUSED_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), " + _BLANK_KEY_REFUSES + " Set a real key."
_BLANK_KEY_FILE_REFUSED_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), " + _BLANK_KEY_REFUSES + " While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."

# Only the env var can be padded: ``resolve_secret`` strips a secret FILE. Measured on
# uvicorn 0.49.0 and requests 2.34.2 (``util/ad-hoc/2026-09-24_padded_api_key_probes.py
# header-probe``): h11 and httptools both drop a header value's leading spaces and tabs,
# h11 also drops trailing ones (httptools keeps them), CR and LF end the header line, and
# requests refuses to send a value that starts with whitespace or holds a line break.
_PADDED_KEY_WARNING = (
    "CANOPY_API_KEY has leading or trailing whitespace, or a line break, and API-key authentication is enabled with the key exactly as set. HTTP does not carry such a key reliably: uvicorn's parsers drop a header value's leading spaces and tabs, h11 drops its trailing ones as well, and a header cannot hold a line break."
    + " So callers presenting the key can fail to authenticate, and the dashboard's own requests to this API send no key at all when it starts with whitespace or holds a line break, because their HTTP client refuses to send it. Remove the whitespace and any line break from the key."
)
_MISSING_KEY_FILE_WARNING = "CANOPY_API_KEY_FILE is set but does not name an existing file, so it is ignored: the key is read from CANOPY_API_KEY instead, exactly as if CANOPY_API_KEY_FILE were unset. Point CANOPY_API_KEY_FILE at the key file, or unset it."


def _is_padded_key(api_key: str) -> bool:
    """True for a key with leading or trailing whitespace, or a line break anywhere in it."""
    return api_key != api_key.strip() or "\r" in api_key or "\n" in api_key


def get_api_key_auth() -> APIKeyAuth:
    """Get the global API key auth handler, creating if needed.

    Creation is the only place the key is read. What that read finds wrong with the
    key's configuration is recorded by variable NAME for
    :func:`report_api_key_configuration`, and nothing is logged here: a set-but-blank key
    (one the blank-key filter leaves auth disabled on), a key with leading or trailing
    whitespace or a line break, and a ``CANOPY_API_KEY_FILE`` that names no existing file.
    """
    global _api_key_auth, _blank_key_source, _blank_key_reported, _padded_key_source, _missing_key_file_var, _key_findings_reported
    if _api_key_auth is None:
        api_key, source, missing_file_var = resolve_secret_detail("CANOPY_API_KEY")
        api_keys = [api_key] if api_key else None
        _api_key_auth = APIKeyAuth(api_keys)
        with _blank_key_lock:
            _blank_key_source = source if api_key is not None and not _api_key_auth.enabled else None
            _blank_key_reported = False
            _padded_key_source = source if api_key is not None and _api_key_auth.enabled and _is_padded_key(api_key) else None
            _missing_key_file_var = missing_file_var
            _key_findings_reported = False
    return _api_key_auth


def report_blank_api_key(log: Any, *, boot_refused: bool = False) -> bool:
    """Log the set-but-blank ``CANOPY_API_KEY`` WARNING through ``log``, at most once.

    :func:`report_api_key_configuration` calls this; ``main.lifespan`` calls that right
    after ``enforce_auth_posture``, once ``configure_logging`` has run, with the system
    logger. The message names the source that was blank (``CANOPY_API_KEY_FILE`` or
    ``CANOPY_API_KEY``) and the remedy for that source, and never the value. It reads
    only what :func:`get_api_key_auth` recorded, never the secret itself, and reports
    once per recorded key however many times the lifespan runs.

    Args:
        log: Any logger with a ``warning(message)`` method.
        boot_refused: True when the posture check has refused to start
            (``JUNIPER_CANOPY_REQUIRE_AUTH=true``). The WARNING then says the blank key
            counts as no key and canopy refuses to start, instead of saying routes serve
            without a key: nothing is serving.

    Returns:
        True when this call logged the WARNING, else False.
    """
    global _blank_key_reported
    with _blank_key_lock:
        if _blank_key_source is None or _blank_key_reported:
            return False
        _blank_key_reported = True
        source = _blank_key_source
    if boot_refused:
        log.warning(_BLANK_KEY_FILE_REFUSED_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_REFUSED_WARNING)
    else:
        log.warning(_BLANK_KEY_FILE_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_WARNING)
    return True


def report_api_key_configuration(log: Any, *, boot_refused: bool = False) -> int:
    """Log, through ``log``, what the one read of ``CANOPY_API_KEY`` found wrong with its configuration.

    ``main.lifespan`` calls this with the system logger once ``configure_logging`` has
    run: right after ``enforce_auth_posture``, or, when the posture check refuses to
    start, from its ``except AuthPostureError`` with ``boot_refused=True``, before the
    error propagates. In this order, each WARNING at most once per recorded read:

    1. ``CANOPY_API_KEY_FILE`` is set but names no existing file, so it was ignored;
    2. the key is set but blank (:func:`report_blank_api_key`, worded for ``boot_refused``);
    3. the key has leading or trailing whitespace or a line break, and auth is enabled
       with it as set.

    Like :func:`report_blank_api_key`, it reads only what :func:`get_api_key_auth`
    recorded -- variable names, never the key or the path.

    Args:
        log: Any logger with a ``warning(message)`` method.
        boot_refused: Passed to :func:`report_blank_api_key`.

    Returns:
        How many WARNINGs this call logged.
    """
    global _key_findings_reported
    with _blank_key_lock:
        if _key_findings_reported:
            missing_file_var = padded_source = None
        else:
            _key_findings_reported = True
            missing_file_var, padded_source = _missing_key_file_var, _padded_key_source
    logged = 0
    if missing_file_var is not None:
        log.warning(_MISSING_KEY_FILE_WARNING)
        logged += 1
    if report_blank_api_key(log, boot_refused=boot_refused):
        logged += 1
    if padded_source is not None:
        log.warning(_PADDED_KEY_WARNING)
        logged += 1
    return logged


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
    global _api_key_auth, _rate_limiter, _blank_key_source, _blank_key_reported, _padded_key_source, _missing_key_file_var, _key_findings_reported
    _api_key_auth = None
    _rate_limiter = None
    with _blank_key_lock:
        _blank_key_source = None
        _blank_key_reported = False
        _padded_key_source = None
        _missing_key_file_var = None
        _key_findings_reported = False


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
