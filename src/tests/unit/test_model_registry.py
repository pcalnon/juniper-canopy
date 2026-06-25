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
    DEFAULT_MODEL_KEY,
    MODELS,
    DatasetTypeSpec,
    ModelSpec,
    compatible,
    compatible_datasets,
    compatible_models,
    dataset_default_params,
    dataset_model_hint,
    dataset_reason,
    dataset_type_options,
    gated_dataset_options,
    get_dataset_spec,
    get_model_spec,
    model_options,
    model_reason,
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


def test_dataset_type_options_preserve_2d_order_then_append_3d_seed():
    """The five original 2-D options are preserved in order (A0 contract); A1-iv-3b appends
    the equities_seq 3-D entry for the recurrence model."""
    options = dataset_type_options()
    assert options[:5] == _PREVIOUS_HARDCODED_OPTIONS
    assert {"label": "Equities (sequence)", "value": "equities_seq"} in options


def test_default_dataset_type_preserved():
    assert DEFAULT_DATASET_TYPE == "spirals"
    assert DEFAULT_DATASET_TYPE in {spec.value for spec in DATASET_TYPES}


def test_dataset_values_are_unique():
    values = [spec.value for spec in DATASET_TYPES]
    assert len(values) == len(set(values))


def test_dataset_seeds_2d_classification_plus_3d_sequence():
    by_value = {spec.value: spec for spec in DATASET_TYPES}
    for value in ("spirals", "xor", "mnist", "circles", "moons"):
        spec = by_value[value]
        assert spec.ndim == 2 and spec.task_type == "classification" and spec.temporal == "none"
    # A1-iv-3b: the 3-D irregular-Δt regression seed that makes the recurrence model selectable.
    seq = by_value["equities_seq"]
    assert seq.ndim == 3 and seq.task_type == "regression" and seq.temporal == "irregular"


def test_default_params_seeded_only_for_equities_seq():
    """A1-iv-3c: the synthetic 2-D types carry no start params; equities_seq carries the
    bounded + stationary registry seed (the single source of truth for a one-shot fit)."""
    by_value = {spec.value: spec for spec in DATASET_TYPES}
    for value in ("spirals", "xor", "mnist", "circles", "moons"):
        assert by_value[value].default_params == {}
    assert by_value["equities_seq"].default_params == {"max_symbols": 5, "regression_target": "return"}


def test_dataset_default_params_returns_seed_copy():
    """A1-iv-3c: the resolver returns the seed for a known value, ``{}`` for an unknown one, and a
    COPY so a caller mutating the result can never corrupt the frozen registry constant."""
    assert dataset_default_params("equities_seq") == {"max_symbols": 5, "regression_target": "return"}
    assert dataset_default_params("spirals") == {}
    assert dataset_default_params("nonexistent") == {}
    first = dataset_default_params("equities_seq")
    first["max_symbols"] = 999
    assert dataset_default_params("equities_seq")["max_symbols"] == 5


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
    # cascor (2-D, classification+regression) matches the five 2-D classification seeds, NOT the
    # 3-D equities_seq (A1-iv-3b added it for the recurrence model).
    assert [dataset.value for dataset in compatible_datasets(_model("cascor"))] == ["spirals", "xor", "mnist", "circles", "moons"]
    # recurrence (3-D irregular) now matches the equities_seq seed (was [] before iv-3b).
    assert [dataset.value for dataset in compatible_datasets(_model("recurrence"))] == ["equities_seq"]


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


# Model-picker options (A1-iv-3a): the registry source for the sidebar nn-model-dropdown.


def test_default_model_key_is_a_live_seed():
    """The picker boots to a real, trainable model (the cascor in-process default)."""
    spec = get_model_spec(DEFAULT_MODEL_KEY)
    assert spec is not None
    assert spec.is_live


def test_model_options_cover_all_models_in_registry_order():
    assert [option["value"] for option in model_options()] == [model.key for model in MODELS]


def test_model_options_label_carries_lifecycle_hint_for_non_live():
    by_value = {option["value"]: option["label"] for option in model_options()}
    # cascor is live -> plain label (no hint).
    assert by_value["cascor"] == "CasCor (Cascade-Correlation)"
    # recurrence is coming_soon -> the label carries the lifecycle hint (D8).
    assert by_value["recurrence"].startswith("Recurrence (LMU)")
    assert "coming soon" in by_value["recurrence"]


# Dataset gate (A1-iv-3b): the model->dataset greying source for the sidebar dropdown.


def _spec(key):
    spec = get_model_spec(key)
    assert spec is not None
    return spec


def test_equities_seq_makes_recurrence_trainable():
    """The 3-D seed gives the recurrence (LMU) model a compatible dataset (was [] before iv-3b)."""
    assert [dataset.value for dataset in compatible_datasets(_spec("recurrence"))] == ["equities_seq"]


def test_dataset_reason_none_when_compatible():
    spirals = next(dataset for dataset in DATASET_TYPES if dataset.value == "spirals")
    assert dataset_reason(spirals, _spec("cascor")) is None


def test_dataset_reason_names_the_failing_axis():
    spirals = next(dataset for dataset in DATASET_TYPES if dataset.value == "spirals")  # 2-D
    equities = next(dataset for dataset in DATASET_TYPES if dataset.value == "equities_seq")  # 3-D
    # 2-D dataset vs the 3-D recurrence model -> ndim reason (what model the dataset needs).
    assert dataset_reason(spirals, _spec("recurrence")) == "needs a 2-D model"
    # 3-D dataset vs the 2-D cascor model -> ndim reason.
    assert dataset_reason(equities, _spec("cascor")) == "needs a 3-D model"


def test_dataset_reason_task_and_temporal_axes():
    # ndim matches, task mismatches -> task reason (a non-ndim axis of the dropdown suffix).
    assert dataset_reason(_TABULAR_REGRESSION, _CLASSIFIER_2D) == "needs a regression model"
    # ndim + task match; irregular-Δt data vs a non-Δt model -> temporal reason.
    assert dataset_reason(_SEQ_IRREGULAR, _PLAIN_3D) == "needs a Δt-aware model"


# Model-table compatibility cell (A1b-1): model_reason is the model-perspective inverse.


def test_model_reason_none_when_compatible():
    spirals = next(dataset for dataset in DATASET_TYPES if dataset.value == "spirals")  # 2-D
    equities = next(dataset for dataset in DATASET_TYPES if dataset.value == "equities_seq")  # 3-D
    assert model_reason(_spec("cascor"), spirals) is None
    assert model_reason(_spec("recurrence"), equities) is None


def test_model_reason_names_the_failing_axis():
    spirals = next(dataset for dataset in DATASET_TYPES if dataset.value == "spirals")  # 2-D
    equities = next(dataset for dataset in DATASET_TYPES if dataset.value == "equities_seq")  # 3-D
    # The 3-D recurrence model vs a 2-D dataset -> it needs 3-D data (inverse of "needs a 3-D model").
    assert model_reason(_spec("recurrence"), spirals) == "needs 3-D data"
    # The 2-D cascor model vs a 3-D dataset -> it needs 2-D data.
    assert model_reason(_spec("cascor"), equities) == "needs 2-D data"


def test_model_reason_task_and_temporal_axes():
    # ndim matches, task mismatches -> the classifier needs classification data.
    assert model_reason(_CLASSIFIER_2D, _TABULAR_REGRESSION) == "needs classification data"
    # ndim + task match; the non-Δt 3-D model vs irregular-Δt data -> temporal reason.
    assert model_reason(_PLAIN_3D, _SEQ_IRREGULAR) == "needs regularly-sampled data"


def test_model_reason_inverse_consistent_with_dataset_reason_over_seeds():
    """model_reason and dataset_reason agree with the predicate on every seed pair (both directions)."""
    for dataset in DATASET_TYPES:
        for model in MODELS:
            same_verdict = (model_reason(model, dataset) is None) == (dataset_reason(dataset, model) is None)
            assert same_verdict
            assert (model_reason(model, dataset) is None) == compatible(dataset, model)


def test_get_dataset_spec_resolves_and_misses():
    spec = get_dataset_spec("equities_seq")
    assert spec is not None
    assert spec.value == "equities_seq" and spec.ndim == 3
    assert get_dataset_spec("nonexistent") is None
    assert get_dataset_spec("") is None


# Sidebar reverse-gate annotation (A1b-2; §5.3): dataset_model_hint.


def test_dataset_model_hint_names_the_constraint_per_dataset():
    # spirals = 2-D -> "2-D models only"; equities_seq = 3-D irregular -> "3-D Δt-aware models only".
    assert dataset_model_hint("spirals") == "2-D models only"
    assert dataset_model_hint("equities_seq") == "3-D Δt-aware models only"


def test_dataset_model_hint_none_without_a_dataset():
    assert dataset_model_hint("") is None
    assert dataset_model_hint("does-not-exist") is None


def test_dataset_model_hint_empty_compatible_set_warns():
    # Degenerate (§5.8): inject an empty model population so nothing is compatible.
    assert dataset_model_hint("spirals", models=()) == "no compatible models"


def test_dataset_model_hint_non_none_for_every_seed_dataset():
    """Each seed dataset has ≥1 compatible model under option (a), so the hint is always a phrase."""
    for dataset in DATASET_TYPES:
        assert dataset_model_hint(dataset.value) is not None


def test_gated_dataset_options_greys_incompatible_for_recurrence():
    by_value = {option["value"]: option for option in gated_dataset_options("recurrence")}
    # equities_seq (3-D) is compatible -> plain, selectable.
    assert by_value["equities_seq"] == {"label": "Equities (sequence)", "value": "equities_seq"}
    # the 2-D types are disabled with a reason-suffix label.
    assert by_value["spirals"]["disabled"] is True
    assert by_value["spirals"]["label"] == "Spirals — needs a 2-D model"


def test_gated_dataset_options_all_plain_for_cascor_then_3d_greyed():
    # cascor (2-D, classification+regression) accepts every 2-D type; only the 3-D seed is greyed.
    by_value = {option["value"]: option for option in gated_dataset_options("cascor")}
    for value in ("spirals", "xor", "mnist", "circles", "moons"):
        assert "disabled" not in by_value[value]
    assert by_value["equities_seq"]["disabled"] is True
    assert by_value["equities_seq"]["label"] == "Equities (sequence) — needs a 3-D model"


def test_gated_dataset_options_unknown_model_is_ungated():
    # No spec -> fall back to all-plain options (never hide every dataset on a desync).
    options = gated_dataset_options("nonexistent")
    assert all("disabled" not in option for option in options)
    assert [option["value"] for option in options] == [dataset.value for dataset in DATASET_TYPES]
