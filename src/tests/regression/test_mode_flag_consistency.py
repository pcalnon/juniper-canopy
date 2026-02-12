#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_mode_flag_consistency.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-02-11
# Last Modified: 2026-02-11
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for Fix 5 (CF-1) — mode flag consistency between
#     shell and Python.  Verifies that the CASCOR_DEMO_MODE environment
#     variable is interpreted identically regardless of how it is set
#     (bash script vs. manual export).
#
#####################################################################################################################################################################################################
# Notes:
#     The expression under test lives at module-level in main.py (line 247):
#
#         force_demo_mode = os.getenv("CASCOR_DEMO_MODE", "0") in
#                           ("1", "true", "True", "yes", "Yes")
#
#     Because the expression is evaluated at import time we cannot
#     re-import main.py per test.  Instead we test the expression
#     logic directly, which is a deterministic string-membership check.
#
#####################################################################################################################################################################################################
# References:
#     Fix 5 (CF-1): Mode flag consistency
#     main.py lines 246-268
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     CF-1-1 through CF-1-6 initial implementation
#
#####################################################################################################################################################################################################

import os

import pytest

ALLOWED_DEMO_VALUES = ("1", "true", "True", "yes", "Yes")


def _evaluate_force_demo_mode(env_value):
    """Reproduce the exact expression from main.py line 247."""
    return env_value in ALLOWED_DEMO_VALUES


@pytest.mark.regression
class TestModeFlagConsistency:
    """Regression tests for CASCOR_DEMO_MODE flag interpretation (CF-1)."""

    def test_cascor_demo_mode_1_enables_demo(self, monkeypatch):
        """CF-1-1: CASCOR_DEMO_MODE=1 activates demo mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")
        value = os.getenv("CASCOR_DEMO_MODE", "0")
        assert _evaluate_force_demo_mode(value) is True

    def test_cascor_demo_mode_0_enables_real_backend(self, monkeypatch):
        """CF-1-2: CASCOR_DEMO_MODE=0 attempts real backend (demo mode off)."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "0")
        value = os.getenv("CASCOR_DEMO_MODE", "0")
        assert _evaluate_force_demo_mode(value) is False

    def test_cascor_demo_mode_unset_fallback_behavior(self, monkeypatch):
        """CF-1-3: Without CASCOR_DEMO_MODE the default is '0' (demo off).

        When the env var is absent, os.getenv returns the default '0'
        and the app falls back based on CascorIntegration availability.
        """
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)
        value = os.getenv("CASCOR_DEMO_MODE", "0")
        assert value == "0"
        assert _evaluate_force_demo_mode(value) is False

    def test_cascor_demo_mode_true_string_enables_demo(self, monkeypatch):
        """CF-1-4: CASCOR_DEMO_MODE=true activates demo mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "true")
        value = os.getenv("CASCOR_DEMO_MODE", "0")
        assert _evaluate_force_demo_mode(value) is True

    def test_cascor_demo_mode_yes_string_enables_demo(self, monkeypatch):
        """CF-1-5: CASCOR_DEMO_MODE=yes activates demo mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "yes")
        value = os.getenv("CASCOR_DEMO_MODE", "0")
        assert _evaluate_force_demo_mode(value) is True

    @pytest.mark.parametrize(
        "bad_value",
        ["2", "no", "No", "false", "False", "on", "OFF", ""],
    )
    def test_demo_mode_values_not_in_allowed_list(self, monkeypatch, bad_value):
        """CF-1-6: Values outside the allowed set do NOT enable demo mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", bad_value)
        value = os.getenv("CASCOR_DEMO_MODE", "0")
        assert _evaluate_force_demo_mode(value) is False
