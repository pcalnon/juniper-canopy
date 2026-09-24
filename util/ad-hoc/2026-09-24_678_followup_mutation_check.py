#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-24_678_followup_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-24
# Last Modified: 2026-09-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   #678 follow-up -- prove each new test FAILS on the
#                defect it claims to catch.
#####################################################################
"""Mutation check for the juniper-canopy#678 follow-up's tests.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-24
Status: ad-hoc -- investigation
Retire when: the #678 follow-up is merged
Related: juniper-canopy#678 (squash 05f2dfc2); util/ad-hoc/2026-09-23_blank_api_key_warning_mutation_check.py,
    whose M5/M6 anchors (``report_blank_api_key(system_logger)`` in main.py) the follow-up's lifespan change removed.

**Why this exists.** A test that passes proves nothing until it has been seen to fail on the defect it names. #678's
boot test passed against mutant V8 -- main.py building its handler without ``get_api_key_auth()`` -- and so did the
whole CI lane. Each ARM below applies one mutation to a COPY of the tree and runs the test files that carry the
follow-up's tests. An arm is CAUGHT only when every test it names fails. The CONTROL arm (no mutation) must pass in
full, or nothing was measured.

**How the harness avoids lying** (the guards of ``2026-09-23_blank_api_key_warning_mutation_check.py``):

* The tree is COPIED per arm; the working tree is never mutated.
* ``-B`` plus a per-arm ``PYTHONPYCACHEPREFIX``, so no ``.pyc`` crosses arms.
* juniper-canopy is often EDITABLE-installed against another checkout, so every arm runs a binding probe asserting
  the modules under test were imported from the copy. If it fails, the run reports NOTHING MEASURED, never a pass.
  (The fresh-interpreter tests check their own child's ``main.__file__`` against the copy.)
* Every anchor must match exactly once. An anchor that rots fails the run.
* An arm that names a test the control did not run fails the run, so a renamed test cannot make an arm vacuous.

Usage (from the repo root, in the canopy conda env)::

    python util/ad-hoc/2026-09-24_678_followup_mutation_check.py [--jobs 4]

Exit status: 0 = control passed and every arm was caught; 1 = an arm survived or an anchor failed; 2 = nothing was
measured (the control failed or a binding probe failed).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # nosec B404 -- runs pytest on a local copy of this repo
import sys
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 -- parses the JUnit XML this script wrote
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAIN = "src/main.py"
SECURITY = "src/security.py"
SECRETS = "src/secrets_util.py"
INTERNAL = "src/frontend/internal_api.py"
TESTS = [
    "src/tests/unit/test_security.py",
    "src/tests/unit/test_secrets_util.py",
    "src/tests/unit/frontend/test_internal_api_key_rules.py",
    "src/tests/unit/frontend/test_internal_api_gate_coverage.py",
    "src/tests/regression/test_blank_api_key_warning_boot.py",
    "src/tests/regression/test_auth_posture_boot_check.py",
]

TS = "test_security.TestSecurityModuleFunctions"
SU = "test_secrets_util.TestResolveSecret"
SD = "test_secrets_util.TestResolveSecretDetail"
IA = "test_internal_api_key_rules"
BOOT = "test_blank_api_key_warning_boot"

# The parameter ids the tests declare (test_internal_api_key_rules.py, test_security.py).
BLANK_IDS = ["empty", "space", "3-spaces", "tab", "space-tab-space", "lf", "crlf", "nbsp", "nel", "fs-us", "em-space"]
NONEMPTY_BLANK_IDS = BLANK_IDS[1:]
REFUSED_IDS = ["leading-space", "leading-tab", "both-sides", "trailing-lf", "trailing-crlf", "inner-crlf", "inner-lf", "leading-nbsp", "leading-fs", "leading-em-space"]
PADDED_IDS = ["leading-space", "leading-tab", "trailing-space", "trailing-tab", "trailing-lf", "trailing-crlf", "inner-crlf", "inner-lf", "trailing-vt"]


def params(prefix: str, test: str, ids: list[str]) -> list[str]:
    return [f"{prefix}::{test}[{case_id}]" for case_id in ids]


BOOT_REFUSED = params(BOOT, "test_blank_key_warns_when_require_auth_refuses_the_boot", ["env", "file"])
BOOT_ORDER = f"{BOOT}::test_lifespan_reports_right_after_the_posture_check"
BOOT_SINGLETON = f"{BOOT}::test_a_fresh_process_builds_its_auth_handler_through_get_api_key_auth"
BOOT_SYSTEM_LOG = f"{BOOT}::test_a_fresh_boot_writes_the_blank_key_warning_to_system_log_once"
BOOT_DOCS = f"{BOOT}::test_a_whitespace_only_env_key_serves_the_docs_exactly_as_no_key_does"
BOOT_SELF_CALL = f"{BOOT}::test_a_whitespace_only_env_key_puts_no_key_on_a_self_call"
BOOT_LEAK = f"{BOOT}::test_a_padded_key_never_reaches_a_log_record"
BOOT_PADDED = f"{BOOT}::test_a_padded_key_warns_once_at_boot"
BOOT_MISSING = f"{BOOT}::test_a_missing_key_file_warns_once_at_boot"
TS_REFUSED = params(TS, "test_a_refused_boot_gets_the_refused_wording", ["env", "file"])
GET_SECRET = f"{SU}::test_get_secret_returns_exactly_the_resolved_value"

BINDING_PROBE = '''
"""Written by 2026-09-24_678_followup_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import main
import secrets_util
import security
from frontend import internal_api

ROOT = Path(__file__).resolve().parents[3]


def test_modules_under_test_come_from_this_copy():
    for mod in (main, secrets_util, security, internal_api):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/test_zz_678_followup_binding_probe.py"
PROBE_KEY = "test_zz_678_followup_binding_probe::test_modules_under_test_come_from_this_copy"

REFUSED_HANDLER = "    except AuthPostureError:\n        report_api_key_configuration(system_logger, boot_refused=True)\n        raise\n"
REFUSED_BRANCH = (
    "    if boot_refused:\n"
    '        log.warning(_BLANK_KEY_FILE_REFUSED_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_REFUSED_WARNING)\n'
    "    else:\n"
    '        log.warning(_BLANK_KEY_FILE_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_WARNING)\n'
)
PADDED_TEST = r'    return api_key != api_key.strip() or "\r" in api_key or "\n" in api_key' + "\n"
ONCE_GUARD = "        if _key_findings_reported:\n            missing_file_var = padded_source = None\n        else:\n            _key_findings_reported = True\n            missing_file_var, padded_source = _missing_key_file_var, _padded_key_source\n"
SELF_CALL_KEY = '    key = get_secret("CANOPY_API_KEY")\n    if not key or not key.strip():\n        return None\n    if not _requests_can_send(key):\n        return None\n    return key\n'


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
    # Item 1 -- the WARNING depends on main.py building its handler through get_api_key_auth().
    Arm(
        "V8-handler-built-without-get_api_key_auth",
        "the validator's V8: main.py builds APIKeyAuth itself, so the key read records nothing and no WARNING fires",
        [Edit(MAIN, "\napi_key_auth = get_api_key_auth()\n", '\nfrom security import APIKeyAuth as _AKA\n\napi_key_auth = _AKA([_k] if (_k := get_secret("CANOPY_API_KEY")) else None)\n')],
        [BOOT_SINGLETON, BOOT_SYSTEM_LOG],
    ),
    # Item 2 -- the refused boot (JUNIPER_CANOPY_REQUIRE_AUTH=true).
    Arm(
        "refused-boot-unreported",
        "#678's behaviour: the posture check raises and nothing reports the blank key",
        [Edit(MAIN, REFUSED_HANDLER, "    except AuthPostureError:\n        raise\n")],
        [*BOOT_REFUSED, BOOT_ORDER],
    ),
    Arm(
        "refused-boot-open-wording",
        "the refused boot is reported with the open-boot text, which says routes serve without a key",
        [Edit(MAIN, "        report_api_key_configuration(system_logger, boot_refused=True)\n", "        report_api_key_configuration(system_logger)\n")],
        [*BOOT_REFUSED, BOOT_ORDER],
    ),
    Arm(
        "refusal-swallowed",
        "the handler reports and does not re-raise: a secured profile boots OPEN",
        [Edit(MAIN, "        report_api_key_configuration(system_logger, boot_refused=True)\n        raise\n", "        report_api_key_configuration(system_logger, boot_refused=True)\n")],
        [*BOOT_REFUSED, BOOT_ORDER],
    ),
    Arm(
        "report-before-the-posture-check",
        "the report moves ahead of enforce_auth_posture: a refused boot gets the open text, before its CRITICAL",
        [
            Edit(MAIN, '    _canopy_api_key = get_secret("CANOPY_API_KEY")\n    try:\n', '    _canopy_api_key = get_secret("CANOPY_API_KEY")\n    report_api_key_configuration(system_logger)\n    try:\n'),
            Edit(MAIN, "        report_api_key_configuration(system_logger, boot_refused=True)\n", ""),
            Edit(MAIN, "        raise\n\n    report_api_key_configuration(system_logger)\n\n", "        raise\n\n"),
        ],
        [*BOOT_REFUSED, BOOT_ORDER],
    ),
    Arm(
        "refused-flag-ignored",
        "report_blank_api_key ignores boot_refused and always logs the open-boot text",
        [Edit(SECURITY, REFUSED_BRANCH, '    log.warning(_BLANK_KEY_FILE_WARNING if source == "CANOPY_API_KEY_FILE" else _BLANK_KEY_ENV_WARNING)\n')],
        [*TS_REFUSED, *BOOT_REFUSED],
    ),
    Arm(
        "refused-text-claims-routes-serve",
        "text form: the refused wording says every route serves without a key; caught only because the tests do not import the text",
        [Edit(SECURITY, 'and because JUNIPER_CANOPY_REQUIRE_AUTH is true, canopy refuses to start."', 'and every route serves without a key."')],
        [*TS_REFUSED, *BOOT_REFUSED],
    ),
    # Item 3 -- the key's two other readers apply the blank rule.
    Arm(
        "docs-switch-reads-the-raw-key",
        "the pre-follow-up _docs_enabled: a whitespace-only env key keeps the docs routes at 404",
        [Edit(MAIN, '_docs_enabled = not (get_secret("CANOPY_API_KEY") or "").strip()\n', '_docs_enabled = not get_secret("CANOPY_API_KEY")\n')],
        [BOOT_DOCS],
    ),
    Arm(
        "self-call-drops-the-blank-rule",
        "internal_api maps only an EMPTY key to None; caught with requests' own refusal taken away, which hides it today",
        [Edit(INTERNAL, "    if not key or not key.strip():\n        return None\n", "    if not key:\n        return None\n")],
        params(IA, "test_a_blank_key_is_no_key_whatever_requests_would_send", NONEMPTY_BLANK_IDS),
    ),
    # Item 6 -- the leak, and the two boot WARNINGs.
    Arm(
        "self-call-sends-a-key-requests-refuses",
        "the leak: a key requests refuses is handed to it, and InvalidHeader quotes it into the handlers' logs",
        [Edit(INTERNAL, "    if not _requests_can_send(key):\n        return None\n", "")],
        [
            *params(IA, "test_a_key_requests_refuses_to_send_is_left_off_the_self_call", REFUSED_IDS),
            *params(IA, "test_every_self_call_header_set_is_one_requests_can_send", REFUSED_IDS),
            BOOT_LEAK,
        ],
    ),
    Arm(
        "self-call-reads-the-key-raw",
        "the pre-follow-up internal_api: `key or None` -- blank keys sent, and padded keys leaked",
        [Edit(INTERNAL, SELF_CALL_KEY, '    key = get_secret("CANOPY_API_KEY")\n    return key or None\n')],
        [
            BOOT_SELF_CALL,
            BOOT_LEAK,
            *params(IA, "test_a_blank_key_puts_no_key_on_a_self_call", NONEMPTY_BLANK_IDS),
            *params(IA, "test_a_key_requests_refuses_to_send_is_left_off_the_self_call", REFUSED_IDS),
            *params(IA, "test_every_self_call_header_set_is_one_requests_can_send", NONEMPTY_BLANK_IDS + REFUSED_IDS),
        ],
    ),
    Arm(
        "no-padded-key-finding",
        "a padded key is never recorded, so boot says nothing about it",
        [Edit(SECURITY, "            _padded_key_source = source if api_key is not None and _api_key_auth.enabled and _is_padded_key(api_key) else None\n", "            _padded_key_source = None\n")],
        [
            BOOT_PADDED,
            *params(TS, "test_a_padded_env_key_warns_and_keeps_auth_enabled_as_set", PADDED_IDS),
            f"{TS}::test_a_key_padded_with_a_non_ascii_space_warns_too",
            f"{TS}::test_a_key_file_var_naming_no_file_warns_before_the_key_findings[env-padded]",
            f"{TS}::test_every_finding_is_reported_once[padded]",
            f"{TS}::test_no_finding_logs_the_key_or_the_path",
            f"{TS}::test_the_report_needs_no_second_read_of_the_secret",
            f"{TS}::test_reset_security_state_clears_every_recorded_finding",
        ],
    ),
    Arm(
        "padding-misses-a-line-break",
        "only leading/trailing whitespace counts: a key with a line break inside it goes unreported",
        [Edit(SECURITY, PADDED_TEST, "    return api_key != api_key.strip()\n")],
        params(TS, "test_a_padded_env_key_warns_and_keeps_auth_enabled_as_set", ["inner-crlf", "inner-lf"]),
    ),
    Arm(
        "padding-flags-inner-whitespace",
        "over-correction: whitespace INSIDE a key, which HTTP carries intact, is reported as padding",
        [Edit(SECURITY, PADDED_TEST, "    return api_key != api_key.strip() or any(c.isspace() for c in api_key)\n")],
        params(TS, "test_a_clean_key_gets_no_padded_key_warning", ["inner-space", "inner-tab"]),
    ),
    Arm(
        "no-missing-key-file-finding",
        "a CANOPY_API_KEY_FILE naming no file is ignored silently again",
        [Edit(SECRETS, "        missing_file_var = file_env_var\n", "        pass\n")],
        [
            BOOT_MISSING,
            *params(TS, "test_a_key_file_var_naming_no_file_warns_before_the_key_findings", ["env-real", "env-unset", "env-blank", "env-padded"]),
            f"{TS}::test_a_key_file_var_naming_a_directory_names_no_file",
            *params(TS, "test_every_finding_is_reported_once", ["blank", "padded"]),
            f"{TS}::test_no_finding_logs_the_key_or_the_path",
            f"{TS}::test_the_report_needs_no_second_read_of_the_secret",
            f"{TS}::test_reset_security_state_clears_every_recorded_finding",
            *params(SD, "test_a_file_var_naming_no_file_is_named", ["env-set", "env-unset"]),
            f"{SD}::test_a_file_var_naming_a_directory_is_named",
            f"{SD}::test_the_custom_file_var_is_the_name_given",
            f"{SD}::test_the_detail_carries_names_never_the_path",
        ],
    ),
    Arm(
        "missing-file-warning-logs-the-path",
        "the WARNING also logs the path the _FILE variable holds -- the key itself, for an operator who confused the two",
        [Edit(SECURITY, "        log.warning(_MISSING_KEY_FILE_WARNING)\n", '        log.warning(_MISSING_KEY_FILE_WARNING + " (CANOPY_API_KEY_FILE=%s)", __import__("os").environ.get("CANOPY_API_KEY_FILE"))\n')],
        [BOOT_LEAK, BOOT_MISSING, f"{TS}::test_no_finding_logs_the_key_or_the_path"],
    ),
    Arm(
        "padded-warning-logs-the-key",
        "the padded-key WARNING also logs %r of the key",
        [Edit(SECURITY, "        log.warning(_PADDED_KEY_WARNING)\n", '        log.warning(_PADDED_KEY_WARNING + " (key: %r)", __import__("os").environ.get("CANOPY_API_KEY"))\n')],
        [BOOT_LEAK, BOOT_PADDED, f"{TS}::test_no_finding_logs_the_key_or_the_path"],
    ),
    Arm(
        "findings-reported-every-startup",
        "the once-guard dropped: every startup repeats the missing-file and padded-key WARNINGs",
        [Edit(SECURITY, ONCE_GUARD, "        missing_file_var, padded_source = _missing_key_file_var, _padded_key_source\n")],
        params(TS, "test_every_finding_is_reported_once", ["blank", "padded"]),
    ),
    # Item 5 -- get_secret's test asserts literal values, so it moves with no mutant of the resolution.
    Arm(
        "V2-file-contents-not-stripped",
        "the validator's V2: a secret file's contents are returned unstripped",
        [Edit(SECRETS, "            return SecretResolution(path.read_text().strip(), file_env_var, None)\n", "            return SecretResolution(path.read_text(), file_env_var, None)\n")],
        [f"{GET_SECRET}[file]", f"{GET_SECRET}[blank-file]"],
    ),
    Arm(
        "V3-env-var-stripped",
        "the validator's V3: the env var is returned stripped",
        [Edit(SECRETS, "    value = os.environ.get(env_var)\n", "    value = os.environ.get(env_var)\n    value = value.strip() if value is not None else None\n")],
        [f"{GET_SECRET}[padded-env]"],
    ),
    Arm(
        "V5-a-blank-file-loses-precedence",
        "the validator's V5: a blank secret file falls through to the env var",
        [Edit(SECRETS, "        if path.is_file():\n", "        if path.is_file() and path.read_text().strip():\n")],
        [f"{GET_SECRET}[blank-file]"],
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
    for var in ("CANOPY_API_KEY", "CANOPY_API_KEY_FILE", "JUNIPER_CANOPY_REQUIRE_AUTH", "JUNIPER_SKIP_AUTH_POSTURE_CHECK"):
        env.pop(var, None)
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=300", f"--junitxml={junit}", *TESTS, PROBE_REL]
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


def run_arm(work: Path, index: int, arm: Arm, known: set[str]) -> tuple[str, bool, list[str]]:
    """Returns (verdict line, caught, extra lines)."""
    unknown = [t for t in arm.expect_fail if t not in known]
    if unknown:
        return f"{arm.name}: EXPECTED TESTS MISSING -- {unknown}", False, []
    root = work / f"arm{index:02d}"
    copy_tree(root)
    try:
        err = mutate(root, arm)
        if err:
            return f"{arm.name}: ANCHOR FAILED -- {err}", False, []
        results, _rc = run(root, arm.name)
        if results.get(PROBE_KEY) != "passed":
            return f"{arm.name}: NOTHING MEASURED -- binding probe did not pass", False, ["NOTHING-MEASURED"]
        survived = [t for t in arm.expect_fail if results.get(t) == "passed"]
        extra = sorted(t for t, v in results.items() if v != "passed" and t not in arm.expect_fail)
        if survived:
            return f"{arm.name}: SURVIVED -- still passing: {survived}", False, []
        return f"{arm.name}: CAUGHT by {len(arm.expect_fail)} named test(s); {len(extra)} other(s) also failing  [{arm.why}]", True, [f"    also failing: {t}" for t in extra]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jobs", type=int, default=4, help="arms run in parallel (default 4)")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="678-followup-mutation-"))
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
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            outcomes = list(pool.map(lambda pair: run_arm(work, pair[0], pair[1], known), enumerate(ARMS)))
        caught = 0
        nothing_measured = False
        for line, ok, extra in outcomes:
            print(line)
            for item in extra:
                if item == "NOTHING-MEASURED":
                    nothing_measured = True
                else:
                    print(item)
            caught += int(ok)
        print(f"{caught}/{len(ARMS)} mutations caught")
        if nothing_measured:
            return 2
        return 0 if caught == len(ARMS) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
