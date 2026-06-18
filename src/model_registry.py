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
# Last Modified: 2026-06-17
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Single source of truth for NN-model and dataset-type specifications used by the
#     model-selection feature. This module (A0) defines the spec dataclasses, seeds the
#     current models and dataset types, and supplies dataset_type_options() so the
#     dashboard dataset-type dropdown no longer hardcodes its options. The compatibility
#     resolvers, the dedicated selection surface, and the nn_model backend mirror are
#     deferred to A1.
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
#     - A1: compatibility predicate + resolvers, the dedicated selection surface, the
#       nn_model backend mirror.
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
"""Model + dataset-type registry (single source of truth) for model selection.

A0 scope: spec dataclasses + seeds + ``dataset_type_options()``. See the module header
and the design-of-record note for the full design.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetTypeSpec:
    """A selectable dataset type and the properties that gate model compatibility."""

    value: str  # stable id sent to the backend (e.g. "spirals")
    label: str  # human-facing label (e.g. "Spirals")
    task_type: str  # juniper-data vocabulary: "classification" | "regression"
    ndim: int  # input rank: 2 (tabular) | 3 (sequence)
    temporal: str = "none"  # "none" | "regular" | "irregular" (3-D only)


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
    tags: frozenset[str] = frozenset()  # facet tags for the A1 selection surface
    description: str = ""
    aliases: tuple[str, ...] = ()
    provider: str = ""  # where it is served ("in-process" | service name)

    @property
    def is_live(self) -> bool:
        """True when the model can be trained right now (back-compat convenience)."""
        return self.status == "live"


# Selectable dataset types. The order is user-facing and MUST match the previously
# inlined dropdown options (spirals first = default). All five current types are 2-D
# classification (juniper-data vocabulary).
DATASET_TYPES: tuple[DatasetTypeSpec, ...] = (
    DatasetTypeSpec(value="spirals", label="Spirals", task_type="classification", ndim=2),
    DatasetTypeSpec(value="xor", label="XOR", task_type="classification", ndim=2),
    DatasetTypeSpec(value="mnist", label="MNIST", task_type="classification", ndim=2),
    DatasetTypeSpec(value="circles", label="Circles", task_type="classification", ndim=2),
    DatasetTypeSpec(value="moons", label="Moons", task_type="classification", ndim=2),
)

# Default dataset type — preserves the prior hardcoded value="spirals".
DEFAULT_DATASET_TYPE: str = DATASET_TYPES[0].value

# Known models. cascor is the live feed-forward backend; recurrence (LMU) is the
# coming-soon 3-D / irregular-delta-t model (published as juniper-recurrence-model
# 0.1.0; the canopy-routable service is not yet deployed — design note §5.7 / §8.4).
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
        status="coming_soon",
        provider="juniper-recurrence",
        description="Legendre Memory Unit regressor for irregular-delta-t time series.",
    ),
)


def dataset_type_options() -> list[dict[str, str]]:
    """Return the dataset-type dropdown options as ``[{"label", "value"}, ...]``.

    Single source for the ``nn-dataset-type-dropdown`` options (previously inlined in
    ``dashboard_manager``). Order is preserved for behavior parity.
    """
    return [{"label": spec.label, "value": spec.value} for spec in DATASET_TYPES]
