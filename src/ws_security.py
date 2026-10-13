"""Origin validation for WebSocket connections (M-SEC-01b).

Explicit copy of juniper-cascor's origin.py — no cross-import per canonical
plan §6.3. Validates the Origin header against a configured allowlist before
accepting WebSocket upgrades. Empty allowlist means reject all (fail-closed).
"""

import logging
from typing import List, Optional

from fastapi import WebSocket

logger = logging.getLogger("juniper_canopy.ws_security")


def is_origin_allowed(origin: Optional[str], allowlist: List[str]) -> bool:
    """Return True if an Origin header value is in the allowlist.

    Transport-agnostic core of :func:`validate_origin`, reused by the REST
    browser-control auth dependency (PR-1) so the HTTP and WebSocket surfaces
    apply identical Origin semantics. Comparison is case-insensitive and
    trailing-slash-insensitive. Fail-closed: a missing/empty ``origin`` (or an
    empty ``allowlist``) returns False.

    Args:
        origin: The request's ``Origin`` header value (or ``None`` if absent).
        allowlist: List of allowed origin strings. Empty = reject all.

    Returns:
        True if ``origin`` matches an allowlisted entry, False otherwise.
    """
    if not origin:
        return False

    origin_lower = origin.lower().rstrip("/")
    return any(origin_lower == allowed.lower().rstrip("/") for allowed in allowlist)


def validate_origin(websocket: WebSocket, allowlist: List[str]) -> bool:
    """Check if the WebSocket connection's Origin header is allowed.

    Args:
        websocket: The incoming WebSocket connection.
        allowlist: List of allowed origin strings. Empty = reject all.

    Returns:
        True if the origin is in the allowlist, False otherwise.
        Missing Origin header is also rejected.
    """
    origin = websocket.headers.get("origin")

    if not origin:
        logger.info("WebSocket origin rejected: no Origin header present")
        return False

    if is_origin_allowed(origin, allowlist):
        return True

    logger.info("WebSocket origin rejected: %s not in allowlist", origin)
    return False
