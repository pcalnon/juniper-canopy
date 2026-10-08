"""Execute the main-verify failure-notify shell.

The catch-up rehearsal never runs the tracker upsert. The tracker is one open
issue per red streak, matched on the workflow's own authorship plus the exact
title. A pull request, a longer title, a case change, or a later duplicate must
not capture it. Opening the issue is the point of the job: a failed create
fails the step, and a failed label does not. This workflow has no Slack step.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404 - runs the workflow's own extracted shell (fixed argv)
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_NAME = "main-verify.yml"
UPSERT_STEP = "Upsert tracking issue (stable title, one per red streak)"
TITLE = "main-verify: post-merge verification failing"
SHA = "abc123def4567890aaaa"
TOKEN = "ghp_SENTINEL_NOT_A_REAL_TOKEN"  # nosec B105 - fixture sentinel, asserted absent from output
REPO = "pcalnon/juniper-canopy"

_GH_STUB = r"""#!/usr/bin/env bash
set -euo pipefail
printf '%s\0' "$@" >> "$GH_LOG"
printf '\n' >> "$GH_LOG"
cmd="${1:-}"
shift || true
if [ "$cmd" = "api" ]; then
  url=""
  jq_filter=""
  prev=""
  for a in "$@"; do
    if [ "$prev" = "--jq" ]; then
      jq_filter="$a"
    fi
    case "$a" in
      repos/*) url="$a" ;;
    esac
    prev="$a"
  done
  printf '%s\n' "$url" >> "$GH_URLS"
  if [ "${GH_API_RC:-0}" != "0" ]; then
    echo "api failed" >&2
    exit "${GH_API_RC}"
  fi
  if [ -n "$jq_filter" ]; then
    jq -r "$jq_filter" "$GH_ISSUES_JSON"
  else
    cat "$GH_ISSUES_JSON"
  fi
  exit 0
fi
if [ "$cmd" = "label" ]; then
  exit "${GH_LABEL_RC:-0}"
fi
if [ "$cmd" = "issue" ]; then
  sub="${1:-}"
  if [ "$sub" = "comment" ]; then
    exit "${GH_COMMENT_RC:-0}"
  fi
  if [ "$sub" = "create" ]; then
    if [ "${GH_CREATE_RC:-0}" != "0" ]; then
      echo "create failed" >&2
      exit "${GH_CREATE_RC}"
    fi
    printf '%s\n' "https://github.com/pcalnon/juniper-canopy/issues/${GH_NEW_NUMBER:-77}"
    exit 0
  fi
  if [ "$sub" = "edit" ]; then
    exit "${GH_EDIT_RC:-0}"
  fi
fi
echo "unexpected gh invocation: $cmd" >&2
exit 99
"""


def _workflow() -> dict:
    wf = REPO_ROOT / ".github" / "workflows" / WORKFLOW_NAME
    return yaml.safe_load(wf.read_text(encoding="utf-8"))


def _step(job: str, name: str) -> dict:
    steps = _workflow().get("jobs", {}).get(job, {}).get("steps", [])
    step = next((s for s in steps if s.get("name") == name), None)
    if step is None or "run" not in step:
        raise AssertionError(f"{name!r} run step missing from {job}")
    return step


def _invocations(log: Path) -> list[list[str]]:
    if not log.is_file():
        return []
    rows: list[list[str]] = []
    for row in log.read_bytes().split(b"\n"):
        if not row:
            continue
        rows.append([part.decode() for part in row.split(b"\0") if part])
    return rows


def _commands(invocations: list[list[str]], *prefix: str) -> list[list[str]]:
    return [inv for inv in invocations if inv[: len(prefix)] == list(prefix)]


class _Ran:
    def __init__(self, proc: subprocess.CompletedProcess[str], invocations: list[list[str]], urls: list[str], bodies: dict[str, str]) -> None:
        self.proc = proc
        self.invocations = invocations
        self.urls = urls
        self.bodies = bodies

    @property
    def returncode(self) -> int:
        return self.proc.returncode

    @property
    def output(self) -> str:
        return self.proc.stdout + self.proc.stderr


@pytest.fixture(scope="module")
def upsert_script() -> str:
    notify = _workflow()["jobs"]["notify"]
    assert notify.get("if") == "failure()", "notify must stay on failure() so a green main does not file a tracker"
    script = _step("notify", UPSERT_STEP)["run"]
    assert "SLACK" not in script and "webhook" not in script.lower()
    return script


def _run(
    script: str,
    issues: list[dict],
    *,
    api_rc: int = 0,
    comment_rc: int = 0,
    create_rc: int = 0,
    label_rc: int = 0,
    edit_rc: int = 0,
) -> _Ran:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        work = root / "work"
        work.mkdir()
        bin_dir = root / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(_GH_STUB, encoding="utf-8")
        gh.chmod(0o755)
        log = root / "gh.log"
        urls = root / "urls.txt"
        issues_path = root / "issues.json"
        issues_path.write_text(json.dumps(issues), encoding="utf-8")
        env = {
            "PATH": str(bin_dir) + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(root),
            "LANG": "C",
            "GH_TOKEN": TOKEN,
            "REPO": REPO,
            "TITLE": TITLE,
            "SHA": SHA,
            "RUN_URL": f"https://github.com/{REPO}/actions/runs/99",
            "SYMBOL_RESULT": "failure",
            "GH_LOG": str(log),
            "GH_URLS": str(urls),
            "GH_ISSUES_JSON": str(issues_path),
            "GH_API_RC": str(api_rc),
            "GH_COMMENT_RC": str(comment_rc),
            "GH_CREATE_RC": str(create_rc),
            "GH_LABEL_RC": str(label_rc),
            "GH_EDIT_RC": str(edit_rc),
        }
        script_path = work / "upsert.sh"
        script_path.write_text(script, encoding="utf-8")
        proc = subprocess.run(  # nosec B603 B607 - extracted workflow shell, fixed argv
            ["bash", "-eo", "pipefail", str(script_path)],
            cwd=work,
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=15,
        )
        url_lines = urls.read_text(encoding="utf-8").splitlines() if urls.is_file() else []
        bodies = {}
        for name in ("issue-body.md", "issue-comment.md"):
            path = work / name
            if path.is_file():
                bodies[name] = path.read_text(encoding="utf-8")
        return _Ran(proc, _invocations(log), url_lines, bodies)


def _assert_no_token(ran: _Ran) -> None:
    blob = ran.output + "".join(ran.bodies.values())
    assert TOKEN not in blob


def test_notify_job_runs_only_on_failure() -> None:
    assert _workflow()["jobs"]["notify"]["if"] == "failure()"
    names = [step.get("name") for step in _workflow()["jobs"]["notify"]["steps"]]
    assert UPSERT_STEP in names
    assert not any("slack" in str(name).lower() for name in names)


def test_first_exact_issue_is_commented_and_decoys_are_not(upsert_script: str) -> None:
    issues = [
        {"number": 11, "title": TITLE, "pull_request": {"url": "https://example.test/pull/11"}},
        {"number": 12, "title": TITLE + " today"},
        {"number": 13, "title": "Main-verify: post-merge verification failing"},
        {"number": 14, "title": "main-verify: post-merge"},
        {"number": 15, "title": TITLE},
        {"number": 16, "title": TITLE},
    ]
    ran = _run(upsert_script, issues)
    assert ran.returncode == 0, ran.output
    comments = _commands(ran.invocations, "issue", "comment")
    assert [inv[2] for inv in comments] == ["15"]
    assert _commands(ran.invocations, "issue", "create") == []
    assert SHA in ran.bodies["issue-comment.md"]
    assert ran.urls
    assert "creator=github-actions%5Bbot%5D" in ran.urls[0]
    assert "state=open" in ran.urls[0]
    assert "per_page=100" in ran.urls[0]
    assert "creator=github-actions[bot]" not in ran.urls[0]
    _assert_no_token(ran)


def test_no_match_opens_one_issue_under_the_stable_title(upsert_script: str) -> None:
    ran = _run(upsert_script, [])
    assert ran.returncode == 0, ran.output
    creates = _commands(ran.invocations, "issue", "create")
    assert len(creates) == 1
    title_at = creates[0].index("--title")
    assert creates[0][title_at + 1] == TITLE
    assert SHA not in creates[0][title_at + 1]
    body = ran.bodies["issue-body.md"]
    assert SHA in body
    edits = _commands(ran.invocations, "issue", "edit")
    assert [inv[2] for inv in edits] == ["77"]
    assert "--add-label" in edits[0]
    assert "main-verify" in edits[0]
    assert "--force" not in edits[0]
    labels = _commands(ran.invocations, "label", "create")
    assert len(labels) == 1
    assert "main-verify" in labels[0]
    assert "--force" not in labels[0]
    _assert_no_token(ran)


def test_label_failures_still_exit_zero(upsert_script: str) -> None:
    ran = _run(upsert_script, [], label_rc=1, edit_rc=1)
    assert ran.returncode == 0, ran.output
    assert len(_commands(ran.invocations, "issue", "create")) == 1
    assert len(_commands(ran.invocations, "issue", "edit")) == 1
    assert len(_commands(ran.invocations, "label", "create")) == 1


def test_issue_create_failure_exits_and_does_not_edit(upsert_script: str) -> None:
    ran = _run(upsert_script, [], create_rc=1)
    assert ran.returncode != 0
    assert "failed to open" in ran.output
    assert _commands(ran.invocations, "issue", "edit") == []
    assert len(_commands(ran.invocations, "issue", "create")) == 1


def test_comment_failure_does_not_open_another_issue(upsert_script: str) -> None:
    ran = _run(upsert_script, [{"number": 15, "title": TITLE}], comment_rc=1)
    assert ran.returncode != 0
    assert _commands(ran.invocations, "issue", "create") == []
    assert [inv[2] for inv in _commands(ran.invocations, "issue", "comment")] == ["15"]


def test_list_failure_still_opens_and_the_query_is_scoped(upsert_script: str) -> None:
    ran = _run(upsert_script, [{"number": 15, "title": TITLE}], api_rc=1)
    assert ran.returncode == 0, ran.output
    assert len(_commands(ran.invocations, "issue", "create")) == 1
    assert _commands(ran.invocations, "issue", "comment") == []
    assert len(ran.urls) == 1
    assert "creator=github-actions%5Bbot%5D" in ran.urls[0]
    assert "state=open" in ran.urls[0]
    assert "per_page=100" in ran.urls[0]
    assert "creator=github-actions[bot]" not in ran.urls[0]
