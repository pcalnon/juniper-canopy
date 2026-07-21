"""N7 (canopy training-runtime defects plan, I-7 / I-5-UX) — dataset_schema pure core.

Unit tests for the schema-driven dataset-panel helpers: JSON-Schema -> renderable field
descriptors (infrastructure fields excluded, bounds/enum/type preserved), the per-generator
availability map with the flag-absent-means-available fallback, the canopy-value -> generator-name
alias, and the availability-gate composition over model-compat option lists. Pure module — no Dash,
no HTTP — so these are the primary N7 gate for the schema->UI mapping and the availability posture.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from dataset_schema import (
    INFRASTRUCTURE_FIELDS,
    GeneratorField,
    apply_availability_gate,
    availability_map,
    generator_name_for_type,
    humanize,
    is_generator_available,
    parse_schema_fields,
    unavailable_reason,
)

# Representative real-shaped schemas (Pydantic model_json_schema output), trimmed to the fields the
# parser must handle: integer/number with inclusive+exclusive bounds, boolean, string+enum, Optional
# (anyOf null branch), and the infrastructure fields that must be dropped.
MNIST_SCHEMA = {
    "properties": {
        "dataset": {"type": "string", "enum": ["mnist", "fashion_mnist"], "default": "mnist", "title": "Dataset"},
        "n_samples": {"anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}], "default": None, "title": "N Samples"},
        "flatten": {"type": "boolean", "default": True, "title": "Flatten"},
        "seed": {"anyOf": [{"minimum": 0, "type": "integer"}, {"type": "null"}], "default": None, "title": "Seed"},
        "train_ratio": {"type": "number", "maximum": 1, "exclusiveMinimum": 0, "default": 0.8, "title": "Train Ratio"},
        "test_ratio": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.2, "title": "Test Ratio"},
        "shuffle": {"type": "boolean", "default": True, "title": "Shuffle"},
    }
}

EQUITIES_SCHEMA = {
    "properties": {
        "symbols": {"anyOf": [{"items": {"type": "string"}, "type": "array"}, {"type": "null"}], "default": None, "title": "Symbols"},
        "regression_target": {"type": "string", "enum": ["next_close", "return", "log_return"], "default": "next_close", "title": "Regression Target"},
        "week52_window": {"type": "integer", "minimum": 2, "maximum": 2520, "default": 252, "title": "Week52 Window"},
        "normalize_features": {"type": "boolean", "default": False, "title": "Normalize Features"},
        "max_symbols": {"anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}], "default": None, "title": "Max Symbols"},
        "seed": {"anyOf": [{"minimum": 0, "type": "integer"}, {"type": "null"}], "default": None, "title": "Seed"},
    }
}


# ---------------------------------------------------------------------------
# parse_schema_fields
# ---------------------------------------------------------------------------


def test_parse_excludes_infrastructure_fields_and_preserves_order():
    fields = parse_schema_fields(MNIST_SCHEMA)
    names = [f.name for f in fields]
    # seed / train_ratio / test_ratio / shuffle are infra -> dropped; declaration order preserved.
    assert names == ["dataset", "n_samples", "flatten"]
    assert INFRASTRUCTURE_FIELDS.isdisjoint(names)


def test_parse_maps_types_bounds_defaults_and_enums():
    by_name = {f.name: f for f in parse_schema_fields(MNIST_SCHEMA)}
    assert by_name["dataset"].input_type == "select"
    assert by_name["dataset"].options == ("mnist", "fashion_mnist")
    assert by_name["dataset"].default == "mnist"
    assert by_name["n_samples"].input_type == "number"
    assert by_name["n_samples"].minimum == 1  # bound read from inside the anyOf non-null branch
    assert by_name["n_samples"].step == 1  # integer -> step 1
    assert by_name["flatten"].input_type == "checkbox"
    assert by_name["flatten"].default is True


def test_parse_reads_exclusive_bounds_and_skips_arrays():
    fields = parse_schema_fields(EQUITIES_SCHEMA)
    by_name = {f.name: f for f in fields}
    # symbols is an array (anyOf array|null) -> not renderable, skipped; seed is infra -> skipped.
    assert "symbols" not in by_name
    assert "seed" not in by_name
    assert by_name["regression_target"].input_type == "select"
    assert by_name["regression_target"].options == ("next_close", "return", "log_return")
    assert by_name["week52_window"].minimum == 2 and by_name["week52_window"].maximum == 2520
    assert by_name["normalize_features"].input_type == "checkbox" and by_name["normalize_features"].default is False
    # max_symbols: exclusive/inclusive minimum inside anyOf non-null branch.
    assert by_name["max_symbols"].input_type == "number" and by_name["max_symbols"].minimum == 1


def test_parse_empty_or_missing_properties_is_empty_list():
    assert parse_schema_fields(None) == []
    assert parse_schema_fields({}) == []
    assert parse_schema_fields({"properties": {}}) == []
    assert parse_schema_fields({"type": "object"}) == []  # no properties key


def test_parse_falls_back_to_humanized_label_without_title():
    schema = {"properties": {"n_arms": {"type": "integer", "default": 2}}}
    field = parse_schema_fields(schema)[0]
    assert field.label == "N Arms"


def test_humanize_snake_and_dash():
    assert humanize("n_samples") == "N Samples"
    assert humanize("max-symbols") == "Max Symbols"


# ---------------------------------------------------------------------------
# availability + alias
# ---------------------------------------------------------------------------


def test_generator_name_alias_maps_plurals_only():
    assert generator_name_for_type("spirals") == "spiral"
    assert generator_name_for_type("moons") == "moon"
    assert generator_name_for_type("mnist") == "mnist"  # identity
    assert generator_name_for_type("equities_seq") == "equities_seq"
    assert generator_name_for_type("") == ""
    assert generator_name_for_type(None) == ""


def test_availability_map_reads_flag_and_defaults_absent_to_true():
    gens = [{"name": "spiral", "available": True}, {"name": "mnist", "available": False}, {"name": "moon"}]
    amap = availability_map(gens)
    assert amap == {"spiral": True, "mnist": False, "moon": True}  # moon has no flag -> available


def test_is_generator_available_flag_absent_and_missing_generator_fallback_true():
    gens = [{"name": "spiral", "available": True}, {"name": "mnist", "available": False}]
    assert is_generator_available("spirals", gens) is True  # alias spirals->spiral, available
    assert is_generator_available("mnist", gens) is False
    assert is_generator_available("mnist", []) is True  # empty list (down/older service) -> available
    assert is_generator_available("mnist", None) is True  # no list at all -> available
    assert is_generator_available("circles", gens) is True  # not in list -> available (fail-open)


def test_unavailable_reason_is_reworded_ui_text():
    # Not the raw "Install with: pip install datasets" — a UI-friendly phrase.
    assert "install" not in unavailable_reason("mnist").lower() or "extra" in unavailable_reason("mnist").lower()
    assert unavailable_reason("mnist")  # non-empty
    assert unavailable_reason("some_other_gen")  # generic fallback non-empty


# ---------------------------------------------------------------------------
# apply_availability_gate
# ---------------------------------------------------------------------------


def test_availability_gate_disables_unavailable_and_preserves_model_gate():
    gens = [{"name": "spiral", "available": True}, {"name": "mnist", "available": False}]
    options = [
        {"label": "Spirals", "value": "spirals"},
        {"label": "MNIST", "value": "mnist"},
        {"label": "Equities (sequence) — needs 3-D data", "value": "equities_seq", "disabled": True},
    ]
    gated = apply_availability_gate(options, gens)
    by_value = {o["value"]: o for o in gated}
    # spiral available -> untouched (still enabled)
    assert not by_value["spirals"].get("disabled")
    assert by_value["spirals"]["label"] == "Spirals"
    # mnist unavailable -> disabled + reworded reason appended
    assert by_value["mnist"]["disabled"] is True
    assert by_value["mnist"]["label"].startswith("MNIST — ")
    # already-disabled (model-incompat) option left exactly as-is (no double reason)
    assert by_value["equities_seq"]["disabled"] is True
    assert by_value["equities_seq"]["label"] == "Equities (sequence) — needs 3-D data"


def test_availability_gate_all_available_when_flag_absent():
    # Flag-absent fallback: an older data service returns entries without `available`.
    gens = [{"name": "spiral"}, {"name": "mnist"}]
    options = [{"label": "Spirals", "value": "spirals"}, {"label": "MNIST", "value": "mnist"}]
    gated = apply_availability_gate(options, gens)
    assert all(not o.get("disabled") for o in gated)


def test_generator_field_is_frozen():
    field = GeneratorField(name="x", label="X", input_type="number")
    with pytest.raises(FrozenInstanceError):
        field.name = "y"  # frozen dataclass
