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
        dataset = {"inputs": np.random.randn(100, 2).tolist(), "targets": np.random.randint(0, 2, 100).tolist()}
        plot = plotter._create_scatter_plot(dataset)
        assert plot is not None

    def test_scatter_plot_with_labels(self, plotter):
        """Should handle labeled data."""
        dataset = {"inputs": np.random.randn(100, 2).tolist(), "targets": ([0, 1] * 50)}  # Two classes
        plot = plotter._create_scatter_plot(dataset)
        assert plot is not None

    def test_scatter_plot_2d_data(self, plotter):
        """Should handle 2D data."""
        dataset = {"inputs": np.random.randn(50, 2).tolist(), "targets": np.random.randint(0, 3, 50).tolist()}
        plot = plotter._create_scatter_plot(dataset)
        assert plot is not None


class TestDatasetPlotterDataParsing:
    """Test data parsing via the public scatter-plot path.

    Black-box replacement for the historically-skipped
    ``TestDatasetPlotterDataParsing`` (asserted on a ``_parse_dataset``
    method that does not exist — dataset parsing happens inline inside
    ``_create_scatter_plot``, the actual observable seam). Each test
    feeds a dataset dict through ``_create_scatter_plot`` and inspects
    the returned figure for the expected trace shape, proving parsing
    succeeded.

    The expected key shape is the one ``_create_scatter_plot`` actually
    consumes: ``{"inputs": ..., "targets": ...}``. The skipped tests
    used ``{"X": ..., "y": ...}`` — neither the canopy code nor any
    caller produces that shape.
    """

    def test_parse_dataset_dict(self, plotter):
        """Parse dataset dict with list-of-list inputs."""
        data = {"inputs": [[0, 0], [1, 1], [0, 1]], "targets": [0, 1, 0]}
        fig = plotter._create_scatter_plot(data)
        assert fig is not None
        # Two unique classes ↦ two scatter traces.
        assert len(fig.data) == 2

    def test_parse_numpy_arrays(self, plotter):
        """Parse numpy arrays converted via .tolist()."""
        X = np.random.randn(100, 2)
        y = np.random.randint(0, 2, 100)
        data = {"inputs": X.tolist(), "targets": y.tolist()}
        fig = plotter._create_scatter_plot(data)
        assert fig is not None
        assert len(fig.data) == len(np.unique(y))

    def test_parse_empty_dataset(self, plotter):
        """Empty dataset returns the documented empty plot, does not raise.

        ``_create_scatter_plot`` returns ``create_empty_plot("No data
        available", theme)`` for ``len(inputs) == 0`` so the dashboard
        survives missing-data states. The skipped test asserted
        ``pytest.raises`` which assumed a different contract.
        """
        data = {"inputs": [], "targets": []}
        fig = plotter._create_scatter_plot(data)
        assert fig is not None


class TestDatasetPlotterColorMapping:
    """Test color mapping for classes.

    Black-box replacement for the historically-skipped
    ``TestDatasetPlotterColorMapping`` (asserted on a
    ``_get_class_colors(n_classes)`` method that does not exist — class
    colors come from ``plotter.default_colors``, a fixed palette that
    ``_create_scatter_plot`` indexes into with ``i % len(default_colors)``).
    """

    def test_default_colors_palette_exists(self, plotter):
        """``default_colors`` is the canonical palette: non-empty list of hex strings."""
        assert hasattr(plotter, "default_colors"), "DatasetPlotter must expose default_colors palette"
        assert isinstance(plotter.default_colors, list)
        assert len(plotter.default_colors) > 0
        for color in plotter.default_colors:
            assert isinstance(color, str)
            assert color.startswith("#")

    def test_scatter_plot_assigns_distinct_colors_per_class(self, plotter):
        """Two classes ↦ two scatter traces with distinct marker colors drawn from the palette."""
        data = {"inputs": [[0, 0], [1, 1], [2, 2], [3, 3]], "targets": [0, 0, 1, 1]}
        fig = plotter._create_scatter_plot(data)
        assert len(fig.data) == 2
        color_0 = fig.data[0].marker.color
        color_1 = fig.data[1].marker.color
        assert color_0 != color_1
        assert color_0 in plotter.default_colors
        assert color_1 in plotter.default_colors

    def test_color_assignment_is_deterministic_for_same_class_set(self, plotter):
        """Same class set ↦ identical color assignment (no RNG)."""
        data = {"inputs": [[0, 0], [1, 1], [2, 2]], "targets": [0, 1, 2]}
        fig1 = plotter._create_scatter_plot(data)
        fig2 = plotter._create_scatter_plot(data)
        colors1 = [trace.marker.color for trace in fig1.data]
        colors2 = [trace.marker.color for trace in fig2.data]
        assert colors1 == colors2

    def test_color_assignment_wraps_when_classes_exceed_palette(self, plotter):
        """Class index wraps modulo palette length.

        ``_create_scatter_plot`` uses ``default_colors[i % len(default_colors)]``,
        so class ``len(palette)`` reuses color index 0. Pinning this
        prevents an IndexError regression when the palette is ever
        truncated or datasets carry many classes.
        """
        palette_len = len(plotter.default_colors)
        n_classes = palette_len + 1
        inputs = [[float(i), float(i)] for i in range(n_classes)]
        targets = list(range(n_classes))
        data = {"inputs": inputs, "targets": targets}
        fig = plotter._create_scatter_plot(data)
        assert len(fig.data) == n_classes
        # The wrap-around class (index palette_len) reuses color 0.
        assert fig.data[0].marker.color == fig.data[palette_len].marker.color


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
        dataset = {"inputs": [[0, 0]], "targets": [0]}
        plot = plotter._create_scatter_plot(dataset)
        assert plot is not None

    def test_many_classes(self, plotter):
        """Should handle many classes."""
        dataset = {
            "inputs": np.random.randn(100, 2).tolist(),
            "targets": np.random.randint(0, 20, 100).tolist(),  # 20 classes
        }
        plot = plotter._create_scatter_plot(dataset)
        assert plot is not None

    def test_high_dimensional_data(self, plotter):
        """Should handle high-dimensional data."""
        dataset = {
            "inputs": np.random.randn(100, 10)[:, :2].tolist(),  # 10 dimensions reduced to 2
            "targets": np.random.randint(0, 2, 100).tolist(),
        }
        # Should either project to 2D or handle gracefully
        plot = plotter._create_scatter_plot(dataset)
        assert plot is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
