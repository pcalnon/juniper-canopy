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
    from settings import Settings

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
    nn_model: str | None = None,
) -> BackendProtocol:
    """Factory: create the appropriate backend based on environment.

    Args:
        service_url: Explicit CasCor service URL (overrides settings/env).
        demo_mode: Explicit demo mode flag (overrides settings/env).
        nn_model: Selected model key (e.g. ``"recurrence"``). When it resolves to a
            recurrence-provider model (via the registry) and
            ``settings.recurrence_service_url`` is configured, a ``RecurrenceBackend`` is
            returned (A1-ii / D5). ``None`` — the startup default — leaves the demo/cascor
            selection below entirely unchanged.

    Selection logic (first match wins):
        0. nn_model -> recurrence provider (+ recurrence_service_url set) -> RecurrenceBackend
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

    # D5 (A1-ii): route an explicit recurrence-provider model to the recurrence service
    # before the demo/cascor resolution. ``nn_model`` is None on the cascor/demo startup
    # path, so everything below is unchanged unless a recurrence model is requested.
    if nn_model:
        recurrence_backend = _try_create_recurrence_backend(nn_model, settings)
        if recurrence_backend is not None:
            return recurrence_backend

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


def _try_create_recurrence_backend(nn_model: str, settings: "Settings") -> Optional[BackendProtocol]:
    """Return a ``RecurrenceBackend`` if ``nn_model`` is a configured recurrence model, else None.

    Returns ``None`` (so ``create_backend`` falls through to the demo/cascor resolution)
    when ``nn_model`` is not a recurrence-provider model, or when it is but
    ``recurrence_service_url`` is unset — the latter is logged loudly.

    D-8 (canopy E2E arc, plan §7.5): the unset-URL branch is a REACHABLE normal path, not a
    mere safety net. Nothing gates an unconfigured recurrence model out of selection —
    ``model_is_trainable`` (``model_registry.py``) gates on the registry ``status`` only, and
    the recurrence spec is hardcoded ``status="live"``, so the A1 picker shows it as trainable
    and ``POST /api/model/select`` accepts it (HTTP 200) whether or not ``recurrence_service_url``
    is configured. When it is unset the selection is recorded but the live backend stays the
    default cascor/demo backend (``_swap_backend`` treats the target type as unchanged), so the
    user is shown a successful selection of a model that is not actually active. Making the
    unset-URL case gate selection or flip the spec status is a deliberate behaviour change
    tracked in the arc ledger, not a docstring's to assume.
    """
    from model_registry import RECURRENCE_PROVIDER, get_model_spec

    spec = get_model_spec(nn_model)
    if spec is None or spec.provider != RECURRENCE_PROVIDER:
        return None
    if not settings.recurrence_service_url:
        logger.warning("Model %r is a recurrence model but recurrence_service_url is not configured — falling back to the default backend", nn_model)
        return None

    from backend.recurrence_backend import RecurrenceBackend
    from backend.recurrence_service_adapter import RecurrenceServiceAdapter

    adapter = RecurrenceServiceAdapter(settings.recurrence_service_url, settings.recurrence_api_key)
    logger.info("Recurrence mode: model %r -> RecurrenceServiceAdapter at %s", nn_model, settings.recurrence_service_url)
    return RecurrenceBackend(adapter)
