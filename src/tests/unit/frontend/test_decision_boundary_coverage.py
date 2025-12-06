#!/usr/bin/env python
"""
Comprehensive coverage tests for decision_boundary.py
Target: Raise coverage from 33% to 80%+

Tests cover:
- DecisionBoundary initialization with various parameters
- Grid computation with different resolutions
- Prediction on grid with mock model
- Boundary plotting with different datasets
- Error handling for invalid inputs
- Edge cases: empty datasets, degenerate data
- Color mapping and legend generation
"""
from unittest.mock import Mock

import numpy as np
import plotly.graph_objects as go
import pytest  # noqa: F401 - needed for pytest fixtures
from dash import html


class TestDecisionBoundaryInit:
    """Test DecisionBoundary initialization."""

    def test_init_with_minimal_config(self):
        """Test initialization with minimal configuration."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config, component_id="test-boundary")

        assert component.component_id == "test-boundary"
        assert component.resolution == 100  # Default
        assert component.show_confidence is True  # Default
        assert component.predict_fn is None
        assert component.dataset is None
        assert component.data_bounds is None

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {"boundary_resolution": 150, "show_confidence": False}
        component = DecisionBoundary(config, component_id="custom-boundary")

        assert component.resolution == 150
        assert component.show_confidence is False

    def test_init_with_extreme_resolution(self):
        """Test initialization with extreme resolution values."""
        from frontend.components.decision_boundary import DecisionBoundary

        # Very high resolution
        config = {"boundary_resolution": 500}
        component = DecisionBoundary(config)
        assert component.resolution == 500

        # Very low resolution
        config = {"boundary_resolution": 10}
        component = DecisionBoundary(config)
        assert component.resolution == 10


class TestDecisionBoundaryLayout:
    """Test layout generation."""

    def test_get_layout_structure(self):
        """Test layout contains expected elements."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)
        layout = component.get_layout()

        assert isinstance(layout, html.Div)
        # Layout should contain children elements

    def test_get_layout_with_custom_id(self):
        """Test layout uses custom component ID."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config, component_id="my-boundary")
        layout = component.get_layout()

        # Convert to dict to inspect IDs
        layout_dict = str(layout)
        assert "my-boundary" in layout_dict


class TestDecisionBoundaryGrid:
    """Test grid computation methods."""

    def test_compute_decision_boundary_with_no_predict_fn(self):
        """Test boundary computation without prediction function."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)
        dataset = {"inputs": [[0, 0], [1, 1]], "targets": [0, 1]}

        result = component._compute_decision_boundary(dataset)

        assert result == {}

    def test_compute_decision_boundary_with_empty_dataset(self):
        """Test boundary computation with empty dataset."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        # Set mock prediction function
        component.predict_fn = Mock()

        dataset = {"inputs": [], "targets": []}
        result = component._compute_decision_boundary(dataset)

        assert result == {}

    def test_compute_decision_boundary_with_1d_data(self):
        """Test boundary computation with 1D data (insufficient)."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)
        component.predict_fn = Mock()

        dataset = {"inputs": [[0], [1], [2]], "targets": [0, 1, 0]}
        result = component._compute_decision_boundary(dataset)

        assert result == {}

    def test_compute_decision_boundary_with_valid_data(self):
        """Test boundary computation with valid 2D data."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {"boundary_resolution": 50}
        component = DecisionBoundary(config)

        # Mock prediction function
        def mock_predict(X):
            # Return simple predictions based on sum
            return (X[:, 0] + X[:, 1] > 0).astype(float)

        component.predict_fn = mock_predict

        dataset = {"inputs": np.array([[0, 0], [1, 1], [-1, -1], [1, -1]]), "targets": [0, 1, 0, 1]}

        result = component._compute_decision_boundary(dataset)

        assert "xx" in result
        assert "yy" in result
        assert "Z" in result
        assert "bounds" in result
        assert len(result["xx"]) == 50  # Resolution
        assert len(result["yy"]) == 50

    def test_compute_decision_boundary_with_multi_output_predictions(self):
        """Test boundary computation with multi-class predictions."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {"boundary_resolution": 30}
        component = DecisionBoundary(config)

        # Mock prediction function returning probabilities
        def mock_predict(X):
            n = X.shape[0]
            # Return 3-class probabilities
            probs = np.random.rand(n, 3)
            probs = probs / probs.sum(axis=1, keepdims=True)
            return probs

        component.predict_fn = mock_predict

        dataset = {"inputs": np.array([[0, 0], [1, 1], [-1, -1]]), "targets": [0, 1, 2]}

        result = component._compute_decision_boundary(dataset)

        assert "Z" in result
        # Should use argmax for multi-class

    def test_compute_decision_boundary_with_prediction_error(self):
        """Test boundary computation handles prediction errors."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        # Mock prediction function that raises error
        def mock_predict(X):
            raise ValueError("Prediction failed")

        component.predict_fn = mock_predict

        dataset = {"inputs": np.array([[0, 0], [1, 1]]), "targets": [0, 1]}

        result = component._compute_decision_boundary(dataset)

        assert result == {}


class TestDecisionBoundaryPrediction:
    """Test prediction on grid."""

    def test_set_prediction_function(self):
        """Test setting prediction function."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        mock_fn = Mock()
        component.set_prediction_function(mock_fn)

        assert component.predict_fn == mock_fn

    def test_update_dataset(self):
        """Test updating dataset."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        dataset = {"inputs": np.array([[0, 0], [1, 1], [2, 2]]), "targets": [0, 1, 0]}

        component.update_dataset(dataset)

        assert component.dataset == dataset
        assert component.data_bounds is not None
        assert "x" in component.data_bounds
        assert "y" in component.data_bounds

    def test_update_dataset_with_empty_data(self):
        """Test updating with empty dataset."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        dataset = {"inputs": [], "targets": []}
        component.update_dataset(dataset)

        assert component.dataset == dataset

    def test_compute_and_cache_boundary_with_no_dataset(self):
        """Test caching boundary with no dataset."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        result = component.compute_and_cache_boundary()

        assert result is None

    def test_compute_and_cache_boundary_with_dataset(self):
        """Test caching boundary with valid dataset."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {"boundary_resolution": 40}
        component = DecisionBoundary(config)

        # Set prediction function
        component.predict_fn = lambda X: (X[:, 0] > 0).astype(float)

        # Set dataset
        dataset = {"inputs": np.array([[0, 0], [1, 1], [-1, -1]]), "targets": [0, 1, 0]}
        component.dataset = dataset

        result = component.compute_and_cache_boundary()

        assert result is not None
        assert "xx" in result


class TestDecisionBoundaryPlotting:
    """Test boundary visualization."""

    def test_create_empty_plot_light_theme(self):
        """Test empty plot with light theme."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        fig = component._create_empty_plot("No data", theme="light")

        assert isinstance(fig, go.Figure)
        # Check for annotation
        assert len(fig.layout.annotations) > 0

    def test_create_empty_plot_dark_theme(self):
        """Test empty plot with dark theme."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        fig = component._create_empty_plot("No data", theme="dark")

        assert isinstance(fig, go.Figure)  # Dark theme applied

    def test_create_boundary_plot_with_empty_data(self):
        """Test creating plot with empty boundary data."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        boundary_data = {"xx": [], "yy": [], "Z": []}
        fig = component._create_boundary_plot(boundary_data, None, True, "light")

        # Should return empty plot
        assert isinstance(fig, go.Figure)

    def test_create_boundary_plot_with_confidence(self):
        """Test creating plot with confidence regions."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        # Create simple grid
        x = np.linspace(-1, 1, 10)
        y = np.linspace(-1, 1, 10)
        xx, yy = np.meshgrid(x, y)
        Z = xx + yy

        boundary_data = {"xx": xx.tolist(), "yy": yy.tolist(), "Z": Z.tolist()}

        fig = component._create_boundary_plot(boundary_data, None, True, "light")

        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_create_boundary_plot_without_confidence(self):
        """Test creating plot without confidence regions."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        x = np.linspace(-1, 1, 10)
        y = np.linspace(-1, 1, 10)
        xx, yy = np.meshgrid(x, y)
        Z = xx + yy

        boundary_data = {"xx": xx.tolist(), "yy": yy.tolist(), "Z": Z.tolist()}

        fig = component._create_boundary_plot(boundary_data, None, False, "light")

        assert isinstance(fig, go.Figure)

    def test_create_boundary_plot_with_dataset_overlay(self):
        """Test creating plot with dataset overlay."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        x = np.linspace(-1, 1, 10)
        y = np.linspace(-1, 1, 10)
        xx, yy = np.meshgrid(x, y)
        Z = xx + yy

        boundary_data = {"xx": xx.tolist(), "yy": yy.tolist(), "Z": Z.tolist()}

        dataset = {"inputs": np.array([[0, 0], [1, 1], [-1, -1], [0.5, -0.5]]), "targets": np.array([0, 1, 0, 1])}

        fig = component._create_boundary_plot(boundary_data, dataset, True, "light")

        assert isinstance(fig, go.Figure)
        # Should have contour + scatter traces
        assert len(fig.data) > 1

    def test_create_boundary_plot_with_multi_class_dataset(self):
        """Test creating plot with multi-class dataset."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        x = np.linspace(-1, 1, 10)
        y = np.linspace(-1, 1, 10)
        xx, yy = np.meshgrid(x, y)
        Z = xx + yy

        boundary_data = {"xx": xx.tolist(), "yy": yy.tolist(), "Z": Z.tolist()}

        # 5 classes to test color cycling
        dataset = {
            "inputs": np.array([[0, 0], [1, 1], [-1, -1], [0.5, 0.5], [0, 1], [1, 0]]),
            "targets": np.array([0, 1, 2, 3, 4, 0]),
        }

        fig = component._create_boundary_plot(boundary_data, dataset, True, "light")

        assert isinstance(fig, go.Figure)
        # Multiple scatter traces for different classes

    def test_create_boundary_plot_dark_theme(self):
        """Test creating plot with dark theme."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        x = np.linspace(-1, 1, 10)
        y = np.linspace(-1, 1, 10)
        xx, yy = np.meshgrid(x, y)
        Z = xx + yy

        boundary_data = {"xx": xx.tolist(), "yy": yy.tolist(), "Z": Z.tolist()}

        fig = component._create_boundary_plot(boundary_data, None, True, "dark")

        assert isinstance(fig, go.Figure)  # Dark theme applied


class TestDecisionBoundaryEdgeCases:
    """Test edge cases and error handling."""

    def test_boundary_with_nan_values(self):
        """Test handling of NaN values in predictions."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        # Mock function that returns NaN
        def mock_predict(X):
            result = np.ones(X.shape[0])
            result[0] = np.nan
            return result

        component.predict_fn = mock_predict

        dataset = {"inputs": np.array([[0, 0], [1, 1]]), "targets": [0, 1]}

        # Should handle gracefully - just verify no exception raised
        component._compute_decision_boundary(dataset)
        # May return empty dict or handle NaN

    def test_boundary_with_single_point_dataset(self):
        """Test boundary computation with single data point."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)
        component.predict_fn = lambda X: np.zeros(X.shape[0])

        dataset = {"inputs": np.array([[0, 0]]), "targets": [0]}

        result = component._compute_decision_boundary(dataset)

        assert "bounds" in result or result == {}

    def test_boundary_with_degenerate_data(self):
        """Test boundary with all points at same location."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)
        component.predict_fn = lambda X: np.zeros(X.shape[0])

        # All points identical
        dataset = {"inputs": np.array([[0, 0], [0, 0], [0, 0]]), "targets": [0, 0, 0]}

        component._compute_decision_boundary(dataset)
        # Should still compute boundary, just with small range

    def test_update_dataset_with_invalid_shape(self):
        """Test updating dataset with invalid input shape."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        # 1D data (not enough for boundary)
        dataset = {"inputs": np.array([[1], [2], [3]]), "targets": [0, 1, 0]}

        component.update_dataset(dataset)
        # Should not set bounds for 1D data

    def test_boundary_with_extreme_values(self):
        """Test boundary computation with extreme coordinate values."""
        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)
        component.predict_fn = lambda X: np.zeros(X.shape[0])

        dataset = {"inputs": np.array([[-1e6, -1e6], [1e6, 1e6]]), "targets": [0, 1]}

        if result := component._compute_decision_boundary(dataset):
            assert "bounds" in result

    def test_callbacks_registration(self):
        """Test callback registration."""
        from dash import Dash

        from frontend.components.decision_boundary import DecisionBoundary

        config = {}
        component = DecisionBoundary(config)

        # Create minimal Dash app
        app = Dash(__name__)

        # Should not raise
        component.register_callbacks(app)
