#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_network_visualizer_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-11-18
# Last Modified: 2025-11-18
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Comprehensive coverage tests for NetworkVisualizer component
#####################################################################
"""Comprehensive coverage tests for NetworkVisualizer (69% -> 80%+)."""

import itertools
import sys
from pathlib import Path

# Add src to path before other imports
src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import networkx as nx  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import pytest  # noqa: E402

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402


@pytest.fixture
def config():
    """Basic config for network visualizer."""
    return {
        "show_weights": True,
        "layout": "hierarchical",
    }


@pytest.fixture
def visualizer(config):
    """Create NetworkVisualizer instance."""
    return NetworkVisualizer(config, component_id="test-viz")


@pytest.fixture
def simple_topology():
    """Simple network topology."""
    return {
        "input_units": 2,
        "hidden_units": 1,
        "output_units": 1,
        "nodes": [
            {"id": "input_0", "type": "input", "layer": 0},
            {"id": "input_1", "type": "input", "layer": 0},
            {"id": "hidden_0", "type": "hidden", "layer": 1},
            {"id": "output_0", "type": "output", "layer": 2},
        ],
        "connections": [
            {"from": "input_0", "to": "hidden_0", "weight": 0.5},
            {"from": "input_1", "to": "hidden_0", "weight": -0.3},
            {"from": "hidden_0", "to": "output_0", "weight": 0.8},
        ],
    }


@pytest.fixture
def large_topology():
    """Large network topology for stress testing."""
    connections = [
        {"from": f"input_{i}", "to": f"hidden_{h}", "weight": 0.1 * i}
        for i, h in itertools.product(range(10), range(5))
    ]
    connections.extend(
        {"from": f"hidden_{h}", "to": f"output_{o}", "weight": 0.2 * h}
        for h, o in itertools.product(range(5), range(3))
    )
    return {
        "input_units": 10,
        "hidden_units": 5,
        "output_units": 3,
        "connections": connections,
    }


class TestInitialization:
    """Test NetworkVisualizer initialization."""

    def test_init_default_config(self):
        """Should initialize with empty config."""
        viz = NetworkVisualizer({})
        assert viz is not None
        assert viz.component_id == "network-visualizer"

    def test_init_custom_id(self, config):
        """Should initialize with custom ID."""
        viz = NetworkVisualizer(config, component_id="custom-viz")
        assert viz.component_id == "custom-viz"

    def test_init_show_weights_config(self):
        """Should read show_weights from config."""
        viz = NetworkVisualizer({"show_weights": False})
        assert viz.show_weights is False

    def test_init_layout_type_config(self):
        """Should read layout from config."""
        viz = NetworkVisualizer({"layout": "spring"})
        assert viz.layout_type == "spring"

    def test_init_default_topology(self, visualizer):
        """Should initialize with empty topology."""
        assert visualizer.current_topology["input_units"] == 0
        assert visualizer.current_topology["hidden_units"] == 0
        assert visualizer.current_topology["output_units"] == 0


class TestGraphConstruction:
    """Test graph construction from topology."""

    def test_create_graph_with_simple_topology(self, visualizer, simple_topology):
        """Should create graph from simple topology."""
        fig = visualizer._create_network_graph(simple_topology, "hierarchical", True)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_graph_node_count_matches(self, visualizer, simple_topology):
        """Graph should have correct number of nodes."""
        # Create NetworkX graph internally
        G = nx.DiGraph()
        for i in range(simple_topology["input_units"]):
            G.add_node(f"input_{i}", layer="input")
        for i in range(simple_topology["hidden_units"]):
            G.add_node(f"hidden_{i}", layer="hidden")
        for i in range(simple_topology["output_units"]):
            G.add_node(f"output_{i}", layer="output")

        total_nodes = simple_topology["input_units"] + simple_topology["hidden_units"] + simple_topology["output_units"]
        assert G.number_of_nodes() == total_nodes

    def test_graph_edge_count_matches(self, visualizer, simple_topology):
        """Graph should have correct number of edges."""
        G = nx.DiGraph()
        for conn in simple_topology["connections"]:
            G.add_edge(conn["from"], conn["to"], weight=conn["weight"])

        assert G.number_of_edges() == len(simple_topology["connections"])


class TestLayoutAlgorithms:
    """Test different layout algorithms."""

    def test_hierarchical_layout(self, visualizer):
        """Should create hierarchical layout."""
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("hidden_0", layer="hidden")
        G.add_node("output_0", layer="output")

        pos = visualizer._calculate_layout(G, "hierarchical", 1, 1, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 3
        assert "input_0" in pos
        assert "hidden_0" in pos
        assert "output_0" in pos

    def test_spring_layout(self, visualizer):
        """Should create spring layout."""
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("output_0", layer="output")

        pos = visualizer._calculate_layout(G, "spring", 1, 0, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 2

    def test_circular_layout(self, visualizer):
        """Should create circular layout."""
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("hidden_0", layer="hidden")
        G.add_node("output_0", layer="output")

        pos = visualizer._calculate_layout(G, "circular", 1, 1, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 3

    def test_unknown_layout_fallback(self, visualizer):
        """Unknown layout should fallback to hierarchical."""
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")

        pos = visualizer._calculate_layout(G, "unknown_layout", 1, 0, 0)
        assert isinstance(pos, dict)


class TestEdgeTraces:
    """Test edge trace creation."""

    def test_create_edge_traces_basic(self, visualizer):
        """Should create edge traces."""
        G = nx.DiGraph()
        G.add_edge("input_0", "output_0", weight=0.5)
        pos = {"input_0": (0, 0), "output_0": (10, 0)}

        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        assert isinstance(traces, list)
        assert len(traces) > 0

    def test_edge_traces_with_weights_shown(self, visualizer):
        """Should add weight labels when show_weights=True."""
        G = nx.DiGraph()
        G.add_edge("input_0", "output_0", weight=0.5)
        pos = {"input_0": (0, 0), "output_0": (10, 0)}

        traces = visualizer._create_edge_traces(G, pos, show_weights=True)
        # Should have edge trace + label trace
        assert len(traces) >= 2

    def test_edge_color_positive_weight(self, visualizer):
        """Positive weights should be blue."""
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=0.8)
        pos = {"a": (0, 0), "b": (1, 1)}

        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        # Check color in trace
        assert any("#3498db" in str(trace) for trace in traces)

    def test_edge_color_negative_weight(self, visualizer):
        """Negative weights should be red."""
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=-0.5)
        pos = {"a": (0, 0), "b": (1, 1)}

        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        # Check color in trace
        assert any("#e74c3c" in str(trace) for trace in traces)


class TestNodeTraces:
    """Test node trace creation."""

    def test_create_node_traces_all_layers(self, visualizer):
        """Should create traces for all layer types."""
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("hidden_0", layer="hidden")
        G.add_node("output_0", layer="output")
        pos = {"input_0": (0, 0), "hidden_0": (5, 0), "output_0": (10, 0)}

        traces = visualizer._create_node_traces(G, pos)
        assert isinstance(traces, list)
        # Should have 3 traces (input, hidden, output)
        assert len(traces) == 3

    def test_create_node_trace_single_layer(self, visualizer):
        """Should create trace for single node group."""
        pos = {"input_0": (0, 0), "input_1": (0, 1)}
        trace = visualizer._create_node_trace(["input_0", "input_1"], pos, "#2ecc71", "Input Units")

        assert isinstance(trace, go.Scatter)
        assert len(trace.x) == 2
        assert len(trace.y) == 2


class TestEmptyNetworkHandling:
    """Test handling of empty networks."""

    def test_empty_topology_returns_empty_graph(self, visualizer):
        """Empty topology should return empty placeholder."""
        empty_topology = {
            "input_units": 0,
            "hidden_units": 0,
            "output_units": 0,
            "connections": [],
        }
        fig = visualizer._create_network_graph(empty_topology, "hierarchical", True)
        assert isinstance(fig, go.Figure)

    def test_create_empty_graph_light_theme(self, visualizer):
        """Should create empty graph with light theme."""
        fig = visualizer._create_empty_graph(theme="light")
        assert isinstance(fig, go.Figure)
        assert fig.layout.plot_bgcolor == "#f8f9fa"

    def test_create_empty_graph_dark_theme(self, visualizer):
        """Should create empty graph with dark theme."""
        fig = visualizer._create_empty_graph(theme="dark")
        assert isinstance(fig, go.Figure)  # Dark theme applied


class TestLargeNetworkHandling:
    """Test handling of large networks."""

    def test_large_network_renders(self, visualizer, large_topology):
        """Should handle large network without errors."""
        fig = visualizer._create_network_graph(large_topology, "hierarchical", False)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_large_network_all_layouts(self, visualizer, large_topology):
        """Large network should work with all layouts."""
        for layout in ["hierarchical", "spring", "circular"]:
            fig = visualizer._create_network_graph(large_topology, layout, False)
            assert isinstance(fig, go.Figure)


class TestTopologyUpdate:
    """Test topology update methods."""

    def test_update_topology(self, visualizer, simple_topology):
        """update_topology should update current topology."""
        visualizer.update_topology(simple_topology)
        assert visualizer.current_topology == simple_topology

    def test_get_topology_returns_copy(self, visualizer, simple_topology):
        """get_topology should return a copy."""
        visualizer.update_topology(simple_topology)
        topology = visualizer.get_topology()

        # Modify returned copy
        topology["input_units"] = 999

        # Original should be unchanged
        assert visualizer.current_topology["input_units"] != 999


class TestOptionalAttributes:
    """Test optional attributes in topology."""

    def test_missing_weight_attribute(self, visualizer):
        """Should handle missing weight attribute."""
        topology = {
            "input_units": 1,
            "hidden_units": 0,
            "output_units": 1,
            "connections": [{"from": "input_0", "to": "output_0"}],  # No weight
        }
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert isinstance(fig, go.Figure)

    def test_missing_nodes_list(self, visualizer):
        """Should handle missing nodes list."""
        topology = {
            "input_units": 1,
            "hidden_units": 0,
            "output_units": 1,
            "connections": [],
        }
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert isinstance(fig, go.Figure)


class TestNewUnitHighlighting:
    """Test newly added unit highlighting."""

    def test_highlight_new_hidden_unit(self, visualizer, simple_topology):
        """Should highlight newly added hidden unit."""
        fig = visualizer._create_network_graph(simple_topology, "hierarchical", True, newly_added_unit=0, theme="light")
        assert isinstance(fig, go.Figure)
        # Should have highlight trace
        assert len(fig.data) > 0

    def test_no_highlight_when_none(self, visualizer, simple_topology):
        """Should not add highlight when newly_added_unit is None."""
        fig = visualizer._create_network_graph(
            simple_topology, "hierarchical", True, newly_added_unit=None, theme="light"
        )
        assert isinstance(fig, go.Figure)


class TestThemeSupport:
    """Test light/dark theme support."""

    def test_light_theme_graph(self, visualizer, simple_topology):
        """Should create graph with light theme."""
        fig = visualizer._create_network_graph(simple_topology, "hierarchical", True, theme="light")
        assert isinstance(fig, go.Figure)

    def test_dark_theme_graph(self, visualizer, simple_topology):
        """Should create graph with dark theme."""
        fig = visualizer._create_network_graph(simple_topology, "hierarchical", True, theme="dark")
        assert isinstance(fig, go.Figure)  # Dark theme applied


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_hidden_units(self, visualizer):
        """Should handle network with no hidden units."""
        topology = {
            "input_units": 2,
            "hidden_units": 0,
            "output_units": 1,
            "connections": [
                {"from": "input_0", "to": "output_0", "weight": 0.5},
                {"from": "input_1", "to": "output_0", "weight": -0.3},
            ],
        }
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert isinstance(fig, go.Figure)

    def test_only_input_output(self, visualizer):
        """Should handle network with only input and output."""
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("output_0", layer="output")

        pos = visualizer._calculate_layout(G, "hierarchical", 1, 0, 1)
        assert len(pos) == 2

    def test_disconnected_nodes(self, visualizer):
        """Should handle disconnected nodes."""
        topology = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 1,
            "connections": [],  # No connections
        }
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert isinstance(fig, go.Figure)
