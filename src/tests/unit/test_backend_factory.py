#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_backend_factory.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-02-26
# Last Modified: 2026-02-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for create_backend() factory function
#####################################################################
"""
Unit tests for create_backend() factory — verify correct backend type for each env var combination.

Task 5.9 of the Microservices Architecture Development Roadmap.
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.demo_backend import DemoBackend
from backend.protocol import BackendProtocol

try:
    import juniper_cascor_client  # noqa: F401

    _HAS_CASCOR_CLIENT = True
except ImportError:
    _HAS_CASCOR_CLIENT = False


def _create_backend_with_env(monkeypatch, env_vars: dict):
    """Call create_backend() with specific environment variables."""
    for key, value in env_vars.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)

    from backend import create_backend

    return create_backend()


class TestFactoryDemoMode:
    """Factory should return DemoBackend when CASCOR_DEMO_MODE is set."""

    def test_demo_mode_explicit(self, monkeypatch):
        """CASCOR_DEMO_MODE=1 → DemoBackend."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "1", "CASCOR_SERVICE_URL": None})
        assert isinstance(backend, DemoBackend)
        assert backend.backend_type == "demo"

    def test_demo_mode_true_string(self, monkeypatch):
        """CASCOR_DEMO_MODE=true → DemoBackend."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "true", "CASCOR_SERVICE_URL": None})
        assert backend.backend_type == "demo"

    def test_demo_mode_yes_string(self, monkeypatch):
        """CASCOR_DEMO_MODE=yes → DemoBackend."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "yes", "CASCOR_SERVICE_URL": None})
        assert backend.backend_type == "demo"

    def test_demo_mode_overrides_service_url(self, monkeypatch):
        """CASCOR_DEMO_MODE=1 takes precedence over CASCOR_SERVICE_URL."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "1", "CASCOR_SERVICE_URL": "http://localhost:8200"})
        assert backend.backend_type == "demo"


class TestFactoryServiceMode:
    """Factory should return ServiceBackend when CASCOR_SERVICE_URL is set."""

    @pytest.mark.skipif(not _HAS_CASCOR_CLIENT, reason="juniper-cascor-client not installed")
    def test_service_url_creates_service_backend(self, monkeypatch):
        """CASCOR_SERVICE_URL set (no demo mode) → ServiceBackend."""
        from backend.service_backend import ServiceBackend

        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "0", "CASCOR_SERVICE_URL": "http://localhost:8200"})
        assert isinstance(backend, ServiceBackend)
        assert backend.backend_type == "service"

    @pytest.mark.skipif(not _HAS_CASCOR_CLIENT, reason="juniper-cascor-client not installed")
    def test_service_url_with_api_key(self, monkeypatch):
        """CASCOR_SERVICE_URL + JUNIPER_DATA_API_KEY should be passed to adapter."""
        backend = _create_backend_with_env(
            monkeypatch,
            {
                "CASCOR_DEMO_MODE": "0",
                "CASCOR_SERVICE_URL": "http://localhost:8200",
                "JUNIPER_DATA_API_KEY": "test-key-123",
            },
        )
        assert backend.backend_type == "service"


class TestFactoryFallback:
    """Factory should fall back to DemoBackend when no env vars are set."""

    def test_no_env_vars_falls_back_to_demo(self, monkeypatch):
        """No CASCOR_DEMO_MODE, no CASCOR_SERVICE_URL → DemoBackend (fallback)."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "0", "CASCOR_SERVICE_URL": None})
        assert isinstance(backend, DemoBackend)
        assert backend.backend_type == "demo"

    def test_demo_mode_disabled_no_url_falls_back(self, monkeypatch):
        """CASCOR_DEMO_MODE=0 with no service URL → DemoBackend fallback."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "0", "CASCOR_SERVICE_URL": None})
        assert backend.backend_type == "demo"

    def test_demo_mode_false_no_url_falls_back(self, monkeypatch):
        """CASCOR_DEMO_MODE=false with no service URL → DemoBackend fallback."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "false", "CASCOR_SERVICE_URL": None})
        assert backend.backend_type == "demo"


class TestFactoryProtocolConformance:
    """Factory output should always conform to BackendProtocol."""

    def test_demo_backend_conforms_to_protocol(self, monkeypatch):
        """DemoBackend from factory satisfies BackendProtocol."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "1", "CASCOR_SERVICE_URL": None})
        assert isinstance(backend, BackendProtocol)

    @pytest.mark.skipif(not _HAS_CASCOR_CLIENT, reason="juniper-cascor-client not installed")
    def test_service_backend_conforms_to_protocol(self, monkeypatch):
        """ServiceBackend from factory satisfies BackendProtocol."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "0", "CASCOR_SERVICE_URL": "http://localhost:8200"})
        assert isinstance(backend, BackendProtocol)

    def test_fallback_backend_conforms_to_protocol(self, monkeypatch):
        """Fallback DemoBackend from factory satisfies BackendProtocol."""
        backend = _create_backend_with_env(monkeypatch, {"CASCOR_DEMO_MODE": "0", "CASCOR_SERVICE_URL": None})
        assert isinstance(backend, BackendProtocol)
