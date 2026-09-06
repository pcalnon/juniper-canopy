#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     model_registry.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/
#
# Date Created:  2026-06-17
# Last Modified: 2026-06-24
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Single source of truth for NN-model and dataset-type specifications used by the
#     model-selection feature. This module (A0) defines the spec dataclasses, seeds the
#     current models and dataset types, and supplies dataset_type_options() so the
#     dashboard dataset-type dropdown no longer hardcodes its options. A1-iv-1 adds the pure
#     compatibility engine (compatible() + temporal_ok() + the compatible_models /
#     compatible_datasets resolvers); the dedicated selection surface and the nn_model
#     backend mirror remain deferred to A1-iv-3+.
#
#     Design of record: juniper-ml
#     notes/JUNIPER_CANOPY_MODEL_DATASET_SELECTION_DESIGN_2026-06-17.md
#
#####################################################################################################################################################################################################
# Notes:
#     - Behavior-preserving: dataset_type_options() reproduces the previously inlined
#       dropdown options exactly (label / value / order); DEFAULT_DATASET_TYPE preserves
#       the prior value="spirals" default.
#     - task_type uses juniper-data's emitted vocabulary ("classification" /
#       "regression"); the recurrence model's 3-D / irregular-delta-t nature is carried
#       by ndim + requires_dt, NOT by a task_type label.
#     - status drives lifecycle presentation in A1 ("live" | "coming_soon" |
#       "experimental" | "deprecated" | "broken"); non-live models are shown but are not
#       trainable.
#
#####################################################################################################################################################################################################
# References:
#     - Tracks canopy issue #368 (model selection).
#
#####################################################################################################################################################################################################
# TODO :
#     - A1-iv-3+: the dedicated selection surface, the nn_model backend mirror, the
#       reason-suffix greying (the per-locus phrasing layered on this engine).
#
#####################################################################################################################################################################################################
# COMPLETED:
#     - A1-iv-1: compatibility predicate (compatible / temporal_ok) + resolvers
#       (compatible_models / compatible_datasets).
#     - A1-iv-3a: model_options() + DEFAULT_MODEL_KEY (the sidebar model-picker source).
#     - A1-iv-3b: equities_seq 3-D seed + dataset_reason() + gated_dataset_options() (the
#       model->dataset compatibility gate).
#     - A1-iv-3c: DatasetTypeSpec.default_params + dataset_default_params() (the registry-seeded
#       juniper-data params the one-shot Start button forwards so the recurrence fit is bounded).
#     - A1b-1: get_dataset_spec() + model_reason() (the model-perspective inverse of
#       dataset_reason) — the compatibility-cell text for the dedicated model-selection surface.
#     - A1b-2: dataset_model_hint() — the sidebar reverse-gate annotation (§5.3) naming the model
#       constraint the selected dataset imposes; also surfaces the empty-compatible-set state (§5.8).
#     - A1-iv-5: flipped recurrence coming_soon → live (service deployed + canopy-wired, deploy #132)
#       + model_is_trainable() (the D8 Train-gate predicate) + model_options(models=) injectability.
#     - A1b-search: model_matches_search() — the model-table search predicate (label + family +
#       category + tags, §5.2) backing the modal search box.
#
#####################################################################################################################################################################################################
"""Model + dataset-type registry (single source of truth) for model selection.

A0 scope: spec dataclasses + seeds + ``dataset_type_options()``. A1-iv-1 adds the pure,
browser-free compatibility engine (``compatible`` + ``temporal_ok`` + the
``compatible_models`` / ``compatible_datasets`` resolvers) — the §4 correctness guarantee.
See the module header and the design-of-record note for the full design.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatasetTypeSpec:
    """A selectable dataset type and the properties that gate model compatibility."""

    value: str  # stable id sent to the backend (e.g. "spirals")
    label: str  # human-facing label (e.g. "Spirals")
    task_type: str  # juniper-data vocabulary: "classification" | "regression"
    ndim: int  # input rank: 2 (tabular) | 3 (sequence)
    temporal: str = "none"  # "none" | "regular" | "irregular" (3-D only)
    # A1-iv-3c: juniper-data generator params the one-shot (recurrence) Start button forwards
    # for a fast, usable fit — the registry is the single source of truth (the synthetic
    # n_samples/noise sidebar inputs do not apply to a 3-D sequence generator). Empty for the
    # synthetic 2-D types. NB: a dict field makes DatasetTypeSpec unhashable — fine here, specs
    # are only ever iterated or indexed by ``.value`` (never set-membered or used as a dict key).
    default_params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSpec:
    """An NN model (or benchmark variant) and the dataset properties it requires."""

    key: str  # globally unique stable id (e.g. "cascor", "lmu-growth-v3")
    label: str  # human-facing label
    category: str  # "feedforward" | "ts_established" | "ts_growth"
    input_ndim: frozenset[int]  # accepted input ranks, e.g. frozenset({2})
    supported_task_types: frozenset[str]  # juniper-data task_type vocabulary
    family: str = ""  # grouping for variants (e.g. "lmu", "cascor")
    variant: str = ""  # variant discriminator within a family
    version: str = ""  # benchmark identity
    benchmark_id: str = ""  # stable ref for result analysis
    requires_dt: bool = False  # consumes per-step delta-t (irregular sequences)
    status: str = "live"  # "live"|"coming_soon"|"experimental"|"deprecated"|"broken"
    execution: str = "live"  # "live" (streamed per-epoch training) | "one_shot" (single blocking fit). Drives the A1-iii one-shot UI: suppress cascade panels + switch metrics accuracy->regression when "one_shot".
    tags: frozenset[str] = frozenset()  # facet tags for the A1 selection surface
    description: str = ""
    aliases: tuple[str, ...] = ()
    provider: str = ""  # where it is served ("in-process" | service name)

    @property
    def is_live(self) -> bool:
        """True when the model can be trained right now (back-compat convenience)."""
        return self.status == "live"


# Selectable dataset types. The order is user-facing; the five 2-D classification types come
# first (spirals = default), preserving the original inlined dropdown order. A1-iv-3b appends
# the 3-D irregular-delta-t regression seed (``equities_seq``) so the recurrence (LMU) model
# has a compatible dataset; the sidebar gate (``gated_dataset_options``) greys it for 2-D models.
DATASET_TYPES: tuple[DatasetTypeSpec, ...] = (
    DatasetTypeSpec(value="spirals", label="Spirals", task_type="classification", ndim=2),
    DatasetTypeSpec(value="xor", label="XOR", task_type="classification", ndim=2),
    DatasetTypeSpec(value="mnist", label="MNIST", task_type="classification", ndim=2),
    DatasetTypeSpec(value="circles", label="Circles", task_type="classification", ndim=2),
    DatasetTypeSpec(value="moons", label="Moons", task_type="classification", ndim=2),
    DatasetTypeSpec(
        value="equities_seq",
        label="Equities (sequence)",
        task_type="regression",
        ndim=3,
        temporal="irregular",
        # Bounded + stationary so the one-shot fit is fast and well-conditioned: cap the universe
        # (vs the ~500-symbol juniper-data default that would blow the 300s train timeout) and use
        # the stationary return target (the raw next_close default extrapolates badly on trending
        # prices — see the recurrence equities readout finding).
        default_params={"max_symbols": 5, "regression_target": "return"},
    ),
)

# Default dataset type — preserves the prior hardcoded value="spirals".
DEFAULT_DATASET_TYPE: str = DATASET_TYPES[0].value

# Provider sentinel for models served by the juniper-recurrence model service. Single
# source of truth shared by the ``recurrence`` ModelSpec seed (below) and the backend
# factory's provider routing (``backend.create_backend``, A1-ii). The cascor model uses
# the ``"in-process"`` provider; demo has none.
RECURRENCE_PROVIDER: str = "juniper-recurrence"

# Known models. cascor is the live in-process feed-forward backend; recurrence (LMU) is the
# live 3-D / irregular-delta-t one-shot model (juniper-recurrence-model 0.1.0). A1-iv-5 flipped
# it coming_soon → live now that the canopy-routable service is deployed + wired in-stack
# (juniper-deploy #132 wires JUNIPER_CANOPY_RECURRENCE_SERVICE_URL → http://juniper-recurrence:8210;
# design §5.7 / §8.4). canopy's D8 Train-gate (model_is_trainable) disables Start for any *non*-live
# model, so a future experimental/coming_soon entry is shown but not trainable.
MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        key="cascor",
        label="CasCor (Cascade-Correlation)",
        category="feedforward",
        input_ndim=frozenset({2}),
        supported_task_types=frozenset({"classification", "regression"}),
        family="cascor",
        status="live",
        provider="in-process",
        description="Cascade-Correlation feed-forward network (current backend).",
    ),
    ModelSpec(
        key="recurrence",
        label="Recurrence (LMU)",
        category="ts_established",
        input_ndim=frozenset({3}),
        supported_task_types=frozenset({"regression"}),
        family="lmu",
        version="0.1.0",
        requires_dt=True,
        status="live",  # A1-iv-5: flipped coming_soon → live (service deployed + canopy-wired, juniper-deploy #132)
        execution="one_shot",
        provider=RECURRENCE_PROVIDER,
        description="Legendre Memory Unit regressor for irregular-delta-t time series.",
    ),
)

# Default selected model for the A1 picker — the live in-process cascor backend (mirrors the
# DEFAULT_DATASET_TYPE first-element convention; MODELS[0] is the cascor seed).
DEFAULT_MODEL_KEY: str = MODELS[0].key


def dataset_type_options() -> list[dict[str, str]]:
    """Return the dataset-type dropdown options as ``[{"label", "value"}, ...]``.

    Single source for the ``nn-dataset-type-dropdown`` options (previously inlined in
    ``dashboard_manager``). Order is preserved for behavior parity.
    """
    return [{"label": spec.label, "value": spec.value} for spec in DATASET_TYPES]


def dataset_default_params(value: str) -> dict[str, object]:
    """Return a copy of the one-shot start params seeded for dataset ``value`` (A1-iv-3c).

    The recurrence (one-shot) Start button forwards these as the juniper-data ``generator``
    params so the fit is bounded + stationary (see ``DatasetTypeSpec.default_params``). A copy
    is returned so a caller can never mutate the registry seed. Unknown ``value`` → ``{}``.
    """
    for spec in DATASET_TYPES:
        if spec.value == value:
            return dict(spec.default_params)
    return {}


def model_options(*, models: tuple[ModelSpec, ...] = MODELS) -> list[dict[str, str]]:
    """Return the model-picker dropdown options as ``[{"label", "value"}, ...]`` (A1-iv-3a).

    Registry order is preserved. Non-``live`` models carry a short lifecycle hint in the label
    (D8) so the picker reads honestly. ``models`` is injectable so the non-live label path stays
    testable once every shipped model is live (post A1-iv-5).
    """
    return [{"label": spec.label if spec.status == "live" else f"{spec.label} — {spec.status.replace('_', ' ')}", "value": spec.key} for spec in models]


def model_is_trainable(model_key: str, *, models: tuple[ModelSpec, ...] = MODELS) -> bool:
    """True when the model for ``model_key`` can be trained now — its status is 'live' (D8; §5.7).

    The D8 Train-gate (A1-iv-5): a non-live model (``coming_soon`` / ``experimental`` /
    ``deprecated`` / ``broken``) is shown and selectable for inspection but NOT trainable, so the
    dashboard disables the Start button for it. An unknown ``model_key`` (no spec) defaults to
    trainable so a transient desync never strands Start — the target model service still fails
    closed on an actual shape/availability mismatch (FR9). ``models`` is injectable so the non-live
    branch stays testable once every shipped model is live.
    """
    if not model_key:
        return True
    for spec in models:
        if model_key == spec.key or model_key in spec.aliases:
            return spec.status == "live"
    return True


def model_matches_search(model: ModelSpec, query: str) -> bool:
    """True when ``model`` matches the free-text search ``query`` (A1b search box; design §5.2).

    Case-insensitive substring match over the model's ``label`` + ``family`` + ``category`` +
    ``tags`` — NOT label-only (§8), so a family ("lmu") or a facet tag finds the model even when the
    label does not contain the term. A blank / whitespace query matches everything (no filter).
    """
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join((model.label, model.family, model.category, *model.tags)).lower()
    return needle in haystack


def get_model_spec(key: str) -> ModelSpec | None:
    """Return the :class:`ModelSpec` for ``key`` (matching ``key`` or an alias), or None.

    Used by the backend factory (``backend.create_backend``) to resolve a selected model
    key to its provider for routing, and available to the A1 selection UI for lookups.
    """
    for spec in MODELS:
        if key == spec.key or key in spec.aliases:
            return spec
    return None


def get_dataset_spec(value: str) -> DatasetTypeSpec | None:
    """Return the :class:`DatasetTypeSpec` for ``value``, or None (symmetric with get_model_spec).

    Used by the A1b model-selection surface to resolve the currently-selected dataset value to
    its spec so the per-model compatibility cell (``model_reason``) can be computed against it.
    """
    for spec in DATASET_TYPES:
        if spec.value == value:
            return spec
    return None


# Compatibility engine (A1-iv-1) — the pure dataset x model predicate + resolvers (design §4).
# Datasets declare PROPERTIES (ndim / task_type / temporal); models declare REQUIREMENTS
# (input_ndim / supported_task_types / requires_dt). Compatibility is a pure, browser-free
# predicate and IS the correctness guarantee (D5): the UI greying layered on top is a
# best-effort affordance, and the target model service still fails closed on a shape mismatch
# (FR9). The temporal clause is the fine discriminator that separates same-ndim / same-task
# models (e.g. two 3-D regressors) as the model population grows (§1). Resolvers filter purely
# on compatibility and are independent of ``status`` (lifecycle gating is a separate
# presentation axis — D8).


def temporal_ok(dataset: DatasetTypeSpec, model: ModelSpec) -> bool:
    """Return True when ``model`` satisfies ``dataset``'s temporal requirement.

    Only *irregular*-delta-t data imposes a constraint: the model must consume per-step
    delta-t (``requires_dt``). Regular and non-temporal datasets place no constraint — a
    delta-t-aware model still accepts them (delta-t is simply constant or absent). Design §4.
    """
    if dataset.temporal == "irregular":
        return model.requires_dt
    return True


def compatible(dataset: DatasetTypeSpec, model: ModelSpec) -> bool:
    """Return True when ``dataset`` can be trained on ``model`` — the design §4 predicate.

    Multi-axis: ``ndim`` (necessary) AND ``task_type`` (carried; currently inert across the
    seeds) AND the temporal clause (``temporal_ok``). This is *compatibility* only and is
    independent of ``model.status``: a ``coming_soon`` model is still compatible (D8).
    """
    return dataset.ndim in model.input_ndim and dataset.task_type in model.supported_task_types and temporal_ok(dataset, model)


def compatible_models(dataset: DatasetTypeSpec, *, models: tuple[ModelSpec, ...] = MODELS) -> list[ModelSpec]:
    """Return the models compatible with ``dataset``, in ``models`` order.

    Pure compatibility — no ``status`` filtering (D8). ``models`` is injectable for tests.
    """
    return [model for model in models if compatible(dataset, model)]


def compatible_datasets(model: ModelSpec, *, dataset_types: tuple[DatasetTypeSpec, ...] = DATASET_TYPES) -> list[DatasetTypeSpec]:
    """Return the dataset types compatible with ``model``, in ``dataset_types`` order.

    Pure compatibility — no ``status`` filtering (D8). ``dataset_types`` is injectable for tests.
    """
    return [dataset for dataset in dataset_types if compatible(dataset, model)]


def dataset_reason(dataset: DatasetTypeSpec, model: ModelSpec) -> str | None:
    """Dataset-perspective incompatibility reason for the dropdown suffix (A1-iv-3b; D2/§5.4).

    Returns ``None`` when ``dataset`` is compatible with ``model``; otherwise a short
    "needs a … model" phrase naming the first failing axis — what KIND of model this dataset
    needs (the reason sits on the greyed option, per the design example "Spirals — needs a
    2-D model").
    """
    if dataset.ndim not in model.input_ndim:
        return f"needs a {dataset.ndim}-D model"
    if dataset.task_type not in model.supported_task_types:
        return f"needs a {dataset.task_type} model"
    if not temporal_ok(dataset, model):
        return "needs a Δt-aware model"
    return None


def model_reason(model: ModelSpec, dataset: DatasetTypeSpec) -> str | None:
    """Model-perspective incompatibility reason for the model-table cell (A1b-1; D2/§5.2).

    Returns ``None`` when ``model`` is compatible with ``dataset``; otherwise a short
    "needs … data" phrase naming the first failing axis — what KIND of data this model needs
    that the current dataset does not supply. This is the model-perspective inverse of
    ``dataset_reason`` (which names what kind of model a dataset needs); the phrase sits in the
    model row's compatibility cell (e.g. "Recurrence (LMU) — needs 3-D data" against a 2-D
    dataset). The axis order mirrors ``dataset_reason`` so the two stay consistent.
    """
    if dataset.ndim not in model.input_ndim:
        dims = " or ".join(f"{n}-D" for n in sorted(model.input_ndim))
        return f"needs {dims} data"
    if dataset.task_type not in model.supported_task_types:
        tasks = " or ".join(sorted(model.supported_task_types))
        return f"needs {tasks} data"
    if not temporal_ok(dataset, model):
        return "needs regularly-sampled data"
    return None


def model_requirement(model: ModelSpec) -> str:
    """What kind of data ``model`` needs, stated without reference to any dataset (Y9; D2/§5.2).

    ``model_reason`` answers a *comparative* question -- "why is this model incompatible with THIS
    dataset" -- and returns ``None`` when there is no dataset to compare against. The model table
    rendered that ``None`` as "✓ compatible", which at ``⊥`` is a **positive falsehood about every
    model**: it asserts agreement with a dataset that does not exist. This states the requirement
    itself, so a ``⊥`` row can say what it WOULD need.

    Deliberately covers every axis rather than the first failing one, because there is no failure to
    report -- the caller wants the whole shape of what this model accepts. Axis order and vocabulary
    mirror ``model_reason`` so the two never read as different constraints.
    """
    dims = " or ".join(f"{n}-D" for n in sorted(model.input_ndim))
    tasks = " or ".join(sorted(model.supported_task_types))
    phrase = f"needs {dims} {tasks} data"
    if model.requires_dt:
        phrase += ", irregular Δt supported"
    return phrase


# N7 (I-7): tensor-rank nouns for the reverse-gate hint. The pre-N7 phrasing ("2-D models only")
# read as a feature-count constraint and misled — e.g. MNIST is ``ndim=2`` (a rank-2 tabular tensor
# of 784 features), so "2-D" wrongly suggested MNIST was excluded. Naming the rank AND its shape
# noun ("rank-2 (tabular)") makes clear the discriminator is tensor rank, not the number of features.
_RANK_NOUNS: dict[int, str] = {2: "tabular", 3: "sequence"}


def dataset_model_hint(dataset_value: str, *, models: tuple[ModelSpec, ...] = MODELS) -> str | None:
    """Sidebar reverse-gate hint naming the model constraint the selected dataset imposes (A1b-2; §5.3).

    Given the selected dataset, a short positive phrase describing what KIND of model it admits —
    so the user sees, at rest in the sidebar, why some models are greyed in the table. This is the
    dataset-side mirror of the table's per-row ``model_reason`` greying (the reverse gate, §5.3):
    it names the structural discriminators (tensor ``ndim``, plus Δt-awareness for irregular
    sequences). N7 (I-7) rewords the rank clause from "N-D" to "rank-N (<shape>)" so it reads as a
    tensor-rank constraint (which it is) rather than a feature-count one (which confused for MNIST).

    Returns ``None`` when no dataset is selected (so the caller clears the annotation); a
    ``"no compatible models"`` warning when the compatible set is empty (the degenerate state,
    §5.8). ``models`` is injectable for tests (mirrors ``compatible_models``).
    """
    spec = get_dataset_spec(dataset_value)
    if spec is None:
        return None
    if not compatible_models(spec, models=models):
        return "no compatible models"
    noun = _RANK_NOUNS.get(spec.ndim)
    parts = [f"rank-{spec.ndim} ({noun})" if noun else f"rank-{spec.ndim}"]
    if spec.temporal == "irregular":
        parts.append("Δt-aware")
    return f"{' '.join(parts)} models only"


def gated_dataset_options(model_key: str) -> list[dict[str, object]]:
    """Dataset-dropdown options gated against the selected model (A1-iv-3b).

    Compatible dataset types are plain, selectable options; incompatible ones are ``disabled``
    with a reason-suffix label (D2). Single source for the initial render (``DEFAULT_MODEL_KEY``)
    and the runtime gate callback. An unknown ``model_key`` (no spec) falls back to ungated
    options so a desync never hides every dataset.
    """
    spec = get_model_spec(model_key)
    options: list[dict[str, object]] = []
    for dataset in DATASET_TYPES:
        reason = dataset_reason(dataset, spec) if spec is not None else None
        if reason is None:
            options.append({"label": dataset.label, "value": dataset.value})
        else:
            options.append({"label": f"{dataset.label} — {reason}", "value": dataset.value, "disabled": True})
    return options
