#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# File Name:     test_cfg_16_create_backend_no_raw_env.py
# Author:        Paul Calnon
# Version:       1.0.0
# Date:          2026-05-21
# Last Modified: 2026-05-21
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Regression tests for v7 roadmap CFG-16: create_backend()
#                must not read legacy CASCOR_DEMO_MODE / CASCOR_SERVICE_URL
#                via raw os.getenv. Both legacy env vars are handled by
#                Settings field_validators in src/settings.py
#                (_check_legacy_demo_mode, _check_cascor_service_url),
#                which emit DeprecationWarning and map them to the
#                Settings fields create_backend() consults.
#####################################################################

"""Regression tests for CFG-16 (v7 roadmap).

Before this change ``src/backend/__init__.py`` re-read ``CASCOR_DEMO_MODE``
and ``CASCOR_SERVICE_URL`` directly via ``os.getenv`` as a "legacy
fallback", duplicating logic that already lives in the Settings
validators ``_check_legacy_demo_mode`` and ``_check_cascor_service_url``.
The redundant raw reads bypassed the deprecation warning at the
``create_backend()`` call site and made the resolution chain harder to
follow.

These tests pin two properties:

1. ``src/backend/__init__.py`` does not contain raw ``os.getenv`` reads
   for either legacy env var (scope guard).
2. The end-to-end legacy path still works — ``CASCOR_DEMO_MODE=1``
   (without ``JUNIPER_CANOPY_DEMO_MODE``) flows through the Settings
   validator and ``create_backend()`` still returns a ``DemoBackend``
   (behaviour guard).
"""

import inspect
import warnings

import pytest


class TestCfg16NoRawCascorEnvReads:
    """Source-level scope guard: backend/__init__.py is Settings-only."""

    @staticmethod
    def _strip_comments_and_docstrings(source: str) -> str:
        """Drop comment lines and triple-quoted docstring blocks so the
        scope guard only fires on executable references to the env
        vars, not on prose that legitimately names them.
        """
        import re

        # Remove triple-quoted strings (greedy across newlines).
        no_docstrings = re.sub(r'"""[\s\S]*?"""', "", source)
        no_docstrings = re.sub(r"'''[\s\S]*?'''", "", no_docstrings)
        # Drop full-line comments.
        lines = [line for line in no_docstrings.splitlines() if not line.lstrip().startswith("#")]
        return "\n".join(lines)

    def test_create_backend_module_has_no_raw_cascor_demo_mode_read(self):
        """Reintroducing ``os.getenv("CASCOR_DEMO_MODE", ...)`` in
        ``backend/__init__.py`` reverts CFG-16. ``Settings.demo_mode``
        already handles the legacy env var via
        ``_check_legacy_demo_mode`` in ``src/settings.py``.
        """
        import backend as backend_pkg

        executable = self._strip_comments_and_docstrings(inspect.getsource(backend_pkg))
        assert "CASCOR_DEMO_MODE" not in executable, "Raw CASCOR_DEMO_MODE read reintroduced in backend/__init__.py; " "use settings.demo_mode — Settings._check_legacy_demo_mode " "handles the legacy env var with DeprecationWarning."

    def test_create_backend_module_has_no_raw_cascor_service_url_read(self):
        """Reintroducing ``os.getenv("CASCOR_SERVICE_URL")`` in
        ``backend/__init__.py`` reverts CFG-16. ``Settings.cascor_service_url``
        already handles the legacy env var via
        ``_check_cascor_service_url`` in ``src/settings.py``.
        """
        import backend as backend_pkg

        executable = self._strip_comments_and_docstrings(inspect.getsource(backend_pkg))
        assert "CASCOR_SERVICE_URL" not in executable, "Raw CASCOR_SERVICE_URL read reintroduced in backend/__init__.py; " "use settings.cascor_service_url — Settings._check_cascor_service_url " "handles the legacy env var with DeprecationWarning."


class TestCfg16LegacyDemoModeEndToEnd:
    """Behaviour guard: removing the raw fallback does not break the
    legacy ``CASCOR_DEMO_MODE`` path."""

    @pytest.fixture()
    def legacy_demo_env(self, monkeypatch):
        """Activate only the legacy CASCOR_DEMO_MODE variable so the
        Settings validator hits its deprecation branch."""
        # The new-prefix var would short-circuit the validator's legacy
        # branch (it returns the pydantic-parsed value when set). The
        # global conftest sets it to "1" — delete it for this test.
        monkeypatch.delenv("JUNIPER_CANOPY_DEMO_MODE", raising=False)
        monkeypatch.delenv("JUNIPER_CANOPY_CASCOR_SERVICE_URL", raising=False)
        monkeypatch.delenv("CASCOR_SERVICE_URL", raising=False)
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

    def test_cascor_demo_mode_routes_to_demo_backend_via_settings(self, legacy_demo_env):
        """``CASCOR_DEMO_MODE=1`` (legacy) must still produce a
        ``DemoBackend`` from ``create_backend()`` after the raw fallback
        is removed. The path is now: env var -> Settings validator
        (emits DeprecationWarning) -> ``settings.demo_mode=True`` ->
        ``create_backend()`` -> ``DemoBackend``.
        """
        from settings import get_settings

        get_settings.cache_clear()

        # demo_mode.get_demo_mode() requires torch via DemoMode; if the
        # local env's torch is broken, skip rather than blame CFG-16.
        pytest.importorskip("torch", exc_type=ImportError)

        from backend import create_backend
        from backend.demo_backend import DemoBackend

        with warnings.catch_warnings():
            # Validator's DeprecationWarning is expected; the
            # behavioural assertion is what we care about.
            warnings.simplefilter("ignore", DeprecationWarning)
            backend = create_backend()

        assert isinstance(backend, DemoBackend), "Legacy CASCOR_DEMO_MODE path no longer routes to DemoBackend. " "Check that Settings._check_legacy_demo_mode still maps " "CASCOR_DEMO_MODE -> settings.demo_mode."

    def test_cascor_demo_mode_emits_deprecation_warning_on_settings_construction(self, legacy_demo_env):
        """``CASCOR_DEMO_MODE=1`` triggers exactly the validator's
        deprecation warning when Settings is constructed. Pins that
        removing the raw ``backend/__init__.py`` fallback did not also
        accidentally remove the validator-level warning users depend on
        to migrate to ``JUNIPER_CANOPY_DEMO_MODE``.
        """
        from settings import Settings, get_settings

        get_settings.cache_clear()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            settings = Settings()

        assert settings.demo_mode is True
        demo_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning) and "CASCOR_DEMO_MODE" in str(w.message)]
        assert len(demo_warnings) >= 1, "Expected DeprecationWarning for CASCOR_DEMO_MODE from " "Settings._check_legacy_demo_mode."
