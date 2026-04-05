#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Regression coverage for Docker runtime defaults
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_docker_demo_mode_default.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-04-04
# Last Modified: 2026-04-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Guards against forcing demo mode as a Docker image default, which can
#     silently route production deployments to synthetic data when a CasCor
#     service URL is configured.
#
#####################################################################################################################################################################################################

"""Regression tests for Docker demo-mode defaults."""

from pathlib import Path

import pytest


@pytest.mark.regression
@pytest.mark.unit
class TestDockerRuntimeDefaults:
    """Ensure Dockerfiles do not hard-force demo mode."""

    def test_root_dockerfile_does_not_force_demo_mode(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
        assert "JUNIPER_CANOPY_DEMO_MODE=1" not in dockerfile

    def test_conf_dockerfile_does_not_force_demo_mode(self):
        dockerfile = Path("conf/Dockerfile").read_text(encoding="utf-8")
        assert "JUNIPER_CANOPY_DEMO_MODE=1" not in dockerfile
