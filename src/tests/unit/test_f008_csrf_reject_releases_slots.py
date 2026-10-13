"""F-CANOPY-008 regression: a rejected CSRF first-frame on ``/ws/control`` must
release everything the handshake reserved.

Found live in the canopy E2E arc (juniper-ml evidence note, F-CANOPY-008): after
a canopy restart the browser's auto-reconnect presented a stale CSRF token five
times, and every rejection kept the per-IP slot it had reserved --
``Per-IP limit reached for 127.0.0.1 (5/5)`` then survived page closes, cookie
and storage clears and idle time; only a canopy restart freed the control plane.
``connect()`` has already succeeded when the CSRF gate runs, so a reject arm that
only ``close()``s leaks the per-IP / per-session slot, the ``active_connections``
entry and the ``{channel="control"}`` gauge count. The fix funnels every reject
arm through ``websocket_manager.disconnect()``.

Every test here drives the REAL handler through the real ``main.app`` -- the
auth seam is never stubbed (the canopy "green tests / dead app" risk class). The
slot snapshot is polled rather than read once because the TestClient's receive
can observe the close frame a beat before the handler's teardown has run.
"""

import time

import pytest
from starlette.websockets import WebSocketDisconnect

_STALE_AUTH = {"type": "auth", "csrf_token": "stale-token-minted-by-a-previous-canopy-process"}


def _reject_once(client, send) -> int:
    """Open a control socket, apply ``send`` as the first frame, and return the
    close code the server answered with."""
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
            send(ws)
            # The handler emits a connection_established frame before the CSRF
            # check, so the close surfaces on a later receive; 5 is an upper bound.
            for _ in range(5):
                ws.receive_json(timeout=5.0)
    return exc.value.code


def _slot_snapshot(mgr) -> dict:
    """Everything a rejected handshake can leak, in one comparable value."""
    return {
        "per_ip": dict(mgr._per_ip_counts),
        "per_session": dict(mgr._per_session_counts),
        "control_gauge": mgr._channel_counts.get("control", 0),
        "active": len(mgr.active_connections),
    }


def _assert_restored(mgr, before: dict, arm: str, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _slot_snapshot(mgr) == before:
            return
        time.sleep(0.02)
    assert _slot_snapshot(mgr) == before, f"{arm}: the rejected handshake leaked its reservation"


@pytest.mark.unit
class TestF008CsrfRejectReleasesSlots:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from main import app

        return TestClient(app)

    def test_stale_token_rejections_do_not_exhaust_the_per_ip_cap(self, client):
        """The live signature: cap+1 stale-token handshakes from ONE IP, then a
        valid handshake still connects. On the leaking handler the (cap+1)-th
        attempt is refused 1013 (per-IP limit) and the operator is locked out."""
        import main

        mgr = main.websocket_manager
        cap = main.settings.websocket.max_connections_per_ip
        before = _slot_snapshot(mgr)

        codes = [_reject_once(client, lambda ws: ws.send_json(_STALE_AUTH)) for _ in range(cap + 1)]
        assert codes == [1008] * (cap + 1), codes
        _assert_restored(mgr, before, "invalid_token x cap+1")

        token = client.get("/api/csrf").json()["csrf_token"]
        with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
            ws.send_json({"type": "auth", "csrf_token": token})
            ws.send_json({"command": "f008_probe"})
            assert isinstance(ws.receive_json(timeout=5.0), dict)
        _assert_restored(mgr, before, "valid handshake after the rejections")

    @pytest.mark.parametrize(
        "arm, send",
        [
            ("invalid_token", lambda ws: ws.send_json(_STALE_AUTH)),
            ("missing_or_invalid_frame", lambda ws: ws.send_json({"command": "stop"})),
            ("malformed_auth", lambda ws: ws.send_text("this-is-not-json")),
        ],
        ids=["invalid_token", "missing_or_invalid_frame", "malformed_auth"],
    )
    def test_each_reject_arm_releases_slot_registration_and_gauge(self, client, arm, send):
        import main

        mgr = main.websocket_manager
        before = _slot_snapshot(mgr)
        assert _reject_once(client, send) == 1008
        _assert_restored(mgr, before, arm)

    def test_auth_timeout_arm_releases_slot_registration_and_gauge(self, client, monkeypatch):
        # Same deterministic idiom as test_main_gate_coverage_ws_helpers: the CSRF
        # first-frame wait_for raises immediately when called with a sentinel
        # timeout, so the auth_timeout arm fires without any real timer.
        import main

        mgr = main.websocket_manager
        _sentinel = 0.654321
        _real_wait_for = main.asyncio.wait_for
        monkeypatch.setattr(main.settings, "ws_control_auth_timeout", _sentinel)

        async def _wait_for(coro, timeout=None):
            if timeout == _sentinel:
                if main.asyncio.iscoroutine(coro):
                    coro.close()
                raise main.asyncio.TimeoutError
            return await _real_wait_for(coro, timeout=timeout)

        monkeypatch.setattr(main.asyncio, "wait_for", _wait_for)
        before = _slot_snapshot(mgr)
        assert _reject_once(client, lambda ws: None) == 1008
        _assert_restored(mgr, before, "auth_timeout")
