#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_dashboard_rendering_regression.py
# Author:        Paul Calnon
# Version:       0.2.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Regression tests to ensure dashboard plots render correctly across all tabs.
#    Tests for Issue: Dashboard image rendering regression.
#
#####################################################################################################################################################################################################
from pathlib import Path

import pytest  # noqa: F401

from frontend.components.dataset_plotter import DatasetPlotter
from frontend.components.decision_boundary import DecisionBoundary
from frontend.components.metrics_panel import MetricsPanel
from frontend.components.network_visualizer import NetworkVisualizer


class TestDashboardPlotRendering:
    """Regression tests for dashboard plot rendering across all tabs."""

    def test_metrics_panel_loss_plot_has_data(self):
        """Test that metrics panel loss plot contains data traces."""
        mp = MetricsPanel({})
        test_data = [
            {
                "epoch": 1,
                "metrics": {"loss": 0.5, "accuracy": 0.7},
                "phase": "output",
                "network_topology": {"hidden_units": 0},
            },
            {
                "epoch": 2,
                "metrics": {"loss": 0.4, "accuracy": 0.75},
                "phase": "output",
                "network_topology": {"hidden_units": 1},
            },
        ]
        loss_fig = mp._create_loss_plot(test_data, "light")

        assert len(loss_fig.data) > 0, "Loss plot should have traces"
        assert loss_fig.data[0].x is not None, "Loss plot should have x data"
        assert loss_fig.data[0].y is not None, "Loss plot should have y data"
        assert len(loss_fig.data[0].x) > 0, "Loss plot should have non-empty x data"

    def test_metrics_panel_accuracy_plot_has_data(self):
        """Test that metrics panel accuracy plot contains data traces."""
        mp = MetricsPanel({})
        test_data = [
            {
                "epoch": 1,
                "metrics": {"loss": 0.5, "accuracy": 0.7},
                "phase": "output",
                "network_topology": {"hidden_units": 0},
            },
            {
                "epoch": 2,
                "metrics": {"loss": 0.4, "accuracy": 0.75},
                "phase": "output",
                "network_topology": {"hidden_units": 1},
            },
        ]
        acc_fig = mp._create_accuracy_plot(test_data, "light")

        assert len(acc_fig.data) > 0, "Accuracy plot should have traces"
        assert acc_fig.data[0].x is not None, "Accuracy plot should have x data"
        assert acc_fig.data[0].y is not None, "Accuracy plot should have y data"

    def test_dataset_plotter_scatter_plot_has_data(self):
        """Test that dataset plotter scatter plot contains data traces."""
        dp = DatasetPlotter({})
        test_dataset = {
            "inputs": [[0, 0], [1, 1], [0, 1], [1, 0]],
            "targets": [0, 0, 1, 1],
            "num_samples": 4,
            "num_features": 2,
        }
        scatter_fig = dp._create_scatter_plot(test_dataset, "light")

        assert len(scatter_fig.data) > 0, "Scatter plot should have traces"
        assert scatter_fig.data[0].x is not None, "Scatter plot should have x data"
        assert len(scatter_fig.data) >= 2, "Scatter plot should have traces for each class"

    def test_decision_boundary_empty_plot_renders(self):
        """Test that decision boundary can create empty plot."""
        db = DecisionBoundary({})
        empty_fig = db._create_empty_plot("Test message", "light")

        assert empty_fig is not None, "Empty plot should be created"
        assert len(empty_fig.layout.annotations) > 0, "Empty plot should have annotation message"

    def test_network_visualizer_graph_has_data(self):
        """Test that network visualizer creates graph with data."""
        nv = NetworkVisualizer({})
        test_topology = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 1,
            "connections": [
                {"source": "input_0", "target": "hidden_0", "weight": 0.5},
                {"source": "input_1", "target": "hidden_0", "weight": -0.3},
                {"source": "hidden_0", "target": "output_0", "weight": 0.8},
            ],
        }
        topo_fig = nv._create_network_graph(test_topology, "spring", True, None, "light")

        assert len(topo_fig.data) > 0, "Network graph should have traces"
        assert topo_fig.data[0].x is not None, "Network graph should have positioned nodes"

    def test_all_plots_support_dark_theme(self):
        """Test that all plot types work with dark theme."""
        # Metrics panel
        mp = MetricsPanel({})
        test_data = [
            {
                "epoch": 1,
                "metrics": {"loss": 0.5, "accuracy": 0.7},
                "phase": "output",
                "network_topology": {"hidden_units": 0},
            }
        ]
        loss_dark = mp._create_loss_plot(test_data, "dark")
        assert str(loss_dark.layout.template) == "plotly_dark" or loss_dark.layout.plot_bgcolor == "#242424", f"Expected dark theme, got template={loss_dark.layout.template}, bgcolor={loss_dark.layout.plot_bgcolor}"

        # Dataset plotter
        dp = DatasetPlotter({})
        test_dataset = {"inputs": [[0, 0]], "targets": [0], "num_samples": 1, "num_features": 2}
        scatter_dark = dp._create_scatter_plot(test_dataset, "dark")
        assert str(scatter_dark.layout.template) == "plotly_dark" or scatter_dark.layout.plot_bgcolor == "#242424"

        # Decision boundary
        db = DecisionBoundary({})
        empty_dark = db._create_empty_plot("Test", "dark")
        assert str(empty_dark.layout.template) == "plotly_dark" or empty_dark.layout.plot_bgcolor == "#242424"

        # Network visualizer
        nv = NetworkVisualizer({})
        empty_nv = nv._create_empty_graph("dark")
        # Network visualizer uses different colors or template
        assert empty_nv.layout.plot_bgcolor in ["#1a1a1a", "#242424"] or str(empty_nv.layout.template) == "plotly_dark"

    def test_plots_preserve_interactivity(self):
        """Test that plots have interactive elements for tooltips/hovers."""
        mp = MetricsPanel({})
        test_data = [
            {
                "epoch": 1,
                "metrics": {"loss": 0.5, "accuracy": 0.7},
                "phase": "output",
                "network_topology": {"hidden_units": 0},
            }
        ]
        loss_fig = mp._create_loss_plot(test_data, "light")

        # Plotly graphs should have hovermode enabled by default or explicitly set
        assert loss_fig.layout.hovermode in [
            "closest",
            "x",
            "y",
            "x unified",
            "y unified",
            True,
        ], "Plot should have hover/tooltip enabled"

    def test_css_no_global_interference(self):
        """Test that CSS doesn't have global selectors that interfere with Plotly."""
        # Get path to CSS files
        css_dir = Path(__file__).parent.parent.parent / "frontend" / "assets"

        # Check dark_mode.css for problematic global * selector
        dark_css_path = css_dir / "dark_mode.css"
        if dark_css_path.exists():
            content = dark_css_path.read_text()
            # The global * selector should not be present
            assert "\n* {" not in content and "\n*{" not in content, "dark_mode.css should not have global * selector that breaks Plotly rendering"

        # Check that plotly_fix.css exists with protective rules
        plotly_css_path = css_dir / "plotly_fix.css"
        assert plotly_css_path.exists(), "plotly_fix.css should exist to protect Plotly from CSS interference"

        plotly_css = plotly_css_path.read_text()
        assert ".js-plotly-plot" in plotly_css, "plotly_fix.css should target Plotly containers"
        assert "opacity: 1 !important" in plotly_css, "plotly_fix.css should force visibility"
        assert "transition: none !important" in plotly_css, "plotly_fix.css should disable transitions on Plotly elements"
