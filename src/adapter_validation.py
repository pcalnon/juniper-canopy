"""Adapter inbound validation for cascor server frames (Phase B-pre-b).

Pydantic model for validating frames received from juniper-cascor over
WebSocket. Malformed frames are logged and counted but do not crash the
adapter — the connection stays up.

This module is scaffolded for Phase C when the adapter opens a /ws/control
stream to cascor. Until then, it provides the CascorServerFrame model
for future use.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger("juniper_canopy.adapter_validation")

# Prometheus counter for malformed frames (created lazily)
_inbound_invalid_counter = None


class CascorServerFrame(BaseModel):
    """Pydantic model for frames received from cascor server.

    Allows extra fields (``extra="allow"``) so new cascor fields don't
    break the adapter. Validates only the minimum required structure.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    data: Optional[Any] = None
    command_id: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


def validate_inbound_frame(raw: dict) -> Optional[CascorServerFrame]:
    """Validate an inbound frame from cascor.

    Returns:
        Validated CascorServerFrame, or None if malformed.
    """
    global _inbound_invalid_counter
    try:
        return CascorServerFrame(**raw)
    except Exception as e:
        logger.warning("Malformed inbound frame from cascor: %s — %s", type(e).__name__, e)
        try:
            if _inbound_invalid_counter is None:
                from prometheus_client import Counter

                _inbound_invalid_counter = Counter(
                    "canopy_adapter_inbound_invalid_total",
                    "Malformed frames received from cascor",
                )
            _inbound_invalid_counter.inc()
        except Exception:  # nosec B110 — graceful degradation when prometheus_client unavailable
            pass
        return None
