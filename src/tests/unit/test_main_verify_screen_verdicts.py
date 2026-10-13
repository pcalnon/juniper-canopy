"""Execute the main-verify screen-verdict shells.

``test_main_verify_catchup_base.py`` pins the step names and that the screens
step records exit codes. It never runs the two shells those names belong to.
A finding (exit 1) must stay screened, so the next catch-up advances past it.
An invocation error (exit >= 2), or a missing code, must not. The clean assert
must still fail the job on a finding. Those are different thresholds in two
steps; renaming a step does not keep them apart.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - runs the workflow's own extracted shell (fixed argv)
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

WORKFLOW_NAME = "main-verify.yml"
VERDICT_STEP = "Assert screens reached a verdict"
CLEAN_STEP = "Assert screens clean"
REPO = Path(__file__).resolve().parents[3]


def _child_env(**overrides: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),  # nosec B108 - bash fallback only
        "LANG": "C",
    }
    env.update(overrides)
    return env


def _step_script(name: str) -> str:
    wf = REPO / ".github" / "workflows" / WORKFLOW_NAME
    doc = yaml.safe_load(wf.read_text(encoding="utf-8"))
    steps = doc.get("jobs", {}).get("symbol-screen", {}).get("steps", [])
    step = next((s for s in steps if s.get("name") == name), None)
    if step is None or "run" not in step:
        raise AssertionError(f"{name!r} run step missing from {WORKFLOW_NAME}")
    return step["run"]


def _run(script: str, **env_vars: str) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "step.sh"
        path.write_text(script, encoding="utf-8")
        # GitHub Actions invokes ``run:`` with ``bash -eo pipefail``. The shells rely on
        # errexit for a non-numeric code; the numeric paths below take an explicit exit.
        return subprocess.run(  # nosec B603 B607 - extracted workflow shell, fixed argv
            ["bash", "-eo", "pipefail", str(path)],
            capture_output=True,
            text=True,
            env=_child_env(**env_vars),
            check=False,
            timeout=15,
        )


@pytest.fixture(scope="module")
def verdict_script() -> str:
    return _step_script(VERDICT_STEP)


@pytest.fixture(scope="module")
def clean_script() -> str:
    return _step_script(CLEAN_STEP)


def _assert_status(script: str, code: int, needle: str, **env_vars: str) -> None:
    proc = _run(script, **env_vars)
    combined = proc.stdout + proc.stderr
    assert proc.returncode == code, combined
    assert needle in combined


@pytest.mark.parametrize(("src", "drc"), [("1", "0"), ("0", "1"), ("1", "1")])
def test_a_finding_is_screened_and_is_not_clean(verdict_script: str, clean_script: str, src: str, drc: str) -> None:
    """Exit 1 is a verdict. The job still goes red, from the clean assert."""
    _assert_status(verdict_script, 0, "IS screened", SRC=src, DRC=drc)
    _assert_status(clean_script, 1, "compositional-loss finding", SRC=src, DRC=drc, HEAD_SHA="abc123")


@pytest.mark.parametrize(("src", "drc"), [("2", "0"), ("0", "2"), ("3", "1"), ("0", "9")])
def test_an_invocation_error_is_not_coverage(verdict_script: str, src: str, drc: str) -> None:
    """Exit >= 2 on either screen means the window was not screened."""
    _assert_status(verdict_script, 2, "NOT screened", SRC=src, DRC=drc)


def test_absent_and_empty_codes_are_invocation_errors(verdict_script: str, clean_script: str) -> None:
    """A missing output is 99, never a successful screen. Empty is missing."""
    _assert_status(verdict_script, 2, "NOT screened")
    _assert_status(verdict_script, 2, "NOT screened", SRC="", DRC="")
    _assert_status(verdict_script, 2, "NOT screened", SRC="0", DRC="")
    _assert_status(verdict_script, 2, "NOT screened", SRC="", DRC="0")
    clean = _run(clean_script, HEAD_SHA="abc123")
    assert clean.returncode == 1, clean.stdout + clean.stderr
    assert "compositional-loss finding" in clean.stdout + clean.stderr


def test_both_screens_clean_exits_zero(verdict_script: str, clean_script: str) -> None:
    _assert_status(verdict_script, 0, "IS screened", SRC="0", DRC="0")
    _assert_status(clean_script, 0, "screens clean", SRC="0", DRC="0", HEAD_SHA="abc123def456")
