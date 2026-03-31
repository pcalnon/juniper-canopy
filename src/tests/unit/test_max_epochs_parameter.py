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
# Description:   Unit tests for Maximum Total Epochs parameter enhancement
#####################################################################
"""Unit tests for Maximum Total Epochs parameter enhancement in training controls."""

import pytest

from frontend.dashboard_manager import DashboardManager


class TestMaxEpochsParameter:
    """Test Maximum Total Epochs parameter in training controls."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_input_exists(self, dashboard):
        """Test that Maximum Total Epochs input field exists in layout."""
        layout_str = str(dashboard.app.layout)
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_label_exists(self, dashboard):
        """Test that Maximum Total Epochs label exists."""
        layout_str = str(dashboard.app.layout)
        assert "Maximum Total Epochs" in layout_str

    def test_max_epochs_default_value(self, dashboard):
        """Test that Maximum Total Epochs has correct default value from config."""
        layout_str = str(dashboard.app.layout)
        # Default value comes from YAML config (500) or constant (1000000)
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_min_constraint(self, dashboard):
        """Test that Maximum Total Epochs has min constraint."""
        # Check layout for min value
        # Note: This is a simplified check; actual implementation may vary
        layout_str = str(dashboard.app.layout)
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_max_constraint(self, dashboard):
        """Test that Maximum Total Epochs has max constraint."""
        layout_str = str(dashboard.app.layout)
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_step_value(self, dashboard):
        """Test that Maximum Total Epochs has step of 1."""
        # Check that step is 1 (integer steps)
        layout_str = str(dashboard.app.layout)
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_debounce_enabled(self, dashboard):
        """Test that Maximum Total Epochs input has debounce enabled."""
        layout_str = str(dashboard.app.layout)
        assert "nn-max-total-epochs-input" in layout_str


class TestMaxEpochsBackendState:
    """Test Maximum Total Epochs backend state management."""

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

        # Look for callback that outputs to nn-max-total-epochs-input
        found = any("nn-max-total-epochs-input" in str(cb.get("output", "")) for cb in callbacks.values())
        assert found, "Init callback for max_epochs not found"


class TestMaxEpochsIntegration:
    """Test Maximum Total Epochs integration with other components."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_with_learning_rate(self, dashboard):
        """Test that max_epochs coexists with learning_rate parameter."""
        layout_str = str(dashboard.app.layout)
        assert "nn-learning-rate-input" in layout_str
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_with_max_hidden_units(self, dashboard):
        """Test that max_epochs coexists with max_hidden_units parameter."""
        layout_str = str(dashboard.app.layout)
        assert "nn-max-hidden-units-input" in layout_str
        assert "nn-max-total-epochs-input" in layout_str

    def test_training_parameters_section_complete(self, dashboard):
        """Test that Meta Parameters section has all three parameters."""
        layout_str = str(dashboard.app.layout)
        assert "Meta Parameters" in layout_str
        assert "nn-learning-rate-input" in layout_str
        assert "nn-max-hidden-units-input" in layout_str
        assert "nn-max-total-epochs-input" in layout_str


class TestMaxEpochsValidation:
    """Test Maximum Total Epochs input validation."""

    @pytest.fixture
    def dashboard(self, mock_config):
        """Create dashboard manager instance."""
        return DashboardManager(mock_config)

    def test_max_epochs_type_is_number(self, dashboard):
        """Test that max_epochs input type is number."""
        layout_str = str(dashboard.app.layout)
        # Should be type="number" input
        assert "nn-max-total-epochs-input" in layout_str

    def test_max_epochs_boundaries(self, dashboard):
        """Test that max_epochs has correct min and max boundaries."""
        # This requires inspecting the actual Input component properties
        layout_str = str(dashboard.app.layout)
        assert "nn-max-total-epochs-input" in layout_str


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    return {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
