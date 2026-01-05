#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_callback_context_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-12-13
# Last Modified: 2025-12-13
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Comprehensive coverage tests for CallbackContextAdapter singleton
#####################################################################
"""Comprehensive coverage tests for CallbackContextAdapter (target: ~100%)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.callback_context import CallbackContextAdapter, get_callback_context  # noqa: E402


class TestSingletonBehavior:
    """Test singleton pattern implementation."""

    def test_same_instance_on_multiple_calls(self):
        """Multiple instantiations should return the same instance."""
        adapter1 = CallbackContextAdapter()
        adapter2 = CallbackContextAdapter()
        assert adapter1 is adapter2

    def test_reset_instance_creates_new_instance(self):
        """reset_instance should allow creation of a new instance."""
        adapter1 = CallbackContextAdapter()
        CallbackContextAdapter.reset_instance()
        adapter2 = CallbackContextAdapter()
        assert adapter1 is not adapter2

    def test_get_callback_context_returns_singleton(self):
        """get_callback_context should return the singleton instance."""
        adapter = CallbackContextAdapter()
        context = get_callback_context()
        assert adapter is context

    def test_new_instance_has_default_state(self):
        """New instance should have test_trigger=None and test_mode=False."""
        CallbackContextAdapter.reset_instance()
        adapter = CallbackContextAdapter()
        assert adapter._test_trigger is None
        assert adapter._test_mode is False

    def test_singleton_thread_safety_lock_exists(self):
        """Singleton should have a lock for thread safety."""
        assert hasattr(CallbackContextAdapter, "_lock")
        assert CallbackContextAdapter._lock is not None


class TestTestModeTriggerId:
    """Test get_triggered_id in test mode."""

    def test_set_test_trigger_enables_test_mode(self):
        """set_test_trigger should enable test mode."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button-id")
        assert adapter.is_test_mode() is True

    def test_get_triggered_id_returns_set_trigger(self):
        """get_triggered_id should return the trigger set via set_test_trigger."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("start-button")
        assert adapter.get_triggered_id() == "start-button"

    def test_get_triggered_id_returns_none_trigger(self):
        """get_triggered_id should return None if None was set as trigger."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger(None)
        assert adapter.get_triggered_id() is None
        assert adapter.is_test_mode() is True

    def test_clear_test_trigger_disables_test_mode(self):
        """clear_test_trigger should disable test mode."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button-id")
        adapter.clear_test_trigger()
        assert adapter.is_test_mode() is False

    def test_clear_test_trigger_clears_trigger_value(self):
        """clear_test_trigger should set trigger to None."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button-id")
        adapter.clear_test_trigger()
        assert adapter._test_trigger is None

    def test_multiple_set_trigger_updates_value(self):
        """Setting trigger multiple times should update the value."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("first-button")
        assert adapter.get_triggered_id() == "first-button"
        adapter.set_test_trigger("second-button")
        assert adapter.get_triggered_id() == "second-button"


class TestProductionModeTriggererId:
    """Test get_triggered_id in production mode (no test trigger set)."""

    def test_production_mode_no_dash_returns_none(self):
        """In production mode without Dash context, should return None."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        with patch.dict("sys.modules", {"dash": None}):
            result = adapter.get_triggered_id()
        assert result is None

    def test_production_mode_dash_import_error_returns_none(self):
        """If dash import fails, should return None."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        with patch("builtins.__import__", side_effect=ImportError("No dash")):
            result = adapter.get_triggered_id()
        assert result is None

    def test_production_mode_dash_callback_context_error_returns_none(self):
        """If accessing callback_context raises exception, return None."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        # Patch dash.callback_context.triggered_id to raise an exception
        with patch("dash.callback_context") as mock_ctx:
            type(mock_ctx).triggered_id = PropertyMock(side_effect=RuntimeError("No callback context"))
            result = adapter.get_triggered_id()
        assert result is None


class TestGetTriggeredPropIds:
    """Test get_triggered_prop_ids method."""

    def test_test_mode_with_trigger_returns_prop_dict(self):
        """In test mode with trigger, should return proper dict."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("my-button")
        result = adapter.get_triggered_prop_ids()
        assert result == {"my-button.n_clicks": 1}

    def test_test_mode_with_none_trigger_returns_empty_dict(self):
        """In test mode with None trigger, should return empty dict."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger(None)
        result = adapter.get_triggered_prop_ids()
        assert result == {}

    def test_production_mode_no_dash_returns_empty_dict(self):
        """In production mode without Dash, should return empty dict."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        with patch.dict("sys.modules", {"dash": None}):
            result = adapter.get_triggered_prop_ids()
        assert result == {}

    def test_production_mode_dash_exception_returns_empty_dict(self):
        """If dash raises exception, should return empty dict."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        # Patch dash.callback_context.triggered_prop_ids to raise an exception
        with patch("dash.callback_context") as mock_ctx:
            type(mock_ctx).triggered_prop_ids = PropertyMock(side_effect=RuntimeError("No context"))
            result = adapter.get_triggered_prop_ids()
        assert result == {}


class TestGetInputsList:
    """Test get_inputs_list method."""

    def test_test_mode_returns_empty_list(self):
        """In test mode, should return empty list."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button")
        result = adapter.get_inputs_list()
        assert result == []

    def test_production_mode_no_dash_returns_empty_list(self):
        """In production mode without Dash, should return empty list."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        with patch.dict("sys.modules", {"dash": None}):
            result = adapter.get_inputs_list()
        assert result == []

    def test_production_mode_dash_exception_returns_empty_list(self):
        """If dash raises exception, should return empty list."""
        adapter = CallbackContextAdapter()
        adapter.clear_test_trigger()
        # Patch dash.callback_context.inputs_list to raise an exception
        with patch("dash.callback_context") as mock_ctx:
            type(mock_ctx).inputs_list = PropertyMock(side_effect=RuntimeError("No context"))
            result = adapter.get_inputs_list()
        assert result == []


class TestIsTestMode:
    """Test is_test_mode method."""

    def test_is_test_mode_false_by_default(self):
        """is_test_mode should be False by default."""
        CallbackContextAdapter.reset_instance()
        adapter = CallbackContextAdapter()
        assert adapter.is_test_mode() is False

    def test_is_test_mode_true_after_set_trigger(self):
        """is_test_mode should be True after set_test_trigger."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button")
        assert adapter.is_test_mode() is True

    def test_is_test_mode_false_after_clear_trigger(self):
        """is_test_mode should be False after clear_test_trigger."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button")
        adapter.clear_test_trigger()
        assert adapter.is_test_mode() is False


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_set_trigger_with_empty_string(self):
        """set_test_trigger with empty string should work."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("")
        assert adapter.get_triggered_id() == ""
        assert adapter.is_test_mode() is True

    def test_get_triggered_prop_ids_with_empty_string(self):
        """get_triggered_prop_ids with empty string trigger should return empty dict (falsy check)."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("")
        result = adapter.get_triggered_prop_ids()
        assert result == {}

    def test_set_trigger_with_special_characters(self):
        """set_test_trigger should handle special characters."""
        adapter = CallbackContextAdapter()
        special_id = "button-with-special_chars.123"
        adapter.set_test_trigger(special_id)
        assert adapter.get_triggered_id() == special_id

    def test_reset_instance_while_in_test_mode(self):
        """reset_instance should work even when in test mode."""
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("button")
        CallbackContextAdapter.reset_instance()
        new_adapter = CallbackContextAdapter()
        assert new_adapter.is_test_mode() is False
        assert new_adapter._test_trigger is None

    def test_singleton_persists_test_state(self):
        """Singleton should persist test state across calls."""
        adapter1 = CallbackContextAdapter()
        adapter1.set_test_trigger("button")
        adapter2 = CallbackContextAdapter()
        assert adapter2.is_test_mode() is True
        assert adapter2.get_triggered_id() == "button"
