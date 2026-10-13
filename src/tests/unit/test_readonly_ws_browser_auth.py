"""PR-1 C5: read-only browser WebSocket key-gate relaxation (/ws/training, /ws).

Companion to ``test_browser_control_auth.py``, split into its own module so the
read-only-stream relaxation stays independently reviewable/droppable (design
decision: a separate commit after ``/ws/control``). These streams carry no
state and no CSRF first-frame, so the keyless same-origin browser is admitted
by the Origin gate alone; a present key is still validated. Drives the real
``main.app`` auth path — the seam is not stubbed.

Design of record: notes/JUNIPER_CANOPY_TRAINING-CONTROL-AUTH_DESIGN_2026-06-30.md §8.3
"""

import pytest

_ALLOWED_ORIGIN = "http://localhost:8050"  # in the default allowed_origins
_DISALLOWED_ORIGIN = "http://evil.example"
_TEST_KEY = "readonly-ws-test-key"


def _enable_api_key_auth(monkeypatch, key: str = _TEST_KEY) -> str:
    """Turn API-key auth ON against the real app without stubbing the seam.

    Points both the singleton accessor and ``main.api_key_auth`` (used by
    ``_authenticate_websocket``) at one shared enabled instance.
    """
    import main
    import security

    auth = security.APIKeyAuth([key])
    monkeypatch.setattr(security, "_api_key_auth", auth)
    monkeypatch.setattr(main, "api_key_auth", auth)
    return key


@pytest.mark.unit
class TestReadOnlyWsBrowserAuthRelaxation:
    """The read-only streams /ws/training and /ws admit the keyless
    same-origin browser (Origin-only), and still guard on a bad Origin."""

    def test_ws_training_keyless_allowed_origin_accepted(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        with client.websocket_connect("/ws/training", headers={"origin": _ALLOWED_ORIGIN}) as ws:
            msg = ws.receive_json()  # initial_status pushed on accept
            assert isinstance(msg, dict)

    def test_ws_compat_keyless_allowed_origin_accepted(self, client, monkeypatch):
        _enable_api_key_auth(monkeypatch)
        with client.websocket_connect("/ws", headers={"origin": _ALLOWED_ORIGIN}) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connection_established"

    def test_ws_training_keyless_disallowed_origin_closed_4003(self, client, monkeypatch):
        from starlette.websockets import WebSocketDisconnect

        _enable_api_key_auth(monkeypatch)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/training", headers={"origin": _DISALLOWED_ORIGIN}):
                pass
        assert exc.value.code == 4003
