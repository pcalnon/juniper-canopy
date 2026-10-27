#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_check_juniper_data_generator_schemas.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   juniper-canopy#737 -- the comparison of canopy's
#                committed juniper-data generator-schema snapshots
#                with a real juniper-data
#                (util/check_juniper_data_generator_schemas.py), and
#                the workflow that runs it
#                (.github/workflows/juniper-data-schema-drift.yml).
#####################################################################
"""The juniper-data schema drift check: it fails on every kind of drift and passes on equality (juniper-canopy#737).

``util/check_juniper_data_generator_schemas.py`` compares every generator in canopy's committed snapshots of
juniper-data's parameter schemas with ``GENERATOR_REGISTRY[name]`` of a real juniper-data:
``params_class.model_json_schema()`` and ``version``. These tests prove it FAILS on each drift the issue names
-- a field added, a field removed, a default changed, the version changed -- naming the generator, the field
and the exact re-capture command, and PASSES on equality, over the committed fixture itself.

None of them needs juniper-data. The registry is a fake serving a fixture's own schemas (or a real pydantic
model, to keep the ``model_json_schema()`` path honest), and the two import modes run in subprocesses
against throwaway ``juniper_data`` packages under ``tmp_path``. The last class pins the workflow's contract
with juniper-data's notify-consumers sender.
"""

from __future__ import annotations

import ast
import copy
import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import types
from pathlib import Path

import pydantic
import pytest
import yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "util" / "check_juniper_data_generator_schemas.py"
WORKFLOW = REPO / ".github" / "workflows" / "juniper-data-schema-drift.yml"
WORKFLOW_REL = ".github/workflows/juniper-data-schema-drift.yml"
SCRIPT_REL = "util/check_juniper_data_generator_schemas.py"
FIXTURES = REPO / "src" / "tests" / "fixtures"
SEQUENCE_FIXTURE = FIXTURES / "juniper_data_sequence_generator_schemas.json"
SEQUENCE_FIXTURE_REL = "src/tests/fixtures/juniper_data_sequence_generator_schemas.json"
SHA_PINNED = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load():
    spec = importlib.util.spec_from_file_location("check_juniper_data_generator_schemas", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # register before exec: typing / dataclass machinery looks modules up by name
    spec.loader.exec_module(module)
    return module


drift = _load()


@pytest.fixture(autouse=True)
def _outside_github_actions(monkeypatch):
    """CI sets these for the test job itself: the script would annotate, and append to the job's real summary."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


# ------------------------------------------------------------------------------------------------ helpers


class FakeParams:
    """Stands in for a pydantic params class: ``model_json_schema()`` hands out a copy of a fixed schema."""

    def __init__(self, schema: dict):
        self._schema = copy.deepcopy(schema)

    def model_json_schema(self) -> dict:
        return copy.deepcopy(self._schema)


def _fixture_data(path: Path = SEQUENCE_FIXTURE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _serving(data: dict) -> dict:
    """A registry serving exactly what ``data`` recorded: the no-drift baseline."""
    return {entry["name"]: {"params_class": FakeParams(entry["schema"]), "version": entry["version"]} for entry in data["generators"]}


def _upstream(mutate, path: Path = SEQUENCE_FIXTURE) -> dict:
    """A registry serving the committed fixture, after ``mutate(generators_by_name)`` changed it UPSTREAM."""
    data = _fixture_data(path)
    mutate({entry["name"]: entry for entry in data["generators"]})
    return _serving(data)


def _juniper(registry: dict, version: str = "9.9.9"):
    return drift.JuniperData(registry, version, Path("site-packages") / "juniper_data", None)


def _check(registry: dict, path: Path = SEQUENCE_FIXTURE, version: str = "9.9.9"):
    return drift.check([drift.load_fixture(path)], _juniper(registry, version))


def _lines_for(result, name: str) -> list[str]:
    [differences] = [found for _fixture, entry, found in result.drifted if entry.name == name]
    return [drift.describe(difference) for difference in differences]


def _main(monkeypatch, registry: dict, argv: list[str], version: str = "9.9.9") -> int:
    monkeypatch.setattr(drift, "load_juniper_data", lambda checkout=None, expected_version=None: _juniper(registry, version))
    return drift.main(argv)


def _snapshot(path: Path, generators: list[dict], tool: str = "util/ad-hoc/2026-10-08_capture_sequence_generator_schemas.py") -> Path:
    provenance = {"source": "juniper-data", "commit": "0" * 40, "dirty": False, "captured": "2026-10-26", "what": "a test snapshot", "tool": tool}
    path.write_text(json.dumps({"_provenance": provenance, "generators": generators}, indent=2), encoding="utf-8")
    return path


def _defaulted_fields(entry: dict) -> list[str]:
    return [name for name, prop in entry["schema"]["properties"].items() if "default" in prop]


def _argparse_flags(tool: Path) -> tuple[set, set]:
    """``(every flag, the required flags)`` that the tool's argparse ``add_argument`` calls declare."""
    flags: set = set()
    required: set = set()
    for node in ast.walk(ast.parse(tool.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "add_argument" and node.args and isinstance(node.args[0], ast.Constant):
            flags.add(node.args[0].value)
            if any(keyword.arg == "required" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords):
                required.add(node.args[0].value)
    return flags, required


# A snapshot of known content, for the comparison's semantics. These tests must not move when the committed
# capture is re-captured or extended (canopy #735/#736 may add generators to it), so they do not read it.
SYNTHETIC = [
    {
        "name": "alpha",
        "version": "1.0.0",
        "schema": {
            "description": "Alpha.",
            "properties": {
                "n_steps": {"default": 2000, "minimum": 8, "title": "N Steps", "type": "integer"},
                "lookback": {"default": 32, "maximum": 512, "minimum": 2, "title": "Lookback", "type": "integer"},
                "seed": {"default": 0, "minimum": 0, "title": "Seed", "type": "integer"},
            },
            "title": "AlphaParams",
            "type": "object",
        },
    },
    {"name": "beta", "version": "2.0.0", "schema": {"properties": {"scaling": {"default": "identity", "enum": ["identity", "standardize"], "title": "Scaling", "type": "string"}}, "title": "BetaParams", "type": "object"}},
]


def _synthetic(tmp_path: Path) -> Path:
    return _snapshot(tmp_path / "juniper_data_synthetic_generator_schemas.json", copy.deepcopy(SYNTHETIC))


# -------------------------------------------------------------------------------------- injected upstream drift

INJECTION_KINDS = ["a-field-added", "a-field-removed", "a-default-changed", "the-version-changed"]


def _target() -> dict:
    """The capture's entry the four injections hit: equities_seq, the generator the issue is about, while the capture holds it."""
    entries = _fixture_data()["generators"]
    return next((entry for entry in entries if entry["name"] == "equities_seq"), entries[-1])


def _injection(kind: str) -> tuple:
    """``(generator, mutate, expected line)`` for one kind of upstream drift; the expected values are read from the capture."""
    target = _target()
    name, properties, fields = target["name"], target["schema"]["properties"], _defaulted_fields(target)
    removed, changed = fields[0], fields[-1]
    injections = {
        "a-field-added": (lambda generators: generators[name]["schema"]["properties"].update(new_knob={"default": 7, "title": "New Knob", "type": "integer"}), 'field "new_knob": added upstream (default 7)'),
        "a-field-removed": (lambda generators: generators[name]["schema"]["properties"].pop(removed), f'field "{removed}": removed upstream (fixture default {drift.show(properties[removed]["default"])})'),
        "a-default-changed": (lambda generators: generators[name]["schema"]["properties"][changed].update(default="drifted"), f'field "{changed}": default: fixture {drift.show(properties[changed]["default"])}, juniper-data "drifted"'),
        "the-version-changed": (lambda generators: generators[name].update(version="99.0.0"), f'version: fixture {drift.show(target["version"])}, juniper-data "99.0.0"'),
    }
    mutate, expected = injections[kind]
    return name, mutate, expected


class TestInjectedDrift:
    """Each kind of upstream change the issue names fails the check and is named precisely."""

    @pytest.mark.parametrize("kind", INJECTION_KINDS)
    def test_the_generator_and_the_field_are_named(self, kind):
        name, mutate, expected = _injection(kind)
        result = _check(_upstream(mutate))
        assert [entry.name for _fixture, entry, _found in result.drifted] == [name]
        assert _lines_for(result, name) == [expected]

    @pytest.mark.parametrize("kind", INJECTION_KINDS)
    def test_main_exits_1_and_prints_the_exact_recapture_command(self, monkeypatch, capsys, kind):
        name, mutate, expected = _injection(kind)
        assert _main(monkeypatch, _upstream(mutate), ["--fixture", str(SEQUENCE_FIXTURE)], version="0.17.2") == 1
        out = capsys.readouterr().out
        tool = drift.load_fixture(SEQUENCE_FIXTURE).tool
        assert f"      {expected}" in out
        assert f"DRIFT: 1 of {len(_fixture_data()['generators'])} generators differ from juniper-data 0.17.2: {name}" in out
        assert "  git -C ../juniper-data fetch --tags origin && git -C ../juniper-data checkout v0.17.2" in out
        assert f"  /opt/miniforge3/envs/JuniperData/bin/python -I {tool} --juniper-data-src ../juniper-data --fixture {SEQUENCE_FIXTURE_REL}" in out
        assert "then update those entries of DECLARED_PARAM_DEFAULTS in src/dataset_schema.py from its output, and the source string recorded for them" in out

    @pytest.mark.parametrize("name", [entry["name"] for entry in _fixture_data()["generators"]])
    def test_drift_in_any_generator_of_the_fixture_is_caught(self, name):
        """Every entry is compared -- nothing is hard-coded to six, or to equities_seq."""
        entry = next(item for item in _fixture_data()["generators"] if item["name"] == name)
        field = _defaulted_fields(entry)[0]

        def mutate(generators):
            generators[name]["schema"]["properties"][field]["default"] = "drifted"

        result = _check(_upstream(mutate))
        assert [found.name for _fixture, found, _diffs in result.drifted] == [name]
        assert _lines_for(result, name) == [f'field "{field}": default: fixture {drift.show(entry["schema"]["properties"][field]["default"])}, juniper-data "drifted"']

    def test_a_generator_juniper_data_no_longer_registers_is_drift(self, tmp_path):
        path = _synthetic(tmp_path)
        registry = _serving(_fixture_data(path))
        del registry["beta"]
        assert _lines_for(_check(registry, path), "beta") == ["not in juniper-data's GENERATOR_REGISTRY: removed or renamed upstream"]

    def test_a_default_flipped_from_zero_to_false_is_drift(self, tmp_path):
        """Python's ``==`` calls ``False == 0`` equal; JSON, and this check, do not."""
        path = _synthetic(tmp_path)
        registry = _upstream(lambda generators: generators["alpha"]["schema"]["properties"]["seed"].update(default=False), path)
        assert _lines_for(_check(registry, path), "alpha") == ['field "seed": default: fixture 0, juniper-data false']

    def test_a_key_inside_a_field_appearing_or_vanishing_is_named(self, tmp_path):
        path = _synthetic(tmp_path)

        def mutate(generators):
            properties = generators["alpha"]["schema"]["properties"]
            properties["n_steps"]["multipleOf"] = 2
            del properties["lookback"]["maximum"]

        assert _lines_for(_check(_upstream(mutate, path), path), "alpha") == ['field "n_steps": multipleOf added upstream: 2', 'field "lookback": maximum removed upstream (fixture 512)']

    def test_a_schema_level_change_is_named(self, tmp_path):
        path = _synthetic(tmp_path)
        registry = _upstream(lambda generators: generators["alpha"]["schema"].update(description="rewritten"), path)
        assert _lines_for(_check(registry, path), "alpha") == ['schema: description: fixture "Alpha.", juniper-data "rewritten"']


class TestEquality:
    """No difference means a pass -- including the representational ones JSON does not count."""

    @pytest.mark.parametrize("path", drift.discover_fixtures(), ids=lambda path: path.name)
    def test_a_registry_serving_a_committed_snapshot_is_no_drift(self, path):
        data = _fixture_data(path)
        result = _check(_serving(data), path)
        assert result.drifted == []
        assert result.compared == len(data["generators"])
        assert result.lines[-1] == f"no drift: {len(data['generators'])} generators in 1 fixture(s) match juniper-data 9.9.9"

    def test_main_exits_0_over_the_committed_snapshots(self, monkeypatch, capsys):
        registry: dict = {}
        for path in drift.discover_fixtures():
            registry.update(_serving(_fixture_data(path)))
        assert _main(monkeypatch, registry, []) == 0
        assert "no drift:" in capsys.readouterr().out

    def test_key_order_and_int_versus_float_are_not_drift(self, tmp_path):
        path = _synthetic(tmp_path)

        def mutate(generators):
            properties = generators["alpha"]["schema"]["properties"]
            properties["n_steps"] = dict(reversed(list(properties["n_steps"].items())))
            properties["n_steps"]["default"] = 2000.0

        assert _check(_upstream(mutate, path), path).drifted == []


class TestJsonEquality:
    @pytest.mark.parametrize(
        ("a", "b", "equal"),
        [
            pytest.param({"a": 1, "b": [1, 2]}, {"b": [1, 2], "a": 1}, True, id="key-order-ignored"),
            pytest.param(1, 1.0, True, id="int-equals-float"),
            pytest.param(True, 1, False, id="true-is-not-one"),
            pytest.param(False, 0, False, id="false-is-not-zero"),
            pytest.param(True, True, True, id="true-is-true"),
            pytest.param([1, 2], [2, 1], False, id="array-order-counts"),
            pytest.param([1, 2], [1, 2, 3], False, id="array-length-counts"),
            pytest.param(None, None, True, id="null-is-null"),
            pytest.param(None, 0, False, id="null-is-not-zero"),
            pytest.param("1", 1, False, id="string-is-not-number"),
            pytest.param(float("nan"), float("nan"), True, id="nan-is-nan"),
        ],
    )
    def test_json_equal(self, a, b, equal):
        assert drift.json_equal(a, b) is equal
        assert drift.json_equal(b, a) is equal


class TestARealPydanticModel:
    """The registry's params classes are pydantic models; the comparison must hold for a real ``model_json_schema()``."""

    @staticmethod
    def _model(default: int, *, with_jitter: bool):
        fields = {"n_steps": (int, pydantic.Field(default, ge=8, description="Length T of the raw series.")), "scaling": (str, "identity")}
        if with_jitter:
            fields["jitter"] = (float, 0.5)
        return pydantic.create_model("ToyParams", **fields)

    def test_a_real_model_round_trips_and_a_real_change_is_caught(self, tmp_path):
        before = self._model(2000, with_jitter=False)
        path = _snapshot(tmp_path / "juniper_data_toy_generator_schemas.json", [{"name": "toy", "version": "1.0.0", "schema": before.model_json_schema()}])
        assert _check({"toy": {"params_class": before, "version": "1.0.0"}}, path).drifted == []
        after = self._model(4000, with_jitter=True)
        assert _lines_for(_check({"toy": {"params_class": after, "version": "1.0.0"}}, path), "toy") == ['field "n_steps": default: fixture 2000, juniper-data 4000', 'field "jitter": added upstream (default 0.5)']


class TestTheCommittedFixtures:
    """Which snapshots are compared, and that the command the report gives can actually run."""

    def test_discovery_finds_the_sequence_capture(self):
        assert SEQUENCE_FIXTURE in drift.discover_fixtures()

    def test_every_juniper_data_snapshot_in_the_fixtures_directory_is_named_by_the_glob(self):
        """A sibling snapshot named outside the glob would be skipped by the check AND by the workflow's path filter."""
        snapshots = []
        for path in sorted(FIXTURES.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if isinstance(data, dict) and isinstance(data.get("_provenance"), dict) and data["_provenance"].get("source") == "juniper-data":
                snapshots.append(path)
        assert SEQUENCE_FIXTURE in snapshots, "the provenance scan found no snapshot at all -- the check below would pass vacuously"
        missed = sorted(path.name for path in snapshots if path not in drift.discover_fixtures())
        assert not missed, f"{missed} carry a juniper-data _provenance block but are not named {drift.FIXTURE_GLOB}: rename them, or widen FIXTURE_GLOB and the workflow's paths filter together"

    @pytest.mark.parametrize("path", drift.discover_fixtures(), ids=lambda path: path.name)
    def test_every_committed_snapshot_is_well_formed(self, path):
        fixture = drift.load_fixture(path)
        assert fixture.entries
        assert (REPO / fixture.tool).is_file(), f"{path.name} names a capture tool that is not in the repository: {fixture.tool}"

    @pytest.mark.parametrize("path", drift.discover_fixtures(), ids=lambda path: path.name)
    def test_each_snapshot_s_capture_tool_takes_the_flags_the_recapture_command_passes(self, path):
        """The printed command must run: every flag it passes exists, and no required flag is left out."""
        fixture = drift.load_fixture(path)
        tool = REPO / fixture.tool
        flags, required = _argparse_flags(tool)
        assert flags, f"no add_argument calls found in {fixture.tool} -- the check below would pass vacuously"
        passed = {token for token in drift.recapture_command(fixture, _juniper({}, "0.17.2")).split() if token.startswith("--")}
        assert passed <= flags, f"the re-capture command for {path.name} passes {sorted(passed - flags)}, which {fixture.tool} does not accept; change the tool or recapture_command() to match"
        assert required <= passed, f"{fixture.tool} requires {sorted(required - passed)}, which the re-capture command for {path.name} omits; change the tool or recapture_command() to match"

    def test_a_wheel_captured_snapshot_gets_the_published_wheel_recipe(self, tmp_path, monkeypatch, capsys):
        """A snapshot whose provenance records a wheel is re-captured from that release's wheel, in a venv, as its tool documents."""
        path = _snapshot(tmp_path / "juniper_data_tabular_generator_schemas.json", copy.deepcopy(SYNTHETIC), tool="util/ad-hoc/2026-10-26_capture_published_generator_schemas.py")
        data = _fixture_data(path)
        data["_provenance"].update(distribution="juniper-data", version="0.17.1", wheel="juniper_data-0.17.1-py3-none-any.whl")
        path.write_text(json.dumps(data), encoding="utf-8")
        assert drift.load_fixture(path).from_wheel is True
        assert drift.load_fixture(SEQUENCE_FIXTURE).from_wheel is False

        assert _main(monkeypatch, _upstream(lambda generators: generators["beta"].update(version="3.0.0"), path), ["--fixture", str(path)], version="0.17.2") == 1
        lines = capsys.readouterr().out.splitlines()
        where = drift.display_path(path)
        wheel = "tmp/jd-wheel/wheel/juniper_data-0.17.2-py3-none-any.whl"
        expected = [
            f"To re-capture {where} from the published juniper-data 0.17.2 wheel, run from the canopy repo root, with ../juniper-data a juniper-data checkout:",
            "  git -C ../juniper-data fetch --tags origin",
            "  python3 -m venv tmp/jd-wheel/venv",
            "  tmp/jd-wheel/venv/bin/pip download --no-deps --only-binary=:all: juniper-data==0.17.2 -d tmp/jd-wheel/wheel",
            f'  tmp/jd-wheel/venv/bin/pip install "$PWD/{wheel}[api]"',
            f"  tmp/jd-wheel/venv/bin/python -I util/ad-hoc/2026-10-26_capture_published_generator_schemas.py --wheel {wheel} --juniper-data-src ../juniper-data --generators alpha beta --fixture {where}",
        ]
        start = lines.index(expected[0])
        assert lines[start : start + len(expected)] == expected

    def test_a_sibling_snapshot_is_compared_and_its_generator_looked_up_by_name(self, tmp_path, monkeypatch, capsys):
        """Flat ``equities`` is not a sequence generator: it is found in the same registry by its name."""
        # Without any flat-equities entry the committed capture may grow, so the sibling below is the only one.
        sequence = [entry for entry in _fixture_data()["generators"] if entry["name"] != "equities"]
        _snapshot(tmp_path / SEQUENCE_FIXTURE.name, sequence)
        equities_schema = {"properties": {"symbols": {"default": None, "title": "Symbols"}}, "title": "EquitiesParams", "type": "object"}
        _snapshot(tmp_path / "juniper_data_equities_generator_schemas.json", [{"name": "equities", "version": "5.0.0", "schema": equities_schema}])
        _snapshot(tmp_path / "unrelated_capture.json", [{"name": "spiral", "version": "1.0.0", "schema": {"properties": {}}}])
        monkeypatch.setattr(drift, "FIXTURES_DIR", tmp_path)
        assert [path.name for path in drift.discover_fixtures()] == ["juniper_data_equities_generator_schemas.json", SEQUENCE_FIXTURE.name]

        registry = _serving({"generators": sequence})
        registry["equities"] = {"params_class": FakeParams(equities_schema), "version": "5.0.0"}
        assert _main(monkeypatch, registry, []) == 0
        assert f"no drift: {len(sequence) + 1} generators in 2 fixture(s)" in capsys.readouterr().out

        registry["equities"] = {"params_class": FakeParams(equities_schema), "version": "6.0.0"}
        assert _main(monkeypatch, registry, []) == 1
        out = capsys.readouterr().out
        assert f"DRIFT: 1 of {len(sequence) + 1} generators differ from juniper-data 9.9.9: equities" in out
        # display_path, not the raw path: with TMPDIR at a checkout's tmp/ (the house convention), tmp_path is inside the repo
        assert f"--fixture {drift.display_path(tmp_path / 'juniper_data_equities_generator_schemas.json')}" in out
        assert f"--fixture {drift.display_path(tmp_path / SEQUENCE_FIXTURE.name)}" not in out


class TestRefusals:
    """A check that could not run exits 2 -- never 0, and never 1 (drift)."""

    def test_no_snapshot_at_all_is_a_refusal(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(drift, "FIXTURES_DIR", tmp_path)
        assert _main(monkeypatch, {}, []) == 2
        assert drift.FIXTURE_GLOB in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("text", "complaint"),
        [
            pytest.param("{not json", "cannot be read as JSON", id="not-json"),
            pytest.param("[]", "is not a JSON object", id="not-an-object"),
            pytest.param(json.dumps({"generators": [{"name": "x", "version": "1", "schema": {}}]}), "no _provenance block", id="no-provenance"),
            pytest.param(json.dumps({"_provenance": {"source": "elsewhere", "tool": "t.py"}, "generators": [{"name": "x", "version": "1", "schema": {}}]}), "no _provenance block", id="not-juniper-data"),
            pytest.param(json.dumps({"_provenance": {"source": "juniper-data"}, "generators": [{"name": "x", "version": "1", "schema": {}}]}), "names no capture tool", id="no-tool"),
            pytest.param(json.dumps({"_provenance": {"source": "juniper-data", "tool": "t.py"}, "generators": []}), "lists no generators", id="empty"),
            pytest.param(json.dumps({"_provenance": {"source": "juniper-data", "tool": "t.py"}, "generators": [{"name": "x", "version": "1"}]}), "generators[0] is not a {name, version, schema} entry", id="no-schema"),
        ],
    )
    def test_a_malformed_snapshot_is_refused(self, tmp_path, monkeypatch, capsys, text, complaint):
        path = tmp_path / "juniper_data_bad_generator_schemas.json"
        path.write_text(text, encoding="utf-8")
        with pytest.raises(drift.CheckError, match=re.escape(complaint)):
            drift.load_fixture(path)
        assert _main(monkeypatch, {}, ["--fixture", str(path)]) == 2
        assert complaint in capsys.readouterr().err

    def test_a_registry_entry_of_another_shape_is_refused(self, tmp_path, monkeypatch, capsys):
        path = _synthetic(tmp_path)
        registry = _serving(_fixture_data(path))
        registry["beta"] = {"version": "2.0.0"}
        assert _main(monkeypatch, registry, ["--fixture", str(path)]) == 2
        assert "GENERATOR_REGISTRY['beta'] no longer offers params_class.model_json_schema() and version" in capsys.readouterr().err

    def test_an_unexpected_error_is_could_not_run_not_drift(self, tmp_path, monkeypatch, capsys):
        class Exploding:
            @staticmethod
            def model_json_schema():
                raise RuntimeError("boom")

        path = _synthetic(tmp_path)
        registry = _serving(_fixture_data(path))
        registry["beta"] = {"params_class": Exploding, "version": "2.0.0"}
        assert _main(monkeypatch, registry, ["--fixture", str(path)]) == 2
        assert "RuntimeError: boom" in capsys.readouterr().err

    def test_an_expected_version_cannot_be_combined_with_a_checkout(self, tmp_path):
        with pytest.raises(SystemExit) as raised:
            drift.main(["--juniper-data-src", str(tmp_path), "--expected-version", "0.17.1"])
        assert raised.value.code == 2


class TestGitHubActionsOutput:
    def test_each_drifted_generator_is_annotated_and_the_report_lands_in_the_job_summary(self, tmp_path, monkeypatch, capsys):
        summary = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

        entries = _fixture_data()["generators"]
        target, change_default, _expected = _injection("a-default-changed")
        changed = _defaulted_fields(_target())[-1]
        other = next(entry["name"] for entry in entries if entry["name"] != target)

        def mutate(generators):
            change_default(generators)
            generators[other]["version"] = "99.0.0"

        assert _main(monkeypatch, _upstream(mutate), ["--fixture", str(SEQUENCE_FIXTURE)]) == 1
        annotations = {line.split("::")[1]: line for line in capsys.readouterr().out.splitlines() if line.startswith("::")}
        titles = [f"error title=juniper-data schema drift%3A {entry['name']}" for entry in entries if entry["name"] in (target, other)]
        assert list(annotations) == titles
        target_line = annotations[f"error title=juniper-data schema drift%3A {target}"]
        assert f"{changed}.default changed" in target_line and "Re-capture: /opt/miniforge3/envs/JuniperData/bin/python -I " in target_line
        assert "version " in annotations[f"error title=juniper-data schema drift%3A {other}"]
        text = summary.read_text(encoding="utf-8")
        assert text.startswith("### juniper-data generator-schema drift") and f"DRIFT: 2 of {len(entries)} generators" in text

    def test_no_drift_is_a_notice(self, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        count = len(_fixture_data()["generators"])
        assert _main(monkeypatch, _serving(_fixture_data()), ["--fixture", str(SEQUENCE_FIXTURE)]) == 0
        assert f"::notice title=juniper-data schema drift::no drift: {count} generators in 1 fixture(s) match juniper-data 9.9.9" in capsys.readouterr().out

    def test_a_refusal_is_an_error_annotation(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setattr(drift, "FIXTURES_DIR", tmp_path)
        assert _main(monkeypatch, {}, []) == 2
        assert capsys.readouterr().out.startswith("::error title=juniper-data schema drift check could not run::no ")

    def test_an_unwritable_job_summary_does_not_change_the_verdict(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "no-such-directory" / "summary.md"))
        assert _main(monkeypatch, _serving(_fixture_data()), ["--fixture", str(SEQUENCE_FIXTURE)]) == 0
        assert "could not append to the job summary" in capsys.readouterr().err

    def test_annotation_text_is_escaped(self, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert drift.annotation("error", "a: b, c", "50%\nnext") == "::error title=a%3A b%2C c::50%25%0Anext"

    def test_nothing_is_annotated_outside_github_actions(self):
        assert drift.annotation("error", "title", "message") is None


# --------------------------------------------------------------------------------- the two import modes, for real

REGISTRY_SOURCE = '''
class ToyParams:
    """Enough of a pydantic model for the check: model_json_schema()."""

    SCHEMA = {schema!r}

    @classmethod
    def model_json_schema(cls):
        return dict(cls.SCHEMA)


GENERATOR_REGISTRY = {{"toy": {{"params_class": ToyParams, "version": "1.0.0"}}}}
'''
TOY_SCHEMA = {"properties": {"n_steps": {"default": 2000, "minimum": 8, "title": "N Steps", "type": "integer"}}, "title": "ToyParams", "type": "object"}


def _toy_snapshot(tmp_path: Path) -> Path:
    return _snapshot(tmp_path / "juniper_data_toy_generator_schemas.json", [{"name": "toy", "version": "1.0.0", "schema": TOY_SCHEMA}])


def _juniper_data_tree(root: Path, schema: dict | None = None, registry_source: str | None = None) -> Path:
    """A minimal ``juniper_data`` package under ``root`` whose registry serves one toy generator."""
    routes = root / "juniper_data" / "api" / "routes"
    routes.mkdir(parents=True)
    for package in (root / "juniper_data", root / "juniper_data" / "api", routes):
        (package / "__init__.py").write_text("", encoding="utf-8")
    source = REGISTRY_SOURCE.format(schema=TOY_SCHEMA if schema is None else schema) if registry_source is None else registry_source
    (routes / "generators.py").write_text(source, encoding="utf-8")
    return root


def _installed(site: Path, version: str) -> Path:
    """``site`` as a site-packages holding juniper-data ``version``: the package plus its dist-info."""
    _juniper_data_tree(site)
    info = site / f"juniper_data-{version}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: juniper-data\nVersion: {version}\n", encoding="utf-8")
    return site


def _run(args: list[str], pythonpath: list[Path] | None = None) -> subprocess.CompletedProcess:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GITHUB_") and key != "PYTHONPATH"}
    env["PYTHONNOUSERSITE"] = "1"
    if pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(str(path) for path in pythonpath)
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60, check=False)


class TestTheInstalledRelease:
    """Installed mode: the version reported is proved to be the package compared."""

    def test_the_expected_release_is_compared(self, tmp_path):
        site = _installed(tmp_path / "site", "9.9.9")
        run = _run(["--fixture", str(_toy_snapshot(tmp_path)), "--expected-version", "9.9.9"], [site])
        assert run.returncode == 0, run.stderr
        assert f"juniper-data 9.9.9 (installed, {(site / 'juniper_data').resolve()})" in run.stdout
        assert "no drift: 1 generators in 1 fixture(s) match juniper-data 9.9.9" in run.stdout

    def test_any_other_version_is_refused(self, tmp_path):
        run = _run(["--fixture", str(_toy_snapshot(tmp_path)), "--expected-version", "9.9.8"], [_installed(tmp_path / "site", "9.9.9")])
        assert run.returncode == 2
        assert "expected juniper-data 9.9.8, but 9.9.9 is installed" in run.stderr

    def test_a_copy_shadowing_the_installed_release_is_refused(self, tmp_path):
        """What the canopy and JuniperData envs both showed: metadata naming one version while another tree answers."""
        shadow = _juniper_data_tree(tmp_path / "shadow")
        site = _installed(tmp_path / "site", "9.9.9")
        run = _run(["--fixture", str(_toy_snapshot(tmp_path))], [shadow, site])
        assert run.returncode == 2
        assert f"ships juniper_data at {(site / 'juniper_data').resolve()}, but it was imported from {(shadow / 'juniper_data').resolve()}" in run.stderr


class TestACheckout:
    """``--juniper-data-src``: the checkout is what is imported, and what the re-capture command names."""

    def test_a_checkout_is_compared_and_named(self, tmp_path):
        checkout = _juniper_data_tree(tmp_path / "juniper-data")
        (checkout / "pyproject.toml").write_text('[project]\nname = "juniper-data"\nversion = "9.8.7"\n', encoding="utf-8")
        run = _run(["--fixture", str(_toy_snapshot(tmp_path)), "--juniper-data-src", str(checkout)])
        assert run.returncode == 0, run.stderr
        assert f"juniper-data 9.8.7 (the checkout {checkout.resolve()})" in run.stdout

    def test_drift_in_a_checkout_exits_1_with_that_checkout_in_the_command(self, tmp_path):
        changed = copy.deepcopy(TOY_SCHEMA)
        changed["properties"]["n_steps"]["default"] = 4000
        checkout = _juniper_data_tree(tmp_path / "juniper-data", schema=changed)
        snapshot = _toy_snapshot(tmp_path)
        run = _run(["--fixture", str(snapshot), "--juniper-data-src", str(checkout)])
        assert run.returncode == 1, run.stderr
        assert 'field "n_steps": default: fixture 2000, juniper-data 4000' in run.stdout
        assert f"--juniper-data-src {checkout.resolve()} --fixture {drift.display_path(snapshot)}" in run.stdout
        assert "git -C" not in run.stdout

    def test_a_package_imported_from_elsewhere_is_not_reported_as_the_checkout(self, tmp_path, monkeypatch):
        """An already-imported juniper_data wins over the path the checkout is inserted at: the check must notice."""
        elsewhere = _juniper_data_tree(tmp_path / "elsewhere")
        checkout = _juniper_data_tree(tmp_path / "juniper-data")
        package = types.ModuleType("juniper_data")
        package.__file__ = str(elsewhere / "juniper_data" / "__init__.py")
        routes = types.ModuleType(drift.REGISTRY_MODULE)
        routes.GENERATOR_REGISTRY = {"toy": {"params_class": FakeParams(TOY_SCHEMA), "version": "1.0.0"}}
        monkeypatch.setitem(sys.modules, "juniper_data", package)
        monkeypatch.setitem(sys.modules, drift.REGISTRY_MODULE, routes)
        monkeypatch.setattr(sys, "path", list(sys.path))  # load_juniper_data inserts the checkout; undo it after
        with pytest.raises(drift.CheckError, match="not from the checkout"):
            drift.load_juniper_data(checkout)

    def test_a_directory_that_is_not_a_checkout_is_refused(self, tmp_path):
        run = _run(["--fixture", str(_toy_snapshot(tmp_path)), "--juniper-data-src", str(tmp_path)])
        assert run.returncode == 2
        assert "is not a juniper-data checkout" in run.stderr

    def test_a_registry_that_cannot_be_imported_names_the_api_extra(self, tmp_path):
        checkout = _juniper_data_tree(tmp_path / "juniper-data", registry_source="import pydantic_settings_is_not_installed_here\n")
        run = _run(["--fixture", str(_toy_snapshot(tmp_path)), "--juniper-data-src", str(checkout)])
        assert run.returncode == 2
        assert "pip install 'juniper-data[api]==X.Y.Z'" in run.stderr

    def test_a_registry_module_without_the_registry_is_refused(self, tmp_path):
        checkout = _juniper_data_tree(tmp_path / "juniper-data", registry_source="REGISTRY = {}\n")
        run = _run(["--fixture", str(_toy_snapshot(tmp_path)), "--juniper-data-src", str(checkout)])
        assert run.returncode == 2
        assert "has no non-empty GENERATOR_REGISTRY dict" in run.stderr


# ------------------------------------------------------------------------------------------------ the workflow


def _workflow() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    data["on"] = data.pop(True, data.get("on"))  # PyYAML (YAML 1.1) reads the bare `on:` key as True
    return data


def _steps() -> list[dict]:
    return [step for job in _workflow()["jobs"].values() for step in job.get("steps", [])]


def _commands() -> list[str]:
    """Each step's ``run:`` text without its whole-line comments: a comment naming a command is not running it."""
    return ["\n".join(line for line in str(step.get("run", "")).splitlines() if not line.lstrip().startswith("#")) for step in _steps() if "run" in step]


class TestTheWorkflow:
    def test_it_listens_for_juniper_data_s_release_dispatch(self):
        assert _workflow()["on"]["repository_dispatch"]["types"] == ["juniper-data-published"]

    def test_it_sets_no_run_name(self):
        """juniper-data's notify-consumers confirms delivery by finding a run whose title is the event type: the default title."""
        assert "run-name" not in _workflow()

    def test_it_is_scheduled_and_can_be_dispatched_for_a_version(self):
        on = _workflow()["on"]
        assert [entry["cron"] for entry in on["schedule"]], "no cron entry"
        assert "version" in on["workflow_dispatch"]["inputs"]

    def test_pull_requests_run_it_for_the_workflow_the_script_and_every_snapshot(self):
        paths = _workflow()["on"]["pull_request"]["paths"]
        assert sorted(paths) == sorted([WORKFLOW_REL, SCRIPT_REL, f"src/tests/fixtures/{drift.FIXTURE_GLOB}"])
        for snapshot in drift.discover_fixtures():
            assert any(fnmatch.fnmatch(snapshot.relative_to(REPO).as_posix(), pattern) for pattern in paths), snapshot.name

    def test_every_action_is_pinned_by_a_full_commit_sha(self):
        uses = [step["uses"] for step in _steps() if "uses" in step]
        assert uses, "no actions found -- the pin check would pass vacuously"
        assert [ref for ref in uses if not SHA_PINNED.match(ref)] == []

    def test_its_token_can_only_read(self):
        assert _workflow()["permissions"] == {"contents": "read"}

    def test_it_installs_the_api_extra_at_the_chosen_version(self):
        assert any('pip install "juniper-data[api]==${VERSION}"' in command for command in _commands())

    def test_it_runs_the_script_isolated_and_held_to_that_version(self):
        assert any(f'python -I {SCRIPT_REL} --expected-version "${{VERSION}}"' in command for command in _commands())

    def test_event_data_reaches_the_shell_only_through_env(self):
        """An expression inside ``run:`` is spliced into the script before bash parses it: a payload could inject commands."""
        assert [command for command in _commands() if "${{" in command] == []
