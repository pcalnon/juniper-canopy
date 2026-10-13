#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_staging_paths_send_one_payload.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   The live dataset swap sends Apply Dataset's body, and the
#                restart modal and live swap carry the nn_model mirror.
#####################################################################
"""Every path that stages a dataset sends the body Apply Dataset sends, and carries the ``nn_model`` mirror.

Three dashboard paths stage a dataset: Apply Dataset (``/api/stage_dataset``), the live swap
(``/api/live_dataset_swap``) and the restart modal's re-stage (``/api/stage_dataset``). canopy#668
found the modal re-staging ``equities`` without its ``symbols`` seed. The live swap had the same
defect and a wider one. It sent the four typed SPIRAL fields for every generator and never
``nn_dataset_params``, so a swap to ``equities`` dropped ``symbols`` and a swap to ``mnist`` dropped
``flatten``. It now builds its body with ``_dataset_stage_payload``, the builder Apply Dataset uses.

canopy#669 added the FR9 ``nn_model`` mirror to the two sidebar Apply paths only. The live swap and
the modal's re-stage and parameter apply now carry it too, so a stale tab is refused (409) by the
routes #669 taught to check it, before anything moves.
"""

from unittest.mock import MagicMock, patch

import pytest

from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, dataset_default_params

# The sidebar's typed spiral inputs keep their values whichever dataset is picked.
FORM = {"n_samples": 200, "noise": 0.1, "rotations": 1.5, "n_spirals": 2}
SEEDED = [spec.value for spec in DATASET_TYPES if dataset_default_params(spec.value)]


@pytest.fixture
def dm():
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


def _resp(status=200, json_body=None):
    r = MagicMock(status_code=status, text="")
    r.json.return_value = {} if json_body is None else json_body
    return r


def _posts(call):
    """Run ``call`` with ``requests.post`` mocked; return ``[(route, json), ...]`` in order."""
    with patch("frontend.dashboard_manager.requests.post", return_value=_resp(200, {"success": True, "data": {"status": "swapped"}})) as post, patch("frontend.dashboard_manager.requests.get", return_value=_resp(200, {})):
        call()
    return [(c.args[0].rsplit("/api/", 1)[-1], c.kwargs.get("json")) for c in post.call_args_list]


def _apply_body(dm, dataset, gen_values=(), gen_ids=(), nn_model=None):
    sent = _posts(lambda: dm._apply_dataset_handler(1, dataset, FORM["n_samples"], FORM["noise"], FORM["rotations"], FORM["n_spirals"], list(gen_values), list(gen_ids), nn_model=nn_model))
    assert [route for route, _ in sent] == ["stage_dataset"]
    return sent[0][1]


def _swap_body(dm, dataset, gen_values=(), gen_ids=(), nn_model=None):
    sent = _posts(lambda: dm._accept_live_switch_handler(n_clicks=1, dataset_type=dataset, gen_values=list(gen_values), gen_ids=list(gen_ids), nn_model=nn_model, **FORM))
    assert [route for route, _ in sent] == ["live_dataset_swap"]
    return sent[0][1]


@pytest.mark.regression
@pytest.mark.unit
class TestTheLiveSwapSendsWhatApplySends:
    @pytest.mark.parametrize("dataset", [spec.value for spec in DATASET_TYPES])
    def test_every_dataset_gets_one_body(self, dm, dataset):
        assert _swap_body(dm, dataset, nn_model="cascor") == _apply_body(dm, dataset, nn_model="cascor")

    @pytest.mark.parametrize("dataset", SEEDED)
    def test_a_seeded_generator_s_seed_travels_with_the_swap(self, dm, dataset):
        # Parity alone would pass if the shared builder lost the seed on BOTH paths; pin the seed.
        seed = dataset_default_params(dataset)
        params = _swap_body(dm, dataset).get("nn_dataset_params", {})
        assert {key: params.get(key) for key in seed} == dict(seed), f"a live swap to {dataset} dropped part of its registry seed"

    def test_the_two_seeds_the_defect_was_found_on(self, dm):
        assert _swap_body(dm, "equities")["nn_dataset_params"]["symbols"]
        assert _swap_body(dm, "mnist")["nn_dataset_params"]["flatten"] is True

    def test_a_non_spiral_swap_carries_no_spiral_fields(self, dm):
        body = _swap_body(dm, "moon")
        assert not {"nn_dataset_elements", "nn_dataset_noise", "nn_spiral_number", "nn_spiral_rotations"} & body.keys()

    def test_spiral_still_sends_its_typed_fields(self, dm):
        body = _swap_body(dm, "spirals")
        assert body["nn_dataset_elements"] == FORM["n_samples"] and body["nn_spiral_number"] == FORM["n_spirals"]

    def test_the_rendered_schema_fields_ride_along(self, dm):
        gen_ids = [{"type": "nn-gen-param", "name": "noise"}]
        assert _swap_body(dm, "moon", gen_values=[0.3], gen_ids=gen_ids)["nn_dataset_params"] == {"noise": 0.3}


@pytest.mark.regression
@pytest.mark.unit
class TestTheMirrorOnTheLiveSwapAndTheRestartModal:
    def test_the_live_swap_mirrors_the_model(self, dm):
        assert _swap_body(dm, "spirals", nn_model="cascor")["nn_model"] == "cascor"

    def test_no_selected_model_sends_no_key_on_the_swap(self, dm):
        assert "nn_model" not in _swap_body(dm, "spirals")

    def test_the_modal_re_stage_mirrors_the_model(self, dm):
        sent = _posts(lambda: dm._restage_dataset({"dataset_type": "circles", "n_samples": 500}, nn_model="cascor"))
        assert sent == [("stage_dataset", {"nn_dataset_type": "circles", "nn_dataset_elements": 500, "nn_model": "cascor"})]

    def test_no_selected_model_sends_no_key_on_the_re_stage(self, dm):
        sent = _posts(lambda: dm._restage_dataset({"dataset_type": "circles"}))
        assert "nn_model" not in sent[0][1]

    def test_the_restart_confirm_mirrors_on_both_modify_phases(self, dm):
        baseline = {
            "dataset": {"dataset_type": "xor", "n_samples": 300, "noise": 0.1, "rotations": None, "n_spirals": None},
            "params": {"nn_learning_rate": 0.01, "nn_max_hidden_units": 100, "nn_patience": 50, "cn_pool_size": 8, "cn_selected_candidates": 1, "cn_correlation_threshold": 0.5},
        }
        dataset_vals = dict(baseline["dataset"], dataset_type="circles")
        param_vals = dict(baseline["params"], nn_learning_rate=0.5)
        sent = _posts(lambda: dm._execute_restart_handler(n_clicks=1, start_fresh=False, dataset_vals=dataset_vals, param_vals=param_vals, baseline=baseline, nn_model="cascor"))
        by_route = dict(sent)
        assert by_route["stage_dataset"]["nn_model"] == "cascor"
        assert by_route["set_params"]["nn_model"] == "cascor"
        # The restart orchestration itself carries no model identity; its body is unchanged.
        assert by_route["train/restart"] == {"start_fresh": False, "reset": True}


@pytest.mark.regression
@pytest.mark.unit
class TestTheCallbacksReadTheModelAsState:
    @pytest.fixture(scope="class")
    def manager(self):
        return DashboardManager({})

    @staticmethod
    def _states(manager, callback_name):
        found = []
        for entry in manager.app.callback_map.values():
            fn = entry.get("callback")
            if getattr(getattr(fn, "__wrapped__", fn), "__name__", None) == callback_name:
                found.append([str(state.get("id")) for state in entry.get("state", [])])
        assert len(found) == 1, f"expected one callback named {callback_name!r}, found {len(found)}"
        return found[0]

    @pytest.mark.parametrize("callback_name", ["accept_live_switch", "execute_restart"])
    def test_the_model_is_read_as_state_not_input(self, manager, callback_name):
        # State, not Input: reading the model must never fire a swap or a restart by itself.
        assert "model-selection-store" in self._states(manager, callback_name)

    def test_the_live_swap_reads_the_rendered_schema_fields(self, manager):
        assert sum("nn-gen-param" in state for state in self._states(manager, "accept_live_switch")) == 2
