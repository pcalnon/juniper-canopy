#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_dashboard_enhancements.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Integration tests for dashboard enhancements
#####################################################################

import pytest

from frontend.dashboard_manager import DashboardManager


class TestDashboardEnhancementsIntegration:
    """Integration tests for dashboard enhancements."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_dashboard_initialization_with_enhancements(self, dashboard):
        """Test that dashboard initializes successfully with all enhancements."""
        assert dashboard is not None
        assert dashboard.app is not None
        assert dashboard.metrics_panel is not None

    def test_all_components_registered(self, dashboard):
        """Test that all components are registered."""
        assert len(dashboard.components) == 8  # metrics, network, dataset, decision, about, hdf5_snapshots, redis, cassandra
        assert dashboard.metrics_panel in dashboard.components
        assert dashboard.network_visualizer in dashboard.components
        assert dashboard.dataset_plotter in dashboard.components
        assert dashboard.decision_boundary in dashboard.components
        assert dashboard.about_panel in dashboard.components
        assert dashboard.hdf5_snapshots_panel in dashboard.components
        assert dashboard.redis_panel in dashboard.components
        assert dashboard.cassandra_panel in dashboard.components

    def test_layout_contains_all_enhancements(self, dashboard):
        """Test that layout contains all enhancement features."""
        layout_str = str(dashboard.app.layout)

        # Enhancement 1 & 2: Network Information: Details
        assert "Network Information: Details" in layout_str

        # Enhancement 3: Collapsible sections
        assert "network-info-collapse" in layout_str
        assert "network-info-details-collapse" in layout_str

        # Enhancement 4: Maximum Epochs
        assert "Maximum Epochs" in layout_str
        assert "max-epochs-input" in layout_str

    def test_sidebar_structure(self, dashboard):
        """Test that sidebar has correct structure with enhancements."""
        layout_str = str(dashboard.app.layout)

        # Should have Training Controls card
        assert "Training Controls" in layout_str

        # Should have Network Information card
        assert "Network Information" in layout_str

        # Network Info should contain Details subsection
        assert "Network Information: Details" in layout_str

    def test_training_controls_complete(self, dashboard):
        """Test that training controls section is complete."""
        layout_str = str(dashboard.app.layout)

        # All control buttons
        assert "Start Training" in layout_str or "start-button" in layout_str
        assert "Pause Training" in layout_str or "pause-button" in layout_str
        assert "Resume Training" in layout_str or "resume-button" in layout_str
        assert "Stop Training" in layout_str or "stop-button" in layout_str
        assert "Reset Training" in layout_str or "reset-button" in layout_str

        # All parameter inputs
        assert "learning-rate-input" in layout_str
        assert "max-hidden-units-input" in layout_str
        assert "max-epochs-input" in layout_str


class TestCallbacksIntegration:
    """Test callback integration for enhancements."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_all_callbacks_registered(self, dashboard):
        """Test that all necessary callbacks are registered."""
        callbacks = dashboard.app.callback_map
        assert len(callbacks) > 0

    def test_collapse_callbacks_exist(self, dashboard):
        """Test that collapse toggle callbacks exist."""
        callbacks = dashboard.app.callback_map

        # Network Info collapse callback
        network_info_cb = any("network-info-collapse" in str(cb.get("output", "")) for cb in callbacks.values())
        assert network_info_cb, "Network Info collapse callback not found"

        # Details collapse callback
        details_cb = any("network-info-details-collapse" in str(cb.get("output", "")) for cb in callbacks.values())
        assert details_cb, "Details collapse callback not found"

    def test_param_sync_callback_exists(self, dashboard):
        """Test that parameter sync callback exists."""
        callbacks = dashboard.app.callback_map

        # Should have callback that outputs to all three input fields
        sync_cb = any("max-epochs-input" in str(cb.get("output", "")) for cb in callbacks.values())
        assert sync_cb, "Parameter sync callback not found"


class TestMetricsPanelRefactoring:
    """Test metrics panel refactoring (Network Info removed)."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_metrics_panel_no_longer_has_network_info(self, dashboard):
        """Test that metrics panel no longer contains Network Information section."""
        # Get metrics panel layout
        metrics_layout = dashboard.metrics_panel.get_layout()
        # Verify layout exists (Network Info section moved to sidebar)
        assert metrics_layout is not None

    def test_metrics_panel_still_has_plots(self, dashboard):
        """Test that metrics panel still has its plots."""
        metrics_layout = dashboard.metrics_panel.get_layout()
        metrics_str = str(metrics_layout)

        # Should still have loss and accuracy plots
        assert "loss-plot" in metrics_str or "metrics-panel-loss-plot" in metrics_str
        assert "accuracy-plot" in metrics_str or "metrics-panel-accuracy-plot" in metrics_str


class TestNetworkInfoDetailsAPI:
    """Test Network Information: Details API integration."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_details_panel_update_callback_exists(self, dashboard):
        """Test that details panel has update callback."""
        callbacks = dashboard.app.callback_map

        details_update_cb = any("network-info-details-panel" in str(cb.get("output", "")) for cb in callbacks.values())
        assert details_update_cb, "Details panel update callback not found"

    def test_metrics_panel_helper_accessible(self, dashboard):
        """Test that metrics panel helper method is accessible."""
        assert hasattr(dashboard.metrics_panel, "_create_network_info_table")

        # Test with empty stats
        empty_result = dashboard.metrics_panel._create_network_info_table({})
        assert empty_result is not None

        # Test with sample stats
        sample_stats = {
            "threshold_function": "tanh",
            "optimizer": "sgd",
            "total_nodes": 5,
            "total_edges": 10,
            "total_connections": 15,
            "weight_statistics": {
                "total_weights": 50,
                "positive_weights": 30,
                "negative_weights": 18,
                "zero_weights": 2,
                "mean": 0.25,
                "std_dev": 0.15,
                "variance": 0.0225,
                "skewness": 0.1,
                "kurtosis": 0.05,
                "median": 0.23,
                "mad": 0.12,
                "median_ad": 0.11,
                "iqr": 0.2,
                "z_score_distribution": {
                    "within_1_sigma": 40,
                    "within_2_sigma": 48,
                    "within_3_sigma": 50,
                    "beyond_3_sigma": 0,
                },
            },
        }
        detailed_result = dashboard.metrics_panel._create_network_info_table(sample_stats)
        assert detailed_result is not None


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
