#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_network_visualizer_layout_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-12-13
# Last Modified: 2025-12-13
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for NetworkVisualizer layout calculation methods
#                to improve coverage from 59% to 80%+
#####################################################################
"""Unit tests for NetworkVisualizer layout calculation methods."""


import itertools
import sys
from pathlib import Path

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import networkx as nx
import plotly.graph_objects as go
import pytest

from frontend.components.network_visualizer import NetworkVisualizer


@pytest.fixture
def visualizer():
    """Create NetworkVisualizer instance with default config."""
    return NetworkVisualizer({"show_weights": True, "layout": "hierarchical"})


def build_test_graph(n_input: int, n_hidden: int, n_output: int) -> nx.DiGraph:
    """Build a test graph with specified node counts."""
    G = nx.DiGraph()
    for i in range(n_input):
        G.add_node(f"input_{i}", layer="input", index=i)
    for i in range(n_hidden):
        G.add_node(f"hidden_{i}", layer="hidden", index=i)
    for i in range(n_output):
        G.add_node(f"output_{i}", layer="output", index=i)
    return G


def add_full_connections(G: nx.DiGraph, n_input: int, n_hidden: int, n_output: int):
    """Add edges between all layers with varied weights."""
    if n_hidden > 0:
        for i, h in itertools.product(range(n_input), range(n_hidden)):
            weight = 0.5 if (i + h) % 2 == 0 else -0.3
            G.add_edge(f"input_{i}", f"hidden_{h}", weight=weight)
        for h, o in itertools.product(range(n_hidden), range(n_output)):
            weight = 0.8 if h % 2 == 0 else -0.6
            G.add_edge(f"hidden_{h}", f"output_{o}", weight=weight)
    else:
        for i, o in itertools.product(range(n_input), range(n_output)):
            G.add_edge(f"input_{i}", f"output_{o}", weight=0.5)


class TestCalculateLayoutBranches:
    """Test _calculate_layout method branches."""

    def test_layout_circular_delegates(self, visualizer):
        """layout_type == 'circular' should delegate to _layout_type_circular."""
        G = build_test_graph(2, 1, 1)
        pos = visualizer._calculate_layout(G, "circular", 2, 1, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 4
        for node in ["input_0", "input_1", "hidden_0", "output_0"]:
            assert node in pos
            coords = pos[node]
            assert len(coords) == 2
            assert isinstance(float(coords[0]), float)
            assert isinstance(float(coords[1]), float)

    def test_layout_hierarchical_delegates(self, visualizer):
        """layout_type == 'hierarchical' should use _layout_type_hierarchical."""
        G = build_test_graph(2, 1, 1)
        pos = visualizer._calculate_layout(G, "hierarchical", 2, 1, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 4
        assert pos["input_0"][0] == 0
        assert pos["output_0"][0] == 10

    def test_layout_spring_delegates(self, visualizer):
        """layout_type == 'spring' should use _layout_type_sprint."""
        G = build_test_graph(2, 1, 1)
        pos = visualizer._calculate_layout(G, "spring", 2, 1, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 4
        for node in G.nodes():
            assert node in pos
            x, y = pos[node]
            assert isinstance(x, float)
            assert isinstance(y, float)

    def test_layout_staggered_delegates(self, visualizer):
        """layout_type == 'staggered' should use _layout_type_staggered."""
        G = build_test_graph(2, 2, 1)
        pos = visualizer._calculate_layout(G, "staggered", 2, 2, 1)
        assert isinstance(pos, dict)
        assert len(pos) == 5
        assert pos["input_0"][0] == 0
        assert pos["output_0"][0] == 10

    def test_layout_unknown_fallback_to_hierarchical(self, visualizer):
        """Unknown layout_type should fall back to hierarchical."""
        G = build_test_graph(1, 0, 1)
        pos = visualizer._calculate_layout(G, "nonexistent_layout", 1, 0, 1)
        assert isinstance(pos, dict)
        assert "input_0" in pos
        assert "output_0" in pos
        assert pos["input_0"][0] == 0
        assert pos["output_0"][0] == 10


class TestLayoutTypeCircular:
    """Test _layout_type_circular method."""

    def test_circular_layout_positions(self, visualizer):
        """All nodes should have (x, y) positions on a circle."""
        G = build_test_graph(3, 2, 1)
        pos = visualizer._layout_type_circular(G, scale=1.0)
        assert len(pos) == 6
        for node, coords in pos.items():
            assert hasattr(coords, "__iter__")
            x, y = coords
            assert isinstance(float(x), float)
            assert isinstance(float(y), float)

    def test_circular_layout_with_scale(self, visualizer):
        """Circular layout should respect scale parameter."""
        G = build_test_graph(2, 0, 2)
        pos_default = visualizer._layout_type_circular(G, scale=1.0)
        pos_scaled = visualizer._layout_type_circular(G, scale=5.0)
        for node in G.nodes():
            x_def, y_def = pos_default[node]
            x_scl, y_scl = pos_scaled[node]
            assert abs(x_scl) >= abs(x_def) or abs(y_scl) >= abs(y_def)

    def test_circular_layout_empty_graph(self, visualizer):
        """Circular layout with empty graph should return empty dict."""
        G = nx.DiGraph()
        pos = visualizer._layout_type_circular(G, scale=1.0)
        assert pos == {}


class TestLayoutTypeSprint:
    """Test _layout_type_sprint method (spring layout)."""

    def test_spring_layout_positions(self, visualizer):
        """All nodes should have (x, y) positions after spring layout."""
        G = build_test_graph(2, 2, 1)
        add_full_connections(G, 2, 2, 1)
        pos = visualizer._layout_type_sprint(G, k=2, iterations=50, seed=42)
        assert len(pos) == 5
        for node, coords in pos.items():
            x, y = coords
            assert isinstance(x, float)
            assert isinstance(y, float)

    def test_spring_layout_scaled(self, visualizer):
        """Spring layout should scale positions by 10."""
        G = build_test_graph(2, 0, 1)
        pos = visualizer._layout_type_sprint(G, k=2, iterations=50, seed=42)
        for node, (x, y) in pos.items():
            assert abs(x) <= 15 or abs(y) <= 15

    def test_spring_layout_deterministic(self, visualizer):
        """Spring layout should be deterministic with same seed."""
        G = build_test_graph(2, 1, 1)
        pos1 = visualizer._layout_type_sprint(G, k=2, iterations=50, seed=42)
        pos2 = visualizer._layout_type_sprint(G, k=2, iterations=50, seed=42)
        for node in G.nodes():
            assert pos1[node][0] == pytest.approx(pos2[node][0], abs=0.01)
            assert pos1[node][1] == pytest.approx(pos2[node][1], abs=0.01)


class TestLayoutTypeHierarchical:
    """Test _layout_type_hierarchical method."""

    def test_hierarchical_no_hidden(self, visualizer):
        """Hierarchical layout with n_hidden=0."""
        G = build_test_graph(2, 0, 1)
        pos = visualizer._layout_type_hierarchical(G, n_input=2, n_hidden=0, n_output=1)
        assert "input_0" in pos
        assert "input_1" in pos
        assert "output_0" in pos
        assert pos["input_0"][0] == 0
        assert pos["output_0"][0] == 10

    def test_hierarchical_one_hidden(self, visualizer):
        """Hierarchical layout with n_hidden=1."""
        G = build_test_graph(2, 1, 1)
        pos = visualizer._layout_type_hierarchical(G, n_input=2, n_hidden=1, n_output=1)
        assert "hidden_0" in pos
        x_hidden = pos["hidden_0"][0]
        assert 0 < x_hidden < 10

    def test_hierarchical_multiple_hidden(self, visualizer):
        """Hierarchical layout with n_hidden>2."""
        G = build_test_graph(3, 5, 2)
        pos = visualizer._layout_type_hierarchical(G, n_input=3, n_hidden=5, n_output=2)
        for i in range(5):
            assert f"hidden_{i}" in pos
            x, y = pos[f"hidden_{i}"]
            assert 0 < x < 10

    def test_hierarchical_node_keys_correct(self, visualizer):
        """Hierarchical layout should create correct node keys."""
        G = build_test_graph(2, 3, 2)
        pos = visualizer._layout_type_hierarchical(G, n_input=2, n_hidden=3, n_output=2)
        expected_keys = {"input_0", "input_1", "hidden_0", "hidden_1", "hidden_2", "output_0", "output_1"}
        assert set(pos.keys()) == expected_keys


class TestLayoutTypeStaggered:
    """Test _layout_type_staggered method."""

    def test_staggered_no_hidden(self, visualizer):
        """Staggered layout with n_hidden=0."""
        G = build_test_graph(2, 0, 1)
        pos = visualizer._layout_type_staggered(G, n_input=2, n_hidden=0, n_output=1)
        assert "input_0" in pos
        assert "output_0" in pos
        assert pos["input_0"][0] == 0
        assert pos["output_0"][0] == 10

    def test_staggered_one_hidden(self, visualizer):
        """Staggered layout with n_hidden=1 should center hidden node."""
        G = build_test_graph(2, 1, 1)
        pos = visualizer._layout_type_staggered(G, n_input=2, n_hidden=1, n_output=1)
        assert "hidden_0" in pos
        x_hidden = pos["hidden_0"][0]
        assert x_hidden == pytest.approx(5.0, abs=0.1)

    def test_staggered_multiple_hidden_zigzag(self, visualizer):
        """Staggered layout with n_hidden>2 should have zigzag pattern."""
        G = build_test_graph(2, 4, 1)
        pos = visualizer._layout_type_staggered(G, n_input=2, n_hidden=4, n_output=4)
        x_positions = [pos[f"hidden_{i}"][0] for i in range(4)]
        assert any(x != x_positions[0] for x in x_positions)
        for i in range(4):
            assert 0 < x_positions[i] < 10

    def test_staggered_node_keys(self, visualizer):
        """Staggered layout should have correct node keys."""
        G = build_test_graph(3, 2, 2)
        pos = visualizer._layout_type_staggered(G, n_input=3, n_hidden=2, n_output=2)
        expected = {"input_0", "input_1", "input_2", "hidden_0", "hidden_1", "output_0", "output_1"}
        assert set(pos.keys()) == expected


class TestCalculateHiddenNodePositionOffsets:
    """Test _calculate_hidden_node_position_offsets method."""

    def test_hidden_offsets_single_node(self, visualizer):
        """Single hidden node should get alternating offset."""
        pos = {}
        visualizer._calculate_hidden_node_position_offsets(1, pos)
        assert "hidden_0" in pos
        x, y = pos["hidden_0"]
        assert 4 < x < 6

    def test_hidden_offsets_two_nodes(self, visualizer):
        """Two hidden nodes should have stagger offset."""
        pos = {}
        visualizer._calculate_hidden_node_position_offsets(2, pos)
        assert "hidden_0" in pos
        assert "hidden_1" in pos
        x0 = pos["hidden_0"][0]
        x1 = pos["hidden_1"][0]
        assert x0 != x1

    def test_hidden_offsets_many_nodes_wave_pattern(self, visualizer):
        """n_hidden > 2 should use wave pattern with first at center."""
        pos = {}
        visualizer._calculate_hidden_node_position_offsets(5, pos)
        for i in range(5):
            assert f"hidden_{i}" in pos
        x0 = pos["hidden_0"][0]
        assert x0 == pytest.approx(5.0, abs=0.1)
        x_values = [pos[f"hidden_{i}"][0] for i in range(5)]
        assert len(set(x_values)) > 1

    def test_hidden_offsets_y_spacing(self, visualizer):
        """Hidden nodes should have correct y-spacing."""
        pos = {}
        visualizer._calculate_hidden_node_position_offsets(4, pos)
        y_values = [pos[f"hidden_{i}"][1] for i in range(4)]
        for i in range(3):
            delta = y_values[i + 1] - y_values[i]
            assert delta == pytest.approx(1.5, abs=0.01)


class TestCreateEdgeTraces:
    """Test _create_edge_traces method."""

    def test_edge_traces_basic(self, visualizer):
        """Should create edge traces for graph with edges."""
        G = nx.DiGraph()
        G.add_edge("input_0", "output_0", weight=0.5)
        pos = {"input_0": (0, 0), "output_0": (10, 0)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        assert len(traces) >= 1
        assert all(isinstance(t, go.Scatter) for t in traces)

    def test_edge_traces_show_weights_true(self, visualizer):
        """show_weights=True should add label traces."""
        G = nx.DiGraph()
        G.add_edge("input_0", "output_0", weight=0.75)
        pos = {"input_0": (0, 0), "output_0": (10, 0)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=True)
        assert len(traces) >= 2
        label_found = any(t.mode == "text" for t in traces)
        assert label_found

    def test_edge_traces_show_weights_false(self, visualizer):
        """show_weights=False should not add label traces."""
        G = nx.DiGraph()
        G.add_edge("input_0", "output_0", weight=0.75)
        pos = {"input_0": (0, 0), "output_0": (10, 0)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        label_traces = [t for t in traces if t.mode == "text"]
        assert not label_traces

    def test_edge_traces_positive_weight_color(self, visualizer):
        """Positive weight edges should be blue (#3498db)."""
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=0.9)
        pos = {"a": (0, 0), "b": (5, 5)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        line_trace = [t for t in traces if t.mode == "lines"][0]
        assert line_trace.line.color == "#3498db"

    def test_edge_traces_negative_weight_color(self, visualizer):
        """Negative weight edges should be red (#e74c3c)."""
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=-0.7)
        pos = {"a": (0, 0), "b": (5, 5)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        line_trace = [t for t in traces if t.mode == "lines"][0]
        assert line_trace.line.color == "#e74c3c"

    def test_edge_traces_mixed_weights(self, visualizer):
        """Mixed positive/negative weights should have correct colors."""
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=0.5)
        G.add_edge("b", "c", weight=-0.3)
        pos = {"a": (0, 0), "b": (5, 0), "c": (10, 0)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        line_traces = [t for t in traces if t.mode == "lines"]
        colors = [t.line.color for t in line_traces]
        assert "#3498db" in colors
        assert "#e74c3c" in colors

    def test_edge_traces_zero_weight(self, visualizer):
        """Zero weight edges should be blue (non-negative)."""
        G = nx.DiGraph()
        G.add_edge("a", "b", weight=0.0)
        pos = {"a": (0, 0), "b": (5, 5)}
        traces = visualizer._create_edge_traces(G, pos, show_weights=False)
        line_trace = [t for t in traces if t.mode == "lines"][0]
        assert line_trace.line.color == "#3498db"


class TestCreateNodeTraces:
    """Test _create_node_traces method."""

    def test_node_traces_all_layers(self, visualizer):
        """Should create traces for input, hidden, and output layers."""
        G = build_test_graph(2, 2, 1)
        pos = {
            "input_0": (0, 0),
            "input_1": (0, 1),
            "hidden_0": (5, 0),
            "hidden_1": (5, 1),
            "output_0": (10, 0),
        }
        traces = visualizer._create_node_traces(G, pos)
        assert len(traces) == 3
        trace_names = [t.name for t in traces]
        assert "Input Units" in trace_names
        assert "Hidden Units" in trace_names
        assert "Output Units" in trace_names

    def test_node_traces_only_input_output(self, visualizer):
        """Should create traces for input and output only when no hidden."""
        G = build_test_graph(2, 0, 1)
        pos = {"input_0": (0, 0), "input_1": (0, 1), "output_0": (10, 0)}
        traces = visualizer._create_node_traces(G, pos)
        assert len(traces) == 2
        trace_names = [t.name for t in traces]
        assert "Input Units" in trace_names
        assert "Output Units" in trace_names

    def test_node_traces_layer_colors(self, visualizer):
        """Verify correct colors for each layer."""
        G = build_test_graph(1, 1, 1)
        pos = {"input_0": (0, 0), "hidden_0": (5, 0), "output_0": (10, 0)}
        traces = visualizer._create_node_traces(G, pos)
        color_map = {t.name: t.marker.color for t in traces}
        assert color_map["Input Units"] == "#2ecc71"
        assert color_map["Hidden Units"] == "#3498db"
        assert color_map["Output Units"] == "#e74c3c"


class TestCreateNodeTrace:
    """Test _create_node_trace method."""

    def test_single_node_trace(self, visualizer):
        """Should create trace for a single node."""
        pos = {"input_0": (0, 0)}
        trace = visualizer._create_node_trace(["input_0"], pos, "#2ecc71", "Input Units")
        assert isinstance(trace, go.Scatter)
        assert trace.name == "Input Units"
        assert len(trace.x) == 1
        assert len(trace.y) == 1
        assert trace.marker.color == "#2ecc71"

    def test_multiple_nodes_trace(self, visualizer):
        """Should create trace for multiple nodes."""
        pos = {"input_0": (0, 0), "input_1": (0, 1.5), "input_2": (0, 3)}
        trace = visualizer._create_node_trace(["input_0", "input_1", "input_2"], pos, "#2ecc71", "Input Units")
        assert len(trace.x) == 3
        assert len(trace.y) == 3
        assert list(trace.x) == [0, 0, 0]

    def test_node_trace_labels(self, visualizer):
        """Node trace text should be formatted labels."""
        pos = {"hidden_0": (5, 0), "hidden_1": (5, 1.5)}
        trace = visualizer._create_node_trace(["hidden_0", "hidden_1"], pos, "#3498db", "Hidden Units")
        assert "Hidden 0" in trace.text
        assert "Hidden 1" in trace.text

    def test_node_trace_marker_properties(self, visualizer):
        """Node trace should have correct marker properties."""
        pos = {"output_0": (10, 0)}
        trace = visualizer._create_node_trace(["output_0"], pos, "#e74c3c", "Output Units")
        assert trace.marker.size == 20
        assert trace.marker.line.width == 2
        assert trace.marker.line.color == "white"


class TestSelectionHighlight:
    """Test _create_selection_highlight method."""

    def test_selection_highlight_empty(self, visualizer):
        """Empty selected_nodes should return empty list."""
        pos = {"input_0": (0, 0)}
        traces = visualizer._create_selection_highlight(pos, [])
        assert traces == []

    def test_selection_highlight_single_node(self, visualizer):
        """Single selected node should create highlight traces."""
        pos = {"input_0": (0, 0)}
        traces = visualizer._create_selection_highlight(pos, ["input_0"])
        assert len(traces) == 2

    def test_selection_highlight_multiple_nodes(self, visualizer):
        """Multiple selected nodes should create multiple highlight trace pairs."""
        pos = {"input_0": (0, 0), "input_1": (0, 1)}
        traces = visualizer._create_selection_highlight(pos, ["input_0", "input_1"])
        assert len(traces) == 4

    def test_selection_highlight_missing_node(self, visualizer):
        """Selected node not in pos should be skipped."""
        pos = {"input_0": (0, 0)}
        traces = visualizer._create_selection_highlight(pos, ["nonexistent"])
        assert traces == []


class TestIntegration:
    """Integration tests for layout methods."""

    def test_full_graph_all_layouts(self, visualizer):
        """Create full graph and test all layout types."""
        topology = {
            "input_units": 3,
            "hidden_units": 4,
            "output_units": 2,
            "connections": [
                {"from": "input_0", "to": "hidden_0", "weight": 0.5},
                {"from": "input_1", "to": "hidden_1", "weight": -0.3},
                {"from": "hidden_0", "to": "output_0", "weight": 0.8},
                {"from": "hidden_1", "to": "output_1", "weight": -0.6},
            ],
        }
        for layout in ["circular", "hierarchical", "spring", "staggered"]:
            fig = visualizer._create_network_graph(topology, layout, show_weights=True)
            assert isinstance(fig, go.Figure)
            assert len(fig.data) > 0

    def test_graph_with_selection(self, visualizer):
        """Create graph with selected nodes."""
        topology = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 1,
            "connections": [
                {"from": "input_0", "to": "hidden_0", "weight": 0.5},
                {"from": "hidden_0", "to": "output_0", "weight": 0.8},
            ],
        }
        fig = visualizer._create_network_graph(
            topology, "hierarchical", show_weights=False, selected_nodes=["hidden_0"]
        )
        assert isinstance(fig, go.Figure)
        trace_names = [t.name for t in fig.data if t.name]
        assert any("Selected" in str(name) for name in trace_names)
