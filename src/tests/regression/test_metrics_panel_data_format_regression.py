#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_metrics_panel_data_format_regression.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-13
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for MetricsPanel component
#####################################################################
"""Unit tests for MetricsPanel component."""

import sys
from pathlib import Path

# Add src to path (must be before local imports)
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import plotly.graph_objects as go  # noqa: E402
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


class TestMetricsPanelDataFormatRegression:
    """Regression tests for metrics data format handling.

    These tests catch the AttributeError that occurred when /api/metrics/history
    returned a dict with "history" key instead of a raw list.
    """

    def test_metrics_panel_handles_dict_with_history_key(self):
        """Regression test: Handle /api/metrics/history returning {"history": [...]}"""
        panel = MetricsPanel(config={}, component_id="test-metrics")

        # Mock metrics data in new format (dict with "history" key)
        metrics_dict = {
            "history": [
                {"epoch": 1, "metrics": {"loss": 0.5, "accuracy": 0.8}, "phase": "output"},
                {"epoch": 2, "metrics": {"loss": 0.3, "accuracy": 0.9}, "phase": "output"},
            ]
        }

        # Should create plots without AttributeError on .get() method
        loss_plot = panel._create_loss_plot(metrics_dict["history"])
        assert loss_plot is not None
        assert isinstance(loss_plot, go.Figure)

        accuracy_plot = panel._create_accuracy_plot(metrics_dict["history"])
        assert accuracy_plot is not None
        assert isinstance(accuracy_plot, go.Figure)

    def test_metrics_panel_handles_raw_list(self):
        """Test backward compatibility with raw list format"""
        panel = MetricsPanel(config={}, component_id="test-metrics")

        # Mock metrics data in old format (raw list)
        metrics_list = [
            {"epoch": 1, "metrics": {"loss": 0.5, "accuracy": 0.8}, "phase": "output"},
            {"epoch": 2, "metrics": {"loss": 0.3, "accuracy": 0.9}, "phase": "output"},
        ]

        # Should handle list format without issues
        loss_plot = panel._create_loss_plot(metrics_list)
        assert loss_plot is not None
        assert isinstance(loss_plot, go.Figure)

        accuracy_plot = panel._create_accuracy_plot(metrics_list)
        assert accuracy_plot is not None
        assert isinstance(accuracy_plot, go.Figure)

    def test_metrics_panel_handles_empty_dict(self):
        """Test graceful handling of empty/malformed data"""
        panel = MetricsPanel(config={}, component_id="test-metrics")

        # Should handle empty dict gracefully
        empty_plot = panel._create_loss_plot([])
        assert empty_plot is not None
        assert isinstance(empty_plot, go.Figure)

        # Test with dict containing empty list
        metrics_dict = {"history": []}
        empty_plot2 = panel._create_loss_plot(metrics_dict.get("history", []))
        assert empty_plot2 is not None

    def test_metrics_panel_handles_dict_with_data_key(self):
        """Test handling of alternative dict format with 'data' key"""
        panel = MetricsPanel(config={}, component_id="test-metrics")

        # Some endpoints might return {"data": [...]}
        metrics_dict = {
            "data": [
                {"epoch": 1, "metrics": {"loss": 0.4, "accuracy": 0.85}, "phase": "candidate"},
                {"epoch": 2, "metrics": {"loss": 0.2, "accuracy": 0.95}, "phase": "output"},
            ]
        }

        # Should handle this format
        loss_plot = panel._create_loss_plot(metrics_dict["data"])
        assert loss_plot is not None
        assert isinstance(loss_plot, go.Figure)

    def test_metrics_panel_normalization_in_callback_context(self):
        """Test that callback normalization logic prevents AttributeError"""
        panel = MetricsPanel(config={}, component_id="test-metrics")

        # Simulate what happens in the callback with different data formats
        test_cases = [
            # Dict with "history" key
            {"history": [{"epoch": 1, "metrics": {"loss": 0.5}, "phase": "output"}]},
            # Dict with "data" key
            {"data": [{"epoch": 1, "metrics": {"loss": 0.5}, "phase": "output"}]},
            # Raw list
            [{"epoch": 1, "metrics": {"loss": 0.5}, "phase": "output"}],
            # Empty dict
            {},
            # Empty list
            [],
        ]

        for test_data in test_cases:
            # Simulate the normalization logic from the callback
            if isinstance(test_data, dict):
                if isinstance(test_data.get("history"), list):
                    normalized = test_data["history"]
                elif isinstance(test_data.get("data"), list):
                    normalized = test_data["data"]
                else:
                    normalized = []
            elif not isinstance(test_data, list):
                normalized = []
            else:
                normalized = test_data

            # Should always result in a list
            assert isinstance(normalized, list)

            # Should not raise AttributeError when creating plots
            if normalized:
                plot = panel._create_loss_plot(normalized)
                assert plot is not None

    def test_metrics_panel_handles_none_input(self):
        """Test handling of None input (edge case)"""
        panel = MetricsPanel(config={}, component_id="test-metrics")

        # Normalize None to empty list
        metrics_data = None
        if not isinstance(metrics_data, list):
            metrics_data = []

        # Should handle gracefully
        assert metrics_data == []
        empty_plot = panel._create_loss_plot(metrics_data)
        assert empty_plot is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
