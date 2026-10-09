#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-10-08_w12_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# Last Modified: 2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Mutation check for W1.2 (recurrence request shaping,
#                ruling R7): every new guard must fail on the defect
#                it names.
#####################################################################
"""Mutation check for W1.2 -- schema-filtered recurrence params, R7 precedence, the effective-request preview.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-08
Status: ad-hoc -- investigation
Retire when: the W1.2 PR is merged and its CHANGELOG entry is released
Related: juniper-ml notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md
    (v1.4.1), item W1.2 (findings F-C2, F-C3; ruling R7). The harness is
    ``2026-10-05_w16_w17_mutation_check.py``'s, with this item's arms.

**Why this exists.** A test that passes proves nothing until it has been seen to fail on the defect it names. Each ARM
applies one mutation -- most of them the pre-change behaviour, put back at one site -- to a COPY of the tree and runs the
test files that name it. An arm is CAUGHT only when every test it names fails. The CONTROL (no mutation) must pass every
file in full, or nothing was measured.

Guards (the 683 / W1.6 harness's): the tree is copied per arm and the working tree is never mutated; ``-B`` plus a
per-arm ``PYTHONPYCACHEPREFIX`` keeps ``.pyc`` from crossing arms; a binding probe asserts the modules under test were
imported from the copy, else NOTHING MEASURED; every anchor must match exactly once; and an arm naming a test the
control did not run fails the run.

Usage (from the repo root, in the canopy conda env)::

    conda run -n JuniperCanopy1 python util/ad-hoc/2026-10-08_w12_mutation_check.py [--jobs 4] [--only NAME ...]

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
REQUEST = "src/backend/recurrence_request.py"
BACKEND = "src/backend/recurrence_backend.py"
SCHEMA = "src/dataset_schema.py"
PREVIEW = "src/frontend/components/recurrence_request_preview.py"
DASHBOARD = "src/frontend/dashboard_manager.py"
MAIN = "src/main.py"

FILES = {
    "test_recurrence_staging": "src/tests/regression/test_recurrence_staging.py",
    "test_recurrence_request": "src/tests/unit/test_recurrence_request.py",
    "test_recurrence_request_preview": "src/tests/unit/frontend/test_recurrence_request_preview.py",
}

R7 = "test_recurrence_staging.TestR7RequestPrecedence"
ROUTE = "test_recurrence_staging.TestTheEffectiveRequestRoute"
STAGED = "test_recurrence_staging.TestTheStagedConfigTranslation"
DECL = "test_recurrence_request.TestTheDeclarationMatchesJuniperData"
SEEDS = "test_recurrence_request.TestEveryRecurrenceSeedIsDeclared"
SAME = "test_recurrence_request.TestSameValue"
SHAPE = "test_recurrence_request.TestShapeStagedRef"
START_BODY = "test_recurrence_request.TestShapeStartBodyRef"
WIRE = "test_recurrence_request.TestTrainRequestBodyMatchesTheAdapter"
BACKEND_PREVIEW = "test_recurrence_request.TestBackendPreview"
PANEL = "test_recurrence_request_preview.TestRefreshHandler"
CALLBACKS = "test_recurrence_request_preview.TestCallbacks"
CARRIED = "test_recurrence_request_preview.TestTheDashboardCarriesIt"

BINDING_PROBE = '''
"""Written by 2026-10-08_w12_mutation_check.py into its per-arm copy ONLY."""
from pathlib import Path

import dataset_schema
from backend import recurrence_backend, recurrence_request
from frontend.components import recurrence_request_preview

ROOT = Path(__file__).resolve().parents[3]


def test_modules_under_test_come_from_this_copy():
    for mod in (dataset_schema, recurrence_backend, recurrence_request, recurrence_request_preview):
        assert ROOT in Path(mod.__file__).resolve().parents, f"{mod.__name__} imported from {mod.__file__}, not {ROOT}"
'''
PROBE_REL = "src/tests/unit/test_zz_w12_binding_probe.py"
PROBE_KEY = "test_zz_w12_binding_probe::test_modules_under_test_come_from_this_copy"


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


GENERIC_RULES = (
    "        if (declared is not None and param not in declared) or param in seed:\n"
    "            not_forwarded.append(canopy_key)  # F-C3: nothing to become; R7: never over the seed\n"
    "        elif declared is None or not same_value(value, declared[param]):\n"
    "            params[param] = value\n"
    "            edited.append(param)\n"
)
UNDECLARED_FORM_KEY = "        if declared is not None and key not in declared:\n            not_forwarded.append(key)\n            undeclared.append(key)\n            continue\n"
PREVIEW_RESOLVE = "        with self._lock:\n            request = self._resolve_request_locked(kwargs)\n            fit_in_progress = self._state == \"training\"\n"
ROUTE_N5 = '    inactive = _selection_inactive_reason()\n    if inactive is not None:\n        return JSONResponse({"ok": False, "error": f"Training could not be started: {inactive}"}, status_code=409)\n'
MACKEY_GLASS_LINE = '    "mackey_glass": {"n_steps": 2000, "lookback": 32, "horizon": 1, "sample_dt": 1.0, "train_ratio": 0.8, "val_ratio": 0.1, "seed": 0, "scaling": "identity", "tau": 17.0, "beta": 0.2, "gamma": 0.1, "n_exp": 10.0, "x0": 0.5, "init_noise_std": 0.0, "discard": 250},\n'
WIRE_CASES = [f"{WIRE}::test_the_same_json_as_the_adapter[dataset_ref{i}-hyperparams{i}]" for i in range(5)]

ARMS = [
    Arm(
        "untouched-defaults-forwarded",
        "F-C2: every rendered form value is forwarded, edited or not (the pre-change merge)",
        [Edit(REQUEST, "        if not same_value(value, rendered):\n", "        if True:  # mutated\n")],
        [
            f"{R7}::test_an_untouched_form_sends_exactly_the_seed",
            f"{R7}::test_a_staged_n_samples_beside_untouched_equities_fields_sends_schema_keys_only",
            f"{R7}::test_an_edited_regression_target_is_sent_and_the_preview_matches",
            f"{SEEDS}::test_an_untouched_form_stages_nothing_but_the_seed[equities_seq]",
            f"{SEEDS}::test_an_untouched_form_stages_nothing_but_the_seed[multi_sine]",
            f"{SHAPE}::test_the_browser_number_round_trip_is_not_an_edit",
            f"{SHAPE}::test_an_edit_to_an_unseeded_key_is_forwarded",
        ],
    ),
    Arm(
        "generic-fields-translated",
        "F-C3: the pre-change translation -- nn_dataset_elements/noise become n_samples/noise for every generator",
        [Edit(REQUEST, GENERIC_RULES, "        params[param] = value  # mutated: the pre-W1.2 translation\n")],
        [
            f"{R7}::test_a_staged_n_samples_beside_untouched_equities_fields_sends_schema_keys_only",
            f"{ROUTE}::test_the_restart_modal_restage_reaches_the_service_as_the_seed",
            f"{STAGED}::test_operator_edits_override_the_seed",
            f"{SHAPE}::test_generic_fields_are_withheld_from_every_recurrence_generator",
            f"{BACKEND_PREVIEW}::test_the_preview_is_the_request_start_sends",
        ],
    ),
    Arm(
        "undeclared-form-key-forwarded",
        "F-C3: a form key the generator does not declare is forwarded unfiltered",
        [Edit(REQUEST, UNDECLARED_FORM_KEY, "        if declared is not None and key not in declared:\n            params[key] = value  # mutated\n            continue\n")],
        [f"{SHAPE}::test_a_parameter_the_generator_does_not_declare_is_withheld_and_named"],
    ),
    Arm(
        "generic-overrides-seed",
        "R7 rule 2: a generic field is allowed over a key the seed sets",
        [Edit(REQUEST, "        if (declared is not None and param not in declared) or param in seed:\n", "        if declared is not None and param not in declared:  # mutated\n")],
        [f"{SHAPE}::test_a_generic_field_never_overrides_the_seed", f"{SHAPE}::test_an_undeclared_generator_is_forwarded_as_staged_except_against_the_seed"],
    ),
    Arm(
        "start-body-unfiltered",
        "F-C3 on the Start-body path: undeclared params ride the one-shot body",
        [Edit(REQUEST, "    if declared is None or not isinstance(params, Mapping):\n", "    if True:  # mutated\n")],
        [f"{START_BODY}::test_an_undeclared_parameter_is_withheld"],
    ),
    Arm(
        "preview-ignores-staged",
        "R7 preview: resolved from the Start body alone, so it disagrees with what Start sends",
        [
            Edit(
                BACKEND,
                PREVIEW_RESOLVE,
                "        with self._lock:\n"
                "            request = recurrence_request.resolve_fit_request(explicit_ref={k: kwargs[k] for k in _DATASET_REF_KEYS if kwargs.get(k) is not None}, staged_cfg=None, hyperparams=dict(self._pending_hyperparams))  # mutated\n"
                '            fit_in_progress = self._state == "training"\n',
            )
        ],
        [
            f"{R7}::test_a_staged_n_samples_beside_untouched_equities_fields_sends_schema_keys_only",
            f"{R7}::test_an_edited_regression_target_is_sent_and_the_preview_matches",
            f"{BACKEND_PREVIEW}::test_the_preview_is_the_request_start_sends",
        ],
    ),
    Arm(
        "body-drops-split",
        "wire contract: the preview body is built differently from the adapter's",
        [Edit(REQUEST, '    dataset: Dict[str, Any] = {"split": dataset_ref.get("split", "train")}\n', "    dataset: Dict[str, Any] = {}  # mutated\n")],
        [*WIRE_CASES, f"{R7}::test_an_edited_regression_target_is_sent_and_the_preview_matches"],
    ),
    Arm(
        "start-not-logged",
        "R7: the request Start sends is not logged at INFO",
        [Edit(BACKEND, '        request.log("start")  # W1.2 / R7: the body about to be POSTed, exactly as the preview showed it\n', "")],
        [f"{ROUTE}::test_the_preview_and_the_start_are_both_logged_at_info"],
    ),
    Arm(
        "preview-not-logged",
        "R7: the preview is not logged at INFO",
        [Edit(BACKEND, '        request.log("preview")\n', "")],
        [f"{ROUTE}::test_the_preview_and_the_start_are_both_logged_at_info"],
    ),
    Arm(
        "route-skips-n5",
        "the preview answers for a selection Start would refuse",
        [Edit(MAIN, ROUTE_N5, "")],
        [f"{ROUTE}::test_an_inactive_selection_is_refused_as_start_refuses_it"],
    ),
    Arm(
        "snapshot-default-wrong",
        "declaration: a default that disagrees with juniper-data makes an untouched field read as an edit",
        [Edit(SCHEMA, '"seed": 42, "lookback": 64}', '"seed": 42, "lookback": 65}')],
        [f"{DECL}::test_every_default_matches[equities_seq]", f"{SEEDS}::test_an_untouched_form_stages_nothing_but_the_seed[equities_seq]", f"{R7}::test_an_untouched_form_sends_exactly_the_seed"],
    ),
    Arm(
        "snapshot-field-missing",
        "the plan's risk row: an incomplete declaration drops a valid equities_seq param",
        [Edit(SCHEMA, '"week52_window": 252, "normalize_features": False, "max_symbols": 14', '"normalize_features": False, "max_symbols": 14')],
        [f"{DECL}::test_equities_seq_declares_every_field_juniper_data_has", f"{DECL}::test_names_match_in_both_directions[equities_seq]"],
    ),
    Arm(
        "rank3-seed-undeclared",
        "a recurrence-reachable generator loses its declaration and is forwarded unfiltered",
        [Edit(SCHEMA, MACKEY_GLASS_LINE, "")],
        [f"{SEEDS}::test_the_seed_s_generator_is_declared[mackey_glass]", f"{DECL}::test_the_capture_and_the_declaration_name_the_same_generators"],
    ),
    Arm(
        "checkbox-equals-count",
        "same_value: True == 1 and False == 0 are let through",
        [Edit(REQUEST, "    if isinstance(left, bool) or isinstance(right, bool):\n        return isinstance(left, bool) and isinstance(right, bool) and left == right\n", "")],
        [f"{SAME}::test_a_checkbox_is_not_a_count"],
    ),
    Arm(
        "panel-asks-for-every-model",
        "the panel requests a preview (and shows) for a live model too",
        [Edit(PREVIEW, "        if model_class != _ONE_SHOT:\n", "        if False:  # mutated\n")],
        [f"{PANEL}::test_a_live_model_shows_nothing_and_asks_nothing", f"{CALLBACKS}::test_the_registered_callback_runs_the_handler"],
    ),
    Arm(
        "edge-detector-always-emits",
        "the 5 s banner poll would dispatch a server preview on every tick",
        [Edit(PREVIEW, "    if (previous && previous.open === open) {\n", "    if (false) {\n")],
        [f"{CALLBACKS}::test_the_edge_detector_idles_unless_the_banner_changed"],
    ),
    Arm(
        "panel-not-above-start",
        "the dashboard stops carrying the panel above Start",
        [Edit(DASHBOARD, "                                                self.recurrence_request_preview.get_layout(),\n", "")],
        [f"{CARRIED}::test_the_panel_sits_above_the_start_button"],
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
    for var in ("JUNIPER_CANOPY_RECURRENCE_API_KEY", "JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE", "JUNIPER_RECURRENCE_API_KEY", "JUNIPER_RECURRENCE_API_KEY_FILE", "JUNIPER_DATA_SRC"):
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
        # A skip is not a failure: the opt-in source check skips in every run (JUNIPER_DATA_SRC is cleared above).
        extra = sorted(t for t, v in results.items() if v not in ("passed", "skipped") and t not in arm.expect_fail)
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
    work = Path(tempfile.mkdtemp(prefix="w12-mutation-"))
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
