"""Unit tests for ``src/model_registry.py`` (model-selection A0).

Locks the behavior-preserving contract (the dataset-type dropdown options + default are
identical to the previously inlined list) and the registry shape / seeds.
"""

from __future__ import annotations

import dataclasses

import pytest

from model_registry import (
    DATASET_TYPES,
    DEFAULT_DATASET_TYPE,
    MODELS,
    DatasetTypeSpec,
    ModelSpec,
    dataset_type_options,
)

# The exact options list that was previously hardcoded inline in dashboard_manager.
_PREVIOUS_HARDCODED_OPTIONS = [
    {"label": "Spirals", "value": "spirals"},
    {"label": "XOR", "value": "xor"},
    {"label": "MNIST", "value": "mnist"},
    {"label": "Circles", "value": "circles"},
    {"label": "Moons", "value": "moons"},
]


def test_dataset_type_options_are_behavior_preserving():
    """dataset_type_options() must reproduce the previously inlined list exactly."""
    assert dataset_type_options() == _PREVIOUS_HARDCODED_OPTIONS


def test_default_dataset_type_preserved():
    assert DEFAULT_DATASET_TYPE == "spirals"
    assert DEFAULT_DATASET_TYPE in {spec.value for spec in DATASET_TYPES}


def test_dataset_values_are_unique():
    values = [spec.value for spec in DATASET_TYPES]
    assert len(values) == len(set(values))


def test_current_dataset_types_are_2d_classification():
    for spec in DATASET_TYPES:
        assert spec.ndim == 2
        assert spec.task_type == "classification"
        assert spec.temporal == "none"


def test_model_keys_are_unique():
    keys = [model.key for model in MODELS]
    assert len(keys) == len(set(keys))


def test_cascor_seed():
    cascor = next(model for model in MODELS if model.key == "cascor")
    assert cascor.is_live
    assert cascor.status == "live"
    assert cascor.category == "feedforward"
    assert cascor.input_ndim == frozenset({2})
    assert cascor.supported_task_types == frozenset({"classification", "regression"})


def test_recurrence_seed_is_coming_soon_and_3d():
    recurrence = next(model for model in MODELS if model.key == "recurrence")
    assert not recurrence.is_live
    assert recurrence.status == "coming_soon"
    assert recurrence.input_ndim == frozenset({3})
    assert recurrence.requires_dt is True
    assert recurrence.supported_task_types == frozenset({"regression"})


def test_specs_are_frozen():
    """Registry specs are immutable constants."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        DATASET_TYPES[0].value = "mutated"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        MODELS[0].status = "broken"  # type: ignore[misc]


def test_spec_types_are_constructible():
    """Sanity: the public dataclasses build with the documented required fields."""
    ds = DatasetTypeSpec(value="seq", label="Seq", task_type="regression", ndim=3, temporal="irregular")
    assert ds.ndim == 3 and ds.temporal == "irregular"
    model = ModelSpec(
        key="demo",
        label="Demo",
        category="ts_growth",
        input_ndim=frozenset({3}),
        supported_task_types=frozenset({"regression"}),
    )
    assert model.is_live  # default status="live"
    assert model.tags == frozenset()
