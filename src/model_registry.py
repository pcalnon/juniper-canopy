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
#     - task_type uses juniper-data's emitted vocabulary, which is THREE values as of
#       2026-09-15: "classification" / "regression" / "structured"
#       (juniper_data/core/meta.py:38,41,59). This registry seeds only the first two —
#       "structured" arrived with juniper-data#402 for arc_agi, whose y is a 900-cell grid
#       rather than a class vector, and arc_agi stays unseeded. Note that NO ModelSpec
#       lists "structured" in supported_task_types, so a future structured generator is
#       compatible with nothing here and would grey out everywhere. Seeding one now FAILS
#       test_every_seeded_dataset_has_a_compatible_model (tests/unit/test_model_registry.py)
#       instead of greying out silently: add the model that accepts it first.
#       The recurrence model's 3-D / irregular-delta-t nature is carried by ndim +
#       requires_dt, NOT by a task_type label.
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
#     - G11: GeneratorBound + SEEDED_GENERATOR_BOUNDS — one boundedness classification per seeded
#       generator, enforced over every seed by TestG11EverySeedIsBounded.
#
#####################################################################################################################################################################################################
"""Model + dataset-type registry (single source of truth) for model selection.

A0 scope: spec dataclasses + seeds + ``dataset_type_options()``. A1-iv-1 adds the pure,
browser-free compatibility engine (``compatible`` + ``temporal_ok`` + the
``compatible_models`` / ``compatible_datasets`` resolvers) — the §4 correctness guarantee.
See the module header and the design-of-record note for the full design.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatasetTypeSpec:
    """A selectable dataset type and the properties that gate model compatibility."""

    value: str  # stable id sent to the backend (e.g. "spirals")
    label: str  # human-facing label (e.g. "Spirals")
    task_type: str  # juniper-data vocabulary: "classification" | "regression" | "structured"
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


@dataclass(frozen=True)
class GeneratorBound:
    """How one seeded juniper-data generator's request is bounded — a G11 classification.

    ``bounding_keys`` EMPTY: the generator synthesises from its own parameters (or loads a fixed
    corpus), so its own defaults bound it and its seed may be ``{}``; ``reason`` says why.

    ``bounding_keys`` NON-EMPTY: the generator pulls an operator-sized universe and is bounded ONLY
    by what the request pins, so its seed must set at least one of these ``default_params`` keys to
    a bounded value; ``reason`` says what it would pull otherwise.

    See ``SEEDED_GENERATOR_BOUNDS``, the one entry per seeded generator that this describes.
    """

    reason: str
    bounding_keys: frozenset[str] = frozenset()


# Selectable dataset types. The order is user-facing; the five 2-D classification types come
# first (spirals = default), preserving the original inlined dropdown order. A1-iv-3b appends
# the 3-D irregular-delta-t regression seed (``equities_seq``) so the recurrence (LMU) model
# has a compatible dataset; the sidebar gate (``gated_dataset_options``) greys it for 2-D models.
#
# §12 (design "Iteration 2 — closing the generator gap") adds the five rank-3 SYNTHETIC
# sequence generators. Two things about their placement are deliberate:
#
#   * They sit BEFORE ``equities_seq``, and what that order decides changed on 2026-09-22.
#     Until canopy#652, ``_gate_dataset_options_handler`` snapped a stranded sidebar dataset to
#     ``enabled[0]`` — the first compatible AND available entry — so this order chose the
#     dataset the operator landed on when they picked Recurrence. OQ-6 was ratified that day
#     as model-primary with a CLEAR (§5.6.1 of juniper-ml's
#     JUNIPER_2026-06-17_JUNIPER-CANOPY_MODEL-DATASET-SELECTION-DESIGN.md): the sidebar now
#     drops a stranded dataset to ``⊥`` and the operator chooses, so this order no longer
#     decides where the SIDEBAR lands on a model change. It still decides two things:
#       - the order the dropdown OFFERS, so ``multi_sine`` is the first enabled option under
#         Recurrence; and
#       - the restart modal's fallback. ``_open_restart_confirm_modal_handler`` keeps its
#         swap by owner ruling (2026-09-22), a deliberate exception to OQ-6: a stranded,
#         non-``⊥`` sidebar dataset is replaced there by ``enabled[0]``, so this order picks
#         the replacement.
#     Measured 2026-09-09, the first enabled entry is ``multi_sine``: generate 0.0s, fit
#     0.10s, r² 1.000. ``equities_seq`` is 40.5s and r² -0.004, and is ``available=false`` in
#     the deployed container: juniper-deploy pins juniper-data 0.15.0, whose image lacks
#     ``yfinance`` (juniper-data#421 added it to the image lock on main on 2026-09-22; no
#     release carries it yet). That is why selecting Recurrence there used to raise §4.7's "no
#     dataset is available for this model" alert. These five declare no ``is_available`` hook,
#     so they are available everywhere.
#   * They carry NO ``default_params``, and that is correct rather than an omission — see
#     ``SEEDED_GENERATOR_BOUNDS`` below (G11), which classifies each of them as bounded by its
#     own defaults: 1,574 windows of (32, 1), generated and fitted in ~0.1s total against a
#     300s timeout.
#
# ``task_type="regression"`` matches what juniper-data declares for all five, so these seeds
# introduce no vocabulary disagreement. ``equities_seq`` agrees too since juniper-data#437
# relabelled it (generator 6.0.0, owner ruling 2026-09-24), which closed the X8 divergence.
# All five are rank-3, so cascor (``input_ndim={2}``) rejects them and the compatibility graph
# keeps exactly two components — §12.2's "this expansion adds no deadlock surface", now measured.
DATASET_TYPES: tuple[DatasetTypeSpec, ...] = (
    DatasetTypeSpec(value="spirals", label="Spirals", task_type="classification", ndim=2),
    DatasetTypeSpec(value="xor", label="XOR", task_type="classification", ndim=2),
    # ``flatten=True`` is SEEDED, not merely inherited. juniper-data's own default is True today,
    # so this is a no-op against the current producer — but ``ndim=2`` above is a static claim,
    # and leaving it true by upstream coincidence is what made this a defect in the first place
    # (canopy#623). Seeded here, canopy SENDS the value that makes its own declaration true; the
    # knob is withheld from the form by ``SHAPE_DETERMINING_FIELDS`` so nothing can override it.
    DatasetTypeSpec(value="mnist", label="MNIST", task_type="classification", ndim=2, default_params={"flatten": True}),
    DatasetTypeSpec(value="circles", label="Circles", task_type="classification", ndim=2),
    DatasetTypeSpec(value="moons", label="Moons", task_type="classification", ndim=2),
    # --- §12 rank-2 synthetics. Validated 2026-09-10 the way §12.4 requires: generated through
    # juniper-data to an NPZ artifact, then fitted with CascadeCorrelationNetwork (input_size /
    # output_size taken from the data; max_iterations 8; max_epochs AND output_epochs both 60,
    # per the resident hazard that setting only the former leaves later passes at 10000).
    #
    # ``gaussian``      1 hidden unit, loss 0.0231 -> 0.0016, train top-1 1.000 in 0.4s.
    # ``checkerboard``  at its OWN default of 200 samples over a 4x4 grid CasCor recruits ONE
    #                   unit and sits at chance (top-1 0.515, loss flat to four decimals). At
    #                   n_samples=2000 it recruits EIGHT and the loss moves (0.2496 -> 0.2418,
    #                   top-1 0.5425). The dataset is fine; 200 samples over 16 cells is simply
    #                   too thin to recruit against. ``n_samples`` is a rendered schema field, so
    #                   raising it is an operator action, not a code change.
    #
    # Both stay ``default_params={}``, matching the five incumbents. Neither imports an external
    # universe, so ``SEEDED_GENERATOR_BOUNDS`` below (G11) classifies both as bounded by their
    # own defaults.
    DatasetTypeSpec(value="gaussian", label="Gaussian Blobs", task_type="classification", ndim=2),
    DatasetTypeSpec(value="checkerboard", label="Checkerboard", task_type="classification", ndim=2),
    # ``equities`` — the rank-2 sibling of ``equities_seq``, and the seed that forced the cascor
    # path to learn to carry ``default_params`` at all. Until then the registry seed reached only
    # the recurrence tier, so a rank-2 dataset needing params could not be expressed: every Apply
    # sent bare defaults and 422'd. All three keys were measured 2026-09-10/11 against a live
    # juniper-data and a real CascadeCorrelationNetwork fit at generator ``3.0.0``, and the seed
    # was re-measured at ``5.0.0`` on 2026-09-22 (below):
    #
    # ``symbols``            — bare defaults are REFUSED, not truncated: the bundled 503-name
    #                          universe exceeds the deployment cap of 14 and juniper-data raises
    #                          InputTooLargeError -> 422. ``max_symbols`` does not rescue this;
    #                          it IS the cap being exceeded. This key is an ARRAY, which
    #                          ``_field_from_property`` deliberately does not render — so it can
    #                          only travel as a registry seed, and that is precisely why the
    #                          form-only payload could never carry this dataset.
    # ``fundamentals_fill``  — the juniper-data default ``"nan"`` leaves non-finite columns
    #                          (total_shares / market_cap / days_since_report).
    # ``normalize_features`` — defaults to False, and equities' columns are raw market
    #                          quantities. Unnormalised, CasCor's first output pass reports a
    #                          loss of 8.21e+21 against 0.2498 normalised at ``5.0.0`` —
    #                          twenty-two orders of magnitude, as it was at ``3.0.0`` (5.83e+21
    #                          against 0.2511). This key has no analogue in the sequence
    #                          sibling's seed.
    #
    # Measured on the seed as written, 2026-09-22, at generator ``5.0.0`` (juniper-data main
    # 68c3cd7), through the service's own path (``params_class`` -> ``bind_deployment_defaults``
    # -> ``generate``) with a cold download cache: generate 13.2s (1.3s warm); X_train
    # (15877, 15), X_val (1986, 15), X_test (1982, 15), a one-hot (n, 2) target, float32, ZERO
    # non-finite in any split. The matrix is 15 columns where ``3.0.0``'s was 16, because
    # juniper-data#395 (``4.0.0``) dropped ``adj_close`` from the default feature set. Row
    # counts move with the calendar: ``end_date`` defaults to the day of generation (2026-09-23
    # UTC here). CasCor, under the bounded trainability probe of juniper-ml's
    # ``util/ad-hoc/2026-09-10_rank2_cascor_fit.py`` (4,000-row train subsample,
    # ``max_iterations`` 8, ``max_epochs`` AND ``output_epochs`` both 60), fits in 5.4s
    # recruiting 4 units (loss 0.2498 -> 0.2482). Fit time is host-dependent; it is a
    # trainability probe, not a benchmark. Train top-1 0.5375 is the honest ceiling for next-day
    # direction, not a defect — the same story as the sequence sibling's r² near zero.
    #
    # Unavailable in the deployed container: juniper-deploy pins juniper-data 0.15.0, whose image
    # lacks the ``equities`` extra's ``yfinance``, so this renders greyed with an install hint
    # there. That is the availability gate doing its job (§12.5), not a broken seed.
    # juniper-data#421 added ``yfinance`` to the image lock on main on 2026-09-22; this becomes
    # available in the container once a juniper-data release carries it and the pin moves.
    DatasetTypeSpec(
        value="equities",
        label="Equities (tabular)",
        task_type="classification",
        ndim=2,
        default_params={
            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
            "fundamentals_fill": "drop",
            "normalize_features": True,
        },
    ),
    # --- §12 rank-3 synthetics. r² is the LMU's fit at the service's effective defaults
    # (d=16, data-driven theta, ridge=0.0), measured 2026-09-09; it is recorded because a
    # generator that fits but learns nothing must not be mistaken for a good default.
    DatasetTypeSpec(value="multi_sine", label="Multi-Sine (sequence)", task_type="regression", ndim=3, temporal="regular"),  # r² 1.000
    DatasetTypeSpec(value="mackey_glass", label="Mackey-Glass (sequence)", task_type="regression", ndim=3, temporal="regular"),  # r² 0.9999
    DatasetTypeSpec(value="irregular_sine", label="Irregular Sine (sequence)", task_type="regression", ndim=3, temporal="irregular"),  # r² 0.9918
    DatasetTypeSpec(value="ar_p", label="AR(p) (sequence)", task_type="regression", ndim=3, temporal="regular"),  # r² 0.043 — a noisy AR process has a low ceiling
    DatasetTypeSpec(value="delay_product", label="Delay Product (sequence)", task_type="regression", ndim=3, temporal="irregular"),  # r² 0.004 — multiplicative target, linear readout
    DatasetTypeSpec(
        value="equities_seq",
        label="Equities (sequence)",
        task_type="regression",
        ndim=3,
        temporal="irregular",
        # Bounded + stationary + FINITE, so the one-shot fit actually runs. Each key is load-bearing
        # and was measured, not reasoned about (design §12.4: a count is not a measured capability).
        #
        # ``symbols`` — NOT ``max_symbols``. ``max_symbols`` is a CAP that REFUSES, not a truncator:
        #   juniper-data compares it against the requested universe (the bundled 503 names) and
        #   raises InputTooLargeError -> HTTP 422 unless ``allow_truncation`` is set. The previous
        #   ``{"max_symbols": 5}`` therefore generated NOTHING, in 0.0s, on every Start — which is
        #   why the pair had never once trained end to end. juniper-ml's
        #   tests/test_equities_symbol_cap_operator.py names this exact trap ("max_symbols alone
        #   does not save a default-universe cell") and warns off the allow_truncation escape,
        #   because enabling it deployment-wide opts everything into silent prefix cuts. An explicit
        #   short list is the remedy it prescribes; juniper-recurrence's own bench does the same.
        #   Five names also sit under the deployment ceiling (14), so the cap keeps its guard value.
        #
        # ``fundamentals_fill="drop"`` — the juniper-data default is ``"nan"``, and at that default
        #   X_train comes back 9.1% NON-FINITE while X_val and X_test are entirely clean. The LMU
        #   refuses it outright (``ValueError: u must be finite``), so fixing only the cap above
        #   moves the failure from generation to the fit rather than removing it. The non-finite
        #   columns are exactly EQUITIES_FEATURE_COLUMNS[7], [8] and [15] — total_shares, market_cap
        #   and days_since_report. NB the schema calls these "pre-2009 missing", but that is not the
        #   whole story: ``start_date="2010-01-01"`` still yields 299,808 non-finite cells, so a
        #   later start does NOT substitute for this key. ``drop`` beats ``zero`` on every measured
        #   axis (fit 39.6s vs 77.3s, r² -0.004 vs -0.034) and, unlike ``zero``, invents no
        #   market caps for the model to fit against. Dropping rows is safe for a SEQUENCE dataset
        #   here because the generator emits per-step dt and this seed is ``temporal="irregular"``:
        #   a gap is representable, which is the whole point of the requires_dt path.
        #
        # ``regression_target="return"`` — unchanged; the stationary target (the raw next_close
        #   default extrapolates badly on trending prices — the recurrence equities readout finding).
        #
        # Measured 2026-09-09 on this seed: generate 0.9s, fit 39.6s, 15,476 train windows of
        # (64, 16) — 40.5s against the 300s train timeout. r² near zero is the honest outcome for
        # next-day equity returns, not a defect; it is also why this seed demonstrates little, and
        # why the §12 synthetic rank-3 generators are the better showcase for the LMU.
        #
        # Re-generated 2026-09-22 at generator ``5.0.0``, by the same method as ``equities``
        # above: 15,557 train windows of (64, 15), ZERO non-finite in any split. The (64, 16)
        # above, and the index [15] under ``fundamentals_fill``, are ``3.0.0``'s: ``4.0.0``
        # dropped ``adj_close``, so ``days_since_report`` is EQUITIES_FEATURE_COLUMNS[14] now.
        # The LMU fit (39.6s, r² -0.004) was NOT re-measured.
        default_params={
            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
            "regression_target": "return",
            "fundamentals_fill": "drop",
        },
    ),
)

# Default dataset type — preserves the prior hardcoded value="spirals".
DEFAULT_DATASET_TYPE: str = DATASET_TYPES[0].value

# --- G10 / G11 (design §12) -------------------------------------------------------------
#
# G10: every generator juniper-data registers is either seeded in ``DATASET_TYPES`` above or
# named HERE with the reason it is not. The point is not bookkeeping — it is that "why is X
# not in the dropdown?" currently has no answer anywhere, so an unseeded generator is
# indistinguishable from a forgotten one.
#
# This is a DATED SNAPSHOT of juniper-data's registry, taken 2026-09-09 by executing it
# (16 generators), and re-checked 2026-09-22 by executing juniper-data main 68c3cd7's
# ``GENERATOR_REGISTRY`` (``api/routes/generators.py``): the same 16 names, none added or
# removed. It is deliberately not derived from an installed ``juniper_data``: canopy
# talks to that service over HTTP and has no version contract with the library, and the copy
# installed in the test env is 0.6.0 — old enough to predate ``equities_seq`` — so asserting
# against it would produce false reds on a stale dependency rather than on real drift. The
# LIVE check is ``/api/dataset/generators`` at runtime; this is the CI-visible half.
KNOWN_UPSTREAM_GENERATORS: frozenset[str] = frozenset(
    {
        "spiral",
        "xor",
        "gaussian",
        "circles",
        "moon",
        "checkerboard",
        "csv_import",
        "equities",
        "equities_seq",
        "multi_sine",
        "mackey_glass",
        "ar_p",
        "irregular_sine",
        "delay_product",
        "mnist",
        "arc_agi",
    }
)

# Generators deliberately NOT offered in the dataset dropdown, each with the reason.
UNSEEDED_GENERATORS: dict[str, str] = {
    "csv_import": ("An import path, not a peer generator: it has no synthesisable default (``file_path`` is " "required, so calling it with defaults raises a ValidationError) and canopy already owns " "that flow in ``dataset_import.py``. Design §12.3 item 4."),
    "arc_agi": (
        "Its ``y`` IS NOT A CLASS VECTOR. ``y`` is the stacked padded ``output_grid`` — the same "
        "shape as ``X``, so flattened it is ``(n, pad_to*pad_to)``: 900 cells valued in [-1..9], "
        "not a 10-way one-hot (juniper-data ``generators/arc_agi/generator.py``). It is a "
        "grid-to-grid map, and no model here consumes that: the rank-2 install path takes "
        "``np.argmax(y, axis=1)`` and would yield a 'class label' in [0, 900). Upstream declared "
        "it ``task_type='classification'`` until juniper-data#402, which added a third task type "
        "and moved it to ``'structured'`` — so the producer's metadata no longer fabricates an "
        "``n_classes`` of 900, and no model's ``supported_task_types`` contains ``'structured'``. "
        "That makes the incompatibility EXPLICIT rather than incidental, and it is why this stays "
        "unseeded. "
        "Its rank is ALSO parameter-dependent (``flatten_pairs`` flips rank-2/rank-3), but that "
        "is a secondary UI hazard it shares with the SEEDED ``mnist`` (``flatten``), now handled "
        "for both by withholding the knob — see ``SHAPE_DETERMINING_FIELDS`` in dataset_schema.py "
        "and canopy#623. Rank was never the blocker; design §12.9 records why widening "
        "``DatasetTypeSpec.ndim`` would not have helped."
    ),
}

# G11, restated — and now given a constant, because code reads it.
#
# Until 2026-09-22 this comment said G11 was "deliberately NOT given a constant of its own,
# because a set no code reads is a rule nobody enforces" — while the seed comment above pointed its
# reader at an ``UNBOUNDED_IMPORT_GENERATORS`` that existed nowhere. The tests that touched G11
# enumerated the seeds they knew; nothing iterated ``DATASET_TYPES`` asserting boundedness, so a
# fifteenth seed with unbounded ``default_params`` passed every test, and the design's §5 table
# recorded G11 as
# "passes" — a vacuous pass. The remedy is the one that comment named: a constant that code reads.
# ``TestG11EverySeedIsBounded`` in tests/regression/test_dataset_generator_contract.py iterates
# ``DATASET_TYPES`` and fails on a seed whose generator has no entry below, and on an
# unbounded-import seed that does not pin one of its bounding keys to a bounded value — the same
# forced decision per generator that G10 makes with ``UNSEEDED_GENERATORS``.
#
# The design's wording ("every seeded generator has bounded ``default_params``") overshoots: it
# fails on the five incumbent 2-D seeds, which carry ``{}`` and always have, and it would fail on
# the five §12 synthetics too. Measurement shows why. The unbounded axis is never the generator's
# PARAMETERS; it is the size of whatever the request asks a generator to bring in from outside.
# A generator that synthesises from its own parameters is bounded by its own defaults — the rank-3
# five produce 1,574 windows in ~0.1s end to end. A generator that pulls an operator-sized UNIVERSE
# is bounded only by what the request pins, and ``equities_seq`` at its defaults asks for 503
# symbols and is refused outright.
#
# That is narrower than "imports data": ``mnist`` also downloads, but it downloads a FIXED corpus
# and ``n_samples`` only subsamples it, so ``{}`` is right for it. The generators the rule actually
# binds are the equities pair, bounded by ``symbols``. ``max_symbols`` is deliberately NOT a
# bounding key: it is the cap juniper-data refuses against, not a truncator.
# ``TestEquitiesSeedIsGenerableAndFinite`` (same test module) pins the rest of what their seeds
# must carry to generate and fit.
#
# Keyed by juniper-data generator NAME (``generator_name_for_type`` of a seed's value), like G10's
# lists: boundedness is a property of the generator, not of canopy's label for it.
SEEDED_GENERATOR_BOUNDS: dict[str, GeneratorBound] = {
    # Rank-2 synthetics: every point comes from the generator's own size parameters.
    "spiral": GeneratorBound("Synthesises every point from its own parameters (2 spirals x 97 points at its defaults) and fetches nothing."),
    "xor": GeneratorBound("Synthesises every point from its own parameters (50 points per quadrant at its defaults) and fetches nothing."),
    "circles": GeneratorBound("Synthesises every point from its own parameters (n_samples=100 at its defaults) and fetches nothing."),
    "moon": GeneratorBound("Synthesises every point from its own parameters (n_samples=200 at its defaults) and fetches nothing."),
    "gaussian": GeneratorBound("Synthesises every point from its own parameters (2 classes x 50 samples at its defaults) and fetches nothing."),
    "checkerboard": GeneratorBound("Synthesises every point from its own parameters (n_samples=200 at its defaults) and fetches nothing."),
    # Downloads — but a FIXED corpus, which is why the rule is narrower than "imports data".
    "mnist": GeneratorBound("Downloads, but a FIXED corpus: the Hugging Face train split, whatever the request asks; n_samples only subsamples it."),
    # Rank-3 synthetics.
    "multi_sine": GeneratorBound("Synthesises its series from its own parameters (n_steps=2000 at its defaults) and fetches nothing."),
    "mackey_glass": GeneratorBound("Synthesises its series from its own parameters (n_steps=2000 at its defaults) and fetches nothing."),
    "irregular_sine": GeneratorBound("Synthesises its series from its own parameters (n_steps=2000 at its defaults) and fetches nothing."),
    "ar_p": GeneratorBound("Synthesises its series from its own parameters (n_steps=2000 at its defaults) and fetches nothing."),
    "delay_product": GeneratorBound("Synthesises its series from its own parameters (n_steps=2000 at its defaults) and fetches nothing."),
    # The universe importers: bounded ONLY by what the seed pins.
    "equities": GeneratorBound(
        "Pulls an operator-sized universe: with no symbols it asks for all 503 bundled constituents, which a default juniper-data deployment refuses (422) against its 14-symbol ceiling.",
        bounding_keys=frozenset({"symbols"}),
    ),
    "equities_seq": GeneratorBound(
        "Pulls an operator-sized universe: with no symbols it asks for all 503 bundled constituents, which a default juniper-data deployment refuses (422) against its 14-symbol ceiling.",
        bounding_keys=frozenset({"symbols"}),
    ),
}

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


def dataset_type_options(*, dataset_types: tuple[DatasetTypeSpec, ...] = DATASET_TYPES) -> list[dict[str, str]]:
    """Return the dataset-type dropdown options as ``[{"label", "value"}, ...]``.

    Single source for the ``nn-dataset-type-dropdown`` options (previously inlined in
    ``dashboard_manager``). Order is preserved for behavior parity. ``dataset_types`` is
    injectable for tests (design §5 enabling change).
    """
    return [{"label": spec.label, "value": spec.value} for spec in dataset_types]


def dataset_default_params(value: str, *, dataset_types: tuple[DatasetTypeSpec, ...] = DATASET_TYPES) -> dict[str, object]:
    """Return a copy of the one-shot start params seeded for dataset ``value`` (A1-iv-3c).

    The recurrence (one-shot) Start button forwards these as the juniper-data ``generator``
    params so the fit is bounded + stationary (see ``DatasetTypeSpec.default_params``). A copy
    is returned so a caller can never mutate the registry seed. Unknown ``value`` → ``{}``.
    ``dataset_types`` is injectable for tests (design §5 enabling change).

    **Deep**, not ``dict(...)``. A shallow copy was sufficient while every seed value was a
    scalar; ``equities_seq`` now seeds a ``symbols`` LIST, and a shallow copy hands every
    caller the same list object as the frozen registry constant — so one
    ``params["symbols"].append(...)`` anywhere would rewrite the seed for the life of the
    process, and the next Start would send a universe nobody chose. Replacing a key is the
    only mutation callers perform today (``dataset_ref_from_staged`` uses ``update``), so
    this costs nothing and closes the aliasing hole before it is opened.
    """
    for spec in dataset_types:
        if spec.value == value:
            return copy.deepcopy(dict(spec.default_params))
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


def get_model_spec(key: str, *, models: tuple[ModelSpec, ...] = MODELS) -> ModelSpec | None:
    """Return the :class:`ModelSpec` for ``key`` (matching ``key`` or an alias), or None.

    Used by the backend factory (``backend.create_backend``) to resolve a selected model
    key to its provider for routing, and available to the A1 selection UI for lookups.
    ``models`` is injectable for tests (design §5 enabling change).
    """
    for spec in models:
        if key == spec.key or key in spec.aliases:
            return spec
    return None


# ``backend.backend_type`` of the live backend when the recurrence service backend is the one
# running. The other two values the property can take ("service", "demo") both serve the
# cascor-family models -- there is no "cascor" backend type, and a guardrail that parametrises
# on one covers nothing.
RECURRENCE_BACKEND_TYPE: str = "recurrence"


def selection_is_live(model_key: str | None, backend_type: str | None, *, models: tuple[ModelSpec, ...] = MODELS) -> bool | None:
    """Whether the live backend actually serves the selected model (design N5 / X1).

    Provider agreement: a recurrence-provider model is live iff the recurrence backend is, and a
    cascor-family model is live iff it is not. ``swapped`` from ``POST /api/model/select`` is the
    WRONG predicate for this -- it is also ``False`` on the healthy path where the user re-selects
    the model already running -- so it is deliberately not consulted.

    Returns ``None`` when either side is unknown: no ``backend_type`` (the first-paint seed, which
    has never round-tripped) or no ``model_key`` (a cleared model). Unknown is not disagreement;
    a caller that treated it as one would trade a silent lie for a loud one.

    Shared by the sidebar summary (``DashboardManager._selection_is_live``), the Start gate
    (``_update_button_appearance_handler``) and the server's start paths (``main.py``), so the
    label, the control and the run cannot answer this question differently -- which is exactly
    how canopy#592 came to fix the label while the run stayed misattributed.
    """
    if model_key is None or model_key == "" or not backend_type:
        return None
    spec = get_model_spec(model_key, models=models)
    selection_needs_recurrence = spec is not None and spec.provider == RECURRENCE_PROVIDER
    return selection_needs_recurrence == (backend_type == RECURRENCE_BACKEND_TYPE)


def get_dataset_spec(value: str, *, dataset_types: tuple[DatasetTypeSpec, ...] = DATASET_TYPES) -> DatasetTypeSpec | None:
    """Return the :class:`DatasetTypeSpec` for ``value``, or None (symmetric with get_model_spec).

    Used by the A1b model-selection surface to resolve the currently-selected dataset value to
    its spec so the per-model compatibility cell (``model_reason``) can be computed against it.
    ``dataset_types`` is injectable for tests (design §5 enabling change).
    """
    for spec in dataset_types:
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

    Y8: whether there IS a reason is ``compatible()``'s verdict, not re-derived here. The axis
    checks below only choose the wording, so they can never disagree with the predicate about
    which pairs are incompatible. An axis ``compatible()`` gains without a phrase here gets the
    generic wording rather than ``None``, because ``None`` on an incompatible pair would put a
    disabled option in the dropdown with no reason on it.
    """
    if compatible(dataset, model):
        return None
    if dataset.ndim not in model.input_ndim:
        return f"needs a {dataset.ndim}-D model"
    if dataset.task_type not in model.supported_task_types:
        return f"needs a {dataset.task_type} model"
    if not temporal_ok(dataset, model):
        return "needs a Δt-aware model"
    return "not compatible with this model"


def model_reason(model: ModelSpec, dataset: DatasetTypeSpec) -> str | None:
    """Model-perspective incompatibility reason for the model-table cell (A1b-1; D2/§5.2).

    Returns ``None`` when ``model`` is compatible with ``dataset``; otherwise a short
    "needs … data" phrase naming the first failing axis — what KIND of data this model needs
    that the current dataset does not supply. This is the model-perspective inverse of
    ``dataset_reason`` (which names what kind of model a dataset needs); the phrase sits in the
    model row's compatibility cell (e.g. "Recurrence (LMU) — needs 3-D data" against a 2-D
    dataset). The axis order mirrors ``dataset_reason`` so the two stay consistent.

    Y8: as in ``dataset_reason``, whether there IS a reason is ``compatible()``'s verdict; the
    axis checks only choose the wording, and an axis they do not name gets the generic phrase.
    """
    if compatible(dataset, model):
        return None
    if dataset.ndim not in model.input_ndim:
        dims = " or ".join(f"{n}-D" for n in sorted(model.input_ndim))
        return f"needs {dims} data"
    if dataset.task_type not in model.supported_task_types:
        tasks = " or ".join(sorted(model.supported_task_types))
        return f"needs {tasks} data"
    if not temporal_ok(dataset, model):
        return "needs regularly-sampled data"
    return "not compatible with this dataset"


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


def gated_dataset_options(model_key: str, *, models: tuple[ModelSpec, ...] = MODELS, dataset_types: tuple[DatasetTypeSpec, ...] = DATASET_TYPES) -> list[dict[str, object]]:
    """Dataset-dropdown options gated against the selected model (A1-iv-3b).

    Compatible dataset types are plain, selectable options; incompatible ones are ``disabled``
    with a reason-suffix label (D2). Single source for the initial render (``DEFAULT_MODEL_KEY``)
    and the runtime gate callback. An unknown ``model_key`` (no spec) falls back to ungated
    options so a desync never hides every dataset.

    Both registries are injectable for tests (design §5 enabling change) — and they must travel
    TOGETHER: resolving the model against a synthetic registry while iterating the production
    dataset seeds would silently score a graph that exists nowhere.

    Y8: ``disabled`` is decided by ``compatible()`` — the load-bearing predicate — and
    ``dataset_reason`` is consulted only for the wording of an option already judged
    incompatible. Deciding it from whether a reason string came back made a presentation helper
    the second, independent expression of the gate.
    """
    spec = get_model_spec(model_key, models=models)
    options: list[dict[str, object]] = []
    for dataset in dataset_types:
        if spec is None or compatible(dataset, spec):
            options.append({"label": dataset.label, "value": dataset.value})
        else:
            options.append({"label": f"{dataset.label} — {dataset_reason(dataset, spec)}", "value": dataset.value, "disabled": True})
    return options
