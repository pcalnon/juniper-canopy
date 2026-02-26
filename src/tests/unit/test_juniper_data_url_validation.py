#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     test_juniper_data_url_validation.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/tests/unit/
#
# Date Created:  2026-02-11
# Last Modified: 2026-02-11
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Unit tests for Fix 4 (RC-5) — JUNIPER_DATA_URL validation in both
#    demo mode and real backend mode. Verifies that the lifespan startup
#    logic correctly requires JUNIPER_DATA_URL, resolves it from config
#    when the env var is absent, and rejects invalid config values
#    (e.g. un-expanded "$" prefixed strings).
#
#####################################################################################################################################################################################################
# Notes:
#    conftest.py sets JUNIPER_DATA_URL=http://localhost:8100 and
#    CASCOR_DEMO_MODE=1 at module load time. Tests that need to verify
#    missing-URL behavior use monkeypatch to temporarily unset these
#    env vars.
#
#    The lifespan function is an async context manager invoked when a
#    FastAPI TestClient context is entered. Tests patch os.environ and
#    the config manager's get() method to control what the lifespan
#    sees at startup.
#
#####################################################################################################################################################################################################
# References:
#    - Fix 4 (RC-5): JUNIPER_DATA_URL validation in src/main.py lifespan
#    - CAN-INT-002: Mandatory JUNIPER_DATA_URL enforcement
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main as main_module
from main import app


@pytest.fixture
def _force_demo_mode():
    """Ensure demo_mode_active is True for tests that need demo mode."""
    original = main_module.demo_mode_active
    main_module.demo_mode_active = True
    yield
    main_module.demo_mode_active = original


@pytest.fixture
def _force_real_mode():
    """Ensure demo_mode_active is False and backend is None."""
    orig_active = main_module.demo_mode_active
    orig_cascor = main_module.backend
    main_module.demo_mode_active = False
    main_module.backend = None
    yield
    main_module.demo_mode_active = orig_active
    main_module.backend = orig_cascor


class TestJuniperDataUrlValidation:
    """Unit tests for JUNIPER_DATA_URL validation during app startup (RC-5)."""

    @pytest.mark.unit
    def test_missing_url_raises_error_in_demo_mode(self, monkeypatch, _force_demo_mode):
        """App fails to start without JUNIPER_DATA_URL when in demo mode."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        with patch.object(main_module.config, "get", wraps=main_module.config.get) as mock_get:
            mock_get.side_effect = lambda key, *a, **kw: (None if key == "backend.juniper_data.url" else main_module.config.__class__.get(main_module.config, key, *a, **kw))
            with pytest.raises(RuntimeError, match="JUNIPER_DATA_URL is required"):
                with TestClient(app):
                    pass

    @pytest.mark.unit
    def test_missing_url_raises_error_in_real_mode(self, monkeypatch, _force_real_mode):
        """App fails to start without JUNIPER_DATA_URL when in real backend mode."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        with patch.object(main_module.config, "get", wraps=main_module.config.get) as mock_get:
            mock_get.side_effect = lambda key, *a, **kw: (None if key == "backend.juniper_data.url" else main_module.config.__class__.get(main_module.config, key, *a, **kw))
            with pytest.raises(RuntimeError, match="JUNIPER_DATA_URL is required"):
                with TestClient(app):
                    pass

    @pytest.mark.unit
    def test_url_resolved_from_config(self, monkeypatch, _force_demo_mode):
        """JUNIPER_DATA_URL is resolved from app_config.yaml when env var is not set."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        config_url = "http://config-host:8100"

        with patch.object(main_module.config, "get", wraps=main_module.config.get) as mock_get:
            mock_get.side_effect = lambda key, *a, **kw: (config_url if key == "backend.juniper_data.url" else main_module.config.__class__.get(main_module.config, key, *a, **kw))
            with TestClient(app):
                resolved = os.environ.get("JUNIPER_DATA_URL")
                assert resolved == config_url

    @pytest.mark.unit
    def test_env_var_takes_precedence_over_config(self, monkeypatch, _force_demo_mode):
        """JUNIPER_DATA_URL env var overrides the config value."""
        env_url = "http://env-override:9999"
        monkeypatch.setenv("JUNIPER_DATA_URL", env_url)

        with TestClient(app):
            assert os.environ.get("JUNIPER_DATA_URL") == env_url

    @pytest.mark.unit
    def test_url_with_dollar_prefix_rejected(self, monkeypatch, _force_demo_mode):
        """Config value starting with '$' is not used as a valid URL."""
        monkeypatch.delenv("JUNIPER_DATA_URL", raising=False)

        with patch.object(main_module.config, "get", wraps=main_module.config.get) as mock_get:
            mock_get.side_effect = lambda key, *a, **kw: ("${JUNIPER_DATA_URL}" if key == "backend.juniper_data.url" else main_module.config.__class__.get(main_module.config, key, *a, **kw))
            with pytest.raises(RuntimeError, match="JUNIPER_DATA_URL is required"):
                with TestClient(app):
                    pass
