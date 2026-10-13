"""Regression guard: the active environment's ``juniper-*`` client wheels must
satisfy the version floors declared in ``pyproject.toml``.

Incident (2026-06-26). Canopy's unit/CI suite was green while the running app
was broken at runtime. The ``JuniperCanopy1`` conda env held
``juniper-data-client==0.4.0`` and ``juniper-cascor-client==0.3.0`` — both
*below* the code's ``pyproject.toml`` floors (``>=0.4.1`` and ``>=0.5.0``). The
multi-repo refactor adopted client APIs that only exist at/above those floors:

* ``JuniperDataClient(on_request=...)``      — added in data-client 0.4.1
  (``src/demo_mode.py``)
* ``CascorControlStream(origin=...)``        — added in cascor-client 0.5.0
  (``src/backend/cascor_service_adapter.py``)
* ``JuniperCascorClient.save_snapshot(...)`` — added in cascor-client 0.5.0
  (``src/backend/cascor_service_adapter.py``)

The suite stayed green because ``src/tests/conftest.py`` patches the data and
cascor clients with mocks for the whole session (see ``mock_juniper_data_client``
— it does ``patch("juniper_data_client.JuniperDataClient", ...)``), so the real
*stale* constructor signatures were never exercised; CI installs from
``requirements.lock`` (correct versions). The breakage lived only at the
real-client call seam, which no test touched.

That session-wide symbol patch is exactly why an ``inspect.signature`` /
``hasattr`` API check would NOT work here — it would inspect the MagicMock, not
the installed wheel. This guard therefore reads the *installed distribution
metadata* via :mod:`importlib.metadata`, which the patch never touches, and
compares it against the floors parsed straight from ``pyproject.toml`` (single
source of truth — bump a floor there and this guard tracks it automatically).

It fails on the stale env and passes once the env matches ``requirements.lock``
(``python -m pip install -r requirements.lock``). See
``notes/CANOPY_RUNTIME_CLIENT_FLOOR_DRIFT_ROOT_CAUSE_2026-06-26.md``.

Note: juniper-ml's ``util/editable_install_drift_check.py`` does NOT catch this
class — it only inspects *editable* installs, while these are plain wheels.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = REPO_ROOT / "pyproject.toml"

# Clients canopy constructs unconditionally on the runtime hot path. They live
# in pyproject's optional-dependencies, but are de-facto required: the demo data
# path (``src/demo_mode.py``) and the cascor service adapter
# (``src/backend/cascor_service_adapter.py``) import and instantiate them. The
# sanity test asserts pyproject declares floors for both; their installed-floor
# compliance is covered by the generic parametrized test below, which skips a
# client that is absent. Absence is a legitimate minimal-install state: canopy
# lazy-imports the clients (they live in optional extras) and CI installs
# neither (mocks + ``pip install -e .`` base) — so the guard must not fail on
# absence, only on installed-but-stale.
RUNTIME_CRITICAL_CLIENTS = ("juniper-data-client", "juniper-cascor-client")


def _juniper_requirements() -> dict[str, SpecifierSet]:
    """Return ``{canonical-name: SpecifierSet}`` for every ``juniper-*``
    requirement that carries a version specifier, gathered from ``[project]``
    dependencies and every ``[project.optional-dependencies]`` group in
    ``pyproject.toml``.

    Requirements without a specifier (e.g. the ``all`` extra's
    ``juniper-canopy[...]`` self-reference) are skipped — there is nothing to
    check. Floors are read here so the guard has a single source of truth and
    cannot drift from the published packaging contract.
    """
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = data.get("project", {})
    req_strings: list[str] = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        req_strings.extend(group)

    floors: dict[str, SpecifierSet] = {}
    for raw in req_strings:
        req = Requirement(raw)
        name = canonicalize_name(req.name)
        if not name.startswith("juniper-"):
            continue
        if not req.specifier:
            continue
        # Intersect if a name appears in more than one group; in practice each
        # juniper-* appears once.
        floors[name] = floors.get(name, SpecifierSet()) & req.specifier
    return floors


_JUNIPER_REQUIREMENTS = _juniper_requirements()


def _drift_message(name: str, installed: str, specifier: SpecifierSet) -> str:
    return f"{name}=={installed} in the active environment violates the " f"pyproject.toml floor '{name}{specifier}'. The environment has drifted " f"below the client API the code requires. Green tests do NOT catch this " f"(the clients are mocked in conftest.py). Fix the environment, not the " f"code: `python -m pip install -r requirements.lock`."


@pytest.mark.unit
def test_pyproject_declares_juniper_floors() -> None:
    """Sanity: the parser actually found floored juniper-* deps.

    Guards against a future pyproject restructure silently turning this whole
    module into a no-op (zero parametrized cases would otherwise still report
    green).
    """
    assert _JUNIPER_REQUIREMENTS, f"No version-floored juniper-* requirements were parsed from {PYPROJECT}; the floor guard would be a silent no-op."
    for name in RUNTIME_CRITICAL_CLIENTS:
        assert canonicalize_name(name) in _JUNIPER_REQUIREMENTS, f"{name} should be a declared, version-floored dependency in pyproject.toml."


@pytest.mark.unit
@pytest.mark.parametrize("name", sorted(_JUNIPER_REQUIREMENTS))
def test_installed_juniper_dep_satisfies_floor(name: str) -> None:
    """Every *installed* juniper-* dependency must satisfy its pyproject floor.

    Absent optional extras are skipped: a genuinely-missing required client
    surfaces as a loud ImportError at collection, not as silent drift. The
    failure mode this guard exists for is *installed-but-stale*.
    """
    specifier = _JUNIPER_REQUIREMENTS[name]
    try:
        installed = importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        pytest.skip(f"{name} not installed in the active env (declared floor '{name}{specifier}'); not the silent-drift case this guard targets.")
    else:
        # ``else`` (rather than a bare trailing statement) so ``installed`` is
        # only read when the lookup succeeded. pytest.skip() raises, but CodeQL
        # does not model that — without the else it flags
        # py/uninitialized-local-variable on ``installed``.
        assert specifier.contains(installed, prereleases=True), _drift_message(name, installed, specifier)
