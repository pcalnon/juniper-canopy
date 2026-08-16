"""
Unit tests for Meta Parameters handler methods in DashboardManager.

Tests the handler logic for tracking parameter changes, applying parameters,
initializing from backend, radio toggle behavior, and cross-section checkbox sync.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest

import frontend.dashboard_manager as dashboard_manager_module
from canopy_constants import TrainingConstants
from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    """Create a DashboardManager with mocked dependencies for handler testing."""
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._settings = MagicMock()
    return manager


# Default applied params store for testing
DEFAULT_APPLIED = {
    "nn_max_iterations": 1000,
    "nn_max_total_epochs": 1000000,
    "nn_learning_rate": 0.01,
    "nn_max_hidden_units": 1000,
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
}


def _make_track_args(**overrides):
    """Build default tracking args and apply overrides."""
    defaults = {
        "nn_max_iter": 1000,
        "nn_max_epochs": 1000000,
        "nn_lr": 0.01,
        "nn_max_hu": 1000,
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
        "applied": DEFAULT_APPLIED,
    }
    defaults.update(overrides)
    return defaults


class TestToggleNnGrowthInputs:
    """Tests for neural network growth input toggle callbacks."""

    def test_preset_epochs_mode(self, dm):
        result = dm._toggle_nn_growth_inputs_handler("preset_epochs")
        assert result == (False, True)

    def test_convergence_mode(self, dm):
        result = dm._toggle_nn_growth_inputs_handler("convergence")
        assert result == (True, False)


class TestToggleCnTrainingInputs:
    """Tests for candidate network training input toggle callbacks."""

    def test_preset_epochs_mode(self, dm):
        result = dm._toggle_cn_training_inputs_handler("preset_epochs")
        assert result == (False, True)

    def test_convergence_mode(self, dm):
        result = dm._toggle_cn_training_inputs_handler("convergence")
        assert result == (True, False)


class TestToggleCnSelectionInputs:
    """Tests for candidate network selection input toggle callbacks."""

    def test_top_mode(self, dm):
        """F-CANOPY-022: ``top`` is the shipped value (cascor's literal)."""
        result = dm._toggle_cn_selection_inputs_handler("top")
        assert result == (False, True)

    def test_top_tier_mode(self, dm):
        """F-CANOPY-022: the pre-fix value still gates, for a persisted store."""
        result = dm._toggle_cn_selection_inputs_handler("top_tier")
        assert result == (False, True)

    def test_random_mode(self, dm):
        result = dm._toggle_cn_selection_inputs_handler("random")
        assert result == (True, False)

    def test_none_disables_both(self, dm):
        result = dm._toggle_cn_selection_inputs_handler(None)
        assert result == (True, True)


class TestCandidateSelectionOptionVocabulary:
    """F-CANOPY-022 — the radio's option values must be cascor literals.

    canopy shipped ``top_tier`` while cascor declares
    ``Literal["top", "random", "mixed"]``
    (juniper-cascor ``src/api/models/training.py:159``, ``:327``), so selecting
    "Add Top Tier Candidates" and clicking Apply returned a pydantic
    ``literal_error`` that the dashboard surfaced as HTTP 502 — the option
    could never be applied, while its sibling ``random`` worked because that
    value happened to match. This pins the vocabulary at the layout so the
    mismatch cannot silently return.
    """

    # cascor api/models/training.py:159,:327
    CASCOR_CANDIDATE_SELECTION_LITERALS = {"top", "random", "mixed"}

    @staticmethod
    def _selection_option_values():
        """Read the radio's option values straight out of the layout source.

        The ``dm`` fixture builds a bare ``__new__`` manager, so the layout is
        never constructed and cannot be walked. Parsing the definition with
        ``ast`` pins the shipped literals without needing a live Dash app.
        """
        import ast
        import pathlib

        source_path = pathlib.Path(dashboard_manager_module.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords}
            id_node = kwargs.get("id")
            if not (isinstance(id_node, ast.Constant) and id_node.value == "cn-candidate-selection-radio"):
                continue
            options_node = kwargs.get("options")
            assert isinstance(options_node, ast.List), "cn-candidate-selection-radio options is not a literal list"
            values = set()
            for element in options_node.elts:
                option = ast.literal_eval(element)
                values.add(option["value"])
            return values

        raise AssertionError("cn-candidate-selection-radio not found in dashboard_manager source")

    def test_every_option_value_is_a_cascor_literal(self):
        values = self._selection_option_values()
        assert values, "no option values found"
        assert values <= self.CASCOR_CANDIDATE_SELECTION_LITERALS, f"option values {sorted(values)} are not all cascor literals " f"{sorted(self.CASCOR_CANDIDATE_SELECTION_LITERALS)}"

    def test_top_tier_is_not_shipped(self):
        assert "top_tier" not in self._selection_option_values(), "the rejected pre-fix value is shipped again"


class TestToggleCnMultiCandidateSubgroup:
    """Tests for multi-candidate subgroup toggle callbacks."""

    def test_unchecked_disables_all(self, dm):
        style, top_disabled, random_disabled = dm._toggle_cn_multi_candidate_subgroup_handler([])
        assert top_disabled is True
        assert random_disabled is True

    def test_checked_enables_all(self, dm):
        style, top_disabled, random_disabled = dm._toggle_cn_multi_candidate_subgroup_handler(["enabled"])
        assert top_disabled is False
        assert random_disabled is False


class TestSyncMultiNodeCheckboxes:
    """Tests for multi-node checkbox synchronization callbacks."""

    def test_cn_checked_forces_nn_on(self, dm):
        with patch("frontend.dashboard_manager.dash.callback_context") as mock_ctx:
            mock_ctx.triggered = [{"prop_id": "cn-multi-candidate-checkbox.value"}]
            nn_out, cn_out = dm._sync_multi_node_checkboxes_handler([], ["enabled"])
            assert nn_out == ["enabled"]
            assert cn_out is dash.no_update

    def test_cn_unchecked_does_not_force_nn_off(self, dm):
        with patch("frontend.dashboard_manager.dash.callback_context") as mock_ctx:
            mock_ctx.triggered = [{"prop_id": "cn-multi-candidate-checkbox.value"}]
            nn_out, cn_out = dm._sync_multi_node_checkboxes_handler(["enabled"], [])
            assert nn_out is dash.no_update
            assert cn_out is dash.no_update

    def test_nn_change_does_not_affect_cn(self, dm):
        with patch("frontend.dashboard_manager.dash.callback_context") as mock_ctx:
            mock_ctx.triggered = [{"prop_id": "nn-multi-node-layers-checkbox.value"}]
            nn_out, cn_out = dm._sync_multi_node_checkboxes_handler(["enabled"], [])
            assert nn_out is dash.no_update
            assert cn_out is dash.no_update


class TestTrackParamChanges:
    """Tests for parameter change tracking callbacks."""

    def test_no_changes_returns_disabled(self, dm):
        args = _make_track_args()
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is True
        assert status is dash.no_update

    def test_empty_applied_returns_disabled(self, dm):
        args = _make_track_args(applied={})
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is True
        assert status == ""

    def test_float_change_detected(self, dm):
        args = _make_track_args(nn_lr=0.05)
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is False
        assert "Unsaved" in status

    def test_int_change_detected(self, dm):
        args = _make_track_args(nn_max_iter=2000)
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is False

    def test_radio_change_detected(self, dm):
        args = _make_track_args(nn_growth_trigger="preset_epochs")
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is False

    def test_checkbox_change_detected(self, dm):
        args = _make_track_args(nn_multi_node=["enabled"])
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is False

    def test_cn_change_detected(self, dm):
        args = _make_track_args(cn_pool_size=200)
        disabled, status = dm._track_param_changes_handler(**args)
        assert disabled is False


class TestApplyParameters:
    """Tests for apply-parameters button callback."""

    def test_no_clicks_returns_no_update(self, dm):
        args = [None] + [None] * 24
        result = dm._apply_parameters_handler(*args)
        assert result == (dash.no_update, dash.no_update)

    @patch("frontend.dashboard_manager.requests.post")
    def test_successful_apply(self, mock_post, dm):
        mock_post.return_value = MagicMock(status_code=200)
        dm._api_url = MagicMock(return_value="http://test/api/set_params")
        result = dm._apply_parameters_handler(
            1,  # n_clicks
            1000,
            1000000,
            0.01,
            1000,  # nn numeric
            [],
            "convergence",
            50,
            0.001,  # nn checkbox/radio/numeric
            50,  # nn_patience
            1.5,
            2,
            1000,
            0.25,  # nn spiral/dataset
            100,
            0.001,
            1,  # cn numeric
            "preset_epochs",
            500,
            0.0001,  # cn radio/numeric
            30,  # cn_patience
            [],
            None,
            1,
            1,  # cn checkbox/radio/numeric
        )
        assert result[1] == "Parameters applied"
        assert isinstance(result[0], dict)
        assert "nn_learning_rate" in result[0]
        assert "cn_pool_size" in result[0]

    @patch("frontend.dashboard_manager.requests.post")
    def test_failed_apply(self, mock_post, dm):
        mock_post.return_value = MagicMock(status_code=500, text="error")
        dm._api_url = MagicMock(return_value="http://test/api/set_params")
        result = dm._apply_parameters_handler(
            1,
            1000,
            1000000,
            0.01,
            1000,
            [],
            "convergence",
            50,
            0.001,
            50,  # nn_patience
            1.5,
            2,
            1000,
            0.25,
            100,
            0.001,
            1,
            "preset_epochs",
            500,
            0.0001,
            30,  # cn_patience
            [],
            None,
            1,
            1,
        )
        assert result[0] is dash.no_update
        assert "Failed" in result[1]


class TestInitParamsFromBackend:
    """Tests for initial parameter loading from backend."""

    def test_already_initialized_returns_no_update(self, dm):
        result = dm._init_params_from_backend_handler(1, {"some": "data"})
        # NUM_OUTPUTS=28 since canopy#204/205/206 added output_epochs /
        # optimizer_type / activation_function to the handler.
        assert len(result) == 28
        assert all(r is dash.no_update for r in result)

    @patch("frontend.dashboard_manager.requests.get")
    def test_successful_init(self, mock_get, dm):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={}),
        )
        dm._api_url = MagicMock(return_value="http://test/api/state")
        result = dm._init_params_from_backend_handler(1, {})
        # NUM_OUTPUTS=28 since canopy#204/205/206.
        assert len(result) == 28
        # Last element is the applied dict
        assert isinstance(result[-1], dict)
        assert "nn_learning_rate" in result[-1]

    @patch("frontend.dashboard_manager.requests.get")
    def test_failed_init_returns_no_update(self, mock_get, dm):
        mock_get.side_effect = Exception("connection error")
        dm._api_url = MagicMock(return_value="http://test/api/state")
        result = dm._init_params_from_backend_handler(1, {})
        # NUM_OUTPUTS=28 since canopy#204/205/206.
        assert len(result) == 28
        assert all(r is dash.no_update for r in result)
