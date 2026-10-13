#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-10-05_w16_w17_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-05
# Last Modified: 2026-10-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Mutation check for the W1.6 / W1.7 recurrence fixes:
#                every new guard must fail on the defect it names.
#####################################################################
"""Mutation check for the W1.6 / W1.7 recurrence fixes (F-C5, F-C6, F-C7, F-C8).

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-05
Status: ad-hoc -- investigation
Retire when: the W1.6 / W1.7 PR is merged and its CHANGELOG entry is released
Related: juniper-ml notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md
    (v1.3.0), items W1.6 / W1.7; the harness is ``2026-09-24_683_validation_mutation_check.py``'s, cut down.

**Why this exists.** A test that passes proves nothing until it has been seen to fail on the defect it names. Each ARM
applies one mutation -- most of them the pre-change code, put back at one site -- to a COPY of the tree and runs the test
files that name it. An arm is CAUGHT only when every test it names fails. The CONTROL (no mutation) must pass every
file in full, or nothing was measured.

The guards are the 683 harness's: the tree is copied per arm and the working tree is never mutated; ``-B`` plus a
per-arm ``PYTHONPYCACHEPREFIX`` keeps ``.pyc`` from crossing arms; a binding probe asserts the modules under test were
imported from the copy (canopy is often editable-installed against another checkout), else NOTHING MEASURED; every
anchor must match exactly once; and an arm naming a test the control did not run fails the run.

Usage (from the repo root, in the canopy conda env)::

    conda run -n JuniperCanopy1 python util/ad-hoc/2026-10-05_w16_w17_mutation_check.py [--jobs 4] [--only NAME ...]

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
ADAPTER = "src/backend/recurrence_service_adapter.py"
REGISTRY = "src/model_registry.py"
DASHBOARD = "src/frontend/dashboard_manager.py"
API_REFERENCE = "docs/api/API_REFERENCE.md"

FILES = {
    "test_recurrence_service_adapter": "src/tests/unit/test_recurrence_service_adapter.py",
    "test_model_registry": "src/tests/unit/test_model_registry.py",
    "test_recurrence_backend": "src/tests/unit/backend/test_recurrence_backend.py",
    "test_completion_reason_status_bar": "src/tests/unit/frontend/test_completion_reason_status_bar.py",
}

W16 = "test_recurrence_service_adapter.TestW16AuthRestoredRateLimit"
VER = "test_recurrence_service_adapter.TestServiceVersion"
REG = "test_model_registry.TestRefreshModelVersions"
RB = "test_recurrence_backend.TestW16RemediesReachTheOperator"
BAR = "test_completion_reason_status_bar.TestFailedRecurrenceFitReason"
BAR_429 = f"{BAR}::test_the_tooltip_holds_a_rate_limited_reason_with_its_wait_uncut"

BINDING_PROBE = '''
"""Written by 2026-10-05_w16_w17_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import model_registry
from backend import recurrence_service_adapter
from frontend import dashboard_manager

ROOT = Path(__file__).resolve().parents[3]


def test_modules_under_test_come_from_this_copy():
    for mod in (model_registry, recurrence_service_adapter, dashboard_manager):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/test_zz_w16w17_binding_probe.py"
PROBE_KEY = "test_zz_w16w17_binding_probe::test_modules_under_test_come_from_this_copy"


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


ARMS = [
    Arm(
        "401-remedy-reverted",
        "F-C5: the pre-change remedy names the setting's Python name",
        [Edit(ADAPTER, '_AUTH_REMEDY = "set JUNIPER_CANOPY_RECURRENCE_API_KEY or JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE to a key the service accepts"', '_AUTH_REMEDY = "check recurrence_api_key"')],
        [
            f"{W16}::test_a_401_remedy_names_both_key_variables",
            f"{W16}::test_a_403_names_both_key_variables_too",
            f"{VER}::test_a_refused_key_on_openapi_is_an_auth_error",
            f"{RB}::test_the_real_adapters_401_remedy_reaches_completion_reason",
        ],
    ),
    Arm(
        "429-is-generic-again",
        "F-C7: the pre-change code -- no 429 branch, so the generic error",
        [Edit(ADAPTER, "        if code == httpx.codes.TOO_MANY_REQUESTS:  # 429\n", "        if False:  # 429\n")],
        [
            f"{W16}::test_a_429_with_retry_after_raises_rate_limited_carrying_the_wait",
            f"{W16}::test_the_wait_alone_reaches_the_message_when_the_reply_has_no_detail",
            f"{W16}::test_a_429_without_retry_after_is_rate_limited_with_the_generic_wording",
            f"{W16}::test_an_http_date_retry_after_is_carried_as_sent",
            f"{W16}::test_a_long_retry_after_is_flattened_and_bounded",
            f"{W16}::test_the_status_route_is_rate_limited_too",
            f"{RB}::test_the_real_adapters_429_wait_reaches_completion_reason",
            f"{BAR_429}[longest-seconds]",
            f"{BAR_429}[cut]",
            f"{BAR_429}[http-date]",
        ],
    ),
    Arm(
        "429-wait-dropped",
        "F-C7: the right type, but the wait never reaches the message",
        [Edit(ADAPTER, "            wait = \"\" if retry_after is None else f\" — retry after {retry_after}{' s' if retry_after.isdigit() else ''}\"\n", '            wait = ""\n')],
        [
            f"{W16}::test_a_429_with_retry_after_raises_rate_limited_carrying_the_wait",
            f"{W16}::test_the_wait_alone_reaches_the_message_when_the_reply_has_no_detail",
            f"{W16}::test_an_http_date_retry_after_is_carried_as_sent",
            f"{W16}::test_the_status_route_is_rate_limited_too",
            f"{RB}::test_the_real_adapters_429_wait_reaches_completion_reason",
            f"{BAR_429}[longest-seconds]",
        ],
    ),
    Arm(
        "retry-after-unbounded",
        "F-C7: a Retry-After of any length rides on the message",
        [Edit(ADAPTER, "    if len(collapsed) > _RETRY_AFTER_MAX_CHARS:\n", "    if False:\n")],
        [f"{W16}::test_a_long_retry_after_is_flattened_and_bounded", f"{BAR_429}[cut]"],
    ),
    Arm(
        "retry-after-lost-on-pickle",
        "F-C7: the fourth value is not kept in args",
        [Edit(ADAPTER, "        super().__init__(message, status_code, body, retry_after)\n", "        super().__init__(message, status_code, body)\n")],
        [f"{W16}::test_rate_limited_round_trips_through_pickle_and_copy", f"{W16}::test_a_429_with_retry_after_raises_rate_limited_carrying_the_wait"],
    ),
    Arm(
        "restored-is-not-a-model",
        "F-C6: the pre-change reading -- only trained counts",
        [Edit(ADAPTER, 'MODEL_PRESENT_STATES: frozenset[str] = frozenset({"trained", "restored"})', 'MODEL_PRESENT_STATES: frozenset[str] = frozenset({"trained"})')],
        [
            f"{W16}::test_a_restored_status_parses_and_reads_as_model_present",
            f"{W16}::test_model_present_is_trained_or_restored_and_nothing_else[restored-True]",
            f"{W16}::test_the_model_present_states_are_exactly_trained_and_restored",
        ],
    ),
    Arm(
        "restored-from-dropped",
        "F-C6: the pre-change parse -- restored_from never read",
        [Edit(ADAPTER, '            restored_from=data.get("restored_from"),\n', "            restored_from=None,\n")],
        [f"{W16}::test_a_restored_status_parses_and_reads_as_model_present"],
    ),
    Arm(
        "no-openapi-fallback",
        "F-C8: health only -- what the plan's premise assumed; 0.5.0's health has no version",
        [Edit(ADAPTER, '        info = self._call("GET", "/openapi.json", self._status_timeout).get("info")\n', "        info = None\n")],
        [
            f"{VER}::test_without_one_the_openapi_info_version_is_read",
            f"{VER}::test_a_health_version_that_is_not_one_falls_through_to_openapi[empty]",
            f"{VER}::test_a_health_version_that_is_not_one_falls_through_to_openapi[null]",
            f"{VER}::test_a_refused_key_on_openapi_is_an_auth_error",
            f"{REG}::test_the_live_services_shape_is_read_from_openapi",
        ],
    ),
    Arm(
        "health-version-ignored",
        "F-C8: a health body that names the version is not read",
        [Edit(ADAPTER, '        version = _version_text(self._call("GET", "/v1/health", self._status_timeout).get("version"))\n', '        version = _version_text(self._call("GET", "/v1/health", self._status_timeout).get("no-such-key"))\n')],
        [
            f"{VER}::test_a_version_in_the_health_body_is_the_answer",
            f"{VER}::test_surrounding_whitespace_is_stripped",
            f"{REG}::test_the_version_is_read_from_a_fake_health_payload",
        ],
    ),
    Arm(
        "blank-version-accepted",
        "F-C8: a blank version string counts as an answer",
        [Edit(ADAPTER, "    if isinstance(value, str) and value.strip():\n        return value.strip()\n", "    if isinstance(value, str):\n        return value.strip()\n")],
        [
            f"{VER}::test_a_health_version_that_is_not_one_falls_through_to_openapi[empty]",
            f"{VER}::test_a_health_version_that_is_not_one_falls_through_to_openapi[blank]",
            f"{VER}::test_no_version_on_either_surface_raises[blank-version]",
        ],
    ),
    Arm(
        "seed-hard-codes-0.1.0",
        "F-C8: the pre-change seed",
        [Edit(REGISTRY, '        version="",  # service-reported', '        version="0.1.0",  # service-reported')],
        [f"{REG}::test_the_recurrence_seed_hard_codes_no_version", f"{REG}::test_only_the_version_changes_and_the_seed_is_untouched"],
    ),
    Arm(
        "registry-raises",
        "F-C8: a failed lookup escapes the registry",
        [Edit(REGISTRY, "    except Exception as exc:  # noqa: BLE001 -- a version is a label: the registry never raises for one\n", "    except ZeroDivisionError as exc:  # noqa: BLE001 -- mutated\n")],
        [
            f"{REG}::test_a_timed_out_lookup_is_labelled_not_raised",
            f"{REG}::test_an_unreachable_service_is_labelled_not_raised",
            f"{REG}::test_any_raising_source_is_labelled_not_raised",
        ],
    ),
    Arm(
        "registry-asks-per-model",
        "F-C8: no cache -- one lookup per model rather than per refresh",
        [Edit(REGISTRY, "        if spec.provider not in reported:\n", "        if True:\n")],
        [f"{REG}::test_each_source_is_asked_once_per_refresh"],
    ),
    Arm(
        "registry-accepts-blank",
        "F-C8: a blank answer becomes the version",
        [Edit(REGISTRY, "    if isinstance(version, str) and version.strip():\n        return version.strip()\n", "    if isinstance(version, str):\n        return version.strip()\n")],
        [f"{REG}::test_an_answer_that_is_not_a_version_is_labelled[empty]", f"{REG}::test_an_answer_that_is_not_a_version_is_labelled[blank]"],
    ),
    Arm(
        "tooltip-bound-400",
        "F-C5 knock-on: the pre-change bound cuts a 401 / 403 reason",
        [Edit(DASHBOARD, "    _FAILURE_REASON_TOOLTIP_MAX_CHARS = 480\n", "    _FAILURE_REASON_TOOLTIP_MAX_CHARS = 400\n")],
        [
            f"{BAR}::test_the_tooltip_holds_every_reason_the_adapter_can_build_uncut[401]",
            f"{BAR}::test_the_tooltip_holds_every_reason_the_adapter_can_build_uncut[403]",
        ],
    ),
    Arm(
        "docs-floor-missing",
        "F-C8: the API reference stops naming the contract floor",
        [Edit(API_REFERENCE, "written against **juniper-recurrence 0.5.0**", "written against **juniper-recurrence**")],
        [f"{VER}::test_the_contract_floor_is_0_5_0_and_the_docs_name_it"],
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


def files_for(keys: list[str]) -> list[str]:
    return sorted({FILES[key.split("::")[0].split(".")[0]] for key in keys})


def run(root: Path, tag: str, files: list[str]) -> tuple[dict[str, str], int]:
    """Run ``files`` in ``root``; return ({key: status}, pytest exit code)."""
    junit = root / f"junit-{tag}.xml"
    env = dict(os.environ, LIBTORCH="", LD_LIBRARY_PATH="", PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    for var in ("JUNIPER_CANOPY_RECURRENCE_API_KEY", "JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE", "JUNIPER_RECURRENCE_API_KEY", "JUNIPER_RECURRENCE_API_KEY_FILE"):
        env.pop(var, None)
    for var in [name for name in env if "SENTRY" in name.upper()]:
        env.pop(var, None)
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=600", f"--junitxml={junit}", *files, PROBE_REL]
    proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)  # nosec B603 -- fixed argv, local copy
    (root / f"pytest-{tag}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
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
        results, _rc = run(root, arm.name, files_for(arm.expect_fail))
        if results.get(PROBE_KEY) != "passed":
            return f"{arm.name}: NOTHING MEASURED -- binding probe did not pass", False, ["NOTHING-MEASURED"]
        survived = [t for t in arm.expect_fail if results.get(t) == "passed"]
        extra = sorted(t for t, v in results.items() if v != "passed" and t not in arm.expect_fail)
        if survived:
            return f"{arm.name}: SURVIVED -- still passing: {survived}", False, []
        return f"{arm.name}: CAUGHT by {len(arm.expect_fail)} named test(s); {len(extra)} other(s) also failing  [{arm.why}]", True, [f"    also failing: {t}" for t in extra[:12]]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jobs", type=int, default=4, help="arms run in parallel (default 4)")
    parser.add_argument("--only", nargs="*", default=None, help="run only the named arms")
    args = parser.parse_args()
    arms = [arm for arm in ARMS if not args.only or arm.name in args.only]
    work = Path(tempfile.mkdtemp(prefix="w16w17-mutation-"))
    try:
        control = work / "control"
        copy_tree(control)
        results, rc = run(control, "control", sorted(FILES.values()))
        bad = sorted(k for k, v in results.items() if v != "passed")
        skipped = sorted(k for k, v in results.items() if v == "skipped")
        print(f"CONTROL: pytest exit {rc}, {len(results)} test(s), {len(bad)} not passing ({len(skipped)} skipped)")
        if rc != 0 or [k for k in bad if k not in skipped] or not results or results.get(PROBE_KEY) != "passed":
            print("NOTHING MEASURED -- the control must pass in full, from this copy:", bad or "(no results / binding failed)")
            print((control / "pytest-control.log").read_text(encoding="utf-8")[-6000:])
            return 2
        known = {k for k, v in results.items() if v == "passed"}
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            outcomes = list(pool.map(lambda pair: run_arm(work, pair[0], pair[1], known), enumerate(arms)))
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
        print(f"{caught}/{len(arms)} mutations caught")
        if nothing_measured:
            return 2
        return 0 if caught == len(arms) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
