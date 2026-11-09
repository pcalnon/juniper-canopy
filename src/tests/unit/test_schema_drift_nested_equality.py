#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_schema_drift_nested_equality.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-11-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   JSON equality inside arrays for the juniper-data
#                schema-drift check (juniper-canopy#737).
#####################################################################
"""``json_equal`` holds inside arrays, which ``diff_json`` does not walk (juniper-canopy#737).

The scalar tests say ``true`` is not ``1`` and ``NaN`` equals ``NaN``. Python's ``==`` says the opposite
once either value sits in a list: ``[0] == [False]`` and ``[float("nan")] != [float("nan")]``. An ``enum``
or an ``anyOf`` is a list, and the committed snapshots carry both, so that is the comparison the drift
report actually makes. These tests fail if the list branch stops recursing, and the scalar tests would
not.

The ``NaN`` half holds for two separate objects only. ``json`` parses every ``NaN`` to one shared float,
which list equality matches by identity, so the drift report's own ``NaN`` case pins ``json_equal``'s
``NaN`` rule, but cannot catch a list branch that compares whole arrays with ``==``.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "util" / "check_juniper_data_generator_schemas.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_juniper_data_generator_schemas_nested", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


drift = _load()


class _FakeParams:
    """``model_json_schema()`` returns a copy, as a pydantic params class does."""

    def __init__(self, schema: dict):
        self._schema = copy.deepcopy(schema)

    def model_json_schema(self) -> dict:
        return copy.deepcopy(self._schema)


def _schema() -> dict:
    """The array shapes the committed snapshots use: an ``enum``, an ``anyOf``, and a nested number."""
    return {
        "type": "object",
        "title": "ToyParams",
        "properties": {
            "flag": {"default": 0, "enum": [0, 1], "title": "Flag", "type": "integer"},
            "n_samples": {
                "anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}],
                "default": None,
                "title": "N Samples",
            },
            "width": {"default": [1], "title": "Width", "type": "array"},
            "samples": {"default": [float("nan")], "title": "Samples", "type": "array"},
        },
    }


def _snapshot(path: Path, schema: dict) -> Path:
    provenance = {
        "source": "juniper-data",
        "commit": "0" * 40,
        "dirty": False,
        "captured": "2026-11-08",
        "what": "nested JSON equality",
        "tool": "util/ad-hoc/2026-10-26_capture_published_generator_schemas.py",
    }
    path.write_text(json.dumps({"_provenance": provenance, "generators": [{"name": "toy", "version": "1.0.0", "schema": schema}]}), encoding="utf-8")
    return path


def _check(path: Path, schema: dict):
    registry = {"toy": {"params_class": _FakeParams(schema), "version": "1.0.0"}}
    juniper = drift.JuniperData(registry, "9.9.9", Path("site-packages") / "juniper_data", None)
    return drift.check([drift.load_fixture(path)], juniper)


def _lines(result) -> list[str]:
    found = [differences for _fixture, entry, differences in result.drifted if entry.name == "toy"]
    assert found, "\n".join(result.lines)
    [differences] = found
    return [drift.describe(difference) for difference in differences]


class TestJsonEqualInsideContainers:
    """The scalar rule, applied where ``==`` and JSON disagree once a value is inside a container."""

    @pytest.mark.parametrize(
        ("left", "right", "equal"),
        [
            pytest.param([0, 1], [False, True], False, id="enum-of-ints-is-not-bools"),
            pytest.param([False], [0], False, id="false-inside-an-array-is-not-zero"),
            pytest.param([1], [1.0], True, id="int-inside-an-array-equals-float"),
            pytest.param([{"minimum": 1, "type": "integer"}], [{"type": "integer", "minimum": True}], False, id="minimum-inside-anyof-is-not-true"),
            pytest.param([{"b": 1, "a": 2}], [{"a": 2.0, "b": 1}], True, id="object-key-order-inside-an-array"),
            pytest.param({"enum": [True]}, {"enum": [1]}, False, id="true-inside-an-object-array"),
            pytest.param([float("nan")], [float("nan")], True, id="nan-inside-an-array"),
            pytest.param([float("nan"), 1], [float("nan"), True], False, id="nan-does-not-excuse-a-nested-bool"),
        ],
    )
    def test_json_equal_recurses(self, left, right, equal):
        assert drift.json_equal(left, right) is equal
        assert drift.json_equal(right, left) is equal

    def test_python_equality_would_hide_the_boolean_and_split_two_nans(self):
        # The assertions above are the contract. These are why the scalar tests cannot stand in for them.
        # The NaN one needs two objects: json's parser returns one shared NaN, which list equality matches.
        assert [0, 1] == [False, True]
        assert [{"minimum": 1}] == [{"minimum": True}]
        assert [float("nan")] != [float("nan")]


class TestTheDriftReport:
    """``diff_json`` must not compare an array with ``==`` before asking ``json_equal``."""

    def test_an_enum_flipped_from_ints_to_bools_is_named(self, tmp_path: Path):
        schema = _schema()
        path = _snapshot(tmp_path / "juniper_data_toy_generator_schemas.json", schema)
        upstream = copy.deepcopy(schema)
        upstream["properties"]["flag"]["enum"] = [False, True]
        result = _check(path, upstream)
        assert [entry.name for _fixture, entry, _diffs in result.drifted] == ["toy"]
        assert _lines(result) == ['field "flag": enum: fixture [0, 1], juniper-data [false, true]']

    def test_an_anyof_minimum_flipped_from_one_to_true_is_named(self, tmp_path: Path):
        schema = _schema()
        path = _snapshot(tmp_path / "juniper_data_toy_generator_schemas.json", schema)
        upstream = copy.deepcopy(schema)
        upstream["properties"]["n_samples"]["anyOf"][0]["minimum"] = True
        result = _check(path, upstream)
        expected = 'field "n_samples": anyOf: fixture [{"minimum": 1, "type": "integer"}, {"type": "null"}], juniper-data [{"minimum": true, "type": "integer"}, {"type": "null"}]'
        assert _lines(result) == [expected]

    def test_an_int_and_a_float_inside_an_array_are_not_drift(self, tmp_path: Path):
        schema = _schema()
        path = _snapshot(tmp_path / "juniper_data_toy_generator_schemas.json", schema)
        upstream = copy.deepcopy(schema)
        upstream["properties"]["width"]["default"] = [1.0]
        assert _check(path, upstream).drifted == []

    def test_nan_inside_an_array_is_not_drift(self, tmp_path: Path):
        schema = _schema()
        path = _snapshot(tmp_path / "juniper_data_toy_generator_schemas.json", schema)
        assert _check(path, copy.deepcopy(schema)).drifted == []
