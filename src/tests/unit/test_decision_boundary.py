#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_decision_boundary.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for DecisionBoundary component
#####################################################################
"""Unit tests for DecisionBoundary component."""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from frontend.components.decision_boundary import DecisionBoundary  # noqa: E402


@pytest.fixture
def config():
    """Basic config for decision boundary."""
    return {
        "boundary_resolution": 50,
    }


@pytest.fixture
def boundary(config):
    """Create DecisionBoundary instance."""
    return DecisionBoundary(config, component_id="test-boundary")


class TestDecisionBoundaryInitialization:
    """Test DecisionBoundary initialization."""

    def test_init_with_default_config(self):
        """Should initialize with empty config."""
        boundary = DecisionBoundary({})
        assert boundary is not None
        assert boundary.component_id == "decision-boundary"

    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        boundary = DecisionBoundary(config, component_id="custom-boundary")
        assert boundary.component_id == "custom-boundary"

    def test_init_sets_resolution(self, config):
        """Should set resolution from config."""
        boundary = DecisionBoundary(config)
        assert boundary.resolution == 50

    def test_init_default_resolution(self):
        """Should use default resolution if not in config."""
        boundary = DecisionBoundary({})
        assert boundary.resolution == 100  # Hardcoded default


class TestDecisionBoundaryLayout:
    """Test DecisionBoundary layout generation."""

    def test_get_layout_returns_div(self, boundary):
        """get_layout should return Dash Div."""
        layout = boundary.get_layout()
        assert layout is not None
        from dash import html

        assert isinstance(layout, html.Div)

    def test_layout_contains_graph(self, boundary):
        """Layout should contain graph component."""
        layout = boundary.get_layout()
        from dash import dcc

        def find_graphs(component):
            graphs = []
            if isinstance(component, dcc.Graph):
                graphs.append(component)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        graphs.extend(find_graphs(child))
                elif component.children is not None:
                    graphs.extend(find_graphs(component.children))
            return graphs

        graphs = find_graphs(layout)
        assert len(graphs) > 0


class TestDecisionBoundaryCallbacks:
    """Test DecisionBoundary callback registration."""

    def test_register_callbacks_returns_none(self, boundary):
        """register_callbacks should return None."""
        from dash import Dash

        app = Dash(__name__)
        result = boundary.register_callbacks(app)
        assert result is None

    def test_register_callbacks_with_mock_app(self, boundary):
        """Should handle callback setup without errors."""
        from dash import Dash

        app = Dash(__name__)
        # Should not raise - direct call without try/except
        boundary.register_callbacks(app)


class TestDecisionBoundaryGridGeneration:
    """Test grid generation via the observable boundary-compute path.

    Black-box replacement for the historically-skipped
    ``TestDecisionBoundaryGridGeneration`` (asserted on a ``_create_grid``
    method that does not exist — grid creation is inline inside
    ``_compute_decision_boundary`` via ``np.meshgrid``). The observable
    contract is that the returned dict carries an ``xx``/``yy`` mesh
    whose shape matches ``boundary.resolution × boundary.resolution``.
    """

    @staticmethod
    def _identity_predict(grid_points):
        """Tiny predict_fn for grid-shape testing — output not inspected."""
        return np.zeros(len(grid_points))

    def test_compute_decision_boundary_produces_mesh(self, boundary):
        """Should produce ``xx``/``yy`` mesh with resolution × resolution shape."""
        boundary.predict_fn = self._identity_predict
        dataset = {"inputs": [[-1, -1], [1, 1]], "targets": [0, 1]}
        result = boundary._compute_decision_boundary(dataset)
        assert result, "boundary dict must be populated when predict_fn is set"
        xx = np.array(result["xx"])
        yy = np.array(result["yy"])
        assert xx.shape == (boundary.resolution, boundary.resolution)
        assert yy.shape == (boundary.resolution, boundary.resolution)

    def test_compute_decision_boundary_honours_resolution(self):
        """Resolution config flows through to the mesh shape.

        Verifies the same configuration knob the skipped
        ``test_grid_resolution`` was probing.
        """
        for resolution in (50, 100):
            b = DecisionBoundary({"boundary_resolution": resolution})
            b.predict_fn = TestDecisionBoundaryGridGeneration._identity_predict
            result = b._compute_decision_boundary({"inputs": [[-1, -1], [1, 1]], "targets": [0, 1]})
            xx = np.array(result["xx"])
            assert xx.shape == (resolution, resolution), f"resolution={resolution} mesh mismatch"

    def test_compute_decision_boundary_with_different_ranges(self, boundary):
        """Mesh bounds expand to enclose the input dataset (plus 1-unit padding)."""
        boundary.predict_fn = self._identity_predict
        dataset = {"inputs": [[-2, -3], [2, 3]], "targets": [0, 1]}
        result = boundary._compute_decision_boundary(dataset)
        bounds = result["bounds"]
        assert bounds["x_min"] <= -2 and bounds["x_max"] >= 2
        assert bounds["y_min"] <= -3 and bounds["y_max"] >= 3


class TestDecisionBoundaryPlotting:
    """Test plotting via ``_create_boundary_plot`` — the real observable seam.

    Black-box replacement for the historically-skipped
    ``TestDecisionBoundaryPlotting`` (asserted on ``_create_contour_plot``
    and ``_plot_dataset_overlay`` methods that do not exist — both
    behaviors live inside ``_create_boundary_plot(boundary_data, dataset,
    show_confidence, theme)``).
    """

    @staticmethod
    def _make_boundary_data():
        """Synthetic boundary-data dict matching ``_compute_decision_boundary`` output."""
        xx, yy = np.meshgrid(np.linspace(-1, 1, 10), np.linspace(-1, 1, 10))
        Z = (xx + yy > 0).astype(float)
        return {"xx": xx.tolist(), "yy": yy.tolist(), "Z": Z.tolist()}

    def test_create_boundary_plot_returns_figure_with_contour(self, boundary):
        """Boundary plot must contain at least one Contour trace."""
        fig = boundary._create_boundary_plot(self._make_boundary_data(), None, True, "light")
        assert fig is not None
        from plotly.graph_objs import Contour

        assert any(isinstance(trace, Contour) for trace in fig.data), "boundary plot must include a Contour trace"

    def test_plot_dataset_overlay_adds_scatter_traces(self, boundary):
        """Dataset overlay adds one scatter trace per class on top of the contour."""
        boundary_data = self._make_boundary_data()
        dataset = {"inputs": [[-0.5, -0.5], [0.5, 0.5], [-0.3, 0.3]], "targets": [0, 1, 0]}
        fig = boundary._create_boundary_plot(boundary_data, dataset, True, "light")
        from plotly.graph_objs import Contour, Scatter

        scatters = [t for t in fig.data if isinstance(t, Scatter)]
        contours = [t for t in fig.data if isinstance(t, Contour)]
        assert len(contours) >= 1
        # Two unique classes ↦ two scatter overlays.
        assert len(scatters) == 2

    def test_create_boundary_plot_with_empty_data_returns_empty_plot(self, boundary):
        """Empty boundary data returns the documented empty plot, does not raise.

        ``_create_boundary_plot`` calls ``create_empty_plot`` when
        xx / yy / Z are empty so the dashboard survives pre-training
        renders. The skipped test asserted ``pytest.raises`` which
        assumed a different contract.
        """
        fig = boundary._create_boundary_plot({"xx": [], "yy": [], "Z": []}, None, True, "light")
        assert fig is not None


class TestDecisionBoundaryDataHandling:
    """Test data handling via ``_compute_decision_boundary``.

    Black-box replacement for the historically-skipped
    ``TestDecisionBoundaryDataHandling`` (asserted on
    ``_prepare_boundary_data`` and ``_extract_ranges`` methods that do
    not exist — both responsibilities live inside
    ``_compute_decision_boundary`` which returns a single dict carrying
    both the mesh and the data-range bounds).
    """

    @staticmethod
    def _identity_predict(grid_points):
        return np.zeros(len(grid_points))

    def test_compute_boundary_returns_serialisable_dict(self, boundary):
        """Result is a JSON-friendly dict (lists, not ndarrays) ready for dcc.Store."""
        boundary.predict_fn = self._identity_predict
        result = boundary._compute_decision_boundary({"inputs": [[0, 0], [1, 1]], "targets": [0, 1]})
        assert isinstance(result["xx"], list)
        assert isinstance(result["yy"], list)
        assert isinstance(result["Z"], list)
        assert isinstance(result["bounds"], dict)

    def test_compute_boundary_extracts_bounds(self, boundary):
        """``bounds`` carries x_min/x_max/y_min/y_max as floats."""
        boundary.predict_fn = self._identity_predict
        result = boundary._compute_decision_boundary({"inputs": [[-1, -1], [1, 1], [0, 0]], "targets": [0, 1, 0]})
        bounds = result["bounds"]
        for key in ("x_min", "x_max", "y_min", "y_max"):
            assert key in bounds
            assert isinstance(bounds[key], float)
        assert bounds["x_min"] < bounds["x_max"]
        assert bounds["y_min"] < bounds["y_max"]


class TestDecisionBoundaryInheritance:
    """Test BaseComponent inheritance."""

    def test_inherits_from_base_component(self, boundary):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(boundary, BaseComponent)

    def test_has_logger(self, boundary):
        """Should have logger from BaseComponent."""
        assert hasattr(boundary, "logger")
        assert boundary.logger is not None

    def test_has_config(self, boundary):
        """Should have config from BaseComponent."""
        assert hasattr(boundary, "config")

    def test_has_component_id(self, boundary):
        """Should have component_id from BaseComponent."""
        assert hasattr(boundary, "component_id")
        assert boundary.component_id == "test-boundary"


class TestDecisionBoundaryConfiguration:
    """Test configuration handling."""

    def test_config_override_resolution(self):
        """Should override resolution from config."""
        config = {"boundary_resolution": 100}
        boundary = DecisionBoundary(config)
        assert boundary.resolution == 100

    def test_config_override_show_confidence(self):
        """Should override show_confidence from config."""
        config = {"show_confidence": False}
        boundary = DecisionBoundary(config)
        assert boundary.show_confidence is False

    def test_config_multiple_overrides(self):
        """Should handle multiple config overrides."""
        config = {
            "boundary_resolution": 75,
            "show_confidence": False,
        }
        boundary = DecisionBoundary(config)
        assert boundary.resolution == 75
        assert boundary.show_confidence is False


class TestDecisionBoundaryEdgeCases:
    """Test edge cases."""

    def test_very_high_resolution(self):
        """Should handle very high resolution."""
        config = {"boundary_resolution": 200}
        boundary = DecisionBoundary(config)
        assert boundary.resolution == 200

    def test_low_resolution(self):
        """Should handle low resolution."""
        config = {"boundary_resolution": 10}
        boundary = DecisionBoundary(config)
        assert boundary.resolution == 10

    def test_single_class_data(self, boundary):
        """Single-class dataset must not crash the boundary-plot path.

        Black-box replacement for the historically-skipped test
        (referenced a ``_create_contour_plot`` method that does not
        exist). With a single-class dataset the overlay produces just
        one scatter trace; the contour itself comes from the
        boundary-data dict.
        """
        boundary_data = {
            "xx": [[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]],
            "yy": [[-1, -1, -1], [0, 0, 0], [1, 1, 1]],
            "Z": [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
        }
        dataset = {"inputs": [[0.1, 0.1], [0.2, 0.2]], "targets": [0, 0]}
        fig = boundary._create_boundary_plot(boundary_data, dataset, True, "light")
        assert fig is not None
        from plotly.graph_objs import Scatter

        scatters = [t for t in fig.data if isinstance(t, Scatter)]
        assert len(scatters) == 1, "single-class data should produce exactly one scatter overlay"

    def test_collinear_data(self, boundary):
        """Collinear dataset must not crash the boundary-plot path."""
        boundary_data = {
            "xx": [[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]],
            "yy": [[-1, -1, -1], [0, 0, 0], [1, 1, 1]],
            "Z": [[0, 1, 0], [1, 0, 1], [0, 1, 0]],
        }
        # All points on y=x diagonal (collinear), with two classes.
        dataset = {
            "inputs": [[float(i), float(i)] for i in range(5)],
            "targets": [0, 1, 0, 1, 0],
        }
        fig = boundary._create_boundary_plot(boundary_data, dataset, True, "light")
        assert fig is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
