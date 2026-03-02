"""Health check models and utilities for JuniperCanopy.

Provides standardized health response models shared across all Juniper
services, and a dependency probe utility for readiness checks.
"""

import time
import urllib.request
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    """Health status of a single dependency."""

    name: str
    status: Literal["healthy", "unhealthy", "degraded", "not_configured"]
    latency_ms: float | None = None
    message: str | None = None


class ReadinessResponse(BaseModel):
    """Standard /v1/health/ready response for all Juniper services."""

    status: Literal["ready", "degraded", "not_ready"]
    version: str
    service: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())
    dependencies: dict[str, DependencyStatus] = {}
    details: dict[str, object] = {}


def probe_dependency(name: str, url: str, timeout: float = 5.0) -> DependencyStatus:
    """Probe a dependency health endpoint. Returns status with latency.

    Args:
        name: Human-readable name of the dependency.
        url: Health endpoint URL to probe.
        timeout: Connection timeout in seconds.

    Returns:
        DependencyStatus with probe results.
    """
    start = time.monotonic()
    try:
        urllib.request.urlopen(url, timeout=timeout)  # nosec B310 — internal health probe
        latency = (time.monotonic() - start) * 1000
        return DependencyStatus(name=name, status="healthy", latency_ms=round(latency, 1), message=url)
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return DependencyStatus(
            name=name,
            status="unhealthy",
            latency_ms=round(latency, 1),
            message=f"{url} — {type(e).__name__}: {e}",
        )
