#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     callback_context.py
# Author:        Paul Calnon
# Version:       0.0.2
#
# Date:          2025-12-12
# Last Modified: 2026-04-05
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:   Callback Context Adapter for Juniper Canopy Dash Application
#
#####################################################################################################################################################################################################
# Notes:
#
#     Callback Context Adapter for Dash Applications
#
#     Provides a testable abstraction layer over dash.callback_context.triggered_id.
#     In production, reads from the real Dash callback context.
#     In tests, allows injection of a fake trigger value.
#
#     This design supports:
#     - Multiple environments (production, test, headless)
#     - Easy mocking for unit tests
#     - Future extensibility for different callback context providers
#
#     Thread safety: _test_mode and _test_trigger use contextvars.ContextVar
#     so concurrent callbacks in different threads/async tasks are isolated.
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
import contextvars
import threading
from typing import Optional

# Context-local test state for thread/async safety
_test_mode_var: contextvars.ContextVar[bool] = contextvars.ContextVar("_test_mode_var", default=False)
_test_trigger_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("_test_trigger_var", default=None)


class CallbackContextAdapter:
    """
    Adapter for accessing Dash callback context in a testable way.

    Usage in production (inside a Dash callback):
        adapter = CallbackContextAdapter()
        trigger = adapter.get_triggered_id()

    Usage in tests:
        adapter = CallbackContextAdapter()
        adapter.set_test_trigger("start-button")
        trigger = adapter.get_triggered_id()  # Returns "start-button"
        adapter.clear_test_trigger()
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_triggered_id(self) -> Optional[str]:
        """
        Get the triggered component ID.

        Returns:
            The ID of the component that triggered the callback,
            or None if no trigger is available.
        """
        if _test_mode_var.get():
            return _test_trigger_var.get()

        try:
            import dash

            triggered_id: str | None = dash.callback_context.triggered_id
            return triggered_id
        except (RuntimeError, AttributeError, ImportError, LookupError):
            return None
        except Exception as exc:
            # Dash raises MissingCallbackContextException when accessed outside
            # a callback — allow it through, but re-raise truly unexpected errors.
            if "Callback" not in type(exc).__name__ and "Dash" not in type(exc).__name__:
                raise
            return None

    def set_test_trigger(self, trigger_id: Optional[str]) -> None:
        """
        Set a test trigger value for unit testing.

        Args:
            trigger_id: The component ID to simulate as the trigger
        """
        _test_mode_var.set(True)
        _test_trigger_var.set(trigger_id)

    def clear_test_trigger(self) -> None:
        """Clear the test trigger and return to production mode."""
        _test_mode_var.set(False)
        _test_trigger_var.set(None)

    def is_test_mode(self) -> bool:
        """Check if adapter is in test mode."""
        return _test_mode_var.get()

    def get_triggered_prop_ids(self) -> dict:
        """
        Get the full triggered property IDs dict.

        Returns:
            Dict of triggered property IDs, or empty dict if unavailable.
        """
        if _test_mode_var.get():
            trigger = _test_trigger_var.get()
            return {f"{trigger}.n_clicks": 1} if trigger else {}
        try:
            import dash

            return dict(dash.callback_context.triggered_prop_ids)
        except Exception:
            return {}

    def get_inputs_list(self) -> list:
        """
        Get the callback inputs list.

        Returns:
            List of callback inputs, or empty list if unavailable.
        """
        if _test_mode_var.get():
            return []

        try:
            import dash

            return list(dash.callback_context.inputs_list)
        except Exception:
            return []

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None


def get_callback_context() -> CallbackContextAdapter:
    """Get the global callback context adapter instance."""
    return CallbackContextAdapter()
