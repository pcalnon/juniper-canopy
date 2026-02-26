"""
Tests for two-mode backend activation via create_backend() factory.

Verifies priority order:
1. CASCOR_DEMO_MODE=1 → DemoBackend (highest priority)
2. CASCOR_SERVICE_URL set → ServiceBackend via CascorServiceAdapter
3. Neither → DemoBackend (default)

Note: conftest.py sets CASCOR_DEMO_MODE=1 at module level, so we must
use monkeypatch to override environment variables for each test.
"""

from unittest.mock import MagicMock, patch

import pytest

try:
    import juniper_cascor_client  # noqa: F401

    _HAS_CASCOR_CLIENT = True
except ImportError:
    _HAS_CASCOR_CLIENT = False


def _create_backend_with_env(monkeypatch, env_vars: dict):
    """
    Helper to call create_backend() with specific environment variables.

    Patches get_demo_mode to avoid connecting to JuniperData.
    """
    for key, value in env_vars.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    from backend import create_backend

    return create_backend()


class TestDemoModePriority:
    """Demo mode takes highest priority when CASCOR_DEMO_MODE=1."""

    def test_demo_mode_when_explicitly_set(self, monkeypatch):
        """CASCOR_DEMO_MODE=1 should create a DemoBackend."""
        from backend.demo_backend import DemoBackend

        backend = _create_backend_with_env(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "1",
                "CASCOR_SERVICE_URL": None,
            },
        )

        assert backend.backend_type == "demo"
        assert isinstance(backend, DemoBackend)

    def test_demo_mode_overrides_service_url(self, monkeypatch):
        """Demo mode takes priority even when CASCOR_SERVICE_URL is set."""
        backend = _create_backend_with_env(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "1",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
            },
        )

        assert backend.backend_type == "demo"

    def test_demo_mode_with_true_string(self, monkeypatch):
        """Various truthy string values for CASCOR_DEMO_MODE."""
        for value in ("1", "true", "yes"):
            backend = _create_backend_with_env(
                monkeypatch,
                {
                    "CASCOR_DEMO_MODE": value,
                    "CASCOR_SERVICE_URL": None,
                },
            )
            assert backend.backend_type == "demo", f"Failed for CASCOR_DEMO_MODE={value}"


@pytest.mark.skipif(not _HAS_CASCOR_CLIENT, reason="juniper-cascor-client not installed")
class TestServiceMode:
    """Service mode activates when CASCOR_SERVICE_URL is set (and no demo mode)."""

    def test_service_mode_creates_backend(self, monkeypatch):
        """Setting CASCOR_SERVICE_URL should create a ServiceBackend."""
        backend = _create_backend_with_env(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
            },
        )

        assert backend.backend_type == "service"

    def test_service_mode_with_api_key(self, monkeypatch):
        """API key should be passed through to the adapter."""
        backend = _create_backend_with_env(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
                "JUNIPER_DATA_API_KEY": "test-key-123",
            },
        )

        assert backend.backend_type == "service"
        assert backend._adapter._api_key == "test-key-123"


class TestDefaultFallback:
    """Without any env vars, falls back to demo mode."""

    def test_no_env_vars_defaults_to_demo(self, monkeypatch):
        """No CASCOR_SERVICE_URL and CASCOR_DEMO_MODE=0 → default to demo mode."""
        backend = _create_backend_with_env(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": None,
            },
        )

        assert backend.backend_type == "demo"
