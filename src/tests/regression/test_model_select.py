#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_model_select.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-24
# Last Modified: 2026-06-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1-iv-2 runtime backend-swap regression tests: POST
#                /api/model/select re-creates the process-global backend
#                for a newly selected model (no-op on unchanged type,
#                refuses mid-training, atomic create-before-teardown).
#####################################################################
"""Regression tests for the A1-iv-2 runtime model swap (juniper-canopy #368).

Exercises ``main._swap_backend`` + ``POST /api/model/select`` with controllable fake backends
(no network): the new backend is created + initialized BEFORE the global is reassigned and the
old one is shut down only AFTER; an unchanged target type is a no-op; an in-flight fit is
refused (409); a failed ``initialize()`` leaves the current backend intact (502); and the
shared ``_seed_training_state`` helper handles every backend type.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import backend as backend_pkg
import main


class _FakeBackend:
    """Controllable BackendProtocol stand-in for the swap mechanism (no network)."""

    def __init__(self, backend_type="demo", execution="live", *, training_active=False, init_ok=True):
        self.backend_type = backend_type
        self.execution = execution
        self._training_active = training_active
        self._init_ok = init_ok
        self.initialized = False
        self.shutdown_called = False

    def is_training_active(self):
        return self._training_active

    async def initialize(self):
        self.initialized = True
        return self._init_ok

    async def shutdown(self):
        self.shutdown_called = True

    def get_status(self):
        return {"fsm_status": "idle", "phase": "idle"}

    def get_synced_state(self):
        return None

    def set_state_update_callback(self, callback):
        pass


@pytest.fixture(scope="module")
def client():
    """One app + lifespan for the module (the lifespan seeds the default demo backend)."""
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def swap_env(monkeypatch):
    """Isolate the swap globals so each test's mutations are auto-restored.

    Defaults selections to 'targets recurrence' so a swap fires from a non-recurrence current
    backend; individual tests override ``main.backend`` / ``backend_pkg.create_backend`` as
    needed.
    """
    monkeypatch.setattr(main, "current_nn_model", None)
    monkeypatch.setattr(main, "_resolved_service_url", None)
    monkeypatch.setattr(main, "_selection_targets_recurrence", lambda nn_model: True)


# --------------------------------------------------------------------------- pure helpers


@pytest.mark.regression
@pytest.mark.unit
def test_selection_targets_recurrence_requires_provider_and_url(monkeypatch):
    monkeypatch.setattr(main, "settings", SimpleNamespace(recurrence_service_url="http://rec.test:8210"))
    assert main._selection_targets_recurrence("recurrence") is True
    # cascor is not a recurrence-provider model.
    assert main._selection_targets_recurrence("cascor") is False
    # unknown key -> no spec -> False.
    assert main._selection_targets_recurrence("does-not-exist") is False
    # recurrence model but no configured URL -> not selectable as recurrence.
    monkeypatch.setattr(main, "settings", SimpleNamespace(recurrence_service_url=None))
    assert main._selection_targets_recurrence("recurrence") is False


@pytest.mark.regression
@pytest.mark.unit
def test_seed_training_state_handles_every_backend_type():
    # Must not raise for any backend_type (the shared startup/swap seeder).
    for backend_type in ("demo", "service", "recurrence", "unknown"):
        main._seed_training_state(_FakeBackend(backend_type=backend_type))


@pytest.mark.regression
@pytest.mark.unit
def test_model_state_response_unknown_model_status(monkeypatch):
    monkeypatch.setattr(main, "backend", _FakeBackend(backend_type="demo"))
    response = main._model_state_response("not-a-model", swapped=False)
    assert response == {"nn_model": "not-a-model", "backend": "demo", "execution": "live", "status": "unknown", "swapped": False}


# --------------------------------------------------------------------------- swap route


@pytest.mark.regression
def test_select_swaps_default_to_recurrence(client, swap_env, monkeypatch):
    current = _FakeBackend(backend_type="demo")
    new_backend = _FakeBackend(backend_type="recurrence", execution="one_shot")
    monkeypatch.setattr(main, "backend", current)
    monkeypatch.setattr(backend_pkg, "create_backend", lambda **kwargs: new_backend)

    response = client.post("/api/model/select", json={"nn_model": "recurrence"})

    assert response.status_code == 200
    body = response.json()
    assert body["nn_model"] == "recurrence"
    assert body["backend"] == "recurrence"
    assert body["execution"] == "one_shot"
    assert body["status"] == "coming_soon"  # real registry status
    assert body["swapped"] is True
    # New backend installed + initialized; old one torn down; selection recorded.
    assert main.backend is new_backend
    assert new_backend.initialized is True
    assert current.shutdown_called is True
    assert main.current_nn_model == "recurrence"


@pytest.mark.regression
def test_select_is_noop_when_target_type_unchanged(client, swap_env, monkeypatch):
    current = _FakeBackend(backend_type="recurrence", execution="one_shot")
    monkeypatch.setattr(main, "backend", current)
    # swap_env makes the selection target recurrence AND the backend is already recurrence.

    response = client.post("/api/model/select", json={"nn_model": "recurrence"})

    assert response.status_code == 200
    body = response.json()
    assert body["swapped"] is False
    assert main.backend is current  # untouched
    assert current.shutdown_called is False  # NOT torn down
    assert main.current_nn_model == "recurrence"


@pytest.mark.regression
def test_select_refused_while_training_active(client, swap_env, monkeypatch):
    current = _FakeBackend(backend_type="demo", training_active=True)
    monkeypatch.setattr(main, "backend", current)
    monkeypatch.setattr(backend_pkg, "create_backend", lambda **kwargs: _FakeBackend(backend_type="recurrence"))

    response = client.post("/api/model/select", json={"nn_model": "recurrence"})

    assert response.status_code == 409
    assert "training" in response.json()["detail"].lower()
    assert main.backend is current  # not swapped
    assert current.shutdown_called is False


@pytest.mark.regression
def test_select_init_failure_leaves_current_backend(client, swap_env, monkeypatch):
    current = _FakeBackend(backend_type="demo")
    failing = _FakeBackend(backend_type="recurrence", init_ok=False)
    monkeypatch.setattr(main, "backend", current)
    monkeypatch.setattr(backend_pkg, "create_backend", lambda **kwargs: failing)

    response = client.post("/api/model/select", json={"nn_model": "recurrence"})

    assert response.status_code == 502
    assert main.backend is current  # current backend untouched
    assert current.shutdown_called is False  # old NOT torn down
    assert failing.shutdown_called is True  # failed new one cleaned up


@pytest.mark.regression
def test_select_unknown_model_returns_422(client, monkeypatch):
    current = _FakeBackend(backend_type="demo")
    monkeypatch.setattr(main, "backend", current)

    response = client.post("/api/model/select", json={"nn_model": "does-not-exist"})

    assert response.status_code == 422
    assert "Unknown model" in response.json()["detail"]
    assert main.backend is current  # untouched
