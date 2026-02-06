#!/usr/bin/env python
"""
Advanced unit tests for ConfigManager with focus on env var expansion and validation.
"""
import os

import pytest
import yaml

from config_manager import ConfigManager, get_config


class TestConfigEnvVarExpansion:
    """Test environment variable expansion in configuration."""

    def test_simple_env_var_expansion(self, tmp_path):
        """Test expansion of ${VAR} in config values."""
        # Set test environment variable
        os.environ["TEST_VAR"] = "/test/path"

        # Create config with env var
        config_data = {"paths": {"data": "${TEST_VAR}/data", "logs": "$TEST_VAR/logs"}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Load config
        config = ConfigManager(str(config_file))

        # Check expansion
        assert config.get("paths.data") == "/test/path/data"
        assert config.get("paths.logs") == "/test/path/logs"

        # Cleanup
        del os.environ["TEST_VAR"]

    def test_nested_env_var_expansion(self, tmp_path):
        """Test expansion in nested structures."""
        os.environ["HOME_DIR"] = "/home/user"
        os.environ["TEST_PORT"] = "9090"

        config_data = {
            "application": {
                "paths": {"root": "${HOME_DIR}/app", "config": "${HOME_DIR}/app/config"},
                "database": {"port": "$TEST_PORT"},
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        assert config.get("application.paths.root") == "/home/user/app"
        assert config.get("application.paths.config") == "/home/user/app/config"
        assert config.get("application.database.port") == "9090"

        del os.environ["HOME_DIR"]
        del os.environ["TEST_PORT"]

    def test_env_var_expansion_in_lists(self, tmp_path):
        """Test expansion in list values."""
        os.environ["LIB_PATH"] = "/usr/lib"

        config_data = {"search_paths": ["${LIB_PATH}/python", "/opt/lib", "$LIB_PATH/site-packages"]}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        paths = config.get("search_paths")
        assert paths[0] == "/usr/lib/python"
        assert paths[1] == "/opt/lib"
        assert paths[2] == "/usr/lib/site-packages"

        del os.environ["LIB_PATH"]


class TestConfigEnvOverrides:
    """Test environment variable overrides with collision handling."""

    def test_simple_override(self, tmp_path):
        """Test basic environment override."""
        config_data = {"server": {"port": 8050}}

        config_file = self._save_config_data_to_disk(tmp_path, config_data, "9000")
        config = ConfigManager(str(config_file))

        assert config.get("server.port") == 9000

        del os.environ["CASCOR_SERVER_PORT"]

    def test_type_conversion(self, tmp_path):
        """Test type conversion for overrides."""
        config_data = {}

        config_file = self._save_config_data_to_disk(tmp_path, config_data, "8080")
        os.environ["CASCOR_DEBUG"] = "true"
        os.environ["CASCOR_TIMEOUT"] = "30.5"
        os.environ["CASCOR_NAME"] = "test"

        config = ConfigManager(str(config_file))

        assert config.get("server.port") == 8080
        assert isinstance(config.get("server.port"), int)

        assert config.get("debug") is True
        assert isinstance(config.get("debug"), bool)

        assert config.get("timeout") == 30.5
        assert isinstance(config.get("timeout"), float)

        assert config.get("name") == "test"
        assert isinstance(config.get("name"), str)

        # Cleanup
        # sourcery skip: no-loop-in-tests
        for key in ["CASCOR_SERVER_PORT", "CASCOR_DEBUG", "CASCOR_TIMEOUT", "CASCOR_NAME"]:
            del os.environ[key]

    def test_nested_override_collision(self, tmp_path):
        """Test handling of non-dict collision in nested overrides."""
        # Not a dictionary at 'server'
        config_data = {"server": "simple_string"}

        config_file = self._save_config_data_to_disk(tmp_path, config_data, "8080")
        config = ConfigManager(str(config_file))

        # Should replace string with dict when env var creates nested path
        assert isinstance(config.get("server"), dict)
        assert config.get("server.port") == 8080

        # Verify original string value was replaced
        assert config.get("server") != "simple_string"

        del os.environ["CASCOR_SERVER_PORT"]

    def _save_config_data_to_disk(self, tmp_path, config_data, arg2):
        result = tmp_path / "test_config.yaml"
        with open(result, "w") as f:
            yaml.dump(config_data, f)
        os.environ["CASCOR_SERVER_PORT"] = arg2
        return result


class TestConfigValidation:
    """Test configuration validation."""

    def test_missing_required_keys(self, tmp_path):
        """Test validation with missing required keys - defaults are applied."""
        config_data = {}  # Empty config

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Should have defaults applied automatically
        assert config.get("application.server.host") == "localhost"
        assert config.get("application.server.port") == 8050
        assert config.get("frontend.dashboard.title") == "Juniper Canopy"

        # Verify config loaded successfully with defaults
        assert config.get("application") is not None
        assert isinstance(config.get("application.server"), dict)

    def test_invalid_type_correction(self, tmp_path, caplog):
        """Test validation corrects invalid types."""
        config_data = {"application": {"server": {"host": 12345, "port": "not_a_number"}}}  # Should be string  # Should be int

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Should be corrected to defaults
        assert isinstance(config.get("application.server.host"), str)
        assert config.get("application.server.host") == "localhost"

        assert isinstance(config.get("application.server.port"), int)
        assert config.get("application.server.port") == 8050


class TestConfigReload:
    """Test configuration reloading."""

    def test_force_reload(self, tmp_path):
        """Test force_reload parameter."""
        config_data = {"value": "first"}

        config_file = tmp_path / "test_config.yaml"
        self._save_and_reload_config_data(config_file, config_data, "first")
        # Modify config file
        config_data["value"] = "second"
        self._save_and_reload_config_data(config_file, config_data, "second")

    def _save_and_reload_config_data(self, config_file, config_data, arg2):
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Get initial config
        config1 = get_config(str(config_file), force_reload=True)
        assert config1.get("value") == arg2

    def test_reload_method(self, tmp_path):
        """Test reload() method."""
        config_data = {"counter": 1}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        assert config.get("counter") == 1

        # Modify file
        config_data["counter"] = 2
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Reload
        config.reload()
        assert config.get("counter") == 2


class TestConfigAccessors:
    """Test configuration accessor methods."""

    def test_get_with_default(self, tmp_path):
        """Test get() with default value."""
        config_data = {"exists": "value"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        assert config.get("exists") == "value"
        assert config.get("missing") is None
        assert config.get("missing", "default") == "default"

    def test_set_nested_path(self, tmp_path):
        """Test setting values with nested paths."""
        config_data = {}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        config.set("a.b.c", "value")
        assert config.get("a.b.c") == "value"

    def test_get_section(self, tmp_path):
        """Test getting entire config section."""
        config_data = {"section1": {"key1": "value1", "key2": "value2"}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        section = config.get_section("section1")
        assert section == {"key1": "value1", "key2": "value2"}

        missing = config.get_section("missing")
        assert missing == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
