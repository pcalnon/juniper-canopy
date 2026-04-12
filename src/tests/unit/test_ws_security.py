"""Tests for Phase B-pre-a WebSocket security: origin validation, per-IP caps, audit logger."""

import json
from unittest.mock import AsyncMock

import pytest

from ws_security import validate_origin


@pytest.mark.unit
class TestOriginValidation:
    """Test origin allowlist validation (M-SEC-01b)."""

    def _make_ws(self, origin=None):
        ws = AsyncMock()
        headers = {}
        if origin is not None:
            headers["origin"] = origin
        ws.headers = headers
        return ws

    def test_origin_allowlist_accepts_configured_origin(self):
        ws = self._make_ws("http://localhost:8050")
        assert validate_origin(ws, ["http://localhost:8050"]) is True

    def test_origin_allowlist_rejects_third_party(self):
        ws = self._make_ws("http://evil.example.com")
        assert validate_origin(ws, ["http://localhost:8050"]) is False

    def test_origin_allowlist_rejects_missing_origin(self):
        ws = self._make_ws(origin=None)
        assert validate_origin(ws, ["http://localhost:8050"]) is False

    def test_empty_allowlist_rejects_all_fail_closed(self):
        ws = self._make_ws("http://localhost:8050")
        assert validate_origin(ws, []) is False

    def test_origin_case_insensitive(self):
        ws = self._make_ws("HTTP://LOCALHOST:8050")
        assert validate_origin(ws, ["http://localhost:8050"]) is True

    def test_origin_port_significant(self):
        ws = self._make_ws("http://localhost:9999")
        assert validate_origin(ws, ["http://localhost:8050"]) is False

    def test_origin_trailing_slash_ignored(self):
        ws = self._make_ws("http://localhost:8050/")
        assert validate_origin(ws, ["http://localhost:8050"]) is True

    def test_multiple_allowed_origins(self):
        ws = self._make_ws("http://127.0.0.1:8050")
        assert validate_origin(ws, ["http://localhost:8050", "http://127.0.0.1:8050"]) is True


@pytest.mark.unit
class TestPerIpLimit:
    """Test per-IP connection caps on canopy websocket_manager (M-SEC-04)."""

    def _make_ws_with_ip(self, ip="127.0.0.1"):
        ws = AsyncMock()
        ws.client = (ip, 12345)
        return ws

    def test_per_ip_allows_under_limit(self):
        from communication.websocket_manager import WebSocketManager

        mgr = WebSocketManager()
        ws = self._make_ws_with_ip("10.0.0.1")
        assert mgr.check_per_ip_limit(ws, max_per_ip=5) is True
        assert mgr._per_ip_counts["10.0.0.1"] == 1

    def test_per_ip_cap_enforced(self):
        from communication.websocket_manager import WebSocketManager

        mgr = WebSocketManager()
        for _ in range(5):
            ws = self._make_ws_with_ip("10.0.0.1")
            mgr.check_per_ip_limit(ws, max_per_ip=5)
        ws6 = self._make_ws_with_ip("10.0.0.1")
        assert mgr.check_per_ip_limit(ws6, max_per_ip=5) is False

    def test_per_ip_counter_decrements_on_disconnect(self):
        from communication.websocket_manager import WebSocketManager

        mgr = WebSocketManager()
        ws = self._make_ws_with_ip("10.0.0.1")
        mgr.check_per_ip_limit(ws, max_per_ip=5)
        mgr.active_connections.add(ws)
        mgr.connection_metadata[ws] = {"client_id": "test"}
        mgr.disconnect(ws)
        assert mgr._per_ip_counts.get("10.0.0.1", 0) == 0


@pytest.mark.unit
class TestAuditLogger:
    """Test audit log skeleton (M-SEC-07)."""

    def test_configure_audit_logger_disabled(self):
        from audit_log import configure_audit_logger

        logger = configure_audit_logger(enabled=False)
        assert logger.name == "canopy.audit"

    def test_crlf_escape(self):
        from audit_log import _escape_crlf

        assert _escape_crlf("hello\r\nworld\t!") == "hello\\r\\nworld\\t!"
        assert _escape_crlf("safe string") == "safe string"

    def test_log_ws_connect_does_not_raise(self):
        from audit_log import configure_audit_logger, log_ws_connect

        configure_audit_logger(enabled=False)
        log_ws_connect("/ws/training", "127.0.0.1", "client-1", origin="http://localhost:8050")

    def test_log_ws_origin_rejected_does_not_raise(self):
        from audit_log import configure_audit_logger, log_ws_origin_rejected

        configure_audit_logger(enabled=False)
        log_ws_origin_rejected("/ws/training", "10.0.0.1", "http://evil.com")
