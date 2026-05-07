"""Auto-discovery of running cascor instances for juniper-canopy.

Probes well-known ports for a running cascor service before falling back
to demo mode.

METRICS-MON R4.2 / seed-10: discovery probes now use
:class:`httpx.AsyncClient` natively rather than offloading
``urllib.request.urlopen`` to a thread-pool worker. Same motivation as
:func:`canopy.health.probe_dependency`: native async scales without the
default 32-worker thread-pool ceiling that the previous offload pattern
imposed.
"""

import logging
from typing import Optional

import httpx

from canopy_constants import ServerConstants

logger = logging.getLogger("juniper_canopy.discovery")

# Module-level aliases preserved for tests that may import these directly.
# The canonical source of truth is :class:`canopy_constants.ServerConstants`.
_DEFAULT_PORTS = list(ServerConstants.DEFAULT_DISCOVERY_PORTS)
_DEFAULT_HOST = ServerConstants.DEFAULT_DISCOVERY_HOST
_DEFAULT_TIMEOUT = ServerConstants.DEFAULT_DISCOVERY_TIMEOUT


async def probe_cascor_url(url: str, timeout: float = _DEFAULT_TIMEOUT) -> bool:
    """Async probe of a cascor URL. Returns True iff the URL serves a
    live cascor health endpoint with the expected status payload.

    METRICS-MON R4.2: uses :class:`httpx.AsyncClient` natively rather
    than offloading a synchronous ``urllib.request.urlopen`` call to the
    asyncio executor. The previous pattern was correct (no event-loop
    block) but consumed one of the default 32 worker threads per
    concurrent probe — :func:`discover_cascor` fans out across N ports,
    so the offload ceiling matters at scale.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{url}{ServerConstants.HEALTH_LIVE_ENDPOINT}")
        if response.status_code != 200:
            return False
        body = response.json()
        return bool(body.get(ServerConstants.HEALTH_STATUS_KEY) == ServerConstants.HEALTH_LIVE_OK_VALUE)
    except Exception:
        return False


async def discover_cascor(
    host: str = _DEFAULT_HOST,
    ports: Optional[list] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> Optional[str]:
    """Probe well-known ports for a running cascor instance.

    Returns the first responding URL (e.g. ``http://localhost:8200``),
    or ``None`` if no cascor instance is found.

    Args:
        host: Hostname to probe (default: localhost).
        ports: List of ports to probe (default: [8200]).
        timeout: Per-probe timeout in seconds.
    """
    if ports is None:
        ports = _DEFAULT_PORTS

    for port in ports:
        url = f"http://{host}:{port}"
        if await probe_cascor_url(url, timeout):
            logger.info(f"Discovered running cascor at {url}")
            return url

    return None
