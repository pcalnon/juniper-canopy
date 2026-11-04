"""Regression: Security Scans must write a Bandit SARIF report and a PR must fail when the upload fails.

Until 2026-10-29 the Security Scans job installed bare ``bandit``. The SARIF formatter ships in the
``bandit[sarif]`` extra, so ``bandit -f sarif`` exited with ``invalid choice: 'sarif'``, wrote no
report, and the step warned "Bandit found security issues" for an argument error. The upload then
ran with ``continue-on-error: true`` and hid ``Path does not exist: reports/security/bandit.sarif``
(main run 40942351409). juniper-canopy#780 installs the extra. juniper-canopy#781 makes a failed
upload fail the required Security Scans job on a pull request; every other event still tolerates it,
because no ruleset requires the code-scanning ``Bandit`` check the upload creates.

The structural tests read the workflows with PyYAML. The shell tests run the job's Bandit step under
GitHub Actions' shell (``bash -eo pipefail``) against a stub ``bandit``, so a formatter failure is
shown to be recorded rather than swallowed, and a clean scan is shown to leave the file the upload
reads. Nothing here installs Bandit or contacts GitHub.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess  # nosec B404 -- runs the workflow's own shell with a stub bandit on PATH, never a shell string
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.regression]

REPO_ROOT = Path(__file__).resolve().parents[3]
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
WEEKLY = REPO_ROOT / ".github" / "workflows" / "security-scan.yml"
SARIF_PATH = "reports/security/bandit.sarif"
SARIF_EXTRA = '"bandit[sarif]"'
# On a pull request a failed upload fails Security Scans. Every other event still tolerates it.
PR_UPLOAD_TOLERATES_FAILURE = "${{ github.event_name != 'pull_request' }}"
BANDIT_STEP = "Run Bandit (SAST) -> SARIF"
UPLOAD_STEP = "Upload Bandit SARIF to GitHub Security"

# GitHub Actions' default shell for a `run:` step on Linux.
ACTIONS_SHELL = ("bash", "--noprofile", "--norc", "-eo", "pipefail")

_STUB = """#!/bin/bash
out=""
fmt=""
prev=""
for arg in "$@"; do
  if [ "$prev" = "-o" ]; then out="$arg"; fi
  if [ "$prev" = "-f" ]; then fmt="$arg"; fi
  prev="$arg"
done
if [ "$fmt" = "sarif" ]; then
  case "${BANDIT_STUB_MODE}" in
    clean)
      printf '%s\\n' '{"version":"2.1.0","runs":[]}' > "$out"
      exit 0
      ;;
    findings)
      printf '%s\\n' '{"version":"2.1.0","runs":[{"results":[{}]}]}' > "$out"
      exit 1
      ;;
    no-formatter)
      echo "invalid choice: 'sarif'" >&2
      exit 2
      ;;
  esac
  echo "unknown BANDIT_STUB_MODE=${BANDIT_STUB_MODE}" >&2
  exit 99
fi
exit 0
"""


def _workflow(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), path.name
    return loaded


def _job_steps(doc: dict, job: str) -> list[dict]:
    steps = doc["jobs"][job]["steps"]
    assert isinstance(steps, list) and steps, job
    return steps


def _step(steps: list[dict], name: str) -> dict:
    matches = [step for step in steps if step.get("name") == name]
    assert len(matches) == 1, f"expected one step named {name!r}, found {len(matches)}"
    return matches[0]


def _pip_lines_naming_bandit(run: str) -> list[str]:
    return [line.strip() for line in run.splitlines() if "pip install" in line and "bandit" in line]


def _assert_installs_sarif_extra(run: str) -> None:
    """The install must name the extra, quoted, and must not also install bare bandit.

    ``[`` is a glob. An unquoted ``bandit[sarif]`` is not the extra the job means to install, and a
    line that installs bare ``bandit`` is the #780 failure even when the extra is named beside it.
    """
    lines = _pip_lines_naming_bandit(run)
    assert lines, "no pip install line names bandit"
    for line in lines:
        assert SARIF_EXTRA in line, f"{line}: the sarif extra must be installed as the quoted token {SARIF_EXTRA}"
        tokens = re.findall(r"bandit(?:\[[^\]]+\])?", line)
        assert tokens, line
        assert all(token == "bandit[sarif]" for token in tokens), f"{line}: a bare bandit install has no sarif formatter"


def _sarif_lines(run: str) -> list[str]:
    return [line.strip() for line in run.splitlines() if "-f sarif" in line]


def _security_steps() -> list[dict]:
    doc = _workflow(CI)
    assert doc["jobs"]["security"]["name"] == "Security Scans"
    return _job_steps(doc, "security")


def test_security_scans_installs_the_sarif_extra() -> None:
    install = _step(_security_steps(), "Install security tools")
    _assert_installs_sarif_extra(str(install.get("run", "")))


def test_a_pull_request_upload_failure_fails_the_job() -> None:
    upload = _step(_security_steps(), UPLOAD_STEP)
    # A boolean `true` is the silent #780 upload. A boolean `false` would fail pushes and dispatches,
    # which the 2026-10-30 ruling still tolerates. Only the event expression is both.
    assert upload.get("continue-on-error") == PR_UPLOAD_TOLERATES_FAILURE
    assert upload.get("if") == "always()", "a failed Bandit step must still reach the upload"
    assert str(upload.get("uses", "")).startswith("github/codeql-action/upload-sarif@")
    assert upload.get("with", {}).get("sarif_file") == SARIF_PATH


def test_the_scan_writes_the_file_the_upload_reads() -> None:
    steps = _security_steps()
    sarif = _sarif_lines(str(_step(steps, BANDIT_STEP).get("run", "")))
    assert len(sarif) == 1, "the Bandit step must invoke the sarif formatter exactly once"
    assert f"-o {SARIF_PATH}" in sarif[0]
    assert "|| true" not in sarif[0], "|| true would record a missing formatter as a clean scan"
    assert "|| BANDIT_EXIT=$?" in sarif[0], "a non-zero sarif invocation must be recorded, not discarded"
    assert _step(steps, UPLOAD_STEP).get("with", {}).get("sarif_file") == SARIF_PATH


@pytest.fixture
def bandit_step(tmp_path: Path) -> Path:
    """The Security Scans Bandit step, with reports/ already created as the previous step does."""
    script = tmp_path / "bandit-step.bash"
    script.write_text(str(_step(_security_steps(), BANDIT_STEP)["run"]), encoding="utf-8")
    (tmp_path / "reports" / "security").mkdir(parents=True)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "bandit"
    stub.write_text(_STUB, encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    return script


def _run_bandit_step(script: Path, mode: str) -> subprocess.CompletedProcess[str]:
    output = script.parent / "github_output.txt"
    env = {
        "PATH": f"{script.parent / 'bin'}{os.pathsep}/usr/bin{os.pathsep}/bin",
        "HOME": str(script.parent),
        "GITHUB_OUTPUT": str(output),
        "BANDIT_STUB_MODE": mode,
    }
    return subprocess.run(  # nosec B603
        [*ACTIONS_SHELL, str(script)],
        cwd=script.parent,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _recorded(script: Path) -> str:
    return (script.parent / "github_output.txt").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("mode", "issues", "report_exists"),
    [
        ("clean", "false", True),
        ("findings", "true", True),
        ("no-formatter", "true", False),
    ],
)
def test_the_bandit_step_records_the_scan_and_leaves_the_upload_a_report(bandit_step: Path, mode: str, issues: str, report_exists: bool) -> None:
    # The step itself stays green in every mode: findings are a warning, and a formatter failure must
    # still reach the upload step, which is what fails a pull request when the report was never written.
    result = _run_bandit_step(bandit_step, mode)
    assert result.returncode == 0, f"mode {mode} exited {result.returncode}: {result.stderr[-400:]}"
    assert f"bandit_found_issues={issues}" in _recorded(bandit_step)
    report = bandit_step.parent / SARIF_PATH
    assert report.is_file() is report_exists
    if report_exists:
        assert report.read_text(encoding="utf-8").strip().startswith("{")


def test_the_weekly_scan_installs_the_extra_and_does_not_swallow_a_formatter_error() -> None:
    doc = _workflow(WEEKLY)
    steps = _job_steps(doc, "security-scan")
    install = _step(steps, "Install dependencies")
    _assert_installs_sarif_extra(str(install.get("run", "")))
    bandit = _step(steps, "Run Bandit (SAST)")
    sarif = _sarif_lines(str(bandit.get("run", "")))
    assert len(sarif) == 1
    assert f"-o {SARIF_PATH}" in sarif[0]
    assert "|| true" not in sarif[0], "the weekly job has no code-scanning upload; swallowing the formatter error would hide a missing report"
    upload = _step(steps, "Upload Security Reports")
    assert upload.get("if") == "always()"
    assert str(upload.get("with", {}).get("path", "")).rstrip("/") == "reports/security"
