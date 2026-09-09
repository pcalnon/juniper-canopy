#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_staging.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   X6 / design §4.9 -- the (recurrence, equities_seq) pair
#                can be STAGED: RecurrenceBackend stages in-process and
#                the next fit consumes it; staging toward a backend the
#                selection does not target is refused (N5), so cascor's
#                by-design refusal of a rank-3 artifact is never reached.
#####################################################################
"""Staging the pair (X6 / design §4.9), and why neither half of it is cross-repo.

Design of record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md`` §4.9.
Handoff ``HANDOFF_2026-09-07_canopy-selection-deadlock-fixed-generator-gap-open.md`` item 2 filed
both branches as cross-repo work -- ``equities_seq`` into cascor's ``Literal``, and a staging
endpoint on juniper-recurrence. Both premises were wrong, and this module pins the corrections:

* cascor refuses 3-D artifacts **by design** at the tier boundary (``api/lifecycle/manager.py``,
  W-2). The only way canopy sent one there was the inactive-selection state N5 names, and
  ``/api/stage_dataset`` now refuses that state before anything leaves canopy.
* the recurrence service is one-shot -- the dataset reference travels in ``POST /v1/train`` -- so
  "staged for the next start" is a canopy-side fact, exactly as ``DemoMode`` already holds it.
  ``RecurrenceBackend`` stages in-process and ``start_training`` consumes it.
"""

import time
from unittest import mock

import pytest
from fastapi.testclient import TestClient

import main
from backend.recurrence_backend import RecurrenceBackend, dataset_ref_from_staged
from backend.recurrence_service_adapter import RecurrenceTrainResult
from frontend.dashboard_manager import DashboardManager
from model_registry import dataset_default_params


class _RecordingAdapter:
    """Stand-in for RecurrenceServiceAdapter that records ``train`` calls (no network)."""

    def __init__(self):
        self.service_url = "http://rec.test:8210"
        self.calls = []

    def train(self, **kwargs):
        self.calls.append(kwargs)
        return RecurrenceTrainResult(
            final_metrics={"r2": 0.5, "mse": 0.1, "loss": 0.1},
            n_epochs=1,
            stopped_reason="fit_complete",
            dataset={"name": "equities_seq", "n_windows": 3, "n_features": 2, "output_dim": 1},
        )


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _text_of(component):
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return "".join(_text_of(child) for child in component)
    return _text_of(getattr(component, "children", None))


# Recurrence recorded over the demo backend: the D-8 / X1 state, ``swapped`` False.
INACTIVE_STATE = {"nn_model": "recurrence", "backend": "demo", "execution": "continuous", "status": "live", "swapped": False}
LIVE_STATE = {"nn_model": "recurrence", "backend": "recurrence", "execution": "one_shot", "status": "live", "swapped": True}
STAGED = {"nn_dataset_type": "equities_seq", "nn_dataset_params": {"max_symbols": 2}}


@pytest.fixture
def backend():
    return RecurrenceBackend(_RecordingAdapter())


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


@pytest.mark.regression
@pytest.mark.unit
class TestTheStagedConfigTranslation:
    """Canopy's staging dialect -> the recurrence service's ``DatasetRef``."""

    def test_registry_defaults_seed_the_params(self):
        ref = dataset_ref_from_staged({"nn_dataset_type": "equities_seq"})
        assert ref == {"generator": "equities_seq", "params": dataset_default_params("equities_seq"), "split": "train"}
        # The bound that keeps the one-shot fit inside the service timeout rides along.
        assert ref["params"]["max_symbols"] == 5

    def test_the_alias_map_is_applied_here_and_only_here(self):
        # The staging PAYLOAD stays in canopy's dialect (``test_the_STAGING_payload_must_NOT_be_translated``);
        # the translation to juniper-data's vocabulary happens where the ref is built for the
        # recurrence service, exactly as the one-shot Start body does (X3 / §4.6).
        assert dataset_ref_from_staged({"nn_dataset_type": "spirals"})["generator"] == "spiral"

    def test_operator_edits_override_the_seed(self):
        ref = dataset_ref_from_staged({"nn_dataset_type": "equities_seq", "nn_dataset_elements": 40, "nn_dataset_params": {"max_symbols": 2, "symbols": ["AAPL"]}})
        assert ref["params"] == {"max_symbols": 2, "regression_target": "return", "n_samples": 40, "symbols": ["AAPL"]}

    def test_spiral_only_typed_fields_never_reach_a_sequence_generator(self):
        ref = dataset_ref_from_staged({"nn_dataset_type": "equities_seq", "nn_spiral_rotations": 2.0, "nn_spiral_number": 3})
        assert "rotations" not in ref["params"]
        assert "n_spirals" not in ref["params"]


@pytest.mark.regression
@pytest.mark.unit
class TestRecurrenceBackendStagesInProcess:
    """The DemoMode contract, on the recurrence backend: stage / peek / status / cancel / consume."""

    def test_stage_then_status_then_cancel(self, backend):
        assert backend.get_pending_dataset() == {"ok": True, "pending": None}
        assert backend.get_status().get("pending_dataset") is None
        result = backend.stage_dataset(nn_dataset_type="equities_seq", nn_dataset_params={"max_symbols": 2}, nn_dataset_noise=None)
        assert result["ok"] is True
        assert result["data"]["status"] == "staged"
        assert result["data"]["config"] == STAGED
        assert result["data"]["dataset_ref"]["generator"] == "equities_seq"
        assert backend.get_pending_dataset()["pending"] == STAGED
        # The banner reconciles off status, as it does for cascor and demo.
        assert backend.get_status()["pending_dataset"] == STAGED
        cancelled = backend.cancel_pending_dataset()
        assert cancelled["ok"] is True
        assert cancelled["data"]["discarded"] == STAGED
        assert backend.get_pending_dataset()["pending"] is None
        assert backend.get_status()["pending_dataset"] is None

    def test_an_empty_body_clears_as_cascor_documents(self, backend):
        backend.stage_dataset(nn_dataset_type="equities_seq")
        assert backend.stage_dataset()["data"]["status"] == "cleared"
        assert backend.get_pending_dataset()["pending"] is None

    def test_a_config_without_a_type_is_refused_and_stages_nothing(self, backend):
        result = backend.stage_dataset(nn_dataset_params={"max_symbols": 2})
        assert result["ok"] is False
        assert "nn_dataset_type" in result["error"]
        assert backend.get_pending_dataset()["pending"] is None

    def test_the_next_fit_consumes_the_staged_dataset(self, backend):
        backend.stage_dataset(**STAGED)
        result = backend.start_training(reset=True)  # the restart route's bare call: no ref at all
        assert result["ok"] is True, result
        assert _wait_until(lambda: not backend.is_training_active())
        call = backend._adapter.calls[0]
        assert call["generator"] == "equities_seq"
        assert call["params"] == {"max_symbols": 2, "regression_target": "return"}
        assert call["split"] == "train"
        # Consumed: the banner closes, as it does when cascor clears ``pending_dataset``.
        assert backend.get_pending_dataset()["pending"] is None
        assert backend.get_status().get("pending_dataset") is None

    def test_the_staged_dataset_wins_over_the_one_shot_body(self, backend):
        # The one-shot Start body carries only the registry's defaults for the dropdown value; it
        # knows nothing of what the operator edited and APPLIED. Preferring it would discard the
        # applied change while reporting success -- the class this arc exists to close.
        backend.stage_dataset(**STAGED)
        result = backend.start_training(reset=True, generator="equities_seq", params=dataset_default_params("equities_seq"))
        assert result["ok"] is True, result
        assert _wait_until(lambda: not backend.is_training_active())
        assert backend._adapter.calls[0]["params"]["max_symbols"] == 2

    def test_without_a_staged_dataset_the_body_is_used_unchanged(self, backend):
        result = backend.start_training(reset=True, generator="equities_seq", params={"max_symbols": 1}, d=4)
        assert result["ok"] is True, result
        assert _wait_until(lambda: not backend.is_training_active())
        call = backend._adapter.calls[0]
        assert call["generator"] == "equities_seq"
        assert call["params"] == {"max_symbols": 1}
        assert call["d"] == 4

    def test_a_bare_start_with_nothing_staged_still_fails_closed(self, backend):
        result = backend.start_training(reset=True)
        assert result["ok"] is False
        assert "no dataset reference" in result["error"]
        assert backend._adapter.calls == []

    def test_the_hyperparameters_still_ride_along(self, backend):
        backend.apply_params(d=6, theta=2.0)
        backend.stage_dataset(**STAGED)
        assert backend.start_training(reset=True)["ok"] is True
        assert _wait_until(lambda: not backend.is_training_active())
        call = backend._adapter.calls[0]
        assert call["d"] == 6
        assert call["theta"] == 2.0


@pytest.mark.regression
@pytest.mark.unit
class TestTheRoutesStageThePair:
    """End to end through the routes the dashboard actually calls."""

    @pytest.fixture
    def client(self):
        with TestClient(main.app) as client:
            yield client

    @pytest.fixture
    def recurrence(self, monkeypatch):
        rb = RecurrenceBackend(_RecordingAdapter())
        monkeypatch.setattr(main, "backend", rb, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        return rb

    def test_stage_dataset_reaches_the_recurrence_backend(self, client, recurrence):
        # Before: 501 "does not support staging" (the #599 guard, which still covers a backend
        # without the capability -- see test_dataset_generator_contract.py).
        resp = client.post("/api/stage_dataset", json=STAGED)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "staged"
        assert recurrence.get_pending_dataset()["pending"] == STAGED

    def test_the_restart_route_fits_the_staged_dataset(self, client, recurrence):
        # The dataset modal's path: stage, then POST /api/train/restart -- a bare start.
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        resp = client.post("/api/train/restart", json={"start_fresh": False, "reset": True})
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is True
        assert _wait_until(lambda: not recurrence.is_training_active())
        assert recurrence._adapter.calls[0]["generator"] == "equities_seq"
        assert recurrence._adapter.calls[0]["params"]["max_symbols"] == 2
        assert recurrence.get_pending_dataset()["pending"] is None

    def test_cancel_pending_reaches_the_recurrence_backend(self, client, recurrence):
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        resp = client.delete("/api/cancel_pending_dataset")
        assert resp.status_code == 200, resp.text
        assert recurrence.get_pending_dataset()["pending"] is None

    def test_train_status_carries_pending_dataset_for_the_banner(self, client, recurrence):
        assert client.post("/api/stage_dataset", json=STAGED).status_code == 200
        resp = client.get("/api/train/status")
        assert resp.status_code == 200, resp.text
        assert resp.json().get("pending_dataset") == STAGED

    def test_staging_is_refused_for_an_inactive_selection_before_anything_leaves_canopy(self, client, monkeypatch):
        # X6's cascor branch, at its cause: Recurrence recorded over the demo backend. Nothing
        # reaches the backend, so nothing reaches cascor -- whose refusal of a rank-3 artifact is
        # correct and stays exactly where it is.
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        fake.stage_dataset.return_value = {"ok": True, "data": {}}
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "equities_seq"})
        assert resp.status_code == 409, resp.text
        error = resp.json()["error"]
        assert "Recurrence (LMU)" in error
        assert "demo" in error
        fake.stage_dataset.assert_not_called()

    def test_a_live_cascor_selection_still_stages_normally(self, client, monkeypatch):
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        fake.stage_dataset.return_value = {"ok": True, "data": {"status": "staged"}}
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "spirals", "nn_dataset_elements": 100})
        assert resp.status_code == 200, resp.text
        fake.stage_dataset.assert_called_once_with(nn_dataset_type="spirals", nn_dataset_elements=100)


@pytest.mark.regression
@pytest.mark.unit
class TestApplyDatasetIsGatedLikeStart:
    """The control-side half of the refusal, in the callback that owns both buttons."""

    @staticmethod
    def _appearance(manager, model_state):
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        return manager._update_button_appearance_handler(button_states=states, model_key="recurrence", dataset_value="equities_seq", model_state=model_state)

    def test_apply_is_disabled_for_an_inactive_selection(self, manager):
        out = self._appearance(manager, INACTIVE_STATE)
        assert out[0] is True  # Start (N5)
        assert out[-1] is True  # Apply Dataset

    def test_apply_stays_enabled_when_the_selection_is_live(self, manager):
        out = self._appearance(manager, LIVE_STATE)
        assert out[0] is False
        assert out[-1] is False

    def test_apply_is_unknown_safe_at_first_paint(self, manager):
        assert self._appearance(manager, None)[-1] is False

    def test_the_notice_names_both_controls(self):
        text = _text_of(DashboardManager._train_gate_notice_handler("recurrence", model_state=INACTIVE_STATE))
        assert "Start and Apply Dataset are disabled" in text
        assert "demo" in text
