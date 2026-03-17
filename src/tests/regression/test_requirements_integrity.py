#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_requirements_integrity.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-03-16
# Last Modified: 2026-03-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for requirements file integrity.  Validates that
#     requirements files specify the correct index URLs for packages
#     that require non-PyPI sources (e.g. PyTorch +cpu builds).
#
#####################################################################################################################################################################################################
# Notes:
#     RQ-1: torch +cpu builds require --extra-index-url for the PyTorch CPU index
#     RQ-2: requirements files must be parseable (no syntax errors)
#     RQ-3: conf/requirements.txt and conf/requirements_ci.txt must both be valid
#     RQ-4: the demo startup script must check pip exit codes
#
#####################################################################################################################################################################################################
# References:
#     PyTorch CPU-only index: https://download.pytorch.org/whl/cpu
#     pip requirements file format: https://pip.pypa.io/en/stable/reference/requirements-file-format/
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     RQ-1 through RQ-7 initial implementation
#
#####################################################################################################################################################################################################

import re
from pathlib import Path

import pytest

# Project root: juniper-canopy/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# All requirements files to validate
REQUIREMENTS_FILES = [
    PROJECT_ROOT / "conf" / "requirements.txt",
    PROJECT_ROOT / "conf" / "requirements_ci.txt",
]

PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def _parse_requirements(filepath):
    """Parse a requirements file into (index_urls, package_specs) tuple.

    Returns:
        tuple: (list of extra-index-url values, list of (package_name, version_spec) tuples)
    """
    index_urls = []
    packages = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Capture --extra-index-url directives
            if line.startswith("--extra-index-url"):
                url = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
                index_urls.append(url.strip())
                continue
            # Skip other pip options (e.g. --find-links)
            if line.startswith("-"):
                continue
            # Parse package==version or package>=version etc.
            match = re.match(r"^([A-Za-z0-9_.-]+)\s*(.*)", line)
            if match:
                packages.append((match.group(1).lower(), match.group(2)))

    return index_urls, packages


@pytest.mark.regression
@pytest.mark.unit
class TestRequirementsIntegrity:
    """Regression tests for requirements file integrity."""

    @pytest.mark.parametrize("req_file", REQUIREMENTS_FILES, ids=lambda p: p.name)
    def test_requirements_file_exists(self, req_file):
        """RQ-1: Requirements file exists and is readable."""
        assert req_file.exists(), f"{req_file} does not exist"
        assert req_file.stat().st_size > 0, f"{req_file} is empty"

    @pytest.mark.parametrize("req_file", REQUIREMENTS_FILES, ids=lambda p: p.name)
    def test_requirements_file_parseable(self, req_file):
        """RQ-2: Requirements file can be parsed without errors."""
        if not req_file.exists():
            pytest.skip(f"{req_file} does not exist")
        index_urls, packages = _parse_requirements(req_file)
        assert len(packages) > 0, f"{req_file} contains no package specifications"

    @pytest.mark.parametrize("req_file", REQUIREMENTS_FILES, ids=lambda p: p.name)
    def test_torch_cpu_has_extra_index_url(self, req_file):
        """RQ-3: When torch+cpu is specified, the PyTorch CPU index URL must be present.

        This is the primary regression test for the demo mode startup failure
        caused by pip being unable to find torch==X.Y.Z+cpu without the
        --extra-index-url pointing to PyTorch's CPU-only package index.
        """
        if not req_file.exists():
            pytest.skip(f"{req_file} does not exist")

        index_urls, packages = _parse_requirements(req_file)

        # Find torch entries with +cpu variant
        torch_cpu_specs = [(name, spec) for name, spec in packages if name == "torch" and "+cpu" in spec]

        if not torch_cpu_specs:
            # No +cpu torch specified — nothing to validate
            return

        # If +cpu torch is present, the PyTorch CPU index must also be present
        assert PYTORCH_CPU_INDEX in index_urls, f"{req_file.name} specifies torch with +cpu build " f"({torch_cpu_specs[0][1]}) but is missing " f"'--extra-index-url {PYTORCH_CPU_INDEX}'. " f"The +cpu variant is only available from the PyTorch CPU index."

    def test_root_requirements_is_symlink_to_conf(self):
        """RQ-4: Root requirements.txt is a symlink to conf/requirements.txt."""
        root_req = PROJECT_ROOT / "requirements.txt"
        conf_req = PROJECT_ROOT / "conf" / "requirements.txt"
        if not root_req.exists():
            pytest.skip("Root requirements.txt does not exist")
        assert root_req.is_symlink(), "Root requirements.txt should be a symlink to conf/requirements.txt"
        assert root_req.resolve() == conf_req.resolve(), f"Root requirements.txt symlink target mismatch: " f"expected {conf_req}, got {root_req.resolve()}"

    @pytest.mark.parametrize("req_file", REQUIREMENTS_FILES, ids=lambda p: p.name)
    def test_no_duplicate_packages(self, req_file):
        """RQ-5: No package should appear more than once in a requirements file."""
        if not req_file.exists():
            pytest.skip(f"{req_file} does not exist")

        _, packages = _parse_requirements(req_file)
        seen = {}
        duplicates = []
        for name, spec in packages:
            if name in seen:
                duplicates.append(f"{name} (first: {seen[name]}, duplicate: {spec})")
            else:
                seen[name] = spec

        assert not duplicates, f"{req_file.name} has duplicate package entries: {', '.join(duplicates)}"

    def test_ci_requirements_has_torch(self):
        """RQ-6: CI requirements must include torch for test compatibility."""
        ci_req = PROJECT_ROOT / "conf" / "requirements_ci.txt"
        if not ci_req.exists():
            pytest.skip("CI requirements file does not exist")

        _, packages = _parse_requirements(ci_req)
        torch_packages = [name for name, _ in packages if name == "torch"]
        assert len(torch_packages) > 0, "CI requirements file must include torch for test compatibility"

    def test_ci_requirements_has_cpu_index_url(self):
        """RQ-7: CI requirements must include the PyTorch CPU index URL."""
        ci_req = PROJECT_ROOT / "conf" / "requirements_ci.txt"
        if not ci_req.exists():
            pytest.skip("CI requirements file does not exist")

        index_urls, _ = _parse_requirements(ci_req)
        assert PYTORCH_CPU_INDEX in index_urls, f"CI requirements file must include " f"'--extra-index-url {PYTORCH_CPU_INDEX}' for CPU-only torch builds"
