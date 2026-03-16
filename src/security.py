"""API security: authentication and rate limiting.

Provides API key authentication and rate limiting for JuniperCanopy.
Configuration is read from environment variables:
    CANOPY_API_KEY: Single API key for authentication (disabled when unset).
    CANOPY_RATE_LIMIT_ENABLED: Enable rate limiting (default: false).
    CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE: Rate limit (default: 60).
"""

import os
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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
        return api_key in self._api_keys

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

        return api_key


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
        api_key = os.environ.get("CANOPY_API_KEY")
        api_keys = [api_key] if api_key else None
        _api_key_auth = APIKeyAuth(api_keys)
    return _api_key_auth


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter, creating if needed."""
    global _rate_limiter
    if _rate_limiter is None:
        enabled = os.environ.get("CANOPY_RATE_LIMIT_ENABLED", "").lower() in ("1", "true", "yes")
        requests_per_minute = int(os.environ.get("CANOPY_RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
        _rate_limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            enabled=enabled,
        )
    return _rate_limiter


def reset_security_state() -> None:
    """Reset global security state. Useful for testing."""
    global _api_key_auth, _rate_limiter
    _api_key_auth = None
    _rate_limiter = None
