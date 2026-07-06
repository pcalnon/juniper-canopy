#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Regression coverage for the Docker default bind host (SEC-F22 / D2)
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_docker_bind_default.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-07-06
# Last Modified: 2026-07-06
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Pins the root Dockerfile's default bind host to a loopback interface
#     (127.0.0.1) so a bare `docker run -p 8050:8050` is safe-by-default under
#     the SEC-F22 / D2 startup bind-guard: an unattested non-loopback bind
#     hard-fails at startup, and a published port to a loopback bind is not
#     reachable from outside the container. Deployments that must be reachable
#     through the published port override SERVER__HOST=0.0.0.0 AND attest the
#     perimeter (JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED / _AUTH_PROXY_ATTESTED).
#     Also guards that no attestation flag is baked into the image (an attestation
#     is a conscious, deploy-time operator choice, never an image default).
#
#     Design-of-record: juniper-ml
#     notes/JUNIPER_CANOPY_CONTROL_SURFACE_AUTH_AND_NAT_DESIGN_2026-07-03.md §4 / §8 (D2).
#
#####################################################################################################################################################################################################

"""Regression tests for the Docker default bind host (SEC-F22 / D2)."""

from pathlib import Path

import pytest

# Resolve repo root from this file's location so tests pass regardless of pytest CWD
# (AGENTS.md documents `cd src && pytest tests/`, but CI and IDEs often run from repo root).
_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.regression
@pytest.mark.unit
class TestDockerBindDefault:
    """The root Dockerfile ships a loopback-safe default bind host (SEC-F22 / D2)."""

    def test_root_dockerfile_defaults_to_loopback_host(self):
        dockerfile = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        # Safe-by-default: the baked bind host is loopback.
        assert "ENV JUNIPER_CANOPY_SERVER__HOST=127.0.0.1" in dockerfile

    def test_root_dockerfile_does_not_bake_non_loopback_host(self):
        dockerfile = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        # The old all-interfaces default must not creep back as the image default.
        assert "ENV JUNIPER_CANOPY_SERVER__HOST=0.0.0.0" not in dockerfile

    def test_root_dockerfile_does_not_bake_a_bind_attestation(self):
        dockerfile = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        # An attestation is a conscious deploy-time choice, never an image
        # default: neither flag may be set as an ENV (an explanatory comment that
        # names the flag is fine — hence the ``ENV `` form, not a bare substring).
        assert "ENV JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED" not in dockerfile
        assert "ENV JUNIPER_CANOPY_AUTH_PROXY_ATTESTED" not in dockerfile
        # The retired single-flag attestation is guarded ecosystem-wide by the
        # migration's own tree-grep acceptance check (zero lingering references),
        # so this test deliberately does not re-embed that retired literal here.
