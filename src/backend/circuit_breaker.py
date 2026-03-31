import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger("juniper_canopy.backend.circuit_breaker")

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for external service calls.

    Tracks consecutive failures and opens the circuit after a threshold,
    preventing cascading failure by short-circuiting calls during outages.

    States:
        CLOSED   — Normal operation; failures counted.
        OPEN     — Calls short-circuited; returns fallback immediately.
        HALF_OPEN — After recovery_timeout, one probe call is allowed.

    Args:
        name: Identifier for logging.
        failure_threshold: Consecutive failures before opening circuit.
        recovery_timeout: Seconds to wait before probing (OPEN → HALF_OPEN).
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._last_success_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit '%s' transitioning OPEN → HALF_OPEN", self.name)
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def call(
        self,
        func: Callable[..., T],
        *args: Any,
        fallback: Optional[Callable[[], T]] = None,
        **kwargs: Any,
    ) -> T:
        """Execute *func* through the circuit breaker.

        Args:
            func: The callable to execute.
            *args: Positional arguments for *func*.
            fallback: Called when circuit is OPEN (returns its result).
            **kwargs: Keyword arguments for *func*.

        Returns:
            Result of *func* or *fallback*.

        Raises:
            The original exception if no fallback is provided and the circuit
            is CLOSED/HALF_OPEN.
        """
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.debug("Circuit '%s' is OPEN — skipping call", self.name)
            if fallback is not None:
                return fallback()
            raise CircuitOpenError(f"Circuit '{self.name}' is open")

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure()
            if fallback is not None and self.state == CircuitState.OPEN:
                return fallback()
            raise exc

    def _record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._last_success_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info("Circuit '%s' recovered — HALF_OPEN → CLOSED", self.name)

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold and self._state != CircuitState.OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' opened after %d consecutive failures",
                    self.name,
                    self._failure_count,
                )

    def reset(self) -> None:
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("Circuit '%s' manually reset to CLOSED", self.name)


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an open circuit with no fallback."""
