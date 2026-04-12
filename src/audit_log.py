"""WebSocket audit logger skeleton (M-SEC-07).

Structured JSON audit log for WebSocket connection lifecycle events.
Uses a dedicated ``canopy.audit`` logger with daily rotation.
"""

import json
import logging
import re
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

_audit_logger: Optional[logging.Logger] = None

# CRLF escape pattern for log injection prevention
_CRLF_RE = re.compile(r"[\r\n\t]")


def _escape_crlf(s: str) -> str:
    """Escape CR, LF, and TAB characters to prevent log injection."""
    return _CRLF_RE.sub(lambda m: repr(m.group(0))[1:-1], s)


def configure_audit_logger(
    log_path: str = "/var/log/canopy/audit.log",
    retention_days: int = 90,
    enabled: bool = True,
) -> logging.Logger:
    """Configure the canopy.audit logger with daily rotation.

    Args:
        log_path: Path to the audit log file.
        retention_days: Number of daily backups to retain.
        enabled: If False, the logger is configured with NullHandler only.

    Returns:
        The configured ``canopy.audit`` logger.
    """
    global _audit_logger
    audit = logging.getLogger("canopy.audit")

    if not enabled:
        audit.addHandler(logging.NullHandler())
        audit.setLevel(logging.CRITICAL + 1)
        _audit_logger = audit
        return audit

    # Ensure parent directory exists
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    handler = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        backupCount=retention_days,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit.addHandler(handler)
    audit.setLevel(logging.INFO)
    audit.propagate = False  # Don't forward to root logger
    _audit_logger = audit
    return audit


def _get_audit_logger() -> logging.Logger:
    """Get the audit logger, configuring with NullHandler if not yet set up."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = logging.getLogger("canopy.audit")
        if not _audit_logger.handlers:
            _audit_logger.addHandler(logging.NullHandler())
    return _audit_logger


def _emit(event_type: str, **fields) -> None:
    """Emit a structured JSON audit event."""
    entry = {
        "event": event_type,
        "timestamp": time.time(),
        **{k: _escape_crlf(str(v)) if isinstance(v, str) else v for k, v in fields.items()},
    }
    _get_audit_logger().info(json.dumps(entry, separators=(",", ":")))


def log_ws_connect(endpoint: str, client_ip: str, client_id: str, origin: Optional[str] = None) -> None:
    """Log a WebSocket connection event."""
    _emit("ws_connect", endpoint=endpoint, client_ip=client_ip, client_id=client_id, origin=origin or "")


def log_ws_disconnect(endpoint: str, client_ip: str, client_id: str, reason: str = "normal") -> None:
    """Log a WebSocket disconnection event."""
    _emit("ws_disconnect", endpoint=endpoint, client_ip=client_ip, client_id=client_id, reason=reason)


def log_ws_origin_rejected(endpoint: str, client_ip: str, origin: str) -> None:
    """Log a rejected origin."""
    _emit("ws_origin_rejected", endpoint=endpoint, client_ip=client_ip, origin=origin)


def log_ws_rate_limited(endpoint: str, client_ip: str, reason: str = "per_ip_cap") -> None:
    """Log a rate-limited connection."""
    _emit("ws_rate_limited", endpoint=endpoint, client_ip=client_ip, reason=reason)
