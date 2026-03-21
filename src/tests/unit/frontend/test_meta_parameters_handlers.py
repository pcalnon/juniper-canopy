"""
Unit tests for Meta Parameters handler methods in DashboardManager.

Tests the handler logic for tracking parameter changes, applying parameters,
initializing from backend, radio toggle behavior, and cross-section checkbox sync.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest

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
        "cn_multi_cand": [],
        "cn_cand_selection": None,
        "cn_top_cands": 1,
        "cn_random_cands": 1,
        "applied": DEFAULT_APPLIED,
    }
    defaults.update(overrides)
    return defaults


class TestToggleNnGrowthInputs:
    def test_preset_epochs_mode(self, dm):
        result = dm._toggle_nn_growth_inputs_handler("preset_epochs")
        assert result == (False, True)

    def test_convergence_mode(self, dm):
        result = dm._toggle_nn_growth_inputs_handler("convergence")
        assert result == (True, False)


class TestToggleCnTrainingInputs:
    def test_preset_epochs_mode(self, dm):
        result = dm._toggle_cn_training_inputs_handler("preset_epochs")
        assert result == (False, True)

    def test_convergence_mode(self, dm):
        result = dm._toggle_cn_training_inputs_handler("convergence")
        assert result == (True, False)


class TestToggleCnSelectionInputs:
    def test_top_tier_mode(self, dm):
        result = dm._toggle_cn_selection_inputs_handler("top_tier")
        assert result == (False, True)

    def test_random_mode(self, dm):
        result = dm._toggle_cn_selection_inputs_handler("random")
        assert result == (True, False)

    def test_none_disables_both(self, dm):
        result = dm._toggle_cn_selection_inputs_handler(None)
        assert result == (True, True)


class TestToggleCnMultiCandidateSubgroup:
    def test_unchecked_disables_all(self, dm):
        style, top_disabled, random_disabled = dm._toggle_cn_multi_candidate_subgroup_handler([])
        assert top_disabled is True
        assert random_disabled is True

    def test_checked_enables_all(self, dm):
        style, top_disabled, random_disabled = dm._toggle_cn_multi_candidate_subgroup_handler(["enabled"])
        assert top_disabled is False
        assert random_disabled is False


class TestSyncMultiNodeCheckboxes:
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
    def test_no_clicks_returns_no_update(self, dm):
        args = [None] + [None] * 22
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
            [],
            None,
            1,
            1,  # cn checkbox/radio/numeric
        )
        assert result[1] == "✓ Parameters applied"
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
            [],
            None,
            1,
            1,
        )
        assert result[0] is dash.no_update
        assert "Failed" in result[1]


class TestInitParamsFromBackend:
    def test_already_initialized_returns_no_update(self, dm):
        result = dm._init_params_from_backend_handler(1, {"some": "data"})
        assert len(result) == 23
        assert all(r is dash.no_update for r in result)

    @patch("frontend.dashboard_manager.requests.get")
    def test_successful_init(self, mock_get, dm):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={}),
        )
        dm._api_url = MagicMock(return_value="http://test/api/state")
        result = dm._init_params_from_backend_handler(1, {})
        assert len(result) == 23
        # Last element is the applied dict
        assert isinstance(result[-1], dict)
        assert "nn_learning_rate" in result[-1]

    @patch("frontend.dashboard_manager.requests.get")
    def test_failed_init_returns_no_update(self, mock_get, dm):
        mock_get.side_effect = Exception("connection error")
        dm._api_url = MagicMock(return_value="http://test/api/state")
        result = dm._init_params_from_backend_handler(1, {})
        assert len(result) == 23
        assert all(r is dash.no_update for r in result)
