#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_constants.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for constants module
#####################################################################

import pytest  # noqa: F401 - needed for test fixtures

from canopy_constants import DashboardConstants, ServerConstants, TrainingConstants


class TestTrainingConstants:
    """Test training constants validity and relationships."""

    def test_epoch_constraints(self):
        """Test epoch min/max/default relationships."""
        assert TrainingConstants.MIN_TRAINING_EPOCHS < TrainingConstants.DEFAULT_TRAINING_EPOCHS
        assert TrainingConstants.DEFAULT_TRAINING_EPOCHS < TrainingConstants.MAX_TRAINING_EPOCHS
        assert TrainingConstants.MIN_TRAINING_EPOCHS == 10
        assert TrainingConstants.MAX_TRAINING_EPOCHS == 1000
        assert TrainingConstants.DEFAULT_TRAINING_EPOCHS == 300

    def test_learning_rate_constraints(self):
        """Test learning rate min/max/default relationships."""
        assert TrainingConstants.MIN_LEARNING_RATE < TrainingConstants.DEFAULT_LEARNING_RATE
        assert TrainingConstants.DEFAULT_LEARNING_RATE < TrainingConstants.MAX_LEARNING_RATE
        assert TrainingConstants.MIN_LEARNING_RATE == 0.0001
        assert TrainingConstants.MAX_LEARNING_RATE == 1.0
        assert TrainingConstants.DEFAULT_LEARNING_RATE == 0.01

    def test_hidden_units_constraints(self):
        """Test hidden units min/max/default relationships."""
        assert TrainingConstants.MIN_HIDDEN_UNITS <= TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS
        assert TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS <= TrainingConstants.MAX_HIDDEN_UNITS
        assert TrainingConstants.MIN_HIDDEN_UNITS == 0
        assert TrainingConstants.MAX_HIDDEN_UNITS == 20
        assert TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS == 20

    def test_constants_are_integers(self):
        """Test that integer constants are actually integers."""
        assert isinstance(TrainingConstants.MIN_TRAINING_EPOCHS, int)
        assert isinstance(TrainingConstants.MAX_TRAINING_EPOCHS, int)
        assert isinstance(TrainingConstants.DEFAULT_TRAINING_EPOCHS, int)
        assert isinstance(TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS, int)
        assert isinstance(TrainingConstants.MIN_HIDDEN_UNITS, int)
        assert isinstance(TrainingConstants.MAX_HIDDEN_UNITS, int)

    def test_constants_are_floats(self):
        """Test that float constants are actually floats."""
        assert isinstance(TrainingConstants.DEFAULT_LEARNING_RATE, float)
        assert isinstance(TrainingConstants.MIN_LEARNING_RATE, float)
        assert isinstance(TrainingConstants.MAX_LEARNING_RATE, float)

    def test_positive_values(self):
        """Test that all training constants are positive."""
        assert TrainingConstants.MIN_TRAINING_EPOCHS > 0
        assert TrainingConstants.MAX_TRAINING_EPOCHS > 0
        assert TrainingConstants.DEFAULT_TRAINING_EPOCHS > 0
        assert TrainingConstants.DEFAULT_LEARNING_RATE > 0
        assert TrainingConstants.MIN_LEARNING_RATE > 0
        assert TrainingConstants.MAX_LEARNING_RATE > 0
        assert TrainingConstants.MIN_HIDDEN_UNITS >= 0
        assert TrainingConstants.MAX_HIDDEN_UNITS > 0
        assert TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS > 0


class TestDashboardConstants:
    """Test dashboard constants."""

    def test_update_intervals(self):
        """Test update interval values and relationships."""
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS == 1000
        assert DashboardConstants.SLOW_UPDATE_INTERVAL_MS == 5000
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS < DashboardConstants.SLOW_UPDATE_INTERVAL_MS

    def test_api_timeout(self):
        """Test API timeout value."""
        assert DashboardConstants.API_TIMEOUT_SECONDS == 2
        assert isinstance(DashboardConstants.API_TIMEOUT_SECONDS, int)
        assert DashboardConstants.API_TIMEOUT_SECONDS > 0

    def test_data_limits(self):
        """Test data limit values and relationships."""
        assert DashboardConstants.MAX_METRICS_HISTORY == 100
        assert DashboardConstants.MAX_DATA_POINTS == 10000
        assert DashboardConstants.MAX_METRICS_HISTORY < DashboardConstants.MAX_DATA_POINTS
        assert isinstance(DashboardConstants.MAX_METRICS_HISTORY, int)
        assert isinstance(DashboardConstants.MAX_DATA_POINTS, int)

    def test_positive_values(self):
        """Test that all dashboard constants are positive."""
        assert DashboardConstants.FAST_UPDATE_INTERVAL_MS > 0
        assert DashboardConstants.SLOW_UPDATE_INTERVAL_MS > 0
        assert DashboardConstants.API_TIMEOUT_SECONDS > 0
        assert DashboardConstants.MAX_METRICS_HISTORY > 0
        assert DashboardConstants.MAX_DATA_POINTS > 0


class TestServerConstants:
    """Test server configuration constants."""

    def test_default_host(self):
        """Test default host value."""
        assert ServerConstants.DEFAULT_HOST == "127.0.0.1"
        assert isinstance(ServerConstants.DEFAULT_HOST, str)

    def test_default_port(self):
        """Test default port value."""
        assert ServerConstants.DEFAULT_PORT == 8050
        assert isinstance(ServerConstants.DEFAULT_PORT, int)
        assert 1024 <= ServerConstants.DEFAULT_PORT <= 65535

    def test_websocket_paths(self):
        """Test WebSocket path values."""
        assert ServerConstants.WS_TRAINING_PATH == "/ws/training"
        assert ServerConstants.WS_CONTROL_PATH == "/ws/control"
        assert isinstance(ServerConstants.WS_TRAINING_PATH, str)
        assert isinstance(ServerConstants.WS_CONTROL_PATH, str)
        assert ServerConstants.WS_TRAINING_PATH.startswith("/")
        assert ServerConstants.WS_CONTROL_PATH.startswith("/")
        assert ServerConstants.WS_TRAINING_PATH != ServerConstants.WS_CONTROL_PATH


class TestModuleLevelConvenience:
    """Test module-level convenience imports."""

    def test_convenience_imports(self):
        """Test that convenience imports match class constants."""
        from canopy_constants import DEFAULT_TRAINING_EPOCHS, MAX_TRAINING_EPOCHS, MIN_TRAINING_EPOCHS

        assert MIN_TRAINING_EPOCHS == TrainingConstants.MIN_TRAINING_EPOCHS
        assert MAX_TRAINING_EPOCHS == TrainingConstants.MAX_TRAINING_EPOCHS
        assert DEFAULT_TRAINING_EPOCHS == TrainingConstants.DEFAULT_TRAINING_EPOCHS
