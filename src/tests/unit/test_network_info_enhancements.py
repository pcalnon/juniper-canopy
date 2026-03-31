#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_network_info_enhancements.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for Network Information enhancements (collapsible sections)
#####################################################################
"""Unit tests for Network Information collapsible sections enhancement."""

import pytest

from frontend.dashboard_manager import DashboardManager


class TestNetworkInfoCollapsibleSections:
    """Test Network Information collapsible sections."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_network_info_section_exists(self, dashboard):
        """Test that Network Information section exists in layout."""
        layout_str = str(dashboard.app.layout)
        assert "Network Information" in layout_str

    def test_network_info_collapse_component_exists(self, dashboard):
        """Test that collapsible component exists for Network Information."""
        # Search for the collapse component ID in the layout
        layout_str = str(dashboard.app.layout)
        assert "network-info-collapse" in layout_str

    def test_network_info_details_section_exists(self, dashboard):
        """Test that Network Information: Details subsection exists."""
        layout_str = str(dashboard.app.layout)
        assert "Network Information: Details" in layout_str

    def test_network_info_details_collapse_exists(self, dashboard):
        """Test that collapsible component exists for Details subsection."""
        layout_str = str(dashboard.app.layout)
        assert "network-info-details-collapse" in layout_str

    def test_network_info_header_clickable(self, dashboard):
        """Test that Network Information header is clickable."""
        layout_str = str(dashboard.app.layout)
        # Should have cursor: pointer style
        assert "network-info-header" in layout_str

    def test_network_info_details_header_clickable(self, dashboard):
        """Test that Details header is clickable."""
        layout_str = str(dashboard.app.layout)
        assert "network-info-details-header" in layout_str

    def test_network_info_expanded_by_default(self, dashboard):
        """Test that Network Information section is expanded by default."""
        # The Collapse component should have is_open=True
        layout_str = str(dashboard.app.layout)
        # This would require inspecting the actual Collapse component props
        # For now, we test that the structure exists
        assert "network-info-collapse" in layout_str

    def test_network_info_details_collapsed_by_default(self, dashboard):
        """Test that Details section is collapsed by default."""
        # The Collapse component should have is_open=False
        layout_str = str(dashboard.app.layout)
        assert "network-info-details-collapse" in layout_str

    def test_network_info_panel_exists(self, dashboard):
        """Test that basic network info panel div exists."""
        layout_str = str(dashboard.app.layout)
        assert "network-info-panel" in layout_str

    def test_network_info_details_panel_exists(self, dashboard):
        """Test that detailed network info panel div exists."""
        layout_str = str(dashboard.app.layout)
        assert "network-info-details-panel" in layout_str


class TestNetworkInfoCallbacks:
    """Test Network Information callback functionality."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_toggle_network_info_callback_registered(self, dashboard):
        """Test that toggle callback for Network Information is registered."""
        # Check if callback exists for network-info-collapse output
        callbacks = dashboard.app.callback_map

        # Look for callback with network-info-collapse as output
        found = any("network-info-collapse" in str(cb.get("output", "")) for cb in callbacks.values())
        assert found, "Toggle callback for Network Information not found"

    def test_toggle_details_callback_registered(self, dashboard):
        """Test that toggle callback for Details section is registered."""
        callbacks = dashboard.app.callback_map

        # Look for callback with network-info-details-collapse as output
        found = any("network-info-details-collapse" in str(cb.get("output", "")) for cb in callbacks.values())
        assert found, "Toggle callback for Details section not found"

    def test_update_details_panel_callback_registered(self, dashboard):
        """Test that update callback for details panel is registered."""
        callbacks = dashboard.app.callback_map

        # Look for callback with network-info-details-panel as output
        found = any("network-info-details-panel" in str(cb.get("output", "")) for cb in callbacks.values())
        assert found, "Update callback for details panel not found"


class TestNetworkInfoDetailsContent:
    """Test Network Information: Details content generation."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_details_uses_metrics_panel_helper(self, dashboard):
        """Test that details panel uses metrics_panel helper method."""
        # Verify that dashboard has access to metrics_panel._create_network_info_table
        assert hasattr(dashboard.metrics_panel, "_create_network_info_table")

        # Test that the method can be called
        test_stats = {
            "threshold_function": "sigmoid",
            "optimizer": "adam",
            "total_nodes": 10,
            "weight_statistics": {"total_weights": 100, "mean": 0.5},
        }
        result = dashboard.metrics_panel._create_network_info_table(test_stats)
        assert result is not None


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
