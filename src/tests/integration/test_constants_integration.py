#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_constants_integration.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Integration tests for constants usage across components
#####################################################################

import pytest

from canopy_constants import DashboardConstants, TrainingConstants
from frontend.dashboard_manager import DashboardManager


@pytest.mark.integration
class TestConstantsIntegration:
    """Test that constants are properly integrated across components."""

    def test_dashboard_uses_constants(self, test_config):
        """Test that dashboard manager uses constants correctly."""
        dashboard = DashboardManager(test_config)

        # Verify the dashboard was created successfully
        assert dashboard.app is not None
        assert hasattr(dashboard, "logger")

        # Smoke test - dashboard should be initialized successfully with constants
        # The actual values are tested in the unit tests

    def test_training_constants_consistency(self):
        """Test that training constants are internally consistent."""
        # Verify defaults fall within valid ranges
        assert TrainingConstants.MIN_TRAINING_EPOCHS <= TrainingConstants.DEFAULT_TRAINING_EPOCHS <= TrainingConstants.MAX_TRAINING_EPOCHS

        assert TrainingConstants.MIN_LEARNING_RATE <= TrainingConstants.DEFAULT_LEARNING_RATE <= TrainingConstants.MAX_LEARNING_RATE

        assert TrainingConstants.MIN_HIDDEN_UNITS <= TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS <= TrainingConstants.MAX_HIDDEN_UNITS

    def test_dashboard_constants_consistency(self):
        """Test that dashboard constants are internally consistent."""
        # Update intervals should be positive and fast < slow
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS > 0
        assert DashboardConstants.SLOW_UPDATE_INTERVAL_MS > 0
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS < DashboardConstants.SLOW_UPDATE_INTERVAL_MS

        # Data limits should be positive and metrics < data points
        assert DashboardConstants.MAX_METRICS_HISTORY > 0
        assert DashboardConstants.MAX_DATA_POINTS > 0
        assert DashboardConstants.MAX_METRICS_HISTORY < DashboardConstants.MAX_DATA_POINTS

        # Timeout should be positive
        assert DashboardConstants.API_TIMEOUT_SECONDS > 0
