"""CSRF token manager for WebSocket control-path authentication (M-SEC-02).

Provides server-side token store with:
- Token minting via ``secrets.token_urlsafe(32)``
- Constant-time validation via ``hmac.compare_digest``
- 1-hour sliding TTL with automatic expiry
- Thread-safe for concurrent HTTP + WS access
"""

import hmac
import logging
import secrets
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("juniper_canopy.csrf")

_DEFAULT_TTL = 3600  # 1 hour


class CsrfTokenStore:
    """Server-side CSRF token store with TTL-based expiry.

    Tokens are minted via ``mint()``, validated via ``validate()``,
    and automatically pruned when stale. Thread-safe.
    """

    def __init__(
        self,
        ttl_seconds: int = _DEFAULT_TTL,
        max_tokens: int = 10000,
        clock: Callable[[], float] = time.monotonic,
    ):
        """
        Args:
            ttl_seconds: Sliding TTL applied on mint and refreshed on each
                successful ``validate()``.
            max_tokens: Cap on stored tokens; the oldest is evicted past it.
            clock: Monotonic time source, in seconds. Injectable so tests can
                drive expiry deterministically instead of sleeping. Production
                callers never pass this.

                This exists because the sliding-TTL tests previously asserted
                against ``time.sleep`` on a real clock, which made them a
                genuine flake on loaded macOS CI runners: the sleeps overshot
                the TTL and a still-valid token read as expired. The margins had
                already been widened 5x and it still flaked intermittently.
                Injecting the clock removes the race outright rather than
                widening the window again.
        """
        self._ttl = ttl_seconds
        self._max_tokens = max_tokens
        self._clock = clock
        self._tokens: dict[str, float] = {}  # token -> expiry_time
        self._lock = threading.Lock()

    def mint(self) -> str:
        """Mint a new CSRF token and store it with TTL.

        Returns:
            The newly minted token string.
        """
        token = secrets.token_urlsafe(32)
        now = self._clock()
        with self._lock:
            self._prune(now)
            if len(self._tokens) >= self._max_tokens:
                # Evict oldest
                oldest_key = min(self._tokens, key=self._tokens.get)
                del self._tokens[oldest_key]
            self._tokens[token] = now + self._ttl
        logger.debug("CSRF token minted (store size=%d)", len(self._tokens))
        return token

    def validate(self, token: str) -> bool:
        """Validate a CSRF token using constant-time comparison.

        Valid tokens have their TTL refreshed (sliding window).

        Returns:
            True if token is valid and not expired.
        """
        if not token:
            return False
        now = self._clock()
        with self._lock:
            for stored_token, expiry in list(self._tokens.items()):
                if expiry < now:
                    continue
                if hmac.compare_digest(stored_token, token):
                    # Refresh TTL (sliding window)
                    self._tokens[stored_token] = now + self._ttl
                    return True
        return False

    def revoke(self, token: str) -> None:
        """Revoke a specific token (e.g., on auth close)."""
        with self._lock:
            self._tokens.pop(token, None)

    def clear(self) -> None:
        """Clear all tokens (e.g., on server restart)."""
        with self._lock:
            self._tokens.clear()

    def _prune(self, now: float) -> None:
        """Remove expired tokens. Must be called under lock."""
        expired = [k for k, v in self._tokens.items() if v < now]
        for k in expired:
            del self._tokens[k]

    @property
    def size(self) -> int:
        """Number of active tokens."""
        with self._lock:
            return len(self._tokens)


# Module-level singleton — cleared on server restart automatically
_csrf_store: Optional[CsrfTokenStore] = None


def get_csrf_store(ttl_seconds: int = _DEFAULT_TTL) -> CsrfTokenStore:
    """Get or create the module-level CSRF token store."""
    global _csrf_store
    if _csrf_store is None:
        _csrf_store = CsrfTokenStore(ttl_seconds=ttl_seconds)
    return _csrf_store
