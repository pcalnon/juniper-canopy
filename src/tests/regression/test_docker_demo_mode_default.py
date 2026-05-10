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

# Resolve repo root from this file's location so tests pass regardless of pytest CWD
# (AGENTS.md documents `cd src && pytest tests/`, but CI and IDEs often run from repo root).
_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.regression
@pytest.mark.unit
class TestDockerRuntimeDefaults:
    """Ensure Dockerfiles do not hard-force demo mode."""

    def test_root_dockerfile_does_not_force_demo_mode(self):
        dockerfile = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        assert "JUNIPER_CANOPY_DEMO_MODE=1" not in dockerfile

    def test_conf_dockerfile_does_not_force_demo_mode(self):
        dockerfile = (_REPO_ROOT / "conf" / "Dockerfile").read_text(encoding="utf-8")
        assert "JUNIPER_CANOPY_DEMO_MODE=1" not in dockerfile

    def test_repo_root_resolution_finds_dockerfiles(self):
        """Locks in the parents[3] path math used by the tests above.

        Regression guard: an earlier revision used relative ``Path("Dockerfile")``
        which only resolved when pytest was invoked from the repo root, so the
        tests passed locally when run from ``src/`` (per AGENTS.md) only because
        FileNotFoundError was being raised — i.e., the assertion was never
        evaluated. This sanity check makes that class of bug loud.
        """
        assert (_REPO_ROOT / "Dockerfile").is_file(), f"Repo-root Dockerfile not found at {_REPO_ROOT}"
        assert (_REPO_ROOT / "conf" / "Dockerfile").is_file(), f"conf/Dockerfile not found under {_REPO_ROOT}"
        # Sanity: the resolved root is the repo, not src/ or tests/.
        assert (_REPO_ROOT / "src").is_dir(), f"Expected src/ under {_REPO_ROOT}"
