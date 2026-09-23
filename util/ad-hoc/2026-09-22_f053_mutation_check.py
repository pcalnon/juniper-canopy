#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-22_f053_mutation_check.py
# Author:        Paul Calnon
# Version:       0.2.0
# Date:          2026-09-22
# Last Modified: 2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   F-CANOPY-053 -- prove the new tests FAIL on each defect
#                they claim to catch, including both rejected guard
#                shapes (#613's ``disabled`` guard, and a
#                ``max_intervals`` guard) on the tab-gated lane.
#####################################################################
"""Mutation check for the F-CANOPY-053 tests.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-22
Status: ad-hoc -- investigation
Retire when: F-CANOPY-053 is validated live and closed in the E2E ledger
Related: F-CANOPY-053 (provisional id); canopy#613 / canopy#614 (the rejected precedent)

**Why this exists.** A test that passes proves nothing until it has been seen to fail on
the defect it names. Each ARM below applies one mutation to a COPY of the tree and runs
the four test files that carry the F-CANOPY-053 tests. An arm is CAUGHT only when every
test it names fails. The CONTROL arm (no mutation) must pass in full, or nothing was
measured.

**Four ways this kind of harness lies, and what is done about each:**

* The tree is COPIED per arm. The working tree is never mutated, so there is nothing to
  restore and no chance of a ``git checkout`` wiping real edits.
* ``-B`` plus a per-arm ``PYTHONPYCACHEPREFIX``. A stale ``.pyc`` from another arm
  cannot be picked up.
* juniper-canopy is often EDITABLE-installed against another checkout, so an import can
  silently resolve outside the copy. Every arm runs a binding probe that asserts the
  modules under test were imported from the copy. If it fails, the run reports
  NOTHING-MEASURED, never a pass.
* Every anchor must match exactly the stated number of times. An anchor that rots fails
  the run; it is not skipped.

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
from typing import Callable, List, Optional, Tuple, Union

REPO = Path(__file__).resolve().parents[2]
PANEL = "src/frontend/components/candidate_metrics_panel.py"
CONSTANTS = "src/canopy_constants.py"
TESTS = [
    "src/tests/unit/frontend/test_poll_gating.py",
    "src/tests/unit/frontend/test_stage2_global_lane.py",
    "src/tests/unit/frontend/test_candidate_metrics_panel.py",
    "src/tests/unit/frontend/test_candidate_metrics_panel_gate_coverage.py",
]

WIRE = "test_stage2_global_lane.TestF053CandidateStatePollWiring"
RULE = "test_poll_gating.TestRunningGuardsNeverContendWithTheTabGate"
BEHAVE = "test_candidate_metrics_panel_gate_coverage.TestF053StateStoreWritesOnlyRealChanges"
LEGACY = "test_candidate_metrics_panel_gate_coverage.TestFetchTrainingStateCallback"
INIT = "test_candidate_metrics_panel.TestCandidateMetricsPanelInit"

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
PROBE_KEY = "test_zz_f053_binding_probe::test_modules_under_test_come_from_this_copy"

GUARD_ANCHOR = r"            prevent_initial_call=False,\n        \)\n        def fetch_training_state\("
STATE_LINE = '                State(f"{self.component_id}-training-state-store", "data"),\n'


def _guard(prop: str, on: str, off: str) -> str:
    return f'            running=[(Output(f"{{self.component_id}}-update-interval", "{prop}"), {on}, {off})],\n            prevent_initial_call=False,\n        )\n        def fetch_training_state('


@dataclass
class Arm:
    name: str
    why: str
    path: str
    pattern: str
    repl: Union[str, Callable[["re.Match[str]"], str]]
    count: int = 1
    expect_fail: List[str] = field(default_factory=list)


ARMS: List[Arm] = [
    Arm(
        "M1-period-back-to-1000ms",
        "the defect itself: at 1000 ms, 0 of 225 writes landed",
        CONSTANTS,
        r"CANDIDATE_STATE_POLL_INTERVAL_MS: Final\[int\] = 10000  # 10 seconds",
        "CANDIDATE_STATE_POLL_INTERVAL_MS: Final[int] = 1000  # 1 second",
        1,
        [f"{WIRE}::test_the_poll_period_is_pinned", f"{INIT}::test_default_update_interval"],
    ),
    Arm(
        "M2-guard-on-disabled",
        "#613's literal guard on this TAB-GATED lane: re-arms the poller on a hidden tab",
        PANEL,
        GUARD_ANCHOR,
        _guard("disabled", "True", "False"),
        1,
        [f"{WIRE}::test_the_poll_carries_no_running_guard", f"{RULE}::test_no_running_guard_writes_a_tab_gated_disabled_prop", f"{RULE}::test_no_running_guard_touches_the_candidate_lane"],
    ),
    Arm(
        "M3-guard-on-max-intervals",
        "the variant this PR first shipped: avoids the gate race, not the evicted-release one",
        PANEL,
        GUARD_ANCHOR,
        _guard("max_intervals", "0", "-1"),
        1,
        [f"{WIRE}::test_the_poll_carries_no_running_guard", f"{RULE}::test_no_running_guard_touches_the_candidate_lane"],
    ),
    Arm(
        "M4-second-writer-of-the-lane",
        "a strand-watchdog-shaped helper becomes a second owner of the lane's clock",
        PANEL,
        r"        # ── Update status display ──\n",
        '        app.callback(Output(f"{self.component_id}-update-interval", "max_intervals"), Input("slow-update-interval", "n_intervals"), prevent_initial_call=True)(lambda n: dash.no_update)\n        # ── Update status display ──\n',
        1,
        [f"{RULE}::test_the_candidate_lane_has_the_gate_as_its_only_writer"],
    ),
    Arm(
        "M5-suppression-removed",
        "every tick rewrites the store and re-fires its consumers",
        PANEL,
        r"if state_out is None or self\._state_unchanged\(state_out, current_state\):",
        "if state_out is None:",
        1,
        [f"{BEHAVE}::test_timestamp_only_change_is_no_update", f"{BEHAVE}::test_stale_age_only_change_is_no_update"],
    ),
    Arm(
        "M6-only-timestamp-is-volatile",
        "an upstream outage rewrites the store every tick via stale_age_seconds",
        PANEL,
        r'_VOLATILE_STATE_KEYS = frozenset\(\{"timestamp", "stale_age_seconds"\}\)',
        '_VOLATILE_STATE_KEYS = frozenset({"timestamp"})',
        1,
        [f"{BEHAVE}::test_stale_age_only_change_is_no_update"],
    ),
    Arm(
        "M7-failure-blanks-the-store",
        "a failed fetch writes {} again, which the badge renders as Inactive",
        PANEL,
        r'(self\.logger\.debug\("Failed to fetch training state"\)\n        )return None',
        lambda m: m.group(1) + "return {}",
        1,
        [
            f"{LEGACY}::test_fetch_swallows_exception_and_returns_empty",
            f"{LEGACY}::test_fetch_non_200_returns_empty",
            f"{BEHAVE}::test_non_200_holds_the_last_good_state",
            f"{BEHAVE}::test_a_payload_that_is_not_an_object_is_a_failure",
        ],
    ),
    Arm(
        "M8-non-object-payload-accepted",
        "a 200 whose body is not a JSON object reaches consumers that call .get on it",
        PANEL,
        r"                if isinstance\(data, dict\):\n                    return data\n",
        "                return data\n",
        1,
        [f"{BEHAVE}::test_a_payload_that_is_not_an_object_is_a_failure"],
    ),
    Arm(
        "M9-store-as-input",
        "the callback's own Output as an Input re-triggers it on its own write",
        PANEL,
        re.escape(STATE_LINE),
        STATE_LINE.replace("State(", "Input("),
        1,
        [f"{WIRE}::test_the_store_rides_as_its_own_state_not_an_input", f"{WIRE}::test_the_states_bind_in_the_order_the_function_reads_them"],
    ),
    Arm(
        "M10-states-swapped",
        "the history list binds to current_state and the state dict to pool_history",
        PANEL,
        r'(State\(f"\{self\.component_id\}-pool-history-store", "data"\),)(.*?)(State\(f"\{self\.component_id\}-training-state-store", "data"\),)',
        lambda m: m.group(3) + m.group(2) + m.group(1),
        1,
        [f"{WIRE}::test_the_states_bind_in_the_order_the_function_reads_them"],
    ),
    Arm(
        "M11-store-state-dropped",
        "current_state is None forever, so nothing is ever suppressed, and the direct unit tests still pass",
        PANEL,
        re.escape(STATE_LINE),
        "",
        1,
        [f"{WIRE}::test_the_store_rides_as_its_own_state_not_an_input", f"{WIRE}::test_the_states_bind_in_the_order_the_function_reads_them"],
    ),
    Arm(
        "M12-failed-comparison-suppresses",
        "an uncomparable payload is treated as unchanged, dropping a real update",
        PANEL,
        r"(        except \(TypeError, ValueError\):\n            )return False(\n        return fetched_canon == current_canon)",
        lambda m: m.group(1) + "return True" + m.group(2),
        1,
        [f"{BEHAVE}::test_a_comparison_that_fails_still_writes"],
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
    repl = arm.repl if callable(arm.repl) else (lambda _m, s=arm.repl: s)
    new, n = re.subn(arm.pattern, repl, text, flags=re.S)
    if n != arm.count:
        return f"anchor matched {n} time(s), expected {arm.count}"
    target.write_text(new, encoding="utf-8")
    return None


def case_key(classname: str, name: str) -> str:
    """``test_module.TestClass::test`` (or ``test_module::test`` at module level)."""
    parts = classname.split(".")
    if len(parts) >= 2 and parts[-1].startswith("Test"):
        return f"{parts[-2]}.{parts[-1]}::{name}"
    return f"{parts[-1]}::{name}"


def run(root: Path, tag: str) -> Tuple[dict, int]:
    """Run the test files in ``root``; return ({key: status}, pytest exit code)."""
    junit = root / f"junit-{tag}.xml"
    env = dict(os.environ, LIBTORCH="", LD_LIBRARY_PATH="", PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=120", f"--junitxml={junit}", *TESTS, PROBE_REL]
    proc = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)  # nosec B603 -- fixed argv, local copy
    results = {}
    if junit.exists():
        for case in ET.parse(junit).getroot().iter("testcase"):  # nosec B314 -- our own output
            status = "passed"
            for child in case:
                if child.tag in ("failure", "error", "skipped"):
                    status = child.tag
            results[case_key(case.get("classname", ""), case.get("name", ""))] = status
    return results, proc.returncode


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="f053-mutation-"))
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
                print(f"{arm.name}: CAUGHT by {len(arm.expect_fail)} test(s); {len(extra)} other(s) also failing  [{arm.why}]")
        print(f"{caught}/{len(ARMS)} mutations caught")
        return 0 if caught == len(ARMS) and not failures else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
