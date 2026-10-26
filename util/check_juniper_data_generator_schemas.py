#!/usr/bin/env python3
"""
Project:     Juniper
Sub-Project: juniper-canopy
Application: util
Author:      Paul Calnon
Version:     0.1.0
License:     MIT License

Compare canopy's committed snapshots of juniper-data's generator parameter schemas with a real
juniper-data, and fail on any difference (juniper-canopy#737).

Why this exists
---------------
canopy forwards to a juniper-data generator only the parameters ``src/dataset_schema.py`` declares
(``DECLARED_PARAM_DEFAULTS``, W1.2 / juniper-canopy#733), and the unit tests pin that table to a committed
capture of juniper-data's schemas, ``src/tests/fixtures/juniper_data_sequence_generator_schemas.json``.
Nothing compared the capture with juniper-data itself, so upstream drift was silent:

* a parameter ADDED upstream is withheld from every request that sets it;
* a parameter REMOVED upstream is still sent, and juniper-data drops unknown keys without a word;
* a changed DEFAULT makes an untouched field read as an edit, so it is sent.

``.github/workflows/juniper-data-schema-drift.yml`` runs this script against each juniper-data release.

What is compared
----------------
Every entry of every ``src/tests/fixtures/juniper_data_*generator_schemas.json``, against the generator of
the same name in juniper-data's ``GENERATOR_REGISTRY``. The fixtures decide WHICH generators -- nothing here
is hard-coded -- so an entry added to a fixture, or a sibling fixture of the same shape (flat ``equities``,
say), is compared from the commit that adds it. For each one:

* ``params_class.model_json_schema()`` -- the ``schema`` field of ``GET /v1/generators`` -- round-tripped
  through JSON as the wire carries it, key by key against the entry's ``schema``;
* ``version`` against the entry's ``version``.

Equality is JSON's: object key order is ignored and ``1`` equals ``1.0``, but ``true`` is not ``1`` (Python's
``==`` says it is). A generator juniper-data no longer registers is drift as well.

Which juniper-data
------------------
By default, the installed one. The registry module imports FastAPI and pydantic-settings, so install the
release WITH its ``[api]`` extra: a bare ``pip install juniper-data`` cannot import it. The script refuses
to compare unless the imported package is the installed distribution's own files, because a copy elsewhere
on ``sys.path`` -- or an editable install, whose metadata version is frozen at install time -- would
otherwise answer under the wrong version. ``--expected-version`` also refuses any version but the one named;
the workflow passes the version it installed, so the release it reports is the release it tested.

``--juniper-data-src`` compares a checkout instead (what the capture tool reads), refusing if
``juniper_data`` was imported from anywhere else. Use it for an editable install too.

Usage, from the canopy repo root::

    python -I util/check_juniper_data_generator_schemas.py
    python -I util/check_juniper_data_generator_schemas.py --expected-version 0.17.1
    /opt/miniforge3/envs/JuniperData/bin/python -I util/check_juniper_data_generator_schemas.py --juniper-data-src ../juniper-data

``-I`` keeps the checkout and the user site off ``sys.path``. Exit codes: 0 no drift; 1 drift (every
difference, and the command that re-captures each affected fixture, are printed); 2 the check could not
run -- no fixture, a malformed fixture, juniper-data not importable or not provably the version reported.
None of those is ever a pass.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import math
import os
import sys
import tomllib
import traceback
from pathlib import Path
from typing import Any, NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "src" / "tests" / "fixtures"

# WHICH snapshots: the sequence-generator capture, and any sibling that follows its naming scheme
# (``juniper_data_<what>_generator_schemas.json``). A NAME glob rather than a scan of every JSON fixture, so
# that the workflow's pull_request ``paths:`` filter names exactly the same set. The unit tests pin the two
# together, and fail if a fixture carrying a juniper-data provenance block is named outside this glob.
FIXTURE_GLOB = "juniper_data_*generator_schemas.json"

REGISTRY_MODULE = "juniper_data.api.routes.generators"
DISTRIBUTION = "juniper-data"

# The re-capture command must be copy-pasteable, so it follows the capture tool's own documented usage. Two
# kinds of snapshot exist, told apart by their provenance block:
#   * captured from a juniper-data CHECKOUT (no ``wheel`` key): the tool imports the checkout, so it runs under
#     an interpreter with juniper-data's dependencies -- the one that tool's usage names;
#   * captured from a PUBLISHED wheel (``wheel`` recorded): the tool must run in a virtualenv installed from
#     that very wheel, which it verifies, under the repo's gitignored tmp/ -- again as that tool documents.
# The unit tests require every committed snapshot's tool to accept each flag its command passes, and to need
# no flag it omits.
CAPTURE_PYTHON = "/opt/miniforge3/envs/JuniperData/bin/python"
JUNIPER_DATA_CHECKOUT = "../juniper-data"
WHEEL_WORKDIR = "tmp/jd-wheel"

_VALUE_WIDTH = 160


class CheckError(Exception):
    """The comparison could not be made. Exit 2: never reported as a pass."""


class Entry(NamedTuple):
    """One generator as a fixture records it."""

    name: str
    version: Any
    schema: dict


class Fixture(NamedTuple):
    """One committed snapshot: where it is, what produced it, its generators, and whether it came from a published wheel."""

    path: Path
    tool: str
    commit: str
    captured: str
    entries: tuple
    from_wheel: bool = False


class Difference(NamedTuple):
    """One difference, by JSON path. ``added``: only juniper-data has it. ``removed``: only the fixture."""

    path: tuple
    kind: str
    fixture: Any = None
    upstream: Any = None


class JuniperData(NamedTuple):
    """The juniper-data compared against: its registry, its version and where it was imported from."""

    registry: dict
    version: str
    package: Path
    checkout: Path | None


class Result(NamedTuple):
    """The report lines, each drifted ``(fixture, entry, differences)``, and how many generators were compared."""

    lines: list
    drifted: list
    compared: int


# ------------------------------------------------------------------------------------------- the fixtures


def display_path(path: Path) -> str:
    """``path`` relative to the canopy repo root when it is inside it (the re-capture command runs there)."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def discover_fixtures(directory: Path | None = None) -> list[Path]:
    """The generator-schema snapshots in ``directory`` (default: canopy's fixtures), sorted by name."""
    return sorted((FIXTURES_DIR if directory is None else Path(directory)).glob(FIXTURE_GLOB))


def load_fixture(path: Path) -> Fixture:
    """Parse one snapshot, refusing anything that is not the capture tool's shape -- an empty one included."""
    where = display_path(path)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CheckError(f"{where}: cannot be read as JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise CheckError(f"{where}: is not a JSON object")
    provenance = data.get("_provenance")
    if not isinstance(provenance, dict) or provenance.get("source") != "juniper-data":
        raise CheckError(f"{where}: has no _provenance block naming juniper-data as its source")
    tool = provenance.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise CheckError(f"{where}: its _provenance names no capture tool, so there is no re-capture command to give")
    generators = data.get("generators")
    if not isinstance(generators, list) or not generators:
        raise CheckError(f"{where}: lists no generators -- an empty snapshot would pass without comparing anything")
    entries = []
    for index, item in enumerate(generators):
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or "version" not in item or not isinstance(item.get("schema"), dict):
            raise CheckError(f"{where}: generators[{index}] is not a {{name, version, schema}} entry")
        entries.append(Entry(item["name"], item["version"], item["schema"]))
    wheel = provenance.get("wheel")
    return Fixture(Path(path), tool, str(provenance.get("commit") or ""), str(provenance.get("captured") or ""), tuple(entries), isinstance(wheel, str) and bool(wheel))


# ---------------------------------------------------------------------------------------------- juniper-data


def checkout_version(checkout: Path) -> str:
    """``[project].version`` from a checkout's ``pyproject.toml``, or ``unknown``."""
    try:
        project = tomllib.loads((checkout / "pyproject.toml").read_text(encoding="utf-8")).get("project")
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown"
    version = project.get("version") if isinstance(project, dict) else None
    return version if isinstance(version, str) and version else "unknown"


def load_juniper_data(checkout: Path | None = None, expected_version: str | None = None) -> JuniperData:
    """Import juniper-data's ``GENERATOR_REGISTRY`` -- installed, or from ``checkout`` -- and prove where it came from."""
    if checkout is not None:
        checkout = Path(checkout).resolve()
        if not (checkout / "juniper_data" / "__init__.py").is_file():
            raise CheckError(f"{checkout} is not a juniper-data checkout: it has no juniper_data/__init__.py")
        sys.path.insert(0, str(checkout))
    try:
        module = importlib.import_module(REGISTRY_MODULE)
    except ImportError as exc:
        raise CheckError(f"cannot import {REGISTRY_MODULE}: {exc}. Install the release with its [api] extra (pip install 'juniper-data[api]==X.Y.Z'): the registry module imports FastAPI and pydantic-settings, which a bare install lacks") from exc
    registry = getattr(module, "GENERATOR_REGISTRY", None)
    if not isinstance(registry, dict) or not registry:
        raise CheckError(f"{REGISTRY_MODULE} has no non-empty GENERATOR_REGISTRY dict: juniper-data has changed shape")
    init_file = getattr(sys.modules.get("juniper_data"), "__file__", None)
    if not init_file:
        raise CheckError("juniper_data was imported as a namespace package, so where it came from cannot be told")
    package = Path(init_file).resolve().parent
    if checkout is not None:
        if not package.is_relative_to(checkout):
            raise CheckError(f"juniper_data was imported from {package}, not from the checkout {checkout}")
        return JuniperData(registry, checkout_version(checkout), package, checkout)
    try:
        distribution = importlib.metadata.distribution(DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError as exc:
        raise CheckError(f"juniper_data imports from {package}, but no {DISTRIBUTION} distribution is installed; for a checkout, pass --juniper-data-src") from exc
    shipped = Path(distribution.locate_file("juniper_data/__init__.py")).resolve().parent
    if shipped != package:
        raise CheckError(f"the installed {DISTRIBUTION} {distribution.version} ships juniper_data at {shipped}, but it was imported from {package} -- so {distribution.version} is not what would be compared. For a checkout or an editable install, pass --juniper-data-src")
    if expected_version is not None and distribution.version != expected_version:
        raise CheckError(f"expected {DISTRIBUTION} {expected_version}, but {distribution.version} is installed")
    return JuniperData(registry, distribution.version, package, None)


def distribution_version(name: str) -> str:
    """The installed version of ``name``, for the report header."""
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


# -------------------------------------------------------------------------------------------- the comparison


def json_equal(a: Any, b: Any) -> bool:
    """Equality as JSON means it: object key order ignored and ``1 == 1.0``, but ``true`` is not ``1``.

    Python's ``==`` gets the last one wrong (``True == 1``), and a default flipped from ``1`` to ``true`` is
    exactly the kind of upstream change this check exists to catch.
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b or (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(json_equal(a[key], b[key]) for key in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and a == b


def diff_json(fixture: Any, upstream: Any, path: tuple = ()) -> list[Difference]:
    """Every difference between two JSON values, by path. Objects recurse; anything else is compared whole."""
    if isinstance(fixture, dict) and isinstance(upstream, dict):
        differences: list[Difference] = []
        for key, value in fixture.items():
            if key in upstream:
                differences.extend(diff_json(value, upstream[key], path + (key,)))
            else:
                differences.append(Difference(path + (key,), "removed", fixture=value))
        differences.extend(Difference(path + (key,), "added", upstream=value) for key, value in upstream.items() if key not in fixture)
        return differences
    if json_equal(fixture, upstream):
        return []
    return [Difference(path, "changed", fixture, upstream)]


def upstream_view(info: Any, name: str) -> dict:
    """``{"version": ..., "schema": ...}`` for one registry entry, its schema as the wire would carry it."""
    try:
        schema = info["params_class"].model_json_schema()
        version = info["version"]
    except (KeyError, TypeError, AttributeError) as exc:
        raise CheckError(f"juniper-data's GENERATOR_REGISTRY[{name!r}] no longer offers params_class.model_json_schema() and version ({type(exc).__name__}: {exc})") from exc
    try:
        schema = json.loads(json.dumps(schema, ensure_ascii=False))
    except (TypeError, ValueError) as exc:
        raise CheckError(f"juniper-data's {name!r} schema is not JSON ({exc}), so GET /v1/generators could not serve it either") from exc
    return {"version": version, "schema": schema}


def compare_entry(entry: Entry, registry: dict) -> list[Difference]:
    """Every difference between one fixture entry and juniper-data's generator of the same name."""
    if entry.name not in registry:
        return [Difference((), "removed")]
    return diff_json({"version": entry.version, "schema": entry.schema}, upstream_view(registry[entry.name], entry.name))


# -------------------------------------------------------------------------------------------- the report


def show(value: Any) -> str:
    """A value as JSON, cut to a readable width."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= _VALUE_WIDTH else text[: _VALUE_WIDTH - 1] + "…"


def _default_of(prop: Any) -> str:
    return show(prop["default"]) if isinstance(prop, dict) and "default" in prop else "none"


def _locate(path: tuple) -> tuple[str, str]:
    """``(label, key)``: which field (or the schema as a whole) a path falls in, and the key path inside it."""
    if len(path) >= 3 and path[:2] == ("schema", "properties"):
        return f'field "{path[2]}"', ".".join(str(part) for part in path[3:])
    return "schema", ".".join(str(part) for part in path[1:])


def describe(difference: Difference) -> str:
    """One line naming what differs: the field, the key inside it, and both values."""
    path, kind = difference.path, difference.kind
    if not path:
        return "not in juniper-data's GENERATOR_REGISTRY: removed or renamed upstream"
    if path == ("version",):
        return f"version: fixture {show(difference.fixture)}, juniper-data {show(difference.upstream)}"
    label, key = _locate(path)
    if not key:
        if kind == "added":
            return f"{label}: added upstream (default {_default_of(difference.upstream)})"
        if kind == "removed":
            return f"{label}: removed upstream (fixture default {_default_of(difference.fixture)})"
        return f"{label}: fixture {show(difference.fixture)}, juniper-data {show(difference.upstream)}"
    if kind == "added":
        return f"{label}: {key} added upstream: {show(difference.upstream)}"
    if kind == "removed":
        return f"{label}: {key} removed upstream (fixture {show(difference.fixture)})"
    return f"{label}: {key}: fixture {show(difference.fixture)}, juniper-data {show(difference.upstream)}"


def summarize(difference: Difference) -> str:
    """A few words for the one-line annotation: ``horizon.default changed``, ``version 6.0.0 -> 7.0.0``."""
    path = difference.path
    if not path:
        return "no longer registered"
    if path == ("version",):
        return f"version {difference.fixture} -> {difference.upstream}"
    label, key = _locate(path)
    subject = label[len("field ") :].strip('"') if label.startswith("field ") else "schema"
    return f"{subject}{'.' + key if key else ''} {difference.kind}"


def _wheel_file(version: str) -> str:
    """The file ``pip download`` writes for a juniper-data release: one pure-Python wheel."""
    return f"juniper_data-{version}-py3-none-any.whl"


def recapture_command(fixture: Fixture, juniper: JuniperData) -> str:
    """The capture-tool command line that rewrites ``fixture`` from the juniper-data compared against."""
    source = str(juniper.checkout) if juniper.checkout is not None else JUNIPER_DATA_CHECKOUT
    where = display_path(fixture.path)
    if fixture.from_wheel:
        names = " ".join(entry.name for entry in fixture.entries)
        return f"{WHEEL_WORKDIR}/venv/bin/python -I {fixture.tool} --wheel {WHEEL_WORKDIR}/wheel/{_wheel_file(juniper.version)} --juniper-data-src {source} --generators {names} --fixture {where}"
    return f"{CAPTURE_PYTHON} -I {fixture.tool} --juniper-data-src {source} --fixture {where}"


def recapture_instructions(fixture: Fixture, juniper: JuniperData) -> list[str]:
    """How to refresh one drifted fixture -- and the declaration pinned to it -- from the juniper-data compared against."""
    where = display_path(fixture.path)
    source = str(juniper.checkout) if juniper.checkout is not None else JUNIPER_DATA_CHECKOUT
    version = juniper.version
    if fixture.from_wheel:
        lines = [f"To re-capture {where} from the published juniper-data {version} wheel, run from the canopy repo root, with {source} a juniper-data checkout:"]
        if juniper.checkout is not None:
            lines.append(f"  (this snapshot is read from a PUBLISHED wheel: {version}, the checkout's version, must be on PyPI first)")
        wheel = f"{WHEEL_WORKDIR}/wheel/{_wheel_file(version)}"
        lines.append(f"  git -C {source} fetch --tags origin")
        lines.append(f"  python3 -m venv {WHEEL_WORKDIR}/venv")
        lines.append(f"  {WHEEL_WORKDIR}/venv/bin/pip download --no-deps --only-binary=:all: juniper-data=={version} -d {WHEEL_WORKDIR}/wheel")
        lines.append(f'  {WHEEL_WORKDIR}/venv/bin/pip install "$PWD/{wheel}[api]"')
    elif juniper.checkout is not None:
        lines = [f"To re-capture {where} from that checkout, run from the canopy repo root:"]
    else:
        lines = [f"To re-capture {where} from juniper-data {version}, run from the canopy repo root, with {source} a juniper-data checkout:"]
        lines.append(f"  git -C {source} fetch --tags origin && git -C {source} checkout v{version}")
    lines.append(f"  {recapture_command(fixture, juniper)}")
    lines.append("then update those entries of DECLARED_PARAM_DEFAULTS in src/dataset_schema.py from its output, and the source string recorded for them, and re-run this check.")
    return lines


def check(fixtures: list[Fixture], juniper: JuniperData) -> Result:
    """Compare every entry of every fixture with ``juniper``; the report says what differs and how to re-capture."""
    origin = f"the checkout {juniper.checkout}" if juniper.checkout is not None else f"installed, {juniper.package}"
    lines = [f"juniper-data {juniper.version} ({origin}); pydantic {distribution_version('pydantic')}"]
    drifted: list = []
    compared = 0
    for fixture in fixtures:
        lines.append(f"{display_path(fixture.path)}: {len(fixture.entries)} generators, captured {fixture.captured or '(undated)'} from juniper-data {fixture.commit[:8] or '(unknown commit)'}")
        for entry in fixture.entries:
            compared += 1
            differences = compare_entry(entry, juniper.registry)
            lines.append(f"  {entry.name:<16} {str(entry.version):<8} {'DRIFT' if differences else 'ok'}")
            lines.extend(f"      {describe(difference)}" for difference in differences)
            if differences:
                drifted.append((fixture, entry, differences))
    if not drifted:
        lines.append(f"no drift: {compared} generators in {len(fixtures)} fixture(s) match juniper-data {juniper.version}")
        return Result(lines, drifted, compared)
    lines.append("")
    lines.append(f"DRIFT: {len(drifted)} of {compared} generators differ from juniper-data {juniper.version}: {', '.join(entry.name for _, entry, _ in drifted)}")
    seen: list[Path] = []
    for fixture, _entry, _differences in drifted:
        if fixture.path in seen:
            continue
        seen.append(fixture.path)
        lines.append("")
        lines.extend(recapture_instructions(fixture, juniper))
    return Result(lines, drifted, compared)


# -------------------------------------------------------------------------------------- GitHub Actions output


def _escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def annotation(level: str, title: str, message: str) -> str | None:
    """A workflow-command line that puts ``message`` on the run page, or None outside GitHub Actions."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return None
    return f"::{level} title={_escape_property(title)}::{_escape_data(message)}"


def write_step_summary(lines: list[str]) -> None:
    """Append the report to the job summary when GitHub Actions provides one."""
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    try:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("### juniper-data generator-schema drift\n\n```text\n" + "\n".join(lines) + "\n```\n")
    except OSError as exc:  # the report is already on stdout; a summary that cannot be written must not turn into exit 1 (drift)
        print(f"warning: could not append to the job summary {summary}: {exc}", file=sys.stderr)


def _emit(line: str | None) -> None:
    if line is not None:
        print(line)


def _could_not_run(message: str) -> int:
    print(f"juniper-data schema drift check could not run: {message}", file=sys.stderr)
    _emit(annotation("error", "juniper-data schema drift check could not run", message))
    return 2


# -------------------------------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare canopy's committed juniper-data generator-schema snapshots with a real juniper-data (juniper-canopy#737).")
    parser.add_argument("--fixture", type=Path, action="append", metavar="PATH", help=f"a snapshot to compare (repeatable); default: every {FIXTURE_GLOB} in {display_path(FIXTURES_DIR)}")
    parser.add_argument("--juniper-data-src", type=Path, metavar="PATH", help="compare a juniper-data checkout instead of the installed package")
    parser.add_argument("--expected-version", metavar="X.Y.Z", help="refuse to compare unless the installed juniper-data is exactly this version")
    args = parser.parse_args(argv)
    if args.juniper_data_src is not None and args.expected_version is not None:
        parser.error("--expected-version checks the installed juniper-data; it cannot be combined with --juniper-data-src")
    try:
        paths = args.fixture or discover_fixtures()
        if not paths:
            raise CheckError(f"no {FIXTURE_GLOB} in {display_path(FIXTURES_DIR)}: nothing to compare, and that must not pass")
        fixtures = [load_fixture(path) for path in paths]
        juniper = load_juniper_data(args.juniper_data_src, args.expected_version)
        result = check(fixtures, juniper)
    except CheckError as exc:
        return _could_not_run(str(exc))
    except Exception:  # an unexpected failure is "could not run" (2): never drift (1), and never a pass
        return _could_not_run(traceback.format_exc().rstrip())
    print("\n".join(result.lines))
    write_step_summary(result.lines)
    if not result.drifted:
        _emit(annotation("notice", "juniper-data schema drift", result.lines[-1]))
        return 0
    for fixture, entry, differences in result.drifted:
        changes = ", ".join(dict.fromkeys(summarize(difference) for difference in differences))
        message = f"{display_path(fixture.path)} vs juniper-data {juniper.version}: {changes}. Re-capture: {recapture_command(fixture, juniper)}"
        _emit(annotation("error", f"juniper-data schema drift: {entry.name}", message))
    return 1


if __name__ == "__main__":
    sys.exit(main())
