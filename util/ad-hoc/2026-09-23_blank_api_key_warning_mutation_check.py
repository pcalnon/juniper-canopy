#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-23_blank_api_key_warning_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-23
# Last Modified: 2026-09-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   APD-ECO-008 follow-up -- prove the blank-key WARNING
#                tests FAIL on each defect they claim to catch.
#####################################################################
"""Mutation check for the set-but-blank ``CANOPY_API_KEY`` WARNING tests.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-23
Status: ad-hoc -- investigation
Retire when: the APD-ECO-008 follow-up to juniper-canopy#660 is merged
Related: juniper-canopy#660 (squash 3a6dea95); APD-ECO-008 (juniper-ml defect register)

**Why this exists.** A test that passes proves nothing until it has been seen to fail on
the defect it names. #660's own test passed against a WARNING that fired on every call,
against one that logged ``%r`` of the value, and against one logged before logging was
configured. Each ARM below applies one mutation to a COPY of the tree and runs the three
test files that carry the WARNING tests. An arm is CAUGHT only when every test it names
fails. The CONTROL arm (no mutation) must pass in full, or nothing was measured.

**How the harness avoids lying** (the same four guards as
``2026-09-22_f053_mutation_check.py``):

* The tree is COPIED per arm; the working tree is never mutated.
* ``-B`` plus a per-arm ``PYTHONPYCACHEPREFIX``, so no ``.pyc`` crosses arms.
* juniper-canopy is often EDITABLE-installed against another checkout, so every arm runs
  a binding probe asserting the modules under test were imported from the copy. If it
  fails, the run reports NOTHING MEASURED, never a pass.
* Every anchor must match exactly once. An anchor that rots fails the run.

Usage (from the repo root, in the canopy conda env)::

    python util/ad-hoc/2026-09-23_blank_api_key_warning_mutation_check.py

Exit status: 0 = control passed and every arm was caught; 1 = an arm survived or an
anchor failed; 2 = nothing was measured (the control failed or a binding probe failed).
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404 -- runs pytest on a local copy of this repo
import sys
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 -- parses the JUnit XML this script wrote
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SECURITY = "src/security.py"
MAIN = "src/main.py"
SECRETS = "src/secrets_util.py"
TESTS = [
    "src/tests/unit/test_security.py",
    "src/tests/unit/test_secrets_util.py",
    "src/tests/regression/test_blank_api_key_warning_boot.py",
]

TS = "test_security.TestSecurityModuleFunctions"
SU = "test_secrets_util.TestResolveSecret"
BOOT = "test_blank_api_key_warning_boot"
BOOT_ENV = f"{BOOT}::test_blank_key_warns_once_through_the_configured_logger[env]"
BOOT_FILE = f"{BOOT}::test_blank_key_warns_once_through_the_configured_logger[file]"
BOOT_ORDER = f"{BOOT}::test_lifespan_reports_right_after_the_posture_check"

BINDING_PROBE = '''
"""Written by 2026-09-23_blank_api_key_warning_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import main
import secrets_util
import security

ROOT = Path(__file__).resolve().parents[3]


def test_modules_under_test_come_from_this_copy():
    for mod in (main, secrets_util, security):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/test_zz_blank_key_binding_probe.py"
PROBE_KEY = "test_zz_blank_key_binding_probe::test_modules_under_test_come_from_this_copy"

REPORT_LINE = '    log.warning(_BLANK_KEY_FILE_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_WARNING)\n'
LIFESPAN_REPORT = "    from security import report_blank_api_key\n\n    report_blank_api_key(system_logger)\n"
FILE_ADVICE = " While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."


@dataclass
class Edit:
    path: str
    old: str  # a literal, matched exactly once
    new: str


@dataclass
class Arm:
    name: str
    why: str
    edits: list[Edit]
    expect_fail: list[str] = field(default_factory=list)


ARMS: list[Arm] = [
    Arm(
        "M1-fires-on-every-call",
        "REQUESTED: the once-guard dropped, so every report call (every startup) logs again",
        [Edit(SECURITY, "        if _blank_key_source is None or _blank_key_reported:\n", "        if _blank_key_source is None:\n")],
        [f"{TS}::test_the_blank_key_warning_is_logged_exactly_once", BOOT_ENV, BOOT_FILE],
    ),
    Arm(
        "M1b-every-read-rearms-it",
        "the #660 shape moved one step: every get_api_key_auth() call re-arms the WARNING",
        [Edit(SECURITY, "            _blank_key_reported = False\n    return _api_key_auth\n", "    _blank_key_reported = False\n    return _api_key_auth\n")],
        [f"{TS}::test_the_blank_key_warning_is_logged_exactly_once"],
    ),
    Arm(
        "M2-logs-repr-of-the-value",
        "REQUESTED: the WARNING also logs %r of the configured value",
        [Edit(SECURITY, REPORT_LINE, '    log.warning((_BLANK_KEY_FILE_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_WARNING) + " (configured value: %r)", resolve_secret("CANOPY_API_KEY")[0])\n')],
        [
            f"{TS}::test_set_but_blank_key_logs_a_distinct_warning[env]",
            f"{TS}::test_set_but_blank_key_logs_a_distinct_warning[file]",
            f"{TS}::test_a_blank_file_beats_a_real_env_key_and_the_advice_names_the_file",
            f"{TS}::test_a_file_var_naming_no_file_leaves_the_env_var_the_source",
            f"{TS}::test_blank_key_report_needs_no_second_read_of_the_secret",
            BOOT_ENV,
            BOOT_FILE,
        ],
    ),
    Arm(
        "M3a-file-source-gets-the-env-advice",
        "REQUESTED: a blank FILE is told to unset CANOPY_API_KEY -- #660's advice, wrong for a file",
        [Edit(SECURITY, REPORT_LINE, "    log.warning(_BLANK_KEY_ENV_WARNING)\n")],
        [f"{TS}::test_set_but_blank_key_logs_a_distinct_warning[file]", f"{TS}::test_a_blank_file_beats_a_real_env_key_and_the_advice_names_the_file", BOOT_FILE],
    ),
    Arm(
        "M3b-file-advice-text-rewritten",
        "REQUESTED (text form): the file message's own advice rewritten to #660's; caught only because the tests do not import the text",
        [Edit(SECURITY, FILE_ADVICE, " Set a real key, or unset CANOPY_API_KEY for an intentional open profile.")],
        [f"{TS}::test_set_but_blank_key_logs_a_distinct_warning[file]", f"{TS}::test_a_blank_file_beats_a_real_env_key_and_the_advice_names_the_file", BOOT_FILE],
    ),
    Arm(
        "M4-logged-where-the-key-is-read",
        "#660's placement: the WARNING is emitted by get_api_key_auth(), i.e. at import, before configure_logging",
        [Edit(SECURITY, "            _blank_key_reported = False\n    return _api_key_auth\n", '            _blank_key_reported = False\n        report_blank_api_key(__import__("logger.logger", fromlist=["get_system_logger"]).get_system_logger())\n    return _api_key_auth\n')],
        [f"{TS}::test_reading_the_key_logs_nothing", BOOT_ENV, BOOT_FILE],
    ),
    Arm(
        "M5-lifespan-never-reports",
        "the lifespan call is dropped: a blank key is never reported",
        [Edit(MAIN, LIFESPAN_REPORT, "    from security import report_blank_api_key  # noqa: F401\n")],
        [BOOT_ENV, BOOT_FILE, BOOT_ORDER],
    ),
    Arm(
        "M6-reported-before-configure-logging",
        "the report runs before configure_logging: it reaches only the last-resort handler again",
        [
            Edit(MAIN, LIFESPAN_REPORT, ""),
            Edit(MAIN, "    configure_logging(settings.log_level, settings.log_format, \"juniper-canopy\")\n", "    from security import report_blank_api_key\n\n    report_blank_api_key(system_logger)\n    configure_logging(settings.log_level, settings.log_format, \"juniper-canopy\")\n"),
        ],
        [BOOT_ENV, BOOT_FILE, BOOT_ORDER],
    ),
    Arm(
        "M7-file-source-misnamed",
        "resolve_secret names the env var when the file supplied the value",
        [Edit(SECRETS, "            return path.read_text().strip(), file_env_var\n", "            return path.read_text().strip(), env_var\n")],
        [
            f"{TS}::test_set_but_blank_key_logs_a_distinct_warning[file]",
            f"{TS}::test_a_blank_file_beats_a_real_env_key_and_the_advice_names_the_file",
            BOOT_FILE,
            f"{SU}::test_file_source_is_named_and_its_value_stripped",
            f"{SU}::test_a_blank_file_still_wins_over_the_env_var",
            f"{SU}::test_custom_file_env_var_is_the_name_reported",
        ],
    ),
    Arm(
        "M8-report-reads-the-secret-again",
        "the report re-derives blankness from a second read instead of the recorded source",
        [Edit(SECURITY, "        source = _blank_key_source\n", '        value, source = resolve_secret("CANOPY_API_KEY")\n        if value is None or value.strip():\n            return False\n')],
        [f"{TS}::test_blank_key_report_needs_no_second_read_of_the_secret"],
    ),
]


def copy_tree(dest: Path) -> None:
    # symlinks=True: notes/ carries dangling links, which copying the target would trip on.
    shutil.copytree(REPO, dest, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", "*.pyc", "logs"))
    (dest / PROBE_REL).write_text(BINDING_PROBE, encoding="utf-8")


def mutate(root: Path, arm: Arm) -> str | None:
    """Apply every edit of ``arm``; return an error string when an anchor does not match exactly once."""
    for edit in arm.edits:
        target = root / edit.path
        text = target.read_text(encoding="utf-8")
        n = text.count(edit.old)
        if n != 1:
            return f"{edit.path}: anchor matched {n} time(s), expected 1: {edit.old[:80]!r}"
        target.write_text(text.replace(edit.old, edit.new), encoding="utf-8")
    return None


def case_key(classname: str, name: str) -> str:
    """``test_module.TestClass::test`` (or ``test_module::test`` at module level)."""
    parts = classname.split(".")
    if len(parts) >= 2 and parts[-1].startswith("Test"):
        return f"{parts[-2]}.{parts[-1]}::{name}"
    return f"{parts[-1]}::{name}"


def run(root: Path, tag: str) -> tuple[dict[str, str], int]:
    """Run the test files in ``root``; return ({key: status}, pytest exit code)."""
    junit = root / f"junit-{tag}.xml"
    env = dict(os.environ, LIBTORCH="", LD_LIBRARY_PATH="", PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    for var in ("CANOPY_API_KEY", "CANOPY_API_KEY_FILE"):
        env.pop(var, None)
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=120", f"--junitxml={junit}", *TESTS, PROBE_REL]
    proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)  # nosec B603 -- fixed argv, local copy
    results: dict[str, str] = {}
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):  # nosec B314 -- our own output
            status = "passed"
            for child in case:
                if child.tag in ("failure", "error", "skipped"):
                    status = child.tag
            results[case_key(case.get("classname", ""), case.get("name", ""))] = status
    return results, proc.returncode


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="blank-key-mutation-"))
    try:
        control = work / "control"
        copy_tree(control)
        results, rc = run(control, "control")
        bad = sorted(k for k, v in results.items() if v != "passed")
        print(f"CONTROL: pytest exit {rc}, {len(results)} test(s), {len(bad)} not passing")
        if rc != 0 or bad or not results or results.get(PROBE_KEY) != "passed":
            print("NOTHING MEASURED -- the control must pass in full, from this copy:", bad or "(no results / binding failed)")
            return 2
        known = set(results)
        caught, failures = 0, []
        for i, arm in enumerate(ARMS):
            unknown = [t for t in arm.expect_fail if t not in known]
            if unknown:
                failures.append(f"{arm.name}: names tests that do not exist: {unknown}")
                print(f"{arm.name}: EXPECTED TESTS MISSING -- {unknown}")
                continue
            root = work / f"arm{i}"
            copy_tree(root)
            err = mutate(root, arm)
            if err:
                failures.append(f"{arm.name}: ANCHOR FAILED -- {err}")
                print(f"{arm.name}: ANCHOR FAILED -- {err}")
                continue
            results, _rc = run(root, arm.name)
            if results.get(PROBE_KEY) != "passed":
                print(f"{arm.name}: NOTHING MEASURED -- binding probe did not pass")
                return 2
            survived = [t for t in arm.expect_fail if results.get(t) == "passed"]
            extra = sorted(t for t, v in results.items() if v != "passed" and t not in arm.expect_fail)
            if survived:
                failures.append(f"{arm.name}: SURVIVED -- {survived}")
                print(f"{arm.name}: SURVIVED -- still passing: {survived}")
            else:
                caught += 1
                print(f"{arm.name}: CAUGHT by {len(arm.expect_fail)} named test(s); {len(extra)} other(s) also failing  [{arm.why}]")
                for t in extra:
                    print(f"    also failing: {t}")
            shutil.rmtree(root, ignore_errors=True)
        print(f"{caught}/{len(ARMS)} mutations caught")
        return 0 if caught == len(ARMS) and not failures else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
