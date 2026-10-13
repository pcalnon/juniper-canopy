"""N3 (canopy training-runtime defects plan, I-6) — the /api/train/restart route.

Regression for the cold-swap restart orchestration that replaced the pre-N3
feedback-free ``POST /api/train/start?reset=true`` callback (three cold-swaps
trained to completion invisibly in the 2026-07-11 incident).

Two layers:

* Integration (``client`` fixture, demo mode) — the happy path end-to-end:
  staging → restart clears ``pending_dataset``; the structured per-step result;
  the ``start_fresh`` toggle rides through to the response.
* Async-unit (``main.api_train_restart`` awaited with a mocked ``main.backend``)
  — the branches the demo backend can't force deterministically: an ACTIVE run is
  stopped + awaited before start (E-2 pin), a stop-await timeout returns a
  retriable 504 with the staged change intact, stop/start refusals surface the
  upstream detail, and the instant-convergence peek (folded finding 2).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Integration — real demo backend via the TestClient
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_restart_route_clears_pending_and_reports_steps(client):
    """Stage a dataset, restart, and assert pending clears + a truthful result."""
    # Start from a known-idle state so the assertion is deterministic.
    client.post("/api/train/stop")

    staged = client.post("/api/stage_dataset", json={"nn_dataset_type": "xor", "nn_dataset_elements": 300})
    assert staged.status_code == 200, staged.text
    assert client.get("/api/status").json().get("pending_dataset"), "precondition: pending_dataset set after staging"

    restarted = client.post("/api/train/restart", json={})
    assert restarted.status_code == 200, restarted.text
    body = restarted.json()
    assert body["success"] is True
    assert body["status"] == "restarted"
    # The start step always runs; its outcome is surfaced (no silent paths).
    assert any(s["step"] == "start" and s["ok"] for s in body["steps"]), body["steps"]

    # Cold-swap consumed the staged config → the banner-reconcile signal clears.
    assert client.get("/api/status").json().get("pending_dataset") is None, "pending_dataset must clear after a successful restart"

    client.post("/api/train/stop")


@pytest.mark.integration
def test_restart_route_forwards_start_fresh_flag(client):
    """The start-fresh toggle rides through to the structured result."""
    client.post("/api/train/stop")
    client.post("/api/stage_dataset", json={"nn_dataset_type": "circles", "nn_dataset_elements": 200})

    restarted = client.post("/api/train/restart", json={"start_fresh": True})
    assert restarted.status_code == 200, restarted.text
    body = restarted.json()
    assert body["success"] is True
    assert body["start_fresh"] is True

    client.post("/api/train/stop")


# ---------------------------------------------------------------------------
# Async-unit — awaited route with a mocked backend
# ---------------------------------------------------------------------------


def _decode(result):
    """Return (status_code, payload) for either a dict or a JSONResponse."""
    if isinstance(result, dict):
        return 200, result
    return result.status_code, json.loads(result.body)


class _RestartBackendHarness:
    """Patch ``main.backend`` + silence the broadcast machinery for a test body."""

    def __init__(self, backend):
        self.backend = backend

    def __enter__(self):
        import main

        self._main = main
        self._orig_backend = main.backend
        main.backend = self.backend
        self._bcast = patch.object(main, "schedule_broadcast", MagicMock())
        self._bcast.start()
        return self

    def __exit__(self, *exc):
        self._bcast.stop()
        self._main.backend = self._orig_backend
        return False


@pytest.mark.asyncio
async def test_restart_idle_skips_stop_and_starts():
    """An idle backend goes straight to start — no stop/await steps."""
    import main

    backend = MagicMock()
    backend.is_training_active.return_value = False
    backend.start_training.return_value = {"ok": True, "is_training": True}
    backend.get_status.return_value = {"is_running": True, "current_epoch": 3}

    with _RestartBackendHarness(backend):
        status, payload = _decode(await main.api_train_restart(body=main._TrainRestartBody(start_fresh=False)))

    assert status == 200
    assert payload["success"] is True
    assert payload["was_active"] is False
    steps = [s["step"] for s in payload["steps"]]
    assert steps == ["start"], steps
    backend.stop_training.assert_not_called()
    backend.start_training.assert_called_once_with(reset=True, start_fresh=False)


@pytest.mark.asyncio
async def test_restart_active_stops_awaits_then_starts():
    """E-2 pin: an ACTIVE run is stopped and awaited before start."""
    import main

    backend = MagicMock()
    # active on the pre-check, still active once (await loop), then stopped.
    backend.is_training_active.side_effect = [True, True, False]
    backend.stop_training.return_value = {"ok": True}
    backend.start_training.return_value = {"ok": True, "is_training": True}
    backend.get_status.return_value = {"is_running": True, "current_epoch": 1}

    with _RestartBackendHarness(backend):
        status, payload = _decode(await main.api_train_restart(body=main._TrainRestartBody(start_fresh=True)))

    assert status == 200
    assert payload["success"] is True
    assert payload["was_active"] is True
    steps = [s["step"] for s in payload["steps"]]
    assert steps == ["stop", "await_stopped", "start"], steps
    backend.stop_training.assert_called_once()
    backend.start_training.assert_called_once_with(reset=True, start_fresh=True)


@pytest.mark.asyncio
async def test_restart_stop_await_timeout_is_retriable_504(monkeypatch):
    """A stop-await timeout returns a retriable 504 and does NOT start."""
    import main

    monkeypatch.setattr(main.BackendConstants, "RESTART_STOP_WAIT_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(main.BackendConstants, "RESTART_STOP_WAIT_POLL_SECONDS", 0.05)

    backend = MagicMock()
    backend.is_training_active.return_value = True  # never settles
    backend.stop_training.return_value = {"ok": True}

    with _RestartBackendHarness(backend):
        status, payload = _decode(await main.api_train_restart(body=main._TrainRestartBody()))

    assert status == 504
    assert payload["success"] is False
    assert payload["retriable"] is True
    assert [s["step"] for s in payload["steps"]] == ["stop", "await_stopped"]
    backend.start_training.assert_not_called()  # staged change survives — no start


@pytest.mark.asyncio
async def test_restart_start_refusal_surfaces_detail_409():
    """A start refusal surfaces the upstream detail and reports failure (T1)."""
    import main

    backend = MagicMock()
    backend.is_training_active.return_value = False
    backend.start_training.return_value = {"ok": False, "error": "Training data not provided"}

    with _RestartBackendHarness(backend):
        status, payload = _decode(await main.api_train_restart(body=main._TrainRestartBody()))

    assert status == 409
    assert payload["success"] is False
    assert "Training data not provided" in payload["message"]
    assert payload["steps"][-1] == {"step": "start", "ok": False, "detail": "Training data not provided"}


@pytest.mark.asyncio
async def test_restart_stop_refusal_surfaces_detail_409():
    """A stop refusal short-circuits with the upstream detail; no start attempted."""
    import main

    backend = MagicMock()
    backend.is_training_active.return_value = True
    backend.stop_training.return_value = {"ok": False, "error": "cascor unreachable"}

    with _RestartBackendHarness(backend):
        status, payload = _decode(await main.api_train_restart(body=main._TrainRestartBody()))

    assert status == 409
    assert payload["success"] is False
    assert "cascor unreachable" in payload["message"]
    backend.start_training.assert_not_called()


@pytest.mark.asyncio
async def test_restart_reports_instant_convergence(monkeypatch):
    """Folded finding 2: an instantly-completed run is reported truthfully."""
    import main

    monkeypatch.setattr(main.BackendConstants, "RESTART_INSTANT_COMPLETE_PEEK_SECONDS", 0.2)
    monkeypatch.setattr(main.BackendConstants, "RESTART_STOP_WAIT_POLL_SECONDS", 0.05)

    backend = MagicMock()
    backend.is_training_active.return_value = False
    backend.start_training.return_value = {"ok": True, "is_training": True}
    # Already terminal by the time we peek (epoch-0 convergence).
    backend.get_status.return_value = {"completed": True, "current_epoch": 0}

    with _RestartBackendHarness(backend):
        status, payload = _decode(await main.api_train_restart(body=main._TrainRestartBody(start_fresh=True)))

    assert status == 200
    assert payload["success"] is True
    assert payload["instant_complete"] is True


@pytest.mark.asyncio
async def test_await_training_stopped_helper(monkeypatch):
    """The bounded stop-wait returns True once idle, False on timeout."""
    import main

    backend = MagicMock()
    with _RestartBackendHarness(backend):
        backend.is_training_active.side_effect = [True, True, False]
        assert await main._await_training_stopped(timeout_s=1.0, poll=0.01) is True

        backend.is_training_active.side_effect = None
        backend.is_training_active.return_value = True
        assert await main._await_training_stopped(timeout_s=0.15, poll=0.05) is False
