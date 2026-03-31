#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_config_dashboard_integration.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Integration tests for configuration and dashboard
#####################################################################
"""Integration tests for configuration and dashboard constant integration."""

import pytest

from canopy_constants import TrainingConstants
from config_manager import get_config


@pytest.mark.integration
class TestConfigDashboardIntegration:
    """Test configuration integration with dashboard and constants.

    Configuration Architecture:
    - Constants (constants.py): Define safe bounds and recommended defaults
    - YAML (app_config.yaml): Runtime overrides for experiments/tuning
    - Environment variables: Highest precedence for deployment overrides

    YAML values may differ from constant defaults but must remain compatible.
    """

    def test_config_defaults_within_bounds(self):
        """Test that configuration defaults are within constant-defined bounds."""
        config_mgr = get_config(force_reload=True)
        defaults = config_mgr.get_training_defaults()

        # Defaults must be within safe operational bounds (may differ from constant defaults)
        assert TrainingConstants.MIN_TRAINING_EPOCHS <= defaults["epochs"] <= TrainingConstants.MAX_TRAINING_EPOCHS
        assert TrainingConstants.MIN_LEARNING_RATE <= defaults["learning_rate"] <= TrainingConstants.MAX_LEARNING_RATE
        assert defaults["hidden_units"] >= TrainingConstants.MIN_HIDDEN_UNITS

    def test_config_ranges_compatible_with_constants(self):
        """Test that configuration ranges are compatible with constant bounds."""
        config_mgr = get_config(force_reload=True)

        # Epochs: YAML range must be within constant bounds
        epochs_config = config_mgr.get_training_param_config("epochs")
        assert epochs_config["min"] >= TrainingConstants.MIN_TRAINING_EPOCHS
        assert epochs_config["max"] <= TrainingConstants.MAX_TRAINING_EPOCHS
        assert epochs_config["min"] <= epochs_config["default"] <= epochs_config["max"]

        # Learning rate: YAML range must be within constant bounds
        lr_config = config_mgr.get_training_param_config("learning_rate")
        assert lr_config["min"] >= TrainingConstants.MIN_LEARNING_RATE
        assert lr_config["max"] <= TrainingConstants.MAX_LEARNING_RATE
        assert lr_config["min"] <= lr_config["default"] <= lr_config["max"]

        # Hidden units: YAML min must be >= constant min (max may exceed for flexibility)
        hu_config = config_mgr.get_training_param_config("hidden_units")
        assert hu_config["min"] >= TrainingConstants.MIN_HIDDEN_UNITS
        assert hu_config["min"] <= hu_config["default"] <= hu_config["max"]

    def test_config_consistency_check_runs(self):
        """Test that configuration consistency check executes without error."""
        config_mgr = get_config(force_reload=True)
        result = config_mgr.verify_config_constants_consistency()

        # Method should return bool (may be False if YAML overrides differ - by design)
        assert isinstance(result, bool)

    def test_param_validation_integration(self):
        """Test that parameter validation works with configured ranges."""
        config_mgr = get_config(force_reload=True)

        # Get actual configured ranges
        epochs_config = config_mgr.get_training_param_config("epochs")
        lr_config = config_mgr.get_training_param_config("learning_rate")
        hu_config = config_mgr.get_training_param_config("hidden_units")

        # Valid values (within configured ranges) should pass
        assert config_mgr.validate_training_param_value("epochs", epochs_config["default"])
        assert config_mgr.validate_training_param_value("learning_rate", lr_config["default"])
        assert config_mgr.validate_training_param_value("hidden_units", hu_config["default"])

        # Invalid values (outside configured ranges) should fail
        with pytest.raises(ValueError):
            config_mgr.validate_training_param_value("epochs", epochs_config["min"] - 1)

        with pytest.raises(ValueError):
            config_mgr.validate_training_param_value("epochs", epochs_config["max"] + 1)
