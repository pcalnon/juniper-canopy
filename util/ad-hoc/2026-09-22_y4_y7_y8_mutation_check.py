#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-22_y4_y7_y8_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-22
# Last Modified: 2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Y4 / Y7 / Y8 -- prove the new tests FAIL on each defect
#                they claim to catch, and that the claims about what the
#                production registry CANNOT catch are measured, not assumed.
#####################################################################
"""Mutation check for the Y4 / Y7 / Y8 selection-UI tests.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-22
Status: ad-hoc -- investigation
Retire when: the Y4 / Y7 / Y8 PR has merged and its tests have run green on main
Related: selection-reachability arc, handoff items 16 and 21; design §4.3 (Y7)

Same construction as ``2026-09-22_f053_mutation_check.py``, whose four anti-lying measures are
kept: a COPY of the tree per arm (the working tree is never touched), ``-B`` plus a per-arm
``PYTHONPYCACHEPREFIX``, a binding probe proving the modules under test were imported from the
copy (canopy is often editable-installed against another checkout), and anchors that must match
exactly the stated number of times.

One addition: ``expect_pass``. Some arms exist to prove a NEGATIVE claim -- e.g. that the
production registry cannot catch a dropped temporal axis, which is the whole reason the Y8 test
carries a synthetic per-axis registry. Those tests must still PASS under the arm; if one fails,
the claim was wrong and the arm reports it.

Test ids: ``module.Class::test`` names one test; a trailing ``[*]`` means every parametrisation
must match the expectation, ``[?]`` means at least one must.

Usage (from the repo root, in the canopy conda env)::

    LIBTORCH= LD_LIBRARY_PATH= python util/ad-hoc/2026-09-22_y4_y7_y8_mutation_check.py

Exit status: 0 = control passed, every arm caught and every expect_pass held; 1 = an arm
survived, an expect_pass failed, or an anchor failed; 2 = nothing was measured.
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
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
DM = "src/frontend/dashboard_manager.py"
REG = "src/model_registry.py"
TESTS = [
    "src/tests/unit/frontend/test_y4_active_tab_restore.py",
    "src/tests/unit/test_dashboard_manager.py::TestLayoutStatePersistence",
    "src/tests/regression/test_y7_model_table_describedby.py",
    "src/tests/regression/test_y8_disabled_derives_from_compatible.py",
    "src/tests/unit/test_model_registry.py",
    "src/tests/regression/test_model_table.py",
]

Y4_WIRE = "test_y4_active_tab_restore.TestY4RestoreWiring"
Y4_RULE = "test_y4_active_tab_restore.TestY4RestoreRule"
Y4_SRC = "test_dashboard_manager.TestLayoutStatePersistence"
Y7_ROW = "test_y7_model_table_describedby.TestY7SelectIsDescribedByItsRow"
Y7_SHAPE = "test_y7_model_table_describedby.TestY7ControlShape"
Y8_OPT = "test_y8_disabled_derives_from_compatible.TestY8DatasetOptions"
Y8_TAB = "test_y8_disabled_derives_from_compatible.TestY8ModelTable"
Y8_AXIS = "test_y8_disabled_derives_from_compatible.TestY8AnAxisTheWordingDoesNotKnow"

BINDING_PROBE = '''
"""Written by 2026-09-22_y4_y7_y8_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import model_registry
from frontend import dashboard_manager

ROOT = Path(__file__).resolve().parents[4]


def test_modules_under_test_come_from_this_copy():
    for mod in (model_registry, dashboard_manager):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/frontend/test_zz_y4y7y8_binding_probe.py"
PROBE_KEY = "test_zz_y4y7y8_binding_probe::test_modules_under_test_come_from_this_copy"

Y4_BLOCK = """\
                var rendered = [];
                [].concat(tabs || []).forEach(function(tab, index) {
                    if (tab && tab.props) rendered.push(tab.props.tab_id || "tab-" + index);
                });
                var saved = state && state.active_tab;
                if (rendered.length && rendered.indexOf(saved) === -1) {
                    var target = rendered.indexOf(currentTab) !== -1 ? currentTab : rendered[0];
                    return target === currentTab ? window.dash_clientside.no_update : target;
                }
"""
ITERATION_SEGMENT = '        @self.app.callback(\n            Output("status-iteration-segment", "style"),'
NEW_ACTIVE_TAB_WRITER = '        self.app.callback(Output("visualization-tabs", "active_tab", allow_duplicate=True), Input("model-class-store", "data"), prevent_initial_call=True)(lambda model_class: dash.no_update)\n'
DATASET_GATE = "        if spec is None or compatible(dataset, spec):"
TABLE_GATE = "            is_compatible = dataset is None or compatible(dataset, model)"
DESCRIBED = '            described = {"aria-describedby": compat_id}'
DATASET_REASON_GATE = '    disabled option in the dropdown with no reason on it.\n    """\n    if compatible(dataset, model):\n        return None\n'


@dataclass
class Arm:
    name: str
    why: str
    path: str
    old: str
    new: str
    count: int = 1
    expect_fail: List[str] = field(default_factory=list)
    expect_pass: List[str] = field(default_factory=list)


ARMS: List[Arm] = [
    # ---------------------------------------------------------------- Y4: the active-tab restore
    Arm(
        "Y4-M1-pre-y4-rule",
        "the shipped defect: nothing checks the tab is rendered",
        DM,
        Y4_BLOCK,
        "",
        1,
        [
            f"{Y4_RULE}::test_runtime_swap_off_a_cascade_tab_lands_on_metrics",
            f"{Y4_RULE}::test_a_saved_tab_that_is_not_rendered_is_never_restored",
            f"{Y4_RULE}::test_an_unknown_saved_tab_keeps_the_shown_tab",
            f"{Y4_RULE}::test_an_empty_store_still_rescues_a_stranded_tab",
            f"{Y4_RULE}::test_the_shown_tab_is_always_rendered_afterwards",
            f"{Y4_SRC}::test_read_callback_never_restores_an_unrendered_tab",
        ],
        [f"{Y4_RULE}::test_an_unreadable_tab_list_keeps_the_pre_y4_rule", f"{Y4_RULE}::test_the_equality_guard_survives", f"{Y4_RULE}::test_cascade_tabs_still_restore_for_a_live_model"],
    ),
    Arm(
        "Y4-M2-tabs-as-state",
        "State is read once, before the one-shot rebuild; the rule still works when CALLED",
        DM,
        '            Input("visualization-tabs", "children"),\n',
        '            State("visualization-tabs", "children"),\n',
        1,
        [f"{Y4_WIRE}::test_the_rendered_tabs_are_an_input_not_state", f"{Y4_WIRE}::test_the_reset_adds_no_active_tab_writer", f"{Y4_SRC}::test_read_callback_reads_the_rendered_tabs"],
        [f"{Y4_RULE}::test_runtime_swap_off_a_cascade_tab_lands_on_metrics", f"{Y4_RULE}::test_the_shown_tab_is_always_rendered_afterwards"],
    ),
    Arm(
        "Y4-M3-fallback-keeps-the-stranded-tab",
        "the membership check runs but never moves off an unrendered tab",
        DM,
        "var target = rendered.indexOf(currentTab) !== -1 ? currentTab : rendered[0];",
        "var target = currentTab;",
        1,
        [f"{Y4_RULE}::test_runtime_swap_off_a_cascade_tab_lands_on_metrics", f"{Y4_RULE}::test_an_empty_store_still_rescues_a_stranded_tab", f"{Y4_RULE}::test_the_shown_tab_is_always_rendered_afterwards", f"{Y4_SRC}::test_read_callback_never_restores_an_unrendered_tab"],
    ),
    Arm(
        "Y4-M4-half-fix-runtime-only",
        "rescues a stranded SHOWN tab but still restores an unrendered SAVED one (the reload path)",
        DM,
        "if (rendered.length && rendered.indexOf(saved) === -1) {",
        "if (rendered.length && rendered.indexOf(currentTab) === -1) {",
        1,
        [f"{Y4_RULE}::test_a_saved_tab_that_is_not_rendered_is_never_restored", f"{Y4_RULE}::test_an_unknown_saved_tab_keeps_the_shown_tab", f"{Y4_RULE}::test_the_shown_tab_is_always_rendered_afterwards", f"{Y4_SRC}::test_read_callback_never_restores_an_unrendered_tab"],
        [f"{Y4_RULE}::test_runtime_swap_off_a_cascade_tab_lands_on_metrics"],
    ),
    Arm(
        "Y4-M5-reset-as-a-new-writer",
        "the reset moved to the model-class rebuild, adding an active_tab writer",
        DM,
        ITERATION_SEGMENT,
        NEW_ACTIVE_TAB_WRITER + ITERATION_SEGMENT,
        1,
        [f"{Y4_WIRE}::test_the_reset_adds_no_active_tab_writer", f"{Y4_SRC}::test_single_mount_time_active_tab_restore"],
    ),
    # ---------------------------------------------------------------- Y8: disabled == not compatible()
    Arm(
        "Y8-M1-option-disabled-though-compatible",
        "the gate greys a compatible pair",
        REG,
        DATASET_GATE,
        "        if spec is None or (compatible(dataset, spec) and dataset.ndim != 3):",
        1,
        [f"{Y8_OPT}::test_disabled_is_exactly_not_compatible[*]", f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[*]"],
    ),
    Arm(
        "Y8-M2-option-gate-drops-the-temporal-axis",
        "an incompatible pair stays selectable -- and ONLY the per-axis registry can see it",
        REG,
        DATASET_GATE,
        "        if spec is None or (dataset.ndim in spec.input_ndim and dataset.task_type in spec.supported_task_types):",
        1,
        [f"{Y8_OPT}::test_disabled_is_exactly_not_compatible[per-axis]", f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[per-axis]"],
        [f"{Y8_OPT}::test_disabled_is_exactly_not_compatible[production]", f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[production]"],
    ),
    Arm(
        "Y8-M3-greyed-option-with-an-empty-reason",
        "the temporal phrase is lost; again invisible to the production registry",
        REG,
        '        return "needs a Δt-aware model"',
        '        return ""',
        1,
        [f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[per-axis]"],
        [f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[production]"],
    ),
    Arm(
        "Y8-M4-dataset-fallback-returns-none",
        "an axis the wording does not name greys an option with the label 'X — None'",
        REG,
        '    return "not compatible with this model"',
        "    return None",
        1,
        [f"{Y8_AXIS}::test_the_dataset_option_is_greyed_with_a_reason", f"{Y8_AXIS}::test_neither_helper_returns_none_for_the_rejected_pair"],
    ),
    Arm(
        "Y8-M5-model-fallback-returns-none",
        "an axis the wording does not name greys a Select with an empty reason cell",
        REG,
        '    return "not compatible with this dataset"',
        "    return None",
        1,
        [f"{Y8_AXIS}::test_the_model_select_is_greyed_with_a_reason", f"{Y8_AXIS}::test_neither_helper_returns_none_for_the_rejected_pair"],
    ),
    Arm(
        "Y8-M6-reason-on-an-enabled-option",
        "a selectable option carries a reason suffix",
        REG,
        '            options.append({"label": dataset.label, "value": dataset.value})',
        '            options.append({"label": f"{dataset.label} — {dataset_reason(dataset, spec) if spec else None}", "value": dataset.value})',
        1,
        [f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[*]"],
    ),
    Arm(
        "Y8-M7-dataset-reason-ungated",
        "the phrase helper re-derives the verdict and names a reason for a COMPATIBLE pair",
        REG,
        DATASET_REASON_GATE,
        '    disabled option in the dropdown with no reason on it.\n    """\n',
        1,
        [f"{Y8_OPT}::test_a_reason_is_shown_iff_disabled[*]"],
    ),
    Arm(
        "Y8-M8-table-gate-drops-the-temporal-axis",
        "the model table enables an incompatible Select -- per-axis registry only",
        DM,
        TABLE_GATE,
        "            is_compatible = dataset is None or (dataset.ndim in model.input_ndim and dataset.task_type in model.supported_task_types)",
        1,
        [f"{Y8_TAB}::test_disabled_is_exactly_not_compatible[per-axis]", f"{Y8_TAB}::test_a_reason_is_shown_iff_disabled[per-axis]"],
        [f"{Y8_TAB}::test_disabled_is_exactly_not_compatible[production]"],
    ),
    Arm(
        "Y8-M9-table-select-disabled-though-compatible",
        "the model table greys a compatible model",
        DM,
        TABLE_GATE,
        "            is_compatible = dataset is None or (compatible(dataset, model) and not model.requires_dt)",
        1,
        [f"{Y8_TAB}::test_disabled_is_exactly_not_compatible[*]", f"{Y8_TAB}::test_a_reason_is_shown_iff_disabled[*]"],
    ),
    # ---------------------------------------------------------------- Y7: aria-describedby
    Arm(
        "Y7-M1-no-describedby",
        "the shipped defect: the reason reaches the button by no rendered channel",
        DM,
        DESCRIBED,
        "            described = {}",
        1,
        [f"{Y7_ROW}::test_every_reason_row_is_described_by_that_reason[?]", f"{Y7_ROW}::test_every_row_is_described_by_its_own_compatibility_cell[*]", f"{Y7_ROW}::test_describedby_targets_are_unique_in_the_table[*]"],
    ),
    Arm(
        "Y7-M2-describedby-dangles",
        "aria-describedby names an element that does not exist",
        DM,
        DESCRIBED,
        '            described = {"aria-describedby": compat_id + "-reason"}',
        1,
        [f"{Y7_ROW}::test_every_reason_row_is_described_by_that_reason[?]", f"{Y7_ROW}::test_every_row_is_described_by_its_own_compatibility_cell[*]"],
    ),
    Arm(
        "Y7-M3-reason-cell-without-id",
        "only the REASON branch loses its id; the ⊥ table has no reason rows and stays green",
        DM,
        '                compat_cell = html.Span(model_reason(model, dataset), id=compat_id, className="text-muted small fst-italic")',
        '                compat_cell = html.Span(model_reason(model, dataset), className="text-muted small fst-italic")',
        1,
        [f"{Y7_ROW}::test_every_reason_row_is_described_by_that_reason[?]", f"{Y7_ROW}::test_every_row_is_described_by_its_own_compatibility_cell[?]"],
        [f"{Y7_ROW}::test_every_row_is_described_by_its_own_compatibility_cell[production:bottom]"],
    ),
    Arm(
        "Y7-M4-lossy-escape",
        "two keys share an id, so a description resolves to two elements",
        DM,
        'else f"_{ord(ch):x}_" for ch in str(model_key))',
        'else "-" for ch in str(model_key))',
        1,
        [f"{Y7_SHAPE}::test_the_cell_id_is_deterministic_valid_and_injective", f"{Y7_ROW}::test_describedby_targets_are_unique_in_the_table[?]", f"{Y7_ROW}::test_every_reason_row_is_described_by_that_reason[?]"],
    ),
    Arm(
        "Y7-M5-raw-key-as-id",
        "a key with whitespace or '.' becomes an invalid id",
        DM,
        '        return f"model-compat-{safe}"',
        '        return f"model-compat-{model_key}"',
        1,
        [f"{Y7_SHAPE}::test_the_cell_id_is_deterministic_valid_and_injective", f"{Y7_ROW}::test_every_row_is_described_by_its_own_compatibility_cell[?]"],
    ),
    Arm(
        "Y7-M6-title-repeats-on-a-disabled-select",
        "the dropped-title decision regresses",
        DM,
        DESCRIBED,
        '            described = {"aria-describedby": compat_id, "title": "repeated reason"}',
        1,
        [f"{Y7_ROW}::test_a_greyed_select_does_not_repeat_the_reason_in_title[?]"],
    ),
    Arm(
        "Y7-M7-the-select-looks-different",
        "the html.Button no longer renders dbc's class string",
        DM,
        "className=f\"btn btn-{'success' if is_active else 'outline-primary'} btn-sm\",",
        "className=f\"btn btn-{'success' if is_active else 'primary'} btn-sm\",",
        1,
        [f"{Y7_SHAPE}::test_the_select_renders_the_classes_dbc_rendered"],
    ),
]


def copy_tree(dest: Path) -> None:
    # symlinks=True: notes/ carries dangling links, which copying the target would trip on.
    shutil.copytree(REPO, dest, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", "*.pyc"))
    (dest / PROBE_REL).write_text(BINDING_PROBE, encoding="utf-8")


def mutate(root: Path, arm: Arm) -> Optional[str]:
    """Apply ``arm`` as a literal replacement; return an error when the anchor count is wrong."""
    target = root / arm.path
    text = target.read_text(encoding="utf-8")
    found = text.count(arm.old)
    if found != arm.count:
        return f"anchor matched {found} time(s), expected {arm.count}"
    target.write_text(text.replace(arm.old, arm.new), encoding="utf-8")
    return None


def case_key(classname: str, name: str) -> str:
    """``test_module.TestClass::test`` (or ``test_module::test`` at module level)."""
    parts = classname.split(".")
    if len(parts) >= 2 and parts[-1].startswith("Test"):
        return f"{parts[-2]}.{parts[-1]}::{name}"
    return f"{parts[-1]}::{name}"


def run(root: Path, tag: str) -> Tuple[Dict[str, str], int]:
    """Run the test files in ``root``; return ({key: status}, pytest exit code)."""
    junit = root / f"junit-{tag}.xml"
    env = dict(os.environ, LIBTORCH="", LD_LIBRARY_PATH="", PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "--timeout=180", f"--junitxml={junit}", *TESTS, PROBE_REL]
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


def select(results: Dict[str, str], entry: str) -> Tuple[List[str], str]:
    """Resolve an id (with an optional ``[*]`` / ``[?]`` suffix) to its keys and its quantifier."""
    if entry.endswith("[*]") or entry.endswith("[?]"):
        base, quantifier = entry[:-3], entry[-2]
        return sorted(k for k in results if k.startswith(base + "[")), quantifier
    return ([entry] if entry in results else []), "*"


def holds(results: Dict[str, str], entry: str, want_fail: bool) -> Optional[bool]:
    keys, quantifier = select(results, entry)
    if not keys:
        return None
    hits = [(results[k] != "passed") == want_fail for k in keys]
    return all(hits) if quantifier == "*" else any(hits)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="y4y7y8-mutation-"))
    try:
        control = work / "control"
        copy_tree(control)
        results, rc = run(control, "control")
        bad = sorted(k for k, v in results.items() if v != "passed")
        print(f"CONTROL: pytest exit {rc}, {len(results)} test(s), {len(bad)} not passing")
        if rc != 0 or bad or not results or results.get(PROBE_KEY) != "passed":
            print("NOTHING MEASURED -- the control must pass in full, from this copy:", bad or "(no results / binding failed)")
            return 2
        caught, failures = 0, []
        for i, arm in enumerate(ARMS):
            missing = [e for e in arm.expect_fail + arm.expect_pass if holds(results, e, True) is None]
            if missing:
                failures.append(f"{arm.name}: names tests that do not exist: {missing}")
                print(f"{arm.name}: EXPECTED TESTS MISSING -- {missing}")
                continue
            root = work / f"arm{i}"
            copy_tree(root)
            err = mutate(root, arm)
            if err:
                failures.append(f"{arm.name}: ANCHOR FAILED -- {err}")
                print(f"{arm.name}: ANCHOR FAILED -- {err}")
                continue
            arm_results, _rc = run(root, arm.name)
            if arm_results.get(PROBE_KEY) != "passed":
                print(f"{arm.name}: NOTHING MEASURED -- binding probe did not pass")
                return 2
            survived = [e for e in arm.expect_fail if not holds(arm_results, e, True)]
            broke = [e for e in arm.expect_pass if not holds(arm_results, e, False)]
            failing = sorted(k for k, v in arm_results.items() if v != "passed")
            if survived or broke:
                failures.append(f"{arm.name}: survived={survived} expect_pass_broken={broke}")
                print(f"{arm.name}: FAILED CHECK -- survived: {survived}; expected-to-pass but failing: {broke}")
            else:
                caught += 1
                held = f"; {len(arm.expect_pass)} expect_pass held" if arm.expect_pass else ""
                print(f"{arm.name}: CAUGHT -- {len(failing)} test(s) failing{held}  [{arm.why}]")
        print(f"{caught}/{len(ARMS)} mutations caught")
        for line in failures:
            print("  ", line)
        return 0 if caught == len(ARMS) and not failures else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
