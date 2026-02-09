#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_config_expansion.py
# File Path:     src/tests/unit/
#
# Created Date:  2026-02-09
# Last Modified: 2026-02-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Tests for config_manager ${VAR:default} expansion and shell-only
#     variable exclusion.
#
#####################################################################################################################################################################################################
# Notes:
#     CE-* tests verify ${VAR:default} expansion logic in ConfigManager.
#     EO-* tests verify shell-only variable exclusion and valid CASCOR_ overrides.
#
#####################################################################################################################################################################################################
# References:
#     src/config_manager.py - _expand_env_vars, _apply_environment_overrides
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     CE-1 through CE-6, EO-1, EO-2 initial implementation
#
#####################################################################################################################################################################################################

import pytest
import yaml

from config_manager import ConfigManager


def _write_yaml_config(tmp_path, data):
    """Write a YAML dict to a temp file and return the path."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(yaml.dump(data, default_flow_style=False))
    return config_file


@pytest.mark.unit
class TestConfigExpansion:
    """Tests for ${VAR:default} expansion in ConfigManager."""

    def test_expand_env_var_with_default_unset(self, tmp_path, monkeypatch):
        """CE-1: Unset var resolves to default value."""
        monkeypatch.delenv("NONEXISTENT_VAR_CE1", raising=False)
        config_path = _write_yaml_config(tmp_path, {"test_key": "${NONEXISTENT_VAR_CE1:fallback_value}"})
        config = ConfigManager(config_path=config_path)
        assert config.config["test_key"] == "fallback_value"

    def test_expand_env_var_with_default_set(self, tmp_path, monkeypatch):
        """CE-2: Set var overrides default value."""
        monkeypatch.setenv("MY_TEST_VAR_CE2", "actual_value")
        config_path = _write_yaml_config(tmp_path, {"test_key": "${MY_TEST_VAR_CE2:fallback_value}"})
        config = ConfigManager(config_path=config_path)
        assert config.config["test_key"] == "actual_value"

    def test_expand_env_var_without_default(self, tmp_path, monkeypatch):
        """CE-3: Unset var with no default keeps literal (os.path.expandvars behaviour)."""
        monkeypatch.delenv("NONEXISTENT_VAR_CE3", raising=False)
        config_path = _write_yaml_config(tmp_path, {"test_key": "${NONEXISTENT_VAR_CE3}"})
        config = ConfigManager(config_path=config_path)
        value = str(config.config["test_key"])
        assert value == "${NONEXISTENT_VAR_CE3}" or value == ""

    def test_backend_path_no_trailing_brace(self):
        """CE-5: Real app_config.yaml backend_path has no trailing brace."""
        config = ConfigManager()
        backend_path = config.config.get("backend", {}).get("cascor_integration", {}).get("backend_path", "")
        assert not backend_path.endswith("}")
        assert "${" not in backend_path

    def test_juniper_data_url_resolved_from_config(self, tmp_path, monkeypatch):
        """CE-6: ${VAR:default} in nested config resolves correctly."""
        monkeypatch.delenv("NONEXIST_JD_URL", raising=False)
        data = {"backend": {"juniper_data": {"url": "${NONEXIST_JD_URL:http://localhost:8100}"}}}
        config_path = _write_yaml_config(tmp_path, data)
        config = ConfigManager(config_path=config_path)
        assert config.config["backend"]["juniper_data"]["url"] == "http://localhost:8100"


@pytest.mark.unit
class TestEnvironmentOverrides:
    """Tests for shell-only variable exclusion and valid CASCOR_ overrides."""

    def test_shell_only_cascor_vars_excluded(self, tmp_path, monkeypatch):
        """EO-1: Shell-only CASCOR_ vars do not pollute config."""
        monkeypatch.setenv("CASCOR_MAIN_FILE", "/some/path/main.py")
        monkeypatch.setenv("CASCOR_SOURCE_DIR", "/some/path/src")
        config_path = _write_yaml_config(tmp_path, {"placeholder": True})
        config = ConfigManager(config_path=config_path)
        assert "main" not in config.config
        assert "source" not in config.config

    def test_valid_cascor_overrides_still_applied(self, tmp_path, monkeypatch):
        """EO-2: Valid CASCOR_ overrides are applied to config."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")
        config_path = _write_yaml_config(tmp_path, {"placeholder": True})
        config = ConfigManager(config_path=config_path)
        assert config.config.get("demo", {}).get("mode") is True
