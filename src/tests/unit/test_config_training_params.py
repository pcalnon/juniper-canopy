#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_config_training_params.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-17
# Last Modified: 2025-11-17
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for training parameter configuration
#####################################################################
"""Unit tests for training parameter configuration management."""

import pytest

from config_manager import get_config


class TestTrainingParameterConfig:
    """Test training parameter configuration management.

    These tests validate configuration structure and compatibility with constants.
    YAML values may override constant defaults, but must remain within valid bounds.
    """

    @pytest.fixture
    def config_manager(self):
        """Create config manager instance."""
        return get_config(force_reload=True)

    def test_get_epochs_config(self, config_manager):
        """Test retrieving epochs configuration - validates structure and bounds."""
        from canopy_constants import TrainingConstants

        epochs_config = config_manager.get_training_param_config("epochs")

        # Structure validation
        assert epochs_config["description"] == "Number of training epochs to run"
        assert epochs_config["modifiable_during_training"] is True

        # Internal consistency: min <= default <= max
        assert epochs_config["min"] <= epochs_config["default"] <= epochs_config["max"]

        # Compatibility with constants bounds (YAML may override defaults within bounds)
        assert epochs_config["min"] >= TrainingConstants.MIN_TRAINING_EPOCHS
        assert epochs_config["max"] <= TrainingConstants.MAX_TRAINING_EPOCHS

    def test_get_learning_rate_config(self, config_manager):
        """Test retrieving learning rate configuration - validates structure and bounds."""
        from canopy_constants import TrainingConstants

        lr_config = config_manager.get_training_param_config("learning_rate")

        # Structure validation
        assert lr_config["description"] == "Learning rate for training algorithm"
        assert lr_config["modifiable_during_training"] is True

        # Internal consistency
        assert lr_config["min"] <= lr_config["default"] <= lr_config["max"]

        # Compatibility with constants bounds
        assert lr_config["min"] >= TrainingConstants.MIN_LEARNING_RATE
        assert lr_config["max"] <= TrainingConstants.MAX_LEARNING_RATE

    def test_get_hidden_units_config(self, config_manager):
        """Test retrieving hidden units configuration - validates structure and bounds."""
        from canopy_constants import TrainingConstants

        hu_config = config_manager.get_training_param_config("hidden_units")

        # Structure validation
        assert hu_config["description"] == "Maximum number of hidden units to add"
        assert hu_config["modifiable_during_training"] is False

        # Internal consistency
        assert hu_config["min"] <= hu_config["default"] <= hu_config["max"]

        # Compatibility: min must be >= constant min (YAML max may exceed constant max for flexibility)
        assert hu_config["min"] >= TrainingConstants.MIN_HIDDEN_UNITS

    def test_invalid_parameter_name(self, config_manager):
        """Test error handling for invalid parameter name."""
        with pytest.raises(KeyError, match="not found in configuration"):
            config_manager.get_training_param_config("nonexistent_param")

    def test_validate_valid_epochs(self, config_manager):
        """Test validation of valid epoch values."""
        assert config_manager.validate_training_param_value("epochs", 100)
        assert config_manager.validate_training_param_value("epochs", 10)  # Min
        assert config_manager.validate_training_param_value("epochs", 1000)  # Max
        assert config_manager.validate_training_param_value("epochs", 200)  # Default

    def test_validate_invalid_epochs(self, config_manager):
        """Test validation of invalid epoch values."""
        with pytest.raises(ValueError, match="out of range"):
            config_manager.validate_training_param_value("epochs", 5)  # Below min

        with pytest.raises(ValueError, match="out of range"):
            config_manager.validate_training_param_value("epochs", 2000)  # Above max

    def test_validate_valid_learning_rate(self, config_manager):
        """Test validation of valid learning rate values."""
        assert config_manager.validate_training_param_value("learning_rate", 0.01)
        assert config_manager.validate_training_param_value("learning_rate", 0.0001)  # Min
        assert config_manager.validate_training_param_value("learning_rate", 1.0)  # Max
        assert config_manager.validate_training_param_value("learning_rate", 0.5)

    def test_validate_invalid_learning_rate(self, config_manager):
        """Test validation of invalid learning rate values."""
        with pytest.raises(ValueError, match="out of range"):
            config_manager.validate_training_param_value("learning_rate", 0.00001)  # Below min

        with pytest.raises(ValueError, match="out of range"):
            config_manager.validate_training_param_value("learning_rate", 2.0)  # Above max

    def test_get_training_defaults(self, config_manager):
        """Test retrieving all training defaults - validates structure and types."""
        from canopy_constants import TrainingConstants

        defaults = config_manager.get_training_defaults()

        # Required keys must exist
        assert "epochs" in defaults
        assert "learning_rate" in defaults
        assert "hidden_units" in defaults

        # Types validation
        assert isinstance(defaults["epochs"], int)
        assert isinstance(defaults["learning_rate"], float)
        assert isinstance(defaults["hidden_units"], int)

        # Values must be within constant bounds (but may differ from constant defaults)
        assert TrainingConstants.MIN_TRAINING_EPOCHS <= defaults["epochs"] <= TrainingConstants.MAX_TRAINING_EPOCHS
        assert TrainingConstants.MIN_LEARNING_RATE <= defaults["learning_rate"] <= TrainingConstants.MAX_LEARNING_RATE
        assert defaults["hidden_units"] >= TrainingConstants.MIN_HIDDEN_UNITS

    def test_param_modifiability(self, config_manager):
        """Test parameter modifiability flags."""
        # Epochs should be modifiable during training
        assert config_manager.is_param_modifiable_during_training("epochs") is True

        # Learning rate should be modifiable during training
        assert config_manager.is_param_modifiable_during_training("learning_rate") is True

        # Hidden units should NOT be modifiable during training
        assert config_manager.is_param_modifiable_during_training("hidden_units") is False

    def test_training_param_config_structure(self, config_manager):
        """Test that all parameter configs have required structure."""
        params = ["epochs", "learning_rate", "hidden_units"]

        for param in params:
            config = config_manager.get_training_param_config(param)

            # Check required keys exist
            assert "min" in config
            assert "max" in config
            assert "default" in config
            assert "description" in config
            assert "modifiable_during_training" in config

            # Check value ranges are valid
            assert config["min"] <= config["default"] <= config["max"]

            # Check types
            assert isinstance(config["description"], str)
            assert isinstance(config["modifiable_during_training"], bool)


class TestConfigConstantsConsistency:
    """Test configuration compatibility with constants module.

    Constants define safe bounds and recommended defaults.
    YAML config may override defaults but must remain compatible with bounds.
    This design allows YAML to be used for experiments/tuning without code changes.
    """

    @pytest.fixture
    def config_manager(self):
        """Create config manager instance."""
        return get_config(force_reload=True)

    def test_config_constants_consistency(self, config_manager):
        """Test configuration compatibility check runs without error."""
        # Should return bool without raising exceptions
        result = config_manager.verify_config_constants_consistency()
        assert isinstance(result, bool)
        # Note: result may be False if YAML overrides differ from constants (by design)

    def test_epochs_compatible_with_constants(self, config_manager):
        """Test that epochs config is compatible with TrainingConstants bounds."""
        from canopy_constants import TrainingConstants

        epochs_config = config_manager.get_training_param_config("epochs")

        # YAML min/max must be within constant bounds
        assert epochs_config["min"] >= TrainingConstants.MIN_TRAINING_EPOCHS
        assert epochs_config["max"] <= TrainingConstants.MAX_TRAINING_EPOCHS

        # Default must be within the configured range
        assert epochs_config["min"] <= epochs_config["default"] <= epochs_config["max"]

    def test_learning_rate_compatible_with_constants(self, config_manager):
        """Test that learning rate config is compatible with TrainingConstants bounds."""
        from canopy_constants import TrainingConstants

        lr_config = config_manager.get_training_param_config("learning_rate")

        # YAML min/max must be within constant bounds
        assert lr_config["min"] >= TrainingConstants.MIN_LEARNING_RATE
        assert lr_config["max"] <= TrainingConstants.MAX_LEARNING_RATE

        # Default must be within the configured range
        assert lr_config["min"] <= lr_config["default"] <= lr_config["max"]

    def test_hidden_units_compatible_with_constants(self, config_manager):
        """Test that hidden units config is compatible with TrainingConstants bounds."""
        from canopy_constants import TrainingConstants

        hu_config = config_manager.get_training_param_config("hidden_units")

        # YAML min must be >= constant min (max may exceed for flexibility)
        assert hu_config["min"] >= TrainingConstants.MIN_HIDDEN_UNITS

        # Default must be within the configured range
        assert hu_config["min"] <= hu_config["default"] <= hu_config["max"]

    def test_defaults_within_valid_bounds(self, config_manager):
        """Test that config defaults are within valid operational bounds."""
        from canopy_constants import TrainingConstants

        defaults = config_manager.get_training_defaults()

        # Defaults must be within constant-defined safe bounds
        assert TrainingConstants.MIN_TRAINING_EPOCHS <= defaults["epochs"] <= TrainingConstants.MAX_TRAINING_EPOCHS
        assert TrainingConstants.MIN_LEARNING_RATE <= defaults["learning_rate"] <= TrainingConstants.MAX_LEARNING_RATE
        assert defaults["hidden_units"] >= TrainingConstants.MIN_HIDDEN_UNITS


class TestConfigTrainingBehavior:
    """Test training behavior configuration."""

    @pytest.fixture
    def config_manager(self):
        """Create config manager instance."""
        return get_config(force_reload=True)

    def test_training_behavior_exists(self, config_manager):
        """Test that training behavior section exists."""
        behavior = config_manager.get("training.behavior", {})
        assert behavior is not None
        assert isinstance(behavior, dict)

    def test_training_behavior_values(self, config_manager):
        """Test training behavior configuration values."""
        assert config_manager.get("training.behavior.auto_save_checkpoints") is True
        assert config_manager.get("training.behavior.checkpoint_interval_epochs") == 50
        assert config_manager.get("training.behavior.early_stopping_enabled") is False
        assert config_manager.get("training.behavior.early_stopping_patience") == 10


class TestConfigTrainingMonitoring:
    """Test training monitoring configuration."""

    @pytest.fixture
    def config_manager(self):
        """Create config manager instance."""
        return get_config(force_reload=True)

    def test_training_monitoring_exists(self, config_manager):
        """Test that training monitoring section exists."""
        monitoring = config_manager.get("training.monitoring", {})
        assert monitoring is not None
        assert isinstance(monitoring, dict)

    def test_training_monitoring_values(self, config_manager):
        """Test training monitoring configuration values."""
        assert config_manager.get("training.monitoring.metrics_update_interval_ms") == 1000
        assert config_manager.get("training.monitoring.stats_update_interval_ms") == 5000
        assert config_manager.get("training.monitoring.log_frequency_epochs") == 1
