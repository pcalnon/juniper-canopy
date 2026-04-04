#!/usr/bin/env python
"""
Integration tests for Meta-Parameters Apply Button functionality.

Tests the complete flow of applying parameter changes from frontend to backend,
verifying the fix for P0-2: Meta-Parameters Apply Button issue.

Key scenarios tested:
1. Apply button sends correct payload keys to API
2. Parameters are persisted in TrainingState
3. Parameters are applied to demo mode instance
4. Change detection works correctly with applied values
5. Full round-trip from UI to backend and back
"""

from unittest.mock import Mock, patch

import pytest

from backend.training_monitor import TrainingState
from demo_mode import DemoMode


@pytest.fixture
def training_state():
    """Fresh training state for each test."""
    return TrainingState()


@pytest.fixture
def demo_mode():
    """Fresh demo mode for each test."""
    demo = DemoMode(update_interval=0.1)
    yield demo
    if demo.is_running:
        demo.stop()


class TestApplyButtonParameterKeys:
    """Verify correct parameter keys are used throughout the flow."""

    def test_training_state_accepts_max_epochs(self, training_state):
        """TrainingState should accept and store max_epochs field."""
        training_state.update_state(max_epochs=300)
        state = training_state.get_state()
        assert "max_epochs" in state
        assert state["max_epochs"] == 300

    def test_training_state_accepts_all_params(self, training_state):
        """TrainingState should accept all three parameter fields."""
        training_state.update_state(
            learning_rate=0.05,
            max_hidden_units=15,
            max_epochs=500,
        )
        state = training_state.get_state()
        assert state["learning_rate"] == 0.05
        assert state["max_hidden_units"] == 15
        assert state["max_epochs"] == 500

    def test_demo_mode_apply_params_all_fields(self, demo_mode):
        """DemoMode.apply_params should handle all three parameters."""
        demo_mode.apply_params(
            learning_rate=0.03,
            max_hidden_units=20,
            max_epochs=400,
        )

        assert demo_mode.network.learning_rate == 0.03
        assert demo_mode.max_hidden_units == 20
        assert demo_mode.max_epochs == 400


class TestApplyButtonApiIntegration:
    """Test the API endpoint correctly processes parameter updates."""

    @pytest.mark.asyncio
    async def test_set_params_endpoint_updates_training_state(self, client):
        """POST /api/set_params should update TrainingState with all params."""
        response = client.post(
            "/api/set_params",
            json={
                "learning_rate": 0.025,
                "max_hidden_units": 12,
                "max_epochs": 350,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        state = data["state"]
        assert state["learning_rate"] == 0.025
        assert state["max_hidden_units"] == 12
        assert state["max_epochs"] == 350

    @pytest.mark.asyncio
    async def test_set_params_rejects_empty_params(self, client):
        """POST /api/set_params should reject empty parameter dict."""
        response = client.post("/api/set_params", json={})

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "No parameters provided" in data["error"]

    @pytest.mark.asyncio
    async def test_api_state_returns_max_epochs(self, client):
        """GET /api/state should include max_epochs field."""
        response = client.get("/api/state")

        assert response.status_code == 200
        state = response.json()
        assert "max_epochs" in state

    @pytest.mark.asyncio
    async def test_set_params_partial_update(self, client):
        """POST /api/set_params should handle partial updates."""
        response = client.post(
            "/api/set_params",
            json={"max_hidden_units": 8},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["state"]["max_hidden_units"] == 8


class TestApplyButtonDashboardIntegration:
    """Test dashboard handler methods with correct parameter keys."""

    def test_apply_handler_uses_correct_keys(self, reset_singletons):
        """_apply_parameters_handler should use max_hidden_units and max_epochs keys."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            builder = EnvironBuilder(
                method="GET",
                base_url="http://localhost:8050/dashboard/",
                path="/dashboard/",
            )
            env = builder.get_environ()

            with manager.app.server.request_context(env):
                params, status = manager._apply_parameters_handler(
                    n_clicks=1,
                    nn_max_iter=1000,
                    nn_max_epochs=600,
                    nn_lr=0.015,
                    nn_max_hu=25,
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

            assert "nn_max_hidden_units" in params
            assert "nn_max_total_epochs" in params
            assert params["nn_max_hidden_units"] == 25
            assert params["nn_max_total_epochs"] == 600

            call_args = mock_post.call_args
            json_payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert "nn_max_hidden_units" in json_payload
            assert "nn_max_total_epochs" in json_payload
            assert "hidden_units" not in json_payload
            assert "epochs" not in json_payload

    def test_track_param_changes_uses_correct_keys(self, reset_singletons):
        """_track_param_changes_handler should compare against correct keys."""
        import dash

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

        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            0.01,
            15,
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

        disabled, status = manager._track_param_changes_handler(
            1000,
            300,
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
        assert disabled is False
        assert "Unsaved" in status

    def test_track_param_changes_float_tolerance(self, reset_singletons):
        """_track_param_changes_handler should use float tolerance for learning_rate.

        This test verifies the fix for P0-12 where float precision issues could
        cause incorrect change detection for learning_rate values.
        """
        import dash

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {
            "nn_learning_rate": 0.06,
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

        # Float precision error that occurs after multiple step increments
        # e.g., 0.01 + 0.001 * 50 = 0.06000000000000004
        lr_with_precision_error = 0.06000000000000004
        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            lr_with_precision_error,
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
        assert disabled is True, f"Should be disabled but got {disabled} for {lr_with_precision_error}"
        assert status is dash.no_update, f"Should be no_update but got '{status}'"

    def test_track_param_changes_learning_rate_actual_change(self, reset_singletons):
        """_track_param_changes_handler should detect actual learning_rate changes."""
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

        # Significant change should be detected
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

        # Another significant change
        disabled, status = manager._track_param_changes_handler(
            1000,
            200,
            0.001,
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

    def test_init_params_from_backend_uses_correct_keys(self, reset_singletons):
        """_init_params_from_backend_handler should use max_hidden_units and max_epochs."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "nn_learning_rate": 0.02,
                "nn_max_hidden_units": 18,
                "nn_max_total_epochs": 250,
                "nn_growth_trigger": "convergence",
                "nn_growth_convergence_threshold": 0.001,
            }
            mock_get.return_value = mock_response

            builder = EnvironBuilder(
                method="GET",
                base_url="http://localhost:8050/dashboard/",
                path="/dashboard/",
            )
            env = builder.get_environ()

            with manager.app.server.request_context(env):
                result = manager._init_params_from_backend_handler(n=1, current_applied=None)

            # Result is a 25-tuple: (...24 values..., applied_dict)
            applied = result[24]
            assert "nn_max_hidden_units" in applied
            assert "nn_max_total_epochs" in applied
            assert "nn_growth_trigger" in applied
            assert "nn_growth_convergence_threshold" in applied
            assert "hidden_units" not in applied
            assert "epochs" not in applied


class TestLearningRateApplyButtonP012:
    """Tests for P0-12: Learning Rate Meta-parameter Apply Button fix.

    These tests verify that the learning_rate parameter is correctly applied
    when the user clicks the Apply button, addressing the P0-12 bug where
    learning_rate updates were not being applied while max_epochs and
    max_hidden_units worked correctly.
    """

    def test_learning_rate_apply_via_api(self, client, reset_singletons):
        """Learning rate should be applied correctly via /api/set_params."""
        response = client.post(
            "/api/set_params",
            json={"learning_rate": 0.07},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["state"]["learning_rate"] == 0.07

    def test_learning_rate_persists_after_apply(self, client, reset_singletons):
        """Learning rate should persist after being applied."""
        client.post("/api/set_params", json={"learning_rate": 0.123})
        state = client.get("/api/state").json()
        assert state["learning_rate"] == 0.123

    def test_learning_rate_multiple_updates(self, client, reset_singletons):
        """Learning rate should be correctly updated multiple times."""
        for lr in [0.01, 0.05, 0.001, 0.15, 0.02]:
            client.post("/api/set_params", json={"learning_rate": lr})
            state = client.get("/api/state").json()
            assert state["learning_rate"] == lr, f"Expected {lr}, got {state['learning_rate']}"

    def test_learning_rate_with_other_params(self, client, reset_singletons):
        """Learning rate should be applied correctly alongside other params."""
        response = client.post(
            "/api/set_params",
            json={
                "learning_rate": 0.035,
                "max_hidden_units": 15,
                "max_epochs": 300,
            },
        )
        assert response.status_code == 200
        state = response.json()["state"]
        assert state["learning_rate"] == 0.035
        assert state["max_hidden_units"] == 15
        assert state["max_epochs"] == 300

    def test_learning_rate_small_values(self, client, reset_singletons):
        """Learning rate should handle small values correctly."""
        for lr in [0.001, 0.0001, 0.00001]:
            client.post("/api/set_params", json={"learning_rate": lr})
            state = client.get("/api/state").json()
            # Use approximate comparison for very small floats
            assert abs(state["learning_rate"] - lr) < 1e-10, f"Expected ~{lr}, got {state['learning_rate']}"

    def test_learning_rate_handler_uses_correct_payload(self, reset_singletons):
        """Dashboard handler should send correct learning_rate in payload."""
        from unittest.mock import Mock, patch

        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            builder = EnvironBuilder(
                method="GET",
                base_url="http://localhost:8050/dashboard/",
                path="/dashboard/",
            )
            env = builder.get_environ()

            with manager.app.server.request_context(env):
                params, status = manager._apply_parameters_handler(
                    n_clicks=1,
                    nn_max_iter=1000,
                    nn_max_epochs=200,
                    nn_lr=0.07,
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

            # Verify the returned params contain correct learning_rate
            assert params["nn_learning_rate"] == 0.07

            # Verify the payload sent to backend contains correct learning_rate
            call_args = mock_post.call_args
            json_payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert json_payload["nn_learning_rate"] == 0.07


class TestApplyButtonRoundTrip:
    """Test complete round-trip of parameter application."""

    def test_parameters_persist_after_apply(self, client, reset_singletons):
        """Parameters should persist after being applied."""
        response = client.post(
            "/api/set_params",
            json={
                "learning_rate": 0.045,
                "max_hidden_units": 22,
                "max_epochs": 450,
            },
        )
        assert response.status_code == 200

        state_response = client.get("/api/state")
        assert state_response.status_code == 200

        state = state_response.json()
        assert state["learning_rate"] == 0.045
        assert state["max_hidden_units"] == 22
        assert state["max_epochs"] == 450

    def test_multiple_apply_operations(self, client, reset_singletons):
        """Multiple apply operations should each persist correctly."""
        client.post("/api/set_params", json={"learning_rate": 0.01})
        state1 = client.get("/api/state").json()
        assert state1["learning_rate"] == 0.01

        client.post("/api/set_params", json={"learning_rate": 0.02})
        state2 = client.get("/api/state").json()
        assert state2["learning_rate"] == 0.02

        client.post("/api/set_params", json={"max_epochs": 500})
        state3 = client.get("/api/state").json()
        assert state3["max_epochs"] == 500


class TestConvergenceStateEndpoint:
    """Tests for /api/state including convergence parameters (Phase 5.2 fix)."""

    @pytest.mark.asyncio
    async def test_api_state_includes_convergence_enabled(self, client):
        """/api/state should include convergence_enabled field."""
        response = client.get("/api/state")
        assert response.status_code == 200
        state = response.json()
        assert "convergence_enabled" in state

    @pytest.mark.asyncio
    async def test_api_state_includes_convergence_threshold(self, client):
        """/api/state should include convergence_threshold field."""
        response = client.get("/api/state")
        assert response.status_code == 200
        state = response.json()
        assert "convergence_threshold" in state

    @pytest.mark.asyncio
    async def test_api_state_convergence_reflects_set_params(self, client):
        """/api/state should reflect convergence params changed via /api/set_params."""
        client.post("/api/set_params", json={"convergence_enabled": False, "convergence_threshold": 0.05})
        state = client.get("/api/state").json()
        assert state["convergence_enabled"] is False
        assert state["convergence_threshold"] == 0.05

    @pytest.mark.asyncio
    async def test_api_state_convergence_defaults(self, client):
        """/api/state convergence params should have correct defaults after reset."""
        # Reset to defaults before checking
        client.post("/api/set_params", json={"convergence_enabled": True, "convergence_threshold": 0.001})
        state = client.get("/api/state").json()
        assert state["convergence_enabled"] is True
        assert state["convergence_threshold"] == 0.001


class TestConvergenceApplyRoundTrip:
    """Tests verifying checkbox/threshold don't revert after Apply (Phase 5.2 fixes)."""

    def test_apply_with_convergence_disabled_stores_false(self, reset_singletons):
        """Applying with unchecked checkbox stores convergence_enabled=False in params store."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            builder = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/")
            env = builder.get_environ()

            with manager.app.server.request_context(env):
                params, status = manager._apply_parameters_handler(
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
            assert status == "Parameters applied"

    def test_apply_with_custom_threshold_stores_value(self, reset_singletons):
        """Applying with edited threshold stores the user's value, not the default."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            builder = EnvironBuilder(method="GET", base_url="http://localhost:8050/dashboard/", path="/dashboard/")
            env = builder.get_environ()

            with manager.app.server.request_context(env):
                params, status = manager._apply_parameters_handler(
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

    def test_track_changes_after_apply_disabled_convergence(self, reset_singletons):
        """After applying with multi-node disabled, track_param_changes detects no diff."""
        import dash

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

    def test_track_changes_detects_growth_trigger_change(self, reset_singletons):
        """track_param_changes detects growth trigger change."""
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
            "preset_epochs",
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

    def test_track_changes_detects_threshold_change(self, reset_singletons):
        """track_param_changes detects convergence threshold change."""
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
        assert disabled is False
        assert "Unsaved" in status
