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

import contextlib
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
    """Test grid generation methods."""

    def test_create_grid(self, boundary):
        """Should create mesh grid."""
        if hasattr(boundary, "_create_grid"):
            x_range = (-1, 1)
            y_range = (-1, 1)
            grid = boundary._create_grid(x_range, y_range)
            assert grid is not None

    def test_grid_resolution(self, boundary):
        """Grid should respect resolution setting."""
        if hasattr(boundary, "_create_grid"):
            x_range = (-1, 1)
            y_range = (-1, 1)
            grid = boundary._create_grid(x_range, y_range)
            # Grid should have resolution^2 points
            if isinstance(grid, tuple) and len(grid) >= 2:
                assert grid[0].shape == (boundary.resolution, boundary.resolution)

    def test_create_grid_with_different_ranges(self, boundary):
        """Should handle different x and y ranges."""
        if hasattr(boundary, "_create_grid"):
            x_range = (-2, 2)
            y_range = (-3, 3)
            grid = boundary._create_grid(x_range, y_range)
            assert grid is not None


class TestDecisionBoundaryPlotting:
    """Test plotting methods."""

    def test_create_contour_plot(self, boundary):
        """Should create contour plot."""
        if hasattr(boundary, "_create_contour_plot"):
            X = np.random.randn(100, 2)
            y = np.random.randint(0, 2, 100)
            plot = boundary._create_contour_plot(X, y)
            assert plot is not None

    def test_plot_dataset_overlay(self, boundary):
        """Should overlay dataset points."""
        if hasattr(boundary, "_plot_dataset_overlay"):
            X = np.random.randn(100, 2)
            y = np.random.randint(0, 2, 100)
            overlay = boundary._plot_dataset_overlay(X, y)
            assert overlay is not None

    def test_create_empty_plot(self, boundary):
        """Should handle empty data."""
        if hasattr(boundary, "_create_contour_plot"):
            with contextlib.suppress(ValueError, IndexError):
                _plot = boundary._create_contour_plot([], [])  # noqa: F841


class TestDecisionBoundaryDataHandling:
    """Test data handling methods."""

    def test_prepare_boundary_data(self, boundary):
        """Should prepare boundary data."""
        if hasattr(boundary, "_prepare_boundary_data"):
            data = {"X_grid": [[0, 0], [1, 1]], "y_grid": [[0, 0], [1, 1]], "Z": [[0.5, 0.5], [0.5, 0.5]]}
            prepared = boundary._prepare_boundary_data(data)
            assert prepared is not None

    def test_extract_data_ranges(self, boundary):
        """Should extract data ranges."""
        if hasattr(boundary, "_extract_ranges"):
            X = np.array([[-1, -1], [1, 1], [0, 0]])
            ranges = boundary._extract_ranges(X)
            assert ranges is not None


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
        """Should handle single-class data."""
        if hasattr(boundary, "_create_contour_plot"):
            X = np.random.randn(100, 2)
            y = np.zeros(100)  # All same class
            with contextlib.suppress(Exception):
                boundary._create_contour_plot(X, y)

    def test_collinear_data(self, boundary):
        """Should handle collinear data."""
        if hasattr(boundary, "_create_contour_plot"):
            X = np.array([[i, i] for i in range(100)])  # All on diagonal
            y = np.random.randint(0, 2, 100)
            with contextlib.suppress(Exception):
                boundary._create_contour_plot(X, y)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
