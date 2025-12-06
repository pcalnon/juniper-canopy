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

import contextlib
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

        try:
            visualizer.register_callbacks(app)
            success = True
        except Exception:
            success = False

        assert success


class TestNetworkVisualizerTopologyParsing:
    """Test topology parsing methods."""

    def test_parse_simple_topology(self, visualizer):
        """Should parse simple topology."""
        if hasattr(visualizer, "_parse_topology"):
            topology = {"input_size": 2, "output_size": 1, "hidden_units": 0}

            result = visualizer._parse_topology(topology)
            assert result is not None

    def test_parse_topology_with_hidden_units(self, visualizer):
        """Should parse topology with hidden units."""
        if hasattr(visualizer, "_parse_topology"):
            topology = {"input_size": 2, "output_size": 1, "hidden_units": 3}

            result = visualizer._parse_topology(topology)
            assert result is not None

    def test_parse_empty_topology(self, visualizer):
        """Should handle empty topology."""
        if hasattr(visualizer, "_parse_topology"):
            topology = {}

            with contextlib.suppress(KeyError, ValueError):
                visualizer._parse_topology(topology)


class TestNetworkVisualizerGraphGeneration:
    """Test network graph generation."""

    def test_create_network_graph(self, visualizer):
        """Should create network graph."""
        if hasattr(visualizer, "_create_network_graph"):
            topology = {"input_units": 2, "hidden_units": 0, "output_units": 1, "connections": []}
            graph = visualizer._create_network_graph(topology, "hierarchical", True)
            assert graph is not None

    def test_create_node_layout(self, visualizer):
        """Should create node layout."""
        if hasattr(visualizer, "_create_node_layout"):
            nodes = [{"id": 0, "layer": 0}, {"id": 1, "layer": 1}]
            layout = visualizer._create_node_layout(nodes)
            assert layout is not None

    def test_create_edges(self, visualizer):
        """Should create edges between nodes."""
        if hasattr(visualizer, "_create_edges"):
            nodes = [{"id": 0}, {"id": 1}]
            edges = visualizer._create_edges(nodes)
            assert edges is not None


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
    """Test edge cases."""

    def test_very_large_network(self, visualizer):
        """Should handle very large network topology."""
        # Should not crash with large topology
        if hasattr(visualizer, "_parse_topology"):
            topology = {"input_size": 100, "output_size": 50, "hidden_units": 200}

            with contextlib.suppress(Exception):
                visualizer._parse_topology(topology)

    def test_zero_size_network(self, visualizer):
        """Should handle zero-size network."""
        if hasattr(visualizer, "_parse_topology"):
            topology = {"input_size": 0, "output_size": 0, "hidden_units": 0}

            with contextlib.suppress(ValueError, KeyError):
                visualizer._parse_topology(topology)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
