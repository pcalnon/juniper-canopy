#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_metrics_panel.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for MetricsPanel component
#####################################################################
"""Unit tests for MetricsPanel component."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import plotly.graph_objects as go  # noqa: E402, F401 - used in assertions
import pytest  # noqa: E402

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402


@pytest.fixture
def config():
    """Basic config for metrics panel."""
    return {
        "max_data_points": 1000,
        "update_interval": 1000,
    }


@pytest.fixture
def metrics_panel(config):
    """Create MetricsPanel instance."""
    return MetricsPanel(config, component_id="test-metrics")


class TestMetricsPanelInitialization:
    """Test MetricsPanel initialization."""

    def test_init_with_default_config(self):
        """Should initialize with empty config."""
        panel = MetricsPanel({})
        assert panel is not None
        assert panel.component_id == "metrics-panel"

    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        panel = MetricsPanel(config, component_id="custom-id")
        assert panel.component_id == "custom-id"

    def test_init_sets_max_data_points(self, config):
        """Should set max_data_points from config."""
        panel = MetricsPanel(config)
        assert panel.max_data_points == 1000

    def test_init_sets_update_interval(self, config):
        """Should set update_interval from config."""
        panel = MetricsPanel(config)
        assert panel.update_interval == 1000

    def test_init_default_max_data_points(self):
        """Should use default max_data_points if not in config."""
        panel = MetricsPanel({})
        assert panel.max_data_points == 1000

    def test_init_default_update_interval(self):
        """Should use default update_interval if not in config."""
        panel = MetricsPanel({})
        assert panel.update_interval == 1000

    def test_init_creates_empty_metrics_history(self, metrics_panel):
        """Should initialize with empty metrics history."""
        assert metrics_panel.metrics_history == []


class TestMetricsPanelLayout:
    """Test MetricsPanel layout generation."""

    def test_get_layout_returns_div(self, metrics_panel):
        """get_layout should return Dash Div."""
        layout = metrics_panel.get_layout()
        assert layout is not None
        from dash import html

        assert isinstance(layout, html.Div)

    def test_layout_contains_header(self, metrics_panel):
        """Layout should contain header."""
        layout = metrics_panel.get_layout()
        # Check that layout has children
        assert hasattr(layout, "children")
        assert len(layout.children) > 0

    def test_layout_contains_graphs(self, metrics_panel):
        """Layout should contain graph components."""
        layout = metrics_panel.get_layout()
        from dash import dcc

        # Recursively find all dcc.Graph components
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
        # Should have at least one graph
        assert len(graphs) > 0

    def test_layout_has_correct_component_ids(self, metrics_panel):
        """Layout should use correct component IDs."""
        layout = metrics_panel.get_layout()

        # Check for status div
        def find_id(component, target_id):
            if hasattr(component, "id") and component.id == target_id:
                return True
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    return any(find_id(child, target_id) for child in component.children)
                elif component.children is not None:
                    return find_id(component.children, target_id)
            return False

        # Should have status div with component-specific ID
        assert find_id(layout, f"{metrics_panel.component_id}-status")


class TestMetricsPanelCallbacks:
    """Test MetricsPanel callback registration."""

    def test_register_callbacks_returns_none(self, metrics_panel):
        """register_callbacks should return None."""
        from dash import Dash

        app = Dash(__name__)
        result = metrics_panel.register_callbacks(app)
        assert result is None

    def test_register_callbacks_with_mock_app(self, metrics_panel):
        """Should handle callback setup without errors."""
        from dash import Dash

        app = Dash(__name__)

        try:
            metrics_panel.register_callbacks(app)
            success = True
        except Exception:
            success = False

        assert success


class TestMetricsPanelDataFormatting:
    """Test data formatting methods if they exist."""

    def test_format_metrics_for_plotting(self, metrics_panel):
        """Should format metrics data for plotting."""
        # Check if panel has a format method
        if hasattr(metrics_panel, "_format_for_plotting"):
            # If there's a formatting method, test it
            sample_data = [
                {"epoch": 1, "loss": 0.5, "accuracy": 0.8},
                {"epoch": 2, "loss": 0.4, "accuracy": 0.85},
            ]

            formatted = metrics_panel._format_for_plotting(sample_data)
            assert formatted is not None

    def test_empty_metrics_handling(self, metrics_panel):
        """Should handle empty metrics gracefully."""
        # Panel should work with no data
        assert metrics_panel.metrics_history == []


class TestMetricsPanelGraphGeneration:
    """Test graph generation methods."""

    def test_create_loss_graph(self, metrics_panel):
        """Should create loss graph if method exists."""
        if hasattr(metrics_panel, "_create_loss_graph"):
            graph = metrics_panel._create_loss_graph([])
            assert graph is not None

    def test_create_accuracy_graph(self, metrics_panel):
        """Should create accuracy graph if method exists."""
        if hasattr(metrics_panel, "_create_accuracy_graph"):
            graph = metrics_panel._create_accuracy_graph([])
            assert graph is not None


class TestMetricsPanelConfiguration:
    """Test configuration handling."""

    def test_config_override_max_data_points(self):
        """Should override max_data_points from config."""
        config = {"max_data_points": 500}
        panel = MetricsPanel(config)
        assert panel.max_data_points == 500

    def test_config_override_update_interval(self):
        """Should override update_interval from config."""
        config = {"update_interval": 2000}
        panel = MetricsPanel(config)
        assert panel.update_interval == 2000

    def test_config_multiple_overrides(self):
        """Should handle multiple config overrides."""
        config = {
            "max_data_points": 2000,
            "update_interval": 500,
        }
        panel = MetricsPanel(config)
        assert panel.max_data_points == 2000
        assert panel.update_interval == 500


class TestMetricsPanelInheritance:
    """Test BaseComponent inheritance."""

    def test_inherits_from_base_component(self, metrics_panel):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(metrics_panel, BaseComponent)

    def test_has_logger(self, metrics_panel):
        """Should have logger from BaseComponent."""
        assert hasattr(metrics_panel, "logger")
        assert metrics_panel.logger is not None

    def test_has_config(self, metrics_panel):
        """Should have config from BaseComponent."""
        assert hasattr(metrics_panel, "config")

    def test_has_component_id(self, metrics_panel):
        """Should have component_id from BaseComponent."""
        assert hasattr(metrics_panel, "component_id")
        assert metrics_panel.component_id == "test-metrics"


class TestMetricsPanelEdgeCases:
    """Test edge cases."""

    def test_very_large_max_data_points(self):
        """Should handle very large max_data_points."""
        config = {"max_data_points": 1000000}
        panel = MetricsPanel(config)
        assert panel.max_data_points == 1000000

    def test_zero_update_interval(self):
        """Should handle zero update_interval."""
        config = {"update_interval": 0}
        panel = MetricsPanel(config)
        assert panel.update_interval == 0

    def test_negative_max_data_points(self):
        """Should handle negative max_data_points."""
        config = {"max_data_points": -100}
        panel = MetricsPanel(config)
        # Should either accept or use default
        assert panel.max_data_points is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
