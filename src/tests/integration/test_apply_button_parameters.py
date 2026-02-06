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
                params, status = manager._apply_parameters_handler(n_clicks=1, lr=0.015, hu=25, epochs=600)

            assert "max_hidden_units" in params
            assert "max_epochs" in params
            assert params["max_hidden_units"] == 25
            assert params["max_epochs"] == 600

            call_args = mock_post.call_args
            json_payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert "max_hidden_units" in json_payload
            assert "max_epochs" in json_payload
            assert "hidden_units" not in json_payload
            assert "epochs" not in json_payload

    def test_track_param_changes_uses_correct_keys(self, reset_singletons):
        """_track_param_changes_handler should compare against correct keys."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {
            "learning_rate": 0.01,
            "max_hidden_units": 10,
            "max_epochs": 200,
        }

        disabled, status = manager._track_param_changes_handler(lr=0.01, hu=10, epochs=200, applied=applied)
        assert disabled is True
        assert status == ""

        disabled, status = manager._track_param_changes_handler(lr=0.01, hu=15, epochs=200, applied=applied)
        assert disabled is False
        assert "Unsaved" in status

        disabled, status = manager._track_param_changes_handler(lr=0.01, hu=10, epochs=300, applied=applied)
        assert disabled is False
        assert "Unsaved" in status

    def test_track_param_changes_float_tolerance(self, reset_singletons):
        """_track_param_changes_handler should use float tolerance for learning_rate.

        This test verifies the fix for P0-12 where float precision issues could
        cause incorrect change detection for learning_rate values.
        """
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {
            "learning_rate": 0.06,
            "max_hidden_units": 10,
            "max_epochs": 200,
        }

        # Float precision error that occurs after multiple step increments
        # e.g., 0.01 + 0.001 * 50 = 0.06000000000000004
        lr_with_precision_error = 0.06000000000000004
        disabled, status = manager._track_param_changes_handler(lr=lr_with_precision_error, hu=10, epochs=200, applied=applied)
        assert disabled is True, f"Should be disabled but got {disabled} for {lr_with_precision_error}"
        assert status == "", f"Should have no status but got '{status}'"

    def test_track_param_changes_learning_rate_actual_change(self, reset_singletons):
        """_track_param_changes_handler should detect actual learning_rate changes."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {
            "learning_rate": 0.01,
            "max_hidden_units": 10,
            "max_epochs": 200,
        }

        # Significant change should be detected
        disabled, status = manager._track_param_changes_handler(lr=0.05, hu=10, epochs=200, applied=applied)
        assert disabled is False
        assert "Unsaved" in status

        # Another significant change
        disabled, status = manager._track_param_changes_handler(lr=0.001, hu=10, epochs=200, applied=applied)
        assert disabled is False
        assert "Unsaved" in status

    def test_init_applied_params_uses_correct_keys(self, reset_singletons):
        """_init_applied_params_handler should use max_hidden_units and max_epochs."""
        from werkzeug.test import EnvironBuilder

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "learning_rate": 0.02,
                "max_hidden_units": 18,
                "max_epochs": 250,
            }
            mock_get.return_value = mock_response

            builder = EnvironBuilder(
                method="GET",
                base_url="http://localhost:8050/dashboard/",
                path="/dashboard/",
            )
            env = builder.get_environ()

            with manager.app.server.request_context(env):
                result = manager._init_applied_params_handler(n=1, current=None)

            assert "max_hidden_units" in result
            assert "max_epochs" in result
            assert "hidden_units" not in result
            assert "epochs" not in result


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
                params, status = manager._apply_parameters_handler(n_clicks=1, lr=0.07, hu=10, epochs=200)

            # Verify the returned params contain correct learning_rate
            assert params["learning_rate"] == 0.07

            # Verify the payload sent to backend contains correct learning_rate
            call_args = mock_post.call_args
            json_payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert json_payload["learning_rate"] == 0.07


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
        assert state3["learning_rate"] == 0.02
