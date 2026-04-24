"""Phase 1B Track 1 security remediation tests (SEC-05/06/12/13/14)."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("JUNIPER_CANOPY_DEMO_MODE", "1")

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


@pytest.fixture(scope="module")
def app_client():
    """TestClient bound to the FastAPI app in demo mode."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        yield client


# =============================================================================
# SEC-13: /api/remote/connect must require POST body, not query params
# =============================================================================


class TestSEC13RemoteConnectBody:
    """authkey now travels in the POST body so it is never logged in URLs."""

    def test_post_body_accepted(self, app_client):
        response = app_client.post(
            "/api/remote/connect",
            json={"host": "localhost", "port": 5000, "authkey": "secret"},
        )
        # In demo mode the handler returns 503, but we care that the body
        # was parsed rather than rejected with 422.
        assert response.status_code in (200, 503)

    def test_query_param_authkey_rejected(self, app_client):
        response = app_client.post(
            "/api/remote/connect",
            params={"host": "localhost", "port": 5000, "authkey": "secret"},
        )
        assert response.status_code == 422

    def test_missing_body_rejected(self, app_client):
        response = app_client.post("/api/remote/connect")
        assert response.status_code == 422

    def test_invalid_port_rejected(self, app_client):
        response = app_client.post(
            "/api/remote/connect",
            json={"host": "localhost", "port": 70000, "authkey": "secret"},
        )
        assert response.status_code == 422


# =============================================================================
# SEC-14: str(e) leaks replaced with generic error + error_id
# =============================================================================


class TestSEC14ErrorResponses:
    """500 responses must not leak exception messages; they expose error_id instead."""

    def test_dataset_generate_error_is_opaque(self, app_client, monkeypatch):
        import main

        def boom(*_args, **_kwargs):
            raise RuntimeError("internal sentinel <should-not-leak>")

        monkeypatch.setattr(main.backend, "regenerate_dataset", boom, raising=False)
        response = app_client.post(
            "/api/dataset/generate",
            json={"n_samples": 100, "n_spirals": 2},
        )
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "Internal server error"
        assert "sentinel" not in repr(body)
        assert len(body.get("error_id", "")) == 12

    def test_set_params_error_is_opaque(self, app_client, monkeypatch):
        import main

        def boom(**_kwargs):
            raise RuntimeError("set_params sentinel <leak-detector>")

        monkeypatch.setattr(main.backend, "apply_params", boom)
        response = app_client.post("/api/set_params", json={"nn_learning_rate": 0.01})
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "Internal server error"
        assert "sentinel" not in repr(body)
        assert len(body.get("error_id", "")) == 12

    def test_remote_connect_error_is_opaque(self, app_client, monkeypatch):
        import main

        adapter = MagicMock()
        adapter.connect_remote_workers.side_effect = RuntimeError("remote sentinel <leak-detector>")
        fake_backend = MagicMock()
        fake_backend.backend_type = "service"
        fake_backend._adapter = adapter
        monkeypatch.setattr(main, "backend", fake_backend)
        response = app_client.post(
            "/api/remote/connect",
            json={"host": "localhost", "port": 5000, "authkey": "secret"},
        )
        assert response.status_code == 500
        body = response.json()
        assert body["error"] == "Internal server error"
        assert "sentinel" not in repr(body)
        assert len(body.get("error_id", "")) == 12


# =============================================================================
# SEC-06: opt-in Sec-WebSocket-Protocol bearer-token auth
# =============================================================================


class TestSEC06WebSocketTokenAuth:
    """Token auth helper must reject bad bearer negotiation when enabled."""

    @pytest.mark.asyncio
    async def test_disabled_is_noop(self):
        import main

        main.settings.ws_auth_enabled = False
        websocket = MagicMock()
        ok, subprotocol = await main._authenticate_websocket_token(websocket)
        assert ok is True
        assert subprotocol is None

    @pytest.mark.asyncio
    async def test_enabled_missing_header_closes(self):
        import main

        main.settings.ws_auth_enabled = True
        try:
            closed = []

            class FakeWS:
                headers = {}

                async def close(self, code: int, reason: str) -> None:
                    closed.append((code, reason))

            ok, sub = await main._authenticate_websocket_token(FakeWS())
            assert ok is False
            assert sub is None
            assert closed == [(1008, "Authentication required")]
        finally:
            main.settings.ws_auth_enabled = False

    @pytest.mark.asyncio
    async def test_enabled_invalid_token_closes(self, monkeypatch):
        import main

        main.settings.ws_auth_enabled = True
        monkeypatch.setattr(main.api_key_auth, "_enabled", True, raising=False)
        monkeypatch.setattr(main.api_key_auth, "_api_keys", {"good-key"}, raising=False)
        try:
            closed = []

            class FakeWS:
                headers = {"sec-websocket-protocol": "bearer, bad-key"}

                async def close(self, code: int, reason: str) -> None:
                    closed.append((code, reason))

            ok, sub = await main._authenticate_websocket_token(FakeWS())
            assert ok is False
            assert sub is None
            assert closed == [(1008, "Invalid authentication token")]
        finally:
            main.settings.ws_auth_enabled = False

    @pytest.mark.asyncio
    async def test_enabled_valid_token_returns_subprotocol(self, monkeypatch):
        import main

        main.settings.ws_auth_enabled = True
        monkeypatch.setattr(main.api_key_auth, "_enabled", True, raising=False)
        monkeypatch.setattr(main.api_key_auth, "_api_keys", {"good-key"}, raising=False)
        try:

            class FakeWS:
                headers = {"sec-websocket-protocol": "bearer, good-key"}

                async def close(self, code: int, reason: str) -> None:  # pragma: no cover
                    raise AssertionError("should not close on valid token")

            ok, sub = await main._authenticate_websocket_token(FakeWS())
            assert ok is True
            assert sub == main.WS_BEARER_SUBPROTOCOL
        finally:
            main.settings.ws_auth_enabled = False


# =============================================================================
# SEC-05 / SEC-12: /ws origin and per-IP checks
# =============================================================================


class TestSEC05SEC12WSOriginAndPerIP:
    """/ws endpoint must enforce origin allowlist and per-IP cap."""

    def test_ws_rejects_bad_origin(self, app_client):
        from starlette.websockets import WebSocketDisconnect

        import main

        main.settings.websocket.allowed_origins = ["http://localhost:8050"]
        with pytest.raises(WebSocketDisconnect):
            with app_client.websocket_connect("/ws", headers={"origin": "http://evil.example"}):
                pass

    def test_ws_accepts_allowed_origin(self, app_client):
        import main

        main.settings.websocket.allowed_origins = ["http://localhost:8050"]
        with app_client.websocket_connect("/ws", headers={"origin": "http://localhost:8050"}) as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connection_established"
