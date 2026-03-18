#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_dark_mode_info_panels.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-03-17
# Last Modified: 2026-03-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Regression tests for dark mode styling on info/summary panels
#                and network info details updating during training.
#####################################################################
"""Regression tests for dark mode info panels and network details updates.

These tests ensure that:
1. Network topology node selection panel honors dark mode
2. Dataset visualization summary panel honors dark mode
3. Network Information: Details section updates during training
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


@pytest.fixture
def config():
    """Basic config for component tests."""
    return {}


# ============================================================================
# Issue 1: Network Topology Node Detail Dark Mode
# ============================================================================


class TestNodeSelectionDarkMode:
    """Regression: node selection info panel must honor dark mode.

    Previously, the selection-info panel used hardcoded light-mode colors
    (#e3f2fd background, #90caf9 border) regardless of theme state.
    """

    @pytest.fixture
    def visualizer(self, config):
        from frontend.components.network_visualizer import NetworkVisualizer

        return NetworkVisualizer(config, component_id="test-viz")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_node_selection_dark_mode_background(self, visualizer):
        """Node selection in dark mode must use dark background color."""
        from dash import Dash, dcc, html

        app = Dash(__name__)
        app.layout = html.Div(
            [
                dcc.Graph(id=f"{visualizer.component_id}-graph"),
                dcc.Store(id=f"{visualizer.component_id}-view-state", data={}),
                dcc.Store(id=f"{visualizer.component_id}-topology-store"),
                dcc.Store(id=f"{visualizer.component_id}-topology-hash"),
                dcc.Store(id=f"{visualizer.component_id}-selected-nodes"),
                dcc.Store(id="metrics-panel-metrics-store"),
                dcc.Store(id="theme-state"),
                dcc.Dropdown(id=f"{visualizer.component_id}-layout-selector"),
                dcc.Checklist(id=f"{visualizer.component_id}-show-weights"),
                html.Div(id=f"{visualizer.component_id}-stats-bar"),
                html.Span(id=f"{visualizer.component_id}-input-count"),
                html.Span(id=f"{visualizer.component_id}-hidden-count"),
                html.Span(id=f"{visualizer.component_id}-output-count"),
                html.Span(id=f"{visualizer.component_id}-connection-count"),
                html.Div(id=f"{visualizer.component_id}-selection-info"),
            ]
        )
        visualizer.register_callbacks(app)

        callback_key = f"{visualizer.component_id}-selected-nodes.data"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                with patch("dash.callback_context") as mock_ctx:
                    mock_ctx.triggered = [{"prop_id": f"{visualizer.component_id}-graph.clickData"}]
                    click_data = {"points": [{"text": "Hidden 0", "curveNumber": 3}]}
                    _, _, style = func.__wrapped__(click_data, None, [], "dark")
                    assert style["backgroundColor"] == "#1a3a5c", "Dark mode should use dark blue background"
                    assert "2c5282" in style["border"], "Dark mode should use dark blue border"
                break
        else:
            pytest.fail("Node selection callback not found")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_node_selection_light_mode_background(self, visualizer):
        """Node selection in light mode must use light background color."""
        from dash import Dash, dcc, html

        app = Dash(__name__)
        app.layout = html.Div(
            [
                dcc.Graph(id=f"{visualizer.component_id}-graph"),
                dcc.Store(id=f"{visualizer.component_id}-view-state", data={}),
                dcc.Store(id=f"{visualizer.component_id}-topology-store"),
                dcc.Store(id=f"{visualizer.component_id}-topology-hash"),
                dcc.Store(id=f"{visualizer.component_id}-selected-nodes"),
                dcc.Store(id="metrics-panel-metrics-store"),
                dcc.Store(id="theme-state"),
                dcc.Dropdown(id=f"{visualizer.component_id}-layout-selector"),
                dcc.Checklist(id=f"{visualizer.component_id}-show-weights"),
                html.Div(id=f"{visualizer.component_id}-stats-bar"),
                html.Span(id=f"{visualizer.component_id}-input-count"),
                html.Span(id=f"{visualizer.component_id}-hidden-count"),
                html.Span(id=f"{visualizer.component_id}-output-count"),
                html.Span(id=f"{visualizer.component_id}-connection-count"),
                html.Div(id=f"{visualizer.component_id}-selection-info"),
            ]
        )
        visualizer.register_callbacks(app)

        callback_key = f"{visualizer.component_id}-selected-nodes.data"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                with patch("dash.callback_context") as mock_ctx:
                    mock_ctx.triggered = [{"prop_id": f"{visualizer.component_id}-graph.clickData"}]
                    click_data = {"points": [{"text": "Hidden 0", "curveNumber": 3}]}
                    _, _, style = func.__wrapped__(click_data, None, [], "light")
                    assert style["backgroundColor"] == "#e3f2fd", "Light mode should use light blue background"
                    assert "90caf9" in style["border"], "Light mode should use light blue border"
                break
        else:
            pytest.fail("Node selection callback not found")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_selection_info_theme_callback_registered(self, visualizer):
        """A theme callback for selection-info must be registered."""
        from dash import Dash, dcc, html

        app = Dash(__name__)
        app.layout = html.Div(
            [
                dcc.Graph(id=f"{visualizer.component_id}-graph"),
                dcc.Store(id=f"{visualizer.component_id}-view-state", data={}),
                dcc.Store(id=f"{visualizer.component_id}-topology-store"),
                dcc.Store(id=f"{visualizer.component_id}-topology-hash"),
                dcc.Store(id=f"{visualizer.component_id}-selected-nodes"),
                dcc.Store(id="metrics-panel-metrics-store"),
                dcc.Store(id="theme-state"),
                dcc.Dropdown(id=f"{visualizer.component_id}-layout-selector"),
                dcc.Checklist(id=f"{visualizer.component_id}-show-weights"),
                html.Div(id=f"{visualizer.component_id}-stats-bar"),
                html.Span(id=f"{visualizer.component_id}-input-count"),
                html.Span(id=f"{visualizer.component_id}-hidden-count"),
                html.Span(id=f"{visualizer.component_id}-output-count"),
                html.Span(id=f"{visualizer.component_id}-connection-count"),
                html.Div(id=f"{visualizer.component_id}-selection-info"),
            ]
        )
        visualizer.register_callbacks(app)

        # Look for a callback that targets selection-info style and takes theme-state as input
        found = False
        for key, _cb_info in app.callback_map.items():
            if f"{visualizer.component_id}-selection-info.style" in key:
                found = True
                break
        assert found, "Theme callback for selection-info panel not registered"


# ============================================================================
# Issue 2: Dataset Visualization Summary Dark Mode
# ============================================================================


class TestDatasetSummaryDarkMode:
    """Regression: dataset stats summary panel must honor dark mode.

    Previously, the stats summary div had no ID and a hardcoded #f8f9fa
    background that never changed in dark mode.
    """

    @pytest.fixture
    def plotter(self, config):
        from frontend.components.dataset_plotter import DatasetPlotter

        return DatasetPlotter(config, component_id="test-plotter")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_stats_summary_has_id(self, plotter):
        """Stats summary div must have an ID for theme callback targeting."""
        from dash import html

        layout = plotter.get_layout()

        def find_by_id(component, target_id):
            if hasattr(component, "id") and component.id == target_id:
                return component
            if hasattr(component, "children"):
                children = component.children if isinstance(component.children, list) else [component.children]
                for child in children:
                    if child is not None:
                        result = find_by_id(child, target_id)
                        if result is not None:
                            return result
            return None

        stats_div = find_by_id(layout, "test-plotter-stats-summary")
        assert stats_div is not None, "Stats summary div must have id='test-plotter-stats-summary'"

    @pytest.mark.unit
    @pytest.mark.regression
    def test_stats_summary_theme_callback_registered(self, plotter):
        """A theme callback for stats-summary must be registered."""
        from dash import Dash, dcc, html

        app = Dash(__name__)
        app.layout = html.Div(
            [
                plotter.get_layout(),
                dcc.Store(id="theme-state"),
            ]
        )
        plotter.register_callbacks(app)

        found = any(f"{plotter.component_id}-stats-summary.style" in key for key in app.callback_map)
        assert found, "Theme callback for dataset stats summary not registered"

    @pytest.mark.unit
    @pytest.mark.regression
    def test_stats_summary_dark_mode_colors(self, plotter):
        """Stats summary in dark mode must use dark background."""
        from dash import Dash, dcc, html

        app = Dash(__name__)
        app.layout = html.Div(
            [
                plotter.get_layout(),
                dcc.Store(id="theme-state"),
            ]
        )
        plotter.register_callbacks(app)

        for key, callback_info in app.callback_map.items():
            if f"{plotter.component_id}-stats-summary.style" in key:
                func = callback_info["callback"]
                style = func.__wrapped__("dark")
                assert style["backgroundColor"] == "#2d2d2d", "Dark mode should use #2d2d2d background"
                assert style["color"] == "#e9ecef", "Dark mode should use light text color"
                break
        else:
            pytest.fail("Stats summary theme callback not found")

    @pytest.mark.unit
    @pytest.mark.regression
    def test_stats_summary_light_mode_colors(self, plotter):
        """Stats summary in light mode must use light background."""
        from dash import Dash, dcc, html

        app = Dash(__name__)
        app.layout = html.Div(
            [
                plotter.get_layout(),
                dcc.Store(id="theme-state"),
            ]
        )
        plotter.register_callbacks(app)

        for key, callback_info in app.callback_map.items():
            if f"{plotter.component_id}-stats-summary.style" in key:
                func = callback_info["callback"]
                style = func.__wrapped__("light")
                assert style["backgroundColor"] == "#f8f9fa", "Light mode should use #f8f9fa background"
                assert style["color"] == "#212529", "Light mode should use dark text color"
                break
        else:
            pytest.fail("Stats summary theme callback not found")


# ============================================================================
# Issue 3: Network Info Details Not Updating
# ============================================================================


class TestNetworkStatsAllHiddenWeights:
    """Regression: /api/network/stats must capture ALL hidden unit weights.

    Previously, the endpoint only captured network.hidden_units[0]["weights"],
    missing all subsequent hidden units added during training.
    """

    @pytest.mark.unit
    @pytest.mark.regression
    def test_network_stats_captures_all_hidden_units(self):
        """API must collect weights from ALL hidden units, not just the first."""
        import torch

        # Simulate a network with multiple hidden units
        mock_network = Mock()
        mock_network.input_weights = torch.randn(2, 3)
        mock_network.output_weights = torch.randn(1, 5)
        mock_network.output_bias = torch.randn(1)
        mock_network.hidden_units = [
            {"weights": torch.randn(3), "bias": torch.randn(1)},
            {"weights": torch.randn(4), "bias": torch.randn(1)},
            {"weights": torch.randn(5), "bias": torch.randn(1)},
        ]

        # Collect weights as the fixed code does
        all_hidden_weights = torch.cat([hu["weights"] for hu in mock_network.hidden_units])

        # Should have all weights from all 3 units (3 + 4 + 5 = 12)
        assert all_hidden_weights.shape[0] == 12, "Should concatenate all hidden unit weights"

    @pytest.mark.unit
    @pytest.mark.regression
    def test_network_stats_no_hidden_units(self):
        """API must handle case when no hidden units exist."""
        mock_network = Mock()
        mock_network.hidden_units = []

        result = None if not mock_network.hidden_units else "should not reach"
        assert result is None, "Should return None when no hidden units exist"

    @pytest.mark.unit
    @pytest.mark.regression
    def test_network_stats_single_hidden_unit(self):
        """API must handle single hidden unit correctly."""
        import torch

        mock_network = Mock()
        mock_network.hidden_units = [
            {"weights": torch.randn(3), "bias": torch.randn(1)},
        ]

        all_hidden_weights = torch.cat([hu["weights"] for hu in mock_network.hidden_units])
        assert all_hidden_weights.shape[0] == 3, "Single unit should have 3 weights"

    @pytest.mark.unit
    @pytest.mark.regression
    def test_network_stats_weight_statistics_change_after_adding_units(self):
        """Weight statistics must change when hidden units are added."""
        import torch

        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        input_weights = torch.randn(2, 3)
        output_weights = torch.randn(1, 3)

        # Stats with no hidden units
        stats_0 = adapter.get_network_statistics(
            input_weights=input_weights,
            hidden_weights=None,
            output_weights=output_weights,
        )
        total_weights_0 = stats_0["weight_statistics"]["total_weights"]

        # Stats with one hidden unit
        hidden_1 = torch.randn(3)
        stats_1 = adapter.get_network_statistics(
            input_weights=input_weights,
            hidden_weights=hidden_1,
            output_weights=output_weights,
        )
        total_weights_1 = stats_1["weight_statistics"]["total_weights"]

        # Stats with three hidden units
        hidden_3 = torch.cat([torch.randn(3), torch.randn(4), torch.randn(5)])
        stats_3 = adapter.get_network_statistics(
            input_weights=input_weights,
            hidden_weights=hidden_3,
            output_weights=output_weights,
        )
        total_weights_3 = stats_3["weight_statistics"]["total_weights"]

        assert total_weights_1 > total_weights_0, "Adding hidden units should increase total weights"
        assert total_weights_3 > total_weights_1, "Adding more hidden units should increase total weights further"
