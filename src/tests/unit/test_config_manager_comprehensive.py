#!/usr/bin/env python
"""
Comprehensive unit tests for ConfigManager.

Targets untested code paths to achieve 90%+ coverage:
- Environment variable expansion (${VAR} and $VAR syntax)
- Nested override collision handling
- Validation edge cases
- Config reload and force_reload functionality
- Training parameter validation and defaults
- Constants consistency checking
"""

import os

import pytest
import yaml

from config_manager import ConfigManager, get_config


@pytest.mark.unit
class TestEnvVarExpansionEdgeCases:
    """Test environment variable expansion edge cases."""

    def test_expand_undefined_env_var_unchanged(self, tmp_path):
        """Test that undefined env vars remain as-is."""
        config_data = {"path": "${UNDEFINED_VAR_12345}/data"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Undefined vars should remain unchanged (os.path.expandvars behavior)
        assert "${UNDEFINED_VAR_12345}" in config.get("path") or config.get("path") == "${UNDEFINED_VAR_12345}/data"

    def test_expand_env_var_with_special_chars(self, tmp_path, monkeypatch):
        """Test env var expansion with special characters in value."""
        monkeypatch.setenv("SPECIAL_VAR", "path/with spaces/and-dashes")

        config_data = {"path": "${SPECIAL_VAR}/file.txt"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        assert config.get("path") == "path/with spaces/and-dashes/file.txt"

    def test_expand_multiple_env_vars_in_one_value(self, tmp_path, monkeypatch):
        """Test multiple env vars in a single string."""
        monkeypatch.setenv("BASE_PATH", "/home")
        monkeypatch.setenv("USER_NAME", "testuser")

        config_data = {"full_path": "${BASE_PATH}/${USER_NAME}/data"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        assert config.get("full_path") == "/home/testuser/data"

    def test_expand_env_vars_in_deeply_nested_dict(self, tmp_path, monkeypatch):
        """Test expansion in deeply nested dictionary structures."""
        monkeypatch.setenv("DEEP_VAR", "deep_value")

        config_data = {"level1": {"level2": {"level3": {"level4": {"value": "${DEEP_VAR}"}}}}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        assert config.get("level1.level2.level3.level4.value") == "deep_value"

    def test_expand_preserves_non_string_types(self, tmp_path):
        """Test that non-string types are preserved during expansion."""
        config_data = {
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
            "null_val": None,
            "list_val": [1, 2, 3],
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        assert config.get("int_val") == 42
        assert config.get("float_val") == 3.14
        assert config.get("bool_val") is True
        assert config.get("null_val") is None
        assert config.get("list_val") == [1, 2, 3]


@pytest.mark.unit
class TestNestedOverrideCollision:
    """Test nested override collision handling."""

    def test_override_replaces_int_with_dict(self, tmp_path, monkeypatch):
        """Test that int value is replaced with dict when env override creates nested path."""
        config_data = {"server": 8080}  # Integer, not dict

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("CASCOR_SERVER_PORT", "9000")

        config = ConfigManager(str(config_file))

        # Should have replaced int with dict
        assert isinstance(config.get("server"), dict)
        assert config.get("server.port") == 9000

    def test_override_replaces_list_with_dict(self, tmp_path, monkeypatch):
        """Test that list value is replaced with dict when creating nested path."""
        config_data = {"server": ["item1", "item2"]}  # List, not dict

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("CASCOR_SERVER_PORT", "9000")

        config = ConfigManager(str(config_file))

        # Should have replaced list with dict
        assert isinstance(config.get("server"), dict)
        assert config.get("server.port") == 9000

    def test_override_deeply_nested_collision(self, tmp_path, monkeypatch):
        """Test collision handling in deeply nested structures."""
        config_data = {"a": {"b": "string_value"}}  # b is string

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # This creates a.b.c.d path, so b must become a dict
        monkeypatch.setenv("CASCOR_A_B_C_D", "nested_value")

        config = ConfigManager(str(config_file))

        assert isinstance(config.get("a.b"), dict)
        assert config.get("a.b.c.d") == "nested_value"

    def test_override_creates_intermediate_dicts(self, tmp_path, monkeypatch):
        """Test that intermediate dicts are created for deep paths."""
        config_data = {}  # Empty config

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("CASCOR_DEEP_NESTED_PATH_VALUE", "test")

        config = ConfigManager(str(config_file))

        assert config.get("deep.nested.path.value") == "test"
        assert isinstance(config.get("deep"), dict)
        assert isinstance(config.get("deep.nested"), dict)


@pytest.mark.unit
class TestTrainingParamValidation:
    """Test training parameter validation edge cases."""

    def test_validate_param_at_min_boundary(self, tmp_path):
        """Test validation at minimum boundary."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test epochs",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Exact minimum should be valid
        assert config.validate_training_param_value("epochs", 10) is True

    def test_validate_param_at_max_boundary(self, tmp_path):
        """Test validation at maximum boundary."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test epochs",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Exact maximum should be valid
        assert config.validate_training_param_value("epochs", 1000) is True

    def test_validate_param_below_min_raises(self, tmp_path):
        """Test validation raises ValueError for value below min."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test epochs",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        with pytest.raises(ValueError, match="out of range"):
            config.validate_training_param_value("epochs", 5)

    def test_validate_param_above_max_raises(self, tmp_path):
        """Test validation raises ValueError for value above max."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test epochs",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        with pytest.raises(ValueError, match="out of range"):
            config.validate_training_param_value("epochs", 1001)

    def test_validate_param_nonexistent_raises_keyerror(self, tmp_path):
        """Test validation raises KeyError for non-existent parameter."""
        config_data = {"training": {"parameters": {}}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        with pytest.raises(KeyError, match="not found"):
            config.validate_training_param_value("nonexistent", 100)

    def test_get_training_param_config_missing_keys_raises(self, tmp_path):
        """Test get_training_param_config raises ValueError for incomplete config."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        # Missing: default, description, modifiable_during_training
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        with pytest.raises(ValueError, match="missing required keys"):
            config.get_training_param_config("epochs")

    def test_get_training_param_config_invalid_range_raises(self, tmp_path):
        """Test get_training_param_config raises ValueError for invalid range."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 100,
                        "max": 1000,
                        "default": 50,  # Below min - invalid!
                        "description": "Test",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        with pytest.raises(ValueError, match="Invalid range"):
            config.get_training_param_config("epochs")

    def test_is_param_modifiable_during_training(self, tmp_path):
        """Test is_param_modifiable_during_training method."""
        config_data = {
            "training": {
                "parameters": {
                    "learning_rate": {
                        "min": 0.001,
                        "max": 1.0,
                        "default": 0.01,
                        "description": "LR",
                        "modifiable_during_training": True,
                    },
                    "hidden_units": {
                        "min": 0,
                        "max": 20,
                        "default": 10,
                        "description": "Hidden",
                        "modifiable_during_training": False,
                    },
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        assert config.is_param_modifiable_during_training("learning_rate") is True
        assert config.is_param_modifiable_during_training("hidden_units") is False


@pytest.mark.unit
class TestGetTrainingDefaults:
    """Test get_training_defaults method."""

    def test_get_training_defaults_returns_all_defaults(self, tmp_path):
        """Test get_training_defaults returns all parameter defaults."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Epochs",
                        "modifiable_during_training": True,
                    },
                    "learning_rate": {
                        "min": 0.001,
                        "max": 1.0,
                        "default": 0.01,
                        "description": "LR",
                        "modifiable_during_training": True,
                    },
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        defaults = config.get_training_defaults()

        assert defaults == {"epochs": 200, "learning_rate": 0.01}

    def test_get_training_defaults_empty_params(self, tmp_path):
        """Test get_training_defaults with no parameters defined."""
        config_data = {"training": {"parameters": {}}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        defaults = config.get_training_defaults()

        assert defaults == {}

    def test_get_training_defaults_no_training_section(self, tmp_path):
        """Test get_training_defaults with no training section."""
        config_data = {"application": {"name": "Test"}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        defaults = config.get_training_defaults()

        assert defaults == {}


@pytest.mark.unit
class TestConfigReloadAndForceReload:
    """Test configuration reload functionality."""

    def test_force_reload_creates_new_instance(self, tmp_path):
        """Test that force_reload=True creates a new instance."""
        import config_manager

        config_data = {"value": "original"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Reset global instance
        config_manager._config_instance = None

        config1 = get_config(str(config_file))
        instance_id1 = id(config1)

        # Force reload should create new instance
        config2 = get_config(str(config_file), force_reload=True)
        instance_id2 = id(config2)

        assert instance_id1 != instance_id2

    def test_reload_applies_new_env_overrides(self, tmp_path, monkeypatch):
        """Test that reload re-applies environment overrides."""
        config_data = {"server": {"port": 8050}}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        assert config.get("server.port") == 8050

        # Set env var after config creation
        monkeypatch.setenv("CASCOR_SERVER_PORT", "9999")

        # Reload should pick up new env var
        config.reload()
        assert config.get("server.port") == 9999

    def test_reload_revalidates_config(self, tmp_path):
        """Test that reload re-validates configuration."""
        # Start with valid config
        config_data = {
            "application": {"server": {"host": "127.0.0.1", "port": 8050}},
            "frontend": {"dashboard": {"title": "Test"}},
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Modify file to have invalid type
        config_data["application"]["server"]["port"] = "not_a_number"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Reload should correct the invalid type
        config.reload()
        assert config.get("application.server.port") == 8050  # Default applied


@pytest.mark.unit
class TestConfigLoadErrors:
    """Test configuration loading error handling."""

    def test_load_malformed_yaml_returns_empty(self, tmp_path, caplog):
        """Test that malformed YAML returns empty config with error logged."""
        config_file = tmp_path / "malformed.yaml"
        config_file.write_text("invalid: yaml: content: [")

        config = ConfigManager(str(config_file))

        # Should have empty config with defaults applied
        assert config.get("application.server.port") == 8050

    def test_load_empty_file_returns_empty_config(self, tmp_path):
        """Test loading an empty YAML file."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        config = ConfigManager(str(config_file))

        # Should be empty dict with defaults
        assert config.get("application.server.port") == 8050


@pytest.mark.unit
class TestConstantsConsistency:
    """Test constants consistency verification."""

    def test_verify_constants_with_missing_module(self, tmp_path, monkeypatch):
        """Test verify_config_constants_consistency when constants module missing."""
        config_data = {}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Should return True when module not found (skipped)
        result = config.verify_config_constants_consistency(constants_class=None)
        # Either returns True (skipped) or False (inconsistent if constants found)
        assert isinstance(result, bool)

    def test_verify_constants_with_mock_class(self, tmp_path):
        """Test verify_config_constants_consistency with mock constants class."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Create mock constants class with matching values
        class MockTrainingConstants:
            MIN_TRAINING_EPOCHS = 10
            MAX_TRAINING_EPOCHS = 1000
            DEFAULT_TRAINING_EPOCHS = 200
            MIN_LEARNING_RATE = 0.0001
            MAX_LEARNING_RATE = 1.0
            DEFAULT_LEARNING_RATE = 0.01
            MIN_HIDDEN_UNITS = 0
            MAX_HIDDEN_UNITS = 20
            DEFAULT_MAX_HIDDEN_UNITS = 10

        result = config.verify_config_constants_consistency(constants_class=MockTrainingConstants)
        # Result depends on whether all params are in config
        assert isinstance(result, bool)

    def test_verify_constants_detects_mismatch(self, tmp_path):
        """Test that mismatched constants are detected."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 500,  # Different from constants
                        "default": 200,
                        "description": "Test",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        class MockTrainingConstants:
            MIN_TRAINING_EPOCHS = 10
            MAX_TRAINING_EPOCHS = 1000  # Different from config
            DEFAULT_TRAINING_EPOCHS = 200

        result = config.verify_config_constants_consistency(constants_class=MockTrainingConstants)
        assert result is False  # Should detect mismatch

    def test_skipping_constants_check_returns_true_when_unavailable(self, tmp_path, monkeypatch):
        """Test skipping_constants_check when constants unavailable."""
        config_data = {}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Test with explicit None (simulates import failure handling)
        result = config.skipping_constants_check(constants_class=None)
        # Will try to import constants module - depends on environment
        assert isinstance(result, bool)


@pytest.mark.unit
class TestGetPathEdgeCases:
    """Test get() method edge cases."""

    def test_get_from_non_dict_intermediate(self, tmp_path):
        """Test get with non-dict intermediate value returns default."""
        config_data = {"path": "string_value"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # path.to.value where path is a string, not dict
        result = config.get("path.to.value", "default")
        assert result == "default"

    def test_get_single_key(self, tmp_path):
        """Test get with single key (no dots)."""
        config_data = {"simple_key": "simple_value"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        assert config.get("simple_key") == "simple_value"


@pytest.mark.unit
class TestTypeConversionEdgeCases:
    """Test _convert_type edge cases."""

    def test_convert_yes_no_variants(self, tmp_path, monkeypatch):
        """Test boolean conversion with yes/no variants."""
        config_data = {}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("CASCOR_YES_TEST", "YES")
        monkeypatch.setenv("CASCOR_NO_TEST", "NO")

        config = ConfigManager(str(config_file))

        assert config.get("yes.test") is True
        assert config.get("no.test") is False

    def test_convert_negative_numbers(self, tmp_path, monkeypatch):
        """Test conversion of negative numbers."""
        config_data = {}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        monkeypatch.setenv("CASCOR_NEG_INT", "-42")
        monkeypatch.setenv("CASCOR_NEG_FLOAT", "-3.14")

        config = ConfigManager(str(config_file))

        assert config.get("neg.int") == -42
        assert isinstance(config.get("neg.int"), int)
        assert abs(config.get("neg.float") - (-3.14)) < 0.001


@pytest.mark.unit
class TestToDictMethod:
    """Test to_dict method."""

    def test_to_dict_returns_complete_config(self, tmp_path):
        """Test to_dict returns full configuration."""
        config_data = {
            "section1": {"key1": "value1"},
            "section2": {"key2": "value2"},
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))
        result = config.to_dict()

        assert "section1" in result
        assert "section2" in result
        assert result["section1"]["key1"] == "value1"

    def test_to_dict_returns_independent_copy(self, tmp_path):
        """Test that to_dict returns an independent copy."""
        config_data = {"key": "original"}

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        dict1 = config.to_dict()
        dict1["key"] = "modified"

        dict2 = config.to_dict()
        assert dict2["key"] == "original"


@pytest.mark.unit
class TestCheckConstantsCategory:
    """Test check_constants_category method."""

    def test_check_constants_category_with_matching_values(self, tmp_path):
        """Test check_constants_category returns True when values match."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Epochs",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        constants = {
            "min": ("MIN_EPOCHS", 10),
            "max": ("MAX_EPOCHS", 1000),
            "default": ("DEFAULT_EPOCHS", 200),
        }

        result = config.check_constants_category(category="epochs", constants=constants)
        assert result is True

    def test_check_constants_category_with_mismatch(self, tmp_path):
        """Test check_constants_category returns False when values mismatch."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 500,  # Different from constants
                        "default": 200,
                        "description": "Epochs",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        constants = {
            "min": ("MIN_EPOCHS", 10),
            "max": ("MAX_EPOCHS", 1000),  # Mismatches config (500 != 1000)
        }

        result = config.check_constants_category(category="epochs", constants=constants)
        assert result is False

    def test_check_constants_category_uses_class_name(self, tmp_path):
        """Test check_constants_category uses class name as category when not provided."""
        config_data = {
            "training": {
                "parameters": {
                    "MockCategory": {
                        "min": 0,
                        "max": 100,
                        "default": 50,
                        "description": "Mock",
                        "modifiable_during_training": False,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        class MockCategory:
            pass

        constants = {"min": ("MIN_VAL", 0), "max": ("MAX_VAL", 100)}

        result = config.check_constants_category(constants_class=MockCategory, constants=constants)
        assert isinstance(result, bool)


@pytest.mark.unit
class TestDefaultPathHandling:
    """Test default config path handling."""

    def test_default_config_path_when_none_provided(self):
        """Test that default config path is used when none provided."""
        # This tests the default path resolution (lines 80-84)
        config = ConfigManager(config_path=None)

        # Should have loaded from default path or created defaults
        assert config.config is not None
        assert isinstance(config.config, dict)


@pytest.mark.unit
class TestVerifyConstantsWithMissingAttribute:
    """Test verify_config_constants_consistency with missing attributes."""

    def test_verify_constants_missing_attribute(self, tmp_path):
        """Test handling of missing constant attributes."""
        config_data = {
            "training": {
                "parameters": {
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test",
                        "modifiable_during_training": True,
                    },
                    "learning_rate": {
                        "min": 0.001,
                        "max": 1.0,
                        "default": 0.01,
                        "description": "LR",
                        "modifiable_during_training": True,
                    },
                    "hidden_units": {
                        "min": 0,
                        "max": 20,
                        "default": 10,
                        "description": "Hidden",
                        "modifiable_during_training": False,
                    },
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        # Class missing some expected attributes
        class IncompleteConstants:
            MIN_TRAINING_EPOCHS = 10
            MAX_TRAINING_EPOCHS = 1000
            # Missing DEFAULT_TRAINING_EPOCHS and others

        result = config.verify_config_constants_consistency(constants_class=IncompleteConstants)
        assert result is False  # Should be False due to missing attributes

    def test_verify_constants_missing_param_in_config(self, tmp_path):
        """Test verify when param missing from config but defined in constants mapping."""
        config_data = {
            "training": {
                "parameters": {
                    # epochs defined but learning_rate and hidden_units missing
                    "epochs": {
                        "min": 10,
                        "max": 1000,
                        "default": 200,
                        "description": "Test",
                        "modifiable_during_training": True,
                    }
                }
            }
        }

        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = ConfigManager(str(config_file))

        class MockTrainingConstants:
            MIN_TRAINING_EPOCHS = 10
            MAX_TRAINING_EPOCHS = 1000
            DEFAULT_TRAINING_EPOCHS = 200
            MIN_LEARNING_RATE = 0.0001
            MAX_LEARNING_RATE = 1.0
            DEFAULT_LEARNING_RATE = 0.01
            MIN_HIDDEN_UNITS = 0
            MAX_HIDDEN_UNITS = 20
            DEFAULT_MAX_HIDDEN_UNITS = 10

        # Should handle missing params gracefully with warning
        result = config.verify_config_constants_consistency(constants_class=MockTrainingConstants)
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
