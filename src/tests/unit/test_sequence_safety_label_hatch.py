"""The sequence-safety label hatch demotes a required screen only for an exact label.

Sequence Safety is a required ruleset check. ``sequence-safety.yml`` reads the PR's
live labels and passes ``--advisory`` to one screen when the label is exactly
``allow-symbol-loss`` or ``docs-rewrite``. A prefix, a case change, surrounding
whitespace, or a failed ``gh`` must not demote it, and an invocation error
(exit >= 2) must not become a finding or a pass.

The shell under test is the workflow's own ``run:`` block, not a copy. ``gh``,
``git`` (when the object is missing), and the two screen binaries are stubs, so
nothing here talks to GitHub.
"""

from __future__ import annotations

import os
import subprocess  # nosec B404 - the workflow's own shell, with stub gh and screens on PATH
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "sequence-safety.yml"
STEP_NAME = "Run sequence-safety screens (symbol + docs)"
SYMBOL_SCOPE = "src/**/*.py"
TOKEN = "sequence-hatch-token-not-real"

_SCREEN = """\
#!/bin/bash
name=$(basename "$0")
{
  printf '%s' "$name"
  for arg in "$@"; do printf '\\t%s' "$arg"; done
  printf '\\n'
} >> "$SCREEN_LOG"
json=0
advisory=0
for arg in "$@"; do
  [[ "$arg" == "--json" ]] && json=1
  [[ "$arg" == "--advisory" ]] && advisory=1
done
if [[ "$json" == 1 ]]; then
  printf '%s\\n' '{}'
  exit 0
fi
if [[ "$name" == juniper-symbol-loss-check && -n "${HARD_SYMBOL:-}" ]]; then exit "$HARD_SYMBOL"; fi
if [[ "$name" == juniper-docs-additions-check && -n "${HARD_DOCS:-}" ]]; then exit "$HARD_DOCS"; fi
if [[ "$advisory" == 1 ]]; then exit 0; fi
if [[ "$name" == juniper-symbol-loss-check ]]; then exit "${SCREEN_SYMBOL_CODE:-0}"; fi
exit "${SCREEN_DOCS_CODE:-0}"
"""

_GH = """\
#!/bin/bash
{
  printf '%s' gh
  for arg in "$@"; do printf '\\t%s' "$arg"; done
  printf '\\n'
} >> "$GH_LOG"
if [[ "${GH_FAIL:-0}" == 1 ]]; then
  [[ -n "${GH_STDERR:-}" ]] && printf '%s\\n' "$GH_STDERR" >&2
  exit 1
fi
printf '%s' "${GH_LABELS-}"
"""

_GIT = """\
#!/bin/bash
{
  printf '%s' git
  for arg in "$@"; do printf '\\t%s' "$arg"; done
  printf '\\n'
} >> "$GIT_LOG"
[[ "$1" == cat-file || "$1" == fetch ]] && exit 1
exit 99
"""


def _workflow() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) reads the bare `on:` key as boolean True.
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


def _screen_script() -> str:
    steps = _workflow()["jobs"]["sequence-safety"]["steps"]
    step = next((s for s in steps if s.get("name") == STEP_NAME), None)
    if step is None or "run" not in step:
        raise AssertionError(f"{STEP_NAME!r} is missing from sequence-safety.yml — the hatch this test runs is gone")
    return step["run"]


def _write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _commit(repo: Path) -> str:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(repo),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True, env=env)  # nosec B603 B607
    (repo / "README").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=repo, check=True, env=env)  # nosec B603 B607
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True, env=env)  # nosec B603 B607
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, env=env, capture_output=True, text=True)  # nosec B603 B607
    return sha.stdout.strip()


def _calls(log: Path, name: str, *, json_report: bool) -> list[list[str]]:
    if not log.is_file() or not log.read_text(encoding="utf-8"):
        return []
    found = []
    for line in log.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if parts[0] != name:
            continue
        is_json = "--json" in parts
        if is_json == json_report:
            found.append(parts)
    return found


class _Result:
    def __init__(self, code: int, out: str, err: str, screen_log: Path, gh_log: Path, git_log: Path) -> None:
        self.code = code
        self.out = out
        self.err = err
        self.symbol = _calls(screen_log, "juniper-symbol-loss-check", json_report=False)
        self.docs = _calls(screen_log, "juniper-docs-additions-check", json_report=False)
        # ``gh pr view --json`` always carries ``--json``. That flag is the query, not a report mode.
        self.gh = [line.split("\t") for line in gh_log.read_text(encoding="utf-8").splitlines()] if gh_log.is_file() else []
        self.git = git_log.read_text(encoding="utf-8") if git_log.is_file() else ""


def _run(
    tmp: Path,
    *,
    labels: str = "",
    pr_number: str | None = "712",
    base_sha: str | None = None,
    symbol_code: int = 0,
    docs_code: int = 0,
    hard_symbol: str = "",
    gh_fail: bool = False,
    gh_stderr: str = "",
    stub_git: bool = False,
) -> _Result:
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    screen = bin_dir / "screen"
    _write_exe(screen, _SCREEN)
    (bin_dir / "juniper-symbol-loss-check").symlink_to(screen)
    (bin_dir / "juniper-docs-additions-check").symlink_to(screen)
    _write_exe(bin_dir / "gh", _GH)
    if stub_git:
        _write_exe(bin_dir / "git", _GIT)
    screen_log = tmp / "screens.log"
    gh_log = tmp / "gh.log"
    git_log = tmp / "git.log"
    work = tmp / "repo"
    work.mkdir()
    if base_sha is None and not stub_git:
        base_sha = _commit(work)
    elif base_sha is None:
        base_sha = "0123456789abcdef0123456789abcdef01234567"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(tmp),
        "LANG": "C",
        "GH_TOKEN": TOKEN,
        "SCREEN_LOG": str(screen_log),
        "GH_LOG": str(gh_log),
        "GIT_LOG": str(git_log),
        "GH_LABELS": labels,
        "GH_FAIL": "1" if gh_fail else "0",
        "GH_STDERR": gh_stderr,
        "SCREEN_SYMBOL_CODE": str(symbol_code),
        "SCREEN_DOCS_CODE": str(docs_code),
        "HARD_SYMBOL": hard_symbol,
        "PR_BASE_SHA": base_sha,
        "SYMBOL_SCOPE": SYMBOL_SCOPE,
    }
    if pr_number is not None:
        env["PR_NUMBER"] = pr_number
    proc = subprocess.run(  # nosec B603 B607 - bash runs the extracted workflow step
        ["bash", "-c", _screen_script()],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    assert TOKEN not in combined, "the hatch printed the token"
    return _Result(proc.returncode, proc.stdout, proc.stderr, screen_log, gh_log, git_log)


def test_the_workflow_scopes_symbols_to_src_and_leaves_docs_universal(tmp_path: Path) -> None:
    """Canopy's damage locus is ``src/**/*.py``. The docs screen keeps the packaged default."""
    assert _workflow()["env"]["SYMBOL_SCOPE"] == SYMBOL_SCOPE
    result = _run(tmp_path)
    assert result.code == 0, result.out
    assert len(result.symbol) == 1 and len(result.docs) == 1
    assert result.symbol[0][result.symbol[0].index("--scope") + 1] == SYMBOL_SCOPE
    assert "--scope" not in result.docs[0]
    assert "--advisory" not in result.symbol[0]
    assert "--advisory" not in result.docs[0]
    assert "--head" in result.symbol[0] and "HEAD" in result.symbol[0]


def test_exact_symbol_label_advises_only_that_screen(tmp_path: Path) -> None:
    """A finding the symbol screen would fail becomes a pass, and the docs screen stays required."""
    result = _run(tmp_path, labels="bug\nallow-symbol-loss\nchore", symbol_code=1, docs_code=0)
    assert result.code == 0, result.out
    assert "--advisory" in result.symbol[0]
    assert "--advisory" not in result.docs[0]


def test_exact_docs_label_advises_only_that_screen(tmp_path: Path) -> None:
    result = _run(tmp_path, labels="docs-rewrite", symbol_code=0, docs_code=1)
    assert result.code == 0, result.out
    assert "--advisory" in result.docs[0]
    assert "--advisory" not in result.symbol[0]


def test_a_finding_without_a_label_is_exit_1(tmp_path: Path) -> None:
    result = _run(tmp_path, symbol_code=1)
    assert result.code == 1
    assert "--advisory" not in result.symbol[0]
    assert len(result.docs) == 1, "a symbol finding must not skip the docs screen"


@pytest.mark.parametrize(
    "labels",
    ["allow-symbol-loss-extra", "Allow-Symbol-Loss", "allow-symbol-loss ", " allow-symbol-loss", "allow-symbol-loss-extra\ndocs-rewrite-please"],
    ids=["prefix", "case", "trailing-space", "leading-space", "near-miss-lines"],
)
def test_an_inexact_label_does_not_advise(tmp_path: Path, labels: str) -> None:
    result = _run(tmp_path, labels=labels, symbol_code=1)
    assert result.code == 1, result.out
    assert "--advisory" not in result.symbol[0]
    assert "--advisory" not in result.docs[0]


def test_a_docs_label_does_not_hide_a_symbol_finding(tmp_path: Path) -> None:
    result = _run(tmp_path, labels="docs-rewrite", symbol_code=1, docs_code=1)
    assert result.code == 1, result.out
    assert "--advisory" not in result.symbol[0]
    assert "--advisory" in result.docs[0]


def test_failed_gh_does_not_advise_from_stderr(tmp_path: Path) -> None:
    """A failing ``gh`` prints the waiver on stderr. Stderr is not a label."""
    result = _run(tmp_path, gh_fail=True, gh_stderr="allow-symbol-loss\ndocs-rewrite", symbol_code=1)
    assert result.code == 1, result.out
    assert result.gh, "gh should have been asked"
    assert "--advisory" not in result.symbol[0]


def test_an_empty_pr_number_does_not_call_gh(tmp_path: Path) -> None:
    result = _run(tmp_path, pr_number="", symbol_code=1)
    assert result.code == 1, result.out
    assert result.gh == []
    assert "--advisory" not in result.symbol[0]


def test_a_pr_number_with_a_space_stays_one_argument(tmp_path: Path) -> None:
    result = _run(tmp_path, pr_number="71 2", labels="allow-symbol-loss", symbol_code=1)
    assert result.code == 0, result.out
    assert "71 2" in result.gh[0]


def test_an_invocation_error_stays_exit_2_with_the_label(tmp_path: Path) -> None:
    """``--advisory`` downgrades a finding. It does not downgrade a screen that could not run."""
    result = _run(tmp_path, labels="allow-symbol-loss\ndocs-rewrite", hard_symbol="2")
    assert result.code == 2, result.out
    assert "--advisory" in result.symbol[0]


def test_a_missing_base_sha_exits_2_and_starts_no_screen(tmp_path: Path) -> None:
    result = _run(tmp_path, base_sha="", labels="allow-symbol-loss")
    assert result.code == 2
    assert "could not resolve a base sha" in result.out
    assert result.symbol == [] and result.docs == [] and result.gh == []


def test_a_missing_object_still_runs_both_screens(tmp_path: Path) -> None:
    """A failed fetch is not a reason to skip the required screens."""
    result = _run(tmp_path, stub_git=True)
    assert result.code == 0, result.out
    assert "fetch" in result.git
    assert len(result.symbol) == 1 and len(result.docs) == 1


def test_an_unset_pr_number_fails_closed(tmp_path: Path) -> None:
    result = _run(tmp_path, pr_number=None)
    assert result.code != 0
    assert result.symbol == [] and result.docs == []
