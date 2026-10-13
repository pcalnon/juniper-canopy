"""The partial-data contract's three-way prompt: accept / drop / fail.

Project:       Juniper
Sub-Project:   JuniperCanopy
Application:   juniper_canopy
File Name:     test_dataset_shortfall_prompt.py
Author:        Paul Calnon
License:       MIT License

When a Start is refused because juniper-data could not produce the staged dataset in
full, the dashboard must put the owner's three options to the operator and act on the
answer. These tests drive the handlers directly (no Dash dispatch): recognition of the
refusal class, the prompt's open/ignore decision, the re-stage payload each option
produces, the Start that follows, the cancel-and-deselect of option 3, and the two
render surfaces that mark a run on partial data.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import dash
import pytest
import requests

from frontend.dashboard_manager import (
    DATASET_SHORTFALL_FAIL_BUTTON,
    DATASET_SHORTFALL_OPTIONS,
    DATASET_SHORTFALL_REFUSAL_MARKER,
    DATASET_SHORTFALL_REFUSAL_SENTENCE,
    DashboardManager,
)

pytestmark = pytest.mark.unit

# cascor's message for the "send neither" case, as ``_describe_dataset_fetch_failure`` builds it
# (cascor#633), after canopy's route and handler have wrapped it.
_REFUSAL = (
    "HTTP 409: Training could not be started: Training cannot be started: [dataset_shortfall_refused] "
    "juniper-data could not produce the requested dataset in full, and this run did not accept a partial one, "
    "so the run is FAILING rather than training on data nobody chose. "
    "Producer detail: HTTP 422: Shares outstanding could not be resolved for part of the requested universe. Affected (2): STZ, XYZ. 1,510 row(s) would carry fabricated values. "
    "To accept it, re-run with --allow-truncated-datasets (or set JUNIPER_CASCOR_ALLOW_TRUNCATED_DATASETS=true, or allow_truncated_datasets: true in the experiment YAML service: block), or send allow_truncation=true on the dataset request itself. "
    "The resulting dataset is permanently annotated as partial, and so is every metric derived from it."
)
_OUTAGE = "HTTP 409: Training could not be started: Training cannot be started: juniper-data fetch failed: connection refused"


@pytest.fixture
def dm():
    return DashboardManager({"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}})


def _response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    resp.raise_for_status.return_value = None
    return resp


class TestRefusalRecognition:
    def test_the_token_matches_cascor_s_constant(self):
        """Cross-repo contract: cascor's ``_PROJECT_API_SHORTFALL_REFUSAL_TOKEN`` (cascor#633)."""
        assert DATASET_SHORTFALL_REFUSAL_MARKER == "[dataset_shortfall_refused]"
        assert DATASET_SHORTFALL_REFUSAL_SENTENCE == "could not produce the requested dataset in full"

    def test_token_and_sentence_each_suffice(self):
        assert DashboardManager._is_dataset_shortfall_refusal(_REFUSAL)
        assert DashboardManager._is_dataset_shortfall_refusal("[dataset_shortfall_refused] anything")
        assert DashboardManager._is_dataset_shortfall_refusal("juniper-data could not produce the requested dataset in full, and ...")

    def test_an_outage_and_nothing_are_not_refusals(self):
        """Every option re-sends the request; a dead service must not open the prompt."""
        assert not DashboardManager._is_dataset_shortfall_refusal(_OUTAGE)
        assert not DashboardManager._is_dataset_shortfall_refusal(None)
        assert not DashboardManager._is_dataset_shortfall_refusal("")

    def test_producer_detail_is_extracted_without_the_remedy(self):
        detail = DashboardManager._producer_detail_from_refusal(_REFUSAL)
        assert detail.startswith("HTTP 422: Shares outstanding could not be resolved")
        assert "STZ, XYZ" in detail and "1,510 row(s)" in detail
        assert "To accept it" not in detail and "permanently annotated" not in detail
        assert DashboardManager._producer_detail_from_refusal(_OUTAGE) == ""


class TestOpenPrompt:
    def test_opens_on_a_shortfall_refused_start(self, dm):
        is_open, body, context = dm._open_dataset_shortfall_prompt_handler({"success": False, "command": "start", "detail": _REFUSAL[:300], "detail_full": _REFUSAL})
        assert is_open is True
        assert context["detail"] == _REFUSAL
        rendered = str(body)
        assert "STZ, XYZ" in rendered, "the producer's own detail must reach the operator"
        assert "Accept broken rows" in rendered and "Drop broken rows" in rendered and "Fail the load" in rendered

    def test_falls_back_to_the_short_detail_when_the_transport_sent_no_full_one(self, dm):
        """The server-side handler writes an untruncated ``detail`` and no ``detail_full``."""
        is_open, _body, context = dm._open_dataset_shortfall_prompt_handler({"success": False, "command": "start", "detail": _REFUSAL})
        assert is_open is True
        assert context["detail"] == _REFUSAL

    @pytest.mark.parametrize(
        "action",
        [
            None,
            {"success": True, "command": "start"},
            {"success": False, "command": "pause", "detail": _REFUSAL},
            {"success": False, "command": "start", "detail": _OUTAGE},
            {"success": False, "command": "start", "detail": ""},
        ],
        ids=["no-action", "success", "other-command", "outage", "empty"],
    )
    def test_everything_else_leaves_the_modal_alone(self, dm, action):
        """``no_update`` -- a later unrelated outcome must not close a prompt the operator has not answered."""
        assert dm._open_dataset_shortfall_prompt_handler(action) == (dash.no_update, dash.no_update, dash.no_update)


class TestRestagePayload:
    def test_policy_rides_on_the_generic_params_channel(self):
        pending = {"dataset_type": "equities", "params": {"start_date": "2015-01-01", "symbols": ["KO"]}}
        payload = DashboardManager._restage_payload_with_policy(pending, DATASET_SHORTFALL_OPTIONS["dataset-shortfall-accept-button"])
        assert payload == {"nn_dataset_type": "equities", "nn_dataset_params": {"start_date": "2015-01-01", "symbols": ["KO"], "allow_truncation": True, "incomplete_rows": "accept"}}

    def test_drop_is_the_other_policy_and_typed_fields_map_back(self):
        pending = {"dataset_type": "spirals", "n_samples": 300, "noise": 0.1, "rotations": 2.0, "n_spirals": 2, "unknown_key": 1}
        payload = DashboardManager._restage_payload_with_policy(pending, DATASET_SHORTFALL_OPTIONS["dataset-shortfall-drop-button"])
        assert payload["nn_dataset_type"] == "spirals"
        assert payload["nn_dataset_elements"] == 300 and payload["nn_dataset_noise"] == 0.1
        assert payload["nn_spiral_rotations"] == 2.0 and payload["nn_spiral_number"] == 2
        assert "unknown_key" not in payload
        assert payload["nn_dataset_params"] == {"allow_truncation": True, "incomplete_rows": "drop"}

    def test_an_explicit_prior_refusal_in_the_held_params_is_overridden(self):
        """The prompt's answer must win over whatever polarity the form had sent."""
        pending = {"dataset_type": "equities", "params": {"allow_truncation": False}}
        payload = DashboardManager._restage_payload_with_policy(pending, DATASET_SHORTFALL_OPTIONS["dataset-shortfall-accept-button"])
        assert payload["nn_dataset_params"]["allow_truncation"] is True


class TestResolvePrompt:
    _PENDING = {"pending_dataset": {"dataset_type": "equities", "params": {"start_date": "2015-01-01"}}}

    def test_no_click_is_a_no_op(self, dm):
        assert dm._resolve_dataset_shortfall_handler(triggered_id=None, clicks=(None, None, None), context=None) == (dash.no_update,) * 5
        assert dm._resolve_dataset_shortfall_handler(triggered_id="dataset-shortfall-accept-button", clicks=(None, None, None), context=None) == (dash.no_update,) * 5

    @pytest.mark.parametrize("button, rows", [("dataset-shortfall-accept-button", "accept"), ("dataset-shortfall-drop-button", "drop")])
    def test_accept_and_drop_restage_with_the_opt_in_and_start(self, dm, button, rows):
        with (
            patch("frontend.dashboard_manager.requests.get", return_value=_response(200, self._PENDING)) as get,
            patch("frontend.dashboard_manager.requests.post", side_effect=[_response(200, {"status": "success"}), _response(200, {"status": "started"})]) as post,
        ):
            is_open, alert, action, dropdown, banner = dm._resolve_dataset_shortfall_handler(triggered_id=button, clicks=(1, None, None), context={"detail": _REFUSAL})
        assert get.call_args.args[0].endswith("/api/status")
        stage_call, start_call = post.call_args_list
        assert stage_call.args[0].endswith("/api/stage_dataset")
        assert stage_call.kwargs["json"] == {"nn_dataset_type": "equities", "nn_dataset_params": {"start_date": "2015-01-01", "allow_truncation": True, "incomplete_rows": rows}}
        assert start_call.args[0].endswith("/api/train/start")
        assert is_open is False
        assert action["success"] is True and action["command"] == "start" and action["last"] == button
        assert dropdown is dash.no_update and banner is dash.no_update
        assert "partial" in str(alert)

    def test_a_second_refusal_is_written_back_for_the_alert_and_the_prompt(self, dm):
        """Drop can empty the universe; the follow-up failure rides the same store and re-opens the prompt."""
        second = requests.HTTPError(response=SimpleNamespace(status_code=409, json=lambda: {"detail": _REFUSAL}, text=_REFUSAL))
        failing_start = _response(200)
        failing_start.raise_for_status.side_effect = second
        with (
            patch("frontend.dashboard_manager.requests.get", return_value=_response(200, self._PENDING)),
            patch("frontend.dashboard_manager.requests.post", side_effect=[_response(200, {"status": "success"}), failing_start]),
        ):
            is_open, alert, action, _dropdown, _banner = dm._resolve_dataset_shortfall_handler(triggered_id="dataset-shortfall-drop-button", clicks=(None, 1, None), context=None)
        assert is_open is False and alert is dash.no_update
        assert action["success"] is False
        assert DATASET_SHORTFALL_REFUSAL_MARKER in action["detail_full"]
        assert len(action["detail"]) <= 300
        # ...and the open handler would put the question again.
        assert dm._open_dataset_shortfall_prompt_handler(action)[0] is True

    def test_a_failed_restage_reports_and_starts_nothing(self, dm):
        with (
            patch("frontend.dashboard_manager.requests.get", return_value=_response(200, self._PENDING)),
            patch("frontend.dashboard_manager.requests.post", return_value=_response(502, text="Backend rejected dataset: boom")) as post,
        ):
            is_open, alert, action, _d, _b = dm._resolve_dataset_shortfall_handler(triggered_id="dataset-shortfall-accept-button", clicks=(1, None, None), context=None)
        assert post.call_count == 1, "no Start after a failed re-stage"
        assert is_open is False and action is dash.no_update
        assert "Could not re-stage" in str(alert) and "boom" in str(alert)

    def test_nothing_staged_means_nothing_to_restage(self, dm):
        with (
            patch("frontend.dashboard_manager.requests.get", return_value=_response(200, {"pending_dataset": None})),
            patch("frontend.dashboard_manager.requests.post") as post,
        ):
            is_open, alert, action, _d, _b = dm._resolve_dataset_shortfall_handler(triggered_id="dataset-shortfall-accept-button", clicks=(1, None, None), context=None)
        post.assert_not_called()
        assert is_open is False and action is dash.no_update
        assert "Nothing to re-stage" in str(alert)

    def test_fail_cancels_the_staged_change_and_deselects_the_dataset(self, dm):
        """Option 3 (owner's ruling): cancel the load, deselect the dataset (``⊥``), let the operator pick another."""
        with patch("frontend.dashboard_manager.requests.delete", return_value=_response(200, {"status": "success"})) as delete:
            is_open, alert, action, dropdown, banner = dm._resolve_dataset_shortfall_handler(triggered_id=DATASET_SHORTFALL_FAIL_BUTTON, clicks=(None, None, 1), context=None)
        assert delete.call_args.args[0].endswith("/api/cancel_pending_dataset")
        assert is_open is False
        assert dropdown is None, "the dataset must be deselected, not left pointing at the refused one"
        assert banner is False
        assert action is dash.no_update
        assert "cancelled" in str(alert).lower()

    def test_a_failed_cancel_keeps_the_selection(self, dm):
        with patch("frontend.dashboard_manager.requests.delete", return_value=_response(502, text="cascor unreachable")):
            is_open, alert, _action, dropdown, banner = dm._resolve_dataset_shortfall_handler(triggered_id=DATASET_SHORTFALL_FAIL_BUTTON, clicks=(None, None, 1), context=None)
        assert is_open is False
        assert dropdown is dash.no_update and banner is dash.no_update
        assert "Could not cancel" in str(alert)


class TestPartialDataIsMarkedWhereTheOperatorLooks:
    _SHORTFALL = {"dataset_id": "equities-3.0.0-abc", "accepted_by_this_run": True, "acceptance_source": "request_params", "summary": "14 of 503 symbols imported (cap 14); accepted by the dataset request itself (allow_truncation=true)"}

    @staticmethod
    def _status(**overrides):
        base = {"is_running": True, "is_paused": False, "completed": False, "failed": False, "phase": "output", "current_epoch": 3, "hidden_units": 1, "max_hidden_units": 10}
        base.update(overrides)
        return SimpleNamespace(json=lambda: base)

    def test_status_bar_carries_the_mark_while_running_and_when_complete(self, dm):
        running = dm._build_unified_status_bar_content(self._status(dataset_shortfall=self._SHORTFALL), latency_ms=5.0)
        assert running[3] == "Running · partial data"
        done = dm._build_unified_status_bar_content(self._status(is_running=False, completed=True, completion_reason="residual_collapsed", dataset_shortfall=self._SHORTFALL), latency_ms=5.0)
        assert done[3] == "Completed — converged · partial data"

    def test_status_bar_is_unmarked_on_a_clean_dataset(self, dm):
        assert dm._build_unified_status_bar_content(self._status(dataset_shortfall=None), latency_ms=5.0)[3] == "Running"
        assert dm._build_unified_status_bar_content(self._status(), latency_ms=5.0)[3] == "Running"

    def test_network_info_opens_with_cascor_s_own_sentence(self, dm):
        rendered = str(dm._render_network_info({"dataset_shortfall": self._SHORTFALL, "input_size": 16, "output_size": 3}))
        assert "Partial dataset" in rendered
        assert "14 of 503 symbols imported" in rendered and "accepted by the dataset request itself" in rendered
        assert "equities-3.0.0-abc" in rendered

    def test_network_info_is_unchanged_on_a_clean_dataset(self, dm):
        assert DashboardManager._dataset_shortfall_note_children({"dataset_shortfall": None}) == []
        assert DashboardManager._dataset_shortfall_note_children({}) == []
        assert "Partial dataset" not in str(dm._render_network_info({"input_size": 2, "output_size": 1}))


class TestWiring:
    def test_prompt_callbacks_are_registered(self, dm):
        keys = list(dm.app.callback_map.keys())
        assert any("dataset-shortfall-modal.is_open" in k for k in keys), "open-prompt callback missing"
        assert any("dataset-shortfall-outcome-alert.children" in k for k in keys), "resolve callback missing"

    def test_the_three_buttons_are_callback_inputs(self, dm):
        """L1 control-graph rule: a button read only as State can never fire."""
        inputs = set()
        for entry in dm.app.callback_map.values():
            for inp in entry.get("inputs", []):
                inputs.add(inp.get("id") if isinstance(inp, dict) else getattr(inp, "component_id", None))
        for button in ("dataset-shortfall-accept-button", "dataset-shortfall-drop-button", DATASET_SHORTFALL_FAIL_BUTTON):
            assert button in inputs, f"{button} is not a callback Input"
