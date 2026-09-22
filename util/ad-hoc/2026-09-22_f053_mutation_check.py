#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-22_f053_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-22
# Last Modified: 2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   F-CANOPY-053 -- prove the new wiring tests FAIL on each
#                defect they claim to catch, including the literal #613
#                shape (a running= guard on the tab-gated lane's
#                ``disabled``).
#####################################################################
"""Mutation check for the F-CANOPY-053 wiring tests.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-22
Status: ad-hoc -- investigation
Retire when: F-CANOPY-053 is validated live and closed in the E2E ledger
Related: F-CANOPY-053 (provisional id); canopy#613 / canopy#614 (the precedent)

**Why this exists.** A wiring test that passes proves nothing until it has been seen to
fail on the defect it names. Each ARM below applies one mutation to a COPY of the tree
and runs the two test files that carry the new tests. An arm is CAUGHT only when every
test it names fails. The CONTROL arm (no mutation) must pass in full, or nothing was
measured.

**Four ways this kind of harness lies, and what is done about each:**

* The tree is COPIED per arm. The working tree is never mutated, so there is nothing
  to restore and no chance of a ``git checkout`` wiping real edits.
* ``-B`` plus a per-arm ``PYTHONPYCACHEPREFIX``. A stale ``.pyc`` compiled from a
  different arm cannot be picked up.
* juniper-canopy is often EDITABLE-installed against another checkout, so an import can
  silently resolve outside the copy. Every arm runs a binding probe that asserts the
  modules under test were imported from the copy. If it fails, the arm reports
  NOTHING-MEASURED, never a pass.
* Every anchor must match exactly the stated number of times. An anchor that rots
  fails the run; it is not skipped.

Usage (from the repo root, in the canopy conda env)::

    LIBTORCH= LD_LIBRARY_PATH= python util/ad-hoc/2026-09-22_f053_mutation_check.py

Exit status: 0 = control passed and every arm was caught; 1 = an arm survived or an
anchor failed; 2 = nothing was measured (the control failed or a binding probe failed).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404 -- runs pytest on a local copy of this repo
import sys
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 -- parses the JUnit XML this script wrote
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
PANEL = "src/frontend/components/candidate_metrics_panel.py"
DASH = "src/frontend/dashboard_manager.py"
TESTS = ["src/tests/unit/frontend/test_poll_gating.py", "src/tests/unit/frontend/test_stage2_global_lane.py"]

S2 = "TestF053CandidateStatePollStopsItsOwnClock"
WD = "TestCandidateStrandWatchdog"
RG = "TestRunningGuardsNeverContendWithTheTabGate"

BINDING_PROBE = '''
"""Written by 2026-09-22_f053_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import canopy_constants
from frontend import dashboard_manager
from frontend.components import candidate_metrics_panel

ROOT = Path(__file__).resolve().parents[4]


def test_modules_under_test_come_from_this_copy():
    for mod in (canopy_constants, dashboard_manager, candidate_metrics_panel):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/frontend/test_zz_f053_binding_probe.py"


@dataclass
class Arm:
    name: str
    why: str
    path: Optional[str] = None
    pattern: Optional[str] = None
    repl: Optional[str] = None
    count: int = 1
    expect_fail: List[str] = field(default_factory=list)


ARMS: List[Arm] = [
    Arm(
        "M1-guard-removed",
        "the F-CANOPY-053 defect itself: no running= guard at all",
        PANEL,
        r'            running=\[\(Output\(f"\{self\.component_id\}-update-interval", "max_intervals"\), 0, -1\)\],\n',
        "",
        1,
        [f"{S2}::test_poll_stops_its_own_clock_while_in_flight", f"{S2}::test_guard_never_writes_the_tab_gates_disabled_prop", f"{RG}::test_no_running_guard_writes_a_tab_gated_disabled_prop"],
    ),
    Arm(
        "M2-guard-on-disabled",
        "the literal #613 shape on this TAB-GATED lane -- would re-arm the poller on every tab switch",
        PANEL,
        r'"max_intervals"\), 0, -1\)\]',
        '"disabled"), True, False)]',
        1,
        [f"{S2}::test_poll_stops_its_own_clock_while_in_flight", f"{S2}::test_guard_never_writes_the_tab_gates_disabled_prop", f"{RG}::test_no_running_guard_writes_a_tab_gated_disabled_prop"],
    ),
    Arm(
        "M3-guard-engages-with-bool",
        "False == 0 in Python, but the renderer compares max_intervals with ===",
        PANEL,
        r'"max_intervals"\), 0, -1\)\]',
        '"max_intervals"), False, -1)]',
        1,
        [f"{S2}::test_poll_stops_its_own_clock_while_in_flight"],
    ),
    Arm(
        "M4-layout-drops-max-intervals",
        "the guarded interval no longer declares max_intervals=-1",
        PANEL,
        r"                    max_intervals=-1,\n",
        "",
        1,
        [f"{S2}::test_the_guarded_interval_exists_and_starts_unlimited"],
    ),
    Arm(
        "M5-second-consumer-of-the-interval",
        "another callback takes the guarded interval as an Input and is silenced by every fetch",
        PANEL,
        r'\[Input\(f"\{self\.component_id\}-training-state-store", "data"\)\],\n            prevent_initial_call=False,\n        \)\n        def update_status_display\(state\):',
        '[Input(f"{self.component_id}-training-state-store", "data"), Input(f"{self.component_id}-update-interval", "n_intervals")],\n            prevent_initial_call=False,\n        )\n        def update_status_display(state, _n=None):',
        1,
        [f"{S2}::test_the_guarded_interval_drives_nothing_else"],
    ),
    Arm(
        "M6-watchdog-removed",
        "#614's strand repair not extended: a network failure freezes the panel for the page's life",
        DASH,
        r"        # F-CANOPY-053 \(provisional id\): THE SAME STRAND, ON THE CANDIDATE PANEL'S GUARD\..*?prevent_initial_call=True,\n        \)\n",
        "",
        1,
        [
            f"{WD}::test_watchdog_exists_and_is_single_output",
            f"{WD}::test_watchdog_rides_an_existing_lane_and_adds_no_poller",
            f"{WD}::test_watchdog_reads_the_guarded_prop_and_the_clamp_as_state",
            f"{WD}::test_watchdog_only_ever_releases_the_guard",
            f"{WD}::test_watchdog_never_fires_while_the_apply_clamp_is_engaged",
            f"{WD}::test_watchdog_keeps_its_own_strand_clock",
            f"{WD}::test_threshold_is_interpolated_into_the_javascript",
        ],
    ),
    Arm(
        "M7-watchdog-shares-the-metrics-clock",
        "the two watchdogs share one window global, so each clears the other's clock",
        DASH,
        r"window\.__candidateStateGuardSince",
        "window.__metricsStoreDisabledSince",
        5,
        [f"{WD}::test_watchdog_keeps_its_own_strand_clock"],
    ),
    Arm(
        "M8-watchdog-watches-the-gate",
        "the watchdog reads the tab gate's disabled, not the prop the guard holds",
        DASH,
        r'dash\.dependencies\.State\(_CANDIDATE_STATE_INTERVAL, "max_intervals"\),',
        'dash.dependencies.State(_CANDIDATE_STATE_INTERVAL, "disabled"),',
        1,
        [f"{WD}::test_watchdog_reads_the_guarded_prop_and_the_clamp_as_state"],
    ),
    Arm(
        "M9-watchdog-can-engage-the-guard",
        "the watchdog writes 0, i.e. can stop the lane itself",
        DASH,
        r"return -1;",
        "return 0;",
        1,
        [f"{WD}::test_watchdog_only_ever_releases_the_guard"],
    ),
    Arm(
        "M10-watchdog-ignores-the-apply-clamp",
        "the watchdog no longer holds off while apply-in-flight is set",
        DASH,
        r"if \(maxIntervals !== 0 \|\| Boolean\(applyInFlight\)\) \{\{",
        "if (maxIntervals !== 0) {{",
        1,
        [f"{WD}::test_watchdog_never_fires_while_the_apply_clamp_is_engaged"],
    ),
]


def copy_tree(dest: Path) -> None:
    # symlinks=True: notes/ carries dangling links, which copying the target would trip on.
    shutil.copytree(REPO, dest, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", "*.pyc"))
    (dest / PROBE_REL).write_text(BINDING_PROBE, encoding="utf-8")


def mutate(root: Path, arm: Arm) -> Optional[str]:
    """Apply ``arm``; return an error string when the anchor does not match exactly."""
    target = root / arm.path
    text = target.read_text(encoding="utf-8")
    new, n = re.subn(arm.pattern, lambda _m: arm.repl, text, flags=re.S)
    if n != arm.count:
        return f"anchor matched {n} time(s), expected {arm.count}"
    target.write_text(new, encoding="utf-8")
    return None


def run(root: Path, tag: str) -> Tuple[dict, int]:
    """Run the test files in ``root``; return ({'Class::test': status}, pytest exit code)."""
    junit = root / f"junit-{tag}.xml"
    env = dict(os.environ, LIBTORCH="", LD_LIBRARY_PATH="", PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=120", f"--junitxml={junit}", *TESTS, PROBE_REL]
    proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)  # nosec B603 -- fixed argv, local copy
    results = {}
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):  # nosec B314 -- our own output
            cls = case.get("classname", "").rsplit(".", 1)[-1]
            status = "passed"
            for child in case:
                if child.tag in ("failure", "error", "skipped"):
                    status = child.tag
            results[f"{cls}::{case.get('name')}"] = status
    return results, proc.returncode


def bound(results: dict) -> bool:
    return results.get("test_zz_f053_binding_probe::test_modules_under_test_come_from_this_copy") == "passed"


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="f053-mutation-"))
    try:
        control = work / "control"
        copy_tree(control)
        results, rc = run(control, "control")
        bad = sorted(k for k, v in results.items() if v != "passed")
        print(f"CONTROL: pytest exit {rc}, {len(results)} test(s), {len(bad)} not passing")
        if rc != 0 or bad or not results or not bound(results):
            print("NOTHING MEASURED -- the control must pass in full, from this copy:", bad or "(no results / binding failed)")
            return 2
        known = set(results)
        caught, failures = 0, []
        for i, arm in enumerate(ARMS):
            root = work / f"arm{i}"
            copy_tree(root)
            err = mutate(root, arm)
            if err:
                failures.append(f"{arm.name}: ANCHOR FAILED -- {err}")
                print(f"{arm.name}: ANCHOR FAILED -- {err}")
                continue
            unknown = [t for t in arm.expect_fail if t not in known]
            if unknown:
                failures.append(f"{arm.name}: names tests that do not exist: {unknown}")
                print(f"{arm.name}: EXPECTED TESTS MISSING -- {unknown}")
                continue
            results, _rc = run(root, arm.name)
            if not bound(results):
                print(f"{arm.name}: NOTHING MEASURED -- binding probe did not pass")
                return 2
            survived = [t for t in arm.expect_fail if results.get(t) == "passed"]
            extra = sorted(t for t, v in results.items() if v != "passed" and t not in arm.expect_fail)
            if survived:
                failures.append(f"{arm.name}: SURVIVED -- {survived}")
                print(f"{arm.name}: SURVIVED -- still passing: {survived}")
            else:
                caught += 1
                print(f"{arm.name}: CAUGHT by {len(arm.expect_fail)} test(s); also failing: {extra or 'none'}  [{arm.why}]")
        print(f"{caught}/{len(ARMS)} mutations caught")
        return 0 if caught == len(ARMS) and not failures else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
