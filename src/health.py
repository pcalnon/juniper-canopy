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

:func:`probe_dependency` stays async (canopy's REST handlers ``await``
it). Internally it now delegates to the shared synchronous
:func:`juniper_observability.probe_dependency` via
:func:`asyncio.to_thread`, eliminating the duplicated implementation.

New code should prefer ``from juniper_observability import …`` for
:class:`DependencyStatus` / :class:`ReadinessResponse` / the synchronous
``probe_dependency`` to make the dependency on the shared lib explicit.

See: notes/code-review/METRICS_MONITORING_R2.1_SHARED_OBSERVABILITY_DESIGN_2026-04-28.md
in juniper-ml.
"""

import asyncio
from typing import Optional

from juniper_observability import DependencyStatus, ReadinessResponse
from juniper_observability import probe_dependency as _probe_dependency_sync
from pydantic import BaseModel

__all__ = ["DependencyStatus", "ErrorResponse", "ReadinessResponse", "probe_dependency"]


class ErrorResponse(BaseModel):
    """Standardized error response model for all Canopy REST endpoints."""

    error: str
    detail: Optional[str] = None
    status_code: int


async def probe_dependency(name: str, url: str, timeout: float = 5.0) -> DependencyStatus:
    """Probe a dependency health endpoint without blocking the event loop.

    Async wrapper around the shared synchronous
    :func:`juniper_observability.probe_dependency` — runs the blocking
    ``urllib.request.urlopen`` call on a worker thread so async REST
    handlers can ``await`` it.

    Args:
        name: Human-readable name of the dependency.
        url: Health endpoint URL to probe.
        timeout: Connection timeout in seconds.

    Returns:
        DependencyStatus with probe results.
    """
    return await asyncio.to_thread(_probe_dependency_sync, name, url, timeout)
