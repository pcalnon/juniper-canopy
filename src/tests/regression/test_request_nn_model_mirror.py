#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_request_nn_model_mirror.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   FR9 / canopy#368 -- the ``nn_model`` mirror on the
#                dataset-stage, live-swap and set-params requests.
#####################################################################
"""The ``nn_model`` mirror: a stale tab or an incompatible pair fails closed at the route.

canopy#368's last open A1 clause, specified in juniper-ml
``notes/JUNIPER_2026-06-15_JUNIPER-CANOPY_AUDIT-REGRESSIONS-AND-MODEL-SELECTION.md`` §4.4 and
FR9 of ``notes/JUNIPER_2026-06-17_JUNIPER-CANOPY_MODEL-DATASET-SELECTION-DESIGN.md`` (§5.9):
"canopy threads ``nn_model`` to the backend; [it] validates ... and fails closed on mismatch
(defence in depth -- a UI desync cannot train an invalid pair)".

``current_nn_model`` is server state; ``model-selection-store`` is per-tab memory. A second tab,
or one opened before another client changed the model, holds a stale selection -- and a request
made under it used to land on whichever backend was live. The concrete hazard: a stale CasCor tab
stages a rank-2 dataset while the recurrence backend is live, which fails only at FIT time.

Every case goes through the real routes (``TestClient``) or the real dashboard handlers, with the
backend replaced at its own seam so what the route FORWARDS can be asserted, not just its status.
"""

from unittest import mock

import dash
import pytest
from fastapi.testclient import TestClient

import main
from backend.recurrence_backend import RecurrenceBackend
from frontend.dashboard_manager import DashboardManager


class _NoFitAdapter:
    """``RecurrenceServiceAdapter`` stand-in. Nothing here starts a fit."""

    service_url = "http://rec.test:8210"

    def train(self, **_kwargs):  # pragma: no cover - never reached
        raise AssertionError("no fit expected")


def _fake_backend(backend_type="demo"):
    fake = mock.MagicMock()
    fake.backend_type = backend_type
    fake.execution = "continuous"
    fake.is_training_active.return_value = False
    fake.stage_dataset.return_value = {"ok": True, "data": {"status": "staged"}}
    fake.swap_dataset_live.return_value = {"ok": True, "data": {"status": "swapped"}}
    fake.apply_params.return_value = {"ok": True, "data": {}}
    return fake


@pytest.fixture
def client():
    with TestClient(main.app) as client:
        yield client


@pytest.mark.regression
@pytest.mark.unit
class TestTheFieldExistsOnBothRequestModels:
    """#368's guardrail, verbatim: "a field absent from a request model is silently dropped"."""

    def test_both_models_carry_nn_model(self):
        assert "nn_model" in main.SetParamsRequest.model_fields
        assert "nn_model" in main.StageDatasetRequest.model_fields

    def test_it_is_optional_on_both(self):
        # Every pre-mirror client and ``curl`` must keep working unchanged.
        assert main.SetParamsRequest().nn_model is None
        assert main.StageDatasetRequest().nn_model is None


@pytest.mark.regression
@pytest.mark.unit
class TestStagingFailsClosed:
    @pytest.fixture
    def cascor_selected(self, client, monkeypatch):
        fake = _fake_backend("demo")
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        return client, fake

    def test_a_request_without_the_mirror_behaves_as_before(self, cascor_selected):
        client, fake = cascor_selected
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "xor"}).status_code == 200
        fake.stage_dataset.assert_called_once_with(nn_dataset_type="xor")

    def test_a_matching_mirror_stages_and_is_not_forwarded(self, cascor_selected):
        client, fake = cascor_selected
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "xor", "nn_model": "cascor"}).status_code == 200
        # A routing key, not a dataset key: a backend's staged config must not carry it.
        fake.stage_dataset.assert_called_once_with(nn_dataset_type="xor")

    def test_a_stale_tab_is_refused_and_nothing_is_staged(self, cascor_selected):
        client, fake = cascor_selected
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "multi_sine", "nn_model": "recurrence"})
        assert resp.status_code == 409, resp.text
        assert "out of date" in resp.json()["error"]
        assert "CasCor" in resp.json()["error"] and "Recurrence" in resp.json()["error"]
        fake.stage_dataset.assert_not_called()

    def test_an_unknown_model_is_refused(self, cascor_selected):
        client, fake = cascor_selected
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "xor", "nn_model": "no-such-model"}).status_code == 422
        fake.stage_dataset.assert_not_called()

    def test_an_incompatible_pair_fails_closed(self, cascor_selected):
        # A rank-3 sequence dataset for the rank-2 CasCor: refused here, not at cascor's tier boundary.
        client, fake = cascor_selected
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "multi_sine", "nn_model": "cascor"})
        assert resp.status_code == 422, resp.text
        assert "needs a 3-D model" in resp.json()["error"]
        fake.stage_dataset.assert_not_called()

    def test_the_generator_spelling_is_judged_like_canopy_s_own(self, cascor_selected):
        # ``spiral`` (juniper-data's name) and ``spirals`` (canopy's value) are the same dataset.
        client, fake = cascor_selected
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "spiral", "nn_model": "cascor"}).status_code == 200

    def test_a_dataset_canopy_cannot_name_is_left_to_the_target_service(self, cascor_selected):
        client, fake = cascor_selected
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "arc_agi", "nn_model": "cascor"}).status_code == 200
        fake.stage_dataset.assert_called_once_with(nn_dataset_type="arc_agi")

    def test_nothing_selected_yet_means_the_boot_model(self, client, monkeypatch):
        # Until the first /api/model/select the boot backend serves the default model, so a mirror
        # naming it is current -- and one naming anything else is stale.
        monkeypatch.setattr(main, "backend", _fake_backend("demo"), raising=False)
        monkeypatch.setattr(main, "current_nn_model", None, raising=False)
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "xor", "nn_model": "cascor"}).status_code == 200
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "xor", "nn_model": "recurrence"}).status_code == 409


@pytest.mark.regression
@pytest.mark.unit
class TestTheHazardTheMirrorExistsFor:
    """The recurrence backend is live; a stale CasCor-era request stages a rank-2 dataset into it."""

    @pytest.fixture
    def recurrence_live(self, client, monkeypatch):
        backend = RecurrenceBackend(_NoFitAdapter())
        monkeypatch.setattr(main, "backend", backend, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        return client, backend

    def test_a_rank_2_dataset_for_the_lmu_fails_closed_at_stage_time(self, recurrence_live):
        client, backend = recurrence_live
        resp = client.post("/api/stage_dataset", json={"nn_dataset_type": "spirals", "nn_model": "recurrence"})
        assert resp.status_code == 422, resp.text
        assert backend.get_pending_dataset()["pending"] is None  # nothing reached the backend

    def test_a_compatible_one_stages_without_the_routing_key(self, recurrence_live):
        client, backend = recurrence_live
        assert client.post("/api/stage_dataset", json={"nn_dataset_type": "multi_sine", "nn_model": "recurrence"}).status_code == 200
        staged = backend.get_pending_dataset()["pending"]
        assert staged == {"nn_dataset_type": "multi_sine"}


@pytest.mark.regression
@pytest.mark.unit
class TestLiveSwapAndSetParams:
    def test_a_stale_live_swap_is_refused_before_anything_moves(self, client, monkeypatch):
        fake = _fake_backend("service")
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        assert client.post("/api/live_dataset_swap", json={"nn_dataset_type": "xor", "nn_model": "recurrence"}).status_code == 409
        fake.swap_dataset_live.assert_not_called()
        assert client.post("/api/live_dataset_swap", json={"nn_dataset_type": "xor", "nn_model": "cascor"}).status_code == 200
        fake.swap_dataset_live.assert_called_once_with(nn_dataset_type="xor")

    def test_a_stale_parameter_apply_is_refused(self, client, monkeypatch):
        fake = _fake_backend("demo")
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        resp = client.post("/api/set_params", json={"nn_learning_rate": 0.02, "nn_model": "recurrence"})
        assert resp.status_code == 409, resp.text
        fake.apply_params.assert_not_called()

    def test_a_matching_parameter_apply_never_forwards_the_routing_key(self, client, monkeypatch):
        fake = _fake_backend("demo")
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        assert client.post("/api/set_params", json={"nn_learning_rate": 0.02, "nn_model": "cascor"}).status_code == 200
        forwarded = fake.apply_params.call_args.kwargs
        assert "nn_model" not in forwarded
        assert forwarded["nn_learning_rate"] == 0.02


@pytest.mark.regression
@pytest.mark.unit
class TestTheDashboardSendsIt:
    # The full, valid form -- ``None`` in a numeric field is refused before any POST (F-CANOPY-017).
    VALID_PARAMS = {
        "n_clicks": 1,
        "nn_max_iter": 1000,
        "nn_max_epochs": 600,
        "nn_lr": 0.015,
        "nn_max_hu": 25,
        "nn_multi_node": [],
        "nn_growth_trigger": "convergence",
        "nn_growth_epochs": 50,
        "nn_growth_conv_thresh": 0.001,
        "nn_patience": 50,
        "nn_spiral_rot": 1.5,
        "nn_spiral_num": 2,
        "nn_dataset_elem": 1000,
        "nn_dataset_noise": 0.25,
        "cn_pool_size": 100,
        "cn_corr_thresh": 0.001,
        "cn_selected": 1,
        "cn_training_complete": "preset_epochs",
        "cn_training_iter": 500,
        "cn_training_conv_thresh": 0.0001,
        "cn_patience": 30,
        "cn_multi_cand": [],
        "cn_cand_selection": None,
        "cn_top_cands": 1,
        "cn_random_cands": 1,
    }

    @pytest.fixture(scope="class")
    def manager(self):
        return DashboardManager({})

    @staticmethod
    def _state_ids(manager, callback_name):
        """The State ids of the callback registered under ``callback_name`` (found by function name)."""
        found = []
        for entry in manager.app.callback_map.values():
            fn = entry.get("callback")
            if getattr(getattr(fn, "__wrapped__", fn), "__name__", None) == callback_name:
                found.append({s.get("id") for s in entry.get("state", []) if isinstance(s.get("id"), str)})
        assert len(found) == 1, f"expected one callback named {callback_name!r}, found {len(found)}"
        return found[0]

    def test_both_apply_callbacks_read_the_selection_as_state(self, manager):
        # State, not Input: reading the model must never trigger an apply on its own.
        assert "model-selection-store" in self._state_ids(manager, "apply_dataset")
        assert "model-selection-store" in self._state_ids(manager, "apply_parameters")

    def _stage(self, manager, nn_model):
        with mock.patch("requests.post") as post, manager.app.server.test_request_context(base_url="http://localhost:8050"):
            post.return_value = mock.Mock(status_code=200, text="")
            manager._apply_dataset_handler(1, "spirals", 100, 0.1, 1.5, 2, [], [], nn_model=nn_model)
        return post.call_args.kwargs["json"]

    def test_apply_dataset_mirrors_the_model(self, manager):
        assert self._stage(manager, "cascor")["nn_model"] == "cascor"

    def test_no_selected_model_sends_no_key(self, manager):
        # Omitted, not ``None``: the server then behaves exactly as before the mirror.
        assert "nn_model" not in self._stage(manager, None)

    def test_apply_parameters_mirrors_on_the_request_but_not_into_the_applied_store(self, manager):
        # The applied store is what the dirty tracker compares the form against; a routing key
        # there would read as an applied parameter nobody can edit.
        with mock.patch("requests.post") as post, mock.patch("requests.get") as get, manager.app.server.test_request_context(base_url="http://localhost:8050"):
            post.return_value = mock.Mock(status_code=200, text="", json=lambda: {})
            get.return_value = mock.Mock(status_code=200, json=lambda: {})
            store, _toast = manager._apply_parameters_handler(**self.VALID_PARAMS, nn_model="cascor")
        assert post.call_args.kwargs["json"]["nn_model"] == "cascor"
        assert isinstance(store, dict) and "nn_model" not in store
        assert store["nn_learning_rate"] == 0.015
