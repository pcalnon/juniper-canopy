#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_main_gate_coverage_ws_helpers.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for src/main.py WebSocket
#                endpoints, authentication helpers, the CSRF endpoint,
#                URL-based dataset import, generator listing, and the
#                application lifespan (startup/shutdown) branches.
#####################################################################
"""Real unit tests for main.py WebSocket / helper / lifespan branches.

WebSocket rejection branches are exercised by calling the async endpoint
functions directly with a lightweight fake WebSocket (so no live server is
needed); the in-loop branches are exercised through the real TestClient WS
transport. The lifespan branches are driven by entering ``main.lifespan``
directly with the network seams (discovery, health probes, backend factory)
patched to synchronous fakes.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import main  # noqa: E402


class _Headers:
    def __init__(self, data):
        self._data = data or {}

    def get(self, key, default=None):
        return self._data.get(key, default)


class FakeWebSocket:
    """Minimal WebSocket double for exercising endpoint rejection branches."""

    def __init__(self, headers=None, query=None, client=("203.0.113.9", 44444)):
        self.headers = _Headers(headers)
        self.query_params = _Headers(query)
        self.client = client
        self.closed = []
        self.sent = []
        self.accepted = False

    async def accept(self, *args, **kwargs):
        self.accepted = True

    async def close(self, code=None, reason=None):
        self.closed.append((code, reason))

    async def send_json(self, data):
        self.sent.append(data)

    async def send_text(self, data):
        self.sent.append(data)

    async def receive_text(self):  # overridden per-test where needed
        raise WebSocketDisconnect()


# =============================================================================
# _authenticate_websocket — invalid key closes 4001 (lines 546-547)
# =============================================================================
class TestAuthenticateWebSocket:
    @pytest.mark.asyncio
    async def test_invalid_key_closes_4001(self):
        fake = FakeWebSocket(headers={"X-API-Key": "wrong-key"})
        keyauth = MagicMock()
        keyauth.enabled = True
        keyauth.validate.return_value = False
        with patch.object(main, "api_key_auth", keyauth):
            authed = await main._authenticate_websocket(fake)
        assert authed is False
        assert fake.closed == [(4001, "Authentication required")]


# =============================================================================
# /ws/training endpoint — early rejection branches (607, 612, 630-631)
# =============================================================================
class TestTrainingEndpointRejections:
    @pytest.mark.asyncio
    async def test_key_auth_failure_returns_early(self):
        fake = FakeWebSocket()
        with patch.object(main, "_authenticate_websocket", AsyncMock(return_value=False)):
            await main.websocket_training_endpoint(fake)
        assert fake.sent == []
        assert fake.accepted is False

    @pytest.mark.asyncio
    async def test_bearer_token_failure_returns_early(self):
        fake = FakeWebSocket()
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(False, None))),
        ):
            await main.websocket_training_endpoint(fake)
        assert fake.accepted is False

    @pytest.mark.asyncio
    async def test_per_ip_limit_closes_1013(self):
        import ws_security

        fake = FakeWebSocket(headers={"origin": "http://localhost:8050"})
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(True, None))),
            patch.object(ws_security, "validate_origin", return_value=True),
            patch.object(main.websocket_manager, "check_per_ip_limit", return_value=False),
        ):
            await main.websocket_training_endpoint(fake)
        assert fake.closed == [(1013, "Per-IP connection limit reached")]


# =============================================================================
# /ws/control endpoint — early rejection branches (728, 733, 751-752)
# =============================================================================
class TestControlEndpointRejections:
    @pytest.mark.asyncio
    async def test_key_auth_failure_returns_early(self):
        fake = FakeWebSocket()
        with patch.object(main, "_authenticate_websocket", AsyncMock(return_value=False)):
            await main.websocket_control_endpoint(fake)
        assert fake.accepted is False

    @pytest.mark.asyncio
    async def test_bearer_token_failure_returns_early(self):
        fake = FakeWebSocket()
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(False, None))),
        ):
            await main.websocket_control_endpoint(fake)
        assert fake.accepted is False

    @pytest.mark.asyncio
    async def test_per_ip_limit_closes_1013(self):
        import ws_security

        fake = FakeWebSocket(headers={"origin": "http://localhost:8050"})
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(True, None))),
            patch.object(ws_security, "validate_origin", return_value=True),
            patch.object(main.websocket_manager, "check_per_ip_limit", return_value=False),
        ):
            await main.websocket_control_endpoint(fake)
        assert fake.closed == [(1013, "Policy violation")]


# =============================================================================
# /ws general endpoint — rejection + receive-loop error (2936, 2941, 2959-2960, 2968-2969)
# =============================================================================
class TestGeneralWsEndpoint:
    @pytest.mark.asyncio
    async def test_key_auth_failure_returns_early(self):
        fake = FakeWebSocket()
        with patch.object(main, "_authenticate_websocket", AsyncMock(return_value=False)):
            await main.ws_endpoint(fake)
        assert fake.accepted is False

    @pytest.mark.asyncio
    async def test_bearer_token_failure_returns_early(self):
        fake = FakeWebSocket()
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(False, None))),
        ):
            await main.ws_endpoint(fake)
        assert fake.accepted is False

    @pytest.mark.asyncio
    async def test_per_ip_limit_closes_1013(self):
        import ws_security

        fake = FakeWebSocket(headers={"origin": "http://localhost:8050"})
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(True, None))),
            patch.object(ws_security, "validate_origin", return_value=True),
            patch.object(main.websocket_manager, "check_per_ip_limit", return_value=False),
        ):
            await main.ws_endpoint(fake)
        assert fake.closed == [(1013, "Per-IP connection limit reached")]

    @pytest.mark.asyncio
    async def test_receive_loop_unexpected_error_logged(self):
        import ws_security

        fake = FakeWebSocket(headers={"origin": "http://localhost:8050"})
        fake.receive_text = AsyncMock(side_effect=ValueError("boom"))
        with (
            patch.object(main, "_authenticate_websocket", AsyncMock(return_value=True)),
            patch.object(main, "_authenticate_websocket_token", AsyncMock(return_value=(True, None))),
            patch.object(ws_security, "validate_origin", return_value=True),
            patch.object(main.websocket_manager, "check_per_ip_limit", return_value=True),
            patch.object(main.websocket_manager, "connect", AsyncMock()),
            patch.object(main.websocket_manager, "disconnect") as disc,
            patch.object(main.system_logger, "error") as log_error,
        ):
            await main.ws_endpoint(fake)
        log_error.assert_called_once()
        disc.assert_called_once_with(fake)


# =============================================================================
# /ws/training in-loop branches via real TestClient transport (659, 662-663, 675-677)
# =============================================================================
class TestTrainingEndpointLoop:
    def test_message_too_large_returns_error(self, client, monkeypatch):
        monkeypatch.setattr(main.settings.websocket, "max_message_size_training", 10)
        with client.websocket_connect("/ws/training") as ws:
            ws.receive_json()  # initial_status
            ws.receive_json()  # state
            ws.send_text("x" * 50)
            found = None
            for _ in range(20):
                msg = ws.receive_json(timeout=3.0)
                if msg.get("error") == "Message too large":
                    found = msg
                    break
            assert found is not None
            assert found["ok"] is False

    def test_no_idle_timeout_branch_processes_ping(self, client, monkeypatch):
        monkeypatch.setattr(main.settings.websocket, "idle_timeout_seconds", 0)
        with client.websocket_connect("/ws/training") as ws:
            ws.receive_json()  # initial_status
            ws.receive_json()  # state
            ws.send_json({"type": "ping"})
            pong = None
            for _ in range(20):
                msg = ws.receive_json(timeout=3.0)
                if msg.get("type") == "pong":
                    pong = msg
                    break
            assert pong is not None and pong.get("type") == "pong"

    def test_idle_timeout_closes_connection(self, client, monkeypatch):
        monkeypatch.setattr(main.settings.websocket, "idle_timeout_seconds", 0.4)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/training") as ws:
                ws.receive_json()  # initial_status
                ws.receive_json()  # state
                for _ in range(60):
                    ws.receive_json(timeout=3.0)
        assert exc_info.value.code == 1000


# =============================================================================
# /ws/control in-loop branches via TestClient (818-822, 829, 846-847, 857-858)
# =============================================================================
def _drain_for(ws, predicate, max_msgs=25):
    for _ in range(max_msgs):
        msg = ws.receive_json(timeout=3.0)
        if predicate(msg):
            return msg
    return None


class TestControlEndpointLoop:
    def test_set_params_command_dispatched(self, client):
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()  # connect/state message
            ws.send_json({"command": "set_params", "params": {"nn_learning_rate": 0.05}, "command_id": "c1"})
            msg = _drain_for(ws, lambda m: m.get("command_id") == "c1" or "ok" in m)
            assert msg is not None
            assert "ok" in msg

    def test_set_params_without_params_errors(self, client):
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "set_params", "command_id": "c2"})
            msg = _drain_for(ws, lambda m: m.get("command_id") == "c2" or m.get("ok") is False)
            assert msg is not None
            assert msg.get("ok") is False

    def test_message_too_large_returns_error(self, client, monkeypatch):
        monkeypatch.setattr(main.settings.websocket, "max_message_size_control", 10)
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"command": "stop", "command_id": "big"})
            msg = _drain_for(ws, lambda m: m.get("error") == "Message too large")
            assert msg is not None

    def test_ping_receives_pong(self, client):
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"type": "ping"})
            pong = _drain_for(ws, lambda m: m.get("type") == "pong")
            assert pong is not None and pong.get("type") == "pong"

    def test_pong_is_noop_then_ping_pongs(self, client):
        with client.websocket_connect("/ws/control") as ws:
            ws.receive_json()
            ws.send_json({"type": "pong"})  # no-op: must not produce a response
            ws.send_json({"type": "ping"})
            pong = _drain_for(ws, lambda m: m.get("type") == "pong")
            assert pong is not None and pong.get("type") == "pong"


# =============================================================================
# /ws/control CSRF first-frame branches (780-787)
# =============================================================================
class TestControlCsrfFirstFrame:
    def test_malformed_auth_frame_closes_1008(self, client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
                ws.send_text("this-is-not-json")
                for _ in range(5):
                    ws.receive_json(timeout=3.0)
        assert exc_info.value.code == 1008

    def test_auth_timeout_closes_1008(self, client, monkeypatch):
        # Deterministic (no wall-clock race): the previous version set a real 0.3s
        # ``ws_control_auth_timeout`` and raced the server's timer against the
        # TestClient's close propagation (flaked on the 3.13/3.14/macos legs). Instead,
        # patch the CSRF first-frame ``asyncio.wait_for`` to raise ``TimeoutError``
        # immediately when it is called with the (distinctive) sentinel auth timeout, so
        # the timeout branch (main.py close-1008) fires without any real timer. Every
        # other ``asyncio.wait_for`` (including the TestClient's own) keeps delegating to
        # the real implementation, so nothing else is affected.
        _sentinel = 0.123456
        _real_wait_for = main.asyncio.wait_for
        monkeypatch.setattr(main.settings, "ws_control_auth_timeout", _sentinel)

        async def _wait_for(coro, timeout=None):
            if timeout == _sentinel:
                if main.asyncio.iscoroutine(coro):
                    coro.close()  # avoid an un-awaited-coroutine RuntimeWarning (promoted to error)
                raise main.asyncio.TimeoutError
            return await _real_wait_for(coro, timeout=timeout)

        monkeypatch.setattr(main.asyncio, "wait_for", _wait_for)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/control", _skip_csrf=True) as ws:
                # The handler emits a ``connection_established`` frame before the CSRF
                # auth check, so the 1008 close surfaces on the *second* receive. The
                # close is immediate (patched, no timer), so the disconnect is raised
                # deterministically on that receive; the loop is just an upper bound.
                for _ in range(5):
                    ws.receive_json(timeout=5.0)
        assert exc_info.value.code == 1008


# =============================================================================
# GET /api/csrf — CSRF disabled branch (line 519)
# =============================================================================
class TestCsrfEndpointDisabled:
    def test_returns_empty_token_when_disabled(self, client, monkeypatch):
        monkeypatch.setattr(main.settings, "csrf_enabled", False)
        resp = client.get("/api/csrf")
        assert resp.status_code == 200
        assert resp.json() == {"csrf_token": "", "enabled": False}


# =============================================================================
# _classify_import_url_target — unresolvable host (line 1379)
# =============================================================================
class TestClassifyImportUrlTarget:
    def test_empty_resolution_is_rejected(self):
        with patch.object(main.socket, "getaddrinfo", return_value=[]):
            reason = main._classify_import_url_target("http://example.test/data.csv")
        assert reason is not None
        assert "Could not resolve host" in reason


# =============================================================================
# POST /api/dataset/import-url — branches (1406, 1413, 1429-1430, 1454-1457,
# 1461-1462, 1467-1472)
# =============================================================================
class _FakeStreamResp:
    def __init__(self, status_code=200, chunks=(b"0.1,0.2,0\n",)):
        self.status_code = status_code
        self._chunks = chunks

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamCM:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *args):
        return False


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    def stream(self, method, url):
        return _FakeStreamCM(self._resp)


class _FakeClientCM:
    def __init__(self, resp=None, raise_on_enter=None):
        self._resp = resp
        self._raise = raise_on_enter

    async def __aenter__(self):
        if self._raise is not None:
            raise self._raise
        return _FakeClient(self._resp)

    async def __aexit__(self, *args):
        return False


class TestImportDatasetUrl:
    def _install(self, mock):
        original = main.backend
        main.backend = mock
        return original

    @pytest.mark.asyncio
    async def test_non_demo_backend_rejected_400(self):
        backend = MagicMock()
        backend.backend_type = "service"
        original = self._install(backend)
        try:
            result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_backend_without_import_returns_501(self, monkeypatch):
        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        backend = MagicMock()
        backend.backend_type = "demo"
        del backend.import_dataset
        original = self._install(backend)
        try:
            result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 501

    @pytest.mark.asyncio
    async def test_httpx_missing_returns_501(self, monkeypatch):
        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        monkeypatch.setattr(main, "_classify_import_url_target", lambda url: None)
        backend = MagicMock()
        backend.backend_type = "demo"
        original = self._install(backend)
        try:
            with patch.dict(sys.modules, {"httpx": None}):
                result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 501

    @pytest.mark.asyncio
    async def test_fetch_timeout_returns_504(self, monkeypatch):
        import httpx

        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        monkeypatch.setattr(main, "_classify_import_url_target", lambda url: None)
        backend = MagicMock()
        backend.backend_type = "demo"
        original = self._install(backend)
        try:
            with patch("httpx.AsyncClient", return_value=_FakeClientCM(raise_on_enter=httpx.TimeoutException("slow"))):
                result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 504

    @pytest.mark.asyncio
    async def test_fetch_http_error_returns_400(self, monkeypatch):
        import httpx

        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        monkeypatch.setattr(main, "_classify_import_url_target", lambda url: None)
        backend = MagicMock()
        backend.backend_type = "demo"
        original = self._install(backend)
        try:
            with patch("httpx.AsyncClient", return_value=_FakeClientCM(raise_on_enter=httpx.HTTPError("bad"))):
                result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_parse_error_returns_400(self, monkeypatch):
        import dataset_import

        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        monkeypatch.setattr(main, "_classify_import_url_target", lambda url: None)

        def _raise(_raw):
            raise dataset_import.DatasetImportError("bad csv")

        monkeypatch.setattr(dataset_import, "parse_csv_bytes", _raise)
        backend = MagicMock()
        backend.backend_type = "demo"
        original = self._install(backend)
        try:
            with patch("httpx.AsyncClient", return_value=_FakeClientCM(resp=_FakeStreamResp())):
                result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_import_value_error_returns_400(self, monkeypatch):
        import dataset_import

        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        monkeypatch.setattr(main, "_classify_import_url_target", lambda url: None)
        monkeypatch.setattr(dataset_import, "parse_csv_bytes", lambda _raw: ([[1.0, 2.0]], [0]))
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.import_dataset.side_effect = ValueError("shape mismatch")
        original = self._install(backend)
        try:
            with patch("httpx.AsyncClient", return_value=_FakeClientCM(resp=_FakeStreamResp())):
                result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_import_unexpected_error_returns_500(self, monkeypatch):
        import dataset_import

        monkeypatch.setattr(main.settings, "dataset_import_url_enabled", True)
        monkeypatch.setattr(main, "_classify_import_url_target", lambda url: None)
        monkeypatch.setattr(dataset_import, "parse_csv_bytes", lambda _raw: ([[1.0, 2.0]], [0]))
        backend = MagicMock()
        backend.backend_type = "demo"
        backend.import_dataset.side_effect = RuntimeError("boom")
        original = self._install(backend)
        try:
            with patch("httpx.AsyncClient", return_value=_FakeClientCM(resp=_FakeStreamResp())):
                result = await main.import_dataset_url(main._ImportUrlRequest(url="http://x.test/d.csv"))
        finally:
            main.backend = original
        assert result.status_code == 500


# =============================================================================
# GET /api/dataset/generators (1482, 1485-1497, 1502-1503, 1513)
# =============================================================================
class _FakeGetResp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _FakeGetClient:
    def __init__(self, payload):
        self._payload = payload

    async def get(self, url):
        return _FakeGetResp(self._payload)


class _FakeGetClientCM:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return _FakeGetClient(self._payload)

    async def __aexit__(self, *args):
        return False


class TestListDatasetGenerators:
    @pytest.mark.asyncio
    async def test_data_service_returns_list(self, monkeypatch):
        monkeypatch.setattr(main, "juniper_data_available", True)
        with patch("httpx.AsyncClient", return_value=_FakeGetClientCM([{"name": "spiral"}, {"name": "xor"}])):
            result = await main.list_dataset_generators()
        assert result == {"generators": [{"name": "spiral"}, {"name": "xor"}]}

    @pytest.mark.asyncio
    async def test_data_service_returns_dict_with_generators(self, monkeypatch):
        monkeypatch.setattr(main, "juniper_data_available", True)
        payload = {"generators": [{"name": "moon"}]}
        with patch("httpx.AsyncClient", return_value=_FakeGetClientCM(payload)):
            result = await main.list_dataset_generators()
        assert result == {"generators": [{"name": "moon"}]}

    @pytest.mark.asyncio
    async def test_fallback_builtin_generators(self, monkeypatch):
        monkeypatch.setattr(main, "juniper_data_available", False)
        result = await main.list_dataset_generators()
        names = {g["name"] for g in result["generators"]}
        assert {"spiral", "xor", "circles", "moon"} <= names


# =============================================================================
# Application lifespan startup/shutdown branches (250-251, 256-257, 270-271,
# 279-289, 327)
# =============================================================================
def _probe(status, latency=1.0, message="ok"):
    return SimpleNamespace(status=status, latency_ms=latency, message=message)


def _service_backend():
    b = MagicMock()
    b.backend_type = "service"
    b.initialize = AsyncMock(return_value=True)
    b.shutdown = AsyncMock()
    b.get_synced_state = MagicMock(return_value=None)
    b.get_status = MagicMock(return_value={})
    return b


def _demo_backend():
    b = MagicMock()
    b.backend_type = "demo"
    b.initialize = AsyncMock(return_value=True)
    b.shutdown = AsyncMock()
    b._demo.training_state = None
    b.get_status = MagicMock(return_value={})
    return b


class TestLifespanBranches:
    def _common_patches(self, monkeypatch):
        import juniper_service_core as jsc

        import backend as backend_mod
        import discovery as discovery_mod

        monkeypatch.setattr(jsc, "enforce_dependency_floors", lambda **k: None)
        monkeypatch.setattr(main, "configure_logging", lambda *a, **k: None)
        monkeypatch.setattr(main, "configure_sentry", lambda *a, **k: None)
        monkeypatch.setattr(main, "set_demo_mode_active", lambda *a, **k: None)
        monkeypatch.setattr(main.websocket_manager, "set_event_loop", MagicMock())
        monkeypatch.setattr(main.websocket_manager, "shutdown", AsyncMock())
        monkeypatch.setattr(main.websocket_manager, "heartbeat_interval", 0)
        return backend_mod, discovery_mod

    def _save_globals(self):
        return (main.backend, main.juniper_data_available, main._resolved_service_url, main.loop_holder.get("loop"))

    def _restore_globals(self, saved):
        main.backend, main.juniper_data_available, main._resolved_service_url, loop = saved
        main.loop_holder["loop"] = loop

    @pytest.mark.asyncio
    async def test_discovery_data_healthy_keepalive_disabled(self, monkeypatch):
        backend_mod, discovery_mod = self._common_patches(monkeypatch)
        svc = _service_backend()
        monkeypatch.setattr(main.settings, "demo_mode", False)
        monkeypatch.setattr(main.settings, "cascor_service_url", None)
        monkeypatch.setattr(main.settings.cascor_discovery, "enabled", True)
        monkeypatch.setattr(main, "probe_dependency", AsyncMock(return_value=_probe("healthy")))
        monkeypatch.setattr(discovery_mod, "discover_cascor", AsyncMock(return_value="http://found:8200"))
        monkeypatch.setattr(backend_mod, "create_backend", MagicMock(return_value=svc))

        saved = self._save_globals()
        try:
            async with main.lifespan(main.app):
                assert main.juniper_data_available is True
                assert main.backend is svc
                assert main._resolved_service_url == "http://found:8200"
        finally:
            self._restore_globals(saved)

    @pytest.mark.asyncio
    async def test_configured_cascor_healthy(self, monkeypatch):
        backend_mod, discovery_mod = self._common_patches(monkeypatch)
        svc = _service_backend()
        monkeypatch.setattr(main.settings, "demo_mode", False)
        monkeypatch.setattr(main.settings, "cascor_service_url", "http://cascor:8200")
        monkeypatch.setattr(discovery_mod, "discover_cascor", AsyncMock(return_value=None))
        monkeypatch.setattr(main, "probe_dependency", AsyncMock(side_effect=[_probe("healthy"), _probe("healthy")]))
        monkeypatch.setattr(backend_mod, "create_backend", MagicMock(return_value=svc))

        saved = self._save_globals()
        try:
            async with main.lifespan(main.app):
                # cascor reachable -> no fallback, backend stays the service mock.
                assert main.backend is svc
                svc.shutdown.assert_not_called()
        finally:
            self._restore_globals(saved)

    @pytest.mark.asyncio
    async def test_configured_cascor_unreachable_falls_back_to_demo(self, monkeypatch):
        backend_mod, discovery_mod = self._common_patches(monkeypatch)
        svc = _service_backend()
        demo = _demo_backend()
        monkeypatch.setattr(main.settings, "demo_mode", False)
        monkeypatch.setattr(main.settings, "cascor_service_url", "http://cascor:8200")
        monkeypatch.setattr(discovery_mod, "discover_cascor", AsyncMock(return_value=None))
        monkeypatch.setattr(main, "probe_dependency", AsyncMock(side_effect=[_probe("healthy"), _probe("unhealthy", message="refused")]))
        monkeypatch.setattr(backend_mod, "create_backend", MagicMock(side_effect=[svc, demo]))

        saved = self._save_globals()
        try:
            async with main.lifespan(main.app):
                # cascor unreachable -> the service backend is shut down and
                # a demo backend replaces it.
                assert main.backend is demo
                svc.shutdown.assert_awaited_once()
                demo.initialize.assert_awaited_once()
                assert main._resolved_service_url is None
        finally:
            self._restore_globals(saved)
