#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_dataset_generator_contract.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-07
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Guardrail G4 (re-specified) — canopy's dataset
#                values reach juniper-data under the right names —
#                plus the X6 staging guard and the X8 task_type
#                tripwire.
#####################################################################
"""G4 — canopy's dataset vocabulary reaches juniper-data under juniper-data's names.

Design of record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md`` §4.6, §4.9,
§5 (G4).

**G4 is re-specified here, deliberately.** The design predicted it would "fail before" because
``spirals``/``moons`` are not registry keys — but as worded (*through* ``generator_name_for_type``)
it already passed: the alias map shipped at ``dataset_schema.py:97-100``. The consensus audit
recorded that as refutation R3. What the design *meant* to catch is drift between canopy's values
and the names it sends upstream, so that is what is asserted: the resolution is total, the alias map
carries no dead entries, and — the actual X3 defect — the one-shot body sends the RESOLVED name.

**Why this is not tested against an installed ``juniper_data``.** That package is importable in the
canopy test env, but it is incidental: canopy talks to juniper-data over HTTP through
``juniper-data-client`` and has no version contract with the library. The copy installed here is
0.6.0, whose registry has 8 generators and contains neither ``moon`` nor ``equities_seq``, so a
subset assertion against it would fail on a stale dependency rather than on real drift — a false
red, which is worse than no test. The live contract is checked at runtime against
``/api/dataset/generators``; this suite checks the half canopy owns.
"""

from unittest import mock
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import main
from dataset_schema import FORM_EXCLUDED_FIELDS, GENERATOR_NAME_ALIASES, PARTIAL_DATA_POLICY_FIELDS, SHAPE_DETERMINING_FIELDS, form_excluded_fields, generator_name_for_type, parse_schema_fields
from frontend.dashboard_manager import DATASET_SHORTFALL_OPTIONS, DashboardManager
from model_registry import DATASET_TYPES, KNOWN_UPSTREAM_GENERATORS, MODELS, SEEDED_GENERATOR_BOUNDS, UNSEEDED_GENERATORS, compatible_models, get_dataset_spec


@pytest.mark.regression
@pytest.mark.unit
class TestG4GeneratorNameResolution:
    """Every canopy dataset value reaches juniper-data under a resolvable name."""

    @pytest.mark.parametrize("spec", DATASET_TYPES, ids=lambda s: s.value)
    def test_every_dataset_value_resolves_to_a_name(self, spec):
        assert generator_name_for_type(spec.value)

    def test_the_alias_map_has_no_dead_entries(self):
        # An alias for a value canopy no longer offers is a rename that was only half done: the
        # entry keeps working, so nothing fails, and the next reader cannot tell whether the value
        # is retired or merely unused.
        values = {spec.value for spec in DATASET_TYPES}
        assert set(GENERATOR_NAME_ALIASES) <= values, f"aliases for unknown dataset values: {sorted(set(GENERATOR_NAME_ALIASES) - values)}"

    @pytest.mark.parametrize("value,target", sorted(GENERATOR_NAME_ALIASES.items()))
    def test_every_alias_actually_renames_something(self, value, target):
        # An identity alias is dead weight and hides the fact that the two vocabularies agree here.
        assert value != target


@pytest.mark.regression
@pytest.mark.unit
class TestX3OneShotBodyUsesTheResolvedName:
    """§4.6 — the one-shot Start body sent canopy's value where juniper-data's name belongs."""

    def test_an_aliased_dataset_is_sent_under_its_upstream_name(self):
        # THE regression. Masked in production only because ``equities_seq`` -- the one dataset a
        # one-shot model can currently reach -- is identity-mapped. The handler must not depend on
        # which datasets happen to be reachable today.
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "spirals")
        assert body["dataset"]["generator"] == "spiral"

    def test_params_are_looked_up_under_canopy_s_value_not_the_upstream_name(self):
        # The asymmetry that makes this easy to "fix" wrongly: canopy's registry is keyed on
        # canopy's values, so translating the params lookup too would silently drop the seeded
        # default_params -- and equities_seq cannot generate OR fit without them (``symbols``
        # clears juniper-data's universe cap, ``fundamentals_fill`` keeps X_train finite; see
        # TestEquitiesSeedIsGenerableAndFinite below).
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        seeded = get_dataset_spec("equities_seq").default_params
        if seeded:
            assert body["dataset"]["params"] == seeded

    def test_a_live_model_still_sends_no_dataset_ref(self):
        assert DashboardManager._resolve_oneshot_start_body_handler("live", "spirals") is None

    def test_the_STAGING_payload_must_NOT_be_translated(self):
        """The counter-guard, and the reason this fix is not symmetric.

        Two wire channels with two vocabularies. The one-shot body reaches **juniper-data** (the
        recurrence service passes ``generator`` straight to ``client.create_dataset``), so it needs
        juniper-data's name. The staging payload reaches **cascor**, whose ``dataset_type`` is a
        ``Literal["spirals", ..., "moons", ...]`` -- canopy's PLURAL dialect. Translating that one
        too, in the name of consistency, would send ``"spiral"`` to a field that does not accept it.

        The design describes both sibling handlers as "applying the alias", which is true but for a
        different purpose: they use it for schema LOOKUP against juniper-data, never to build a
        payload bound for cascor.
        """
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = MagicMock(ok=True, status_code=200, text="{}")
            post.return_value.json.return_value = {}
            DashboardManager({})._apply_dataset_handler(1, "spirals", 100, 0.1, 2.0, 2)
        sent = post.call_args.kwargs["json"]
        assert sent["nn_dataset_type"] == "spirals", "cascor's Literal takes canopy's value, not juniper-data's"


@pytest.mark.regression
@pytest.mark.unit
class TestX6StagingIsGuarded:
    """§4.9 — a backend that cannot stage says so, instead of 500-ing opaquely."""

    def test_a_backend_without_stage_dataset_answers_501_with_a_reason(self, monkeypatch):
        class NoStaging:
            backend_type = "recurrence"

        monkeypatch.setattr(main, "backend", NoStaging(), raising=False)
        resp = TestClient(main.app).post("/api/stage_dataset", json={"nn_dataset_type": "equities_seq"})
        assert resp.status_code == 501, resp.text
        body = resp.json()
        # The operator used to get "Internal server error" + an opaque error_id for a condition
        # that is neither internal nor an error.
        assert "does not support staging" in body["error"]
        assert "recurrence" in body["error"]
        assert "error_id" not in body

    def test_a_backend_with_stage_dataset_is_unaffected(self, monkeypatch):
        class Staging:
            backend_type = "service"

            def stage_dataset(self, **params):
                return {"ok": True, "data": params}

        monkeypatch.setattr(main, "backend", Staging(), raising=False)
        resp = TestClient(main.app).post("/api/stage_dataset", json={"nn_dataset_type": "spirals"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "success"


@pytest.mark.regression
@pytest.mark.unit
class TestX8TaskTypeDivergenceIsDeliberate:
    """X8 — canopy and juniper-data label ``equities_seq`` differently, and that is load-bearing.

    canopy calls it ``regression`` (``model_registry.py``); juniper-data calls it
    ``classification`` (``juniper_data/api/routes/generators.py``). The generator is genuinely
    **dual-target** -- it emits both a next-day direction (one-hot) and a next-day close -- and the
    LMU consumes the regression target, so both labels are locally correct and neither vocabulary
    has a word for "both".

    The divergence is inert today: ``GeneratorInfo`` omits ``task_type`` from the wire, so canopy
    never sees upstream's value. It becomes load-bearing the moment §12 seeds generators from the
    upstream registry, or someone "fixes the drift" in the obvious direction. These tests exist to
    make that moment loud.
    """

    def test_canopy_labels_equities_seq_as_regression(self):
        assert get_dataset_spec("equities_seq").task_type == "regression", "canopy must keep labelling equities_seq 'regression'. juniper-data calls it " "'classification'; aligning canopy to that gives the LMU ZERO compatible datasets " "(see the companion test). The generator is dual-target and both labels are locally " "correct -- if you are here to reconcile the vocabularies, change the PREDICATE or the " "generator's declaration, not this seed."

    def test_relabelling_it_would_leave_the_lmu_with_no_dataset(self):
        # The consequence, MEASURED rather than asserted in prose, so the warning above cannot rot
        # into a claim nobody has checked.
        import dataclasses

        relabelled = dataclasses.replace(get_dataset_spec("equities_seq"), task_type="classification")
        assert compatible_models(relabelled, models=MODELS) == []

    def test_the_lmu_s_compatible_set_is_the_six_rank_3_seeds(self):
        """Was ``exactly_one``, and the one was ``equities_seq`` — which is exactly why §12 exists.

        The old assertion pinned "how little slack there is: one relabelled seed is the
        difference between a usable model and an unselectable one". §12's five synthetics
        remove that knife-edge, and the ORDER is pinned as well as the membership, for what it
        still decides. It no longer decides where the SIDEBAR lands when Recurrence is picked:
        since OQ-6's ratification (canopy#652, 2026-09-22) the sidebar gate clears a stranded
        dataset to ``⊥`` and the operator chooses. It does decide the order the dropdown
        OFFERS, and the restart modal's fallback, which keeps its ``enabled[0]`` swap by owner
        ruling (2026-09-22), a deliberate exception to OQ-6. So ``multi_sine`` leading is what
        makes both the first option offered and the modal's replacement for a stranded dataset
        one that is instant, offline and actually learnable (r² 1.000), rather than
        ``equities_seq``: 40.5s, r² -0.004, and unavailable in the deployed container
        (juniper-deploy pins juniper-data 0.15.0, whose image lacks ``yfinance``).
        """
        recurrence = next(m for m in MODELS if m.key == "recurrence")
        assert [d.value for d in DATASET_TYPES if compatible_models(d, models=(recurrence,))] == [
            "multi_sine",
            "mackey_glass",
            "irregular_sine",
            "ar_p",
            "delay_product",
            "equities_seq",
        ]

    def test_every_lmu_dataset_but_equities_is_available_without_an_extra(self):
        """The §4.7 empty-set state was the CONTAINER'S NORMAL STATE, and this is why it is not.

        ``yfinance`` is absent from the requirements.lock of every juniper-data release so far
        (juniper-data#421 adds it on main, unreleased as of 2026-09-23), so ``equities_seq`` is
        ``available=false`` in the container — and while it was the LMU's only compatible dataset, picking
        Recurrence in the container produced "No dataset is available for this model" and
        nothing else. The five synthetics are numpy-only and declare no ``is_available`` hook
        upstream, so they are available in every deployment.

        Asserted against canopy's own registry (no ``juniper_data`` import — see this module's
        docstring): every rank-3 seed except the equities one must be a generator canopy does
        NOT list as needing an optional extra.
        """
        recurrence = next(m for m in MODELS if m.key == "recurrence")
        rank3 = [d.value for d in DATASET_TYPES if compatible_models(d, models=(recurrence,))]
        needs_extra = {"equities_seq", "equities", "mnist", "arc_agi"}
        assert [v for v in rank3 if v not in needs_extra] == ["multi_sine", "mackey_glass", "irregular_sine", "ar_p", "delay_product"]


@pytest.mark.regression
@pytest.mark.unit
class TestG10EveryUpstreamGeneratorIsSeededOrNamed:
    """G10 (design §12) — an unseeded generator must be distinguishable from a forgotten one.

    Before this, "why is X not in the dataset dropdown?" had no answer anywhere in the repo:
    ten of juniper-data's sixteen generators were simply absent, with nothing recording
    whether that was a decision or an oversight. ``UNSEEDED_GENERATORS`` now carries the
    reason for each, and this suite keeps the two lists honest against each other.

    ``KNOWN_UPSTREAM_GENERATORS`` is a dated snapshot (2026-09-09, taken by executing
    juniper-data's registry), not an import — see this module's docstring for why canopy must
    not assert against the installed ``juniper_data``. Upstream ADDING a generator is
    therefore not caught here; it is caught at runtime by ``/api/dataset/generators``.
    """

    def test_every_known_generator_is_either_seeded_or_named_unseeded(self):
        seeded = {generator_name_for_type(spec.value) for spec in DATASET_TYPES}
        accounted = seeded | set(UNSEEDED_GENERATORS)
        missing = KNOWN_UPSTREAM_GENERATORS - accounted
        assert not missing, f"generators that are neither seeded nor explained: {sorted(missing)} — add a seed, or an UNSEEDED_GENERATORS entry saying why not"

    def test_no_generator_is_both_seeded_and_named_unseeded(self):
        seeded = {generator_name_for_type(spec.value) for spec in DATASET_TYPES}
        both = seeded & set(UNSEEDED_GENERATORS)
        assert not both, f"listed as deliberately unseeded but present in the dropdown: {sorted(both)}"

    def test_the_unseeded_list_names_no_unknown_generator(self):
        # An entry for a generator upstream does not have is either a typo or a rename that was
        # half-done; either way the "reason" it records is about nothing.
        unknown = set(UNSEEDED_GENERATORS) - KNOWN_UPSTREAM_GENERATORS
        assert not unknown, f"UNSEEDED_GENERATORS names generators absent from the snapshot: {sorted(unknown)}"

    def test_every_seeded_value_resolves_to_a_known_generator(self):
        seeded = {generator_name_for_type(spec.value) for spec in DATASET_TYPES}
        unknown = seeded - KNOWN_UPSTREAM_GENERATORS
        assert not unknown, f"seeded values that juniper-data does not register: {sorted(unknown)}"

    @pytest.mark.parametrize("name", sorted(UNSEEDED_GENERATORS))
    def test_each_exclusion_carries_a_substantive_reason(self, name):
        # A one-word reason ("deferred") is the failure mode this list exists to prevent.
        reason = UNSEEDED_GENERATORS[name]
        assert len(reason.split()) >= 8, f"{name}'s exclusion reason is too thin to act on: {reason!r}"


# What "bounded" means for each key a G11 classification may name as bounding. A key with no rule
# here FAILS ``test_every_bounding_key_has_a_rule`` rather than passing by default: a bound nobody
# defined is not a bound.
#
# ``symbols``: an explicit, non-empty list of ticker strings no longer than juniper-data's DEFAULT
# deployment ceiling, ``EQUITIES_DEFAULT_MAX_SYMBOLS = 14`` (``juniper_data/core/limits.py`` at
# main 68c3cd7, 2026-09-22). An empty list or ``None`` falls back to the 503-name bundled universe,
# and on a default deployment a longer list is refused with 422 rather than truncated. A dated
# snapshot, like G10's: a deployment that lowers its ceiling is not visible from here.
_EQUITIES_DEFAULT_SYMBOL_CEILING = 14


def _symbols_are_bounded(value):
    return isinstance(value, (list, tuple)) and 0 < len(value) <= _EQUITIES_DEFAULT_SYMBOL_CEILING and all(isinstance(symbol, str) and symbol.strip() for symbol in value)


_BOUNDED_VALUE_RULES = {"symbols": _symbols_are_bounded}


def _seeded_generator_names():
    return {generator_name_for_type(spec.value) for spec in DATASET_TYPES}


def _unbounded_import_seeds():
    """Seeds whose generator is classified as importing an unbounded universe."""
    seeds = []
    for spec in DATASET_TYPES:
        bound = SEEDED_GENERATOR_BOUNDS.get(generator_name_for_type(spec.value))
        if bound is not None and bound.bounding_keys:
            seeds.append(spec)
    return seeds


@pytest.mark.regression
@pytest.mark.unit
class TestG11EverySeedIsBounded:
    """G11 (design §12) — enforced over EVERY seed, not over the seeds someone remembered.

    Until 2026-09-22 G11 was enforced by enumerating names: the tests that touched it listed the
    seeds they knew, and ``model_registry.py`` pointed its reader at an
    ``UNBOUNDED_IMPORT_GENERATORS`` that existed nowhere. A fifteenth seed with unbounded
    ``default_params`` passed everything, and the design's §5 table recorded G11 as "passes" -- the
    vacuous-pass shape.

    ``SEEDED_GENERATOR_BOUNDS`` is the authority now, and this suite forces a recorded decision per
    SEEDED generator the way G10 forces one per UPSTREAM generator: every seed's generator is
    classified, and a generator that imports an unbounded universe must have its seed pin one of
    its bounding keys to a bounded value.
    """

    @pytest.mark.parametrize("spec", DATASET_TYPES, ids=lambda s: s.value)
    def test_every_seeded_generator_is_classified(self, spec):
        name = generator_name_for_type(spec.value)
        assert name in SEEDED_GENERATOR_BOUNDS, f"seed {spec.value!r} (generator {name!r}) has no G11 classification. Add a SEEDED_GENERATOR_BOUNDS entry in model_registry.py: " f"GeneratorBound(reason) if its own defaults bound it, or GeneratorBound(reason, bounding_keys=...) naming the default_params keys that bound it if it pulls an operator-sized universe."

    @pytest.mark.parametrize("spec", _unbounded_import_seeds(), ids=lambda s: s.value)
    def test_every_unbounded_import_seed_pins_a_bounding_key(self, spec):
        bound = SEEDED_GENERATOR_BOUNDS[generator_name_for_type(spec.value)]
        pinned = {key: spec.default_params[key] for key in sorted(bound.bounding_keys) if key in spec.default_params}
        assert any(_BOUNDED_VALUE_RULES[key](value) for key, value in pinned.items()), f"seed {spec.value!r} imports an unbounded universe and must pin one of {sorted(bound.bounding_keys)} to a bounded value in its default_params; " f"got {pinned or 'none of them'}. Without it every Start asks for the whole universe. 'max_symbols' is not a bounding key: it is the cap juniper-data refuses against."

    def test_there_is_an_unbounded_import_seed_to_check(self):
        # Guards the vacuous pass: with nothing classified as an unbounded import, the pinning test
        # above is parametrised over an empty list and asserts nothing.
        assert _unbounded_import_seeds(), "no seed is classified as an unbounded import -- the pinning test would be vacuous"

    def test_the_equities_pair_stays_classified_as_unbounded_imports(self):
        # The classification is a recorded decision, so it is also the easiest way to switch the
        # pinning check off: reclassify a universe importer as self-bounded and its seed is never
        # inspected. The two measured importers are pinned to the class they were measured in.
        for name in sorted({"equities", "equities_seq"} & _seeded_generator_names()):
            assert "symbols" in SEEDED_GENERATOR_BOUNDS[name].bounding_keys, f"{name} must stay classified as an unbounded import bounded by 'symbols'"

    def test_the_classification_names_only_seeded_generators(self):
        # An entry for a generator no seed uses records a decision about nothing: a half-done
        # un-seeding, or a typo that leaves the real seed unclassified.
        dead = set(SEEDED_GENERATOR_BOUNDS) - _seeded_generator_names()
        assert not dead, f"SEEDED_GENERATOR_BOUNDS classifies generators no seed uses: {sorted(dead)}"

    def test_every_bounding_key_has_a_rule(self):
        # A bounding key with no definition of "bounded" would pass or fail by accident of the
        # default. Neither is a decision.
        named = {key for bound in SEEDED_GENERATOR_BOUNDS.values() for key in bound.bounding_keys}
        undefined = named - set(_BOUNDED_VALUE_RULES)
        assert not undefined, f"bounding keys with no boundedness rule in this module: {sorted(undefined)}"

    @pytest.mark.parametrize("name", sorted(SEEDED_GENERATOR_BOUNDS))
    def test_each_classification_carries_a_substantive_reason(self, name):
        # G10's bar: a one-word reason is the failure mode a recorded decision exists to prevent.
        reason = SEEDED_GENERATOR_BOUNDS[name].reason
        assert len(reason.split()) >= 8, f"{name}'s G11 reason is too thin to act on: {reason!r}"


@pytest.mark.regression
@pytest.mark.unit
class TestEquitiesSeedIsGenerableAndFinite:
    """An equities seed must carry the two keys without which it cannot train at all.

    Both were measured against juniper-data on 2026-09-09, and each defeated the pair
    (recurrence, equities_seq) at a DIFFERENT stage -- which is how the arc could ship N5
    (canopy#601) and in-process staging (canopy#607) and still never once train end to end.

    1. ``symbols``. ``max_symbols`` is a CAP that REFUSES, not a truncator: juniper-data
       compares it against the requested universe (503 bundled names) and raises
       InputTooLargeError -> 422 unless ``allow_truncation`` is set. The shipped seed
       ``{"max_symbols": 5}`` generated nothing, in 0.0s, on every Start.
    2. ``fundamentals_fill``. Its juniper-data default is ``"nan"``, and at that default
       X_train comes back 9.1% non-finite (total_shares / market_cap / days_since_report)
       while X_val and X_test are entirely clean -- so a spot check that samples val or
       test sees a perfectly healthy dataset. LMURegressor.fit refuses it outright:
       ``ValueError: u must be finite``.

    Hermetic on purpose: this reads canopy's own registry and imports no ``juniper_data``.
    The copy installed in the canopy test env is 0.6.0, whose registry predates
    ``equities_seq`` entirely (see this module's docstring), so asserting against it would
    produce a false red on a stale dependency rather than on real drift.

    Not pinned here: the specific tickers, or ``drop`` vs ``zero``. Those are tuning. The
    invariant is that a seed which cannot generate, or which generates values its only
    compatible model refuses, must not sit in the dropdown looking selectable.
    """

    # Both equities generators take the same universe and fundamentals knobs, so a future
    # ``equities`` seed inherits both traps unchanged.
    EQUITIES_GENERATORS = frozenset({"equities", "equities_seq"})

    def _equities_seeds(self):
        return [spec for spec in DATASET_TYPES if generator_name_for_type(spec.value) in self.EQUITIES_GENERATORS]

    def test_there_is_at_least_one_equities_seed_to_check(self):
        # Guards the vacuous pass: if the seed is renamed out of the family, the two tests
        # below keep passing while asserting over an empty list.
        assert self._equities_seeds(), "no equities-family seed found -- the assertions below would be vacuous"

    def test_every_equities_seed_pins_its_universe(self):
        # This used to accept ``allow_truncation: True`` as an alternative to a ``symbols`` list.
        # It is not one: a seeded opt-in rides on every Apply and every one-shot Start, so it
        # pre-answers the partial-data question the three-way prompt exists to ask -- and no seed
        # may carry either policy field (TestNoPathSendsAPartialDataStance). Only an explicit
        # universe bounds the request.
        for spec in self._equities_seeds():
            params = spec.default_params
            symbols = params.get("symbols")
            pinned = isinstance(symbols, (list, tuple)) and len(symbols) > 0
            assert pinned, f"{spec.value!r} relies on juniper-data's default 503-name universe: it pins no " f"'symbols' list, so every Start 422s with InputTooLargeError. 'max_symbols' does NOT " f"rescue this -- it IS the cap being exceeded -- and a seeded allow_truncation is not a " f"remedy either: it would opt every run into a cut universe without asking. got={params!r}"

    def test_every_equities_seed_pins_a_finite_fundamentals_fill(self):
        for spec in self._equities_seeds():
            fill = spec.default_params.get("fundamentals_fill")
            assert fill in ("zero", "drop"), f"{spec.value!r} leaves fundamentals_fill at juniper-data's 'nan' default, which puts " f"non-finite values in X_train (and ONLY X_train) -- LMURegressor.fit rejects them with " f"'u must be finite'. A later start_date is not a substitute: start_date=2010-01-01 " f"still yields 299,808 non-finite cells. got={fill!r}"

    def test_a_rank2_equities_seed_normalises_its_features(self):
        """The third key, which the rank-3 sibling does not need and did not reveal.

        equities' feature columns are raw market quantities -- close prices, volumes, market
        caps in the 1e11 range -- and ``normalize_features`` defaults to False. Fed to CasCor
        unnormalised, the first output pass reports a loss of **5.83e+21** against **0.2511**
        normalised: twenty-two orders of magnitude, and train top-1 pinned at chance either way
        so accuracy alone would NOT have caught it. Measured 2026-09-10.

        Scoped to rank-2 deliberately. The LMU path standardises upstream of the readout, and
        ``equities_seq`` was measured fitting cleanly without this key; asserting it there would
        pin a value nothing has shown to be needed.
        """
        for spec in self._equities_seeds():
            if spec.ndim != 2:
                continue
            assert spec.default_params.get("normalize_features") is True, f"{spec.value!r} is rank-2 and leaves normalize_features at juniper-data's False default, so CasCor " f"is fed raw market quantities -- first-pass loss 5.83e+21 vs 0.2511 normalised. got={spec.default_params!r}"


@pytest.mark.regression
@pytest.mark.unit
class TestTheCascorPathCarriesRegistryDefaults:
    """The registry seed must reach the CASCOR staging payload, not only the recurrence one.

    Until 2026-09-11 ``dataset_default_params`` had exactly two production consumers --
    ``_resolve_oneshot_start_body_handler`` (gated on ``model_class == "one_shot"``) and
    ``dataset_ref_from_staged`` -- both recurrence. ``_apply_dataset_handler`` built the cascor
    payload from the rendered form alone, so a rank-2 dataset that NEEDS params could not be
    expressed at all: ``equities`` would send bare defaults and 422 on every Apply, because its
    ``symbols`` key is an array that ``_field_from_property`` deliberately does not render.

    Two halves, and both are needed. The payload is seeded from the registry so unrendered keys
    travel; the rendered controls are seeded too (``apply_seeded_defaults``) so a key that is
    both seeded and rendered is not posted back at its SCHEMA default, silently undoing the seed.
    """

    @staticmethod
    def _staged_payload(dataset_value, gen_values=None, gen_ids=None):
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = MagicMock(ok=True, status_code=200, text="{}")
            post.return_value.json.return_value = {}
            DashboardManager({})._apply_dataset_handler(1, dataset_value, 100, 0.1, 2.0, 2, gen_values=gen_values, gen_ids=gen_ids)
        return post.call_args.kwargs["json"]

    def test_an_unrendered_array_param_reaches_cascor(self):
        # THE regression. ``symbols`` has no control, so a form-only payload could never carry it.
        sent = self._staged_payload("equities")
        assert sent["nn_dataset_params"]["symbols"] == ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
        assert sent["nn_dataset_params"]["fundamentals_fill"] == "drop"
        assert sent["nn_dataset_params"]["normalize_features"] is True

    def test_the_form_overrides_the_seed(self):
        # The operator's edit must win -- the seed is a default, not a floor.
        sent = self._staged_payload("equities", gen_values=["zero"], gen_ids=[{"type": "nn-gen-param", "name": "fundamentals_fill"}])
        assert sent["nn_dataset_params"]["fundamentals_fill"] == "zero"
        # ...and the unrendered key still rides along beside the override.
        assert sent["nn_dataset_params"]["symbols"] == ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]

    def test_an_unseeded_dataset_is_unchanged(self):
        # No behaviour change for a seed that carries {} (``xor`` is one; of the cascor-compatible
        # seeds only ``mnist`` and ``equities`` carry params): the payload must not sprout an
        # empty params key it never had.
        sent = self._staged_payload("xor")
        assert "nn_dataset_params" not in sent

    def test_the_rendered_control_shows_the_seeded_value_not_the_schema_default(self):
        # The other half. If the panel renders juniper-data's "nan" while the registry seeds
        # "drop", the operator is shown one value, a different one is sent, and the next Apply
        # posts "nan" back over the seed.
        schema = {"properties": {"fundamentals_fill": {"type": "string", "enum": ["zero", "nan", "drop"], "default": "nan"}}}
        generators = [{"name": "equities", "available": True, "schema": schema}]
        _title, _style, children = DashboardManager({})._render_dataset_params_handler("equities", generators=generators)
        rendered = [child for child in children if getattr(child, "id", None) == {"type": "nn-gen-param", "name": "fundamentals_fill"}]
        assert rendered, "fundamentals_fill was not rendered at all"
        assert rendered[0].value == "drop"


@pytest.mark.regression
@pytest.mark.unit
class TestNoPathSendsAPartialDataStance:
    """No channel may put ``allow_truncation`` / ``incomplete_rows`` on the wire unasked.

    juniper-data 0.15.0 (juniper-data#418, APD-DATA-052) made ``allow_truncation`` a tri-state:
    ``null`` / omitted defers to the deployment, ``true`` opts in, and an explicit ``false``
    REFUSES -- HTTP 422 on any shortfall, even where the deployment opted in. cascor#624 already
    honoured a caller's explicit value over cascor's own setting, so a ``false`` from canopy now
    overrides every opt-in on the path. Silence is the only value that defers, which is why
    ``PARTIAL_DATA_POLICY_FIELDS`` withholds both fields from the form.

    Only the form's RENDER half was pinned (``test_parse_excludes_partial_data_policy_fields``).
    The registry seed is the channel that bypasses the form's filter BY DESIGN -- Apply applies it
    before filtering, so an unrendered array like ``symbols`` can travel -- and it is also the
    whole of the one-shot Start body. So every channel that builds a dataset request is walked
    here, over every seed.

    The one sender is deliberate and stays: the shortfall prompt's accept / drop buttons re-stage
    with ``allow_truncation: true`` -- the operator answering the question at the moment it
    arises. The last test pins that it never sends anything else.
    """

    @staticmethod
    def _policy_fields_in(params):
        return sorted(PARTIAL_DATA_POLICY_FIELDS & set(params or {}))

    @pytest.mark.parametrize("spec", DATASET_TYPES, ids=lambda s: s.value)
    def test_no_seed_carries_a_policy_field(self, spec):
        carried = self._policy_fields_in(spec.default_params)
        assert not carried, f"{spec.value!r} seeds {carried}. The seed rides on every Apply AND every one-shot Start, so it would answer the partial-data question for every run before it is asked -- and since juniper-data 0.15.0 an explicit false refuses every shortfall."

    @pytest.mark.parametrize("spec", DATASET_TYPES, ids=lambda s: s.value)
    def test_the_default_apply_sends_neither_field(self, spec):
        sent = TestTheCascorPathCarriesRegistryDefaults._staged_payload(spec.value)
        assert not (self._policy_fields_in(sent) or self._policy_fields_in(sent.get("nn_dataset_params"))), f"Apply for {spec.value!r} sent {sent!r}"

    def test_a_stale_policy_control_is_filtered_and_nothing_else_is(self):
        # A tab rendered before these controls were withheld still carries them, and an unticked
        # one posts ``allow_truncation: False``. The filter must drop both fields and ONLY them:
        # the ordinary edit beside them still wins, and the unrendered seed still rides -- or a
        # green result here could mean the filter dropped everything.
        sent = TestTheCascorPathCarriesRegistryDefaults._staged_payload(
            "equities",
            gen_values=[False, "accept", "zero"],
            gen_ids=[
                {"type": "nn-gen-param", "name": "allow_truncation"},
                {"type": "nn-gen-param", "name": "incomplete_rows"},
                {"type": "nn-gen-param", "name": "fundamentals_fill"},
            ],
        )
        params = sent["nn_dataset_params"]
        assert not self._policy_fields_in(params), f"a stale control forwarded a partial-data stance: {params!r}"
        assert params["fundamentals_fill"] == "zero", "the filter swallowed an ordinary content param"
        assert params["symbols"] == ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"], "the seed stopped riding alongside the form"

    @pytest.mark.parametrize("spec", DATASET_TYPES, ids=lambda s: s.value)
    def test_the_one_shot_start_body_sends_neither_field(self, spec):
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", spec.value)
        assert body is not None, "the one-shot handler built no body at all -- this check would be vacuous"
        params = body["dataset"].get("params")
        assert not self._policy_fields_in(params), f"the one-shot Start body for {spec.value!r} carries {params!r}"

    @pytest.mark.parametrize("spec", DATASET_TYPES, ids=lambda s: s.value)
    def test_the_restart_modal_restage_sends_neither_field(self, spec):
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = MagicMock(ok=True, status_code=200, text="{}")
            post.return_value.json.return_value = {}
            DashboardManager({})._restage_dataset({"dataset_type": spec.value, "n_samples": 100, "noise": 0.1})
        assert post.called, "the restart modal re-stage posted nothing -- this check would be vacuous"
        sent = post.call_args.kwargs["json"]
        assert not (self._policy_fields_in(sent) or self._policy_fields_in(sent.get("nn_dataset_params"))), f"the restart modal re-stage for {spec.value!r} sent {sent!r}"

    def test_the_shortfall_prompt_only_ever_opts_in(self):
        # The deliberate exception, pinned so it cannot drift into what this class forbids. Every
        # prompt option that re-stages opts IN; "fail" (option 3) re-stages nothing -- it cancels
        # the load instead, and is not in this map.
        assert DATASET_SHORTFALL_OPTIONS, "the prompt's options vanished -- this pin would be vacuous"
        for button, choice in DATASET_SHORTFALL_OPTIONS.items():
            assert choice.get("allow_truncation") is True, f"{button} sends allow_truncation={choice.get('allow_truncation')!r}; the prompt may only ever opt in"


class TestAShapeDeterminingKnobIsWithheldNotRendered:
    """canopy#623 — a field that can contradict ``DatasetTypeSpec.ndim`` must not be rendered.

    ``mnist`` is seeded ``ndim=2``, and juniper-data's mnist generator flips to rank-3
    ``(N, 28, 28)`` when ``flatten=False``. That knob is a plain boolean, so the schema-driven
    panel rendered it as a checkbox and ``_collect_generator_params`` forwarded ``False``
    (it drops only ``None`` and ``""``). Apply then returned **200 with a green banner** — no
    canopy-side rank check exists — and the failure surfaced at Start as a 409 from cascor's
    tier-boundary guard, naming the juniper-recurrence tier to an operator who picked MNIST.

    The registry's ``arc_agi`` entry recorded this exact hazard as its reason for NOT being
    seeded, while ``mnist`` — which has it too — shipped. The exclusion was applied to one
    member of a two-member class.

    Design §12.9 of JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md rejected
    the alternative (widen the registry's rank type): no ``ModelSpec`` accepts more than one
    rank, so a variable-rank dataset is compatible with nothing under the sound reading.
    """

    MNIST_SCHEMA = {
        "properties": {
            "dataset": {"type": "string", "enum": ["mnist", "fashion_mnist"], "default": "mnist"},
            "n_samples": {"anyOf": [{"minimum": 1, "type": "integer"}, {"type": "null"}], "default": None},
            "flatten": {"type": "boolean", "default": True, "title": "Flatten"},
            "seed": {"type": "integer", "default": 0},
        }
    }

    def test_the_rank_flipping_knob_is_not_rendered_for_mnist(self):
        # THE regression. Before the fix this rendered a "Flatten" checkbox.
        generators = [{"name": "mnist", "available": True, "schema": self.MNIST_SCHEMA}]
        _title, _style, children = DashboardManager({})._render_dataset_params_handler("mnist", generators=generators)
        names = [child.id["name"] for child in children if isinstance(getattr(child, "id", None), dict)]
        assert "flatten" not in names, "mnist's rank-flipping knob is rendered; an operator can contradict ndim=2"
        # The ordinary content params are untouched -- this withholds one field, not the panel.
        assert "dataset" in names and "n_samples" in names

    def test_the_same_field_name_is_still_rendered_for_another_generator(self):
        # Why the exclusion is keyed PER GENERATOR. This schema space has cross-generator name
        # collisions (``normalize_features`` in three, ``one_hot_labels`` in two), so a global
        # name-keyed exclusion would reach fields that are ordinary content params elsewhere.
        assert "flatten" in form_excluded_fields("mnist")
        assert "flatten" not in form_excluded_fields("equities")
        assert "flatten_pairs" in form_excluded_fields("arc_agi")
        assert "flatten_pairs" not in form_excluded_fields("mnist")

    def test_an_unknown_generator_gets_the_universal_set_only(self):
        # A generator canopy does not recognise has no rank declaration to contradict.
        assert form_excluded_fields("not_a_generator") == FORM_EXCLUDED_FIELDS
        assert form_excluded_fields(None) == FORM_EXCLUDED_FIELDS

    def test_the_withheld_value_still_reaches_cascor(self):
        # Withholding the CONTROL must not drop the VALUE: the registry seeds ``flatten=True``
        # so canopy sends what makes its own ``ndim=2`` declaration true, rather than relying on
        # juniper-data's default staying True. The seed rides the same channel as equities'
        # unrendered ``symbols``.
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = MagicMock(ok=True, status_code=200, text="{}")
            post.return_value.json.return_value = {}
            DashboardManager({})._apply_dataset_handler(1, "mnist", 100, 0.1, 2.0, 2, gen_values=None, gen_ids=None)
        sent = post.call_args.kwargs["json"]
        assert sent["nn_dataset_params"]["flatten"] is True

    def test_every_shape_determining_field_names_a_real_generator(self):
        # A map keyed on a name nothing produces is a rule that never fires. Both keys must be
        # generators canopy knows upstream, or the exclusion silently protects nothing.
        for gen_name in SHAPE_DETERMINING_FIELDS:
            assert gen_name in KNOWN_UPSTREAM_GENERATORS, f"{gen_name} is not an upstream generator"

    def test_the_registry_asserts_the_rank_rather_than_inheriting_it(self):
        # The seed must be PRESENT, not merely the control absent -- absence alone would leave
        # the value to juniper-data's default, making canopy's ndim=2 true by coincidence.
        spec = get_dataset_spec("mnist")
        assert spec is not None and spec.ndim == 2
        assert spec.default_params.get("flatten") is True, "ndim=2 is asserted, not merely inherited"

    def test_a_fabricated_control_id_cannot_override_the_withheld_knob(self):
        # The test this replaced carried this name and asserted only the two registry values
        # above -- it never constructed a control id, so it claimed a defence the code did not
        # have. It does now: ``_collect_generator_params`` filters by the same per-generator
        # exclusion the renderer uses.
        #
        # The realistic attacker is not an attacker. It is a browser tab rendered BEFORE the
        # canopy#625 deploy, which still holds the ``flatten`` checkbox in its layout: the
        # operator unticks it and Apply posts ``flatten: False``. ``False`` passes the blank-drop
        # (``False is None`` and ``False == ""`` are both false), so before this fix it
        # overrode the seed and flipped mnist to rank-3 -- canopy#623 verbatim, from a client
        # the server cannot see or upgrade.
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = MagicMock(ok=True, status_code=200, text="{}")
            post.return_value.json.return_value = {}
            DashboardManager({})._apply_dataset_handler(
                1,
                "mnist",
                100,
                0.1,
                2.0,
                2,
                gen_values=[False],
                gen_ids=[{"type": "nn-gen-param", "name": "flatten"}],
            )
        sent = post.call_args.kwargs["json"]
        assert sent["nn_dataset_params"]["flatten"] is True, "a fabricated/stale `flatten` control overrode the seed; mnist would be staged rank-3 against its own ndim=2"

    def test_the_filter_drops_only_the_withheld_field_not_the_panel(self):
        # Guard against over-correction: the exclusion must not swallow ordinary content params
        # travelling on the same channel, or the fix trades canopy#623 for a silent param loss.
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = MagicMock(ok=True, status_code=200, text="{}")
            post.return_value.json.return_value = {}
            DashboardManager({})._apply_dataset_handler(
                1,
                "mnist",
                100,
                0.1,
                2.0,
                2,
                gen_values=[False, 7, "zalando-datasets/fashion_mnist"],
                gen_ids=[
                    {"type": "nn-gen-param", "name": "flatten"},
                    {"type": "nn-gen-param", "name": "n_samples"},
                    {"type": "nn-gen-param", "name": "dataset"},
                ],
            )
        sent = post.call_args.kwargs["json"]["nn_dataset_params"]
        assert sent["flatten"] is True, "the withheld knob was not filtered"
        assert sent["n_samples"] == 7 and sent["dataset"] == "zalando-datasets/fashion_mnist", "ordinary content params must still reach cascor"


class TestSplitPlumbingNeverReachesTheContentForm:
    """canopy#630 — the panel must not render the partition split as a dataset knob.

    ``INFRASTRUCTURE_FIELDS`` named the split plumbing of a TWO-partition world
    (``train_ratio`` / ``test_ratio`` / ``shuffle`` / ``seed`` / ``use_cache``). The
    three-partition contract added ``sizing_mode`` / ``val_percent`` / ``test_percent`` /
    ``val_ratio``, and the set silently stopped covering its own subject: measured before the
    fix, **all 16 upstream generators leaked at least one**, and 13 of canopy's 14 selectable
    dataset types rendered at least one control.

    These are not inert. ``_collect_generator_params`` drops only ``None`` and ``""``, so a
    rendered value is POSTED on every Apply — an operator adjusting what looks like a dataset
    knob was reshaping the train/val/test split that cascor and juniper-data own.

    The census that produced those numbers lives at
    ``juniper-ml/util/ad-hoc/2026-09-15_split_field_form_leak_census.py``.
    """

    #: Every field name the partition contract owns. A NEW split field added upstream and not
    #: added here is exactly the regression this class exists to catch.
    SPLIT_PLUMBING = frozenset({"sizing_mode", "val_percent", "test_percent", "val_ratio", "train_ratio", "test_ratio"})

    def test_no_split_field_survives_the_universal_exclusion(self):
        # The direct statement of the rule, independent of any generator's schema.
        assert self.SPLIT_PLUMBING <= FORM_EXCLUDED_FIELDS, f"not excluded: {sorted(self.SPLIT_PLUMBING - FORM_EXCLUDED_FIELDS)}"

    def test_no_generator_renders_a_split_field(self):
        """The property that matters, measured against a schema shaped like the real ones.

        Written over a synthetic schema rather than a live juniper-data import so it runs in
        canopy's own CI with no cross-repo dependency — the field NAMES are the contract.
        """
        schema = {
            "properties": {
                # The split plumbing, exactly as juniper-data emits it.
                "sizing_mode": {"type": "string", "default": "carve"},
                "val_percent": {"type": "number", "default": 40.0},
                "test_percent": {"type": "number", "default": 30.0},
                "val_ratio": {"type": "number", "default": 0.1},
                "train_ratio": {"type": "number", "default": 0.6},
                "test_ratio": {"type": "number", "default": 0.2},
                # Genuine content params, which MUST survive.
                "n_samples": {"type": "integer", "default": 200},
                "noise": {"type": "number", "default": 0.1},
            }
        }
        rendered = {f.name for f in parse_schema_fields(schema)}
        assert not (rendered & self.SPLIT_PLUMBING), f"split plumbing rendered as content params: {sorted(rendered & self.SPLIT_PLUMBING)}"
        # Not a vacuous pass: the content params are still there, so the exclusion is
        # selective rather than the parser having returned nothing.
        assert rendered == {"n_samples", "noise"}

    def test_sizing_mode_is_not_rendered_as_a_free_text_box(self):
        """The second half of #630, closed by the same exclusion.

        ``sizing_mode`` is a closed choice, but its schema emits ``type: string`` with no
        ``enum``, and ``_field_from_property`` maps a bare string to a text input — so an
        operator got a free text box and a typo became a 422 from juniper-data. Excluding the
        field removes the control entirely; there is no separate fix.
        """
        schema = {"properties": {"sizing_mode": {"type": "string", "default": "carve"}}}
        assert [f.name for f in parse_schema_fields(schema)] == []
        # And it is genuinely the EXCLUSION doing this, not the parser refusing bare strings:
        # the same shape under a different name still renders, as a text input.
        other = parse_schema_fields({"properties": {"label_column": {"type": "string", "default": "y"}}})
        assert [(f.name, f.input_type) for f in other] == [("label_column", "text")]

    def test_the_per_generator_exclusion_still_composes(self):
        # canopy#623's SHAPE_DETERMINING_FIELDS are unioned ON TOP of the universal set, so
        # widening the universal set must not drop them.
        assert "flatten" in form_excluded_fields("mnist")
        assert self.SPLIT_PLUMBING <= form_excluded_fields("mnist")
