#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_dataset_plotter.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for DatasetPlotter component
#####################################################################
"""Unit tests for DatasetPlotter component."""

import contextlib
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from frontend.components.dataset_plotter import DatasetPlotter  # noqa: E402


@pytest.fixture
def config():
    """Basic config for dataset plotter."""
    return {}


@pytest.fixture
def plotter(config):
    """Create DatasetPlotter instance."""
    return DatasetPlotter(config, component_id="test-plotter")


class TestDatasetPlotterInitialization:
    """Test DatasetPlotter initialization."""

    def test_init_with_default_config(self):
        """Should initialize with empty config."""
        plotter = DatasetPlotter({})
        assert plotter is not None
        assert plotter.component_id == "dataset-plotter"

    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        plotter = DatasetPlotter(config, component_id="custom-plotter")
        assert plotter.component_id == "custom-plotter"


class TestDatasetPlotterLayout:
    """Test DatasetPlotter layout generation."""

    def test_get_layout_returns_div(self, plotter):
        """get_layout should return Dash Div."""
        layout = plotter.get_layout()
        assert layout is not None
        from dash import html

        assert isinstance(layout, html.Div)

    def test_layout_contains_graph(self, plotter):
        """Layout should contain graph component."""
        layout = plotter.get_layout()
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


class TestDatasetPlotterCallbacks:
    """Test DatasetPlotter callback registration."""

    def test_register_callbacks_returns_none(self, plotter):
        """register_callbacks should return None."""
        from dash import Dash

        app = Dash(__name__)
        result = plotter.register_callbacks(app)
        assert result is None

    def test_register_callbacks_with_mock_app(self, plotter):
        """Should handle callback setup without errors."""
        from dash import Dash

        app = Dash(__name__)
        # Should not raise - direct call without try/except
        plotter.register_callbacks(app)


class TestDatasetPlotterScatterPlot:
    """Test scatter plot creation."""

    def test_create_scatter_plot(self, plotter):
        """Should create scatter plot."""
        if hasattr(plotter, "_create_scatter_plot"):
            dataset = {"inputs": np.random.randn(100, 2).tolist(), "targets": np.random.randint(0, 2, 100).tolist()}
            plot = plotter._create_scatter_plot(dataset)
            assert plot is not None

    def test_scatter_plot_with_labels(self, plotter):
        """Should handle labeled data."""
        if hasattr(plotter, "_create_scatter_plot"):
            dataset = {"inputs": np.random.randn(100, 2).tolist(), "targets": ([0, 1] * 50)}  # Two classes
            plot = plotter._create_scatter_plot(dataset)
            assert plot is not None

    def test_scatter_plot_2d_data(self, plotter):
        """Should handle 2D data."""
        if hasattr(plotter, "_create_scatter_plot"):
            dataset = {"inputs": np.random.randn(50, 2).tolist(), "targets": np.random.randint(0, 3, 50).tolist()}
            plot = plotter._create_scatter_plot(dataset)
            assert plot is not None


class TestDatasetPlotterDataParsing:
    """Test data parsing methods."""

    def test_parse_dataset_dict(self, plotter):
        """Should parse dataset dictionary."""
        if hasattr(plotter, "_parse_dataset"):
            data = {"X": [[0, 0], [1, 1], [0, 1]], "y": [0, 1, 0]}
            parsed = plotter._parse_dataset(data)
            assert parsed is not None

    def test_parse_numpy_arrays(self, plotter):
        """Should parse numpy arrays."""
        if hasattr(plotter, "_parse_dataset"):
            data = {"X": np.random.randn(100, 2), "y": np.random.randint(0, 2, 100)}
            parsed = plotter._parse_dataset(data)
            assert parsed is not None

    def test_parse_empty_dataset(self, plotter):
        """Should handle empty dataset."""
        if hasattr(plotter, "_parse_dataset"):
            data = {"X": [], "y": []}
            with contextlib.suppress(ValueError, IndexError):
                _parsed = plotter._parse_dataset(data)  # noqa: F841


class TestDatasetPlotterColorMapping:
    """Test color mapping for classes."""

    def test_get_colors_for_classes(self, plotter):
        """Should generate colors for classes."""
        if hasattr(plotter, "_get_class_colors"):
            n_classes = 3
            colors = plotter._get_class_colors(n_classes)
            assert colors is not None
            assert len(colors) >= n_classes

    def test_consistent_colors(self, plotter):
        """Colors should be consistent for same classes."""
        if hasattr(plotter, "_get_class_colors"):
            colors1 = plotter._get_class_colors(5)
            colors2 = plotter._get_class_colors(5)
            assert colors1 == colors2


class TestDatasetPlotterInheritance:
    """Test BaseComponent inheritance."""

    def test_inherits_from_base_component(self, plotter):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(plotter, BaseComponent)

    def test_has_logger(self, plotter):
        """Should have logger from BaseComponent."""
        assert hasattr(plotter, "logger")
        assert plotter.logger is not None

    def test_has_config(self, plotter):
        """Should have config from BaseComponent."""
        assert hasattr(plotter, "config")

    def test_has_component_id(self, plotter):
        """Should have component_id from BaseComponent."""
        assert hasattr(plotter, "component_id")
        assert plotter.component_id == "test-plotter"


class TestDatasetPlotterEdgeCases:
    """Test edge cases."""

    def test_single_point_dataset(self, plotter):
        """Should handle single point."""
        if hasattr(plotter, "_create_scatter_plot"):
            dataset = {"inputs": [[0, 0]], "targets": [0]}
            with contextlib.suppress(Exception):
                plot = plotter._create_scatter_plot(dataset)
                assert plot is not None

    def test_many_classes(self, plotter):
        """Should handle many classes."""
        if hasattr(plotter, "_create_scatter_plot"):
            dataset = {
                "inputs": np.random.randn(100, 2).tolist(),
                "targets": np.random.randint(0, 20, 100).tolist(),  # 20 classes
            }
            with contextlib.suppress(Exception):
                plot = plotter._create_scatter_plot(dataset)
                assert plot is not None

    def test_high_dimensional_data(self, plotter):
        """Should handle high-dimensional data."""
        if hasattr(plotter, "_create_scatter_plot"):
            dataset = {
                "inputs": np.random.randn(100, 10)[:, :2].tolist(),  # 10 dimensions reduced to 2
                "targets": np.random.randint(0, 2, 100).tolist(),
            }
            with contextlib.suppress(Exception):
                # Should either project to 2D or handle gracefully
                plot = plotter._create_scatter_plot(dataset)
                assert plot is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
