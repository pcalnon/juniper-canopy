#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_dependency_floor_boot_check.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-07-01
# Last Modified: 2026-07-01
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for the E-8 boot-time dependency-floor self-check. canopy's
#     FastAPI lifespan calls juniper-service-core's ``enforce_dependency_floors
#     (distribution="juniper-canopy")`` before binding, so the server fails loud on
#     a below-floor juniper-* wheel instead of serving on a stale one (the canopy
#     "green tests / dead app" incident class). The automatic *prevention* companion
#     to ``make check-env`` / ``juniper-env-drift-check`` (E-2 *detection*).
#
#####################################################################################################################################################################################################
# References:
#     E-8 (juniper-ml notes/JUNIPER_ML_CUSTOM-AGENT-SUITE-ENHANCEMENTS_PLAN_2026-06-27.md §6.11)
#     juniper-service-core >= 0.4.0 (dependency_floors)
#####################################################################################################################################################################################################
"""Regression tests for the E-8 boot-time dependency-floor self-check in canopy's lifespan."""

from pathlib import Path

import pytest

# src/tests/regression/<this> -> parents[2] == src/
_MAIN_PY = Path(__file__).resolve().parents[2] / "main.py"


def test_lifespan_wires_dependency_floor_check():
    """The lifespan must call ``enforce_dependency_floors(distribution="juniper-canopy")``
    and do so BEFORE ``create_backend`` (fail loud before serving)."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    assert 'enforce_dependency_floors(distribution="juniper-canopy"' in src, "canopy lifespan must call enforce_dependency_floors(distribution='juniper-canopy')"
    assert "from juniper_service_core import enforce_dependency_floors" in src, "canopy must import enforce_dependency_floors from juniper_service_core"
    # Ordering: the floor check must precede backend initialization so a below-floor
    # env fails startup before any real work / binding.
    assert src.index("enforce_dependency_floors(distribution=") < src.index("create_backend"), "the floor check must run before create_backend"


def test_check_passes_for_the_current_env():
    """Against the actually-installed environment, canopy's declared juniper-* floors
    are satisfied, so the boot check does not raise. (In CI this runs on the freshly
    resolved lockfile; a real below-floor wheel here would be a genuine drift signal.)"""
    from juniper_service_core import enforce_dependency_floors

    # Must not raise: reads canopy's installed Requires-Dist floors and verifies the
    # installed juniper-* versions satisfy them.
    enforce_dependency_floors(distribution="juniper-canopy")


def test_check_raises_on_a_synthetic_below_floor(monkeypatch):
    """canopy's floors ARE enforced: force every installed version below floor and the
    check raises DependencyFloorError (which, at boot, fails uvicorn's startup)."""
    from juniper_service_core import DependencyFloorError, dependency_floors, enforce_dependency_floors

    # Real floors come from canopy's Requires-Dist (unpatched); every installed
    # version reports 0.0.1 -> below every juniper-* floor -> violation.
    monkeypatch.setattr(dependency_floors.metadata, "version", lambda dist: "0.0.1")
    with pytest.raises(DependencyFloorError):
        enforce_dependency_floors(distribution="juniper-canopy")


def test_escape_hatch_bypasses_the_check(monkeypatch):
    """The documented escape hatch bypasses the check even when it would otherwise fail."""
    from juniper_service_core import dependency_floors, enforce_dependency_floors

    monkeypatch.setenv("JUNIPER_SKIP_DEP_FLOOR_CHECK", "1")
    monkeypatch.setattr(dependency_floors.metadata, "version", lambda dist: "0.0.1")
    # Would raise without the escape hatch; with it set, returns cleanly.
    enforce_dependency_floors(distribution="juniper-canopy")
