"""Auto-discovery of running cascor instances for juniper-canopy.

Probes well-known ports for a running cascor service before falling back to demo mode.
Uses urllib.request (stdlib) via asyncio executor to avoid blocking the event loop.
"""

import asyncio
import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger("juniper_canopy.discovery")

_DEFAULT_PORTS = [8200]
_DEFAULT_HOST = "localhost"
_DEFAULT_TIMEOUT = 2.0


def _probe_url_sync(url: str, timeout: float) -> bool:
    """Synchronous probe of a cascor URL. Validates response body."""
    try:
        req = urllib.request.Request(f"{url}/v1/health/live")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            if resp.status != 200:
                return False
            body = json.loads(resp.read())
            return body.get("status") == "alive"
    except Exception:
        return False


async def probe_cascor_url(url: str, timeout: float = _DEFAULT_TIMEOUT) -> bool:
    """Async probe of a cascor URL. Runs synchronous I/O in executor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _probe_url_sync, url, timeout)


async def discover_cascor(
    host: str = _DEFAULT_HOST,
    ports: Optional[list] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> Optional[str]:
    """
    Probe well-known ports for a running cascor instance.

    Returns the first responding URL (e.g. 'http://localhost:8200'), or None
    if no cascor instance is found.

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
