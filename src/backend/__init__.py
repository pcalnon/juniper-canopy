"""
Backend Integration Package

Interfaces with the CasCor neural network backend for monitoring and data collection.

Provides:
    - BackendProtocol: Unified interface for all backend implementations
    - DemoBackend: Adapter wrapping DemoMode for development/testing
    - ServiceBackend: Adapter wrapping CascorServiceAdapter for production (lazy import)
    - create_backend(): Factory function selecting the appropriate backend
"""

import logging
import os

from backend.demo_backend import DemoBackend
from backend.protocol import BackendProtocol

__all__ = [
    "BackendProtocol",
    "DemoBackend",
    "create_backend",
]

logger = logging.getLogger("juniper_canopy.backend")


def create_backend() -> BackendProtocol:
    """
    Factory: create the appropriate backend based on environment.

    Selection logic:
        1. CASCOR_DEMO_MODE=1/true/yes  -> DemoBackend (explicit demo)
        2. CASCOR_SERVICE_URL set        -> ServiceBackend (real CasCor)
        3. Otherwise                     -> DemoBackend (fallback)

    Returns:
        A BackendProtocol-conforming backend instance.
    """
    from demo_mode import get_demo_mode

    force_demo = os.getenv("CASCOR_DEMO_MODE", "0").lower() in ("1", "true", "yes")
    service_url = os.getenv("CASCOR_SERVICE_URL")

    if force_demo:
        logger.info("Demo mode explicitly enabled via CASCOR_DEMO_MODE")
        return DemoBackend(get_demo_mode(update_interval=1.0))

    if service_url:
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        api_key = os.getenv("JUNIPER_DATA_API_KEY")
        logger.info(f"Service mode: connecting to CasCor at {service_url}")
        adapter = CascorServiceAdapter(service_url=service_url, api_key=api_key)
        return ServiceBackend(adapter)

    logger.info("No CASCOR_SERVICE_URL set — falling back to demo mode")
    return DemoBackend(get_demo_mode(update_interval=1.0))
