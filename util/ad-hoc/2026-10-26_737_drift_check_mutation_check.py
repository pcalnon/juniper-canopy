#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-10-26_737_drift_check_mutation_check.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-26
# Last Modified: 2026-10-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Mutation check for juniper-canopy#737: every guard in
#                the juniper-data schema drift check must fail on the
#                defect it names.
#####################################################################
"""Mutation check for juniper-canopy#737 -- the juniper-data generator-schema drift check and its workflow.

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-10-26
Status: ad-hoc -- investigation
Retire when: the juniper-canopy#737 PR is merged and its CHANGELOG entry is released
Related: juniper-canopy#737; ``util/check_juniper_data_generator_schemas.py``,
    ``src/tests/unit/test_check_juniper_data_generator_schemas.py`` and
    ``.github/workflows/juniper-data-schema-drift.yml``. The rules are ``2026-10-08_w12_mutation_check.py``'s.

**Why this exists.** A test that passes proves nothing until it has been seen to fail on the defect it names.
Each ARM applies one mutation -- one guard disabled or inverted -- to a COPY of the files the test module reads,
and runs that module. An arm is CAUGHT only when every test it names fails. The CONTROL (no mutation) must pass
every test, or nothing was measured.

Guards: the working tree is never mutated, only per-arm copies under the repo's ``tmp/`` (never ``/tmp``);
``-B`` plus a per-arm ``PYTHONPYCACHEPREFIX`` keeps ``.pyc`` from crossing arms; every anchor must match exactly
once; and an arm naming a test the control did not run fails the run. The copy holds no conftest, so the module
runs isolated from canopy's -- it needs none.

Usage (from the repo root, in the canopy conda env)::

    /opt/miniforge3/envs/JuniperCanopy1/bin/python util/ad-hoc/2026-10-26_737_drift_check_mutation_check.py [--keep]

Exit status: 0 = the control passed and every arm was caught; 1 = an arm survived or an anchor did not match
exactly once; 2 = nothing was measured (the control did not pass in full).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 -- runs pytest on a local copy of this repo's files
import sys
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 -- parses the JUnit XML this script wrote
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]
SCRIPT = "util/check_juniper_data_generator_schemas.py"
TESTS = "src/tests/unit/test_check_juniper_data_generator_schemas.py"
WORKFLOW = ".github/workflows/juniper-data-schema-drift.yml"
FILES = ("pyproject.toml", SCRIPT, TESTS, WORKFLOW)


class Arm(NamedTuple):
    name: str
    path: str
    anchor: str
    replacement: str
    tests: tuple


def _injected(kind: str, tests: tuple = ("test_the_generator_and_the_field_are_named", "test_main_exits_1_and_prints_the_exact_recapture_command")) -> tuple:
    return tuple(f"TestInjectedDrift::{test}[{kind}]" for test in tests)


ARMS = (
    Arm("bool-equals-number", SCRIPT, "return isinstance(a, bool) and isinstance(b, bool) and a == b", "return a == b", ("TestInjectedDrift::test_a_default_flipped_from_zero_to_false_is_drift", "TestJsonEquality::test_json_equal[true-is-not-one]", "TestJsonEquality::test_json_equal[false-is-not-zero]")),
    Arm("added-keys-ignored", SCRIPT, 'differences.extend(Difference(path + (key,), "added", upstream=value) for key, value in upstream.items() if key not in fixture)', "differences.extend([])", _injected("a-field-added") + ("TestInjectedDrift::test_a_key_inside_a_field_appearing_or_vanishing_is_named",)),
    Arm("removed-keys-ignored", SCRIPT, 'differences.append(Difference(path + (key,), "removed", fixture=value))', "pass", _injected("a-field-removed") + ("TestInjectedDrift::test_a_key_inside_a_field_appearing_or_vanishing_is_named",)),
    Arm("version-ignored", SCRIPT, 'return diff_json({"version": entry.version, "schema": entry.schema}, upstream_view(registry[entry.name], entry.name))', 'return diff_json({"schema": entry.schema}, {"schema": upstream_view(registry[entry.name], entry.name)["schema"]})', _injected("the-version-changed") + ("TestTheCommittedFixtures::test_a_sibling_snapshot_is_compared_and_its_generator_looked_up_by_name",)),
    Arm("unregistered-generator-passes", SCRIPT, 'return [Difference((), "removed")]', "return []", ("TestInjectedDrift::test_a_generator_juniper_data_no_longer_registers_is_drift",)),
    Arm("drift-exits-0", SCRIPT, "    return 1\n\n\nif __name__", "    return 0\n\n\nif __name__", _injected("a-field-added", ("test_main_exits_1_and_prints_the_exact_recapture_command",)) + ("TestGitHubActionsOutput::test_each_drifted_generator_is_annotated_and_the_report_lands_in_the_job_summary", "TestACheckout::test_drift_in_a_checkout_exits_1_with_that_checkout_in_the_command")),
    Arm("glob-sequence-only", SCRIPT, 'FIXTURE_GLOB = "juniper_data_*generator_schemas.json"', 'FIXTURE_GLOB = "juniper_data_sequence_generator_schemas.json"', ("TestTheCommittedFixtures::test_a_sibling_snapshot_is_compared_and_its_generator_looked_up_by_name", "TestTheWorkflow::test_pull_requests_run_it_for_the_workflow_the_script_and_every_snapshot")),
    Arm("empty-snapshot-passes", SCRIPT, "if not isinstance(generators, list) or not generators:", "if not isinstance(generators, list):", ("TestRefusals::test_a_malformed_snapshot_is_refused[empty]",)),
    Arm("no-snapshot-passes", SCRIPT, "        if not paths:\n            raise CheckError(", "        if not paths:\n            return 0\n            raise CheckError(", ("TestRefusals::test_no_snapshot_at_all_is_a_refusal", "TestGitHubActionsOutput::test_a_refusal_is_an_error_annotation")),
    Arm("unexpected-error-is-drift", SCRIPT, "        return _could_not_run(traceback.format_exc().rstrip())", "        return 1", ("TestRefusals::test_an_unexpected_error_is_could_not_run_not_drift",)),
    Arm("shadowing-copy-accepted", SCRIPT, "    if shipped != package:", "    if False:", ("TestTheInstalledRelease::test_a_copy_shadowing_the_installed_release_is_refused",)),
    Arm("any-version-accepted", SCRIPT, "if expected_version is not None and distribution.version != expected_version:", "if False:", ("TestTheInstalledRelease::test_any_other_version_is_refused",)),
    Arm("checkout-origin-unchecked", SCRIPT, "        if not package.is_relative_to(checkout):", "        if False:", ("TestACheckout::test_a_package_imported_from_elsewhere_is_not_reported_as_the_checkout",)),
    Arm("recapture-flag-wrong", SCRIPT, "--juniper-data-src {source} --fixture {where}", "--juniper-data-src {source} --output {where}", _injected("a-default-changed", ("test_main_exits_1_and_prints_the_exact_recapture_command",)) + ("TestACheckout::test_drift_in_a_checkout_exits_1_with_that_checkout_in_the_command", "TestTheCommittedFixtures::test_each_snapshot_s_capture_tool_takes_the_flags_the_recapture_command_passes[juniper_data_sequence_generator_schemas.json]")),
    Arm("wheel-provenance-ignored", SCRIPT, "isinstance(wheel, str) and bool(wheel))", "False)", ("TestTheCommittedFixtures::test_a_wheel_captured_snapshot_gets_the_published_wheel_recipe",)),
    Arm("wheel-recipe-drops-the-wheel", SCRIPT, " --wheel {WHEEL_WORKDIR}/wheel/{_wheel_file(juniper.version)}", "", ("TestTheCommittedFixtures::test_a_wheel_captured_snapshot_gets_the_published_wheel_recipe",)),
    Arm("annotation-title-unescaped", SCRIPT, '.replace(":", "%3A").replace(",", "%2C")', "", ("TestGitHubActionsOutput::test_annotation_text_is_escaped", "TestGitHubActionsOutput::test_each_drifted_generator_is_annotated_and_the_report_lands_in_the_job_summary")),
    Arm("summary-error-escapes", SCRIPT, "    except OSError as exc:  # the report is already on stdout", "    except KeyError as exc:  # the report is already on stdout", ("TestGitHubActionsOutput::test_an_unwritable_job_summary_does_not_change_the_verdict",)),
    Arm("workflow-sets-run-name", WORKFLOW, "name: juniper-data Schema Drift\n", "name: juniper-data Schema Drift\nrun-name: juniper-data schema drift\n", ("TestTheWorkflow::test_it_sets_no_run_name",)),
    Arm("workflow-drops-the-api-extra", WORKFLOW, 'python -m pip install "juniper-data[api]==${VERSION}"', 'python -m pip install "juniper-data==${VERSION}"', ("TestTheWorkflow::test_it_installs_the_api_extra_at_the_chosen_version",)),
    Arm("workflow-drops-expected-version", WORKFLOW, 'util/check_juniper_data_generator_schemas.py --expected-version "${VERSION}"', "util/check_juniper_data_generator_schemas.py", ("TestTheWorkflow::test_it_runs_the_script_isolated_and_held_to_that_version",)),
    Arm("workflow-splices-the-payload", WORKFLOW, 'version="${PAYLOAD_VERSION#v}"', 'version="${{ github.event.client_payload.version }}"', ("TestTheWorkflow::test_event_data_reaches_the_shell_only_through_env",)),
    Arm("workflow-loses-the-dispatch", WORKFLOW, "    types: [juniper-data-published]", "    types: [data-published]", ("TestTheWorkflow::test_it_listens_for_juniper_data_s_release_dispatch",)),
)


def snapshot_files() -> list[str]:
    """The committed snapshots and the capture tool each names: the test module reads both."""
    found = []
    for path in sorted((REPO / "src" / "tests" / "fixtures").glob("juniper_data_*.json")):
        found.append(path.relative_to(REPO).as_posix())
        tool = json.loads(path.read_text(encoding="utf-8")).get("_provenance", {}).get("tool")
        if tool:
            found.append(tool)
    return found


def copy_tree(dest: Path) -> None:
    for relative in (*FILES, *snapshot_files()):
        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, target)


def mutate(root: Path, arm: Arm) -> str | None:
    path = root / arm.path
    text = path.read_text(encoding="utf-8")
    count = text.count(arm.anchor)
    if count != 1:
        return f"anchor matched {count} times in {arm.path}"
    path.write_text(text.replace(arm.anchor, arm.replacement), encoding="utf-8")
    return None


def run(root: Path, tag: str) -> dict[str, str]:
    junit = root / f"junit-{tag}.xml"
    env = {key: value for key, value in os.environ.items() if not key.startswith("GITHUB_")}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPYCACHEPREFIX=str(root / ".pyc-prefix"))
    cmd = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q", f"--junitxml={junit}", TESTS]
    subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True, check=False, timeout=600)  # nosec B603 -- fixed argv, local copy
    if not junit.is_file():
        return {}
    outcomes: dict[str, str] = {}
    for case in ET.parse(junit).getroot().iter("testcase"):  # nosec B314 -- this script's own JUnit output
        key = f"{case.get('classname', '').rsplit('.', 1)[-1]}::{case.get('name')}"
        status = "passed"
        for child in case:
            if child.tag in ("failure", "error", "skipped"):
                status = child.tag
        outcomes[key] = status
    return outcomes


def main() -> int:
    parser = argparse.ArgumentParser(description="Mutation check for juniper-canopy#737.")
    parser.add_argument("--keep", action="store_true", help="keep the per-arm copies under tmp/ for inspection")
    args = parser.parse_args()
    (REPO / "tmp").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="737-mutation-check-", dir=REPO / "tmp"))
    try:
        control_root = work / "control"
        copy_tree(control_root)
        control = run(control_root, "control")
        not_passed = sorted(key for key, status in control.items() if status != "passed")
        if not control or not_passed:
            print(f"NOTHING MEASURED: the control ran {len(control)} tests and these did not pass: {not_passed}")
            return 2
        print(f"control: {len(control)} tests, all passed")
        survived = []
        for index, arm in enumerate(ARMS):
            unknown = [test for test in arm.tests if test not in control]
            if unknown:
                print(f"  {arm.name:<34} HARNESS ERROR: names tests the control did not run: {unknown}")
                survived.append(arm.name)
                continue
            root = work / f"arm-{index:02d}"
            copy_tree(root)
            problem = mutate(root, arm)
            if problem:
                print(f"  {arm.name:<34} HARNESS ERROR: {problem}")
                survived.append(arm.name)
                continue
            outcomes = run(root, arm.name)
            missed = [test for test in arm.tests if outcomes.get(test) not in ("failure", "error")]
            others = sorted(key for key, status in outcomes.items() if status in ("failure", "error") and key not in arm.tests)
            verdict = "CAUGHT" if not missed else f"SURVIVED (still passing: {missed})"
            print(f"  {arm.name:<34} {verdict}; {len(others)} other test(s) failed too")
            if missed:
                survived.append(arm.name)
        print(f"{len(ARMS) - len(survived)} of {len(ARMS)} arms caught")
        return 1 if survived else 0
    finally:
        if args.keep:
            print(f"kept: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
