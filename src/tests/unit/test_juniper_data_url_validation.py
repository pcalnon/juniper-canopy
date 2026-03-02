#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.2.0
# File Name:     test_juniper_data_url_validation.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/tests/unit/
#
# Date Created:  2026-02-11
# Last Modified: 2026-03-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Unit tests for JUNIPER_DATA_URL validation via Pydantic Settings.
#    After the migration from ConfigManager to Settings (BaseSettings),
#    the URL is always resolved from Settings.juniper_data_url which
#    has a default of "http://localhost:8100" and picks up JUNIPER_DATA_URL
#    env var via a field_validator fallback.
#
#####################################################################################################################################################################################################

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main as main_module
from main import app
from settings import Settings, get_settings


@pytest.fixture
def _force_demo_mode(monkeypatch):
    """Ensure demo mode via environment for tests that need it."""
    monkeypatch.setenv("CASCOR_DEMO_MODE", "1")
    yield


class TestJuniperDataUrlValidation:
    """Unit tests for JUNIPER_DATA_URL validation via Settings (RC-5)."""

    @pytest.mark.unit
    def test_settings_default_url_is_localhost(self):
        """Settings provides default juniper_data_url of http://localhost:8100."""
        get_settings.cache_clear()
        s = get_settings()
        assert s.juniper_data_url == "http://localhost:8100"

    @pytest.mark.unit
    def test_juniper_data_url_env_picked_up_by_settings(self, monkeypatch):
        """JUNIPER_DATA_URL env var is picked up by Settings via field_validator."""
        get_settings.cache_clear()
        monkeypatch.setenv("JUNIPER_DATA_URL", "http://custom-host:9000")
        get_settings.cache_clear()
        s = Settings()
        assert s.juniper_data_url == "http://custom-host:9000"

    @pytest.mark.unit
    def test_env_var_takes_precedence_over_config(self, monkeypatch, _force_demo_mode):
        """JUNIPER_DATA_URL env var overrides the config value."""
        env_url = "http://env-override:9999"
        monkeypatch.setenv("JUNIPER_DATA_URL", env_url)

        with TestClient(app):
            assert os.environ.get("JUNIPER_DATA_URL") == env_url

    @pytest.mark.unit
    def test_url_propagated_to_env_during_startup(self, _force_demo_mode):
        """Settings juniper_data_url is propagated to JUNIPER_DATA_URL env var at startup."""
        with TestClient(app):
            url = os.environ.get("JUNIPER_DATA_URL")
            assert url is not None
            assert "localhost" in url or "8100" in url
