"""
Pin CI lane wiring: which lanes install what, and which test directories any lane actually names.

Three guards, one theme -- a suite can be green, or look green, while not running.

Regression guard for the class that kept ``Scheduled Tests`` red for 63 consecutive runs
(2026-07-21 .. 2026-09-21). Its last green run was 2026-07-20; ``#459`` added the offending import
at 17:57 that evening. Retention reaches back to 2026-05-01 and holds 58 successes, so this is a
regression with a date, not a lane that never worked. Two lanes install the repo differently:

* ``.github/workflows/ci.yml``              -- ``pip install -e ".[juniper-cascor]"``  (real client)
* ``.github/workflows/scheduled-tests.yml`` -- ``pip install -e .``                    (stub)

Both lanes now install several extras at once
(``.[test,juniper-cascor,observability]``, canopy#650), so the check below is membership in the
bracketed list rather than a match against the whole bracket.

With no real client, ``src/tests/conftest.py`` injects a stub registering only
``juniper_cascor_client``, ``.exceptions`` and ``.client``. But
``src/backend/cascor_service_adapter.py`` imports ``ENDPOINT_TRAINING_START`` from
``juniper_cascor_client.constants`` (added 2026-07-20, #459), which the stub does not provide, so
four test modules that import ``CascorServiceAdapter`` at module scope died at COLLECTION -- and a
collection error exits the job 1 no matter how many tests pass.

The failure was invisible on PRs precisely because the required lane installs the extra.

Repairing that lane, on its own, would have destroyed evidence: ``src/tests/contract/`` was named
by NO workflow path list, and its tests are ``@pytest.mark.unit`` so the scheduled lane's
``-m "slow or integration"`` deselected them. A collection error was the only thing in CI that
mentioned the directory at all. ``src/tests/performance/`` was in the same state -- 5 tests, 1
explicitly skipped, 4 live and running nowhere. Both are now named by the unit lane.

The three guards:

* ``TestTheStubCoversEverySubmoduleSrcImports`` -- a new ``juniper_cascor_client`` submodule
  imported by ``src/`` that the stub does not register.
* ``TestEveryTestDirectoryIsNamedBySomeLane`` -- a test directory no lane names.
* ``TestEveryPytestLaneInstallsTheCascorExtra`` -- a lane that runs this suite without the extra.

The first is the load-bearing one for the outage: it pins the cause rather than one workflow's
spelling, so it still fires if the workflows are renamed or a third lane is added.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
CONFTEST = SRC / "tests" / "conftest.py"
WORKFLOWS = REPO / ".github" / "workflows"

CLIENT = "juniper_cascor_client"
EXTRA = "juniper-cascor"

# Submodules ``src/`` imports that the stub deliberately does NOT fabricate. Each entry is a
# decision with a cost: a lane that does not install the real client cannot collect the modules
# importing it. That cost is paid by TestEveryPytestLaneInstallsTheCascorExtra below, which is
# what makes these exemptions safe rather than merely tolerated.
#
#   testing   -- conftest says so in a comment. Stubbing it would defeat the
#                ``pytest.importorskip`` guards that skip FakeCascorClient suites when the real
#                package is absent; they would run against a MagicMock and pass vacuously.
#   constants -- these are wire values (endpoint paths, retry method allow-lists). A stub would
#                have to invent them, and an invented endpoint that drifts from the client's real
#                one is a fixture encoding the defect it is supposed to catch. Better to require
#                the real package than to assert against a value this repo made up.
NOT_STUBBED_BY_DESIGN = {"testing", "constants"}


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────────────────────
def _production_sources() -> list[Path]:
    """Every .py under src/ except the test tree itself and build artefacts."""
    return [p for p in SRC.rglob("*.py") if "tests" not in p.relative_to(SRC).parts and "__pycache__" not in p.parts]


def _imported_submodules() -> dict[str, set[Path]]:
    """Map ``juniper_cascor_client.<sub>`` -> the production files importing it.

    Covers both ``from juniper_cascor_client.sub import X`` and ``import juniper_cascor_client.sub``,
    at any nesting depth (a lazy import inside a function still executes at call time).
    """
    found: dict[str, set[Path]] = {}
    for path in _production_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover - not expected in this repo
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            for name in names:
                if name == CLIENT or not name.startswith(CLIENT + "."):
                    continue
                found.setdefault(name.split(".", 1)[1].split(".")[0], set()).add(path)
    return found


def _stubbed_submodules() -> set[str]:
    """Submodules conftest registers in ``sys.modules`` under the stub branch."""
    text = CONFTEST.read_text(encoding="utf-8")
    return set(re.findall(rf'sys\.modules\[["\']{re.escape(CLIENT)}\.([A-Za-z_][A-Za-z0-9_]*)["\']\]', text))


def _workflow_docs() -> list[tuple[Path, dict]]:
    docs: list[tuple[Path, dict]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:  # pragma: no cover - a malformed workflow is its own failure
            continue
        if isinstance(loaded, dict):
            docs.append((path, loaded))
    return docs


def _strip_comments(shell: str) -> str:
    """Drop whole-line ``#`` comments from a run-step body.

    Load-bearing: this file's own workflow comment NAMES the extra, so a substring search over
    the raw text is satisfied by the prose explaining the requirement rather than by the command
    meeting it. Caught by mutation-check -- the first draft of this guard passed with the extra
    removed.
    """
    return "\n".join(line for line in shell.splitlines() if not line.lstrip().startswith("#"))


def _run_steps(doc: dict) -> list[str]:
    steps: list[str] = []
    for job in (doc.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                steps.append(_strip_comments(step["run"]))
    return steps


def _installs_extra(shell: str) -> bool:
    """True iff some ``pip install`` COMMAND (not a comment) requests the extra.

    MEMBERSHIP in the bracketed extras list, not equality with it. The original pattern was
    ``\\[juniper-cascor\\]`` -- the extra had to be the WHOLE bracket -- so a lane installing
    ``.[test,juniper-cascor,observability]`` read as not installing it at all. That is what this
    guard reported against canopy#650, where every lane did install the extra, and it would have
    rejected any future multi-extra lane the same way. The guard's subject is whether the real
    client reaches the lane, not how many extras share the brackets.
    """
    for line in shell.splitlines():
        if not re.search(r"pip\s+install\b", line):
            continue
        for match in re.finditer(r"\[([^\]]*)\]", line):
            if EXTRA in [part.strip() for part in match.group(1).split(",")]:
                return True
    return False


def _lanes_running_this_suite() -> list[tuple[Path, str]]:
    """Workflows whose run-steps invoke pytest against this repo's tests."""
    lanes: list[tuple[Path, str]] = []
    for path, doc in _workflow_docs():
        joined = "\n".join(_run_steps(doc))
        if re.search(r"\bpytest\b", joined) and re.search(r"\bsrc/tests\b|-m\s+[\"']", joined):
            lanes.append((path, joined))
    return lanes


# ─────────────────────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.regression
class TestTheStubCoversEverySubmoduleSrcImports:
    """The stub must satisfy every ``juniper_cascor_client`` submodule production code imports."""

    def test_constants_is_imported_by_src(self):
        """Anchor: the submodule whose absence caused the outage is still the one src imports."""
        assert "constants" in _imported_submodules(), "src/ no longer imports juniper_cascor_client.constants. If that import was removed " "on purpose, drop this anchor test; the coverage test below stands on its own."

    def test_every_imported_submodule_is_stubbed_or_exempt(self):
        imported = _imported_submodules()
        stubbed = _stubbed_submodules()
        missing = {sub: paths for sub, paths in imported.items() if sub not in stubbed and sub not in NOT_STUBBED_BY_DESIGN}
        assert not missing, (
            "src/tests/conftest.py's juniper_cascor_client stub does not register " + ", ".join(sorted(missing)) + " -- so a lane installed WITHOUT the [juniper-cascor] extra dies at COLLECTION, not " "at an assertion. Imported by: " + "; ".join(f"{sub} <- {', '.join(sorted(str(p.relative_to(REPO)) for p in paths))}" for sub, paths in sorted(missing.items())) + ". Either register it in the stub branch of conftest, or add it to " "NOT_STUBBED_BY_DESIGN with the reason it must not be fabricated."
        )

    def test_testing_submodule_stays_unstubbed(self):
        """``.testing`` is exempt by design -- keep that a decision, not an accident."""
        assert "testing" not in _stubbed_submodules(), "conftest now stubs juniper_cascor_client.testing. That defeats the " "pytest.importorskip guards which skip FakeCascorClient suites when the real package " "is absent -- they would run against a MagicMock and pass vacuously."


@pytest.mark.regression
class TestEveryTestDirectoryIsNamedBySomeLane:
    """A test directory no workflow names runs nowhere, however green the badge is.

    ``src/tests/contract/`` was in this state from its creation until 2026-09-21: absent from all
    three of ci.yml's path lists, and its tests are ``@pytest.mark.unit`` so the scheduled lane's
    ``-m "slow or integration"`` selector deselected them. Its only trace in CI was a COLLECTION
    error -- which repairing the scheduled lane would have silently removed.
    """

    # ``ui`` is excluded from the default addopts (``--ignore=src/tests/ui``) and runs in its own
    # lane; the exemption is recorded here so it stays a decision rather than another blind spot.
    EXEMPT = {"ui"}

    def _test_dirs(self) -> set[str]:
        """Immediate subdirectories of src/tests that actually contain test modules."""
        return {child.name for child in (SRC / "tests").iterdir() if child.is_dir() and child.name != "__pycache__" and any(child.rglob("test_*.py"))}

    def test_discovery_finds_the_known_directories(self):
        """Guard the instrument before trusting the check built on it."""
        found = self._test_dirs()
        assert {"unit", "regression", "integration", "contract"} <= found, f"Test-directory discovery returned {sorted(found)}, which is missing one of the " "directories known to exist. The wiring check below would pass vacuously."

    def test_every_test_directory_appears_in_some_lane(self):
        joined = "\n".join(joined for _, joined in _lanes_running_this_suite())
        unwired = sorted(name for name in self._test_dirs() if name not in self.EXEMPT and f"src/tests/{name}" not in joined)
        assert not unwired, "These src/tests subdirectories are named by no workflow pytest invocation, so their " f"tests run in no lane: {', '.join(unwired)}. Add each to a lane's path list (or to " "EXEMPT with the lane that covers it). A directory that runs nowhere still collects, " "so it can look healthy while asserting nothing."


@pytest.mark.regression
class TestEveryPytestLaneInstallsTheCascorExtra:
    """A lane that runs this suite must install the real client, or it cannot collect it."""

    def test_at_least_one_lane_was_discovered(self):
        """Guard the instrument: a parser that finds nothing would pass the next test vacuously."""
        assert _lanes_running_this_suite(), "No workflow was detected as running pytest. The discovery helper is broken, and " "test_every_pytest_lane_installs_the_extra would pass without checking anything."

    def test_every_pytest_lane_installs_the_extra(self):
        offenders = [str(path.relative_to(REPO)) for path, joined in _lanes_running_this_suite() if not _installs_extra(joined)]
        assert not offenders, "These workflows run pytest over src/tests without installing the " f'[{EXTRA}] extra: {", ".join(offenders)}. src/tests/conftest.py will inject the ' "juniper_cascor_client stub, which does not carry every submodule src/ imports, and " "test modules importing CascorServiceAdapter will fail at COLLECTION -- exiting the " "job 1 regardless of how many tests pass. This is what kept Scheduled Tests red for " "63 consecutive runs (2026-07-21 .. 2026-09-21)."
