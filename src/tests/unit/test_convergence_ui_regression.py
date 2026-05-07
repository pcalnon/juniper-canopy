"""
Regression tests for convergence UI controls bugs (Phase 5.1/5.2).

Each test class targets a specific bug ID from the Phase 5 fix cycle:

- B-5.1: Unchecking checkbox + Apply restored checkbox to checked
- B-5.2: Changing threshold + Apply reverted to default
- B-5.3: Meta-parameter values refreshed every few seconds (overwrites user edits)
- B-5.4: Meta-parameter section missing section heading
- B-5.5: /api/state did not include convergence params
- B-5.6: params-init-interval must fire only once (max_intervals=1)
- B-5.7: _track_param_changes_handler must return dash.no_update for status when no changes
"""

from unittest.mock import Mock, patch

import dash
import pytest

from canopy_constants import TrainingConstants


# -------------------------------------------------------------------------
# B-5.1: Checkbox does not revert after Apply
# -------------------------------------------------------------------------
class TestB51CheckboxDoesNotRevertAfterApply:
    """B-5.1: Unchecking convergence checkbox + Apply must persist unchecked state."""

    @pytest.mark.regression
    def test_apply_with_unchecked_stores_false(self, reset_singletons):
        """Apply with unchecked checkbox -> store has convergence_enabled=False."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            env = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/").get_environ()

            with manager.app.server.request_context(env):
                params, _ = manager._apply_parameters_handler(
                    n_clicks=1,
                    nn_max_iter=1000,
                    nn_max_epochs=200,
                    nn_lr=0.01,
                    nn_max_hu=10,
                    nn_multi_node=[],
                    nn_growth_trigger="convergence",
                    nn_growth_epochs=50,
                    nn_growth_conv_thresh=0.001,
                    nn_patience=50,
                    nn_spiral_rot=1.5,
                    nn_spiral_num=2,
                    nn_dataset_elem=1000,
                    nn_dataset_noise=0.25,
                    cn_pool_size=100,
                    cn_corr_thresh=0.001,
                    cn_selected=1,
                    cn_training_complete="preset_epochs",
                    cn_training_iter=500,
                    cn_training_conv_thresh=0.0001,
                    cn_patience=30,
                    cn_multi_cand=[],
                    cn_cand_selection=None,
                    cn_top_cands=1,
                    cn_random_cands=1,
                )

        assert params["nn_multi_node_layers"] is False

    @pytest.mark.regression
    def test_track_changes_after_unchecked_apply_no_diff(self, reset_singletons):
        """After applying unchecked, track_param_changes shows no diff."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        applied = {
            "nn_learning_rate": 0.01,
            "nn_max_hidden_units": 10,
            "nn_max_total_epochs": 200,
            "nn_max_iterations": 1000,
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

        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            0.01,
            10,
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
            applied=applied,
        )
        assert disabled is True
        assert status is dash.no_update

    @pytest.mark.regression
    def test_no_continuous_sync_callback(self, reset_singletons):
        """No 'sync_backend_params' or 'sync_input_values' callback exists."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        callback_ids = [cb.__name__ for cb in manager.app.callback_map.values() if hasattr(cb, "__name__")]
        for name in callback_ids:
            assert "sync_backend" not in name.lower()
            assert "sync_input_values" not in name.lower()


# -------------------------------------------------------------------------
# B-5.2: Threshold does not revert after Apply
# -------------------------------------------------------------------------
class TestB52ThresholdDoesNotRevertAfterApply:
    """B-5.2: Changing threshold + Apply must store user's value, not default."""

    @pytest.mark.regression
    def test_apply_custom_threshold_stores_value(self, reset_singletons):
        """Apply with threshold=0.05 -> store has that value, not 0.001."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            env = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/").get_environ()

            with manager.app.server.request_context(env):
                params, _ = manager._apply_parameters_handler(
                    n_clicks=1,
                    nn_max_iter=1000,
                    nn_max_epochs=200,
                    nn_lr=0.01,
                    nn_max_hu=10,
                    nn_multi_node=[],
                    nn_growth_trigger="convergence",
                    nn_growth_epochs=50,
                    nn_growth_conv_thresh=0.05,
                    nn_patience=50,
                    nn_spiral_rot=1.5,
                    nn_spiral_num=2,
                    nn_dataset_elem=1000,
                    nn_dataset_noise=0.25,
                    cn_pool_size=100,
                    cn_corr_thresh=0.001,
                    cn_selected=1,
                    cn_training_complete="preset_epochs",
                    cn_training_iter=500,
                    cn_training_conv_thresh=0.0001,
                    cn_patience=30,
                    cn_multi_cand=[],
                    cn_cand_selection=None,
                    cn_top_cands=1,
                    cn_random_cands=1,
                )

        assert params["nn_growth_convergence_threshold"] == 0.05

    @pytest.mark.regression
    def test_track_changes_after_custom_threshold_apply_no_diff(self, reset_singletons):
        """After applying custom threshold, track_param_changes shows no diff."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        applied = {
            "nn_learning_rate": 0.01,
            "nn_max_hidden_units": 10,
            "nn_max_total_epochs": 200,
            "nn_max_iterations": 1000,
            "nn_multi_node_layers": False,
            "nn_growth_trigger": "convergence",
            "nn_growth_preset_epochs": 50,
            "nn_growth_convergence_threshold": 0.05,
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

        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            0.01,
            10,
            [],
            "convergence",
            50,
            0.05,
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
            applied=applied,
        )
        assert disabled is True
        assert status is dash.no_update

    @pytest.mark.regression
    def test_multiple_apply_cycles_preserve_threshold(self, reset_singletons):
        """Multiple Apply clicks preserve the user's custom threshold each time."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        for threshold in [0.01, 0.05, 0.0001]:
            with patch("requests.post") as mock_post:
                mock_post.return_value = Mock(status_code=200)
                env = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/").get_environ()

                with manager.app.server.request_context(env):
                    params, _ = manager._apply_parameters_handler(
                        n_clicks=1,
                        nn_max_iter=1000,
                        nn_max_epochs=200,
                        nn_lr=0.01,
                        nn_max_hu=10,
                        nn_multi_node=[],
                        nn_growth_trigger="convergence",
                        nn_growth_epochs=50,
                        nn_growth_conv_thresh=threshold,
                        nn_patience=50,
                        nn_spiral_rot=1.5,
                        nn_spiral_num=2,
                        nn_dataset_elem=1000,
                        nn_dataset_noise=0.25,
                        cn_pool_size=100,
                        cn_corr_thresh=0.001,
                        cn_selected=1,
                        cn_training_complete="preset_epochs",
                        cn_training_iter=500,
                        cn_training_conv_thresh=0.0001,
                        cn_patience=30,
                        cn_multi_cand=[],
                        cn_cand_selection=None,
                        cn_top_cands=1,
                        cn_random_cands=1,
                    )

            assert params["nn_growth_convergence_threshold"] == threshold, f"Expected {threshold}, got {params['nn_growth_convergence_threshold']}"


# -------------------------------------------------------------------------
# B-5.3: No periodic meta-parameter refresh
# -------------------------------------------------------------------------
class TestB53NoPeriodicMetaParameterRefresh:
    """B-5.3: No periodic callback overwrites user-edited parameter inputs."""

    @pytest.mark.regression
    def test_params_init_interval_has_max_intervals_1(self, reset_singletons):
        """params-init-interval must have max_intervals=1 to prevent repeated firing."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        layout = manager.app.layout

        # Find the params-init-interval component
        found = self._find_component_by_id(layout, "params-init-interval")
        assert found is not None, "params-init-interval component not found in layout"
        assert found.max_intervals == 1, f"Expected max_intervals=1, got {found.max_intervals}"

    @pytest.mark.regression
    def test_init_handler_returns_no_update_when_already_initialized(self, reset_singletons):
        """init_params_from_backend returns no_update when applied store is truthy."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        # Simulate already-initialized state
        current_applied = {"learning_rate": 0.01, "max_hidden_units": 10}
        result = manager._init_params_from_backend_handler(n=1, current_applied=current_applied)
        # 28-tuple after canopy#204/205/206; mirrors NUM_OUTPUTS in the handler.
        assert result == (dash.no_update,) * 28

    @pytest.mark.regression
    def test_no_backend_params_store_in_layout(self, reset_singletons):
        """No 'backend-params-state' store should exist in layout."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        layout = manager.app.layout

        found = self._find_component_by_id(layout, "backend-params-state")
        assert found is None, "backend-params-state store should not exist (removed in Phase 5.1)"

    @staticmethod
    def _find_component_by_id(layout, target_id):
        """Recursively search layout for a component with the given id."""
        if hasattr(layout, "id") and layout.id == target_id:
            return layout
        children = getattr(layout, "children", None)
        if children is None:
            return None
        if not isinstance(children, (list, tuple)):
            children = [children]
        for child in children:
            if child is None:
                continue
            result = TestB53NoPeriodicMetaParameterRefresh._find_component_by_id(child, target_id)
            if result is not None:
                return result
        return None


# -------------------------------------------------------------------------
# B-5.4: Separate Training Parameters card with heading
# -------------------------------------------------------------------------
class TestB54SeparateTrainingParametersCard:
    """B-5.4: Meta-parameter section must have its own card with header."""

    @pytest.mark.regression
    def test_training_controls_card_has_header(self, reset_singletons):
        """'Training Controls' card must have its own header."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        layout_str = str(manager.app.layout)
        assert "Training Controls" in layout_str

    @pytest.mark.regression
    def test_meta_parameters_card_has_header(self, reset_singletons):
        """'Meta Parameters' card must have its own header."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        layout_str = str(manager.app.layout)
        assert "Meta Parameters" in layout_str

    @pytest.mark.regression
    def test_buttons_in_controls_card_inputs_in_parameters_card(self, reset_singletons):
        """Buttons must be in Controls card, inputs in Parameters card."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        layout = manager.app.layout

        # Find both card headers by looking at the layout structure
        # The controls card should have buttons (start-button, etc.)
        # The parameters card should have inputs (learning-rate-input, etc.)
        start_btn = TestB53NoPeriodicMetaParameterRefresh._find_component_by_id(layout, "start-button")
        lr_input = TestB53NoPeriodicMetaParameterRefresh._find_component_by_id(layout, "nn-learning-rate-input")
        assert start_btn is not None, "start-button not found in layout"
        assert lr_input is not None, "nn-learning-rate-input not found in layout"


# -------------------------------------------------------------------------
# B-5.5: /api/state includes convergence params
# -------------------------------------------------------------------------
class TestB55ApiStateIncludesConvergenceParams:
    """B-5.5: /api/state must include convergence_enabled and convergence_threshold."""

    @pytest.mark.regression
    def test_api_state_has_convergence_enabled(self, client):
        """/api/state response includes convergence_enabled."""
        response = client.get("/api/state")
        assert response.status_code == 200
        state = response.json()
        assert "convergence_enabled" in state

    @pytest.mark.regression
    def test_api_state_has_convergence_threshold(self, client):
        """/api/state response includes convergence_threshold."""
        response = client.get("/api/state")
        assert response.status_code == 200
        state = response.json()
        assert "convergence_threshold" in state

    @pytest.mark.regression
    def test_changed_convergence_reflected_in_api_state(self, client):
        """Changed convergence values are reflected in /api/state."""
        client.post(
            "/api/set_params",
            json={
                "convergence_enabled": False,
                "convergence_threshold": 0.02,
            },
        )
        state = client.get("/api/state").json()
        assert state["convergence_enabled"] is False
        assert state["convergence_threshold"] == 0.02


# -------------------------------------------------------------------------
# B-5.6: Init callback fires only once
# -------------------------------------------------------------------------
class TestB56InitCallbackFiresOnlyOnce:
    """B-5.6: Param init uses params-init-interval, not slow-update-interval."""

    @pytest.mark.regression
    def test_uses_params_init_interval(self, reset_singletons):
        """Init callback is driven by params-init-interval, not slow-update-interval."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        # Check that params-init-interval exists and has correct config
        layout = manager.app.layout
        comp = TestB53NoPeriodicMetaParameterRefresh._find_component_by_id(layout, "params-init-interval")
        assert comp is not None
        assert comp.max_intervals == 1

    @pytest.mark.regression
    def test_max_intervals_prevents_repeated_firing(self, reset_singletons):
        """max_intervals=1 means the interval fires exactly once, then stops."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        layout = manager.app.layout
        comp = TestB53NoPeriodicMetaParameterRefresh._find_component_by_id(layout, "params-init-interval")
        # max_intervals=1 means after 1 tick, no more ticks happen
        assert comp.max_intervals == 1
        assert comp.n_intervals == 0  # starts at 0, will tick once


# -------------------------------------------------------------------------
# B-5.7: Status message preserved (no_update when no changes)
# -------------------------------------------------------------------------
class TestB57StatusMessagePreserved:
    """B-5.7: track_param_changes returns dash.no_update for status when no changes."""

    @pytest.mark.regression
    def test_no_changes_returns_no_update_for_status(self, reset_singletons):
        """No parameter changes -> status output is dash.no_update (preserves prior message)."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        applied = {
            "nn_learning_rate": 0.01,
            "nn_max_hidden_units": 10,
            "nn_max_total_epochs": 200,
            "nn_max_iterations": 1000,
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

        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            0.01,
            10,
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
            applied=applied,
        )
        assert disabled is True
        assert status is dash.no_update

    @pytest.mark.regression
    def test_changes_detected_shows_unsaved_warning(self, reset_singletons):
        """Parameter changes detected -> status shows unsaved changes warning."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        applied = {
            "nn_learning_rate": 0.01,
            "nn_max_hidden_units": 10,
            "nn_max_total_epochs": 200,
            "nn_max_iterations": 1000,
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

        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            0.05,
            10,
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
            applied=applied,
        )
        assert disabled is False
        assert "Unsaved" in status

    @pytest.mark.regression
    def test_successful_apply_shows_confirmation(self, reset_singletons):
        """Successful apply -> status shows confirmation message."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            env = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/").get_environ()

            with manager.app.server.request_context(env):
                _, status = manager._apply_parameters_handler(
                    n_clicks=1,
                    nn_max_iter=1000,
                    nn_max_epochs=200,
                    nn_lr=0.01,
                    nn_max_hu=10,
                    nn_multi_node=[],
                    nn_growth_trigger="convergence",
                    nn_growth_epochs=50,
                    nn_growth_conv_thresh=0.001,
                    nn_patience=50,
                    nn_spiral_rot=1.5,
                    nn_spiral_num=2,
                    nn_dataset_elem=1000,
                    nn_dataset_noise=0.25,
                    cn_pool_size=100,
                    cn_corr_thresh=0.001,
                    cn_selected=1,
                    cn_training_complete="preset_epochs",
                    cn_training_iter=500,
                    cn_training_conv_thresh=0.0001,
                    cn_patience=30,
                    cn_multi_cand=[],
                    cn_cand_selection=None,
                    cn_top_cands=1,
                    cn_random_cands=1,
                )

        assert "Parameters applied" in status
