#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_empty_axis_commit_and_restage_zeros.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-06
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Empty-string dataset commits, and zeros on the
#                restart re-stage and the shortfall retry.
#####################################################################
"""Commit paths that only the ``None`` half of ``⊥`` was pinning, and zeros the sidebar builder does not send.

``selection_axis_unset`` treats ``""`` as unset so a widget that emits an empty string cannot
commit. Start's button tests pin that helper, so deleting ``value == ""`` from it fails them.
Replacing one call site with ``is None`` does not: Apply, the restart re-stage, and the live
swap were only driven with ``None``. An empty string on those wires is destructive. Apply's
empty body clears a staged dataset, and a live swap with no target stops the running run.

``_restage_dataset`` builds its own body. It is not ``_dataset_stage_payload``, so a truthiness
check there drops ``0`` and ``0.0`` while the sidebar suite stays green. The shortfall retry
has the same ``is not None`` test, and its pending-dataset read must fail closed when the
status route does not return a config.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from frontend.dashboard_manager import DATASET_SHORTFALL_OPTIONS, DashboardManager

pytestmark = [pytest.mark.regression, pytest.mark.unit]


@pytest.fixture
def dm():
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


def _text(node) -> str:
    if node is None or isinstance(node, (int, float, bool)):
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, (list, tuple)):
        return "".join(_text(child) for child in node)
    return _text(getattr(node, "children", None))


def _response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = {} if json_data is None else json_data
    return resp


class TestAnEmptyStringDoesNotCommit:
    """``""`` is the other half of ``⊥``. ``None`` is already refused on these wires."""

    def test_apply_refuses_and_does_not_post(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as post:
            banner, alert = dm._apply_dataset_handler(1, "", 100, 0.1, 2.0, 2)
        post.assert_not_called()
        assert banner is False
        text = _text(alert)
        assert "No dataset selected" in text
        assert "clear" in text

    def test_restage_refuses_and_does_not_post(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as post:
            ok, detail = dm._restage_dataset({"dataset_type": "", "n_samples": 100, "noise": 0.0})
        post.assert_not_called()
        assert ok is False
        assert "No dataset" in detail

    def test_live_swap_refuses_and_does_not_post(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as post:
            modal, _progress, alert, in_flight = dm._accept_live_switch_handler(1, "", 100, 0.0, 2, 1.0)
        post.assert_not_called()
        assert modal is False and in_flight is False
        text = _text(alert)
        assert "No dataset selected" in text
        assert "stop the current run" in text

    def test_the_confirmation_names_the_empty_target_and_keeps_zero_noise(self, dm):
        _is_open, rows = dm._open_live_switch_modal_handler(1, "", 0, 0.0, 0, None)
        text = _text(rows)
        assert "none selected" in text
        assert "0.0" in text
        assert "Samples" in text

    def test_apply_stays_disabled_for_an_empty_string_dataset(self, dm):
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        enabled = dm._update_button_appearance_handler(button_states=states, model_key="cascor", dataset_value="spirals")
        disabled = dm._update_button_appearance_handler(button_states=states, model_key="cascor", dataset_value="")
        assert enabled[-1] is False
        assert disabled[-1] is True


class TestRestartRestageKeepsZeros:
    def _posted(self, dm, dataset_vals, nn_model="cascor"):
        with patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = _response(200, text="")
            ok, detail = dm._restage_dataset(dataset_vals, nn_model=nn_model)
        assert ok is True and detail == ""
        assert post.call_args.args[0].endswith("/api/stage_dataset")
        return post.call_args.kwargs["json"]

    def test_zero_counts_and_zero_noise_are_sent(self, dm):
        body = self._posted(
            dm,
            {"dataset_type": "circles", "n_samples": 0, "noise": 0.0, "rotations": None, "n_spirals": 0},
        )
        assert body == {
            "nn_dataset_type": "circles",
            "nn_dataset_elements": 0,
            "nn_dataset_noise": 0.0,
            "nn_spiral_number": 0,
            "nn_model": "cascor",
        }

    def test_a_seeded_generator_keeps_the_seed_and_the_zero_typed_fields(self, dm):
        from model_registry import dataset_default_params

        seed = dataset_default_params("equities")
        assert seed.get("symbols"), "an empty seed would make a dropped list look like a pass"
        body = self._posted(dm, {"dataset_type": "equities", "n_samples": 0, "noise": 0.0})
        assert body["nn_dataset_elements"] == 0
        assert body["nn_dataset_noise"] == 0.0
        assert body["nn_dataset_params"]["symbols"] == seed["symbols"]

    @pytest.mark.parametrize("nn_model", ["", None, 0, False])
    def test_a_falsy_model_is_omitted(self, dm, nn_model):
        body = self._posted(dm, {"dataset_type": "circles", "n_samples": 1}, nn_model=nn_model)
        assert "nn_model" not in body
        assert body["nn_dataset_elements"] == 1

    def test_the_outcome_label_counts_zero_samples(self):
        assert DashboardManager._describe_dataset({"dataset_type": "circles", "n_samples": 0}) == "circles (0 samples)"
        assert DashboardManager._describe_dataset({"dataset_type": "circles", "n_samples": None}) == "circles"
        assert DashboardManager._describe_dataset(None) == "current"


class TestRestartRestageFailuresStayMessages:
    def test_a_connection_error_is_unreachable_and_does_not_raise(self, dm):
        with patch("frontend.dashboard_manager.requests.post", side_effect=requests.ConnectionError("connection refused")):
            ok, detail = dm._restage_dataset({"dataset_type": "circles", "n_samples": 1})
        assert ok is False
        assert detail.startswith("backend unreachable:")
        assert "connection refused" in detail

    @pytest.mark.parametrize("text", ["", None])
    def test_an_empty_error_body_names_the_status(self, dm, text):
        with patch("frontend.dashboard_manager.requests.post", return_value=_response(422, text=text)):
            ok, detail = dm._restage_dataset({"dataset_type": "circles", "n_samples": 1})
        assert ok is False
        assert detail == "HTTP 422"

    def test_a_long_error_body_is_cut_at_300(self, dm):
        with patch("frontend.dashboard_manager.requests.post", return_value=_response(502, text="Z" * 301)):
            ok, detail = dm._restage_dataset({"dataset_type": "circles", "n_samples": 1})
        assert ok is False
        assert detail == "Z" * 300


class TestPendingDatasetReadFailsClosed:
    def _fetch(self, dm, response=None, error=None):
        with patch("frontend.dashboard_manager.requests.get", return_value=response, side_effect=error) as get:
            found = dm._fetch_pending_dataset_config()
        assert get.call_args.args[0].endswith("/api/status")
        return found

    def test_a_non_200_is_nothing_even_when_the_body_holds_a_config(self, dm):
        body = {"pending_dataset": {"dataset_type": "equities", "noise": 0.0}}
        assert self._fetch(dm, _response(503, json_data=body)) is None

    def test_a_connection_error_is_nothing(self, dm):
        assert self._fetch(dm, error=requests.ConnectionError("refused")) is None

    def test_a_non_json_body_is_nothing(self, dm):
        resp = _response(200)
        resp.json.side_effect = ValueError("not json")
        assert self._fetch(dm, resp) is None

    def test_a_non_object_body_is_nothing(self, dm):
        assert self._fetch(dm, _response(200, json_data=[{"dataset_type": "equities"}])) is None

    @pytest.mark.parametrize("pending", ["equities", [], 0, None], ids=["string", "list", "zero", "null"])
    def test_a_pending_that_is_not_a_dict_is_nothing(self, dm, pending):
        assert self._fetch(dm, _response(200, json_data={"pending_dataset": pending})) is None

    def test_an_empty_pending_is_nothing(self, dm):
        assert self._fetch(dm, _response(200, json_data={"pending_dataset": {}})) is None

    def test_a_dict_whose_only_value_is_zero_is_kept_and_copied(self, dm):
        original = {"noise": 0.0}
        found = self._fetch(dm, _response(200, json_data={"pending_dataset": original}))
        assert found == {"noise": 0.0}
        assert found is not original


class TestShortfallRetryKeepsZeros:
    def test_zero_typed_fields_are_sent_and_none_is_omitted(self):
        pending = {
            "dataset_type": "spirals",
            "n_samples": 0,
            "noise": 0.0,
            "rotations": None,
            "n_spirals": 0,
            "unknown_key": 0,
        }
        payload = DashboardManager._restage_payload_with_policy(pending, DATASET_SHORTFALL_OPTIONS["dataset-shortfall-accept-button"])
        assert payload["nn_dataset_type"] == "spirals"
        assert payload["nn_dataset_elements"] == 0
        assert payload["nn_dataset_noise"] == 0.0
        assert payload["nn_spiral_number"] == 0
        assert "nn_spiral_rotations" not in payload
        assert "unknown_key" not in payload
        assert payload["nn_dataset_params"]["allow_truncation"] is True
        assert payload["nn_dataset_params"]["incomplete_rows"] == "accept"

    @pytest.mark.parametrize(
        "pending",
        [
            {"dataset_type": "equities"},
            {"dataset_type": "equities", "params": None},
            {"dataset_type": "equities", "params": ""},
            {"dataset_type": "equities", "params": False},
            {"dataset_type": "equities", "params": {}},
        ],
        ids=["absent", "none", "blank", "false", "empty"],
    )
    def test_a_missing_or_falsy_params_dict_still_carries_the_choice(self, pending):
        payload = DashboardManager._restage_payload_with_policy(pending, DATASET_SHORTFALL_OPTIONS["dataset-shortfall-drop-button"])
        assert payload["nn_dataset_params"] == {"allow_truncation": True, "incomplete_rows": "drop"}

    def test_a_connection_error_on_the_retry_stage_is_a_message(self, dm):
        with patch("frontend.dashboard_manager.requests.post", side_effect=requests.ConnectionError("refused")):
            ok, detail = dm._post_stage_dataset({"nn_dataset_type": "equities"})
        assert ok is False
        assert detail.startswith("backend unreachable:")

    def test_an_empty_retry_error_names_the_status(self, dm):
        with patch("frontend.dashboard_manager.requests.post", return_value=_response(502, text="")):
            ok, detail = dm._post_stage_dataset({"nn_dataset_type": "equities"})
        assert ok is False
        assert detail == "HTTP 502"

    def test_a_connection_error_on_cancel_is_a_message(self, dm):
        with patch("frontend.dashboard_manager.requests.delete", side_effect=requests.ConnectionError("refused")):
            ok, detail = dm._cancel_pending_dataset_via_api()
        assert ok is False
        assert detail.startswith("backend unreachable:")


class TestProducerDetailSecondStop:
    def test_the_resulting_dataset_sentence_is_cut_when_the_remedy_is_absent(self):
        detail = (
            "HTTP 409: [dataset_shortfall_refused] juniper-data could not produce the requested dataset in full. "
            "Producer detail: HTTP 422: 2 symbols failed. "
            "The resulting dataset is permanently annotated as partial."
        )
        extracted = DashboardManager._producer_detail_from_refusal(detail)
        assert extracted == "HTTP 422: 2 symbols failed."
        assert "permanently annotated" not in extracted

    def test_a_detail_with_neither_stop_is_the_producer_sentence(self):
        assert DashboardManager._producer_detail_from_refusal("Producer detail:   just the sentence") == "just the sentence"
        assert DashboardManager._producer_detail_from_refusal("no marker here") == ""
