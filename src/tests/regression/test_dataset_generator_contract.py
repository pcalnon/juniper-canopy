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
from dataset_schema import GENERATOR_NAME_ALIASES, generator_name_for_type
from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, KNOWN_UPSTREAM_GENERATORS, MODELS, UNSEEDED_GENERATORS, compatible_models, get_dataset_spec


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
        remove that knife-edge, and the ORDER matters as much as the membership: the sidebar
        gate snaps to the first compatible AND available entry, so ``multi_sine`` leading is
        what makes selecting Recurrence land on a dataset that is instant, offline and
        actually learnable (r² 1.000) instead of on ``equities_seq``, which is 40.5s, r²
        -0.004, and unavailable in the container at all.
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

        ``yfinance`` is absent from juniper-data's requirements.lock, so ``equities_seq`` is
        ``available=false`` there — and while it was the LMU's only compatible dataset, picking
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
        for spec in self._equities_seeds():
            params = spec.default_params
            symbols = params.get("symbols")
            pinned = isinstance(symbols, (list, tuple)) and len(symbols) > 0
            assert pinned or params.get("allow_truncation") is True, f"{spec.value!r} relies on juniper-data's default 503-name universe: it pins neither a " f"'symbols' list nor allow_truncation, so every Start 422s with InputTooLargeError. " f"'max_symbols' does NOT rescue this -- it IS the cap being exceeded. got={params!r}"

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
        # No behaviour change for the seven cascor-compatible seeds that carry {}: the payload
        # must not sprout an empty params key it never had.
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
