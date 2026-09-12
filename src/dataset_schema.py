#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.5.0
# File Name:     dataset_schema.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/
#
# Date Created:  2026-07-21
# Last Modified: 2026-07-21
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     N7 (training-runtime defects plan, I-7 / U-6 / I-5-UX): the schema-driven
#     dataset-panel core. Pure, browser-free helpers that turn a juniper-data
#     generator's JSON-Schema (``params_class.model_json_schema()``, surfaced by
#     GET /v1/generators as of juniper-data 0.10.0 / D1) into an ordered list of
#     renderable field descriptors, and that read the additive per-generator
#     ``available`` flag with a flag-absent-means-available fallback (older
#     juniper-data). The dashboard maps these descriptors into sidebar inputs and
#     the availability gate; the staging dialect stays intact because non-spiral
#     schema params are forwarded through cascor's generic ``params`` channel.
#
#     Design of record: juniper-ml
#     notes/JUNIPER_2026-07-11_JUNIPER-CANOPY_TRAINING-RUNTIME-DEFECTS-PLAN.md §4 I-7 / §4-U U-6 / row N7.
#
#####################################################################################################################################################################################################
# Notes:
#     - Pure module: no Dash, no httpx, no I/O. The dashboard owns the fetch (cached
#       httpx GET of /api/dataset/generators) and the rendering; this module owns the
#       schema->fields mapping and the availability predicate so both are unit-testable
#       without a browser or a live data service.
#     - INFRASTRUCTURE_FIELDS are the split/seed/cache plumbing every generator schema
#       carries (train_ratio/test_ratio/shuffle/seed/use_cache). cascor and juniper-data
#       own those; the canopy training sidebar surfaces generator *content* params only.
#     - GENERATOR_NAME_ALIASES bridges canopy's historical plural dataset-type values
#       ("spirals"/"moons") to juniper-data's singular registry keys ("spiral"/"moon").
#       Everything else is identity.
#
#####################################################################################################################################################################################################
# References:
#     - juniper-data GET /v1/generators (juniper_data/api/routes/generators.py): each
#       entry is {name, version, description, available: bool, schema: <JSON-Schema>}.
#     - cascor StageDatasetRequest.params (src/api/models/training.py): the generic
#       generator-params channel forwarded verbatim to juniper-data create_dataset.
#
#####################################################################################################################################################################################################
# TODO :
#     - Surface the generator's per-501 install hint verbatim once the /v1/generators
#       list carries it (today only the create-time 501 body carries the hint text).
#
#####################################################################################################################################################################################################
# COMPLETED:
#     - N7: parse_schema_fields / availability_map / is_generator_available /
#       generator_name_for_type / apply_availability_gate / unavailable_reason.
#
#####################################################################################################################################################################################################
"""Schema-driven dataset-panel helpers (N7): JSON-Schema -> field descriptors + availability.

The dashboard's Dataset sub-section historically rendered spiral-centric typed inputs for
every dataset type (I-7). This module supplies the pure core that lets the panel render only
the fields the *selected* generator actually declares, with schema-derived labels, bounds and
defaults, and lets it gate generators the deployment cannot serve (``available: false``) with a
UI-friendly reason. Both are pure so they can be exercised without Dash or a live data service.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

# Split / seed / cache plumbing every generator schema carries. cascor and juniper-data own the
# split ratios and RNG seeding, so the canopy training sidebar must not surface them as generator
# content params (they would collide with cascor's own dataset config). Excluded from the rendered
# field set and from the generic ``params`` payload.
INFRASTRUCTURE_FIELDS: frozenset[str] = frozenset(
    {
        "train_ratio",
        "test_ratio",
        "shuffle",
        "seed",
        "use_cache",
    }
)

# The partial-data contract's two DECISION fields. juniper-data's ``equities`` /
# ``equities_seq`` / ``csv_import`` schemas carry ``allow_truncation`` (the gate: accept a
# dataset the producer cannot deliver in full) and ``incomplete_rows`` (accept or drop the
# rows it could not resolve, once the gate is open). Rendered as ordinary sidebar inputs
# they broke the contract twice over: an unticked checkbox sent an EXPLICIT
# ``allow_truncation: false`` on every apply -- which cascor#624 honours over its own
# deployment default, so the operator's silence became a refusal and the failure message
# lost its remedy -- and a ticked one pre-answered a question the contract says must be
# put to the operator when the shortfall actually happens. The dashboard's three-way
# prompt owns both fields: the form sends NEITHER, so a default apply expresses option 3
# (fail) and the prompt supplies options 1 and 2 (accept / drop) on the re-stage.
PARTIAL_DATA_POLICY_FIELDS: frozenset[str] = frozenset({"allow_truncation", "incomplete_rows"})

# Everything the schema-driven form must neither render nor forward.
FORM_EXCLUDED_FIELDS: frozenset[str] = INFRASTRUCTURE_FIELDS | PARTIAL_DATA_POLICY_FIELDS

# canopy dataset-type value -> juniper-data generator name. canopy's registry (model_registry.
# DATASET_TYPES) keeps the historical plural values "spirals"/"moons"; juniper-data's generator
# registry keys are singular "spiral"/"moon". Everything else (xor, mnist, circles, equities_seq)
# is identity. The cascor #396 translation applies the same alias server-side for staging; this
# copy lets canopy resolve the schema/availability of the *selected* value locally.
GENERATOR_NAME_ALIASES: dict[str, str] = {
    "spirals": "spiral",
    "moons": "moon",
}

# UI-reworded unavailability reasons keyed by juniper-data generator name.
#
# **The wire carries the install hint now, and this map is the FALLBACK, not the source.** The
# comment here used to say ``/v1/generators`` "carries ``available: bool`` but not the install
# hint (that reaches the client only in the create-time 501 body)". That stopped being true at
# juniper-data's W-4: ``GeneratorInfo.install_hint`` is a first-class field on that response, and
# its own docstring gives the reason — without it ``available: false`` "says a generator cannot
# run and nothing at all about what would fix that, so a preflight has nowhere to send an
# operator". canopy was hand-maintaining reworded duplicates of a string the producer already
# publishes, for two generators, and falling back to a bare "unavailable in this deployment" for
# every other one — including both equities seeds, which are exactly the ones an operator is most
# likely to hit, since the ``equities`` extra is absent from juniper-data's lockfile.
#
# So the derivation is now: if the producer published a hint, this generator needs an optional
# extra and the label says so generically (the dropdown option has no room for a pip command —
# the full hint goes in the params panel, via ``unavailable_hint``). Only when the producer
# published nothing does this curated map speak, and it survives for exactly one reason: a
# juniper-data older than W-4 sends no hint at all, and "unavailable in this deployment" is a
# worse answer than the two entries below for the two generators canopy happens to know about.
_UNAVAILABLE_REASONS: dict[str, str] = {
    "mnist": "needs juniper-data's optional dataset extra",
    "arc_agi": "needs juniper-data's optional dataset extra",
}
_UNAVAILABLE_REASON_DEFAULT: str = "unavailable in this deployment"
# What the label says when the producer published a hint: short, because it shares a dropdown
# option with the dataset name. The actionable text is the hint itself, rendered in the panel.
_UNAVAILABLE_REASON_HAS_HINT: str = "needs an optional juniper-data extra"


@dataclass(frozen=True)
class GeneratorField:
    """A single renderable generator parameter derived from a JSON-Schema property.

    ``input_type`` is the abstract control kind the dashboard maps to a concrete Dash input:
    ``"number"`` -> ``dbc.Input(type="number")``; ``"checkbox"`` -> a boolean toggle; ``"select"``
    -> a dropdown over ``options``; ``"text"`` -> a free-text input. ``minimum``/``maximum`` are the
    (possibly exclusive) numeric bounds; ``options`` is the enum choice list for ``select``.
    """

    name: str
    label: str
    input_type: str  # "number" | "checkbox" | "select" | "text"
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    description: str = ""
    options: tuple[str, ...] = field(default_factory=tuple)


def humanize(name: str) -> str:
    """Fallback label for a schema property with no ``title`` (``n_samples`` -> ``N Samples``)."""
    return " ".join(part.capitalize() for part in str(name).replace("-", "_").split("_") if part)


def generator_name_for_type(value: str | None) -> str:
    """Resolve a canopy dataset-type value to its juniper-data generator name via the alias map."""
    if not value:
        return ""
    return GENERATOR_NAME_ALIASES.get(value, value)


def _primary_branch(prop: Mapping[str, Any]) -> dict[str, Any]:
    """Collapse a schema property to the branch that carries its type/bounds.

    Optional fields render as ``{"anyOf": [{...type...}, {"type": "null"}], ...}``; pick the first
    non-null branch and merge the property-level keys (``default``/``title``/``description``) over
    it so bounds nested inside the branch (e.g. ``max_symbols``: ``minimum`` lives in the branch)
    are preserved. A non-anyOf property is returned unchanged.
    """
    any_of = prop.get("anyOf")
    if not isinstance(any_of, list):
        return dict(prop)
    for branch in any_of:
        if isinstance(branch, Mapping) and branch.get("type") != "null":
            merged = dict(branch)
            for carry in ("default", "title", "description"):
                if carry in prop:
                    merged[carry] = prop[carry]
            return merged
    return dict(prop)


def _bound(branch: Mapping[str, Any], inclusive: str, exclusive: str) -> float | None:
    """Return the inclusive bound, falling back to the exclusive one (UI hint precision only)."""
    for key in (inclusive, exclusive):
        if key in branch:
            value = branch[key]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return value
    return None


def _field_from_property(name: str, prop: Mapping[str, Any]) -> GeneratorField | None:
    """Map one JSON-Schema property to a :class:`GeneratorField`, or None if not renderable.

    Array / object properties (e.g. equities ``symbols``, spiral ``origin``) and null-only
    properties are skipped — they have sensible generator defaults and no simple sidebar control.
    """
    branch = _primary_branch(prop)
    label = prop.get("title") or branch.get("title") or humanize(name)
    description = prop.get("description") or branch.get("description") or ""
    default = prop.get("default", branch.get("default"))
    enum = branch.get("enum") or prop.get("enum")
    json_type = branch.get("type")

    if enum:
        options = tuple(str(choice) for choice in enum)
        return GeneratorField(name=name, label=label, input_type="select", default=default, description=description, options=options)
    if json_type == "boolean":
        return GeneratorField(name=name, label=label, input_type="checkbox", default=default, description=description)
    if json_type in ("integer", "number"):
        minimum = _bound(branch, "minimum", "exclusiveMinimum")
        maximum = _bound(branch, "maximum", "exclusiveMaximum")
        step: float | None = 1 if json_type == "integer" else None
        return GeneratorField(name=name, label=label, input_type="number", default=default, minimum=minimum, maximum=maximum, step=step, description=description)
    if json_type == "string":
        return GeneratorField(name=name, label=label, input_type="text", default=default, description=description)
    # array / object / null-only -> not renderable as a simple sidebar control; use the default.
    return None


def parse_schema_fields(schema: Mapping[str, Any] | None, *, exclude: Iterable[str] = FORM_EXCLUDED_FIELDS) -> list[GeneratorField]:
    """Return the ordered renderable content fields of a generator ``schema``.

    ``schema`` is a Pydantic ``model_json_schema()`` dict (its ``properties`` map). Excluded
    fields (``exclude`` — the split/seed/cache plumbing plus the partial-data policy fields the
    three-way prompt owns, by default) and non-renderable (array/object/null-only)
    properties are dropped. Property order is preserved (Pydantic emits declaration order), which is
    the user-facing field order. A missing/empty ``properties`` yields ``[]``.
    """
    if not schema:
        return []
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return []
    excluded = set(exclude)
    fields: list[GeneratorField] = []
    for name, prop in properties.items():
        if name in excluded or not isinstance(prop, Mapping):
            continue
        parsed = _field_from_property(name, prop)
        if parsed is not None:
            fields.append(parsed)
    return fields


def apply_seeded_defaults(fields: Sequence[GeneratorField], seeded: Mapping[str, Any] | None) -> list[GeneratorField]:
    """Overlay a registry ``default_params`` seed onto schema-derived field defaults.

    Without this the params panel renders juniper-data's schema defaults while the registry
    seeds something else, so the operator is shown one value and a different one is sent —
    and, worse, the rendered control sends the SCHEMA default straight back over the seed on
    every Apply. ``equities`` is the case that forces it: its seed pins
    ``fundamentals_fill="drop"`` and ``normalize_features=True`` precisely because the schema
    defaults (``"nan"`` / ``False``) produce a dataset CasCor cannot fit — non-finite columns
    and a first-pass loss twenty-two orders of magnitude out.

    Pure and injectable: the seed arrives as a plain mapping rather than being looked up here,
    so this module keeps its "no registry import" shape and a test can state the seed directly.
    Keys the schema does not render are ignored here — they ride to the backend through the
    payload seed in ``_apply_dataset_handler``, which is the only channel an array-valued param
    like ``symbols`` has.

    Args:
        fields: the schema-derived fields, in render order.
        seeded: the registry's ``default_params`` for this dataset (``{}``/None -> unchanged).

    Returns:
        A new list; ``fields`` is not mutated and neither are its (frozen) members.
    """
    if not seeded:
        return list(fields)
    return [dataclasses.replace(field_, default=seeded[field_.name]) if field_.name in seeded else field_ for field_ in fields]


def availability_map(generators: Sequence[Mapping[str, Any]] | None) -> dict[str, bool]:
    """Map generator name -> availability from a ``/v1/generators`` list (flag-absent -> True).

    An entry with no ``available`` key (older juniper-data, or the built-in demo fallback list)
    defaults to available — the documented compat posture (I-5 / N7): canopy must not grey out a
    generator merely because the running data service predates the availability surface.
    """
    result: dict[str, bool] = {}
    for entry in generators or ():
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name")
        if not name:
            continue
        result[str(name)] = bool(entry.get("available", True))
    return result


def is_generator_available(value: str | None, generators: Sequence[Mapping[str, Any]] | None) -> bool:
    """True when the generator for canopy dataset-type ``value`` is available (or the flag is absent).

    Resolves ``value`` to its generator name via the alias map, then reads the availability map.
    A generator absent from the list (e.g. the fallback demo list, or a desync) is treated as
    available so a transient/older data service never strands a dataset type (fail-open UI; the
    create call still fails closed with the 501 install hint if the extra is truly missing).
    """
    name = generator_name_for_type(value)
    if not name:
        return True
    return availability_map(generators).get(name, True)


def unavailable_hint(value: str | None, generators: Sequence[Mapping[str, Any]] | None) -> str | None:
    """The producer's own install hint for ``value``'s generator, or None.

    ``GeneratorInfo.install_hint`` (juniper-data W-4) is the same string the generator's guarded
    ``ImportError`` carries and the same text the 501 on ``POST /v1/datasets`` returns, so it is
    the one place the remedy is stated by the party that knows it. Reading it here is what stops
    canopy re-wording a curated string it does not own.

    Returns None for a generator that declares no optional dependency, for one missing from the
    list, and for a juniper-data older than W-4 that sends no hint — all of which are "nothing
    actionable to add", not errors.
    """
    name = generator_name_for_type(value)
    if not name:
        return None
    for entry in generators or ():
        if isinstance(entry, Mapping) and entry.get("name") == name:
            hint = entry.get("install_hint")
            return hint if isinstance(hint, str) and hint.strip() else None
    return None


def unavailable_reason(value: str | None, generators: Sequence[Mapping[str, Any]] | None = None) -> str:
    """Short UI reason a generator is greyed — for the dropdown label, which has no room for more.

    Derived from the wire first: a generator the producer published an install hint for needs an
    optional extra, and says so without canopy hand-maintaining a per-generator string. The
    curated map speaks only when the producer published nothing (a pre-W-4 juniper-data), and the
    generic phrase only when neither does.

    ``generators`` is optional so the existing call shape keeps working; omitting it simply means
    the wire cannot be consulted and the curated/generic path is taken. The ACTIONABLE text —
    the pip command — is ``unavailable_hint``, rendered where there is room for it.
    """
    name = generator_name_for_type(value)
    if unavailable_hint(value, generators):
        return _UNAVAILABLE_REASON_HAS_HINT
    return _UNAVAILABLE_REASONS.get(name, _UNAVAILABLE_REASON_DEFAULT)


def apply_availability_gate(options: Sequence[Mapping[str, Any]], generators: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Disable unavailable dataset options in a model-compat option list, with a reworded reason.

    Composition rule: an option already ``disabled`` (a model-incompatibility gate — the primary
    D5 correctness gate) is left untouched (no double reason). An enabled option whose generator is
    unavailable becomes ``disabled`` with an availability reason appended to its label. Available
    options pass through unchanged. Pure over the option dicts (``{"label","value",...}``) so the
    dashboard can compose it after ``model_registry.gated_dataset_options``.
    """
    gated: list[dict[str, Any]] = []
    for option in options:
        out = dict(option)
        value = out.get("value")
        if not out.get("disabled") and not is_generator_available(value, generators):
            base = out.get("label", value)
            out["label"] = f"{base} — {unavailable_reason(value, generators)}"
            out["disabled"] = True
        gated.append(out)
    return gated
