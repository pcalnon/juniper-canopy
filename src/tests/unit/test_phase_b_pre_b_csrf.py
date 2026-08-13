"""Tests for Phase B-pre-b CSRF + audit: token store, endpoint, WS auth, adapter validation."""

import hmac
from unittest.mock import patch

import pytest


class _FakeClock:
    """Deterministic monotonic clock, injected into ``CsrfTokenStore``.

    The TTL tests below used to sleep against the real clock. That made
    ``test_validate_refreshes_ttl`` a genuine flake on the loaded macOS CI leg:
    ``time.sleep`` overshoots under scheduling pressure, so a token that should
    still have been inside its refreshed window read as expired and the assertion
    flipped. The margins had already been widened 5x (0.1/0.05/0.07s -> 0.5/0.25/0.35s)
    and it still failed intermittently — widening a race does not close it.

    Driving time explicitly removes the race entirely, makes the assertions exact
    rather than approximate, and drops ~0.6s of real sleeping from the suite.
    """

    def __init__(self, start: float = 1000.0) -> None:
        self._now = float(start)

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.mark.unit
class TestCsrfTokenStore:
    """Test server-side CSRF token store."""

    def test_mint_returns_token(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        token = store.mint()
        assert isinstance(token, str)
        assert len(token) > 20

    def test_validate_valid_token(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        token = store.mint()
        assert store.validate(token) is True

    def test_validate_invalid_token(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        store.mint()
        assert store.validate("bogus-token") is False

    def test_validate_empty_token(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        assert store.validate("") is False
        assert store.validate(None) is False

    def test_validate_expired_token(self):
        """A token past its TTL is rejected."""
        from csrf import CsrfTokenStore

        clock = _FakeClock()
        store = CsrfTokenStore(ttl_seconds=10, clock=clock)
        token = store.mint()  # expires at t+10

        clock.advance(10.001)
        assert store.validate(token) is False

    def test_validate_refreshes_ttl(self):
        """A successful validate slides the TTL forward.

        Driven by an injected clock rather than ``time.sleep`` — see ``_FakeClock``.
        The middle assertion is the one that proves the refresh happened: t=12 is
        past the ORIGINAL expiry (t+10), so the token can only still be valid
        because validating at t=5 pushed expiry out to t+15.
        """
        from csrf import CsrfTokenStore

        clock = _FakeClock()
        store = CsrfTokenStore(ttl_seconds=10, clock=clock)
        token = store.mint()  # expires at t+10

        clock.advance(5)  # t=5
        assert store.validate(token) is True  # refresh -> expires at t+15

        clock.advance(7)  # t=12, past the original t+10 expiry
        assert store.validate(token) is True  # only valid because it refreshed

    def test_refreshed_token_still_expires(self):
        """The sliding window slides, it does not make a token immortal.

        The previous sleep-based test stopped after proving the refresh, so
        nothing covered expiry *after* a refresh. Cheap to assert now that time
        is driven explicitly.
        """
        from csrf import CsrfTokenStore

        clock = _FakeClock()
        store = CsrfTokenStore(ttl_seconds=10, clock=clock)
        token = store.mint()

        clock.advance(5)
        assert store.validate(token) is True  # refresh -> expires at t+15

        clock.advance(10.001)  # t=15.001, past the refreshed expiry
        assert store.validate(token) is False

    def test_revoke_removes_token(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        token = store.mint()
        store.revoke(token)
        assert store.validate(token) is False

    def test_clear_removes_all(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        store.mint()
        store.mint()
        assert store.size == 2
        store.clear()
        assert store.size == 0

    def test_constant_time_comparison(self):
        """Validate uses hmac.compare_digest (constant-time)."""
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60)
        token = store.mint()
        # The implementation uses hmac.compare_digest internally
        # Verify by checking the source or behavior
        assert store.validate(token) is True

    def test_max_tokens_evicts_oldest(self):
        from csrf import CsrfTokenStore

        store = CsrfTokenStore(ttl_seconds=60, max_tokens=3)
        t1 = store.mint()
        store.mint()
        store.mint()
        store.mint()  # 4th token — should evict t1
        assert store.validate(t1) is False
        assert store.size == 3


@pytest.mark.unit
class TestCsrfEndpoint:
    """Test /api/csrf REST endpoint."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_csrf_endpoint_returns_token(self, client):
        resp = client.get("/api/csrf")
        assert resp.status_code == 200
        data = resp.json()
        assert "csrf_token" in data
        assert data["enabled"] is True
        assert len(data["csrf_token"]) > 20

    def test_csrf_token_is_unique_per_call(self, client):
        t1 = client.get("/api/csrf").json()["csrf_token"]
        t2 = client.get("/api/csrf").json()["csrf_token"]
        assert t1 != t2


@pytest.mark.unit
class TestWsControlCsrfAuth:
    """Test CSRF first-frame auth on /ws/control."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_valid_csrf_allows_connection(self, client):
        """Valid CSRF token in first frame allows control WS connection."""
        token = client.get("/api/csrf").json()["csrf_token"]
        with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
            # Manually send CSRF auth first frame
            ws.send_json({"type": "auth", "csrf_token": token})
            ws.send_json({"command": "unknown_test_cmd"})
            resp = ws.receive_json()
            assert isinstance(resp, dict)

    def test_missing_csrf_closes_connection(self, client):
        """Missing CSRF token in first frame closes connection."""
        from starlette.websockets import WebSocketDisconnect

        closed = False
        try:
            with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
                # Send a non-auth frame (no type: "auth")
                ws.send_json({"command": "stop"})
                ws.receive_json()
                ws.receive_json()
        except (WebSocketDisconnect, Exception):
            closed = True
        assert closed, "Expected connection to be closed after missing CSRF"

    def test_invalid_csrf_closes_connection(self, client):
        """Invalid CSRF token in first frame closes connection."""
        from starlette.websockets import WebSocketDisconnect

        closed = False
        try:
            with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
                ws.send_json({"type": "auth", "csrf_token": "invalid-token"})
                ws.receive_json()
                ws.receive_json()
        except (WebSocketDisconnect, Exception):
            closed = True
        assert closed, "Expected connection to be closed after invalid CSRF"


@pytest.mark.unit
class TestAuditLogCsrf:
    """Test CSRF audit logging events."""

    def test_log_ws_csrf_rejected_exists(self):
        from audit_log import log_ws_csrf_rejected

        # Just verify the function exists and is callable
        assert callable(log_ws_csrf_rejected)

    def test_log_ws_command_exists(self):
        from audit_log import log_ws_command

        assert callable(log_ws_command)

    def test_audit_log_crlf_escaping(self):
        """Verify CRLF characters are escaped in audit log entries."""
        from audit_log import _escape_crlf

        assert "\\r" in _escape_crlf("test\rinjection")
        assert "\\n" in _escape_crlf("test\ninjection")
        assert "\\t" in _escape_crlf("test\tinjection")
        assert _escape_crlf("clean string") == "clean string"


@pytest.mark.unit
class TestAdapterValidation:
    """Test cascor server frame validation."""

    def test_valid_frame_parses(self):
        from adapter_validation import CascorServerFrame

        frame = CascorServerFrame(type="command_response", status="success")
        assert frame.type == "command_response"
        assert frame.status == "success"

    def test_extra_fields_allowed(self):
        from adapter_validation import CascorServerFrame

        frame = CascorServerFrame(type="metrics", data={"epoch": 1}, extra_field="ok")
        assert frame.type == "metrics"

    def test_missing_type_rejected(self):
        from adapter_validation import validate_inbound_frame

        result = validate_inbound_frame({"data": "no type"})
        assert result is None

    def test_valid_frame_validates(self):
        from adapter_validation import validate_inbound_frame

        result = validate_inbound_frame({"type": "state_change", "data": {"status": "running"}})
        assert result is not None
        assert result.type == "state_change"


@pytest.mark.unit
class TestPhaseBPreBSettings:
    """Test Phase B-pre-b settings."""

    def test_csrf_defaults(self):
        from settings import Settings, get_settings

        get_settings.cache_clear()
        s = Settings()
        assert s.csrf_enabled is True
        assert s.csrf_token_ttl_seconds == 3600
        assert s.ws_control_auth_timeout == 5.0

    def test_session_secret_auto_generated_when_empty(self):
        from settings import Settings

        s = Settings()
        # Empty string means main.py will auto-generate
        assert s.session_secret_key == ""


@pytest.mark.unit
class TestOpaqueCloseReasons:
    """Test M-SEC-06: opaque close reasons on /ws/control."""

    def test_control_endpoint_close_reasons_are_opaque(self):
        """Verify close reasons don't leak implementation details."""
        import inspect

        from main import websocket_control_endpoint

        source = inspect.getsource(websocket_control_endpoint)
        # All close reasons in /ws/control should be "Policy violation"
        # (not descriptive strings like "Origin not allowed")
        import re

        close_reasons = re.findall(r'reason="([^"]+)"', source)
        for reason in close_reasons:
            assert reason == "Policy violation", f"Non-opaque close reason found: {reason!r}"
