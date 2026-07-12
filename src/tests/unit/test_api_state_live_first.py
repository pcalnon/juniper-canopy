"""N2 (training-runtime defects plan §4 I-1): /api/state live-first base fields + /api/stream_health.

The 2026-07-10 incident: in service mode, /api/state served base fields
(status/phase/current_epoch/timestamp) solely from the relay-fed in-process
``training_state`` global — which went ~8 hours stale when the WS relay
silently died — while ALREADY making a live cascor call per GET for the
parameter keys. The route now derives base fields from a consolidated live
``backend.get_status()`` fetch in the same off-loop thread hop, and falls back
to the global ONLY on upstream error, marked ``stale: true`` with an age.

Also covers the new GET /api/stream_health route feeding the degraded-mode
badge dimension.
"""

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _restore_training_state():
    """These tests poison the module-global ``training_state``; restore it after each."""
    snapshot = main.training_state.get_state()
    yield
    main.training_state.update_state(**snapshot)


class _FakeServiceBackend:
    """Minimal service-mode backend for the /api/state + /api/stream_health routes."""

    backend_type = "service"

    def __init__(self, status=None, params=None, stream_health=None):
        self._status = status if status is not None else {}
        self._adapter = SimpleNamespace(
            get_canopy_params=lambda: dict(params or {}),
            get_stream_health=lambda: stream_health or {"overall": "healthy", "relay": {}, "control": {}},
        )

    def get_status(self):
        return self._status


_LIVE_RUNNING_STATUS = {
    "is_training": True,
    "is_running": True,
    "is_paused": False,
    "completed": False,
    "failed": False,
    "fsm_status": "RUNNING",
    "phase": "output",
    "current_epoch": 42,
    "hidden_units": 3,
    "max_epochs": 1000,
}


@pytest.mark.unit
class TestApiStateLiveFirst:
    def test_base_fields_come_from_live_fetch(self, client, monkeypatch):
        """While cascor is reachable, status/phase/current_epoch/timestamp are live."""
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(status=dict(_LIVE_RUNNING_STATUS), params={"nn_learning_rate": 0.05}))
        # Poison the global with stale values the live fetch must override.
        main.training_state.update_state(status="Stopped", phase="Idle", current_epoch=0, timestamp=time.time() - 3600.0)

        before = time.time()
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "Started"
        assert data["phase"] == "output"
        assert data["current_epoch"] == 42
        assert data["stale"] is False
        assert data["timestamp"] >= before - 1.0  # fresh, not the hour-old global
        assert data["nn_learning_rate"] == 0.05  # params ride the same live posture

    def test_completed_status_maps_from_live_booleans(self, client, monkeypatch):
        status = dict(_LIVE_RUNNING_STATUS, is_training=False, is_running=False, completed=True, fsm_status="CONVERGED", current_epoch=99)
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(status=status))
        data = client.get("/api/state").json()
        assert data["status"] == "Completed"
        assert data["current_epoch"] == 99
        assert data["stale"] is False

    def test_failed_and_paused_statuses_map(self, client, monkeypatch):
        failed = dict(_LIVE_RUNNING_STATUS, is_running=False, is_training=False, failed=True)
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(status=failed))
        assert client.get("/api/state").json()["status"] == "Failed"

        paused = dict(_LIVE_RUNNING_STATUS, is_running=False, is_training=False, is_paused=True)
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(status=paused))
        assert client.get("/api/state").json()["status"] == "Paused"

    def test_upstream_error_falls_back_to_global_with_stale_marker(self, client, monkeypatch):
        """On upstream error the route serves the relay-fed global, honestly
        marked stale with an age — never silently-stale (the 8-hour class)."""
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(status={"is_training": False, "error": "circuit open"}))
        stale_ts = time.time() - 120.0
        main.training_state.update_state(status="Started", phase="Output", current_epoch=7, timestamp=stale_ts)

        data = client.get("/api/state").json()

        assert data["stale"] is True
        assert data["stale_age_seconds"] == pytest.approx(120.0, abs=10.0)
        # Base fields are the last-known global values.
        assert data["status"] == "Started"
        assert data["current_epoch"] == 7
        assert data["timestamp"] == pytest.approx(stale_ts, abs=1.0)

    def test_status_result_without_fsm_status_is_treated_as_error(self, client, monkeypatch):
        """A malformed / non-nested upstream payload must not be trusted for base fields."""
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(status={"is_training": False}))
        data = client.get("/api/state").json()
        assert data["stale"] is True

    def test_demo_mode_state_has_no_stale_marker(self, client):
        """Demo mode path is untouched by the live-first change (no upstream)."""
        data = client.get("/api/state").json()
        assert "stale" not in data


@pytest.mark.unit
class TestApiStreamHealth:
    def test_service_mode_passthrough(self, client, monkeypatch):
        payload = {
            "overall": "degraded",
            "relay": {"status": "degraded", "connected": True},
            "control": {"status": "reconnecting", "enabled": True},
        }
        monkeypatch.setattr(main, "backend", _FakeServiceBackend(stream_health=payload))
        response = client.get("/api/stream_health")
        assert response.status_code == 200
        assert response.json() == payload

    def test_non_service_mode_is_not_applicable(self, client):
        """Demo/recurrence backends have no upstream stream — overall n/a."""
        response = client.get("/api/stream_health")
        assert response.status_code == 200
        data = response.json()
        assert data["overall"] == "n/a"
        assert data["relay"] is None
        assert data["control"] is None
