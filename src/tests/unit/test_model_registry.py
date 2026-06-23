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
    compatible,
    compatible_datasets,
    compatible_models,
    dataset_type_options,
    temporal_ok,
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


# Compatibility engine (A1-iv-1): the pure predicate + resolvers (design §4). These ARE the
# correctness guarantee (D5), so they carry the bulk of the browser-free (B0) coverage.
# Synthetic specs exercise the task_type / temporal axes that the all-2-D-classification seeds
# cannot reach on their own.

_SEQ_IRREGULAR = DatasetTypeSpec(value="seq_irr", label="Seq (irregular)", task_type="regression", ndim=3, temporal="irregular")
_SEQ_REGULAR = DatasetTypeSpec(value="seq_reg", label="Seq (regular)", task_type="regression", ndim=3, temporal="regular")
_TABULAR_REGRESSION = DatasetTypeSpec(value="tab_reg", label="Tabular (regression)", task_type="regression", ndim=2, temporal="none")

_DT_AWARE_3D = ModelSpec(key="dt3d", label="dt-aware 3-D", category="ts_established", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"}), requires_dt=True)
_PLAIN_3D = ModelSpec(key="plain3d", label="plain 3-D", category="ts_established", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"}), requires_dt=False)
_CLASSIFIER_2D = ModelSpec(key="clf2d", label="2-D classifier", category="feedforward", input_ndim=frozenset({2}), supported_task_types=frozenset({"classification"}))


def _model(key: str) -> ModelSpec:
    return next(model for model in MODELS if model.key == key)


def test_compatible_seeded_ndim_gate():
    """The ndim axis gates the two real seeds: spirals(2-D) ↔ cascor only."""
    spirals = next(spec for spec in DATASET_TYPES if spec.value == "spirals")
    assert compatible(spirals, _model("cascor")) is True
    assert compatible(spirals, _model("recurrence")) is False  # 2-D dataset, 3-D model


def test_temporal_ok_only_irregular_constrains():
    """Only irregular-Δt data requires a Δt-consuming model; regular/none never constrain."""
    assert temporal_ok(_SEQ_IRREGULAR, _DT_AWARE_3D) is True
    assert temporal_ok(_SEQ_IRREGULAR, _PLAIN_3D) is False
    assert temporal_ok(_SEQ_REGULAR, _PLAIN_3D) is True
    assert temporal_ok(_TABULAR_REGRESSION, _CLASSIFIER_2D) is True


def test_compatible_task_type_axis():
    """task_type is enforced even when ndim matches."""
    assert compatible(_TABULAR_REGRESSION, _model("cascor")) is True  # cascor supports regression
    assert compatible(_TABULAR_REGRESSION, _CLASSIFIER_2D) is False  # classification-only model


def test_compatible_temporal_axis_is_the_fine_discriminator():
    """Two same-ndim/same-task 3-D regressors are separated ONLY by the temporal clause."""
    assert compatible(_SEQ_IRREGULAR, _DT_AWARE_3D) is True
    assert compatible(_SEQ_IRREGULAR, _PLAIN_3D) is False  # ndim+task pass; temporal fails
    assert compatible(_SEQ_REGULAR, _PLAIN_3D) is True  # regular data is fine for the non-dt model


def test_compatible_is_independent_of_status():
    """Compatibility is orthogonal to lifecycle status (D8): coming_soon ≠ incompatible."""
    recurrence = _model("recurrence")
    assert recurrence.status == "coming_soon"
    assert compatible(_SEQ_IRREGULAR, recurrence) is True


def test_compatible_models_resolver_over_seeds():
    spirals = next(spec for spec in DATASET_TYPES if spec.value == "spirals")
    assert compatible_models(spirals) == [_model("cascor")]
    # A 3-D irregular regression dataset resolves to recurrence from the real MODELS table.
    assert compatible_models(_SEQ_IRREGULAR) == [_model("recurrence")]


def test_compatible_datasets_resolver_over_seeds():
    # cascor (2-D, classification+regression) matches all five 2-D classification seeds.
    assert compatible_datasets(_model("cascor")) == list(DATASET_TYPES)
    # recurrence (3-D) matches NONE of the current 2-D seeds — the iv-3 "no 3-D dataset yet" gap.
    assert compatible_datasets(_model("recurrence")) == []


def test_resolvers_are_injectable_and_order_preserving():
    seq_types = (_SEQ_IRREGULAR, _SEQ_REGULAR, _TABULAR_REGRESSION)
    assert compatible_datasets(_DT_AWARE_3D, dataset_types=seq_types) == [_SEQ_IRREGULAR, _SEQ_REGULAR]
    assert compatible_models(_SEQ_IRREGULAR, models=(_PLAIN_3D, _DT_AWARE_3D)) == [_DT_AWARE_3D]


def test_compatible_models_preserves_input_order():
    """When several models match, the resolver yields them in input order (no reordering)."""
    m1 = ModelSpec(key="m1", label="m1", category="feedforward", input_ndim=frozenset({2}), supported_task_types=frozenset({"regression"}))
    m2 = ModelSpec(key="m2", label="m2", category="feedforward", input_ndim=frozenset({2}), supported_task_types=frozenset({"regression"}))
    assert compatible_models(_TABULAR_REGRESSION, models=(m1, m2)) == [m1, m2]
    assert compatible_models(_TABULAR_REGRESSION, models=(m2, m1)) == [m2, m1]


def test_resolvers_agree_with_predicate_over_seeds():
    """Resolvers are exactly the predicate filtered over the registry (no hidden criteria)."""
    for dataset in DATASET_TYPES:
        assert compatible_models(dataset) == [model for model in MODELS if compatible(dataset, model)]
    for model in MODELS:
        assert compatible_datasets(model) == [dataset for dataset in DATASET_TYPES if compatible(dataset, model)]
