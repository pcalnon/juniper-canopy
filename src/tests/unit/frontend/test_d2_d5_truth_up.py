"""E2E-ledger docs/behaviour truth-up (Phase 4): D-2 and D-5.

* D-2 (matrix C2.9-04, confirmed live at C2.6-05): ``nn-init-output-weights-dropdown``
  travelled on the Apply gather as a ``State`` but sat OUTSIDE the 27-input dirty
  set of ``track_param_changes``, so changing it alone never enabled Apply -- yet
  its value still applied on the next unrelated Apply. It is now a dirty-tracked
  Input and the handler compares it against the applied store's
  ``nn_init_output_weights`` (which the apply handler has always stored).
* D-5 (doc-only): the Phase-D registration comment said the WS-control flag is
  "off (default)" while ``settings.enable_ws_control_buttons`` has defaulted to
  ``True`` since the D-49 flip. The comment now says so.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import dash
import pytest

SRC_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("JUNIPER_CANOPY_DEMO_MODE", "1")

# The 24 positional values every existing caller passes (in Input order), all
# equal to the applied store below so only the field under test can be dirty.
_POSITIONAL = [1000, 200, 0.01, 10, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1]
_APPLIED = {
    "nn_max_iterations": 1000,
    "nn_max_total_epochs": 200,
    "nn_learning_rate": 0.01,
    "nn_max_hidden_units": 10,
    "nn_multi_node_layers": False,
    "nn_growth_trigger": "convergence",
    "nn_growth_preset_epochs": 50,
    "nn_growth_convergence_threshold": 0.001,
    "nn_patience": 50,
    "nn_spiral_rotations": 1.5,
    "nn_spiral_number": 2,
    "nn_dataset_elements": 1000,
    "nn_dataset_noise": 0.25,
    "cn_pool_size": 100,
    "cn_correlation_threshold": 0.001,
    "cn_selected_candidates": 1,
    "cn_training_complete": "preset_epochs",
    "cn_training_iterations": 500,
    "cn_training_convergence_threshold": 0.0001,
    "cn_patience": 30,
    "cn_multi_candidate": False,
    "cn_candidate_selection": None,
    "cn_top_candidates": 1,
    "cn_random_candidates": 1,
    "nn_init_output_weights": "random",
}


@pytest.fixture
def dashboard_manager():
    from frontend.dashboard_manager import DashboardManager

    return DashboardManager({"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}})


@pytest.mark.unit
class TestD2InitOutputWeightsIsDirtyTracked:
    def test_changing_only_init_output_weights_enables_apply(self, dashboard_manager):
        disabled, status = dashboard_manager._track_param_changes_handler(*_POSITIONAL, applied=_APPLIED, nn_init_output_weights="zeros")
        assert disabled is False
        assert status == "⚠️ Unsaved changes"

    def test_same_init_output_weights_stays_clean(self, dashboard_manager):
        disabled, status = dashboard_manager._track_param_changes_handler(*_POSITIONAL, applied=_APPLIED, nn_init_output_weights="random")
        assert disabled is True
        assert status is dash.no_update

    def test_legacy_positional_callers_are_unaffected(self, dashboard_manager):
        # Callers that predate D-2 pass 24 positionals + applied= and nothing for
        # the new field; with no current value and a store lacking the key the
        # comparison is clean, exactly as before.
        legacy = {k: v for k, v in _APPLIED.items() if k != "nn_init_output_weights"}
        disabled, status = dashboard_manager._track_param_changes_handler(*_POSITIONAL, applied=legacy)
        assert disabled is True
        assert status is dash.no_update

    def test_dropdown_is_an_input_of_the_dirty_tracker(self, dashboard_manager):
        specs = [spec for key, spec in dashboard_manager.app.callback_map.items() if "apply-params-button.disabled" in key and "params-status.children" in key]
        assert specs, "the dirty-tracker callback (apply-params-button.disabled + params-status.children) must be registered"
        inputs = {(i["id"], i["property"]) for i in specs[0]["inputs"]}
        assert ("nn-init-output-weights-dropdown", "value") in inputs


@pytest.mark.unit
class TestD2MountHydrationSeedsTheField:
    """The regression the first cut of D-2 introduced (caught by the UI sub-suite):
    the mount hydration seeded a fixed 27-key applied store, so once the tracker
    compared ``nn_init_output_weights`` every fresh session read "unsaved
    changes". The seed now carries the key and hydrates the dropdown."""

    def _hydrate(self, dashboard_manager, state):
        from unittest.mock import MagicMock, patch

        resp = MagicMock(status_code=200)
        resp.json.return_value = state
        with patch("frontend.dashboard_manager.requests.get", return_value=resp):
            return dashboard_manager._init_params_from_backend_handler(1, None)

    def test_seed_carries_the_key_and_hydrates_the_dropdown(self, dashboard_manager):
        result = self._hydrate(dashboard_manager, {"nn_init_output_weights": "zeros"})
        assert len(result) == 29
        assert result[27] == "zeros"  # the hydrated dropdown value
        assert result[-1]["nn_init_output_weights"] == "zeros"  # the applied store stays last

    def test_fresh_session_is_clean_on_mount(self, dashboard_manager):
        from canopy_constants import TrainingConstants

        result = self._hydrate(dashboard_manager, {})
        seeded = result[-1]
        assert seeded["nn_init_output_weights"] == TrainingConstants.DEFAULT_INIT_OUTPUT_WEIGHTS
        current = [seeded[k] for k in ("nn_max_iterations", "nn_max_total_epochs", "nn_learning_rate", "nn_max_hidden_units")]
        current += [["enabled"] if seeded["nn_multi_node_layers"] else []]
        current += [seeded[k] for k in ("nn_growth_trigger", "nn_growth_preset_epochs", "nn_growth_convergence_threshold", "nn_patience", "nn_spiral_rotations", "nn_spiral_number", "nn_dataset_elements", "nn_dataset_noise", "cn_pool_size", "cn_correlation_threshold", "cn_selected_candidates", "cn_training_complete", "cn_training_iterations", "cn_training_convergence_threshold", "cn_patience")]
        current += [["enabled"] if seeded["cn_multi_candidate"] else []]
        current += [seeded[k] for k in ("cn_candidate_selection", "cn_top_candidates", "cn_random_candidates")]
        disabled, status = dashboard_manager._track_param_changes_handler(*current, nn_output_epochs=seeded["nn_output_epochs"], nn_optimizer_type=seeded["nn_optimizer_type"], nn_activation_function=seeded["nn_activation_function_name"], applied=seeded, nn_init_output_weights=result[27])
        assert disabled is True
        assert status is dash.no_update


@pytest.mark.unit
class TestD5PhaseDCommentMatchesTheDefault:
    def test_flag_defaults_on_and_the_comment_says_so(self):
        import frontend.dashboard_manager as dm_module
        from settings import get_settings

        assert get_settings().enable_ws_control_buttons is True
        source = Path(dm_module.__file__).read_text(encoding="utf-8")
        marker = "# automatic REST fallback if the send() promise rejects. When the flag"
        assert marker in source
        tail = source[source.index(marker) : source.index(marker) + 600]
        assert "is off (default)" not in tail
        assert "settings.enable_ws_control_buttons" in tail
