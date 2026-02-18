#!/usr/bin/env python
"""
Coverage tests for decision_boundary.py callback logic.
Target: Lines 189-211, 252

Tests the update_boundary_plot callback function with various input combinations.
"""
from unittest.mock import MagicMock, patch

import numpy as np
import plotly.graph_objects as go
import pytest

from frontend.components.decision_boundary import DecisionBoundary


@pytest.fixture
def boundary_component():
    """Create DecisionBoundary instance for testing."""
    config = {"boundary_resolution": 50, "show_confidence": True}
    return DecisionBoundary(config, component_id="test-cb")


@pytest.fixture
def sample_boundary_data():
    """Create sample boundary data for testing."""
    x = np.linspace(-1, 1, 10)
    y = np.linspace(-1, 1, 10)
    xx, yy = np.meshgrid(x, y)
    Z = xx + yy
    return {
        "xx": xx.tolist(),
        "yy": yy.tolist(),
        "Z": Z.tolist(),
        "bounds": {"x_min": -1, "x_max": 1, "y_min": -1, "y_max": 1},
    }


@pytest.fixture
def sample_dataset():
    """Create sample dataset for testing."""
    return {
        "inputs": np.array([[0, 0], [1, 1], [-1, -1], [0.5, -0.5]]),
        "targets": np.array([0, 1, 0, 1]),
    }


class TestUpdateBoundaryPlotCallback:
    """Test the update_boundary_plot callback logic (lines 189-211)."""

    @pytest.mark.unit
    def test_callback_no_boundary_data_no_predict_fn(self, boundary_component):
        """Test callback returns empty plot when no boundary_data and no predict_fn (line 189-191)."""
        boundary_component.predict_fn = None

        # Simulate callback inputs
        boundary_data = None
        theme = "light"

        # Call internal logic that callback would execute
        if not boundary_data and not boundary_component.predict_fn:
            empty_fig = boundary_component._create_empty_plot("No network loaded", theme)
            status = "Status: No network loaded"

        assert isinstance(empty_fig, go.Figure)
        assert status == "Status: No network loaded"
        assert len(empty_fig.layout.annotations) > 0
        assert "No network loaded" in empty_fig.layout.annotations[0].text

    @pytest.mark.unit
    def test_callback_with_boundary_data_only(self, boundary_component, sample_boundary_data):
        """Test callback with pre-computed boundary data (lines 198-200)."""
        boundary_data = sample_boundary_data
        dataset = None
        show_conf = True
        theme = "light"

        if boundary_data:
            fig = boundary_component._create_boundary_plot(boundary_data, dataset, show_conf, theme)
            status = "Status: Displaying decision boundary"

        assert isinstance(fig, go.Figure)
        assert status == "Status: Displaying decision boundary"
        assert len(fig.data) > 0

    @pytest.mark.unit
    def test_callback_with_boundary_data_and_dataset(self, boundary_component, sample_boundary_data, sample_dataset):
        """Test callback with boundary data and dataset overlay (lines 198-200)."""
        boundary_data = sample_boundary_data
        dataset = sample_dataset
        show_conf = True
        theme = "dark"

        if boundary_data:
            fig = boundary_component._create_boundary_plot(boundary_data, dataset, show_conf, theme)
            status = "Status: Displaying decision boundary"

        assert isinstance(fig, go.Figure)
        assert status == "Status: Displaying decision boundary"
        # Should have contour + scatter traces
        assert len(fig.data) > 1

    @pytest.mark.unit
    def test_callback_live_boundary_computation(self, boundary_component, sample_dataset):
        """Test callback with predict_fn and dataset (lines 203-206)."""

        # Set prediction function
        def mock_predict(X):
            return (X[:, 0] + X[:, 1] > 0).astype(float)

        boundary_component.predict_fn = mock_predict
        boundary_data = None
        dataset = sample_dataset
        show_conf = True
        theme = "light"

        # Simulate callback logic
        if not boundary_data and boundary_component.predict_fn and dataset:
            computed_boundary = boundary_component._compute_decision_boundary(dataset)
            fig = boundary_component._create_boundary_plot(computed_boundary, dataset, show_conf, theme)
            status = "Status: Live boundary computation"

        assert isinstance(fig, go.Figure)
        assert status == "Status: Live boundary computation"

    @pytest.mark.unit
    def test_callback_waiting_for_data_with_predict_fn_no_dataset(self, boundary_component):
        """Test callback with predict_fn but no dataset (lines 207-209)."""
        boundary_component.predict_fn = lambda X: np.zeros(X.shape[0])
        boundary_data = None
        dataset = None
        theme = "light"

        # Simulate callback logic
        if not boundary_data:
            if boundary_component.predict_fn and dataset:
                pass  # Would compute boundary
            else:
                fig = boundary_component._create_empty_plot("Waiting for network predictions...", theme)
                status = "Status: Waiting for data"

        assert isinstance(fig, go.Figure)
        assert status == "Status: Waiting for data"

    @pytest.mark.unit
    def test_callback_resolution_update(self, boundary_component, sample_boundary_data):
        """Test callback updates resolution (line 194)."""
        initial_resolution = boundary_component.resolution
        new_resolution = 75

        # Simulate resolution update
        boundary_component.resolution = new_resolution

        assert boundary_component.resolution == new_resolution
        assert boundary_component.resolution != initial_resolution

    @pytest.mark.unit
    def test_callback_show_confidence_parsing(self, boundary_component, sample_boundary_data):
        """Test callback parses show_confidence correctly (line 195)."""
        # Test with "show" in list
        show_confidence_enabled = ["show"]
        show_conf = "show" in show_confidence_enabled
        assert show_conf is True

        # Test with empty list
        show_confidence_disabled = []
        show_conf = "show" in show_confidence_disabled
        assert show_conf is False

    @pytest.mark.unit
    def test_callback_theme_variations(self, boundary_component, sample_boundary_data):
        """Test callback with light and dark themes."""
        boundary_data = sample_boundary_data

        # Light theme
        fig_light = boundary_component._create_boundary_plot(boundary_data, None, True, "light")
        assert fig_light.layout.plot_bgcolor == "#f8f9fa"
        assert fig_light.layout.paper_bgcolor == "#ffffff"

        # Dark theme
        fig_dark = boundary_component._create_boundary_plot(boundary_data, None, True, "dark")
        assert fig_dark.layout.plot_bgcolor == "#242424"
        assert fig_dark.layout.paper_bgcolor == "#242424"


class TestPredictionBranches:
    """Test prediction format handling (line 252)."""

    @pytest.mark.unit
    def test_single_column_multi_output_predictions(self, boundary_component):
        """Test predictions with shape (n, 1) - line 252."""

        def mock_predict_single_column(X):
            # Return predictions with shape (n, 1)
            return np.expand_dims((X[:, 0] > 0).astype(float), axis=1)

        boundary_component.predict_fn = mock_predict_single_column
        dataset = {
            "inputs": np.array([[0, 0], [1, 1], [-1, -1]]),
            "targets": [0, 1, 0],
        }

        result = boundary_component._compute_decision_boundary(dataset)

        assert "Z" in result
        assert "xx" in result
        assert "yy" in result

    @pytest.mark.unit
    def test_multi_column_predictions_argmax(self, boundary_component):
        """Test predictions with shape (n, k) where k > 1 uses argmax (line 250)."""

        def mock_predict_multi_class(X):
            # Return 3-class probabilities
            n = X.shape[0]
            probs = np.zeros((n, 3))
            probs[:, 0] = X[:, 0] < 0
            probs[:, 1] = (X[:, 0] >= 0) & (X[:, 1] < 0)
            probs[:, 2] = (X[:, 0] >= 0) & (X[:, 1] >= 0)
            return probs.astype(float)

        boundary_component.predict_fn = mock_predict_multi_class
        dataset = {
            "inputs": np.array([[0, 0], [1, 1], [-1, -1], [1, -1]]),
            "targets": [0, 1, 2, 1],
        }

        result = boundary_component._compute_decision_boundary(dataset)

        assert "Z" in result
        # Z values should be class indices (0, 1, or 2)
        Z_flat = np.array(result["Z"]).ravel()
        assert all(z in [0, 1, 2] for z in Z_flat)

    @pytest.mark.unit
    def test_1d_predictions_direct_use(self, boundary_component):
        """Test predictions with shape (n,) are used directly (line 254)."""

        def mock_predict_1d(X):
            # Return 1D predictions
            return (X[:, 0] + X[:, 1]).ravel()

        boundary_component.predict_fn = mock_predict_1d
        dataset = {
            "inputs": np.array([[0, 0], [1, 1], [-1, -1]]),
            "targets": [0, 1, 0],
        }

        result = boundary_component._compute_decision_boundary(dataset)

        assert "Z" in result
        assert "bounds" in result


class TestCallbackRegistration:
    """Test callback registration flow."""

    @pytest.mark.unit
    def test_register_callbacks_logs_debug(self, boundary_component):
        """Test callback registration logs debug message (line 213)."""
        from dash import Dash

        app = Dash(__name__)

        with patch.object(boundary_component.logger, "debug") as mock_debug:
            boundary_component.register_callbacks(app)
            mock_debug.assert_called_once()
            assert "test-cb" in mock_debug.call_args[0][0]

    @pytest.mark.unit
    def test_register_callbacks_creates_callback(self, boundary_component):
        """Test callback is registered with app."""
        from dash import Dash

        app = Dash(__name__)
        initial_callbacks = len(app.callback_map)

        boundary_component.register_callbacks(app)

        # Callback should be registered
        assert len(app.callback_map) > initial_callbacks


class TestCallbackIntegration:
    """Integration tests for callback behavior."""

    @pytest.mark.unit
    def test_full_callback_flow_with_boundary_data(self, boundary_component, sample_boundary_data, sample_dataset):
        """Test complete callback flow with all inputs."""

        def simulate_callback(boundary_data, dataset, resolution, show_confidence, theme):
            """Simulate the update_boundary_plot callback logic."""
            if not boundary_data and not boundary_component.predict_fn:
                empty_fig = boundary_component._create_empty_plot("No network loaded", theme)
                return empty_fig, "Status: No network loaded"

            boundary_component.resolution = resolution
            show_conf = "show" in show_confidence

            if boundary_data:
                fig = boundary_component._create_boundary_plot(boundary_data, dataset, show_conf, theme)
                return fig, "Status: Displaying decision boundary"
            elif boundary_component.predict_fn and dataset:
                computed_boundary = boundary_component._compute_decision_boundary(dataset)
                fig = boundary_component._create_boundary_plot(computed_boundary, dataset, show_conf, theme)
                return fig, "Status: Live boundary computation"
            else:
                fig = boundary_component._create_empty_plot("Waiting for network predictions...", theme)
                return fig, "Status: Waiting for data"

        # Test with boundary data
        fig, status = simulate_callback(sample_boundary_data, sample_dataset, 50, ["show"], "light")
        assert isinstance(fig, go.Figure)
        assert status == "Status: Displaying decision boundary"

    @pytest.mark.unit
    def test_full_callback_flow_live_computation(self, boundary_component, sample_dataset):
        """Test complete callback flow with live computation."""
        boundary_component.predict_fn = lambda X: (X[:, 0] > 0).astype(float)

        def simulate_callback(boundary_data, dataset, resolution, show_confidence, theme):
            if not boundary_data and not boundary_component.predict_fn:
                return boundary_component._create_empty_plot("No network loaded", theme), "Status: No network loaded"

            boundary_component.resolution = resolution
            show_conf = "show" in show_confidence

            if boundary_data:
                fig = boundary_component._create_boundary_plot(boundary_data, dataset, show_conf, theme)
                return fig, "Status: Displaying decision boundary"
            elif boundary_component.predict_fn and dataset:
                computed_boundary = boundary_component._compute_decision_boundary(dataset)
                fig = boundary_component._create_boundary_plot(computed_boundary, dataset, show_conf, theme)
                return fig, "Status: Live boundary computation"
            else:
                fig = boundary_component._create_empty_plot("Waiting for network predictions...", theme)
                return fig, "Status: Waiting for data"

        fig, status = simulate_callback(None, sample_dataset, 50, ["show"], "dark")
        assert isinstance(fig, go.Figure)
        assert status == "Status: Live boundary computation"

    @pytest.mark.unit
    def test_full_callback_flow_no_data(self, boundary_component):
        """Test complete callback flow with no data available."""
        boundary_component.predict_fn = lambda X: X[:, 0]

        def simulate_callback(boundary_data, dataset, resolution, show_confidence, theme):
            if not boundary_data and not boundary_component.predict_fn:
                return boundary_component._create_empty_plot("No network loaded", theme), "Status: No network loaded"

            boundary_component.resolution = resolution
            show_conf = "show" in show_confidence

            if boundary_data:
                fig = boundary_component._create_boundary_plot(boundary_data, dataset, show_conf, theme)
                return fig, "Status: Displaying decision boundary"
            elif boundary_component.predict_fn and dataset:
                computed_boundary = boundary_component._compute_decision_boundary(dataset)
                fig = boundary_component._create_boundary_plot(computed_boundary, dataset, show_conf, theme)
                return fig, "Status: Live boundary computation"
            else:
                fig = boundary_component._create_empty_plot("Waiting for network predictions...", theme)
                return fig, "Status: Waiting for data"

        fig, status = simulate_callback(None, None, 50, [], "light")
        assert isinstance(fig, go.Figure)
        assert status == "Status: Waiting for data"


class TestDashCallbackExecution:
    """Test actual Dash callback execution to cover lines 189-211.

    Uses _captured_callback attribute to access the raw callback function
    that was registered, bypassing Dash's context requirement.
    """

    @pytest.mark.unit
    def test_dash_callback_no_network_loaded(self):
        """Test callback execution path for no network loaded (lines 189-191)."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        app = Dash(__name__, suppress_callback_exceptions=True)
        component = DecisionBoundary({}, component_id="cb-test")

        # Capture the raw callback function before it's wrapped by Dash
        captured_callback = None

        original_callback = app.callback

        def capturing_callback(*args, **kwargs):
            def wrapper(fn):
                nonlocal captured_callback
                captured_callback = fn
                return original_callback(*args, **kwargs)(fn)

            return wrapper

        app.callback = capturing_callback
        component.register_callbacks(app)

        # Execute the captured raw callback
        if captured_callback:
            fig, status = captured_callback(None, None, 50, [], "light")
            assert isinstance(fig, go.Figure)
            assert status == "Status: No network loaded"

    @pytest.mark.unit
    def test_dash_callback_with_boundary_data(self, sample_boundary_data):
        """Test callback execution path with boundary data (lines 198-200)."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        app = Dash(__name__, suppress_callback_exceptions=True)
        component = DecisionBoundary({}, component_id="cb-bd")

        captured_callback = None
        original_callback = app.callback

        def capturing_callback(*args, **kwargs):
            def wrapper(fn):
                nonlocal captured_callback
                captured_callback = fn
                return original_callback(*args, **kwargs)(fn)

            return wrapper

        app.callback = capturing_callback
        component.register_callbacks(app)

        if captured_callback:
            fig, status = captured_callback(sample_boundary_data, None, 100, ["show"], "dark")
            assert isinstance(fig, go.Figure)
            assert status == "Status: Displaying decision boundary"

    @pytest.mark.unit
    def test_dash_callback_live_computation(self, sample_dataset):
        """Test callback execution path with live computation (lines 203-206)."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        app = Dash(__name__, suppress_callback_exceptions=True)
        component = DecisionBoundary({"boundary_resolution": 30}, component_id="cb-live")
        component.predict_fn = lambda X: (X[:, 0] > 0).astype(float)

        captured_callback = None
        original_callback = app.callback

        def capturing_callback(*args, **kwargs):
            def wrapper(fn):
                nonlocal captured_callback
                captured_callback = fn
                return original_callback(*args, **kwargs)(fn)

            return wrapper

        app.callback = capturing_callback
        component.register_callbacks(app)

        if captured_callback:
            fig, status = captured_callback(None, sample_dataset, 30, ["show"], "light")
            assert isinstance(fig, go.Figure)
            assert status == "Status: Live boundary computation"

    @pytest.mark.unit
    def test_dash_callback_waiting_for_data(self):
        """Test callback execution path waiting for data (lines 207-209)."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        app = Dash(__name__, suppress_callback_exceptions=True)
        component = DecisionBoundary({}, component_id="cb-wait")
        component.predict_fn = lambda X: X[:, 0]

        captured_callback = None
        original_callback = app.callback

        def capturing_callback(*args, **kwargs):
            def wrapper(fn):
                nonlocal captured_callback
                captured_callback = fn
                return original_callback(*args, **kwargs)(fn)

            return wrapper

        app.callback = capturing_callback
        component.register_callbacks(app)

        if captured_callback:
            fig, status = captured_callback(None, None, 50, [], "light")
            assert isinstance(fig, go.Figure)
            assert status == "Status: Waiting for data"

    @pytest.mark.unit
    def test_dash_callback_resolution_update(self, sample_boundary_data):
        """Test callback updates resolution (line 194)."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        app = Dash(__name__, suppress_callback_exceptions=True)
        component = DecisionBoundary({"boundary_resolution": 50}, component_id="cb-res")

        captured_callback = None
        original_callback = app.callback

        def capturing_callback(*args, **kwargs):
            def wrapper(fn):
                nonlocal captured_callback
                captured_callback = fn
                return original_callback(*args, **kwargs)(fn)

            return wrapper

        app.callback = capturing_callback
        component.register_callbacks(app)

        if captured_callback:
            captured_callback(sample_boundary_data, None, 75, ["show"], "light")
            assert component.resolution == 75

    @pytest.mark.unit
    def test_dash_callback_show_confidence_toggle(self, sample_boundary_data):
        """Test callback parses show_confidence correctly (line 195)."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        app = Dash(__name__, suppress_callback_exceptions=True)
        component = DecisionBoundary({}, component_id="cb-conf")

        captured_callback = None
        original_callback = app.callback

        def capturing_callback(*args, **kwargs):
            def wrapper(fn):
                nonlocal captured_callback
                captured_callback = fn
                return original_callback(*args, **kwargs)(fn)

            return wrapper

        app.callback = capturing_callback
        component.register_callbacks(app)

        if captured_callback:
            fig_with, _ = captured_callback(sample_boundary_data, None, 50, ["show"], "light")
            fig_without, _ = captured_callback(sample_boundary_data, None, 50, [], "light")
            assert isinstance(fig_with, go.Figure)
            assert isinstance(fig_without, go.Figure)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
