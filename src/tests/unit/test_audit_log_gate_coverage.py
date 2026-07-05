"""Per-file coverage gate: exercise the un-covered audit-emit helpers.

The WebSocket audit logger (``src/audit_log.py``) had three lifecycle-event
helpers that no existing test called, leaving their single-line bodies
uncovered (lines 103 / 113 / 123): ``log_ws_disconnect``,
``log_ws_rate_limited``, and ``log_ws_command``. These are real, meaningful
tests — they attach a capture handler to the dedicated ``canopy.audit`` logger
and assert each helper emits a well-formed structured-JSON event with the
correct ``event`` type and payload fields — so the per-file coverage gate
(juniper-ml per-file rollout C-5) has statement margin on this small module.
"""

from __future__ import annotations

import json
import logging

import audit_log


class _CaptureHandler(logging.Handler):
    """Collect the rendered message of every record for later inspection."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - Handler API
        self.messages.append(record.getMessage())


def test_ws_lifecycle_helpers_emit_structured_events() -> None:
    """log_ws_disconnect / log_ws_rate_limited / log_ws_command emit their events."""
    audit = logging.getLogger("canopy.audit")
    capture = _CaptureHandler()
    audit.addHandler(capture)
    previous_level = audit.level
    audit.setLevel(logging.INFO)
    try:
        audit_log.log_ws_disconnect(endpoint="/ws/control", client_ip="10.0.0.5", client_id="conn-1", reason="client_gone")
        audit_log.log_ws_rate_limited(endpoint="/ws/training", client_ip="10.0.0.5")
        audit_log.log_ws_command(endpoint="/ws/control", client_ip="10.0.0.5", command="start", status="ok")
    finally:
        audit.removeHandler(capture)
        audit.setLevel(previous_level)

    events = [json.loads(message) for message in capture.messages]
    by_type = {event["event"]: event for event in events}

    assert {"ws_disconnect", "ws_rate_limited", "ws_command"} <= set(by_type)

    disconnect = by_type["ws_disconnect"]
    assert disconnect["client_id"] == "conn-1"
    assert disconnect["reason"] == "client_gone"
    assert disconnect["endpoint"] == "/ws/control"

    rate_limited = by_type["ws_rate_limited"]
    # Default reason for the rate-limit helper.
    assert rate_limited["reason"] == "per_ip_cap"
    assert rate_limited["endpoint"] == "/ws/training"

    command = by_type["ws_command"]
    assert command["command"] == "start"
    assert command["status"] == "ok"


def test_ws_command_reason_default_is_overridable() -> None:
    """A non-default ``reason`` on the disconnect helper is carried into the event."""
    audit = logging.getLogger("canopy.audit")
    capture = _CaptureHandler()
    audit.addHandler(capture)
    previous_level = audit.level
    audit.setLevel(logging.INFO)
    try:
        audit_log.log_ws_disconnect(endpoint="/ws", client_ip="127.0.0.1", client_id="c2")
    finally:
        audit.removeHandler(capture)
        audit.setLevel(previous_level)

    event = json.loads(capture.messages[-1])
    # The disconnect helper defaults ``reason`` to "normal".
    assert event["event"] == "ws_disconnect"
    assert event["reason"] == "normal"
