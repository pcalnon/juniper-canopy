#!/usr/bin/env python
"""
Integration tests — control-command failure propagation (2026-07-09 PR-A).

A backend ``ControlResult`` with ``ok=False`` must surface as a *failure* at
both transport layers:

- REST ``/api/train/*`` → HTTP **409** with the backend error in ``detail``
  (previously: HTTP 200 ``{"status": "started", "ok": false, ...}`` plus a
  "Training started successfully" broadcast).
- ``/ws/control`` command dispatch → ``command_response`` **error** envelope
  (``data.status == "error"``, legacy top-level ``ok: false``) so the Phase D
  clientside ``send()`` promise rejects and the §S10 danger alert fires
  (previously: a success envelope wrapping the failed result — the "dead
  button" class).

Absent-``ok`` results (demo-state dicts) keep the legacy success
interpretation — pinned here so demo mode cannot regress.

Diagnosis: juniper-ml
``notes/JUNIPER_2026-07-09_JUNIPER-ECOSYSTEM_TRAINING-START-FAILURE-DIAGNOSIS-AND-FIX-PLAN.md`` §4.2.
"""

import pytest
from fastapi.testclient import TestClient

import main
from backend.protocol import ControlResult

pytestmark = [pytest.mark.integration, pytest.mark.api]

_ERROR = "No network created"


class _FailingBackend:
    """Stub backend whose every control method reports ``ok=False``.

    Mirrors what ``ServiceBackend`` returns against a fresh cascor with no
    network (service_backend.py start_training guard).
    """

    backend_type = "service"
    execution = "live"

    def start_training(self, reset=True, **kwargs):
        return ControlResult(ok=False, error=_ERROR)

    def stop_training(self):
        return ControlResult(ok=False, error=_ERROR)

    def pause_training(self):
        return ControlResult(ok=False, error=_ERROR)

    def resume_training(self):
        return ControlResult(ok=False, error=_ERROR)

    def reset_training(self):
        return ControlResult(ok=False, error=_ERROR)

    def apply_params(self, **params):
        return {"ok": False, "error": _ERROR}

    def is_training_active(self):
        return False

    def get_status(self):
        return {"is_training": False, "is_running": False}


class _LegacyShapeBackend(_FailingBackend):
    """Demo-shape control results: no ``ok`` key at all — must stay a success."""

    def start_training(self, reset=True, **kwargs):
        return {"is_running": True, "current_epoch": 0}

    def stop_training(self):
        return {"is_running": False}

    def reset_training(self):
        return {"is_running": False, "current_epoch": 0}


@pytest.fixture(scope="module")
def client():
    """One app + lifespan for the module (lifespan seeds the default demo backend)."""
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def failing_backend(monkeypatch):
    """Swap the module-global backend for the ok=False stub (auto-restored)."""
    fb = _FailingBackend()
    monkeypatch.setattr(main, "backend", fb)
    return fb


class TestRestFailurePropagation:
    """REST ``/api/train/*`` must not report a failed control result as success."""

    @pytest.mark.parametrize(
        "route",
        [
            "/api/train/start",
            "/api/train/pause",
            "/api/train/resume",
            "/api/train/stop",
            "/api/train/reset",
        ],
    )
    def test_ok_false_returns_409_with_backend_error(self, client, failing_backend, route):
        resp = client.post(route)
        assert resp.status_code == 409
        assert _ERROR in resp.json()["detail"]

    def test_start_ok_false_does_not_claim_started(self, client, failing_backend):
        # The pre-fix body was {"status": "started", "ok": false, ...} with HTTP 200.
        resp = client.post("/api/train/start")
        assert resp.status_code == 409
        assert "started" not in resp.json().get("status", "")

    def test_absent_ok_stays_success_for_legacy_shapes(self, client, monkeypatch):
        # Demo-state dicts carry no ``ok`` key; they must keep returning 200.
        monkeypatch.setattr(main, "backend", _LegacyShapeBackend())
        resp = client.post("/api/train/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"


class TestWsControlFailurePropagation:
    """``/ws/control`` must answer a failed command with an error envelope."""

    def _receive_command_response(self, websocket, timeout_messages=100):
        for _ in range(timeout_messages):
            msg = websocket.receive_json()
            if msg.get("type") == "command_response":
                return msg
        raise TimeoutError(f"No command_response within {timeout_messages} messages")

    def test_start_failure_gets_error_envelope(self, client, failing_backend):
        with client.websocket_connect("/ws/control") as websocket:
            conn_msg = websocket.receive_json()
            assert conn_msg.get("type") == "connection_established"

            websocket.send_json({"command": "start", "command_id": "prfx-cid-1", "reset": True})
            response = self._receive_command_response(websocket)

            # Envelope semantics the Phase D clientside depends on: status
            # "error" rejects the send() promise (websocket_client.js), which
            # routes into the REST fallback + §S10 danger alert.
            assert response["data"]["status"] == "error"
            assert response["data"]["command_id"] == "prfx-cid-1"
            assert _ERROR in response["data"]["error"]
            assert response["data"]["code"] == "command_failed"
            # Legacy compat fields mirror the failure.
            assert response["ok"] is False
            assert _ERROR in response["error"]

    def test_start_failure_keeps_result_payload_for_diagnostics(self, client, failing_backend):
        with client.websocket_connect("/ws/control") as websocket:
            assert websocket.receive_json().get("type") == "connection_established"

            websocket.send_json({"command": "start", "command_id": "prfx-cid-2", "reset": True})
            response = self._receive_command_response(websocket)

            # The failed ControlResult still rides along under data.result so
            # clients/tests can inspect the backend's own fields.
            assert response["data"]["result"] == {"ok": False, "error": _ERROR}
