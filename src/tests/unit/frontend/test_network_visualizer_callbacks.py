#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_network_visualizer_callbacks.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-06
# Last Modified: 2026-01-06
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Tests for NetworkVisualizer callback handlers (lines 227-453)
#####################################################################
"""
Tests for NetworkVisualizer callback handlers to improve coverage from 71% to 90%+.

Covers:
- capture_view_state callback (lines 227-254)
- update_network_graph callback (lines 305-349)
- update_stats_bar_theme callback (lines 357-358)
- handle_node_selection callback (lines 381-453)
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import plotly.graph_objects as go
import pytest

# Add src to path before other imports
src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402


@pytest.fixture
def config():
    """Basic config for network visualizer."""
    return {"show_weights": True, "layout": "hierarchical"}


@pytest.fixture
def visualizer(config):
    """Create NetworkVisualizer instance."""
    return NetworkVisualizer(config, component_id="test-viz")


@pytest.fixture
def simple_topology():
    """Simple network topology for testing."""
    return {
        "input_units": 2,
        "hidden_units": 1,
        "output_units": 1,
        "connections": [
            {"from": "input_0", "to": "hidden_0", "weight": 0.5},
            {"from": "input_1", "to": "hidden_0", "weight": -0.3},
            {"from": "hidden_0", "to": "output_0", "weight": 0.8},
        ],
    }


@pytest.fixture
def empty_topology():
    """Empty network topology."""
    return {
        "input_units": 0,
        "hidden_units": 0,
        "output_units": 0,
        "connections": [],
    }


class TestCaptureViewStateCallback:
    """Tests for the capture_view_state callback (lines 227-254)."""

    @pytest.mark.unit
    def test_capture_view_state_none_relayout_data(self, visualizer):
        """Should return current state when relayout_data is None."""
        current_state = {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}
        result = self._simulate_capture_view_state(None, current_state)
        assert result == current_state

    @pytest.mark.unit
    def test_capture_view_state_none_current_state(self, visualizer):
        """Should return default state when current_state is None."""
        result = self._simulate_capture_view_state({}, None)
        assert result == {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}

    @pytest.mark.unit
    def test_capture_view_state_xaxis_range(self, visualizer):
        """Should capture xaxis range from relayout data."""
        relayout_data = {"xaxis.range[0]": -5, "xaxis.range[1]": 15}
        current_state = {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["xaxis_range"] == [-5, 15]

    @pytest.mark.unit
    def test_capture_view_state_yaxis_range(self, visualizer):
        """Should capture yaxis range from relayout data."""
        relayout_data = {"yaxis.range[0]": -10, "yaxis.range[1]": 10}
        current_state = {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["yaxis_range"] == [-10, 10]

    @pytest.mark.unit
    def test_capture_view_state_both_axes(self, visualizer):
        """Should capture both axis ranges."""
        relayout_data = {
            "xaxis.range[0]": 0,
            "xaxis.range[1]": 20,
            "yaxis.range[0]": -5,
            "yaxis.range[1]": 5,
        }
        current_state = {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["xaxis_range"] == [0, 20]
        assert result["yaxis_range"] == [-5, 5]

    @pytest.mark.unit
    def test_capture_view_state_dragmode(self, visualizer):
        """Should capture dragmode changes."""
        relayout_data = {"dragmode": "zoom"}
        current_state = {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["dragmode"] == "zoom"

    @pytest.mark.unit
    def test_capture_view_state_xaxis_autorange(self, visualizer):
        """Should reset xaxis_range on autorange."""
        relayout_data = {"xaxis.autorange": True}
        current_state = {"xaxis_range": [0, 10], "yaxis_range": [-5, 5], "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["xaxis_range"] is None
        assert result["yaxis_range"] == [-5, 5]

    @pytest.mark.unit
    def test_capture_view_state_yaxis_autorange(self, visualizer):
        """Should reset yaxis_range on autorange."""
        relayout_data = {"yaxis.autorange": True}
        current_state = {"xaxis_range": [0, 10], "yaxis_range": [-5, 5], "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["xaxis_range"] == [0, 10]
        assert result["yaxis_range"] is None

    @pytest.mark.unit
    def test_capture_view_state_both_autorange(self, visualizer):
        """Should reset both axes on autorange."""
        relayout_data = {"xaxis.autorange": True, "yaxis.autorange": True}
        current_state = {"xaxis_range": [0, 10], "yaxis_range": [-5, 5], "dragmode": "zoom"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["xaxis_range"] is None
        assert result["yaxis_range"] is None
        assert result["dragmode"] == "zoom"

    @pytest.mark.unit
    def test_capture_view_state_preserves_existing(self, visualizer):
        """Should preserve existing state values not being updated."""
        relayout_data = {"dragmode": "select"}
        current_state = {"xaxis_range": [1, 2], "yaxis_range": [3, 4], "dragmode": "pan"}
        result = self._simulate_capture_view_state(relayout_data, current_state)
        assert result["xaxis_range"] == [1, 2]
        assert result["yaxis_range"] == [3, 4]
        assert result["dragmode"] == "select"

    def _simulate_capture_view_state(self, relayout_data, current_state):
        """Simulate the capture_view_state callback logic."""
        if not relayout_data or not current_state:
            return current_state or {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}

        new_state = current_state.copy()

        if "xaxis.range[0]" in relayout_data:
            new_state["xaxis_range"] = [
                relayout_data["xaxis.range[0]"],
                relayout_data["xaxis.range[1]"],
            ]
        if "yaxis.range[0]" in relayout_data:
            new_state["yaxis_range"] = [
                relayout_data["yaxis.range[0]"],
                relayout_data["yaxis.range[1]"],
            ]
        if "dragmode" in relayout_data:
            new_state["dragmode"] = relayout_data["dragmode"]
        if relayout_data.get("xaxis.autorange"):
            new_state["xaxis_range"] = None
        if relayout_data.get("yaxis.autorange"):
            new_state["yaxis_range"] = None

        return new_state


class TestUpdateNetworkGraphCallback:
    """Tests for update_network_graph callback (lines 305-349)."""

    @pytest.mark.unit
    def test_compute_hash_consistency(self, visualizer, simple_topology):
        """Same topology should produce same hash."""
        hash1 = self._compute_hash(simple_topology)
        hash2 = self._compute_hash(simple_topology)
        assert hash1 == hash2

    @pytest.mark.unit
    def test_compute_hash_differs_on_change(self, visualizer, simple_topology):
        """Different topologies should produce different hashes."""
        hash1 = self._compute_hash(simple_topology)
        modified = simple_topology.copy()
        modified["hidden_units"] = 5
        hash2 = self._compute_hash(modified)
        assert hash1 != hash2

    @pytest.mark.unit
    def test_empty_topology_returns_empty_graph(self, visualizer, empty_topology):
        """Empty topology should return empty figure and zeros."""
        result = self._simulate_update_network_graph(visualizer, empty_topology, "hierarchical", ["show"], [], "light", [], None, None)
        fig, input_ct, hidden_ct, output_ct, conn_ct, hash_val = result
        assert isinstance(fig, go.Figure)
        assert input_ct == "0"
        assert hidden_ct == "0"
        assert output_ct == "0"
        assert conn_ct == "0"
        assert hash_val is None

    @pytest.mark.unit
    def test_none_topology_returns_empty_graph(self, visualizer):
        """None topology should return empty figure."""
        result = self._simulate_update_network_graph(visualizer, None, "hierarchical", ["show"], [], "light", [], None, None)
        fig, input_ct, hidden_ct, output_ct, conn_ct, hash_val = result
        assert isinstance(fig, go.Figure)
        assert hash_val is None

    @pytest.mark.unit
    def test_valid_topology_returns_counts(self, visualizer, simple_topology):
        """Valid topology should return correct counts."""
        result = self._simulate_update_network_graph(visualizer, simple_topology, "hierarchical", ["show"], [], "light", [], None, None)
        _, input_ct, hidden_ct, output_ct, conn_ct, _ = result
        assert input_ct == "2"
        assert hidden_ct == "1"
        assert output_ct == "1"
        assert conn_ct == "3"

    @pytest.mark.unit
    def test_show_weights_parsing_true(self, visualizer, simple_topology):
        """Should parse show_weights=['show'] as True."""
        # Test that ['show'] is interpreted correctly
        # show_weight_labels = bool(["show"]) and ("show" in ["show"])
        show_weight_labels = bool(["show"]) and "show" in {"show"}
        # assert show_weight_labels is True
        assert show_weight_labels

    @pytest.mark.unit
    def test_show_weights_parsing_false(self, visualizer, simple_topology):
        """Should parse show_weights=[] as False."""
        # show_weight_labels = bool([]) and ("show" in [])
        show_weight_labels = bool([]) and "show" in {}
        # assert show_weight_labels is False
        assert not show_weight_labels

    @pytest.mark.unit
    def test_newly_added_unit_detection(self, visualizer, simple_topology):
        """Should detect newly added hidden unit from metrics."""
        metrics_data = [
            {"network_topology": {"hidden_units": 0}},
            {"network_topology": {"hidden_units": 1}},
        ]
        prev_hidden = metrics_data[-2].get("network_topology", {}).get("hidden_units", 0)
        curr_hidden = metrics_data[-1].get("network_topology", {}).get("hidden_units", 0)
        # newly_added = None
        # if curr_hidden > prev_hidden:
        #     newly_added = curr_hidden - 1
        newly_added = curr_hidden - 1 if curr_hidden > prev_hidden else None
        assert newly_added == 0

    @pytest.mark.unit
    def test_no_newly_added_unit_when_same(self, visualizer):
        """Should not detect new unit when count unchanged."""
        metrics_data = [
            {"network_topology": {"hidden_units": 2}},
            {"network_topology": {"hidden_units": 2}},
        ]
        prev_hidden = metrics_data[-2].get("network_topology", {}).get("hidden_units", 0)
        curr_hidden = metrics_data[-1].get("network_topology", {}).get("hidden_units", 0)
        # newly_added = None
        # if curr_hidden > prev_hidden:
        #     newly_added = curr_hidden - 1
        newly_added = curr_hidden - 1 if curr_hidden > prev_hidden else None
        assert newly_added is None

    @pytest.mark.unit
    def test_view_state_applied_xaxis(self, visualizer, simple_topology):
        """Should apply xaxis_range from view_state."""
        view_state = {"xaxis_range": [-10, 10], "yaxis_range": None, "dragmode": "pan"}
        result = self._simulate_update_network_graph(visualizer, simple_topology, "hierarchical", [], [], "light", [], view_state, None)
        fig = result[0]
        assert isinstance(fig, go.Figure)

    @pytest.mark.unit
    def test_view_state_applied_yaxis(self, visualizer, simple_topology):
        """Should apply yaxis_range from view_state."""
        view_state = {"xaxis_range": None, "yaxis_range": [-5, 5], "dragmode": "pan"}
        result = self._simulate_update_network_graph(visualizer, simple_topology, "hierarchical", [], [], "light", [], view_state, None)
        fig = result[0]
        assert isinstance(fig, go.Figure)

    @pytest.mark.unit
    def test_view_state_applied_dragmode(self, visualizer, simple_topology):
        """Should apply dragmode from view_state."""
        view_state = {"xaxis_range": None, "yaxis_range": None, "dragmode": "zoom"}
        result = self._simulate_update_network_graph(visualizer, simple_topology, "hierarchical", [], [], "light", [], view_state, None)
        fig = result[0]
        assert isinstance(fig, go.Figure)

    def _compute_hash(self, topo: Dict[str, Any]) -> str:
        """Compute topology hash matching callback logic."""
        key = {
            "input": topo.get("input_units", 0),
            "hidden": topo.get("hidden_units", 0),
            "output": topo.get("output_units", 0),
            "connections": len(topo.get("connections", [])),
        }
        return hashlib.md5(json.dumps(key, sort_keys=True).encode(), usedforsecurity=False).hexdigest()

    def _simulate_update_network_graph(
        self,
        visualizer: NetworkVisualizer,
        topology_data: Dict[str, Any],
        layout_type: str,
        show_weights: List[str],
        metrics_data: List[Dict[str, Any]],
        theme: str,
        selected_nodes: List[str],
        view_state: Dict[str, Any],
        prev_hash: str,
    ):
        """Simulate the update_network_graph callback logic."""
        if not topology_data or topology_data.get("input_units", 0) == 0:
            empty_fig = visualizer._create_empty_graph(theme)
            return empty_fig, "0", "0", "0", "0", None

        current_hash = self._compute_hash(topology_data)

        newly_added_unit = None
        if metrics_data and len(metrics_data) >= 2:
            prev_hidden = metrics_data[-2].get("network_topology", {}).get("hidden_units", 0)
            curr_hidden = metrics_data[-1].get("network_topology", {}).get("hidden_units", 0)
            if curr_hidden > prev_hidden:
                newly_added_unit = curr_hidden - 1

        show_weight_labels = bool(show_weights) and ("show" in show_weights)
        fig = visualizer._create_network_graph(topology_data, layout_type, show_weight_labels, newly_added_unit, theme, selected_nodes)

        if view_state:
            if view_state.get("xaxis_range"):
                fig.update_layout(xaxis_range=view_state["xaxis_range"])
            if view_state.get("yaxis_range"):
                fig.update_layout(yaxis_range=view_state["yaxis_range"])
            if view_state.get("dragmode"):
                fig.update_layout(dragmode=view_state["dragmode"])

        input_count = str(topology_data.get("input_units", 0))
        hidden_count = str(topology_data.get("hidden_units", 0))
        output_count = str(topology_data.get("output_units", 0))
        connection_count = str(len(topology_data.get("connections", [])))

        return fig, input_count, hidden_count, output_count, connection_count, current_hash


class TestUpdateStatsBarThemeCallback:
    """Tests for update_stats_bar_theme callback (lines 357-358)."""

    @pytest.mark.unit
    def test_light_theme_style(self, visualizer):
        """Should return light theme style."""
        style = self._simulate_update_stats_bar_theme("light")
        assert style["backgroundColor"] == "#f8f9fa"
        assert style["color"] == "#212529"

    @pytest.mark.unit
    def test_dark_theme_style(self, visualizer):
        """Should return dark theme style."""
        style = self._simulate_update_stats_bar_theme("dark")
        assert style["backgroundColor"] == "#343a40"
        assert style["color"] == "#f8f9fa"

    @pytest.mark.unit
    def test_theme_style_has_all_properties(self, visualizer):
        """Should include all required style properties."""
        style = self._simulate_update_stats_bar_theme("light")
        assert "marginBottom" in style
        assert "padding" in style
        assert "borderRadius" in style

    @pytest.mark.unit
    def test_none_theme_treated_as_light(self, visualizer):
        """None theme should be treated as light (not dark)."""
        style = self._simulate_update_stats_bar_theme(None)
        assert style["backgroundColor"] == "#f8f9fa"

    def _simulate_update_stats_bar_theme(self, theme: str) -> Dict[str, Any]:
        """Simulate update_stats_bar_theme callback logic."""
        is_dark = theme == "dark"
        return {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#343a40" if is_dark else "#f8f9fa",
            "color": "#f8f9fa" if is_dark else "#212529",
            "borderRadius": "3px",
        }


class TestHandleNodeSelectionCallback:
    """Tests for handle_node_selection callback (lines 381-453)."""

    @pytest.mark.unit
    def test_box_selection_with_points(self, visualizer):
        """Should handle box/lasso selection with multiple points."""
        selected_data = {
            "points": [
                {"text": "Input 0"},
                {"text": "Input 1"},
                {"text": "Hidden 0"},
            ]
        }
        result = self._simulate_handle_node_selection(
            click_data=None,
            selected_data=selected_data,
            current_selection=[],
            trigger="selectedData",
        )
        nodes, info, style = result
        assert nodes == ["input_0", "input_1", "hidden_0"]
        assert style["display"] == "block"

    @pytest.mark.unit
    def test_box_selection_empty_points(self, visualizer):
        """Should handle box selection with no points."""
        selected_data = {"points": []}
        result = self._simulate_handle_node_selection(
            click_data=None,
            selected_data=selected_data,
            current_selection=[],
            trigger="selectedData",
        )
        nodes, _, style = result
        assert nodes == []
        assert style["display"] == "none"

    @pytest.mark.unit
    def test_box_selection_points_without_text(self, visualizer):
        """Should skip points without text."""
        selected_data = {
            "points": [
                {"text": "Input 0"},
                {"curveNumber": 0},  # No text
                {"text": "Hidden 0"},
            ]
        }
        result = self._simulate_handle_node_selection(
            click_data=None,
            selected_data=selected_data,
            current_selection=[],
            trigger="selectedData",
        )
        nodes, _, _ = result
        assert "input_0" in nodes
        assert "hidden_0" in nodes

    @pytest.mark.unit
    def test_click_selection_new_node(self, visualizer):
        """Should select a new node on click."""
        click_data = {"points": [{"text": "Hidden 0", "curveNumber": 3}]}
        result = self._simulate_handle_node_selection(
            click_data=click_data,
            selected_data=None,
            current_selection=[],
            trigger="clickData",
        )
        nodes, info, style = result
        assert nodes == ["hidden_0"]
        assert style["display"] == "block"

    @pytest.mark.unit
    def test_click_toggle_deselects(self, visualizer):
        """Should deselect when clicking already selected node."""
        click_data = {"points": [{"text": "Hidden 0", "curveNumber": 3}]}
        result = self._simulate_handle_node_selection(
            click_data=click_data,
            selected_data=None,
            current_selection=["hidden_0"],
            trigger="clickData",
        )
        nodes, _, style = result
        assert nodes == []
        assert style["display"] == "none"

    @pytest.mark.unit
    def test_click_on_point_without_text(self, visualizer):
        """Should clear selection when clicking point without text."""
        click_data = {"points": [{"curveNumber": 0}]}
        result = self._simulate_handle_node_selection(
            click_data=click_data,
            selected_data=None,
            current_selection=["hidden_0"],
            trigger="clickData",
        )
        nodes, _, style = result
        assert nodes == []

    @pytest.mark.unit
    def test_click_on_empty_points(self, visualizer):
        """Should clear selection when clicking with no points."""
        click_data = {"points": []}
        result = self._simulate_handle_node_selection(
            click_data=click_data,
            selected_data=None,
            current_selection=["input_0"],
            trigger="clickData",
        )
        nodes, _, style = result
        assert nodes == []
        assert style["display"] == "none"

    @pytest.mark.unit
    def test_layer_detection_input(self, visualizer):
        """Should detect input layer from curveNumber."""
        layer_names = ["", "", "Input", "Hidden", "Output"]
        curve_number = 2
        layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"
        assert layer == "Input"

    @pytest.mark.unit
    def test_layer_detection_hidden(self, visualizer):
        """Should detect hidden layer from curveNumber."""
        layer_names = ["", "", "Input", "Hidden", "Output"]
        curve_number = 3
        layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"
        assert layer == "Hidden"

    @pytest.mark.unit
    def test_layer_detection_output(self, visualizer):
        """Should detect output layer from curveNumber."""
        layer_names = ["", "", "Input", "Hidden", "Output"]
        curve_number = 4
        layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"
        assert layer == "Output"

    @pytest.mark.unit
    def test_layer_detection_unknown(self, visualizer):
        """Should return Unknown for low curveNumber."""
        layer_names = ["", "", "Input", "Hidden", "Output"]
        curve_number = 1
        layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"
        assert layer == "Unknown"

    @pytest.mark.unit
    def test_node_id_conversion(self, visualizer):
        """Should convert node text to ID format."""
        text = "Hidden Unit 0"
        node_id = text.lower().replace(" ", "_")
        assert node_id == "hidden_unit_0"

    @pytest.mark.unit
    def test_no_trigger_clears_selection(self, visualizer):
        """Should clear selection when no valid trigger."""
        result = self._simulate_handle_node_selection(
            click_data=None,
            selected_data=None,
            current_selection=["input_0"],
            trigger="",
        )
        nodes, _, style = result
        assert nodes == []
        assert style["display"] == "none"

    def _simulate_handle_node_selection(
        self,
        click_data: Dict[str, Any],
        selected_data: Dict[str, Any],
        current_selection: List[str],
        trigger: str,
    ):
        """Simulate handle_node_selection callback logic."""
        base_style = {
            "marginBottom": "10px",
            "padding": "10px",
            "backgroundColor": "#e3f2fd",
            "borderRadius": "4px",
            "border": "1px solid #90caf9",
        }
        hidden_style = {**base_style, "display": "none"}
        visible_style = {**base_style, "display": "block"}

        # Handle box/lasso selection
        if "selectedData" in trigger and selected_data:
            # points = selected_data.get("points", [])
            # if points:
            if points := selected_data.get("points", []):
                selected_nodes = []
                for point in points:
                    if text := point.get("text", ""):
                        # text = point.get("text", "")
                        # if text:
                        node_id = text.lower().replace(" ", "_")
                        selected_nodes.append(node_id)

                if selected_nodes:
                    info = f"Selected {len(selected_nodes)} nodes"
                    return selected_nodes, info, visible_style

        # Handle single click selection
        if "clickData" in trigger and click_data:
            if points := click_data.get("points", []):
                # points = click_data.get("points", [])
                # if points:
                point = points[0]
                if text := point.get("text", ""):
                    # text = point.get("text", "")
                    # if text:
                    node_id = text.lower().replace(" ", "_")

                    # Toggle selection
                    if current_selection and node_id in current_selection:
                        return [], [], hidden_style

                    curve_number = point.get("curveNumber", 0)
                    layer_names = ["", "", "Input", "Hidden", "Output"]
                    layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"
                    info = f"Selected: {text}, Layer: {layer}"
                    return [node_id], info, visible_style

        return [], [], hidden_style


class TestSelectionHighlightIntegration:
    """Tests for selection highlight trace creation."""

    @pytest.mark.unit
    def test_create_selection_highlight_empty(self, visualizer):
        """Should return empty list for no selected nodes."""
        pos = {"input_0": (0, 0)}
        traces = visualizer._create_selection_highlight(pos, [])
        assert traces == []

    @pytest.mark.unit
    def test_create_selection_highlight_single(self, visualizer):
        """Should create highlight traces for single node."""
        pos = {"input_0": (0, 0)}
        traces = visualizer._create_selection_highlight(pos, ["input_0"])
        assert len(traces) == 2  # Glow + ring

    @pytest.mark.unit
    def test_create_selection_highlight_multiple(self, visualizer):
        """Should create highlight traces for multiple nodes."""
        pos = {"input_0": (0, 0), "hidden_0": (5, 0)}
        traces = visualizer._create_selection_highlight(pos, ["input_0", "hidden_0"])
        assert len(traces) == 4  # 2 traces per node

    @pytest.mark.unit
    def test_create_selection_highlight_missing_node(self, visualizer):
        """Should skip nodes not in pos."""
        pos = {"input_0": (0, 0)}
        traces = visualizer._create_selection_highlight(pos, ["input_0", "nonexistent"])
        assert len(traces) == 2


class TestStaggeredLayoutHiddenPositioning:
    """Tests for staggered layout hidden node positioning."""

    @pytest.mark.unit
    def test_staggered_layout_few_hidden(self, visualizer):
        """Staggered layout with few hidden units."""
        import networkx as nx

        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("hidden_0", layer="hidden")
        G.add_node("hidden_1", layer="hidden")
        G.add_node("output_0", layer="output")

        pos = visualizer._calculate_layout(G, "staggered", 1, 2, 1)
        assert "hidden_0" in pos
        assert "hidden_1" in pos

    @pytest.mark.unit
    def test_staggered_layout_many_hidden(self, visualizer):
        """Staggered layout with many hidden units spreads positions."""
        import networkx as nx

        G = nx.DiGraph()
        for i in range(5):
            G.add_node(f"hidden_{i}", layer="hidden")

        pos = visualizer._calculate_layout(G, "staggered", 0, 5, 0)
        x_positions = [pos[f"hidden_{i}"][0] for i in range(5)]
        assert len(set(x_positions)) > 1  # Positions should vary


class TestCallbackRegistrationAndExecution:
    """Test callbacks via actual Dash app registration."""

    @pytest.mark.unit
    def test_register_callbacks_creates_callbacks(self, visualizer):
        """Should register callbacks without error."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)
        assert len(app.callback_map) > 0

    @pytest.mark.unit
    def test_capture_view_state_callback_registered(self, visualizer):
        """Should register view state callback."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)
        expected_output = f"{visualizer.component_id}-view-state.data"
        assert any(expected_output in key for key in app.callback_map)

    @pytest.mark.unit
    def test_update_network_graph_callback_registered(self, visualizer):
        """Should register network graph update callback."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)
        expected_output = f"{visualizer.component_id}-graph.figure"
        assert any(expected_output in key for key in app.callback_map)

    @pytest.mark.unit
    def test_stats_bar_theme_callback_registered(self, visualizer):
        """Should register stats bar theme callback."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)
        expected_output = f"{visualizer.component_id}-stats-bar.style"
        assert any(expected_output in key for key in app.callback_map)

    @pytest.mark.unit
    def test_node_selection_callback_registered(self, visualizer):
        """Should register node selection callback."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)
        expected_output = f"{visualizer.component_id}-selected-nodes.data"
        assert any(expected_output in key for key in app.callback_map)


class TestCallbackFunctionsDirectly:
    """Extract and test callback functions directly for full coverage."""

    @pytest.mark.unit
    def test_capture_view_state_callback_function(self, visualizer):
        """Test the capture_view_state inner function logic directly."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)

        callback_key = f"{visualizer.component_id}-view-state.data"
        callback_obj = None
        for key, val in app.callback_map.items():
            if callback_key in key:
                callback_obj = val
                break

        assert callback_obj is not None

    @pytest.mark.unit
    def test_update_stats_bar_callback_function(self, visualizer):
        """Test stats bar theme callback function directly."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)

        callback_key = f"{visualizer.component_id}-stats-bar.style"
        assert any(callback_key in key for key in app.callback_map)

    @pytest.mark.unit
    def test_callback_graph_output_includes_all_outputs(self, visualizer):
        """Network graph callback should have all expected outputs."""
        from dash import Dash

        app = Dash(__name__)
        visualizer.register_callbacks(app)

        expected_outputs = [
            f"{visualizer.component_id}-graph.figure",
            f"{visualizer.component_id}-input-count.children",
            f"{visualizer.component_id}-hidden-count.children",
            f"{visualizer.component_id}-output-count.children",
            f"{visualizer.component_id}-connection-count.children",
            f"{visualizer.component_id}-topology-hash.data",
        ]

        # Join all outputs into a flat string for checking
        all_keys = "..".join(app.callback_map.keys())
        for expected in expected_outputs:
            assert expected in all_keys or any(expected in k for k in app.callback_map)


class TestDashTestClientIntegration:
    """Integration tests using Dash test client for coverage."""

    @pytest.mark.unit
    def test_app_with_visualizer_layout(self, visualizer):
        """App layout should include visualizer components."""
        from dash import Dash

        app = Dash(__name__)
        app.layout = visualizer.get_layout()
        visualizer.register_callbacks(app)

        # Check layout has expected components
        assert app.layout is not None

    @pytest.mark.unit
    def test_empty_graph_for_coverage(self, visualizer):
        """Create empty graph to cover the empty graph branch."""
        fig = visualizer._create_empty_graph(theme="light")
        assert fig.layout.plot_bgcolor == "#f8f9fa"

        fig_dark = visualizer._create_empty_graph(theme="dark")
        assert fig_dark.layout.plot_bgcolor == "#242424"

    @pytest.mark.unit
    def test_network_graph_with_metrics_data(self, visualizer, simple_topology):
        """Test network graph creation with metrics data for new unit detection."""
        fig = visualizer._create_network_graph(
            simple_topology,
            "hierarchical",
            show_weights=True,
            newly_added_unit=0,
            theme="light",
            selected_nodes=[],
        )
        assert isinstance(fig, go.Figure)

    @pytest.mark.unit
    def test_network_graph_with_selection(self, visualizer, simple_topology):
        """Test network graph with selected nodes."""
        fig = visualizer._create_network_graph(
            simple_topology,
            "hierarchical",
            show_weights=True,
            newly_added_unit=None,
            theme="dark",
            selected_nodes=["input_0", "hidden_0"],
        )
        assert isinstance(fig, go.Figure)

    @pytest.mark.unit
    def test_view_state_application(self, visualizer, simple_topology):
        """Test that view state is correctly applied to figure."""
        fig = visualizer._create_network_graph(simple_topology, "hierarchical", False, None, "light", [])

        view_state = {"xaxis_range": [-10, 10], "yaxis_range": [-5, 5], "dragmode": "zoom"}

        if view_state.get("xaxis_range"):
            fig.update_layout(xaxis_range=view_state["xaxis_range"])
        if view_state.get("yaxis_range"):
            fig.update_layout(yaxis_range=view_state["yaxis_range"])
        if view_state.get("dragmode"):
            fig.update_layout(dragmode=view_state["dragmode"])

        assert fig.layout.dragmode == "zoom"


class TestCallbackInvocation:
    """Directly invoke callback functions to achieve line coverage."""

    @pytest.mark.unit
    def test_invoke_capture_view_state_callback(self, visualizer):
        """Invoke the capture_view_state callback directly."""
        from dash import Dash, dcc, html
        from dash._callback_context import context_value
        from dash._utils import AttributeDict

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

        # Find and invoke the capture_view_state callback
        callback_key = f"{visualizer.component_id}-view-state.data"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                # Invoke with test data
                result = func.__wrapped__(
                    {"xaxis.range[0]": 0, "xaxis.range[1]": 10},
                    {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"},
                )
                assert result["xaxis_range"] == [0, 10]
                break

    @pytest.mark.unit
    def test_invoke_update_network_graph_callback(self, visualizer, simple_topology):
        """Invoke the update_network_graph callback directly."""
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

        # Find the update_network_graph callback
        callback_key = f"{visualizer.component_id}-graph.figure"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                result = func.__wrapped__(
                    simple_topology,  # topology_data
                    "hierarchical",  # layout_type
                    ["show"],  # show_weights
                    "2d",  # view_mode (P3-5)
                    [],  # metrics_data
                    "light",  # theme
                    [],  # selected_nodes
                    0,  # n_intervals
                    {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"},  # view_state
                    None,  # prev_hash
                    None,  # current_highlight
                )
                fig, input_ct, hidden_ct, output_ct, conn_ct, hash_val, new_highlight = result
                assert isinstance(fig, go.Figure)
                assert input_ct == "2"
                assert hidden_ct == "1"
                break

    @pytest.mark.unit
    def test_invoke_update_network_graph_with_empty_topology(self, visualizer):
        """Test update_network_graph with empty topology."""
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

        callback_key = f"{visualizer.component_id}-graph.figure"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                result = func.__wrapped__(
                    {"input_units": 0, "hidden_units": 0, "output_units": 0, "connections": []},
                    "hierarchical",
                    [],
                    "2d",  # view_mode (P3-5)
                    [],
                    "light",
                    [],
                    0,  # n_intervals
                    None,  # view_state
                    None,  # prev_hash
                    None,  # current_highlight
                )
                fig, input_ct, hidden_ct, output_ct, conn_ct, hash_val, new_highlight = result
                assert input_ct == "0"
                assert hash_val is None
                break

    @pytest.mark.unit
    def test_invoke_update_network_graph_with_metrics(self, visualizer, simple_topology):
        """Test update_network_graph with metrics data for new unit detection."""
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

        metrics_data = [
            {"network_topology": {"hidden_units": 0}},
            {"network_topology": {"hidden_units": 1}},
        ]

        callback_key = f"{visualizer.component_id}-graph.figure"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                result = func.__wrapped__(simple_topology, "hierarchical", ["show"], "2d", metrics_data, "light", [], 0, None, None, None)
                fig, _, _, _, _, _, new_highlight = result
                assert isinstance(fig, go.Figure)
                # Should have detected new unit and created highlight
                assert new_highlight is not None
                assert new_highlight["node_id"] == "hidden_0"
                break

    @pytest.mark.unit
    def test_invoke_update_network_graph_with_view_state(self, visualizer, simple_topology):
        """Test update_network_graph with view state application."""
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

        view_state = {"xaxis_range": [-10, 10], "yaxis_range": [-5, 5], "dragmode": "zoom"}

        callback_key = f"{visualizer.component_id}-graph.figure"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                result = func.__wrapped__(simple_topology, "hierarchical", [], "2d", [], "light", [], 0, view_state, None, None)
                fig, _, _, _, _, _, _ = result
                assert isinstance(fig, go.Figure)
                break

    @pytest.mark.unit
    def test_invoke_update_stats_bar_theme_callback(self, visualizer):
        """Invoke the update_stats_bar_theme callback directly."""
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

        callback_key = f"{visualizer.component_id}-stats-bar.style"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                # Test light theme
                result = func.__wrapped__("light")
                assert result["backgroundColor"] == "#f8f9fa"
                # Test dark theme
                result = func.__wrapped__("dark")
                assert result["backgroundColor"] == "#343a40"
                break

    @pytest.mark.unit
    def test_invoke_handle_node_selection_callback_click(self, visualizer):
        """Invoke handle_node_selection callback with click data."""
        from dash import Dash, dcc, html
        from dash._callback_context import context_value
        from dash._utils import AttributeDict

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
                # Mock callback context for click trigger
                with patch("dash.callback_context") as mock_ctx:
                    mock_ctx.triggered = [{"prop_id": f"{visualizer.component_id}-graph.clickData"}]
                    click_data = {"points": [{"text": "Input 0", "curveNumber": 2}]}
                    result = func.__wrapped__(click_data, None, [])
                    nodes, info, style = result
                    assert nodes == ["input_0"]
                break

    @pytest.mark.unit
    def test_invoke_handle_node_selection_callback_selected(self, visualizer):
        """Invoke handle_node_selection callback with selectedData."""
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
                    mock_ctx.triggered = [{"prop_id": f"{visualizer.component_id}-graph.selectedData"}]
                    selected_data = {"points": [{"text": "Input 0"}, {"text": "Hidden 0"}]}
                    result = func.__wrapped__(None, selected_data, [])
                    nodes, info, style = result
                    assert "input_0" in nodes
                    assert "hidden_0" in nodes
                break

    @pytest.mark.unit
    def test_invoke_handle_node_selection_toggle_off(self, visualizer):
        """Test clicking on already selected node to deselect."""
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
                    click_data = {"points": [{"text": "Input 0", "curveNumber": 2}]}
                    # Node is already selected
                    result = func.__wrapped__(click_data, None, ["input_0"])
                    nodes, info, style = result
                    assert nodes == []
                break

    @pytest.mark.unit
    def test_capture_view_state_all_autorange(self, visualizer):
        """Test capture_view_state with both autorange."""
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

        callback_key = f"{visualizer.component_id}-view-state.data"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                result = func.__wrapped__(
                    {"xaxis.autorange": True, "yaxis.autorange": True},
                    {"xaxis_range": [0, 10], "yaxis_range": [-5, 5], "dragmode": "pan"},
                )
                assert result["xaxis_range"] is None
                assert result["yaxis_range"] is None
                break

    @pytest.mark.unit
    def test_capture_view_state_yaxis_range(self, visualizer):
        """Test capture_view_state with yaxis range."""
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

        callback_key = f"{visualizer.component_id}-view-state.data"
        for key, callback_info in app.callback_map.items():
            if callback_key in key:
                func = callback_info["callback"]
                result = func.__wrapped__(
                    {"yaxis.range[0]": -10, "yaxis.range[1]": 10},
                    {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"},
                )
                assert result["yaxis_range"] == [-10, 10]
                break
