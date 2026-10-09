#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-10-08_w15_w17_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# Last Modified: 2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Mutation check for W1.5's canopy half and W1.7's
#                display half: every new guard must fail on the
#                defect it names.
#####################################################################
"""Mutation check for W1.5's canopy half (F-C4, F-CON1, F-CON2) and W1.7's display half (F-C8).

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-08
Status: ad-hoc -- investigation
Retire when: the W1.5 / W1.7 canopy PR is merged and its CHANGELOG entry is released
Related: juniper-ml notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md
    (v1.4.1), items W1.5 and W1.7; the harness is ``2026-10-05_w16_w17_mutation_check.py``'s, unchanged in its guards.

**Why this exists.** A test that passes proves nothing until it has been seen to fail on the defect it names. Each ARM
applies one mutation -- most of them the pre-change behaviour, or the shortcut the plan warns against ("``state ==
trained`` is success") -- to a COPY of the tree and runs the test files that name it. An arm is CAUGHT only when every
test it names fails. The CONTROL (no mutation) must pass every file in full, or nothing was measured.

The guards are the earlier harness's: the tree is copied per arm and the working tree is never mutated; ``-B`` plus a
per-arm ``PYTHONPYCACHEPREFIX`` keeps ``.pyc`` from crossing arms; a binding probe asserts the modules under test were
imported from the copy (canopy is often editable-installed against another checkout), else NOTHING MEASURED; every
anchor must match exactly once; and an arm naming a test the control did not run fails the run.

Usage (from the repo root, in the canopy conda env)::

    conda run -n JuniperCanopy1 python util/ad-hoc/2026-10-08_w15_w17_mutation_check.py [--jobs 4] [--only NAME ...]

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
BACKEND = "src/backend/recurrence_backend.py"
DASHBOARD = "src/frontend/dashboard_manager.py"
MAIN = "src/main.py"

FILES = {
    "test_recurrence_operation_identity": "src/tests/unit/test_recurrence_operation_identity.py",
    "test_recurrence_backend_upstream": "src/tests/unit/backend/test_recurrence_backend_upstream.py",
    "test_recurrence_version_display": "src/tests/regression/test_recurrence_version_display.py",
    "test_recurrence_service_adapter": "src/tests/unit/test_recurrence_service_adapter.py",
    "test_model_select": "src/tests/regression/test_model_select.py",
}

RACES = "test_recurrence_operation_identity.TestTheFourRaces"
BLIND = "test_recurrence_operation_identity.TestNeverSucceededBlindly"
NAMED = "test_recurrence_operation_identity.TestTheRequestIsNamed"
BUSY = "test_recurrence_operation_identity.TestTheBusy409"
OP_RACES = "test_recurrence_backend_upstream.TestTheFourRacesReachTheOperator"
FOLLOW = "test_recurrence_backend_upstream.TestFollowingAFitUpstream"
EVERY = "test_recurrence_backend_upstream.TestEveryFitIsNamed"
DISPLAY = "test_recurrence_version_display.TestTheDisplayedVersionIsTheServices"
NOWAIT = "test_recurrence_version_display.TestNothingWaitsOnTheLookup"
STARTUP = "test_recurrence_version_display.TestStartupAsksTheConfiguredService"
SHOWS = "test_recurrence_version_display.TestWhereTheVersionShows"

BINDING_PROBE = '''
"""Written by 2026-10-08_w15_w17_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import main
from backend import recurrence_backend, recurrence_service_adapter
from frontend import dashboard_manager

ROOT = Path(__file__).resolve().parents[3]


def test_modules_under_test_come_from_this_copy():
    for mod in (main, recurrence_backend, recurrence_service_adapter, dashboard_manager):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/test_zz_w15w17_binding_probe.py"
PROBE_KEY = "test_zz_w15w17_binding_probe::test_modules_under_test_come_from_this_copy"


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
        "trained-alone-is-success",
        "W1.5: whose operation it was is never asked -- a status that says trained is canopy's success",
        [Edit(ADAPTER, '    if status.requested_by != request_id or status.operation not in (None, "train"):\n', "    if False:\n")],
        [
            f"{BLIND}::test_anything_less_is_unknown[another-callers-fit]",
            f"{BLIND}::test_trained_alone_never_settles_it",
            f"{FOLLOW}::test_another_callers_model_after_a_timeout_is_not_canopys",
        ],
    ),
    Arm(
        "a-restore-counts-as-a-fit",
        "W1.5: the operation kind is not checked, so a restore carrying canopy's id reads as canopy's fit",
        [Edit(ADAPTER, '    if status.requested_by != request_id or status.operation not in (None, "train"):\n', "    if status.requested_by != request_id:\n")],
        [f"{BLIND}::test_anything_less_is_unknown[a-restore-with-canopys-id]"],
    ),
    Arm(
        "the-model-producer-is-not-checked",
        "W1.5: canopy's operation is enough -- whose model the service holds is not asked",
        [Edit(ADAPTER, "    if status.model_present and status.operation_id is not None and status.model_operation_id == status.operation_id:\n", "    if status.model_present:\n")],
        [f"{BLIND}::test_anything_less_is_unknown[model-from-another-operation]", f"{BLIND}::test_anything_less_is_unknown[no-model-named]"],
    ),
    Arm(
        "a-timeout-is-recorded-failed",
        "F-C4, the pre-change code: a read timeout fails the fit instead of following it",
        [Edit(BACKEND, "            if isinstance(exc, RecurrenceServiceTimeoutError) and exc.reply_pending:\n", "            if False:\n")],
        [
            f"{OP_RACES}::test_race_timeout_then_success",
            f"{OP_RACES}::test_race_timeout_then_failure",
            f"{OP_RACES}::test_race_timeout_then_unreachable",
            f"{FOLLOW}::test_the_window_closing_is_unknown_never_success",
            f"{FOLLOW}::test_a_0_5_0_service_after_a_timeout_is_unknown",
        ],
    ),
    Arm(
        "no-request-id-is-sent",
        "F-CON2: the train request is anonymous, so a timed-out caller cannot find its own operation",
        [Edit(ADAPTER, "        headers = {REQUEST_ID_HEADER: request_id} if request_id else None\n", "        headers = None\n")],
        [
            f"{NAMED}::test_the_request_id_goes_out_as_x_request_id",
            f"{RACES}::test_race_timeout_then_success",
            f"{OP_RACES}::test_race_timeout_then_success",
            f"{EVERY}::test_each_fit_sends_its_own_request_id",
        ],
    ),
    Arm(
        "the-busy-holder-is-ignored",
        "F-CON1, the pre-change code: a 409 object detail is str()-ed, naming nobody",
        [Edit(ADAPTER, "            holder = _busy_holder(response)\n", "            holder = None\n")],
        [f"{RACES}::test_race_409_from_another_caller", f"{OP_RACES}::test_race_409_from_another_caller", f"{BUSY}::test_a_restore_holder_is_named_as_one"],
    ),
    Arm(
        "the-old-string-409-changes",
        "W1.5: the published 0.5.0's string detail is no longer read as before",
        [
            Edit(
                ADAPTER,
                '            raise RecurrenceTrainInProgressError(f"recurrence training already in progress ({method} {path}){suffix}", status_code=code, body=response.text)\n',
                '            raise RecurrenceTrainInProgressError(f"recurrence training already in progress ({method} {path}) — {_BUSY_REMEDY}{suffix}", status_code=code, body=response.text)\n',
            )
        ],
        [
            f"{BUSY}::test_the_old_string_detail_is_tolerated_unchanged",
            f"{EVERY}::test_the_old_string_409_still_fails_with_its_old_wording",
            "test_recurrence_service_adapter.TestServiceDetailInTheMessage::test_409_keeps_its_wording_and_appends_the_detail",
        ],
    ),
    Arm(
        "unreachable-reads-as-failed",
        "W1.5: an unreadable status is reported as the fit failing",
        [Edit(ADAPTER, "            return RecurrenceTrainOutcome(OUTCOME_UNKNOWN, reason, error=exc)\n", "            return RecurrenceTrainOutcome(OUTCOME_FAILED, reason, error=exc)\n")],
        [f"{RACES}::test_race_timeout_then_unreachable", f"{OP_RACES}::test_race_timeout_then_unreachable"],
    ),
    Arm(
        "a-5xx-failure-detail-leaks",
        "the #683 rule broken on the new path: a 5xx failure's detail reaches the reason",
        [
            Edit(
                ADAPTER,
                '    detail = _render_detail({"detail": failure.detail}) if failure is not None and code is not None and httpx.codes.is_client_error(code) else None\n',
                '    detail = _render_detail({"detail": failure.detail}) if failure is not None else None\n',
            )
        ],
        [f"{RACES}::test_a_5xx_failure_keeps_its_detail_off_the_reason[500]", f"{RACES}::test_a_5xx_failure_keeps_its_detail_off_the_reason[502]", f"{RACES}::test_a_5xx_failure_keeps_its_detail_off_the_reason[503]"],
    ),
    Arm(
        "every-timeout-is-reply-pending",
        "W1.5: a connect timeout -- the request never sent -- is followed as though the service had it",
        [Edit(ADAPTER, "reply_pending=isinstance(exc, httpx.ReadTimeout)) from exc\n", "reply_pending=True) from exc\n")],
        [f"{RACES}::test_a_connect_timeout_never_reached_the_service", f"{FOLLOW}::test_a_connect_timeout_fails_without_following"],
    ),
    Arm(
        "the-follow-window-never-closes",
        "W1.5: the follower polls forever; a fit still running is never reported",
        [Edit(BACKEND, "                if time.monotonic() >= deadline:\n", "                if False:\n")],
        [f"{FOLLOW}::test_the_window_closing_is_unknown_never_success"],
    ),
    Arm(
        "a-single-blip-settles",
        "W1.5: one failed status read ends the following, dropping a fit that may still finish",
        [Edit(BACKEND, "_RECONCILE_READ_ATTEMPTS = 3\n", "_RECONCILE_READ_ATTEMPTS = 1\n")],
        [f"{FOLLOW}::test_a_single_unreadable_read_is_not_a_verdict", f"{FOLLOW}::test_a_read_that_answers_resets_the_count"],
    ),
    Arm(
        "running-upstream-is-not-said",
        "W1.5: a followed fit reads as an ordinary fit in flight",
        [Edit(BACKEND, '        if state == "training" and upstream:\n', "        if False:\n")],
        [f"{FOLLOW}::test_while_followed_the_fit_is_running_upstream"],
    ),
    Arm(
        "the-bar-says-stopped",
        "W1.5: an unknown outcome renders as Stopped",
        [Edit(DASHBOARD, '        elif status_data.get("outcome_unknown", False):\n', "        elif False:\n")],
        [f"{OP_RACES}::test_race_timeout_then_unreachable"],
    ),
    Arm(
        "selection-asks-nothing",
        "F-C8 display half, the pre-change state: no production caller on selection",
        [Edit(MAIN, "    if version_source is not None:\n        _schedule_model_version_refresh(version_source)\n", "    if False:\n        _schedule_model_version_refresh(version_source)\n")],
        [
            f"{DISPLAY}::test_the_displayed_version_comes_from_the_fake_service",
            f"{DISPLAY}::test_the_next_selection_response_carries_it",
            f"{DISPLAY}::test_a_failed_lookup_is_labelled_not_hidden",
        ],
    ),
    Arm(
        "startup-asks-nothing",
        "F-C8 display half, the pre-change state: no production caller at startup",
        [Edit(MAIN, "    _start_model_version_refresh()\n", "    pass\n")],
        [f"{STARTUP}::test_the_lifespan_calls_it"],
    ),
    Arm(
        "shutdown-waits-on-the-refresh",
        "W1.7: shutdown awaits an unfinished lookup instead of abandoning it",
        [Edit(MAIN, "        refresh.cancel()\n", "        pass\n")],
        [f"{STARTUP}::test_shutdown_abandons_an_unfinished_refresh"],
    ),
    Arm(
        "the-selection-waits-on-the-lookup",
        "W1.7: the selection response blocks on the service's answer",
        [Edit(MAIN, "        _schedule_model_version_refresh(version_source)\n", "        await _refresh_model_versions(version_source)\n")],
        [f"{NOWAIT}::test_the_selection_answers_while_the_lookup_is_in_flight"],
    ),
    Arm(
        "the-version-key-is-always-sent",
        "W1.7: a payload key that is not optional -- every pre-W1.7 client sees a changed shape",
        [Edit(MAIN, "    if reported is not None and reported.version:\n        payload[\"version\"] = reported.version\n", "    payload[\"version\"] = reported.version if reported is not None else None\n")],
        [f"{SHOWS}::test_no_version_until_a_service_reports_one", "test_model_select::test_model_state_response_unknown_model_status"],
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
    for var in ("JUNIPER_CANOPY_RECURRENCE_API_KEY", "JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE", "JUNIPER_RECURRENCE_API_KEY", "JUNIPER_RECURRENCE_API_KEY_FILE", "JUNIPER_CANOPY_RECURRENCE_SERVICE_URL"):
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
    work = Path(tempfile.mkdtemp(prefix="w15w17-mutation-"))
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
