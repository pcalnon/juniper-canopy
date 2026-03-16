#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_csp_bootstrap_cdn.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-03-16
# Last Modified: 2026-03-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for Content-Security-Policy compatibility with
#     dash-bootstrap-components CDN stylesheet loading.
#
#     Regression introduced by commit c692a07 ("feat(security): comprehensive
#     security hardening") which added a CSP that blocked the Bootstrap CSS
#     CDN, breaking the entire dashboard layout (sidebar, tabs, content visibility).
#
#####################################################################################################################################################################################################
# Notes:
#     These tests ensure the CSP allows the Bootstrap CDN used by
#     dash-bootstrap-components and does not regress to blocking it.
#
#####################################################################################################################################################################################################

from urllib.parse import urlparse

import dash_bootstrap_components as dbc
import pytest


@pytest.mark.regression
@pytest.mark.unit
class TestCSPBootstrapCDN:
    """Regression tests: CSP must allow Bootstrap CSS from CDN."""

    def test_csp_allows_bootstrap_cdn_domain(self):
        """CSP style-src must include the Bootstrap CDN origin.

        The SecurityHeadersMiddleware CSP must allow the domain used by
        dbc.themes.BOOTSTRAP so the browser does not block the stylesheet.
        """
        from middleware import _DEFAULT_CSP

        bootstrap_url = dbc.themes.BOOTSTRAP
        parsed = urlparse(bootstrap_url)
        cdn_origin = f"{parsed.scheme}://{parsed.hostname}"

        assert cdn_origin in _DEFAULT_CSP, f"CSP does not allow Bootstrap CDN origin {cdn_origin!r}. " f"dbc.themes.BOOTSTRAP resolves to {bootstrap_url!r}. " f"Current CSP: {_DEFAULT_CSP!r}"

    def test_csp_contains_style_src_cdn(self):
        """CSP style-src directive must include https://cdn.jsdelivr.net."""
        from middleware import _DEFAULT_CSP

        # Extract style-src directive
        for directive in _DEFAULT_CSP.split(";"):
            directive = directive.strip()
            if directive.startswith("style-src"):
                assert "https://cdn.jsdelivr.net" in directive, f"style-src directive does not allow cdn.jsdelivr.net: {directive!r}"
                break
        else:
            pytest.fail(f"No style-src directive found in CSP: {_DEFAULT_CSP!r}")

    def test_csp_allows_data_uri_images(self):
        """CSP img-src must allow data: URIs for Bootstrap SVG icons.

        Bootstrap 5 CSS uses data:image/svg+xml URIs for form control
        indicators (select arrows, checkboxes, radio buttons, validation icons).
        """
        from middleware import _DEFAULT_CSP

        for directive in _DEFAULT_CSP.split(";"):
            directive = directive.strip()
            if directive.startswith("img-src"):
                assert "data:" in directive, f"img-src directive does not allow data: URIs: {directive!r}"
                break
        else:
            pytest.fail(f"No img-src directive found in CSP: {_DEFAULT_CSP!r}. " "Without img-src 'self' data:, Bootstrap form control SVG icons will not render.")

    def test_csp_does_not_allow_cdn_in_script_src(self):
        """CSP script-src must NOT include CDN domains.

        dbc JavaScript is served locally (serve_locally=True is default).
        Allowing CDN domains in script-src would be a security risk.
        """
        from middleware import _DEFAULT_CSP

        for directive in _DEFAULT_CSP.split(";"):
            directive = directive.strip()
            if directive.startswith("script-src"):
                assert "cdn.jsdelivr.net" not in directive, f"script-src should NOT allow cdn.jsdelivr.net: {directive!r}. " "dbc JavaScript is served locally; CDN in script-src is a security risk."
                break

    def test_security_headers_middleware_uses_default_csp(self):
        """SecurityHeadersMiddleware default CSP matches the module constant."""
        from unittest.mock import AsyncMock, MagicMock

        from middleware import _DEFAULT_CSP, SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)
        assert middleware._csp == _DEFAULT_CSP

    def test_dashboard_response_includes_csp_header(self):
        """Dashboard responses must include the CSP header."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            response = client.get("/dashboard/")
            assert "Content-Security-Policy" in response.headers, "Dashboard response missing Content-Security-Policy header"
            csp = response.headers["Content-Security-Policy"]
            assert "cdn.jsdelivr.net" in csp, f"Dashboard CSP does not allow Bootstrap CDN: {csp!r}"
