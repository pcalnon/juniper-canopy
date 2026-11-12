"""The lockfile regen refuses an empty payload before it can sign a commit.

``#775`` moved ``base64 -w0`` out of a ``jq --arg`` substitution. A failure inside
``$(...)`` used as an argument does not trip ``set -e``, so a failing encode would
have handed ``jq`` an empty string and ``createCommitOnBranch`` would have signed a
commit that empties ``requirements.lock``. The encode is now its own assignment,
and an empty result exits 1 before ``jq`` or ``gh``.

The shell under test is the workflow's own ``run:`` block, not a copy. ``gh`` is a
stub. The two commit-body paths the step writes are relocated under ``tmp_path``
in every case; the workflow text itself is not modified. Off
Linux, a runner whose ``base64`` cannot run the step's ``base64 -w0 FILE`` gets a
stand-in for exactly that form (see ``_BASE64_W0_STAND_IN``).

``gh api graphql`` exits 1 on a response that carries GraphQL ``errors`` and on an
HTTP failure, after writing the body to stdout and ``gh: <message>`` to stderr
(cli/cli ``pkg/cmd/api/api.go``, ``processResponse``). The stub fails the same way.
Called bare under ``set -e``, that exit ended the step before its own diagnostic;
the step now captures gh's status and stderr, prints the diagnostic, and fails, with
the token's value masked in anything gh printed.
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess  # nosec B404 - the workflow's own shell, with stub gh and base64 on PATH
import sys
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.regression, pytest.mark.unit]

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "lockfile-update.yml"
STEP_NAME = "Commit updated lockfile (GitHub-signed, via API)"
TOKEN = "lockfile-regen-token-not-real"
REPO_NAME = "pcalnon/juniper-canopy"
BRANCH = "dependabot/pip/example"
PR_HEADLINE = "chore(deps): auto-regenerate requirements.lock after pyproject change"
PUSH_HEADLINE = "[dependabot skip] Update requirements.lock"
LOCK_BYTES = b"# lock\npackage==1.2.3\n"
SIGNED = {
    "data": {
        "createCommitOnBranch": {
            "commit": {"oid": "abc123", "url": "https://example.test/commit/abc123"},
        }
    }
}

_GH = """\
#!/bin/bash
{
  printf '%s' gh
  for arg in "$@"; do printf '\\t%s' "$arg"; done
  printf '\\n'
} >> "$GH_LOG"
printf '%s' "${GH_STDOUT-}"
if [[ "${GH_RC:-0}" -ne 0 ]]; then
  printf '%s\\n' "${GH_ERR:-gh failed}" >&2
  exit "${GH_RC}"
fi
"""

STALE = 'Expected branch to point to "abc" but it did not. Pull and try again.'

_JQ_POISON = """\
#!/bin/bash
printf 'jq\\n' >> "$JQ_LOG"
exit 97
"""

_B64_FAIL_WITH_BYTES = """\
#!/bin/bash
printf 'called\\n' >> "$B64_LOG"
printf 'encoded-but-failed'
exit 1
"""

_B64_EMPTY = """\
#!/bin/bash
printf 'called\\n' >> "$B64_LOG"
exit 0
"""

_B64_FORBIDDEN = """\
#!/bin/bash
printf 'called\\n' >> "$B64_LOG"
exit 99
"""

# The step runs on ubuntu-latest and encodes with the coreutils form ``base64 -w0 FILE``,
# which GNU and uutils coreutils both accept. BSD/macOS base64
# refuses the FILE operand ("base64: invalid argument requirements.lock"), so on CI's required
# macOS unit-test leg every case that reaches the real encoder stopped at the encode: the
# guard working, not the path the case is about. Where this runner's base64 fails a probe of
# the step's exact form, those cases get this stand-in instead. It emulates that one form
# only; any other argv exits non-zero, so a changed invocation is not silently emulated.
# Linux always runs the real base64: there a failing probe is a real problem, so the case
# runs and says so. Nothing is skipped: the macOS leg still runs every case.
_BASE64_W0_STAND_IN = """\
#!/usr/bin/env python3
import base64
import sys

if len(sys.argv) != 3 or sys.argv[1] != "-w0":
    sys.exit("base64 stand-in emulates only `base64 -w0 FILE`, got " + repr(sys.argv[1:]))
with open(sys.argv[2], "rb") as fh:
    sys.stdout.write(base64.b64encode(fh.read()).decode("ascii"))
"""


def _on_linux() -> bool:
    return sys.platform.startswith("linux")


def _base64_runs_the_steps_form(scratch: Path) -> bool:
    """Whether this runner's base64 runs the step's exact form on a one-byte file.

    Judged by the output, not only the exit status: ``-w0`` on stdin passes on macOS
    while the step's FILE operand is refused, so a probe of any other form measures
    the wrong thing.
    """
    probe = scratch / "base64-probe"
    probe.mkdir()
    (probe / "requirements.lock").write_bytes(b"x")
    try:
        proc = subprocess.run(  # nosec B603 B607 - capability probe, fixed argv
            ["base64", "-w0", "requirements.lock"],
            cwd=probe,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout == "eA=="


def _workflow() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) reads the bare `on:` key as boolean True.
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


def _step() -> dict:
    steps = _workflow()["jobs"]["update-lockfile"]["steps"]
    found = [step for step in steps if step.get("name") == STEP_NAME]
    assert len(found) == 1, STEP_NAME
    assert "run" in found[0]
    return found[0]


def _script() -> str:
    return _step()["run"]


def _uncommented(script: str) -> str:
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


def _ci_paths(script: str) -> tuple[str, str]:
    """The two absolute paths the commit step writes. Read from the step, not hardcoded."""
    found = re.findall(r"(/\S*lockfile-commit(?:-result)?\.json)", script)
    body = [path for path in found if path.endswith("/lockfile-commit.json")]
    result = [path for path in found if path.endswith("/lockfile-commit-result.json")]
    assert body and result, found
    assert len(set(body)) == 1 and len(set(result)) == 1
    return body[0], result[0]


def _write_exe(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _git(repo: Path, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(repo),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    return subprocess.run(  # nosec B603 B607 - git against the temp repo only
        ["git", *args],
        cwd=repo,
        env=env,
        check=not capture,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path, text: str) -> str:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "core.autocrlf", "false")
    (repo / "requirements.lock").write_bytes(text.encode("utf-8"))
    _git(repo, "add", "requirements.lock")
    _git(repo, "commit", "-q", "-m", "base")
    return _git(repo, "rev-parse", "HEAD", capture=True).stdout.strip()


class _Result:
    def __init__(self, code: int, out: str, err: str, gh_log: Path, jq_log: Path, b64_log: Path, body: Path, result: Path, head: str) -> None:
        self.code = code
        self.out = out
        self.err = err
        self.gh = gh_log.read_text(encoding="utf-8") if gh_log.is_file() else ""
        self.jq = jq_log.read_text(encoding="utf-8") if jq_log.is_file() else ""
        self.b64 = b64_log.read_text(encoding="utf-8") if b64_log.is_file() else ""
        self.body = body
        self.result = result
        self.head = head

    @property
    def combined(self) -> str:
        return self.out + self.err


def _run(
    tmp: Path,
    *,
    committed: str = LOCK_BYTES.decode("utf-8"),
    dirty: str | None = None,
    delete_lock: bool = False,
    event: str = "pull_request",
    base64_stub: str | None = None,
    poison_jq: bool = False,
    gh_stdout: str = "",
    gh_rc: int = 0,
    gh_err: str = "gh failed",
    script: str | None = None,
) -> _Result:
    source = script if script is not None else _script()
    body_path, result_path = _ci_paths(source)
    local_body = tmp / "lockfile-commit.json"
    local_result = tmp / "lockfile-commit-result.json"
    # Relocated in EVERY run, not only the ones expected to reach jq: a regressed guard
    # opens the body's redirect before a poisoned jq exits, so an unrelocated run writes on
    # the host, and `not result.body.exists()` would check a path the step never writes.
    # The workflow's paths stay in the file CI runs; the test copy writes beside the repo.
    executed = source.replace(body_path, str(local_body)).replace(result_path, str(local_result))
    assert body_path not in executed and result_path not in executed
    repo = tmp / "repo"
    head = _init_repo(repo, committed)
    if dirty is not None:
        (repo / "requirements.lock").write_text(dirty, encoding="utf-8")
    if delete_lock:
        (repo / "requirements.lock").unlink()
    bin_dir = tmp / "bin"
    bin_dir.mkdir()
    _write_exe(bin_dir / "gh", _GH)
    if poison_jq:
        _write_exe(bin_dir / "jq", _JQ_POISON)
    if base64_stub is not None:
        _write_exe(bin_dir / "base64", base64_stub)
    elif not _on_linux() and not _base64_runs_the_steps_form(tmp):
        _write_exe(bin_dir / "base64", _BASE64_W0_STAND_IN)
    gh_log = tmp / "gh.log"
    jq_log = tmp / "jq.log"
    b64_log = tmp / "b64.log"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '/usr/bin:/bin')}",
        "HOME": str(tmp),
        "LANG": "C",
        "GH_TOKEN": TOKEN,
        "GH_LOG": str(gh_log),
        "JQ_LOG": str(jq_log),
        "B64_LOG": str(b64_log),
        "GH_STDOUT": gh_stdout,
        "GH_RC": str(gh_rc),
        "GH_ERR": gh_err,
        "EVENT_NAME": event,
        "GITHUB_REPOSITORY": REPO_NAME,
        "BRANCH": BRANCH,
    }
    proc = subprocess.run(  # nosec B603 B607 - bash runs the extracted workflow step
        ["bash", "-c", executed],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    assert TOKEN not in combined, "the commit step printed the token"
    return _Result(proc.returncode, proc.stdout, proc.stderr, gh_log, jq_log, b64_log, local_body, local_result, head)


def _mutation(result: _Result) -> dict:
    assert result.body.is_file(), result.combined
    payload = json.loads(result.body.read_text(encoding="utf-8"))
    return payload["variables"]["input"]


def test_the_encode_is_its_own_statement_ahead_of_jq() -> None:
    """The defect was ``--arg contents "$(base64 ...)"``. A comment naming it must not count."""
    step = _step()
    assert step["if"] == "steps.gate.outputs.proceed == 'true'"
    code = _uncommented(step["run"])
    for line in code.splitlines():
        assert not ("base64" in line and ("jq" in line or "--arg" in line)), line
    assign = "LOCK_B64=$(base64 -w0 requirements.lock)"
    guard = '[ -z "${LOCK_B64}" ]'
    assert assign in code
    assert guard in code
    assert code.index("set -euo pipefail") < code.index(assign) < code.index(guard) < code.index("jq -n")
    assert "exit 1" in code[code.index(guard) : code.index("jq -n")]
    body, result = _ci_paths(step["run"])
    assert Path(body).is_absolute() and Path(result).is_absolute()
    assert not Path(body).is_relative_to(REPO)
    assert not Path(result).is_relative_to(REPO)


def test_an_empty_lockfile_is_not_committed(tmp_path: Path) -> None:
    """Coreutils ``base64 -w0`` of an empty file is empty and exits 0. The guard has to refuse that."""
    result = _run(tmp_path, dirty="", poison_jq=True)
    assert result.code == 1, result.combined
    assert "base64 produced an empty payload" in result.combined
    assert "lockfile NOT committed" in result.combined
    assert result.jq == ""
    assert result.gh == ""
    assert not result.body.exists()


def test_an_empty_encode_of_a_nonempty_file_is_not_committed(tmp_path: Path) -> None:
    """The guard reads the payload. A non-empty lockfile whose encode is empty is still refused."""
    result = _run(tmp_path, dirty="still-has-bytes\n", base64_stub=_B64_EMPTY, poison_jq=True)
    assert result.code == 1, result.combined
    assert "base64 produced an empty payload" in result.combined
    assert result.b64 == "called\n"
    assert result.jq == ""
    assert result.gh == ""


def test_a_failing_encode_that_printed_bytes_does_not_reach_jq(tmp_path: Path) -> None:
    """``set -e`` has to fire on the assignment. The emptiness check would let these bytes through."""
    result = _run(tmp_path, dirty="changed\n", base64_stub=_B64_FAIL_WITH_BYTES, poison_jq=True)
    assert result.code != 0, result.combined
    assert "empty payload" not in result.combined
    assert result.b64 == "called\n"
    assert result.jq == ""
    assert result.gh == ""


def test_a_missing_lockfile_does_not_reach_jq(tmp_path: Path) -> None:
    result = _run(tmp_path, delete_lock=True, poison_jq=True)
    assert result.code != 0, result.combined
    assert result.jq == ""
    assert result.gh == ""


def test_an_unchanged_lockfile_commits_nothing(tmp_path: Path) -> None:
    result = _run(tmp_path, base64_stub=_B64_FORBIDDEN, poison_jq=True)
    assert result.code == 0, result.combined
    assert "Lockfile already up to date" in result.combined
    assert result.b64 == ""
    assert result.jq == ""
    assert result.gh == ""


@pytest.mark.parametrize(
    ("event", "headline"),
    [("pull_request", PR_HEADLINE), ("push", PUSH_HEADLINE)],
)
def test_a_changed_lockfile_is_committed_as_its_own_bytes(tmp_path: Path, event: str, headline: str) -> None:
    dirty = b"pyproject-bumped\npackage==9.9.9\n"
    result = _run(
        tmp_path,
        dirty=dirty.decode("utf-8"),
        event=event,
        gh_stdout=json.dumps(SIGNED),
    )
    assert result.code == 0, result.combined
    assert result.out == "Signed lockfile commit: https://example.test/commit/abc123\n"
    assert result.err == ""
    mutation = _mutation(result)
    addition = mutation["fileChanges"]["additions"]
    assert len(addition) == 1
    assert addition[0]["path"] == "requirements.lock"
    assert base64.b64decode(addition[0]["contents"]) == dirty
    assert mutation["expectedHeadOid"] == result.head
    assert mutation["branch"] == {"repositoryNameWithOwner": REPO_NAME, "branchName": BRANCH}
    assert mutation["message"]["headline"] == headline
    assert result.gh.startswith("gh\t")
    assert "--input" in result.gh
    assert str(result.body) in result.gh


def test_graphql_errors_fail_the_step(tmp_path: Path) -> None:
    """An ``errors`` body from a ``gh`` that exits 0.

    The real CLI exits 0 on one only when it finds no message to print, for example
    a single error without a ``message`` (api.go ``parseErrorResponse`` joins the
    messages, and an empty join is no error). The exit-1 shape is
    ``test_a_graphql_error_that_fails_gh_prints_the_steps_diagnostic``.
    """
    result = _run(
        tmp_path,
        dirty="changed\n",
        gh_stdout=json.dumps({"errors": [{"message": "expectedHeadOid mismatch"}]}),
    )
    assert result.code == 1, result.combined
    assert "createCommitOnBranch failed" in result.combined
    assert "expectedHeadOid mismatch" in result.combined
    assert "Signed lockfile commit" not in result.combined
    assert result.gh.startswith("gh\t")


def test_a_failing_gh_does_not_report_a_signed_commit(tmp_path: Path) -> None:
    result = _run(tmp_path, dirty="changed\n", gh_rc=1)
    assert result.code != 0, result.combined
    assert "Signed lockfile commit" not in result.combined
    assert result.gh.startswith("gh\t")


def test_a_graphql_error_that_fails_gh_prints_the_steps_diagnostic(tmp_path: Path) -> None:
    """The real CLI's shape: the ``errors`` body on stdout, ``gh: <message>`` on stderr, exit 1.

    A bare ``gh api graphql`` under ``set -e`` ended the step at that exit, so the
    step's own ``createCommitOnBranch failed`` diagnostic never printed.
    """
    body = {"data": {"createCommitOnBranch": None}, "errors": [{"type": "STALE_DATA", "message": STALE}]}
    result = _run(tmp_path, dirty="changed\n", gh_stdout=json.dumps(body), gh_rc=1, gh_err=f"gh: {STALE}")
    assert result.code == 1, result.combined
    assert f"gh: {STALE}" in result.err
    assert "createCommitOnBranch failed" in result.out
    assert "lockfile NOT committed" in result.out
    assert "STALE_DATA" in result.out
    assert "gh exited 1" in result.out
    assert "re-run this job" in result.out
    assert "gh api graphql failed" not in result.combined
    assert "Signed lockfile commit" not in result.combined
    assert result.gh.startswith("gh\t")


@pytest.mark.parametrize(
    ("gh_stdout", "gh_err", "printed", "names_the_token"),
    [
        ("<html>502 Bad Gateway</html>\n", "gh: HTTP 502", "empty or not JSON", False),
        (json.dumps({"message": "Bad credentials", "status": "401"}), "gh: Bad credentials (HTTP 401)", '"Bad credentials"', True),
        ("", "error connecting to api.github.com", "empty or not JSON", False),
    ],
    ids=["http-502-html", "http-401-json", "no-response"],
)
def test_an_http_failure_prints_that_the_commit_is_unknown(tmp_path: Path, gh_stdout: str, gh_err: str, printed: str, names_the_token: bool) -> None:
    """No GraphQL ``errors``: the request failed at the HTTP level or before any response.

    The log alone cannot show whether a commit landed (an HTTP error is not proof that
    the mutation did not run), so the step does not say nothing was committed.
    """
    result = _run(tmp_path, dirty="changed\n", gh_stdout=gh_stdout, gh_rc=1, gh_err=gh_err)
    assert result.code == 1, result.combined
    assert gh_err in result.err
    assert "gh api graphql failed (exit 1)" in result.out
    assert "cannot show whether the lock commit landed" in result.out
    assert printed in result.out
    assert f"Check {BRANCH} for the lock commit" in result.out
    assert ("CROSS_REPO_DISPATCH_TOKEN is invalid or expired" in result.out) is names_the_token
    assert "createCommitOnBranch failed" not in result.combined
    assert "Signed lockfile commit" not in result.combined


def test_gh_output_is_printed_with_the_token_masked(tmp_path: Path) -> None:
    """What gh printed reaches the log through the step's mask; ``_run`` refuses any ``TOKEN``."""
    body = {"errors": [{"type": "FORBIDDEN", "message": f"token {TOKEN} lacks access ({TOKEN})"}]}
    result = _run(tmp_path, dirty="changed\n", gh_stdout=json.dumps(body), gh_rc=1, gh_err=f"gh: token {TOKEN} lacks access ({TOKEN})")
    assert result.code == 1, result.combined
    assert "gh: token *** lacks access (***)" in result.err
    assert "token *** lacks access (***)" in result.out
    assert "createCommitOnBranch failed" in result.out


def test_an_http_failure_body_is_printed_with_the_token_masked(tmp_path: Path) -> None:
    """The HTTP-failure branch prints a JSON body through the same mask as gh's message."""
    body = {"message": f"bad token {TOKEN}", "status": "403"}
    result = _run(tmp_path, dirty="changed\n", gh_stdout=json.dumps(body), gh_rc=1, gh_err=f"gh: bad token {TOKEN} (HTTP 403)")
    assert result.code == 1, result.combined
    assert "gh: bad token *** (HTTP 403)" in result.err
    assert "gh api graphql failed (exit 1)" in result.out
    assert '"bad token ***"' in result.out


@pytest.mark.parametrize(
    ("gh_rc", "gh_stdout", "printed"),
    [
        (4, "", "gh api graphql failed (exit 4)"),
        (0, json.dumps({"errors": [{"type": "X"}]}), "gh exited 0"),
    ],
    ids=["exit-4-no-token", "exit-0-errors-without-a-message"],
)
def test_the_diagnostic_names_the_exit_status_gh_gave(tmp_path: Path, gh_rc: int, gh_stdout: str, printed: str) -> None:
    """Both diagnostics report gh's own exit status, and the step exits 1 whatever that was.

    gh exits 4 when it has no usable token (cli/cli ``internal/ghcmd/cmd.go``, ``exitAuth``),
    and 0 on an ``errors`` body that carries no message.
    """
    result = _run(tmp_path, dirty="changed\n", gh_stdout=gh_stdout, gh_rc=gh_rc, gh_err="gh: set the GH_TOKEN environment variable")
    assert result.code == 1, result.combined
    assert printed in result.out
    assert "Signed lockfile commit" not in result.combined
