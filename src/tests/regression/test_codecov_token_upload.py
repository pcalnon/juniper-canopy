"""The unit lane's Codecov upload must send the repository token and the file pytest wrote.

``#779`` added ``token: ${{ secrets.CODECOV_TOKEN }}`` to "Upload Coverage to Codecov".
Without it Codecov refused the upload ("Token required - not valid tokenless upload")
inside a step whose ``fail_ci_if_error: false`` keeps the job green, so coverage for
``main`` stopped updating and CI stayed green. The tests that landed with that commit
cover the memory-budget suite moving into ``src/tests/unit/``. They do not read this step.

A comment in the workflow already names the secret, so a search of the file text is
satisfied by the prose. This module loads the YAML and checks the step. The same check
rejects a second upload that omits the token, a token that is a different secret or
empty, and an upload whose ``files`` are not the ``--cov-report=xml:`` path the job's
own pytest invocation writes. A comment or an ``echo`` of that flag is not a write.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.regression]

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

TOKEN = "${{ secrets.CODECOV_TOKEN }}"
ACTION = "codecov/codecov-action@"

_PYTEST = "python -m pytest src/tests/unit/ --cov-report=xml:reports/coverage.xml\n"


def _strip_comments(shell: str) -> str:
    """Drop whole-line ``#`` comments. A comment that names the flag is not a command."""
    return "\n".join(line for line in shell.splitlines() if not line.lstrip().startswith("#"))


def _pytest_xml_paths(steps: list) -> set[str]:
    """``--cov-report=xml:`` paths from comment-stripped run steps that invoke pytest."""
    found: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            continue
        body = _strip_comments(str(step.get("run") or ""))
        if not re.search(r"\bpytest\b", body):
            continue
        for match in re.finditer(r"--cov-report=xml:(\S+)", body):
            found.add(match.group(1).rstrip("\\").strip("'\""))
    return found


def _file_entries(files: object) -> list[str]:
    """Exact file entries. A longer name that merely contains the path does not match."""
    if files is None:
        return []
    parts = files if isinstance(files, list) else re.split(r"[\n,]", str(files))
    return [str(part).strip().strip("'\"") for part in parts if str(part).strip()]


def codecov_upload_problems(doc: dict) -> list[str]:
    """Problems with every ``codecov/codecov-action`` step. Empty means the upload is wired.

    Each such step must sit in a job whose pytest invocation writes at least one coverage
    XML file, must send ``TOKEN`` exactly, and must name every XML path that invocation writes.
    """
    problems: list[str] = []
    uploads = 0
    jobs = doc.get("jobs") or {}
    if not isinstance(jobs, dict):
        return ["workflow has no jobs map"]
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        if not isinstance(steps, list):
            continue
        written = _pytest_xml_paths(steps)
        for step in steps:
            if not isinstance(step, dict):
                continue
            uses = str(step.get("uses") or "")
            if not uses.startswith(ACTION):
                continue
            uploads += 1
            where = f"{job_id} / {step.get('name') or uses}"
            entered = step.get("with") if isinstance(step.get("with"), dict) else {}
            token = entered.get("token")
            if token != TOKEN:
                problems.append(f"{where}: token is {token!r}, expected {TOKEN}")
            if not written:
                problems.append(f"{where}: no pytest --cov-report=xml: path in this job")
                continue
            entries = _file_entries(entered.get("files"))
            missing = sorted(written - set(entries))
            if missing:
                problems.append(f"{where}: files {entries} omit the xml path pytest writes: {', '.join(missing)}")
    if uploads == 0:
        problems.append("no codecov/codecov-action step")
    return problems


def _workflow() -> dict:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _doc(pytest_run: str, *, token: str | None = TOKEN, files: object = "reports/coverage.xml", extra_steps: list | None = None) -> dict:
    entered: dict = {}
    if token is not None:
        entered["token"] = token
    if files is not None:
        entered["files"] = files
    steps: list = [
        {"name": "Unit Tests", "run": pytest_run},
        {"name": "Upload Coverage to Codecov", "uses": "codecov/codecov-action@deadbeef", "with": entered},
    ]
    if extra_steps:
        steps.extend(extra_steps)
    return {"jobs": {"unit-tests": {"steps": steps}}}


def test_shipped_unit_lane_sends_the_token_and_the_file_pytest_writes() -> None:
    """The workflow on disk, parsed. The comment above the step does not count."""
    problems = codecov_upload_problems(_workflow())
    assert problems == [], "Codecov upload is not wired to the repository token and the xml pytest writes: " + "; ".join(problems)


def test_a_comment_naming_the_secret_does_not_count() -> None:
    text = """
jobs:
  unit-tests:
    steps:
      - name: Unit Tests
        run: |
          # token: ${{ secrets.CODECOV_TOKEN }}
          python -m pytest --cov-report=xml:reports/coverage.xml
      - name: Upload Coverage to Codecov
        # token: ${{ secrets.CODECOV_TOKEN }}
        uses: codecov/codecov-action@303a32d7a59b442fa8d48b6a1cc6825c09c847a5
        with:
          files: reports/coverage.xml
"""
    problems = codecov_upload_problems(yaml.safe_load(text))
    assert any("token is None" in problem for problem in problems), problems


def test_a_commented_cov_report_flag_is_not_a_write() -> None:
    run = "# --cov-report=xml:reports/coverage.xml\npython -m pytest src/tests/unit/\n"
    problems = codecov_upload_problems(_doc(run))
    assert any("no pytest --cov-report=xml:" in problem for problem in problems), problems


def test_echoing_the_flag_without_pytest_is_not_a_write() -> None:
    problems = codecov_upload_problems(_doc("echo --cov-report=xml:reports/coverage.xml\n"))
    assert any("no pytest --cov-report=xml:" in problem for problem in problems), problems


def test_upload_that_names_a_different_file_is_rejected() -> None:
    problems = codecov_upload_problems(_doc(_PYTEST, files="reports/other.xml"))
    assert any("reports/coverage.xml" in problem for problem in problems), problems


def test_a_filename_that_merely_contains_the_xml_path_does_not_count() -> None:
    problems = codecov_upload_problems(_doc(_PYTEST, files="reports/coverage.xml.bak"))
    assert any("reports/coverage.xml" in problem for problem in problems), problems


@pytest.mark.parametrize("token", ["", "${{ secrets.GITHUB_TOKEN }}", "secrets.CODECOV_TOKEN"])
def test_only_the_repository_secret_expression_counts(token: str) -> None:
    problems = codecov_upload_problems(_doc(_PYTEST, token=token))
    assert any(f"token is {token!r}" in problem for problem in problems), problems


def test_an_omitted_token_key_is_rejected() -> None:
    problems = codecov_upload_problems(_doc(_PYTEST, token=None))
    assert any("token is None" in problem for problem in problems), problems


def test_a_second_upload_without_a_token_is_rejected() -> None:
    extra = {"name": "Upload again", "uses": "codecov/codecov-action@abc", "with": {"files": "reports/coverage.xml"}}
    problems = codecov_upload_problems(_doc(_PYTEST, extra_steps=[extra]))
    assert any("Upload again" in problem and "token is None" in problem for problem in problems), problems


@pytest.mark.parametrize(
    "files",
    [
        "reports/coverage.xml",
        "reports/coverage.xml,reports/coverage.json",
        ["reports/coverage.json", "reports/coverage.xml"],
    ],
)
def test_files_that_include_the_xml_path_are_accepted(files: object) -> None:
    assert codecov_upload_problems(_doc(_PYTEST, files=files)) == []


def test_every_xml_path_pytest_writes_is_uploaded() -> None:
    run = "python -m pytest --cov-report=xml:reports/coverage.xml --cov-report=xml:reports/other.xml\n"
    problems = codecov_upload_problems(_doc(run, files="reports/coverage.xml"))
    assert any("reports/other.xml" in problem for problem in problems), problems


def test_removing_the_codecov_step_is_rejected() -> None:
    doc = _doc(_PYTEST)
    doc["jobs"]["unit-tests"]["steps"] = doc["jobs"]["unit-tests"]["steps"][:1]
    problems = codecov_upload_problems(doc)
    assert problems == ["no codecov/codecov-action step"]
