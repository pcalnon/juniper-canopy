"""
Pin the open-PR budget alarm (``.github/workflows/pr-budget-alarm.yml``).

The alarm is report-only: a breach stays green, and a failed ``gh pr list`` stays
green too. The failure must not look like an empty queue, or a GitHub blip
would clear an alarm that had been firing. Thresholds are ``>=`` against the
repo variables, and an empty variable is the default (15 / 30), not zero.
Only a branch whose name starts with ``cursor/`` counts toward the cursor
budget. The Slack body carries the counts and the run URL, never the webhook.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "pr-budget-alarm.yml"

GH_STUB = """#!/bin/bash
printf '%s\\n' "$@" > "$GH_ARGS"
if [ "${GH_RC}" -ne 0 ]; then
  printf '%s' "$GH_ERR" >&2
  exit "${GH_RC}"
fi
printf '%s' "$GH_STDOUT"
"""

CURL_STUB = """#!/bin/bash
printf '%s\\0' "$@" > "$CURL_ARGS"
exit "${CURL_RC}"
"""


def _workflow() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) reads the bare `on:` key as boolean True.
    data["on"] = data.pop(True, data.get("on"))
    return data


def _step(name_prefix: str) -> dict:
    matches = [s for s in _workflow()["jobs"]["budget-alarm"]["steps"] if str(s.get("name", "")).startswith(name_prefix)]
    assert len(matches) == 1, name_prefix
    return matches[0]


def _outputs(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            parsed[key] = value
    return parsed


def _install(tmp_path: Path, name: str, body: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return bin_dir


def _prs(names: list[str]) -> str:
    return json.dumps([{"number": index + 1, "headRefName": name} for index, name in enumerate(names)])


def _run_count(tmp_path: Path, *, names: list[str] | None = None, raw: str | None = None, gh_rc: int = 0, gh_err: str = "", warn: str | None = "", alarm: str | None = ""):
    bin_dir = _install(tmp_path, "gh", GH_STUB)
    output = tmp_path / "github_output"
    summary = tmp_path / "step_summary"
    output.write_text("", encoding="utf-8")
    summary.write_text("", encoding="utf-8")
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["GH_TOKEN"] = "test-token"
    env["GH_REPO"] = "pcalnon/juniper-canopy"
    env["GITHUB_OUTPUT"] = str(output)
    env["GITHUB_STEP_SUMMARY"] = str(summary)
    env["GH_ARGS"] = str(tmp_path / "gh.args")
    env["GH_RC"] = str(gh_rc)
    env["GH_ERR"] = gh_err
    env["GH_STDOUT"] = raw if raw is not None else _prs(names or [])
    if warn is None:
        env.pop("PR_BUDGET_WARN", None)
    else:
        env["PR_BUDGET_WARN"] = warn
    if alarm is None:
        env.pop("PR_BUDGET_ALARM", None)
    else:
        env["PR_BUDGET_ALARM"] = alarm
    result = subprocess.run(
        ["bash", "-c", _step("Count open PRs")["run"]],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    args = (tmp_path / "gh.args").read_text(encoding="utf-8") if (tmp_path / "gh.args").exists() else ""
    return result, _outputs(output.read_text(encoding="utf-8")), summary.read_text(encoding="utf-8"), args


def _run_slack(tmp_path: Path, *, webhook: str, level: str = "WARN", total: str = "16", cursor: str = "2", curl_rc: int = 0):
    bin_dir = _install(tmp_path, "curl", CURL_STUB)
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["SLACK_WEBHOOK_URL"] = webhook
    env["RUN_URL"] = "https://github.com/pcalnon/juniper-canopy/actions/runs/99"
    env["LEVEL"] = level
    env["TOTAL"] = total
    env["CURSOR"] = cursor
    env["WARN"] = "15"
    env["ALARM"] = "30"
    env["CURL_ARGS"] = str(tmp_path / "curl.args")
    env["CURL_RC"] = str(curl_rc)
    result = subprocess.run(
        ["bash", "-c", _step("Slack notification")["run"]],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    recorded = (tmp_path / "curl.args").read_text(encoding="utf-8") if (tmp_path / "curl.args").exists() else ""
    return result, recorded


class TestBudgetThresholds:
    def test_empty_and_unset_variables_default_to_15_and_30(self, tmp_path):
        for warn, alarm in (("", ""), (None, None)):
            _, outputs, summary, _ = _run_count(tmp_path, names=[], warn=warn, alarm=alarm)
            assert outputs["warn"] == "15"
            assert outputs["alarm"] == "30"
            assert outputs["level"] == "OK"
            assert "| Warn threshold (`PR_BUDGET_WARN`) | 15 |" in summary
            assert "| Alarm threshold (`PR_BUDGET_ALARM`) | 30 |" in summary

    @pytest.mark.parametrize(
        ("count", "level"),
        [(14, "OK"), (15, "WARN"), (29, "WARN"), (30, "ALARM")],
    )
    def test_total_boundaries_are_inclusive(self, tmp_path, count, level):
        _, outputs, summary, _ = _run_count(tmp_path, names=["feature/a"] * count)
        assert outputs["total"] == str(count)
        assert outputs["cursor"] == "0"
        assert outputs["level"] == level
        assert f"**{level}**" in summary

    @pytest.mark.parametrize(
        ("count", "level"),
        [(14, "OK"), (15, "WARN"), (30, "ALARM")],
    )
    def test_the_cursor_subset_breaches_on_its_own(self, tmp_path, count, level):
        _, outputs, _, _ = _run_count(tmp_path, names=["cursor/flood"] * count)
        assert outputs["total"] == str(count)
        assert outputs["cursor"] == str(count)
        assert outputs["level"] == level

    def test_alarm_wins_when_both_thresholds_are_crossed(self, tmp_path):
        _, outputs, summary, _ = _run_count(tmp_path, names=["feature/a"] * 30)
        assert outputs["level"] == "ALARM"
        assert "WARN:" not in summary
        assert "ALARM:" in summary

    def test_only_a_cursor_slash_prefix_counts(self, tmp_path):
        """A looser prefix (`cursor`, or any `cursor` substring) would count the decoys too."""
        names = ["cursor/real", "cursor", "Cursor/no", "feature/cursor/no", "cursorfoo"]
        _, outputs, _, _ = _run_count(tmp_path, names=names)
        assert outputs["total"] == "5"
        assert outputs["cursor"] == "1"
        assert outputs["level"] == "OK"

    def test_the_query_is_open_prs_only_and_capped(self, tmp_path):
        _, _, _, args = _run_count(tmp_path, names=["feature/a"])
        assert args.splitlines() == ["pr", "list", "--repo", "pcalnon/juniper-canopy", "--state", "open", "--limit", "500", "--json", "number,headRefName"]


class TestQueryFailureStaysGreen:
    def test_gh_failure_is_not_an_empty_queue(self, tmp_path):
        result, outputs, summary, _ = _run_count(tmp_path, gh_rc=1, gh_err="rate limit\nexceeded")
        assert result.returncode == 0
        assert outputs == {"level": "OK"}
        assert "total=" not in (tmp_path / "github_output").read_text(encoding="utf-8")
        assert "Could not query open PRs" in summary
        assert "rate limit exceeded" in result.stdout
        assert result.returncode == 0

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        _, empty, _, _ = _run_count(empty_dir, names=[])
        assert empty["total"] == "0"
        assert empty["cursor"] == "0"
        assert "total" not in outputs

    def test_invalid_json_does_not_pass_as_an_empty_queue(self, tmp_path):
        result, outputs, _, _ = _run_count(tmp_path, raw="not-json")
        assert result.returncode != 0
        assert outputs.get("total") != "0"
        assert not (outputs.get("level") == "OK" and outputs.get("total") == "0")


class TestSlackNotice:
    def test_a_missing_webhook_is_annotated_and_does_not_post(self, tmp_path):
        result, recorded = _run_slack(tmp_path, webhook="")
        assert result.returncode == 0
        assert recorded == ""
        assert "SLACK_WEBHOOK_URL secret not set" in result.stdout
        assert "16 open PR(s), 2 on cursor/" in result.stdout
        assert "hooks.slack.com" not in result.stdout

    def test_the_payload_carries_counts_and_not_the_webhook(self, tmp_path):
        webhook = "https://hooks.example.test/services/SECRET-TOKEN"
        result, recorded = _run_slack(tmp_path, webhook=webhook, level="ALARM", total="31", cursor="4")
        assert result.returncode == 0
        args = [part for part in recorded.split("\0") if part]
        payload = json.loads(args[args.index("-d") + 1])
        assert set(payload) == {"text"}
        assert "ALARM" in payload["text"]
        assert "31 open PR(s)" in payload["text"]
        assert "4 on cursor/" in payload["text"]
        assert "actions/runs/99" in payload["text"]
        assert "SECRET-TOKEN" not in payload["text"]
        assert webhook not in payload["text"]
        assert args[-1] == webhook

    def test_a_failed_post_fails_the_script_and_the_step_continues(self, tmp_path):
        result, _ = _run_slack(tmp_path, webhook="https://hooks.example.test/services/SECRET", curl_rc=22)
        assert result.returncode != 0
        step = _step("Slack notification")
        assert step["continue-on-error"] is True
        assert step["if"] == "steps.count.outputs.level != 'OK'"


class TestWorkflowContract:
    def test_it_is_schedule_and_dispatch_only_with_read_permissions(self):
        workflow = _workflow()
        assert "pull_request" not in workflow["on"]
        assert workflow["on"]["schedule"] == [{"cron": "0 14 * * *"}]
        assert "workflow_dispatch" in workflow["on"]
        assert workflow["permissions"] == {"contents": "read", "pull-requests": "read"}
        assert workflow["concurrency"]["group"] == "pr-budget-alarm"
        assert workflow["concurrency"]["cancel-in-progress"] is True

    def test_the_token_is_the_built_in_github_token(self):
        env = _step("Count open PRs")["env"]
        assert env["GH_TOKEN"] == "${{ github.token }}"
        assert env["GH_REPO"] == "${{ github.repository }}"
