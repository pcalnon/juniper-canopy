#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_rate_limit_default.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-03-16
# Last Modified: 2026-03-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for rate limiting default configuration.
#
#     Regression introduced by commit c692a07 ("feat(security): comprehensive
#     security hardening") which changed the rate limiter default from disabled
#     to enabled at 60 req/min. This caused 429 Too Many Requests errors on
#     internal dashboard API calls, breaking status display and metrics fetching.
#
#####################################################################################################################################################################################################
# Notes:
#     The conftest.py sets JUNIPER_CANOPY_RATE_LIMIT_ENABLED=false globally, so these
#     tests must use monkeypatch to override settings before testing the default.
#     The reset_singletons fixture (autouse) calls reset_security_state() which
#     clears the cached _rate_limiter singleton.
#
#####################################################################################################################################################################################################
"""Regression tests for rate limiting default configuration."""

import pytest


@pytest.mark.regression
@pytest.mark.unit
class TestRateLimitDefault:
    """Regression tests: rate limiting must be disabled by default."""

    def test_rate_limiter_disabled_by_default(self, monkeypatch):
        """Rate limiter must be disabled when settings.rate_limit_enabled is False.

        The dashboard makes high-frequency internal HTTP requests to its own
        API endpoints. Rate limiting these self-to-self calls is counterproductive.
        The rate limiter should be opt-in (explicitly enabled via settings).
        """
        from unittest.mock import MagicMock

        from security import get_rate_limiter, reset_security_state

        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = False
        mock_settings.rate_limit_requests_per_minute = 60
        monkeypatch.setattr("security.get_settings", lambda: mock_settings)

        reset_security_state()
        limiter = get_rate_limiter()

        assert limiter.enabled is False, "Rate limiter is enabled by default. It must be disabled by default " "because the Dash dashboard makes internal HTTP requests to /api/* " "endpoints that would exceed the rate limit and cause 429 errors."

    def test_rate_limiter_can_be_enabled_via_settings(self, monkeypatch):
        """Rate limiter can be explicitly enabled via settings."""
        from unittest.mock import MagicMock

        from security import get_rate_limiter, reset_security_state

        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 60
        monkeypatch.setattr("security.get_settings", lambda: mock_settings)

        reset_security_state()
        limiter = get_rate_limiter()

        assert limiter.enabled is True

    def test_rate_limiter_custom_requests_per_minute(self, monkeypatch):
        """Rate limiter uses requests_per_minute from settings."""
        from unittest.mock import MagicMock

        from security import get_rate_limiter, reset_security_state

        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = True
        mock_settings.rate_limit_requests_per_minute = 200
        monkeypatch.setattr("security.get_settings", lambda: mock_settings)

        reset_security_state()
        limiter = get_rate_limiter()

        assert limiter.enabled is True
        assert limiter.limit == 200

    def test_rate_limiter_disabled_with_settings_false(self, monkeypatch):
        """Rate limiter is disabled when settings.rate_limit_enabled is False."""
        from unittest.mock import MagicMock

        from security import get_rate_limiter, reset_security_state

        mock_settings = MagicMock()
        mock_settings.rate_limit_enabled = False
        mock_settings.rate_limit_requests_per_minute = 60
        monkeypatch.setattr("security.get_settings", lambda: mock_settings)

        reset_security_state()
        limiter = get_rate_limiter()

        assert limiter.enabled is False

    def test_settings_rate_limit_default_false(self, monkeypatch):
        """Settings.rate_limit_enabled must default to False.

        This aligns the Pydantic settings default with the runtime behavior
        of get_rate_limiter() and the documented default in security.py.
        """
        monkeypatch.delenv("CANOPY_RATE_LIMIT_ENABLED", raising=False)
        monkeypatch.delenv("JUNIPER_CANOPY_RATE_LIMIT_ENABLED", raising=False)

        from settings import Settings

        settings = Settings()
        assert settings.rate_limit_enabled is False, "Settings.rate_limit_enabled must default to False to match " "the documented and runtime default behavior."

    def test_security_module_docstring_says_default_false(self):
        """The security module docstring must document default as false."""
        import security

        docstring = security.__doc__
        assert "default: false" in docstring.lower() or "default: false" in docstring, "security.py module docstring must document rate limiting default as false. " f"Current docstring: {docstring!r}"

    def test_no_429_on_api_status_without_rate_limit(self):
        """API endpoints must not return 429 when rate limiting is disabled."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            # Simulate the dashboard's rapid polling pattern
            for _ in range(10):
                response = client.get("/api/status")
                assert response.status_code != 429, f"Got 429 Too Many Requests on /api/status with rate limiting " f"disabled. Response: {response.text}"
