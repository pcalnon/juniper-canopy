"""
Unit Tests for ConfigManager

Tests configuration loading, nested access, environment overrides,
and the singleton pattern.
"""

import pytest
import yaml

# Import the module under test
from config_manager import ConfigManager, get_config


@pytest.mark.unit
class TestConfigManager:
    """Test suite for ConfigManager class."""

    def test_initialization_with_valid_config(self, mock_config_file):
        """Test ConfigManager initialization with valid config file."""
        config = ConfigManager(config_path=str(mock_config_file))

        assert config.config is not None  # trunk-ignore(bandit/B101)
        assert isinstance(config.config, dict)  # trunk-ignore(bandit/B101)
        assert config.config_path == mock_config_file  # trunk-ignore(bandit/B101)

    def test_initialization_without_config_file(self, tmp_path):
        """Test ConfigManager initialization with non-existent file."""
        non_existent = tmp_path / "does_not_exist.yaml"
        config = ConfigManager(config_path=str(non_existent))

        # Should create config with defaults without raising error
        assert config.config is not None  # trunk-ignore(bandit/B101)
        assert isinstance(config.config, dict)  # trunk-ignore(bandit/B101)
        # Defaults should be applied
        assert config.get("application.server.port") == 8050  # trunk-ignore(bandit/B101)
        assert config.get("application.server.host") == "localhost"  # trunk-ignore(bandit/B101)

    def test_get_nested_key_access(self, test_config_dict, tmp_path):
        """Test nested configuration key access using dot notation."""
        # Create temporary config file
        config_file = tmp_path / "test_nested.yaml"
        with open(config_file, "w") as f:
            yaml.dump(test_config_dict, f)

        config = ConfigManager(config_path=str(config_file))

        # Test nested access
        assert config.get("application.name") == "Juniper Canopy Test"  # trunk-ignore(bandit/B101)
        assert config.get("server.port") == 8050  # trunk-ignore(bandit/B101)
        assert config.get("logging.console.level") == "DEBUG"  # trunk-ignore(bandit/B101)

    def test_get_with_default_value(self, mock_config_file):
        """Test get() method with default values."""
        config = ConfigManager(config_path=str(mock_config_file))

        # Non-existent key should return default
        assert config.get("nonexistent.key", "default_value") == "default_value"  # trunk-ignore(bandit/B101)
        assert config.get("another.missing.key", 42) == 42  # trunk-ignore(bandit/B101)
        assert config.get("missing", None) is None  # trunk-ignore(bandit/B101)

    def test_get_without_default_returns_none(self, mock_config_file):
        """Test get() without default returns None for missing keys."""
        config = ConfigManager(config_path=str(mock_config_file))

        result = config.get("nonexistent.key")
        assert result is None  # trunk-ignore(bandit/B101)

    def test_set_configuration_value(self, mock_config_file):
        """Test setting configuration values programmatically."""
        config = ConfigManager(config_path=str(mock_config_file))

        # Set new value
        config.set("new.nested.value", "test_value")

        # Verify it was set
        assert config.get("new.nested.value") == "test_value"  # trunk-ignore(bandit/B101)

    def test_set_overwrites_existing_value(self, mock_config_file):
        """Test that set() overwrites existing values."""
        config = ConfigManager(config_path=str(mock_config_file))

        original_port = config.get("server.port")
        config.set("server.port", 9999)

        assert config.get("server.port") == 9999  # trunk-ignore(bandit/B101)
        assert config.get("server.port") != original_port  # trunk-ignore(bandit/B101)

    def test_get_section(self, test_config_dict, tmp_path):
        """Test retrieving entire configuration section."""
        config_file = tmp_path / "test_section.yaml"
        with open(config_file, "w") as f:
            yaml.dump(test_config_dict, f)

        config = ConfigManager(config_path=str(config_file))

        # Get entire section
        server_section = config.get_section("server")

        assert isinstance(server_section, dict)  # trunk-ignore(bandit/B101)
        assert "host" in server_section  # trunk-ignore(bandit/B101)
        assert "port" in server_section  # trunk-ignore(bandit/B101)
        assert server_section["host"] == "127.0.0.1"  # trunk-ignore(bandit/B101)
        assert server_section["port"] == 8050  # trunk-ignore(bandit/B101)

    def test_get_section_nonexistent_returns_empty_dict(self, mock_config_file):
        """Test get_section() with non-existent section."""
        config = ConfigManager(config_path=str(mock_config_file))

        result = config.get_section("nonexistent_section")
        assert result == {}  # trunk-ignore(bandit/B101)

    def test_to_dict_returns_copy(self, mock_config_file):
        """Test to_dict() returns a copy of the configuration."""
        config = ConfigManager(config_path=str(mock_config_file))

        config_dict = config.to_dict()

        # Modify the returned dict
        config_dict["test_key"] = "test_value"

        # Original config should be unchanged
        assert "test_key" not in config.config  # trunk-ignore(bandit/B101)

    def test_environment_variable_override_simple(self, mock_config_file, monkeypatch):
        """Test environment variable overrides with simple keys."""
        # Set environment variable
        monkeypatch.setenv("CASCOR_SERVER_PORT", "9999")

        config = ConfigManager(config_path=str(mock_config_file))

        # Environment variable should override config file
        assert config.get("server.port") == 9999  # trunk-ignore(bandit/B101)

    def test_environment_variable_override_nested(self, mock_config_file, monkeypatch):
        """Test environment variable overrides with nested keys."""
        # Set nested environment variable
        monkeypatch.setenv("CASCOR_LOGGING_CONSOLE_LEVEL", "ERROR")

        config = ConfigManager(config_path=str(mock_config_file))

        # Environment variable should override
        assert config.get("logging.console.level") == "ERROR"  # trunk-ignore(bandit/B101)

    def test_environment_variable_creates_new_keys(self, mock_config_file, monkeypatch):
        """Test that environment variables can create new configuration keys."""
        monkeypatch.setenv("CASCOR_NEW_SETTING_VALUE", "new_value")

        config = ConfigManager(config_path=str(mock_config_file))

        assert config.get("new.setting.value") == "new_value"  # trunk-ignore(bandit/B101)

    def test_type_conversion_boolean_true(self, mock_config_file, monkeypatch):
        """Test boolean type conversion for true values."""
        test_cases = ["true", "True", "TRUE", "yes", "Yes", "1"]

        for i, value in enumerate(test_cases):  # sourcery skip: no-loop-in-tests
            monkeypatch.setenv(f"CASCOR_TEST_BOOL_{i}", value)

        config = ConfigManager(config_path=str(mock_config_file))

        for i in range(len(test_cases)):  # sourcery skip: no-loop-in-tests
            assert config.get(f"test.bool.{i}") is True  # trunk-ignore(bandit/B101)

    def test_type_conversion_boolean_false(self, mock_config_file, monkeypatch):
        """Test boolean type conversion for false values."""
        test_cases = ["false", "False", "FALSE", "no", "No", "0"]

        for i, value in enumerate(test_cases):  # sourcery skip: no-loop-in-tests
            monkeypatch.setenv(f"CASCOR_TEST_FALSE_{i}", value)

        config = ConfigManager(config_path=str(mock_config_file))

        for i in range(len(test_cases)):  # sourcery skip: no-loop-in-tests
            assert config.get(f"test.false.{i}") is False  # trunk-ignore(bandit/B101)

    def test_type_conversion_integer(self, mock_config_file, monkeypatch):
        """Test integer type conversion."""
        monkeypatch.setenv("CASCOR_TEST_INT", "12345")

        config = ConfigManager(config_path=str(mock_config_file))

        value = config.get("test.int")
        assert isinstance(value, int)  # trunk-ignore(bandit/B101)
        assert value == 12345  # trunk-ignore(bandit/B101)

    def test_type_conversion_float(self, mock_config_file, monkeypatch):
        """Test float type conversion."""
        monkeypatch.setenv("CASCOR_TEST_FLOAT", "3.14159")

        config = ConfigManager(config_path=str(mock_config_file))

        value = config.get("test.float")
        assert isinstance(value, float)  # trunk-ignore(bandit/B101)
        assert abs(value - 3.14159) < 0.00001  # trunk-ignore(bandit/B101)

    def test_type_conversion_string_fallback(self, mock_config_file, monkeypatch):
        """Test that non-numeric strings remain as strings."""
        monkeypatch.setenv("CASCOR_TEST_STRING", "hello_world")

        config = ConfigManager(config_path=str(mock_config_file))

        value = config.get("test.string")
        assert isinstance(value, str)  # trunk-ignore(bandit/B101)
        assert value == "hello_world"  # trunk-ignore(bandit/B101)

    def test_reload_configuration(self, tmp_path):
        """Test reloading configuration from file."""
        # Create initial config
        config_file = tmp_path / "reload_test.yaml"
        initial_config = {"test_value": "initial"}

        with open(config_file, "w") as f:
            yaml.dump(initial_config, f)

        config = ConfigManager(config_path=str(config_file))
        assert config.get("test_value") == "initial"  # trunk-ignore(bandit/B101)

        # Modify config file
        modified_config = {"test_value": "modified"}
        with open(config_file, "w") as f:
            yaml.dump(modified_config, f)

        # Reload
        config.reload()
        assert config.get("test_value") == "modified"  # trunk-ignore(bandit/B101)


@pytest.mark.unit
class TestConfigManagerSingleton:
    """Test suite for global configuration singleton."""

    def test_get_config_returns_instance(self, mock_config_file):
        """Test get_config() returns ConfigManager instance."""
        config = get_config(config_path=str(mock_config_file))

        assert isinstance(config, ConfigManager)  # trunk-ignore(bandit/B101)

    def test_get_config_singleton_behavior(self, mock_config_file):
        """Test that get_config() returns the same instance."""
        # Reset global instance
        import config_manager

        config_manager._config_instance = None

        config1 = get_config(config_path=str(mock_config_file))
        config2 = get_config()

        # Should be the same instance
        assert config1 is config2  # trunk-ignore(bandit/B101)

    def test_singleton_persists_modifications(self, mock_config_file):
        """Test that modifications persist across get_config() calls."""
        # Reset global instance
        import config_manager

        config_manager._config_instance = None

        config1 = get_config(config_path=str(mock_config_file))
        config1.set("test.singleton", "test_value")

        config2 = get_config()

        # Modification should be visible in second call
        assert config2.get("test.singleton") == "test_value"  # trunk-ignore(bandit/B101)


# Fixtures for this test module
@pytest.fixture
def test_config_dict():
    """Provide test configuration dictionary."""
    return {
        "application": {"name": "Juniper Canopy Test", "version": "1.0.0", "environment": "testing"},
        "server": {"host": "127.0.0.1", "port": 8050},
        "logging": {"console": {"enabled": True, "level": "DEBUG"}, "file": {"enabled": False}},
    }
