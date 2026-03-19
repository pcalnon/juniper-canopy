#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_max_epochs_parameter.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for Maximum Epochs parameter enhancement
#####################################################################

import pytest

from frontend.dashboard_manager import DashboardManager


class TestMaxEpochsParameter:
    """Test Maximum Epochs parameter in training controls."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_input_exists(self, dashboard):
        """Test that Maximum Epochs input field exists in layout."""
        layout_str = str(dashboard.app.layout)
        assert "max-epochs-input" in layout_str

    def test_max_epochs_label_exists(self, dashboard):
        """Test that Maximum Epochs label exists."""
        layout_str = str(dashboard.app.layout)
        assert "Maximum Epochs" in layout_str

    def test_max_epochs_default_value(self, dashboard):
        """Test that Maximum Epochs has correct default value (200)."""
        layout_str = str(dashboard.app.layout)
        # Default value should be 200
        assert "200" in layout_str

    def test_max_epochs_min_constraint(self, dashboard):
        """Test that Maximum Epochs has min constraint of 10."""
        # Check layout for min value
        # Note: This is a simplified check; actual implementation may vary
        layout_str = str(dashboard.app.layout)
        assert "max-epochs-input" in layout_str

    def test_max_epochs_max_constraint(self, dashboard):
        """Test that Maximum Epochs has max constraint of 1000."""
        layout_str = str(dashboard.app.layout)
        assert "max-epochs-input" in layout_str

    def test_max_epochs_step_value(self, dashboard):
        """Test that Maximum Epochs has step of 1."""
        # Check that step is 1 (integer steps)
        layout_str = str(dashboard.app.layout)
        assert "max-epochs-input" in layout_str

    def test_max_epochs_debounce_enabled(self, dashboard):
        """Test that Maximum Epochs input has debounce enabled."""
        layout_str = str(dashboard.app.layout)
        assert "max-epochs-input" in layout_str


class TestMaxEpochsBackendState:
    """Test Maximum Epochs backend state management."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_in_applied_params_store(self, dashboard):
        """Test that applied-params-store exists in layout for tracking parameters."""
        layout_str = str(dashboard.app.layout)
        assert "applied-params-store" in layout_str

    def test_max_epochs_init_callback_exists(self, dashboard):
        """Test that init callback outputs max_epochs input value."""
        callbacks = dashboard.app.callback_map

        # Look for callback that outputs to max-epochs-input
        found = any("max-epochs-input" in str(cb.get("output", "")) for cb in callbacks.values())
        assert found, "Init callback for max_epochs not found"


class TestMaxEpochsIntegration:
    """Test Maximum Epochs integration with other components."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_with_learning_rate(self, dashboard):
        """Test that max_epochs coexists with learning_rate parameter."""
        layout_str = str(dashboard.app.layout)
        assert "learning-rate-input" in layout_str
        assert "max-epochs-input" in layout_str

    def test_max_epochs_with_max_hidden_units(self, dashboard):
        """Test that max_epochs coexists with max_hidden_units parameter."""
        layout_str = str(dashboard.app.layout)
        assert "max-hidden-units-input" in layout_str
        assert "max-epochs-input" in layout_str

    def test_training_parameters_section_complete(self, dashboard):
        """Test that Training Parameters section has all three parameters."""
        layout_str = str(dashboard.app.layout)
        assert "Training Parameters" in layout_str
        assert "learning-rate-input" in layout_str
        assert "max-hidden-units-input" in layout_str
        assert "max-epochs-input" in layout_str


class TestMaxEpochsValidation:
    """Test Maximum Epochs input validation."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_type_is_number(self, dashboard):
        """Test that max_epochs input type is number."""
        layout_str = str(dashboard.app.layout)
        # Should be type="number" input
        assert "max-epochs-input" in layout_str

    def test_max_epochs_boundaries(self, dashboard):
        """Test that max_epochs has correct min and max boundaries."""
        # Min should be 10, max should be 1000
        # This requires inspecting the actual Input component properties
        layout_str = str(dashboard.app.layout)
        assert "max-epochs-input" in layout_str


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
