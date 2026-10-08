#!/usr/bin/env python
"""Falsy seeds and zero bounds the schema helpers must not drop.

``apply_seeded_defaults`` is what stops the params panel showing juniper-data's schema
default while the registry seed (the value that is actually sent) says something else.
The equities seed that forced the helper uses truthy values (``"drop"``, ``True``), so a
truthiness check in the overlay still passes that suite and silently keeps the schema
default whenever the seed is ``False``, ``0`` or ``None``.

``_bound`` is the same class of bug one level down: a minimum of ``0`` is a real bound
(noise, an exclusive floor of 0), and ``bool`` is an ``int``. The rendered schemas the
parser tests use start at 1 or 2, and the one ``exclusiveMinimum: 0`` sits on
``train_ratio``, which is excluded before ``_bound`` ever sees it.
"""

from __future__ import annotations

import pytest

from dataset_schema import GeneratorField, apply_seeded_defaults, dataset_type_for_generator_name, parse_schema_fields

pytestmark = pytest.mark.unit

_KNOWN = ("spirals", "moons", "xor")


def _fields():
    return [
        GeneratorField(name="normalize_features", label="Normalize Features", input_type="checkbox", default=True),
        GeneratorField(name="noise", label="Noise", input_type="number", default=0.1),
        GeneratorField(name="title", label="Title", input_type="text", default="schema"),
        GeneratorField(name="n_samples", label="N Samples", input_type="number", default=100),
    ]


class TestFalsySeedsOverlayTheSchemaDefault:
    def test_false_zero_and_none_replace_the_schema_default(self):
        fields = _fields()
        overlaid = apply_seeded_defaults(fields, {"normalize_features": False, "noise": 0, "title": None, "symbols": ["AAPL"]})
        assert [field.name for field in overlaid] == [field.name for field in fields]
        assert overlaid[0].default is False
        assert overlaid[1].default == 0
        assert overlaid[2].default is None
        # A key the form does not render (an array such as ``symbols``) does not become a control.
        assert overlaid[3].default == 100
        assert overlaid[3] is fields[3]
        # The overlay copies; the schema-derived field the panel still holds is unchanged.
        assert overlaid[0] is not fields[0]
        assert fields[0].default is True

    @pytest.mark.parametrize("seeded", [None, {}], ids=["none", "empty"])
    def test_no_seed_keeps_the_schema_fields(self, seeded):
        fields = _fields()
        copied = apply_seeded_defaults(fields, seeded)
        assert copied is not fields
        assert copied[0] is fields[0]
        assert copied[0].default is True


class TestAZeroBoundIsABound:
    def test_zero_inclusive_and_exclusive_bounds_survive(self):
        schema = {
            "properties": {
                "noise": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.0},
                "ratio": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1},
                # Inclusive wins, and it wins even when that inclusive value is the falsy 0.
                "offset": {"type": "integer", "minimum": 0, "exclusiveMinimum": 5, "default": 0},
                # ``True`` is an int. It is not a bound, so the exclusive floor is the one shown.
                "count": {"anyOf": [{"type": "integer", "minimum": True, "exclusiveMinimum": 2}, {"type": "null"}], "default": None},
                "bad": {"type": "integer", "minimum": "0"},
            }
        }
        by_name = {field.name: field for field in parse_schema_fields(schema, exclude=())}
        assert by_name["noise"].minimum == 0 and by_name["noise"].maximum == 1
        assert by_name["ratio"].minimum == 0 and by_name["ratio"].maximum == 1
        assert by_name["offset"].minimum == 0
        assert by_name["count"].minimum == 2
        assert by_name["bad"].minimum is None


class TestDatasetTypeForGeneratorName:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("spiral", "spirals"),
            ("moon", "moons"),
            ("spirals", "spirals"),
            ("xor", "xor"),
            ("arc_agi", None),
            ("", None),
            (None, None),
        ],
    )
    def test_the_alias_resolves_and_an_unknown_name_does_not(self, name, expected):
        assert dataset_type_for_generator_name(name, _KNOWN) == expected

    def test_identity_wins_when_the_generator_name_is_itself_a_dropdown_value(self):
        # Checked before the alias map. A backend that says ``spiral`` selects the
        # dropdown entry ``spiral`` when that entry exists, not ``spirals``.
        assert dataset_type_for_generator_name("spiral", ("spiral", "spirals")) == "spiral"

    def test_the_alias_does_not_fire_when_the_canopy_value_is_not_seeded(self):
        assert dataset_type_for_generator_name("spiral", ("xor",)) is None
