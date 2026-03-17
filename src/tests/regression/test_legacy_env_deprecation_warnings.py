#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# File Name:     test_legacy_env_deprecation_warnings.py
# Author:        Paul Calnon
# Version:       1.0.0
# Date:          2026-03-16
# Last Modified: 2026-03-16
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Regression tests for legacy CASCOR_* env var deprecation warnings.
#                Ensures deprecated env vars emit exactly one warning and that
#                new-prefix env vars suppress the warning entirely.
#####################################################################

"""Regression tests for legacy CASCOR_* env var deprecation warnings.

These tests verify that:
1. Legacy CASCOR_* env vars trigger DeprecationWarning when used
2. New JUNIPER_CANOPY_* env vars take precedence and suppress warnings
3. The conftest.py environment setup prevents warning spam during test runs
4. Settings validators correctly fall back through the priority chain
"""

import os
import warnings

import pytest


@pytest.fixture()
def clean_settings_env(monkeypatch):
    """Remove all CASCOR_* and JUNIPER_CANOPY_* env vars for isolated testing."""
    legacy_vars = [
        "CASCOR_BACKEND_PATH",
        "CASCOR_LOG_LEVEL",
        "CASCOR_DEMO_MODE",
        "CASCOR_DEMO_UPDATE_INTERVAL",
        "CASCOR_SERVICE_URL",
    ]
    new_vars = [
        "JUNIPER_CANOPY_BACKEND_PATH",
        "JUNIPER_CANOPY_LOG_LEVEL",
        "JUNIPER_CANOPY_DEMO_MODE",
        "JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL",
        "JUNIPER_CANOPY_CASCOR_SERVICE_URL",
        "JUNIPER_CANOPY_JUNIPER_DATA_URL",
    ]
    for var in legacy_vars + new_vars:
        monkeypatch.delenv(var, raising=False)
    # Always keep demo mode on for tests
    monkeypatch.setenv("JUNIPER_CANOPY_DEMO_MODE", "1")
    # Keep data URL set (required by conftest contract)
    monkeypatch.setenv("JUNIPER_DATA_URL", "http://localhost:8100")


class TestLegacyBackendPathWarning:
    """Verify CASCOR_BACKEND_PATH deprecation warning behavior."""

    def test_legacy_backend_path_emits_deprecation_warning(self, clean_settings_env, monkeypatch):
        """Legacy CASCOR_BACKEND_PATH should emit a DeprecationWarning."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("CASCOR_BACKEND_PATH", "/legacy/path")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_BACKEND_PATH" in str(w.message)]
        assert len(deprecation_msgs) >= 1, "Expected DeprecationWarning for CASCOR_BACKEND_PATH"
        assert settings.backend_path == "/legacy/path"

    def test_new_prefix_suppresses_backend_path_warning(self, clean_settings_env, monkeypatch):
        """JUNIPER_CANOPY_BACKEND_PATH should suppress the deprecation warning."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("JUNIPER_CANOPY_BACKEND_PATH", "/new/path")
        monkeypatch.setenv("CASCOR_BACKEND_PATH", "/legacy/path")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_BACKEND_PATH" in str(w.message)]
        assert len(deprecation_msgs) == 0, "No warning expected when new prefix is set"
        assert settings.backend_path == "/new/path"

    def test_no_env_var_uses_default(self, clean_settings_env):
        """No env vars set should use the default backend_path without warning."""
        from settings import Settings, get_settings

        get_settings.cache_clear()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_BACKEND_PATH" in str(w.message)]
        assert len(deprecation_msgs) == 0, "No warning expected when neither env var is set"
        assert settings.backend_path == "../juniper-cascor"


class TestLegacyLogLevelWarning:
    """Verify CASCOR_LOG_LEVEL deprecation warning behavior."""

    def test_legacy_log_level_emits_deprecation_warning(self, clean_settings_env, monkeypatch):
        """Legacy CASCOR_LOG_LEVEL should emit a DeprecationWarning."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("CASCOR_LOG_LEVEL", "WARNING")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_LOG_LEVEL" in str(w.message)]
        assert len(deprecation_msgs) >= 1, "Expected DeprecationWarning for CASCOR_LOG_LEVEL"
        assert settings.log_level == "WARNING"

    def test_new_prefix_suppresses_log_level_warning(self, clean_settings_env, monkeypatch):
        """JUNIPER_CANOPY_LOG_LEVEL should suppress the deprecation warning."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("JUNIPER_CANOPY_LOG_LEVEL", "ERROR")
        monkeypatch.setenv("CASCOR_LOG_LEVEL", "WARNING")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_LOG_LEVEL" in str(w.message)]
        assert len(deprecation_msgs) == 0, "No warning expected when new prefix is set"
        assert settings.log_level == "ERROR"


class TestLegacyDemoUpdateIntervalWarning:
    """Verify CASCOR_DEMO_UPDATE_INTERVAL deprecation warning behavior."""

    def test_legacy_demo_interval_emits_deprecation_warning(self, clean_settings_env, monkeypatch):
        """Legacy CASCOR_DEMO_UPDATE_INTERVAL should emit a DeprecationWarning."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("CASCOR_DEMO_UPDATE_INTERVAL", "2.5")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_DEMO_UPDATE_INTERVAL" in str(w.message)]
        assert len(deprecation_msgs) >= 1, "Expected DeprecationWarning for CASCOR_DEMO_UPDATE_INTERVAL"
        assert settings.demo_update_interval == 2.5


class TestConftestEnvironmentSetup:
    """Verify conftest.py properly sets new-prefix env vars to prevent warning spam."""

    def test_conftest_sets_backend_path(self):
        """conftest.py should set JUNIPER_CANOPY_BACKEND_PATH."""
        assert os.environ.get("JUNIPER_CANOPY_BACKEND_PATH") is not None, "conftest.py must set JUNIPER_CANOPY_BACKEND_PATH to prevent " "DeprecationWarning spam from CASCOR_BACKEND_PATH"

    def test_conftest_sets_log_level(self):
        """conftest.py should set JUNIPER_CANOPY_LOG_LEVEL."""
        assert os.environ.get("JUNIPER_CANOPY_LOG_LEVEL") is not None, "conftest.py must set JUNIPER_CANOPY_LOG_LEVEL to prevent " "DeprecationWarning spam from CASCOR_LOG_LEVEL"

    def test_conftest_sets_demo_update_interval(self):
        """conftest.py should set JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL."""
        assert os.environ.get("JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL") is not None, "conftest.py must set JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL to prevent " "DeprecationWarning spam from CASCOR_DEMO_UPDATE_INTERVAL"

    def test_settings_creation_emits_no_cascor_deprecation_warnings(self):
        """Creating Settings with conftest env setup should emit zero CASCOR_* deprecation warnings."""
        from settings import Settings, get_settings

        get_settings.cache_clear()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            Settings()

        cascor_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_" in str(w.message)]
        assert len(cascor_warnings) == 0, f"Expected zero CASCOR_* deprecation warnings under conftest env, got {len(cascor_warnings)}: {[str(w.message) for w in cascor_warnings]}"


class TestNewPrefixPriority:
    """Verify new JUNIPER_CANOPY_* prefix always takes priority over legacy CASCOR_*."""

    def test_new_prefix_overrides_legacy_backend_path(self, clean_settings_env, monkeypatch):
        """JUNIPER_CANOPY_BACKEND_PATH must override CASCOR_BACKEND_PATH."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("JUNIPER_CANOPY_BACKEND_PATH", "/new/wins")
        monkeypatch.setenv("CASCOR_BACKEND_PATH", "/legacy/loses")
        settings = Settings()
        assert settings.backend_path == "/new/wins"

    def test_new_prefix_overrides_legacy_log_level(self, clean_settings_env, monkeypatch):
        """JUNIPER_CANOPY_LOG_LEVEL must override CASCOR_LOG_LEVEL."""
        from settings import Settings, get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("JUNIPER_CANOPY_LOG_LEVEL", "CRITICAL")
        monkeypatch.setenv("CASCOR_LOG_LEVEL", "DEBUG")
        settings = Settings()
        assert settings.log_level == "CRITICAL"
