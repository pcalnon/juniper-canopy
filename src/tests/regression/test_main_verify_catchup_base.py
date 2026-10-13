#!/usr/bin/env python
"""Drift guard for main-verify.yml's SCREENED-not-GREEN catch-up base.

Project:     Juniper
Sub-Project: juniper-canopy
Application: regression tests
Author:      Paul Calnon
License:     MIT License

``main-verify.yml`` resolves its catch-up BASE from the newest run that reached a
sequence-safety VERDICT, not the newest run that was GREEN. The signal it reads is an
EXACT step name looked up through the jobs API.

Drift in that name is SILENT: the resolver simply matches nothing, falls through to the
legacy ``status=success`` tier, and restores the recurring-red defect while every check
stays green. That is the vacuous-pass shape, so BOTH halves are pinned here -- the
workflow must define the step, and the resolver must grep for the same literal. Either
assertion alone can drift past the other.

Measured cost of the defect on this repo, 2026-08-31: canopy#549 merged without a
sequence-safety waiver, ``main-verify`` failed on ``b9ad8255``, and because the base was
resolved from the last GREEN run it stayed pinned at ``ab210ec7`` -- so every subsequent
push re-screened the same window and failed again. ``main`` was permanently red rather
than self-clearing, and needed a hand-authored waiver commit (canopy#553) to escape.

Ported from juniper-ml (ml#1291). Design of record lives there:
``notes/JUNIPER_2026-08-23_JUNIPER-ML_MAIN-VERIFY-CATCHUP-BASE-SCREENED-NOT-GREEN-DESIGN.md``.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

WORKFLOW_NAME = "main-verify.yml"
SCREEN_JOB_ID = "symbol-screen"


def _find_repo_root(start: Path) -> Path:
    """Walk up until a directory holding .github/workflows is found."""
    for candidate in (start, *start.parents):
        if (candidate / ".github" / "workflows").is_dir():
            return candidate
    raise unittest.SkipTest(f"no .github/workflows above {start}")


class VerdictStepNameDriftTest(unittest.TestCase):
    """The tier-1 coverage signal is an exact step name; pin it from both sides."""

    VERDICT_STEP = "Assert screens reached a verdict"
    CLEAN_STEP = "Assert screens clean"
    SCREEN_JOB = "Symbol & Docs Screen"

    doc: dict
    job: dict

    @classmethod
    def setUpClass(cls) -> None:
        repo_root = _find_repo_root(Path(__file__).resolve().parent)
        wf = repo_root / ".github" / "workflows" / WORKFLOW_NAME
        if not wf.is_file():
            raise unittest.SkipTest(f"{WORKFLOW_NAME} not present at {wf}")
        cls.doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
        cls.job = cls.doc.get("jobs", {}).get(SCREEN_JOB_ID, {})

    def test_workflow_defines_the_verdict_assert_step(self) -> None:
        """The coverage signal the resolver reads must actually exist."""
        names = [s.get("name") for s in self.job.get("steps", [])]
        self.assertIn(self.VERDICT_STEP, names, f"tier-1 coverage step missing; steps are {names}")

    def test_verdict_step_precedes_the_clean_assert(self) -> None:
        """Coverage must be asserted BEFORE the verdict, or a finding skips it."""
        names = [s.get("name") for s in self.job.get("steps", [])]
        self.assertIn(self.CLEAN_STEP, names)
        self.assertLess(names.index(self.VERDICT_STEP), names.index(self.CLEAN_STEP))

    def test_screens_step_does_not_fail_on_findings(self) -> None:
        """The screens step must RECORD exit codes, not exit on them.

        If it exits non-zero on a finding, the coverage step is SKIPPED on exactly the
        runs whose windows most need marking screened -- silently reinstating the bug.
        """
        steps = self.job.get("steps", [])
        screens = next((s for s in steps if s.get("id") == "screens"), None)
        self.assertIsNotNone(screens, "screens step (id: screens) not found")
        run = screens["run"]
        self.assertIn('echo "src=${src}" >> "$GITHUB_OUTPUT"', run)
        self.assertIn('echo "drc=${drc}" >> "$GITHUB_OUTPUT"', run)
        self.assertNotIn("exit 1", run, "screens step must not fail on a finding")

    def test_resolver_greps_the_same_verdict_step_name(self) -> None:
        """The resolver's literal and the step's name must not drift apart."""
        steps = self.job.get("steps", [])
        resolver = next((s for s in steps if s.get("id") == "base"), None)
        self.assertIsNotNone(resolver, "resolver step (id: base) not found")
        run = resolver["run"]
        self.assertIn(self.VERDICT_STEP, run)
        self.assertIn(self.SCREEN_JOB, run)

    def test_resolver_prefers_the_screened_tier_over_legacy_success(self) -> None:
        """Tier 1 must be consulted first, and tier 2 must survive as the fallback.

        Deleting tier 2 would strand the FIRST run after this change (no historical run
        carries the tier-1 step name); deleting tier 1 is the defect itself.
        """
        steps = self.job.get("steps", [])
        resolver = next((s for s in steps if s.get("id") == "base"), None)
        self.assertIsNotNone(resolver)
        run = resolver["run"]
        self.assertIn("status=completed", run, "tier-1 walk over completed runs is missing")
        self.assertIn("status=success", run, "tier-2 legacy fallback is missing")
        self.assertLess(
            run.index('if [ -n "$screened" ]'),
            run.index('elif [ -n "$last_ok" ]'),
            "screened tier must be tested before the legacy success tier",
        )

    def test_screen_job_name_matches_the_workflow_job(self) -> None:
        """The resolver filters jobs by DISPLAY name; pin it to the real one."""
        self.assertEqual(self.job.get("name"), self.SCREEN_JOB)


if __name__ == "__main__":
    unittest.main()
