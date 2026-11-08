"""
Pin the AGENTS.md date check (``.github/workflows/agents-md-touch-up.yml``).

The job used to rewrite the header, commit, and push. That left unsigned
commits and ``[skip ci]`` orphans, so it now only verifies. These tests run
that verify step. A missing field warns and passes. A value that is not
YYYY-MM-DD fails. A future date fails even when the line was added. Today's
UTC date passes with no diff and with ``BASE_SHA`` unset. A past bump that is
not today passes. An unchanged header fails even if prose mentions the
marker. A three-dot diff against a base tip that moved the header does not
treat the PR's old line as a bump. Surrounding whitespace still parses. Only
the first header line is the value. The checkout action stays a full commit
SHA with full history, and the job cannot push.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "agents-md-touch-up.yml"
SHA_PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")
TODAY = "2026-11-04"

DATE_STUB = """#!/bin/bash
if [ "$#" -eq 2 ] && [ "$1" = "-u" ] && [ "$2" = "+%Y-%m-%d" ]; then
  printf '%s\\n' "$FIXED_TODAY"
  exit 0
fi
printf 'unexpected date invocation: %s\\n' "$*" >&2
exit 1
"""


def _workflow() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) reads the bare `on:` key as boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _steps() -> list[dict]:
    return _workflow()["jobs"]["verify-date"]["steps"]


def _verify_step() -> dict:
    matches = [step for step in _steps() if str(step.get("name", "")).startswith("Verify AGENTS.md")]
    assert len(matches) == 1, matches
    return matches[0]


# The fixture's git, and the verify step's own `git diff`, must not read the developer's
# global or system config. CI's runner has none, so these all pass there and fail only on a
# workstation: commit.gpgsign asks a hardware key to sign every fixture commit (a PIN prompt,
# or a hang), color.ui=always puts escape codes into the diff the step parses, and a refusing
# core.hooksPath hook fails every fixture commit. The identity is set per repository in _init.
_UNSIGNED = ("-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false")


def _hermetic_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *_UNSIGNED, "-C", str(repo), *args], env=_hermetic_env(), check=True, capture_output=True, text=True)


def _init(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "agents-md-test@example.com")
    _git(repo, "config", "user.name", "Agents Md Test")


def _commit(repo: Path, body: str, message: str) -> str:
    (repo / "AGENTS.md").write_text(body, encoding="utf-8")
    _git(repo, "add", "AGENTS.md")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _doc(date: str, extra: str = "") -> str:
    return f"**Last Updated**: {date}\n{extra}"


def _run(repo: Path, *, base_sha: str | None, today: str = TODAY) -> subprocess.CompletedProcess[str]:
    bin_dir = repo / ".stub-bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "date"
    stub.write_text(DATE_STUB, encoding="utf-8")
    stub.chmod(0o755)
    env = _hermetic_env()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["FIXED_TODAY"] = today
    env.pop("BASE_SHA", None)
    if base_sha is not None:
        env["BASE_SHA"] = base_sha
    return subprocess.run(
        ["bash", "-c", _verify_step()["run"]],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class TestHeaderValue:
    def test_a_missing_field_warns_and_passes(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("# Guide\nNo header here.\n", encoding="utf-8")
        result = _run(repo, base_sha=None)
        assert result.returncode == 0
        assert "no '**Last Updated**:' field" in result.stdout
        assert "nothing to verify" in result.stdout

    @pytest.mark.parametrize("value", ["yesterday", "2026/11/04", "2026-11-4"])
    def test_a_non_iso_value_fails_and_names_itself(self, tmp_path: Path, value: str):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text(f"**Last Updated**: {value}\n", encoding="utf-8")
        result = _run(repo, base_sha=None)
        assert result.returncode == 1
        assert "not a YYYY-MM-DD date" in result.stdout
        assert value in result.stdout

    def test_an_empty_value_fails(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("**Last Updated**:\n", encoding="utf-8")
        result = _run(repo, base_sha=None)
        assert result.returncode == 1
        assert "not a YYYY-MM-DD date: ''" in result.stdout

    def test_a_future_date_fails_even_when_the_line_was_added(self, tmp_path: Path):
        repo = tmp_path / "repo"
        _init(repo)
        base = _commit(repo, _doc("2020-01-01"), "old")
        _commit(repo, _doc("2999-01-01"), "bumped into the future")
        result = _run(repo, base_sha=base)
        assert result.returncode == 1
        assert "in the future" in result.stdout
        assert "2999-01-01" in result.stdout
        assert "was bumped" not in result.stdout

    def test_today_passes_with_no_diff_and_with_base_sha_unset(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text(_doc(TODAY), encoding="utf-8")
        result = _run(repo, base_sha=None)
        assert result.returncode == 0
        assert "already today's UTC date" in result.stdout
        assert "BASE_SHA" not in result.stderr

    @pytest.mark.parametrize(
        "line",
        [
            "**Last Updated**:   2026-11-04  \n",
            "**Last Updated**:2026-11-04\n",
            "**Last Updated**:\t2026-11-04\t\n",
        ],
    )
    def test_surrounding_whitespace_still_parses_as_today(self, tmp_path: Path, line: str):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "AGENTS.md").write_text(line, encoding="utf-8")
        result = _run(repo, base_sha=None)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "already today's UTC date" in result.stdout

    def test_only_the_first_header_line_is_the_value(self, tmp_path: Path):
        repo = tmp_path / "good"
        repo.mkdir()
        (repo / "AGENTS.md").write_text("**Last Updated**: 2026-11-04\n**Last Updated**: not-a-date\n", encoding="utf-8")
        good = _run(repo, base_sha=None)
        assert good.returncode == 0
        assert "already today's UTC date" in good.stdout

        bad_repo = tmp_path / "bad"
        bad_repo.mkdir()
        (bad_repo / "AGENTS.md").write_text("**Last Updated**: not-a-date\n**Last Updated**: 2026-11-04\n", encoding="utf-8")
        bad = _run(bad_repo, base_sha=None)
        assert bad.returncode == 1
        assert "not-a-date" in bad.stdout
        assert "already today's UTC date" not in bad.stdout


class TestTheDiff:
    def test_a_past_bump_that_is_not_today_passes(self, tmp_path: Path):
        repo = tmp_path / "repo"
        _init(repo)
        base = _commit(repo, _doc("2020-01-01"), "old")
        _commit(repo, _doc("2020-06-01"), "bumped")
        result = _run(repo, base_sha=base)
        assert result.returncode == 0
        assert "was bumped in this PR" in result.stdout
        assert "2020-06-01" in result.stdout

    def test_an_unchanged_header_fails_even_if_prose_mentions_the_marker(self, tmp_path: Path):
        repo = tmp_path / "repo"
        _init(repo)
        base = _commit(repo, _doc("2020-01-01", "hello\n"), "old")
        _commit(repo, _doc("2020-01-01", "hello\nSee the **Last Updated**: field.\n"), "prose")
        result = _run(repo, base_sha=base)
        assert result.returncode == 1
        assert "was bumped" not in result.stdout
        assert "still 2020-01-01" in result.stdout
        assert f"**Last Updated**: {TODAY}" in result.stdout

    def test_a_base_tip_that_moved_the_header_is_not_this_prs_bump(self, tmp_path: Path):
        """Two-dot against that base shows the PR's old line as an addition. Three-dot does not."""
        repo = tmp_path / "repo"
        _init(repo)
        _commit(repo, _doc("2020-01-01", "intro\n"), "merge base")
        _git(repo, "branch", "pr")
        base = _commit(repo, _doc("2020-06-01", "intro\n"), "base moved the header")
        _git(repo, "checkout", "pr")
        _commit(repo, _doc("2020-01-01", "intro\nThe **Last Updated**: field is mentioned.\n"), "prose only")
        two_dot = _git(repo, "diff", base, "HEAD", "--", "AGENTS.md").stdout
        three_dot = _git(repo, "diff", f"{base}...HEAD", "--", "AGENTS.md").stdout
        assert any(line.startswith("+**Last Updated**:") for line in two_dot.splitlines())
        assert not any(line.startswith("+**Last Updated**:") for line in three_dot.splitlines())
        result = _run(repo, base_sha=base)
        assert result.returncode == 1
        assert "was bumped" not in result.stdout
        assert "still 2020-01-01" in result.stdout

    def test_an_unset_base_sha_on_the_diff_path_fails_closed(self, tmp_path: Path):
        repo = tmp_path / "repo"
        _init(repo)
        _commit(repo, _doc("2020-01-01"), "old")
        result = _run(repo, base_sha=None)
        assert result.returncode != 0
        assert "BASE_SHA" in result.stderr
        assert "unbound variable" in result.stderr
        assert "was bumped" not in result.stdout


class TestWorkflowContract:
    def test_it_verifies_on_pull_requests_that_touch_agents_md(self):
        on = _workflow()["on"]["pull_request"]
        assert on["types"] == ["opened", "reopened", "synchronize"]
        assert on["paths"] == ["AGENTS.md"]
        assert _workflow()["permissions"] == {"contents": "read"}
        assert _workflow()["concurrency"]["cancel-in-progress"] is True
        assert "pull_request.number" in _workflow()["concurrency"]["group"]

    def test_checkout_is_sha_pinned_and_has_the_history_the_three_dot_diff_needs(self):
        step = next(step for step in _steps() if str(step.get("uses", "")).startswith("actions/checkout@"))
        assert SHA_PINNED.match(step["uses"]), step["uses"]
        assert step["with"]["fetch-depth"] == 0
        assert step["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"

    def test_the_verify_step_reads_the_base_sha_and_does_not_rewrite_or_push(self):
        step = _verify_step()
        script = step["run"]
        assert step["env"]["BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
        assert 'git diff "${BASE_SHA}...HEAD"' in script
        assert "git commit" not in script
        assert "git push" not in script
        assert "continue-on-error" not in step
