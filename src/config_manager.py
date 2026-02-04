#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     config_manager.py
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-13
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This file contains the configuration management system for the Juniper
#       prototype Frontend, including loading and validating configuration
#       settings for the monitoring and diagnostics of the Cascade Correlation
#       Neural Network.
#
#####################################################################################################################################################################################################
# Notes:
#
# Configuration Management System
#
# Provides flexible YAML-based configuration loading with environment variable
# substitution and profile support.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import contextlib
import logging
import os

# import traceback
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict, Union

import yaml


class TrainingParamConfig(TypedDict):
    """Type definition for training parameter config."""

    min: Union[int, float]
    max: Union[int, float]
    default: Union[int, float]
    description: str
    modifiable_during_training: bool


class ConfigManager:
    """
    Central configuration manager for Juniper Canopy application.

    Supports:
    - YAML configuration files
    - Environment variable substitution
    - Configuration profiles (development, testing, production)
    - Nested configuration access
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to YAML configuration file. If None, uses default.
        """
        self.logger = logging.getLogger(__name__)

        if config_path is None:
            # Default to conf/app_config.yaml relative to project root
            # project_root = Path(__file__).parent.parent.parent
            project_root = Path(__file__).parent.parent
            config_path = project_root / "conf" / "app_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self._expand_env_vars()
        self._apply_environment_overrides()
        self._validate_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            self.logger.warning(f"Configuration file not found: {self.config_path}")
            return {}

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
                self.logger.info(f"Configuration loaded from {self.config_path}")
                return config or {}
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            return {}

    def _expand_env_vars(self):
        """
        Recursively expand environment variables in configuration values.

        Supports ${VAR} and $VAR syntax in string values.
        """

        def expand_value(value):
            """Recursively expand environment variables."""
            if isinstance(value, str):
                return os.path.expandvars(value)
            elif isinstance(value, dict):
                return {k: expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_value(item) for item in value]
            return value

        self.config = expand_value(self.config)
        self.logger.debug("Environment variables expanded in configuration")

    def _apply_environment_overrides(self):
        """
        Apply environment variable overrides to configuration.

        Environment variables in format: CASCOR_SECTION_KEY=value
        Example: CASCOR_SERVER_PORT=8080
        """
        prefix = "CASCOR_"

        for env_var, value in os.environ.items():
            if env_var.startswith(prefix):
                # Remove prefix and convert to lowercase
                key_path = env_var[len(prefix) :].lower().split("_")

                # Navigate to nested dictionary and set value
                current = self.config
                for key in key_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    elif not isinstance(current[key], dict):
                        # Handle collision: non-dict exists where dict is needed
                        self.logger.warning(f"Environment override collision at {'.'.join(key_path[:-1])}: " f"replacing {type(current[key]).__name__} with dict")
                        current[key] = {}
                    current = current[key]

                # Convert value to appropriate type
                current[key_path[-1]] = self._convert_type(value)
                self.logger.debug(f"Applied environment override: {env_var}={value}")

    def _convert_type(self, value: str) -> Any:
        """
        Convert string value to appropriate Python type.

        Args:
            value: String value to convert

        Returns:
            Converted value
        """
        # Try boolean
        if value.lower() in {"true", "yes", "1"}:
            return True
        if value.lower() in {"false", "no", "0"}:
            return False

        # Try integer
        with contextlib.suppress(ValueError):
            return int(value)
        # Try float
        with contextlib.suppress(ValueError):
            return float(value)
        # Return as string
        return value

    def _validate_config(self):
        """
        Validate configuration against required keys and types.

        Logs warnings for missing/invalid values and applies sensible defaults.
        """
        required_keys = {
            "application.server.host": (str, "localhost"),
            "application.server.port": (int, 8050),
            "frontend.dashboard.title": (str, "Juniper Canopy"),
        }

        for key_path, (expected_type, default_value) in required_keys.items():
            value = self.get(key_path)

            if value is None:
                self.logger.warning(f"Missing required config key {key_path!r}, using default: {default_value}")
                self.set(key_path, default_value)
            elif not isinstance(value, expected_type):
                self.logger.warning(f"Invalid type for config key {key_path!r}: " f"expected {expected_type.__name__}, got {type(value).__name__}, " f"using default: {default_value}")
                self.set(key_path, default_value)

        self.logger.debug("Configuration validation complete")

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation path.

        Args:
            key_path: Dot-separated path (e.g., 'server.host')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key_path.split(".")
        current = self.config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def set(self, key_path: str, value: Any):
        """
        Set configuration value by dot-notation path.

        Args:
            key_path: Dot-separated path (e.g., 'server.host')
            value: Value to set
        """
        keys = key_path.split(".")
        current = self.config

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.

        Args:
            section: Section name

        Returns:
            Section dictionary or empty dict if not found
        """
        return self.config.get(section, {})

    def reload(self):
        """Reload configuration from file."""
        self.config = self._load_config()
        self._expand_env_vars()
        self._apply_environment_overrides()
        self._validate_config()
        self.logger.info("Configuration reloaded")

    def get_training_param_config(self, param_name: str) -> TrainingParamConfig:
        """
        Get training parameter configuration with validation.

        Args:
            param_name: Name of parameter (e.g., 'epochs', 'learning_rate')

        Returns:
            TrainingParamConfig dictionary with min/max/default/etc.

        Raises:
            KeyError: If parameter not found in config
            ValueError: If parameter config is invalid
        """
        try:
            param_config = self.config["training"]["parameters"][param_name]

            # Validate structure
            required_keys = {"min", "max", "default", "description", "modifiable_during_training"}
            if any(key not in param_config for key in required_keys):
                raise ValueError(f"Invalid parameter config for {param_name}: missing required keys")

            # Validate value ranges
            if not (param_config["min"] <= param_config["default"] <= param_config["max"]):
                raise ValueError(f"Invalid range for {param_name}: " f"min={param_config['min']}, default={param_config['default']}, max={param_config['max']}")

            return param_config

        except KeyError as e:
            raise KeyError(f"Training parameter {param_name!r} not found in configuration") from e

    def validate_training_param_value(self, param_name: str, value: Union[int, float]) -> bool:
        """
        Validate a training parameter value against configured constraints.

        Args:
            param_name: Name of parameter
            value: Value to validate

        Returns:
            True if valid

        Raises:
            ValueError: If value is out of range
        """
        param_config = self.get_training_param_config(param_name)

        if not (param_config["min"] <= value <= param_config["max"]):
            raise ValueError(f"{param_name} value {value} is out of range " f"[{param_config['min']}, {param_config['max']}]")

        return True

    def get_training_defaults(self) -> Dict[str, Union[int, float]]:
        """
        Get all training parameter default values.

        Returns:
            Dictionary mapping parameter names to default values
        """
        params = self.config.get("training", {}).get("parameters", {})
        return {param_name: param_config["default"] for param_name, param_config in params.items()}

    def is_param_modifiable_during_training(self, param_name: str) -> bool:
        """
        Check if a parameter can be modified during training.

        Args:
            param_name: Name of parameter

        Returns:
            True if modifiable during training
        """
        param_config = self.get_training_param_config(param_name)
        return param_config["modifiable_during_training"]

    def verify_config_constants_consistency(self, constants_class: object = None) -> bool:
        """
        Verify that YAML config values match constants module.

        Issues warnings if values differ but doesn't fail.
        Constants take precedence over YAML for application defaults.

        Returns:
            True if consistent, False if discrepancies found
        """
        if constants_class is None:
            try:
                from canopy_constants import TrainingConstants

                constants_class = TrainingConstants
            except ImportError:
                self.logger.warning("Constants module not found, skipping consistency check")
                return True

        if self.skipping_constants_check(constants_class=constants_class):
            return True

        consistency_mapping = {
            "epochs": {
                "min": "MIN_TRAINING_EPOCHS",
                "max": "MAX_TRAINING_EPOCHS",
                "default": "DEFAULT_TRAINING_EPOCHS",
            },
            "learning_rate": {
                "min": "MIN_LEARNING_RATE",
                "max": "MAX_LEARNING_RATE",
                "default": "DEFAULT_LEARNING_RATE",
            },
            "hidden_units": {
                "min": "MIN_HIDDEN_UNITS",
                "max": "MAX_HIDDEN_UNITS",
                "default": "DEFAULT_MAX_HIDDEN_UNITS",
            },
        }

        consistent = True
        for param_name, const_attrs in consistency_mapping.items():
            try:
                config = self.get_training_param_config(param_name)
            except KeyError:
                self.logger.warning(f"Training parameter {param_name!r} not found in configuration, skipping")
                continue

            for key, const_attr in const_attrs.items():
                try:
                    const_value = getattr(constants_class, const_attr)
                    config_value = config.get(key)
                    if config_value != const_value:
                        self.logger.warning(f"Config {param_name}.{key} ({config_value}) != " f"{constants_class.__name__}.{const_attr} ({const_value})")
                        consistent = False
                except AttributeError:
                    self.logger.warning(f"Constant {const_attr} not found in {constants_class.__name__}")
                    consistent = False

        return consistent

    def skipping_constants_check(self, constants_class: object = None) -> bool:
        try:
            if constants_class is None:
                from canopy_constants import TrainingConstants

                constants_class = TrainingConstants
            return False
        except ImportError:
            self.logger.warning("Constants module not found, skipping consistency check")
            return True

    def check_constants_category(self, constants_class: object = None, constants: dict = None, category: str = None) -> bool:
        if category is None and constants_class is not None:
            category = constants_class.__name__
        consistent = True

        config_from_method = self.get_training_param_config(category)
        config_from_self = self.config.get(category, {})
        config = config_from_method or config_from_self if config_from_method != config_from_self else config_from_method

        try:
            for key, value_tup in constants.items():
                const_name = value_tup[0]
                const_value = value_tup[1]
                if config.get(key) != const_value:
                    self.logger.warning(f"Config {category}.{key} ({config.get(key)}) != {const_name} ({const_value})")
                    consistent = False
                    break

        except ValueError as e:
            self.logger.error(f"Unable to perform Constants check for {category} Class {constants_class}: " f"Config obj {config.key} ({config.get(key)}), {const_name} ({const_value}) Raised: {e}")
            raise ValueError("Unable to perform Constants check") from e
        return consistent

    def to_dict(self) -> Dict[str, Any]:
        """
        Get complete configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        return self.config.copy()


# Global configuration instance
_config_instance: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None, force_reload: bool = False) -> ConfigManager:
    """
    Get global configuration manager instance.

    Args:
        config_path: Optional path to configuration file
        force_reload: If True, force reload even if instance exists (useful for tests)

    Returns:
        ConfigManager instance
    """
    global _config_instance

    if _config_instance is None or force_reload:
        _config_instance = ConfigManager(config_path)

    return _config_instance
