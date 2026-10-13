#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_network_visualizer.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for NetworkVisualizer component
#####################################################################
"""Unit tests for NetworkVisualizer component."""

import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402


@pytest.fixture
def config():
    """Basic config for network visualizer."""
    return {}


@pytest.fixture
def visualizer(config):
    """Create NetworkVisualizer instance."""
    return NetworkVisualizer(config, component_id="test-network")


class TestNetworkVisualizerInitialization:
    """Test NetworkVisualizer initialization."""

    def test_init_with_default_config(self):
        """Should initialize with empty config."""
        viz = NetworkVisualizer({})
        assert viz is not None
        assert viz.component_id == "network-visualizer"

    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        viz = NetworkVisualizer(config, component_id="custom-viz")
        assert viz.component_id == "custom-viz"

    def test_init_sets_show_weights(self):
        """Should set show_weights from config."""
        config = {"show_weights": False}
        viz = NetworkVisualizer(config)
        assert viz.show_weights is False

    def test_init_default_show_weights(self):
        """Should use default show_weights if not in config."""
        viz = NetworkVisualizer({})
        assert viz.show_weights is True


class TestNetworkVisualizerLayout:
    """Test NetworkVisualizer layout generation."""

    def test_get_layout_returns_div(self, visualizer):
        """get_layout should return Dash Div."""
        layout = visualizer.get_layout()
        assert layout is not None
        from dash import html

        assert isinstance(layout, html.Div)

    def test_layout_contains_graph(self, visualizer):
        """Layout should contain graph component."""
        layout = visualizer.get_layout()
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

    def test_layout_has_component_id(self, visualizer):
        """Layout should use correct component IDs."""
        layout = visualizer.get_layout()

        def find_id(component, target_id):
            if hasattr(component, "id") and target_id in str(component.id):
                return True
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    return any(find_id(child, target_id) for child in component.children)
                elif component.children is not None:
                    return find_id(component.children, target_id)
            return False

        # Should have component-specific ID
        assert find_id(layout, visualizer.component_id)


class TestNetworkVisualizerCallbacks:
    """Test NetworkVisualizer callback registration."""

    def test_register_callbacks_returns_none(self, visualizer):
        """register_callbacks should return None."""
        from dash import Dash

        app = Dash(__name__)
        result = visualizer.register_callbacks(app)
        assert result is None

    def test_register_callbacks_with_mock_app(self, visualizer):
        """Should handle callback setup without errors."""
        from dash import Dash

        app = Dash(__name__)
        # Should not raise - direct call without try/except
        visualizer.register_callbacks(app)


class TestNetworkVisualizerTopologyParsing:
    """Test topology parsing via the observable graph-creation path.

    Black-box replacement for the historically-skipped
    ``TestNetworkVisualizerTopologyParsing`` (asserted on a
    ``_parse_topology`` method that does not exist — topology parsing
    happens inline inside ``_create_network_graph``, the actual
    observable seam). The expected schema is the one
    ``_create_network_graph`` consumes:
    ``{"input_units": N, "hidden_units": N, "output_units": N,
    "connections": [...]}``. The skipped tests used ``input_size`` /
    ``output_size`` — names that no caller actually produces.
    """

    def test_parse_simple_topology(self, visualizer):
        """Topology with no hidden units → graph has at least input + output traces."""
        topology = {"input_units": 2, "output_units": 1, "hidden_units": 0, "connections": []}
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert fig is not None
        # `_create_network_graph` produces edge_traces + node_traces.
        # Even with 0 hidden units and 0 connections, node traces for
        # input/output still appear.
        assert len(fig.data) > 0

    def test_parse_topology_with_hidden_units(self, visualizer):
        """Topology with hidden units → graph honours the hidden count.

        ``_create_node_trace`` derives display labels via
        ``node_id.replace("_", " ").title()``, so ``hidden_0`` →
        ``"Hidden 0"``. We assert on the display form (what a user
        actually sees in the rendered figure).
        """
        topology = {
            "input_units": 2,
            "output_units": 1,
            "hidden_units": 3,
            "connections": [
                {"from": "input_0", "to": "hidden_0", "weight": 0.1},
                {"from": "hidden_2", "to": "output_0", "weight": 0.2},
            ],
        }
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert fig is not None
        all_text = " ".join(str(trace.text or "") + " " + str(trace.hovertext or "") for trace in fig.data)
        for i in range(3):
            assert f"Hidden {i}" in all_text, f"Hidden {i} missing from rendered figure"
        # Also pin the input/output rendering so accidental layer
        # mis-bucketing surfaces.
        for i in range(2):
            assert f"Input {i}" in all_text
        assert "Output 0" in all_text

    def test_parse_empty_topology(self, visualizer):
        """Empty topology returns the documented empty-graph figure, does not raise.

        ``_create_network_graph`` treats missing keys as zero-counts and
        renders a degenerate figure rather than raising — the dashboard
        survives early-load states. The skipped test asserted
        ``pytest.raises`` which assumed a different contract.
        """
        topology = {}
        fig = visualizer._create_network_graph(topology, "hierarchical", True)
        assert fig is not None


class TestNetworkVisualizerGraphGeneration:
    """Test network graph generation."""

    def test_create_network_graph(self, visualizer):
        """Should create network graph."""
        topology = {"input_units": 2, "hidden_units": 0, "output_units": 1, "connections": []}
        graph = visualizer._create_network_graph(topology, "hierarchical", True)
        assert graph is not None

    def test_create_node_layout(self, visualizer):
        """Node positions must be computed for every node in the topology.

        Black-box replacement for the historically-skipped
        ``test_create_node_layout`` (asserted on a ``_create_node_layout``
        method that does not exist — node positioning lives in
        ``_calculate_layout(G, layout_type, n_input, n_hidden, n_output)``
        which returns ``Dict[str, Tuple[float, float]]``).
        """
        import networkx as nx

        # Build the topology graph the same way ``_create_network_graph``
        # does, then drive ``_calculate_layout`` directly.
        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("hidden_0", layer="hidden")
        G.add_node("output_0", layer="output")
        pos = visualizer._calculate_layout(G, "hierarchical", n_input=1, n_hidden=1, n_output=1)
        assert isinstance(pos, dict)
        # Every node must have a 2D position.
        for node_id in ("input_0", "hidden_0", "output_0"):
            assert node_id in pos, f"layout missing position for {node_id}"
            x, y = pos[node_id]
            assert isinstance(x, (int, float))
            assert isinstance(y, (int, float))

    def test_create_edges(self, visualizer):
        """Edge traces must be emitted for each connection in the topology.

        Black-box replacement for the historically-skipped
        ``test_create_edges`` (asserted on a ``_create_edges`` method
        that does not exist — edge trace creation lives in
        ``_create_edge_traces(G, pos, show_weights)`` which returns a
        list of plotly ``Scatter`` traces).
        """
        import networkx as nx

        G = nx.DiGraph()
        G.add_node("input_0", layer="input")
        G.add_node("output_0", layer="output")
        G.add_edge("input_0", "output_0", weight=0.42)
        pos = {"input_0": (0.0, 0.0), "output_0": (1.0, 0.0)}
        edges = visualizer._create_edge_traces(G, pos, show_weights=True)
        assert isinstance(edges, list)
        assert len(edges) >= 1
        # The single connection in the test topology must produce at
        # least one edge trace carrying the endpoints.
        # Plotly Scatter ``x``/``y`` are tuples of numbers (with possible
        # ``None`` separators for multi-edge traces).
        edge_xs = []
        edge_ys = []
        for trace in edges:
            edge_xs.extend([v for v in trace.x if v is not None])
            edge_ys.extend([v for v in trace.y if v is not None])
        # Endpoints must appear among the trace coordinates.
        assert 0.0 in edge_xs and 1.0 in edge_xs
        assert 0.0 in edge_ys


class TestNetworkVisualizerInheritance:
    """Test BaseComponent inheritance."""

    def test_inherits_from_base_component(self, visualizer):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(visualizer, BaseComponent)

    def test_has_logger(self, visualizer):
        """Should have logger from BaseComponent."""
        assert hasattr(visualizer, "logger")
        assert visualizer.logger is not None

    def test_has_config(self, visualizer):
        """Should have config from BaseComponent."""
        assert hasattr(visualizer, "config")

    def test_has_component_id(self, visualizer):
        """Should have component_id from BaseComponent."""
        assert hasattr(visualizer, "component_id")
        assert visualizer.component_id == "test-network"


class TestNetworkVisualizerConfiguration:
    """Test configuration handling."""

    def test_config_override_layout_type(self):
        """Should override layout_type from config."""
        config = {"layout": "spring"}
        viz = NetworkVisualizer(config)
        assert viz.layout_type == "spring"

    def test_config_with_extra_params(self):
        """Should handle extra config parameters."""
        config = {"show_weights": False, "extra_param": "value"}
        viz = NetworkVisualizer(config)
        assert viz.show_weights is False


class TestNetworkVisualizerEdgeCases:
    """Test edge cases via ``_create_network_graph`` — the real seam.

    Black-box replacement for the historically-skipped
    ``TestNetworkVisualizerEdgeCases`` (asserted on a ``_parse_topology``
    method that does not exist). The schema used here matches the one
    ``_create_network_graph`` consumes:
    ``input_units``/``output_units``/``hidden_units`` (not
    ``input_size``/``output_size``).
    """

    def test_very_large_network(self, visualizer):
        """Large topology renders without crashing."""
        topology = {
            "input_units": 100,
            "output_units": 50,
            "hidden_units": 200,
            "connections": [],
        }
        fig = visualizer._create_network_graph(topology, "hierarchical", False)
        assert fig is not None
        # Sanity: rendered figure has traces.
        assert len(fig.data) > 0

    def test_zero_size_network(self, visualizer):
        """All-zero topology returns the documented empty-graph figure, does not raise.

        Treats zero counts as the no-network state the dashboard renders
        before any training has started. The skipped test asserted
        ``pytest.raises`` which assumed a different contract than the
        one that actually exists.
        """
        topology = {"input_units": 0, "output_units": 0, "hidden_units": 0, "connections": []}
        fig = visualizer._create_network_graph(topology, "hierarchical", False)
        assert fig is not None


class TestHierarchyDepthFilter:
    """CAN-020: ``_apply_hierarchy_filter`` is the per-render filter that
    drops cascade-order hidden units beyond the slider's value. Pure
    function — no Dash, no state — so we can drive it directly.
    """

    @pytest.fixture
    def topology_with_5_hidden(self):
        return {
            "input_units": 2,
            "hidden_units": 5,
            "output_units": 2,
            "connections": [
                {"from": "input_0", "to": "hidden_0", "weight": 0.1},
                {"from": "input_0", "to": "hidden_1", "weight": 0.2},
                {"from": "input_1", "to": "hidden_2", "weight": 0.3},
                {"from": "hidden_0", "to": "hidden_1", "weight": 0.4},
                {"from": "hidden_1", "to": "hidden_3", "weight": 0.5},
                {"from": "hidden_2", "to": "hidden_4", "weight": 0.6},
                {"from": "hidden_3", "to": "output_0", "weight": 0.7},
                {"from": "hidden_4", "to": "output_1", "weight": 0.8},
                {"from": "input_0", "to": "output_0", "weight": 0.9},
            ],
        }

    def test_none_depth_returns_topology_unchanged(self, topology_with_5_hidden):
        result, label = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, None, 5)
        assert result is topology_with_5_hidden  # same reference, no copy on no-op
        assert label == "all"

    def test_depth_at_total_returns_unchanged(self, topology_with_5_hidden):
        result, label = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 5, 5)
        assert result is topology_with_5_hidden
        assert label == "all"

    def test_depth_above_total_returns_unchanged(self, topology_with_5_hidden):
        result, label = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 99, 5)
        assert result is topology_with_5_hidden
        assert label == "all"

    def test_depth_zero_returns_unchanged(self, topology_with_5_hidden):
        """Slider at 0 means 'no filter applied', not 'show no hidden units'.
        The slider min is 0 only because we never actually set the value to 0
        in the clientside handler — but the filter must treat 0 as a no-op so
        the rendered graph never blanks out by accident."""
        result, label = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 0, 5)
        assert result is topology_with_5_hidden
        assert label == "all"

    def test_depth_3_keeps_first_3_units(self, topology_with_5_hidden):
        result, label = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 3, 5)
        assert result is not topology_with_5_hidden  # copy, not mutation
        assert result["hidden_units"] == 3
        assert label == "3 of 5"

    def test_depth_3_drops_connections_to_filtered_units(self, topology_with_5_hidden):
        result, _ = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 3, 5)
        # Edges touching hidden_3 or hidden_4 must be gone.
        for conn in result["connections"]:
            from_node = conn.get("from", "")
            to_node = conn.get("to", "")
            assert "hidden_3" not in (from_node, to_node), f"hidden_3 leaked in {conn}"
            assert "hidden_4" not in (from_node, to_node), f"hidden_4 leaked in {conn}"

    def test_depth_3_keeps_connections_among_first_3(self, topology_with_5_hidden):
        result, _ = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 3, 5)
        kept_pairs = {(c.get("from"), c.get("to")) for c in result["connections"]}
        # These should remain.
        assert ("input_0", "hidden_0") in kept_pairs
        assert ("input_0", "hidden_1") in kept_pairs
        assert ("input_1", "hidden_2") in kept_pairs
        assert ("hidden_0", "hidden_1") in kept_pairs
        # input→output skip-layer connections also stay.
        assert ("input_0", "output_0") in kept_pairs

    def test_depth_1_keeps_only_first_unit(self, topology_with_5_hidden):
        result, label = NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 1, 5)
        assert result["hidden_units"] == 1
        assert label == "1 of 5"
        for conn in result["connections"]:
            from_node = conn.get("from", "")
            to_node = conn.get("to", "")
            for hidden_idx in (1, 2, 3, 4):
                assert f"hidden_{hidden_idx}" not in (from_node, to_node), f"hidden_{hidden_idx} leaked at depth=1"

    def test_filter_does_not_mutate_input(self, topology_with_5_hidden):
        """The input dict comes from a Dash store; other callbacks read it.
        Mutation would be a race. Verify defensively."""
        original_n = topology_with_5_hidden["hidden_units"]
        original_conns = list(topology_with_5_hidden["connections"])
        NetworkVisualizer._apply_hierarchy_filter(topology_with_5_hidden, 2, 5)
        assert topology_with_5_hidden["hidden_units"] == original_n
        assert topology_with_5_hidden["connections"] == original_conns

    def test_filter_handles_malformed_node_id(self):
        """Defensive: connections with non-conventional node IDs (e.g. legacy
        formats, custom backends) should not crash the filter — they're kept
        as-is when the unit-index can't be parsed."""
        topology = {
            "input_units": 1,
            "hidden_units": 3,
            "output_units": 1,
            "connections": [
                {"from": "input_0", "to": "hidden_0", "weight": 0.1},
                {"from": "hidden_x", "to": "hidden_y", "weight": 0.2},  # unparseable
                {"from": "hidden_2", "to": "output_0", "weight": 0.3},
            ],
        }
        result, _ = NetworkVisualizer._apply_hierarchy_filter(topology, 1, 3)
        # hidden_2 connection dropped; hidden_x/y connection retained (can't filter it).
        kept_pairs = {(c.get("from"), c.get("to")) for c in result["connections"]}
        assert ("input_0", "hidden_0") in kept_pairs
        assert ("hidden_x", "hidden_y") in kept_pairs
        assert ("hidden_2", "output_0") not in kept_pairs


class TestHierarchyDepthSliderWiring:
    """Source-level invariants: the slider wiring must match the dashboard
    contract. Same pattern as TestGapWs25TopologyRestGate / etc.
    """

    @pytest.fixture
    def visualizer_source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "frontend" / "components" / "network_visualizer.py"
        return path.read_text(encoding="utf-8")

    def test_slider_id_in_layout(self, visualizer_source):
        assert "depth-slider" in visualizer_source
        assert "depth-slider-container" in visualizer_source
        assert "depth-label" in visualizer_source

    def test_slider_is_input_to_graph_callback(self, visualizer_source):
        assert "depth-slider" in visualizer_source
        # Both the depth-slider value and the depth-label readout must be wired.
        assert "depth_filter" in visualizer_source

    def test_clientside_callback_bumps_max(self, visualizer_source):
        """Slider max must be bumped clientside when hidden_units grows."""
        assert "topology.hidden_units" in visualizer_source
        # Container must hide when nHidden === 0.
        assert 'display: "none"' in visualizer_source or "display: 'none'" in visualizer_source

    def test_clientside_preserves_user_value(self, visualizer_source):
        """The clientside callback must preserve the user's pick across grow
        events (so a focus on the first 3 units isn't reset every cascade_add)."""
        assert "currentValue" in visualizer_source

    def test_apply_hierarchy_filter_is_static(self):
        """``_apply_hierarchy_filter`` should be callable without a NetworkVisualizer
        instance — the filter is a pure function and tests + future reuse expect that."""
        import inspect

        method = inspect.getattr_static(NetworkVisualizer, "_apply_hierarchy_filter")
        assert isinstance(method, staticmethod)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
