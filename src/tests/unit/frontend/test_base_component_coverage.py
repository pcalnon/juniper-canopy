#!/usr/bin/env python
"""
Unit tests for frontend/base_component.py to improve coverage to 90%+.

Tests cover:
- Constructor variations (different config values, missing keys)
- Abstract method enforcement
- Logger initialization
- Initialize/cleanup lifecycle
- Config update functionality
"""

import logging
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from frontend.base_component import BaseComponent


class ConcreteComponent(BaseComponent):
    """Concrete implementation for testing abstract base class."""

    def get_layout(self) -> Any:
        return {"type": "div", "id": self.component_id}

    def register_callbacks(self, app):
        pass


class TestBaseComponentConstructor:
    """Test constructor variations."""

    def test_constructor_with_minimal_config(self):
        """Test constructor with empty config dict."""
        component = ConcreteComponent(config={}, component_id="test-minimal")

        assert component.config == {}
        assert component.component_id == "test-minimal"
        assert component.is_initialized is False

    def test_constructor_with_full_config(self):
        """Test constructor with populated config dict."""
        config = {
            "enabled": True,
            "buffer_size": 1000,
            "update_interval": 500,
            "nested": {"key1": "value1", "key2": 42},
        }
        component = ConcreteComponent(config=config, component_id="test-full")

        assert component.config == config
        assert component.config["enabled"] is True
        assert component.config["nested"]["key2"] == 42

    def test_constructor_with_special_characters_in_id(self):
        """Test constructor with special characters in component_id."""
        component = ConcreteComponent(config={}, component_id="test-component_v2.1")

        assert component.component_id == "test-component_v2.1"

    def test_constructor_with_empty_string_id(self):
        """Test constructor with empty string as component_id."""
        component = ConcreteComponent(config={}, component_id="")

        assert component.component_id == ""


class TestBaseComponentLogger:
    """Test logger initialization."""

    def test_logger_initialized_with_correct_name(self):
        """Test logger is created with correct naming pattern."""
        component = ConcreteComponent(config={}, component_id="test-logger")

        expected_name = "frontend.base_component.ConcreteComponent"
        assert component.logger.name == expected_name

    def test_logger_is_logging_instance(self):
        """Test logger is a valid logging.Logger instance."""
        component = ConcreteComponent(config={}, component_id="test-logger-type")

        assert isinstance(component.logger, logging.Logger)

    def test_different_subclasses_have_different_logger_names(self):
        """Test different subclasses get unique logger names."""

        class AnotherComponent(BaseComponent):
            def get_layout(self):
                return None

            def register_callbacks(self, app):
                pass

        comp1 = ConcreteComponent(config={}, component_id="comp1")
        comp2 = AnotherComponent(config={}, component_id="comp2")

        assert "ConcreteComponent" in comp1.logger.name
        assert "AnotherComponent" in comp2.logger.name
        assert comp1.logger.name != comp2.logger.name


class TestAbstractMethodEnforcement:
    """Test abstract method enforcement."""

    def test_cannot_instantiate_base_class_directly(self):
        """Test BaseComponent cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseComponent(config={}, component_id="test")

        assert "abstract" in str(exc_info.value).lower()

    def test_missing_get_layout_raises_error(self):
        """Test missing get_layout implementation raises TypeError."""

        with pytest.raises(TypeError):

            class IncompleteComponent1(BaseComponent):
                def register_callbacks(self, app):
                    pass

            IncompleteComponent1(config={}, component_id="test")

    def test_missing_register_callbacks_raises_error(self):
        """Test missing register_callbacks implementation raises TypeError."""

        with pytest.raises(TypeError):

            class IncompleteComponent2(BaseComponent):
                def get_layout(self):
                    return None

            IncompleteComponent2(config={}, component_id="test")


class TestInitializeMethod:
    """Test initialize method."""

    def test_initialize_sets_flag(self):
        """Test initialize sets is_initialized flag."""
        component = ConcreteComponent(config={}, component_id="test-init")

        assert component.is_initialized is False
        component.initialize()
        assert component.is_initialized is True

    def test_initialize_logs_message(self):
        """Test initialize logs info message."""
        component = ConcreteComponent(config={}, component_id="test-init-log")

        with patch.object(component.logger, "info") as mock_info:
            component.initialize()
            mock_info.assert_called_once()
            assert "test-init-log" in str(mock_info.call_args)

    def test_initialize_only_runs_once(self):
        """Test initialize only executes once (idempotent)."""
        component = ConcreteComponent(config={}, component_id="test-init-once")

        with patch.object(component.logger, "info") as mock_info:
            component.initialize()
            component.initialize()
            component.initialize()
            mock_info.assert_called_once()


class TestCleanupMethod:
    """Test cleanup method."""

    def test_cleanup_logs_message(self):
        """Test cleanup logs info message."""
        component = ConcreteComponent(config={}, component_id="test-cleanup")

        with patch.object(component.logger, "info") as mock_info:
            component.cleanup()
            mock_info.assert_called_once()
            assert "test-cleanup" in str(mock_info.call_args)

    def test_cleanup_can_be_called_multiple_times(self):
        """Test cleanup can be called multiple times without error."""
        component = ConcreteComponent(config={}, component_id="test-cleanup-multi")

        component.cleanup()
        component.cleanup()
        component.cleanup()


class TestGetComponentId:
    """Test get_component_id method."""

    def test_returns_component_id(self):
        """Test get_component_id returns the component_id."""
        component = ConcreteComponent(config={}, component_id="my-unique-id")

        assert component.get_component_id() == "my-unique-id"

    def test_returns_same_id_as_attribute(self):
        """Test get_component_id returns same value as direct attribute access."""
        component = ConcreteComponent(config={}, component_id="consistency-test")

        assert component.get_component_id() == component.component_id


class TestUpdateConfig:
    """Test update_config method."""

    def test_update_config_adds_new_keys(self):
        """Test update_config adds new keys to config."""
        component = ConcreteComponent(config={"existing": 1}, component_id="test-update")

        component.update_config({"new_key": "new_value"})

        assert component.config["existing"] == 1
        assert component.config["new_key"] == "new_value"

    def test_update_config_overwrites_existing_keys(self):
        """Test update_config overwrites existing keys."""
        component = ConcreteComponent(config={"key1": "old_value", "key2": 100}, component_id="test-overwrite")

        component.update_config({"key1": "new_value"})

        assert component.config["key1"] == "new_value"
        assert component.config["key2"] == 100

    def test_update_config_logs_debug_message(self):
        """Test update_config logs debug message."""
        component = ConcreteComponent(config={}, component_id="test-update-log")

        with patch.object(component.logger, "debug") as mock_debug:
            component.update_config({"key": "value"})
            mock_debug.assert_called_once()
            assert "test-update-log" in str(mock_debug.call_args)

    def test_update_config_with_empty_dict(self):
        """Test update_config with empty dict doesn't change config."""
        original_config = {"key1": "value1", "key2": 42}
        component = ConcreteComponent(config=original_config.copy(), component_id="test-empty")

        component.update_config({})

        assert component.config == original_config

    def test_update_config_with_nested_dict(self):
        """Test update_config handles nested dictionaries."""
        component = ConcreteComponent(config={"nested": {"a": 1, "b": 2}}, component_id="test-nested")

        component.update_config({"nested": {"a": 10, "c": 3}})

        assert component.config["nested"] == {"a": 10, "c": 3}


class TestComponentLifecycle:
    """Test full component lifecycle scenarios."""

    def test_full_lifecycle(self):
        """Test complete component lifecycle: create, init, use, cleanup."""
        config = {"setting": True}
        component = ConcreteComponent(config=config, component_id="lifecycle-test")

        assert not component.is_initialized

        component.initialize()
        assert component.is_initialized

        layout = component.get_layout()
        assert layout is not None

        component.update_config({"setting": False})
        assert component.config["setting"] is False

        component.cleanup()

    def test_cleanup_before_initialize(self):
        """Test cleanup can be called before initialize without error."""
        component = ConcreteComponent(config={}, component_id="cleanup-first")

        component.cleanup()
        assert not component.is_initialized
