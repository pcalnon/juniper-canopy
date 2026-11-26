"""Pin the publish docs' numbers to the publish workflow: the bounds the docs state are the bounds the steps run.

``docs/ci_cd/CICD_REFERENCE.md`` and ``docs/ci_cd/CICD_MANUAL.md`` give an operator the numbers that decide whether a
failed check was lag: how often and how far apart the JSON checks poll, and how long the install check waits and how
many times it tries. Each is read here from ``publish.yml`` and required in the docs, so a change to either side alone
fails. A module of its own, as juniper-cascor's is (juniper-cascor#777): ``test_publish_one_artifact.py`` reads the
workflow alone, and its negative control (``util/ad-hoc/2026-11-15_verify_publish_one_artifact_tests_are_not_vacuous.py``)
copies the workflow, that test file and ``pyproject.toml``, and no doc.

Project: juniper-canopy
Author: Paul Calnon
Created: 2026-11-26
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# CI's unit lane selects with a NEGATIVE expression over src/tests/unit/, so it would run an unmarked module too; the
# documented fast run, `pytest -m "unit and not slow"` (AGENTS.md), would collect it and silently DESELECT it.
# Module-level, so it covers tests added later.
pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "publish.yml"
DOCS = REPO / "docs" / "ci_cd"
#: The JSON check every copy of the template runs; its first copy, in the TestPyPI job, is read here.
INDEX_CHECK = "Verify TestPyPI serves exactly these files"
INSTALL = "verify-testpypi-install"
INSTALL_CHECK = "Verify TestPyPI install"


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _run(job: dict, name: str) -> str:
    found = [s for s in job.get("steps") or [] if s.get("name") == name]
    assert len(found) == 1, f"expected exactly one step named {name!r}"
    return str(found[0]["run"])


def _doc(name: str) -> str:
    """The doc's text with each run of whitespace made one space: a rewrapped paragraph states the same bounds."""
    return " ".join((DOCS / name).read_text(encoding="utf-8").split())


def _retry() -> tuple[int, list[int], list[int]]:
    """The install check's (tries, the waits inside its loop, the waits before it), read from its commands."""
    run = _run(_jobs()[INSTALL], INSTALL_CHECK)
    commands = [line.strip() for line in run.splitlines() if line.strip() and not line.strip().startswith("#")]
    loops = [i for i, c in enumerate(commands) if re.fullmatch(r"for attempt in [0-9 ]+; do", c)]
    assert len(loops) == 1, "expected one retry loop"
    start, end = loops[0], commands.index("done", loops[0])
    tries = len(commands[start].split()[3:-1])
    waits = [int(c.split()[1]) for c in commands[start:end] if re.fullmatch(r"sleep [0-9]+", c)]
    before = [int(c.split()[1]) for c in commands[:start] if re.fullmatch(r"sleep [0-9]+", c)]
    return tries, waits, before


class TestPublishDocsStateTheBounds:
    def test_the_json_checks_bounds(self):
        run = _run(_jobs()["testpypi"], INDEX_CHECK)
        attempts = int(re.search(r'"HASH_CHECK_ATTEMPTS", "(\d+)"', run).group(1))
        interval = int(re.search(r'"HASH_CHECK_INTERVAL", "(\d+)"', run).group(1))
        assert f"A JSON check polls up to {attempts} times, {interval} s apart" in _doc("CICD_REFERENCE.md")

    def test_the_install_checks_wait_and_retry(self):
        tries, waits, before = _retry()
        # One wait before the first try, and one between tries (none after the last, which the loop's own error ends).
        assert len(waits) == 1
        assert len(before) == 1
        stated = f"It waits {before[0]} s, then makes {tries} tries, {waits[0]} s apart"
        for name in ("CICD_REFERENCE.md", "CICD_MANUAL.md"):
            assert stated in _doc(name), name
        # The error the check stops with after its last try, as the step prints it and as the docs quote it.
        error = f"is not installable from TestPyPI after {tries} tries (index lag?)"
        assert error in _run(_jobs()[INSTALL], INSTALL_CHECK)
        for name in ("CICD_REFERENCE.md", "CICD_MANUAL.md"):
            assert error in _doc(name), name
