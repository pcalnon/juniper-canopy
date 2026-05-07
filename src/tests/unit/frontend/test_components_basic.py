#!/usr/bin/env python
"""Basic tests for frontend components."""

import dash_bootstrap_components as dbc
import pytest
from dash import Dash

from frontend.components.dataset_plotter import DatasetPlotter
from frontend.components.decision_boundary import DecisionBoundary
from frontend.components.metrics_panel import MetricsPanel
from frontend.components.network_visualizer import NetworkVisualizer


@pytest.fixture
def dash_app():
    """Create a minimal Dash app for testing."""
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
    )
    app.callback_map = {}
    return app


class TestMetricsPanelBasic:
    """Basic tests for MetricsPanel component."""

    def test_get_layout_returns_valid_structure(self):
        """Test that get_layout returns a valid Dash component structure."""
        component = MetricsPanel({}, component_id="test-metrics")
        layout = component.get_layout()

        assert layout is not None
        assert hasattr(layout, "children")

    def test_register_callbacks_doesnt_raise(self, dash_app):
        """Test that register_callbacks executes without raising exceptions."""
        component = MetricsPanel({}, component_id="test-metrics")

        try:
            component.register_callbacks(dash_app)
        except Exception as e:
            pytest.fail(f"register_callbacks raised {type(e).__name__}: {e}")

    def test_register_callbacks_increases_callback_map(self, dash_app):
        """Test that register_callbacks adds callbacks to the app."""
        component = MetricsPanel({}, component_id="test-metrics")
        initial_count = len(dash_app.callback_map)

        component.register_callbacks(dash_app)

        # MetricsPanel should register at least one callback
        assert len(dash_app.callback_map) > initial_count

    def test_component_initialization(self):
        """Test that MetricsPanel initializes with correct attributes."""
        config = {"max_data_points": 500, "update_interval": 2000}
        component = MetricsPanel(config, component_id="test-metrics")

        assert component.component_id == "test-metrics"
        assert component.max_data_points == 500
        assert component.update_interval == 2000

    def test_default_configuration(self):
        """Test that MetricsPanel uses default values when config is empty."""
        component = MetricsPanel({}, component_id="test-metrics")

        assert component.max_data_points == 1000  # Default value
        assert component.update_interval == 1000  # Default value


class TestNetworkVisualizerBasic:
    """Basic tests for NetworkVisualizer component."""

    def test_get_layout_returns_valid_structure(self):
        """Test that get_layout returns a valid Dash component structure."""
        component = NetworkVisualizer({}, component_id="test-network")
        layout = component.get_layout()

        assert layout is not None
        assert hasattr(layout, "children")

    def test_register_callbacks_doesnt_raise(self, dash_app):
        """Test that register_callbacks executes without raising exceptions."""
        component = NetworkVisualizer({}, component_id="test-network")

        try:
            component.register_callbacks(dash_app)
        except Exception as e:
            pytest.fail(f"register_callbacks raised {type(e).__name__}: {e}")

    def test_register_callbacks_increases_callback_map(self, dash_app):
        """Test that register_callbacks adds callbacks to the app."""
        component = NetworkVisualizer({}, component_id="test-network")
        initial_count = len(dash_app.callback_map)

        component.register_callbacks(dash_app)

        # NetworkVisualizer should register at least one callback
        assert len(dash_app.callback_map) > initial_count

    def test_component_initialization(self):
        """Test that NetworkVisualizer initializes with correct attributes."""
        config = {"show_weights": False, "layout": "spring"}
        component = NetworkVisualizer(config, component_id="test-network")

        assert component.component_id == "test-network"
        assert component.show_weights is False
        assert component.layout_type == "spring"

    def test_default_configuration(self):
        """Test that NetworkVisualizer uses default values when config is empty."""
        component = NetworkVisualizer({}, component_id="test-network")

        assert component.show_weights is True  # Default value
        assert component.layout_type == "hierarchical"  # Default value


class TestDatasetPlotterBasic:
    """Basic tests for DatasetPlotter component."""

    def test_get_layout_returns_valid_structure(self):
        """Test that get_layout returns a valid Dash component structure."""
        component = DatasetPlotter({}, component_id="test-dataset")
        layout = component.get_layout()

        assert layout is not None
        assert hasattr(layout, "children")

    def test_register_callbacks_doesnt_raise(self, dash_app):
        """Test that register_callbacks executes without raising exceptions."""
        component = DatasetPlotter({}, component_id="test-dataset")

        try:
            component.register_callbacks(dash_app)
        except Exception as e:
            pytest.fail(f"register_callbacks raised {type(e).__name__}: {e}")

    def test_register_callbacks_increases_callback_map(self, dash_app):
        """Test that register_callbacks adds callbacks to the app."""
        component = DatasetPlotter({}, component_id="test-dataset")
        initial_count = len(dash_app.callback_map)

        component.register_callbacks(dash_app)

        # DatasetPlotter should register at least one callback
        assert len(dash_app.callback_map) > initial_count

    def test_component_initialization(self):
        """Test that DatasetPlotter initializes with correct attributes."""
        component = DatasetPlotter({}, component_id="test-dataset")

        assert component.component_id == "test-dataset"
        assert component.default_colors is not None
        assert len(component.default_colors) == 5

    def test_default_dataset_is_none(self):
        """Test that DatasetPlotter starts with no dataset."""
        component = DatasetPlotter({}, component_id="test-dataset")

        assert component.current_dataset is None


class TestDecisionBoundaryBasic:
    """Basic tests for DecisionBoundary component."""

    def test_get_layout_returns_valid_structure(self):
        """Test that get_layout returns a valid Dash component structure."""
        component = DecisionBoundary({}, component_id="test-boundary")
        layout = component.get_layout()

        assert layout is not None
        assert hasattr(layout, "children")

    def test_register_callbacks_doesnt_raise(self, dash_app):
        """Test that register_callbacks executes without raising exceptions."""
        component = DecisionBoundary({}, component_id="test-boundary")

        try:
            component.register_callbacks(dash_app)
        except Exception as e:
            pytest.fail(f"register_callbacks raised {type(e).__name__}: {e}")

    def test_register_callbacks_increases_callback_map(self, dash_app):
        """Test that register_callbacks adds callbacks to the app."""
        component = DecisionBoundary({}, component_id="test-boundary")
        initial_count = len(dash_app.callback_map)

        component.register_callbacks(dash_app)

        # DecisionBoundary should register at least one callback
        assert len(dash_app.callback_map) > initial_count

    def test_component_initialization(self):
        """Test that DecisionBoundary initializes with correct attributes."""
        config = {"boundary_resolution": 150, "show_confidence": False}
        component = DecisionBoundary(config, component_id="test-boundary")

        assert component.component_id == "test-boundary"
        assert component.resolution == 150
        assert component.show_confidence is False

    def test_default_configuration(self):
        """Test that DecisionBoundary uses default values when config is empty."""
        component = DecisionBoundary({}, component_id="test-boundary")

        assert component.resolution == 100  # Default value
        assert component.show_confidence is True  # Default value

    def test_predict_fn_is_none_initially(self):
        """Test that predict_fn is None on initialization."""
        component = DecisionBoundary({}, component_id="test-boundary")

        assert component.predict_fn is None


class TestAllComponentsConformToInterface:
    """Test that all components conform to BaseComponent interface."""

    @pytest.mark.parametrize(
        "component_class,component_id",
        [
            (MetricsPanel, "test-metrics"),
            (NetworkVisualizer, "test-network"),
            (DatasetPlotter, "test-dataset"),
            (DecisionBoundary, "test-boundary"),
        ],
    )
    def test_component_has_get_layout(self, component_class, component_id):
        """Test that component has get_layout method."""
        component = component_class({}, component_id=component_id)
        assert hasattr(component, "get_layout")
        assert callable(component.get_layout)

    @pytest.mark.parametrize(
        "component_class,component_id",
        [
            (MetricsPanel, "test-metrics"),
            (NetworkVisualizer, "test-network"),
            (DatasetPlotter, "test-dataset"),
            (DecisionBoundary, "test-boundary"),
        ],
    )
    def test_component_has_register_callbacks(self, component_class, component_id):
        """Test that component has register_callbacks method."""
        component = component_class({}, component_id=component_id)
        assert hasattr(component, "register_callbacks")
        assert callable(component.register_callbacks)

    @pytest.mark.parametrize(
        "component_class,component_id",
        [
            (MetricsPanel, "test-metrics"),
            (NetworkVisualizer, "test-network"),
            (DatasetPlotter, "test-dataset"),
            (DecisionBoundary, "test-boundary"),
        ],
    )
    def test_component_has_component_id(self, component_class, component_id):
        """Test that component has component_id attribute."""
        component = component_class({}, component_id=component_id)
        assert hasattr(component, "component_id")
        assert component.component_id == component_id

    @pytest.mark.parametrize(
        "component_class,component_id",
        [
            (MetricsPanel, "test-metrics"),
            (NetworkVisualizer, "test-network"),
            (DatasetPlotter, "test-dataset"),
            (DecisionBoundary, "test-boundary"),
        ],
    )
    def test_component_layout_is_not_none(self, component_class, component_id):
        """Test that get_layout does not return None."""
        component = component_class({}, component_id=component_id)
        layout = component.get_layout()
        assert layout is not None
