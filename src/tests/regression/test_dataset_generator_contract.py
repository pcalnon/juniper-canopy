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
from model_registry import DATASET_TYPES, MODELS, compatible_models, get_dataset_spec


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

    def test_the_lmu_has_exactly_one_compatible_dataset_today(self):
        # Pins how little slack there is: one relabelled seed is the difference between a usable
        # model and an unselectable one.
        recurrence = next(m for m in MODELS if m.key == "recurrence")
        assert [d.value for d in DATASET_TYPES if compatible_models(d, models=(recurrence,))] == ["equities_seq"]


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
