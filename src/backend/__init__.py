"""
Backend Integration Package

Interfaces with the CasCor neural network backend for monitoring and data collection.

Provides:
    - BackendProtocol: Unified interface for all backend implementations
    - DemoBackend: Adapter wrapping DemoMode for development/testing
    - ServiceBackend: Adapter wrapping CascorServiceAdapter for production (lazy import)
    - create_backend(): Factory function selecting the appropriate backend
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from backend.protocol import BackendProtocol

if TYPE_CHECKING:
    from backend.demo_backend import DemoBackend

__all__ = [
    "BackendProtocol",
    "DemoBackend",
    "create_backend",
]

logger = logging.getLogger("juniper_canopy.backend")


def create_backend(
    *,
    service_url: str | None = None,
    demo_mode: bool | None = None,
) -> BackendProtocol:
    """Factory: create the appropriate backend based on environment.

    Args:
        service_url: Explicit CasCor service URL (overrides settings/env).
        demo_mode: Explicit demo mode flag (overrides settings/env).

    Selection logic (first match wins):
        1. demo_mode=True (explicit)           -> DemoBackend
        2. settings.demo_mode=True             -> DemoBackend
        3. service_url provided                -> ServiceBackend
        4. settings.cascor_service_url set     -> ServiceBackend
        5. Otherwise                           -> DemoBackend (fallback)

    Legacy ``CASCOR_DEMO_MODE`` and ``CASCOR_SERVICE_URL`` env vars are
    handled transparently by ``Settings._check_legacy_demo_mode`` and
    ``Settings._check_cascor_service_url`` (which emit DeprecationWarning),
    so they flow through the corresponding Settings fields above.

    Returns:
        A BackendProtocol-conforming backend instance.
    """
    from backend.demo_backend import DemoBackend
    from demo_mode import get_demo_mode
    from settings import get_settings

    settings = get_settings()

    # Resolve demo mode
    force_demo = demo_mode if demo_mode is not None else settings.demo_mode

    if force_demo:
        logger.info("Demo mode explicitly enabled")
        return DemoBackend(get_demo_mode(update_interval=1.0))

    # Resolve service URL
    resolved_url = service_url or settings.cascor_service_url

    if resolved_url:
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend
        from secrets_util import get_secret

        api_key = get_secret("JUNIPER_CASCOR_API_KEY") or get_secret("JUNIPER_DATA_API_KEY")
        # E.2 PR-2-C: forward the configured Origin to the
        # ``CascorControlStream`` inside the adapter's
        # ``ControlStreamSupervisor`` so cascor's fail-closed
        # ``/ws/control`` allowlist (juniper-cascor#129) admits the
        # docker-compose canopy upgrade. Empty string → opt-out
        # (pre-0.5.0 behaviour of sending no Origin header).
        ws_origin: Optional[str] = settings.cascor_ws_origin or None
        logger.info(f"Service mode: connecting to CasCor at {resolved_url}")
        adapter = CascorServiceAdapter(service_url=resolved_url, api_key=api_key, ws_origin=ws_origin)
        return ServiceBackend(adapter)

    logger.info("No CasCor service URL configured — falling back to demo mode")
    return DemoBackend(get_demo_mode(update_interval=1.0))
