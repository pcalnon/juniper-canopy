"""Health check models and utilities for JuniperCanopy.

METRICS-MON R2.1.5 / seed-06: :class:`DependencyStatus` and
:class:`ReadinessResponse` are re-exported from the shared
:mod:`juniper_observability` package so all three Juniper servers
consume one source of truth. :class:`ErrorResponse` is canopy-specific
and stays here.

The migration **closes BUG-JD-06-equivalent naive-tz drift**: canopy's
former ``timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())``
used local time, while juniper-data's was already tz-aware UTC. The
shared model uses ``datetime.now(UTC).timestamp()`` so all services
emit the same epoch-seconds value regardless of host timezone.

METRICS-MON R4.2 / seed-10: :func:`probe_dependency` is now native async
(:class:`httpx.AsyncClient`) rather than a thread-pool offload of the
shared synchronous probe. The previous ``asyncio.to_thread`` path was
correct (it didn't block the event loop) but consumed one of the
default 32 worker threads per concurrent probe — under N>32
simultaneous readiness checks (Kubernetes orchestrator hitting all
canopy replicas during a rolling restart, dashboard auto-refresh fan-out
to many upstream peers) the pool would exhaust. Native httpx async I/O
scales without that ceiling.

The shared synchronous :func:`juniper_observability.probe_dependency`
remains the canonical implementation for synchronous callers; canopy
just no longer routes through it for async paths.

The wire contract on :class:`DependencyStatus` is unchanged — same
``status`` literals (``healthy`` / ``unhealthy`` / ``degraded`` /
``not_configured``), same ``latency_ms`` semantics, and the ``message``
text mirrors the shared lib's ``"{url} — {type(e).__name__}: {e}"``
format on failure paths so operator dashboards keep parsing it.

See: notes/code-review/METRICS_MONITORING_R2.1_SHARED_OBSERVABILITY_DESIGN_2026-04-28.md
and METRICS_MONITORING_R4_ENTRY_PLAN_2026-05-01.md in juniper-ml.
"""

import logging
import time
from typing import Optional

import httpx
from juniper_observability import DependencyStatus, ReadinessResponse
from pydantic import BaseModel

__all__ = ["DependencyStatus", "ErrorResponse", "ReadinessResponse", "probe_dependency"]

logger = logging.getLogger("juniper_canopy.health")


class ErrorResponse(BaseModel):
    """Standardized error response model for all Canopy REST endpoints."""

    error: str
    detail: Optional[str] = None
    status_code: int


async def probe_dependency(name: str, url: str, timeout: float = 5.0) -> DependencyStatus:
    """Probe a dependency health endpoint without blocking the event loop.

    Native async implementation using :class:`httpx.AsyncClient` (R4.2 /
    seed-10). Replaces the previous ``asyncio.to_thread`` wrapper around
    the shared synchronous probe.

    Args:
        name: Human-readable name of the dependency.
        url: Health endpoint URL to probe.
        timeout: Per-request timeout in seconds.

    Returns:
        :class:`DependencyStatus` populated with the probe outcome —
        ``status="healthy"`` on HTTP 200, ``"unhealthy"`` on any other
        outcome (HTTP non-200, transport error, timeout). The message
        format matches the shared synchronous probe so dashboards can
        parse either side of the migration.
    """
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
        latency = round((time.monotonic() - start) * 1000, 1)
        if response.status_code == 200:
            return DependencyStatus(
                name=name,
                status="healthy",
                latency_ms=latency,
                message=url,
            )
        # Non-200 surfaces as unhealthy (matches the shared lib, which
        # raises HTTPError on 4xx/5xx and routes through the except
        # branch). Operator dashboards parse the ``status`` field, not
        # the HTTP code from message text.
        return DependencyStatus(
            name=name,
            status="unhealthy",
            latency_ms=latency,
            message=f"{url} — HTTPStatusError: {response.status_code} {response.reason_phrase}",
        )
    except Exception as e:  # noqa: BLE001 — probe surfaces every failure mode (mirrors shared lib)
        latency = round((time.monotonic() - start) * 1000, 1)
        return DependencyStatus(
            name=name,
            status="unhealthy",
            latency_ms=latency,
            message=f"{url} — {type(e).__name__}: {e}",
        )
