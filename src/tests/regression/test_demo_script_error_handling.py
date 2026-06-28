#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_demo_script_error_handling.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-03-16
# Last Modified: 2026-03-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for the demo startup script's error handling.
#     Validates that juniper_canopy-demo.bash properly detects and reports
#     dependency installation failures instead of silently continuing.
#
#####################################################################################################################################################################################################
# Notes:
#     DS-1: The dependency check section must test the pip exit code
#     DS-2: A pip failure must produce a non-zero exit and error message
#     DS-3: Missing requirements.txt must produce a non-zero exit
#     DS-4: The success message must only appear after a successful pip install
#
#####################################################################################################################################################################################################
# References:
#     Script under test: util/juniper_canopy-demo.bash (lines 107-120)
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     DS-1 through DS-6 initial implementation
#
#####################################################################################################################################################################################################
"""Regression tests for demo startup script error handling and dependency check validation."""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEMO_SCRIPT = PROJECT_ROOT / "util" / "juniper_canopy-demo.bash"


def _read_demo_script():
    """Read the demo startup script content."""
    return DEMO_SCRIPT.read_text()


def _extract_dependency_section(script_content):
    """Extract the dependency checking section from the script.

    Looks for the section between the 'Install/update dependencies' comment
    block and the next major comment block.  Skips the comment block header
    lines (#### borders) that surround the section title.
    """
    lines = script_content.splitlines()
    in_section = False
    past_header = False
    section_lines = []

    for line in lines:
        # Detect start of dependency section
        if "Install/update dependencies" in line:
            in_section = True
            past_header = False
            continue
        if in_section and not past_header:
            # Skip the closing #### border of the header comment block
            if line.startswith("####") and len(line) > 10:
                past_header = True
                continue
            # Skip other comment lines in the header block
            if line.startswith("#"):
                continue
            past_header = True
        # Detect end of section (next major comment block)
        if in_section and past_header and line.startswith("####") and len(line) > 10:
            break
        if in_section and past_header:
            section_lines.append(line)

    return "\n".join(section_lines)


@pytest.mark.regression
@pytest.mark.unit
class TestDemoScriptErrorHandling:
    """Regression tests for demo script dependency error handling."""

    def test_demo_script_exists(self):
        """DS-1: Demo startup script exists."""
        assert DEMO_SCRIPT.exists(), f"Demo script not found at {DEMO_SCRIPT}"

    def test_pip_exit_code_is_checked(self):
        """DS-2: The dependency section must check pip's exit code.

        The original bug was that `pip install` ran without checking its
        return code, so failures were silently ignored.  The fix wraps
        pip install in an `if !` or equivalent conditional.
        """
        section = _extract_dependency_section(_read_demo_script())

        # The section should contain a conditional check around pip install
        # Valid patterns: "if ! pip install", "if pip install ... ; then" with else, etc.
        has_conditional_pip = bool(re.search(r"if\s+!\s+pip\s+install", section) or re.search(r"pip\s+install.*\|\|", section))
        assert has_conditional_pip, "The dependency section must check pip install's exit code. " "Use 'if ! pip install ...' or 'pip install ... || exit 1' " "to detect and handle failures."

    def test_failure_produces_error_message(self):
        """DS-3: A pip failure must produce an error message for the user."""
        section = _extract_dependency_section(_read_demo_script())

        # On failure, the script should print an error indicator
        has_error_output = bool(re.search(r"(✗|Failed|Error|failed|error).*dependenc", section, re.IGNORECASE) or re.search(r"dependenc.*(✗|Failed|Error|failed|error)", section, re.IGNORECASE))
        assert has_error_output, "The dependency section must print an error message when pip install fails."

    def test_failure_exits_nonzero(self):
        """DS-4: A pip failure must cause the script to exit with non-zero status."""
        section = _extract_dependency_section(_read_demo_script())

        # After the pip failure branch, there should be an exit with non-zero code
        has_exit = bool(re.search(r"exit\s+[1-9]", section))
        assert has_exit, "The dependency section must exit with non-zero status when pip install fails."

    def test_success_message_only_on_success(self):
        """DS-5: The success message must only appear in the success branch.

        The original bug had the success message outside the conditional,
        printing even when pip install failed.
        """
        script = _read_demo_script()
        lines = script.splitlines()

        # Find lines with the success indicator and pip install
        pip_install_line = None
        success_line = None
        exit_on_fail_line = None

        for i, line in enumerate(lines):
            stripped = line.strip()
            if "pip install" in stripped and "conf/requirements.txt" in stripped:
                pip_install_line = i
            if "Dependencies up to date" in stripped and pip_install_line is not None:
                success_line = i
            if stripped.startswith("exit") and "1" in stripped and pip_install_line is not None:
                if exit_on_fail_line is None:
                    exit_on_fail_line = i

        assert pip_install_line is not None, "Could not find pip install line"
        assert success_line is not None, "Could not find success message line"

        # The success message must come AFTER the exit-on-failure
        # (meaning it's in the success branch, not unconditional)
        assert exit_on_fail_line is not None, "Could not find exit-on-failure line after pip install"
        assert success_line > exit_on_fail_line, "Success message must appear after the failure exit, " "meaning it's only reached on the success path. " f"Exit on fail is at line {exit_on_fail_line + 1}, " f"success message at line {success_line + 1}."

    def test_missing_requirements_file_handled(self):
        """DS-6: The script must handle a missing requirements.txt gracefully.

        If conf/requirements.txt doesn't exist, the script should report
        an error rather than silently skipping dependency installation.
        """
        section = _extract_dependency_section(_read_demo_script())

        # Check for an else branch that handles missing file
        has_else_for_missing = bool(re.search(r"else", section))
        has_missing_file_error = bool(re.search(r"(not found|missing|does not exist).*requirements", section, re.IGNORECASE) or re.search(r"requirements.*(not found|missing|does not exist)", section, re.IGNORECASE))
        assert has_else_for_missing and has_missing_file_error, "The dependency section must handle a missing requirements.txt " "with an error message, not silently skip it."


# Pattern matching a hard-coded conda-activate of any literal JuniperCanopy* env
# name (the bare unversioned "JuniperCanopy", which does not exist, or a pinned
# "JuniperCanopy1" that re-drifts on the next versioned rebuild). The fix replaces
# these with activation of a dynamically-resolved variable.
_HARDCODED_ACTIVATE = re.compile(r"""conda\s+activate\s+["']?JuniperCanopy""")

# Pattern matching activation of a shell variable (the dynamic-resolution fix),
# e.g. ``conda activate "${CANOPY_ENV_NAME}"``.
_DYNAMIC_ACTIVATE = re.compile(r"""conda\s+activate\s+["']?\$\{?[A-Za-z_]""")


@pytest.mark.regression
@pytest.mark.unit
class TestDemoScriptEnvResolution:
    """Regression tests for the demo script's conda-environment resolution.

    The canopy conda env name is versioned (AGENTS.md): rebuilds increment the
    suffix (JuniperCanopy1, JuniperCanopy2, ...) and rename the old env
    ``*-DEPRECATED``.  The launcher previously hard-coded ``conda activate
    JuniperCanopy`` -- an env that does not exist -- so on-host ``./demo`` died
    at activation.  These guards assert the launcher resolves the live env
    dynamically and never reintroduces a hard-coded name.
    """

    def test_no_hardcoded_canopy_env_activation(self):
        """EV-1: The launcher must not ``conda activate`` a hard-coded JuniperCanopy* literal.

        This is the core regression: it fails on the original
        ``conda activate JuniperCanopy`` (and on any pinned ``JuniperCanopy1``)
        and passes only once activation targets a resolved variable.
        """
        script = _read_demo_script()
        match = _HARDCODED_ACTIVATE.search(script)
        assert match is None, "The demo launcher must not 'conda activate' a hard-coded JuniperCanopy* " f"env name (found: {match.group(0)!r}). The env name is versioned and " "must be resolved dynamically; activate a variable such as " "'conda activate \"${CANOPY_ENV_NAME}\"'."

    def test_activation_uses_resolved_variable(self):
        """EV-2: Activation must target a dynamically-resolved shell variable."""
        script = _read_demo_script()
        assert _DYNAMIC_ACTIVATE.search(script) is not None, "The demo launcher must activate a resolved variable " "(e.g. 'conda activate \"${CANOPY_ENV_NAME}\"'), not a literal env name."

    def test_resolver_discovers_via_conda_env_list(self):
        """EV-3: The launcher must discover the env from ``conda env list``."""
        script = _read_demo_script()
        assert "conda env list" in script, "The launcher must enumerate environments via 'conda env list' to " "discover the live versioned env, rather than assuming a fixed name."

    def test_resolver_excludes_deprecated_envs(self):
        """EV-4: Resolution must exclude ``*-DEPRECATED`` environments."""
        script = _read_demo_script()
        assert "-DEPRECATED" in script, "The env resolver must exclude '*-DEPRECATED' environments so a stale " "deprecated env is never activated."

    def test_unresolved_env_is_fatal(self):
        """EV-5: A failed resolution must abort the launcher (non-zero), not continue.

        The resolver returns non-zero on zero/ambiguous matches and the call
        site guards it with ``|| exit`` so the script never proceeds to launch
        against a missing or ambiguous environment.
        """
        script = _read_demo_script()
        guards_with_exit = bool(re.search(r"resolve_canopy_env\s*\|\|\s*exit", script) or re.search(r"resolve_canopy_env[\s\S]{0,400}?\breturn\s+1\b", script))
        assert guards_with_exit, "A failed env resolution must abort the launcher (e.g. " "'resolve_canopy_env || exit 1'), not silently continue."
