"""
Tests for two-mode backend activation in main.py — Phase 4 decoupling.

Verifies priority order:
1. CASCOR_DEMO_MODE=1 → Demo mode (highest priority)
2. CASCOR_SERVICE_URL set → Service mode via CascorServiceAdapter
3. Neither → Demo mode (default)

Note: conftest.py sets CASCOR_DEMO_MODE=1 at module level, so we must
use monkeypatch to override environment variables for each test.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest

try:
    import juniper_cascor_client  # noqa: F401

    _HAS_CASCOR_CLIENT = True
except ImportError:
    _HAS_CASCOR_CLIENT = False


def _reload_main_module(monkeypatch, env_vars: dict):
    """
    Helper to reload main.py with specific environment variables.

    Since main.py executes activation logic at module load time,
    we must reload the module to test different configurations.
    """
    # Set environment variables
    for key, value in env_vars.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    # Remove cached module to force re-import
    for mod_name in list(sys.modules.keys()):
        if mod_name == "main" or mod_name.startswith("main."):
            del sys.modules[mod_name]

    import main

    importlib.reload(main)
    return main


class TestDemoModePriority:
    """Demo mode takes highest priority when CASCOR_DEMO_MODE=1."""

    def test_demo_mode_when_explicitly_set(self, monkeypatch):
        """CASCOR_DEMO_MODE=1 should activate demo mode."""
        main = _reload_main_module(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "1",
                "CASCOR_SERVICE_URL": None,
            },
        )

        assert main.demo_mode_active is True
        assert main.backend is None

    def test_demo_mode_overrides_service_url(self, monkeypatch):
        """Demo mode takes priority even when CASCOR_SERVICE_URL is set."""
        main = _reload_main_module(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "1",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
            },
        )

        assert main.demo_mode_active is True
        assert main.backend is None

    def test_demo_mode_with_true_string(self, monkeypatch):
        """Various truthy string values for CASCOR_DEMO_MODE."""
        for value in ("1", "true", "True", "yes", "Yes"):
            main = _reload_main_module(
                monkeypatch,
                {
                    "CASCOR_DEMO_MODE": value,
                    "CASCOR_SERVICE_URL": None,
                },
            )
            assert main.demo_mode_active is True, f"Failed for CASCOR_DEMO_MODE={value}"


@pytest.mark.skipif(not _HAS_CASCOR_CLIENT, reason="juniper-cascor-client not installed")
class TestServiceMode:
    """Service mode activates when CASCOR_SERVICE_URL is set (and no demo mode)."""

    def test_service_mode_creates_adapter(self, monkeypatch):
        """Setting CASCOR_SERVICE_URL should create a CascorServiceAdapter."""
        main = _reload_main_module(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
            },
        )

        from backend.cascor_service_adapter import CascorServiceAdapter

        assert main.demo_mode_active is False
        assert main.backend is not None
        assert isinstance(main.backend, CascorServiceAdapter)

    def test_service_mode_with_api_key(self, monkeypatch):
        """API key should be passed to the adapter."""
        main = _reload_main_module(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
                "CASCOR_SERVICE_API_KEY": "test-key-123",
            },
        )

        assert main.backend is not None
        assert main.backend._api_key == "test-key-123"


class TestDefaultFallback:
    """Without any env vars, falls back to demo mode."""

    def test_no_env_vars_defaults_to_demo(self, monkeypatch):
        """No CASCOR_SERVICE_URL and CASCOR_DEMO_MODE=0 → default to demo mode."""
        main = _reload_main_module(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": None,
            },
        )

        assert main.demo_mode_active is True
        assert main.backend is None
