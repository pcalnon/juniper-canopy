#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_auth_posture_boot_check.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-07-19
# Last Modified: 2026-07-19
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for the SEC-F01 boot-time auth-posture self-check. canopy's
#     FastAPI lifespan calls juniper-service-core's ``enforce_auth_posture(...,
#     require_auth=False, service_name="juniper-canopy")`` before binding, so an
#     empty/placeholder CANOPY_API_KEY secret -- which silently disables APIKeyAuth
#     and serves the control surface open (the HO-2 incident class) -- is at least
#     LOUD at boot. The security companion to the E-8 dependency-floor self-check
#     (test_dependency_floor_boot_check.py).
#
#####################################################################################################################################################################################################
# References:
#     SEC-F01 / HO-2 (containerized-stack security audit; juniper-service-core auth_posture module)
#     juniper-service-core >= 0.5.0 (enforce_auth_posture)
#####################################################################################################################################################################################################
"""Regression tests for the SEC-F01 boot-time auth-posture self-check in canopy's lifespan."""

from pathlib import Path

import pytest

# src/tests/regression/<this> -> parents[2] == src/
_MAIN_PY = Path(__file__).resolve().parents[2] / "main.py"


def test_lifespan_wires_auth_posture_check():
    """The lifespan must call ``enforce_auth_posture(..., service_name="juniper-canopy")``
    with require_auth=False (the loud-WARNING posture) and do so BEFORE ``create_backend``."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    assert "from juniper_service_core import enforce_auth_posture" in src, "canopy must import enforce_auth_posture from juniper_service_core"
    assert 'service_name="juniper-canopy"' in src, "the posture check must identify itself as juniper-canopy"
    assert "require_auth=False" in src, "this wave runs the loud-WARNING posture; flipping to fail-closed is the JUNIPER_CANOPY_REQUIRE_AUTH follow-up"
    # The check must consume the real resolved key, mirroring security.get_api_key_auth.
    assert 'get_secret("CANOPY_API_KEY")' in src, "the posture check must consume the resolved CANOPY_API_KEY secret"
    # Ordering: posture check must precede backend initialization / binding.
    assert src.index("enforce_auth_posture(") < src.index("create_backend"), "the auth-posture check must run before create_backend"


def test_no_key_and_not_required_warns_open(monkeypatch, caplog):
    """The HO-2 class made loud: no real key + require_auth=False logs a WARNING
    naming the service, and does NOT raise (canopy still starts)."""
    from juniper_service_core import enforce_auth_posture

    monkeypatch.delenv("JUNIPER_SKIP_AUTH_POSTURE_CHECK", raising=False)
    with caplog.at_level("WARNING"):
        enforce_auth_posture([], require_auth=False, service_name="juniper-canopy")
    assert any("running OPEN" in rec.getMessage() and "juniper-canopy" in rec.getMessage() for rec in caplog.records), "an open posture must produce a loud WARNING"


def test_blank_key_counts_as_unset(monkeypatch, caplog):
    """An empty/whitespace key -- exactly what an empty secret file resolves to -- is
    NOT real auth: the check must treat it as running open, not as configured."""
    from juniper_service_core import auth_is_configured, enforce_auth_posture

    assert not auth_is_configured([""])
    assert not auth_is_configured(["   "])
    monkeypatch.delenv("JUNIPER_SKIP_AUTH_POSTURE_CHECK", raising=False)
    with caplog.at_level("WARNING"):
        enforce_auth_posture(["   "], require_auth=False, service_name="juniper-canopy")
    assert any("running OPEN" in rec.getMessage() for rec in caplog.records), "a blank key must be reported as an open posture"


def test_real_key_passes_quietly(monkeypatch, caplog):
    """With a real key configured the check logs INFO (secured) and never warns."""
    from juniper_service_core import enforce_auth_posture

    monkeypatch.delenv("JUNIPER_SKIP_AUTH_POSTURE_CHECK", raising=False)
    with caplog.at_level("INFO"):
        enforce_auth_posture(["a-real-canopy-key"], require_auth=True, service_name="juniper-canopy")
    assert not any(rec.levelname in ("WARNING", "CRITICAL") for rec in caplog.records), "a configured key must not warn"


def test_required_with_no_key_raises(monkeypatch):
    """The fail-closed posture this wave prepares for: require_auth=True with no real
    key raises AuthPostureError (which, at boot, fails uvicorn's startup)."""
    from juniper_service_core import AuthPostureError, enforce_auth_posture

    monkeypatch.delenv("JUNIPER_SKIP_AUTH_POSTURE_CHECK", raising=False)
    with pytest.raises(AuthPostureError):
        enforce_auth_posture([], require_auth=True, service_name="juniper-canopy")


def test_escape_hatch_bypasses_the_check(monkeypatch):
    """The documented escape hatch bypasses the check even when it would otherwise raise."""
    from juniper_service_core import enforce_auth_posture

    monkeypatch.setenv("JUNIPER_SKIP_AUTH_POSTURE_CHECK", "1")
    # Would raise without the escape hatch; with it set, returns cleanly.
    enforce_auth_posture([], require_auth=True, service_name="juniper-canopy")
