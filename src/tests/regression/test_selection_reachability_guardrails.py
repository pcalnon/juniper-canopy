#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_selection_reachability_guardrails.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Guardrails G1-G11 for the selection-reachability
#                remediation. This PR lands G5 (model-state truth);
#                G1a-G1d / G3 / G6 / G7 / G8 arrive with their own
#                phases and share this module.
#####################################################################
"""Guardrails for the selection-reachability remediation design.

Design of record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-REACHABILITY-DESIGN.md`` (§5
names each guardrail and the status it must have before and after its phase). Evaluation of
record: ``JUNIPER_2026-09-02_JUNIPER-CANOPY_SELECTION-DEADLOCK-PROPOSALS.md``.

**G5 — the model summary reflects the backend that is actually live (X1 / N5).**

``POST /api/model/select`` returns HTTP 200 for a ``recurrence`` selection even when
``recurrence_service_url`` is unset (the code default): ``_swap_backend`` (``main.py:3891``)
sees that the selection routes to the same backend type already running, records the selection,
and no-ops. The response says so — it carries ``backend`` and ``swapped`` — but the sidebar
summary read only ``nn_model`` and the registry's lifecycle ``status``, both of which are
"recurrence" and "live", so it rendered *"Active: Recurrence (LMU)"* while cascor trained.

That is silent benchmark misattribution: the run is real, the numbers are real, and the model
they are filed under is wrong. The design ships this guardrail FIRST for that reason — unblocking
the deadlock without it would convert a blocked control into a wrong result (§7).

**The predicate under test is deliberately not ``swapped``.** ``swapped is False`` is also the
correct, healthy answer when the user re-selects the model that is already live, so a summary
gated on it would report a running CasCor as inactive. ``test_noop_reselect_of_the_live_model_still_reads_active``
is the false-positive guard that pins that distinction; it fails against the naive predicate.
"""

from unittest import mock

import dash
import pytest
from fastapi.testclient import TestClient

import main
from backend.demo_backend import DemoBackend
from dataset_schema import generator_name_for_type
from demo_mode import DemoMode
from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, DEFAULT_DATASET_TYPE, DEFAULT_MODEL_KEY, MODELS, DatasetTypeSpec, ModelSpec, compatible, compatible_datasets, model_requirement, selection_is_live


@pytest.fixture
def manager():
    """A DashboardManager instance (also validates the layout + callbacks register cleanly)."""
    return DashboardManager({})


# The X1 payload, shaped exactly as ``main._model_state_response`` builds it (``main.py:3860-3871``)
# for a recurrence selection over an unconfigured service. ``test_the_real_route_payload_reads_not_active``
# below re-derives this from the live route rather than trusting the literal.
X1_PAYLOAD = {
    "nn_model": "recurrence",
    "backend": "demo",
    "execution": "continuous",
    "status": "live",
    "swapped": False,
}


@pytest.mark.regression
@pytest.mark.unit
class TestG5ModelStateTruth:
    """G5 — the summary must not claim a model is active when another backend is running."""

    def test_recurrence_selected_over_a_non_recurrence_backend_is_not_live(self):
        assert DashboardManager._selection_is_live(X1_PAYLOAD) is False

    def test_recurrence_selected_over_the_recurrence_backend_is_live(self):
        data = {**X1_PAYLOAD, "backend": "recurrence", "swapped": True}
        assert DashboardManager._selection_is_live(data) is True

    @pytest.mark.parametrize("backend_type", ["service", "demo"])
    def test_cascor_selected_over_a_cascor_family_backend_is_live(self, backend_type):
        # The REAL domain of ``backend.backend_type`` is exactly {"service", "demo", "recurrence"}
        # (``service_backend.py:84``, ``demo_backend.py:71``, ``recurrence_backend.py:121``). An
        # earlier revision of this test parametrised on "cascor", which the property never returns
        # — so the live-cascor case, the one the predicate most needed pinned, went uncovered while
        # the suite read green. Both non-recurrence types serve the cascor model.
        data = {"nn_model": "cascor", "backend": backend_type, "status": "live", "swapped": False}
        assert DashboardManager._selection_is_live(data) is True

    def test_the_backend_type_domain_is_exactly_three_values(self):
        # Pins the premise of every case above against the property implementations themselves, so
        # a fourth backend type cannot appear without this suite noticing.
        from backend.demo_backend import DemoBackend as _Demo
        from backend.recurrence_backend import RecurrenceBackend as _Rec
        from backend.service_backend import ServiceBackend as _Svc

        assert {_Svc.backend_type.fget(None), _Demo.backend_type.fget(None), _Rec.backend_type.fget(None)} == {"service", "demo", "recurrence"}

    def test_an_absent_backend_is_unknown_not_a_disagreement(self):
        # The first-paint seed has never round-tripped, so it carries no ``backend``. Reporting
        # "NOT ACTIVE" there would trade a silent lie for a loud one.
        assert DashboardManager._selection_is_live({"nn_model": "cascor", "status": "live"}) is None

    def test_summary_names_the_backend_that_is_really_running(self):
        summary = DashboardManager._model_summary_text(X1_PAYLOAD)
        assert summary.startswith("Selected: Recurrence (LMU)")
        assert "NOT ACTIVE" in summary
        assert "demo" in summary
        # The old, false rendering must be gone outright — not merely supplemented.
        assert not summary.startswith("Active:")

    def test_noop_reselect_of_the_live_model_still_reads_active(self):
        # THE FALSE-POSITIVE GUARD. ``swapped`` is False here too, because re-selecting the model
        # already running is a legitimate no-op. A summary gated on ``swapped`` alone would call a
        # perfectly healthy CasCor "NOT ACTIVE"; this test fails against that naive predicate.
        data = {"nn_model": "cascor", "backend": "cascor", "status": "live", "swapped": False}
        assert DashboardManager._model_summary_text(data) == "Active: CasCor (Cascade-Correlation)"

    def test_lifecycle_status_note_survives_the_truth_up(self):
        # The pre-existing ``· coming soon`` suffix is orthogonal to backend agreement and must
        # still render on both branches.
        live_but_soon = {"nn_model": "recurrence", "backend": "recurrence", "status": "coming_soon", "swapped": True}
        assert DashboardManager._model_summary_text(live_but_soon) == "Active: Recurrence (LMU) · coming soon"
        assert "· coming soon" in DashboardManager._model_summary_text({**X1_PAYLOAD, "status": "coming_soon"})

    def test_the_real_route_payload_reads_not_active(self, monkeypatch):
        """End-to-end: take the ACTUAL wire payload and feed it to the ACTUAL summary.

        The unit cases above assert against a hand-written dict, which pins the summary but not
        the contract between it and the route. This one closes that gap — if
        ``_model_state_response`` ever stops carrying ``backend``, the literal above keeps
        passing and this fails.
        """
        # The D-8 condition: no recurrence service URL configured, default backend live.
        monkeypatch.setattr(main.settings, "recurrence_service_url", None, raising=False)
        monkeypatch.setattr(main, "backend", DemoBackend(DemoMode(update_interval=1.0)), raising=False)

        resp = TestClient(main.app).post("/api/model/select", json={"nn_model": "recurrence"})
        assert resp.status_code == 200, resp.text
        body = resp.json()

        # Precondition: this really is the X1 state (mirrors test_d8_d11_phase4_truth_up.py).
        assert body["nn_model"] == "recurrence"
        assert body["swapped"] is False
        assert body["backend"] != "recurrence"

        summary = DashboardManager._model_summary_text(body)
        assert "NOT ACTIVE" in summary, summary
        assert body["backend"] in summary


# ---------------------------------------------------------------------------
# G1 / G2 / G6 — reachability, safety, and the Start gate
# ---------------------------------------------------------------------------


def _components(tree):
    """Flatten a Dash component tree to a list of components (children may be list/tuple/scalar)."""
    out: list = []
    seen: set = set()

    def visit(node):
        if node is None or isinstance(node, (str, int, float, bool)):
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                visit(child)
            return
        if id(node) in seen:
            return
        seen.add(id(node))
        out.append(node)
        visit(getattr(node, "children", None))

    visit(tree)
    return out


def _dataset_dropdown_is_clearable(manager):
    """Read ``clearable`` off the SHIPPED layout, so G1a goes red when the ✕ is removed.

    Deriving this rather than hard-coding ``True`` is what makes G1a a reachability test instead of
    a restatement of the fix: revert the one-keyword change and the clear transition disappears
    from the BFS below, which is exactly the deadlock.
    """
    for component in _components(manager.app.layout):
        if getattr(component, "id", None) == "nn-dataset-type-dropdown":
            return bool(getattr(component, "clearable", False))
    raise AssertionError("nn-dataset-type-dropdown not found in the layout")


def _selectable_models(manager, dataset_value, models=MODELS, dataset_types=DATASET_TYPES):
    """Model keys whose table Select button is ENABLED for ``dataset_value`` (the real gate)."""
    enabled = set()
    for component in _components(manager._build_model_selection_table(dataset_value, None, models=models, dataset_types=dataset_types)):
        cid = getattr(component, "id", None)
        if isinstance(cid, dict) and cid.get("type") == "model-select-btn" and not getattr(component, "disabled", False):
            enabled.add(cid["index"])
    return enabled


#: Availability injections. ``ALL_AVAILABLE`` is the flag-absent fallback (an empty list means
#: every generator reads available); ``NONE_AVAILABLE`` names every seeded generator as absent,
#: which is the deployed container's real state for the LMU today — ``yfinance`` is not in
#: juniper-data's lockfile — and is the only way to produce the empty compatible ∩ available set.
ALL_AVAILABLE: list = []
NONE_AVAILABLE = [{"name": generator_name_for_type(spec.value), "available": False} for spec in DATASET_TYPES]


def _pickable_datasets(manager, model_key, dataset_value, generators=ALL_AVAILABLE, models=MODELS, dataset_types=DATASET_TYPES):
    """Dataset values the dropdown will actually let the user choose, given the current model.

    Availability is injected as all-available throughout this module. These are REACHABILITY
    assertions about the compatibility gate; letting them inherit a live
    ``/api/dataset/generators`` call would make them depend on whether a service happened to be up,
    and on a runner with no resolver the DNS failure hangs rather than erroring fast. G1d asserts
    the opposite extreme (nothing available) by injecting that instead.
    """
    options, _value, _notice = manager._gate_dataset_options_handler(model_key, dataset_value, generators=generators, models=models, dataset_types=dataset_types)
    if options is dash.no_update:
        return set()
    return {opt["value"] for opt in options if not opt.get("disabled")}


def _model_clear_is_offered(manager):
    """Whether the shipped layout actually offers the model-clear control (N11 / OQ-N6).

    Read from the layout for the same reason ``_dataset_dropdown_is_clearable`` is: it keeps the
    BFS a description of what the UI admits, not a restatement of what this PR changed.
    """
    return any(getattr(c, "id", None) == "model-selection-clear" for c in _components(manager.app.layout))


def _explore(manager, *, clearable=None, model_clearable=None, generators=ALL_AVAILABLE, models=MODELS, dataset_types=DATASET_TYPES, start=None):
    """BFS the COMPOSED transition relation over the real handlers, from the mount state.

    Transitions, each corresponding to a gesture the UI actually exposes:

    1. choose any ENABLED dataset option — the dropdown does not re-gate, because the dataset
       rides as ``State`` on the gate callback, so picking one cannot move the model;
    2. clear the dataset to ``⊥``, only when the shipped dropdown is ``clearable``;
    3. click any ENABLED model Select, which writes ``model-selection-store`` and therefore FIRES
       the gate, which may snap the dataset. The snap is applied here exactly as the callback
       applies it — which is why this must run at handler level. Written over ``model_registry``
       alone, the same assertion goes green against the deadlocked code;
    4. click "Clear model", which writes ``None`` to the same store and re-fires the same gate.

    Transition 4 is why ``⊥`` had to be extended to the model axis. The design defined ``⊥`` on the
    dataset axis only, so ``Reach ⊆ compatible ∪ {(m, ⊥)}`` has no term for a cleared MODEL and
    would fail against the very affordance §4.11 ships.
    """
    if clearable is None:
        clearable = _dataset_dropdown_is_clearable(manager)
    if model_clearable is None:
        model_clearable = _model_clear_is_offered(manager)
    # The layout's seeded value is not the app's first settled state. ``params-init-interval``
    # fires the gate once, ~1 s after load, so the mount pass ALWAYS runs — and where the seeded
    # dataset is unavailable it is cleared before the user can touch anything. Starting the search
    # at the raw layout default would credit the UI with a state it occupies only transiently, and
    # would make G1d assert about a pre-gate snapshot rather than about the recovery state.
    seed_model, seed_dataset = start if start is not None else (DEFAULT_MODEL_KEY, DEFAULT_DATASET_TYPE)
    _options, mounted, _notice = manager._gate_dataset_options_handler(seed_model, seed_dataset, generators=generators, models=models, dataset_types=dataset_types)
    start = (seed_model, seed_dataset if mounted is dash.no_update else mounted)
    seen = {start}
    queue = [start]
    while queue:
        model_key, dataset_value = queue.pop()
        successors = {(model_key, ds) for ds in _pickable_datasets(manager, model_key, dataset_value, generators, models, dataset_types)}
        if clearable:
            successors.add((model_key, None))
        if model_clearable:
            # The clear writes None to the store, which re-fires the gate exactly as a Select does.
            _options, snapped, _notice = manager._gate_dataset_options_handler(None, dataset_value, generators=generators, models=models, dataset_types=dataset_types)
            successors.add((None, dataset_value if snapped is dash.no_update else snapped))
        for target in _selectable_models(manager, dataset_value, models, dataset_types):
            _options, snapped, _notice = manager._gate_dataset_options_handler(target, dataset_value, generators=generators, models=models, dataset_types=dataset_types)
            successors.add((target, dataset_value if snapped is dash.no_update else snapped))
        for state in successors:
            if state not in seen:
                seen.add(state)
                queue.append(state)
    return seen


@pytest.mark.regression
@pytest.mark.unit
class TestG1Reachability:
    """G1a/G1b — every compatible pair reachable, and nothing invalid reachable."""

    def test_g1a_every_compatible_and_available_pair_is_reachable(self, manager):
        missing = {(m.key, d.value) for m in MODELS for d in compatible_datasets(m)} - _explore(manager)
        assert not missing, f"compatible but unreachable: {sorted(missing)}"

    def test_g1a_names_the_pair_this_arc_exists_for(self, manager):
        # Kept separate from the set-difference case so a regression reports the SUBJECT.
        assert ("recurrence", "equities_seq") in _explore(manager)

    def test_g1b_no_reachable_state_is_invalid(self, manager):
        # ``⊥`` must be admitted EXPLICITLY: it is not in compatible(), so a bare
        # ``Reach ⊆ compatible`` would fail on this design's own change. The ``∪ {(m, ⊥)}`` term is
        # the whole difference between "incomplete" and "invalid", and belongs in the assertion
        # rather than only in the prose.
        allowed = {(m.key, d.value) for m in MODELS for d in compatible_datasets(m)} | {(m.key, None) for m in MODELS}
        # N11 extends ``⊥`` to the MODEL axis. A cleared model is incomplete, never invalid: no
        # dataset can disagree with a model that has not been chosen, and Start is disabled there.
        # Without these terms the assertion fails against §4.11's own affordance.
        allowed |= {(None, d.value) for d in DATASET_TYPES} | {(None, None)}
        invalid = _explore(manager) - allowed
        assert not invalid, f"reachable but not compatible: {sorted(invalid)}"

    def test_g2_the_deadlock_returns_only_when_BOTH_clears_are_withheld(self, manager):
        # Ties G1a's pass to a mechanism rather than to coincidence. Withhold both clear
        # affordances and the target pair is unreachable again: this is the deadlock, in-suite.
        reach = _explore(manager, clearable=False, model_clearable=False)
        assert ("recurrence", "equities_seq") not in reach
        assert reach == {("cascor", d.value) for d in compatible_datasets(MODELS[0])}

    @pytest.mark.parametrize(
        "withheld,kept",
        [
            ({"clearable": False}, "the model clear"),
            ({"model_clearable": False}, "the dataset ✕"),
        ],
    )
    def test_g2_either_clear_alone_opens_the_graph(self, manager, withheld, kept):
        # MEASURED, and contrary to how the design frames §4.11: the two affordances are not a fix
        # plus a companion, they are TWO INDEPENDENT CUT VERTICES. Clearing the model ungates the
        # dataset list, from which equities_seq can be picked directly and Recurrence then
        # selected — reaching the target without ever touching the dataset ✕.
        #
        # Consequence worth keeping pinned: removing either one alone does NOT resurface the
        # deadlock, so neither can be regression-tested by its own absence. Only the pair can.
        assert ("recurrence", "equities_seq") in _explore(manager, **withheld), f"{kept} should still reach it"


@pytest.mark.regression
@pytest.mark.unit
class TestG6StartRequiresACompleteSelection:
    """G6 / X5 — Start is disabled at ``⊥`` on EITHER axis."""

    @staticmethod
    def _appearance(manager, model_key, dataset_value):
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        return manager._update_button_appearance_handler(button_states=states, model_key=model_key, dataset_value=dataset_value)

    def test_a_complete_selection_leaves_start_enabled(self, manager):
        assert self._appearance(manager, "cascor", "spirals")[0] is False

    @pytest.mark.parametrize("empty", [None, ""])
    def test_start_is_disabled_with_no_dataset(self, manager, empty):
        # Before the ✕ this state could not exist. Now it can, and an unguarded cascor start would
        # train on whatever was LAST STAGED while the sidebar showed no dataset.
        assert self._appearance(manager, "cascor", empty)[0] is True

    @pytest.mark.parametrize("empty", [None, ""])
    def test_start_is_disabled_with_no_model(self, manager, empty):
        # ``model_is_trainable(None)`` answers True by design, so the model axis needs its own
        # check — otherwise the "clear model / show all" affordance ships an ungated Start.
        assert self._appearance(manager, empty, "spirals")[0] is True

    def test_apply_dataset_is_disabled_exactly_when_the_dataset_is_unset(self, manager):
        assert self._appearance(manager, "cascor", "spirals")[-1] is False
        assert self._appearance(manager, "cascor", None)[-1] is True


@pytest.mark.regression
@pytest.mark.unit
class TestCommitPathsAreGuarded:
    """Every path that could COMMIT a ``⊥`` refuses it — and none of them was merely vacuous."""

    def test_apply_dataset_refuses_and_does_not_post(self, manager):
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            banner, alert = manager._apply_dataset_handler(1, None, 100, 0.1, 2.0, 2)
        # An empty body is not a no-op: cascor documents it as clearing any prior staging, so this
        # click used to DISCARD a dataset change the operator had already staged.
        post.assert_not_called()
        assert banner is False
        assert alert is not None

    def test_restage_refuses_and_does_not_post(self, manager):
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            ok, detail = manager._restage_dataset({"dataset_type": None, "n_samples": 100})
        post.assert_not_called()
        assert ok is False
        assert "No dataset" in detail

    def test_live_swap_refuses_and_does_not_post(self, manager):
        # The most expensive path: the backend's live swap stops the training future and discards
        # in-flight candidates, so an unguarded empty body destroys a running experiment — and
        # rendered "Live dataset swap complete." while doing it.
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            modal, _progress, alert, in_flight = manager._accept_live_switch_handler(1, None, 100, 0.1, 2, 2.0)
        post.assert_not_called()
        assert modal is False and in_flight is False
        assert alert is not None

    def test_the_live_swap_confirmation_names_the_missing_dataset(self, manager):
        # N4: name the consequence at the locus. The row used to be skipped like any other absent
        # field, so the user confirmed a swap whose target was unset without being told.
        _is_open, rows = manager._open_live_switch_modal_handler(1, None, 100, 0.1, 2, 2.0)
        assert "none selected" in " ".join(str(row) for row in rows)


# ---------------------------------------------------------------------------
# G8 / Y9 — the model axis clears, ungates its peer, and stops overclaiming
# ---------------------------------------------------------------------------


@pytest.mark.regression
@pytest.mark.unit
class TestG8ClearedModelUngatesTheDataset:
    """G8 — a cleared model renders ungated dataset options, not ``no_update``."""

    def test_the_clear_control_exists_in_the_layout(self, manager):
        # §5.5's second affordance was specified at canopy#394, deferred on a premise that #397
        # falsified 13 hours later, and never revisited. Pin its existence.
        assert _model_clear_is_offered(manager)

    @pytest.mark.parametrize("empty", [None, ""])
    def test_a_cleared_model_ungates_every_compatible_dataset(self, manager, empty):
        options, _value, _notice = manager._gate_dataset_options_handler(empty, "spirals", generators=[])
        assert options is not dash.no_update
        enabled = {o["value"] for o in options if not o.get("disabled")}
        # Ungated means the union of both models' datasets is offered — in particular the one the
        # deadlock hid, which no single model's gate would enable alongside the others.
        assert "equities_seq" in enabled
        assert "spirals" in enabled

    def test_clearing_the_model_keeps_the_dataset(self, manager):
        # §5.6's dataset-primary conflict policy, expressible for the first time now that BOTH
        # axes can be cleared.
        _options, value, _notice = manager._gate_dataset_options_handler(None, "equities_seq", generators=[])
        assert value is dash.no_update

    def test_the_clear_writes_none_and_does_not_post(self, manager):
        # Clearing is a statement about the UI's filter, not a request to change the live backend,
        # and there is no "no model" for /api/model/select to select.
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            store, model_class, summary, is_open, state = manager._select_model_from_table_handler([], "model-selection-clear", 1)
        post.assert_not_called()
        assert store is None
        assert model_class is dash.no_update
        assert is_open is False
        assert "No model selected" in summary
        # N5: no selection has round-tripped, so the payload store is unknown, not stale.
        assert state is None

    def test_the_clear_is_inert_before_it_is_clicked(self, manager):
        # The button is in the DOM from first paint; its callback must not fire on the no-click.
        assert manager._select_model_from_table_handler([], "model-selection-clear", None) == (dash.no_update,) * 5

    def test_start_stays_disabled_at_a_cleared_model(self, manager):
        # The ungated-Start hole that §4.11 would otherwise have shipped. Pinned here, at the
        # affordance that opens it, as well as in the G6 suite.
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        assert manager._update_button_appearance_handler(button_states=states, model_key=None, dataset_value="spirals")[0] is True


@pytest.mark.regression
@pytest.mark.unit
class TestY9ModelTableDoesNotOverclaimAtBottom:
    """Y9 — at ``⊥`` the table must not report every model as compatible."""

    def test_no_row_claims_compatibility_without_a_dataset(self, manager):
        rendered = " ".join(str(c) for c in _components(manager._build_model_selection_table(None, "cascor")))
        assert "✓ compatible" not in rendered

    def test_each_row_states_what_it_would_require(self, manager):
        rendered = " ".join(str(c) for c in _components(manager._build_model_selection_table(None, "cascor")))
        # The requirement is stated per model, from the registry, not hard-coded here.
        for model in MODELS:
            assert model_requirement(model) in rendered

    def test_every_select_stays_enabled_without_a_dataset(self, manager):
        # THE guard on the Y9 fix. ``⊥`` is compatible with every model — that is what makes it the
        # cut vertex — so correcting the CLAIM must not re-disable the control. Re-disabling here
        # would silently restore the deadlock while the compatibility cell read honestly.
        assert _selectable_models(manager, None) == {model.key for model in MODELS}

    def test_a_real_dataset_still_reports_compatibility_normally(self, manager):
        rendered = " ".join(str(c) for c in _components(manager._build_model_selection_table("spirals", "cascor")))
        assert "✓ compatible" in rendered


# ---------------------------------------------------------------------------
# G3 / G1d — the empty compatible ∩ available set, and the notices
# ---------------------------------------------------------------------------


def _alert_text(component):
    """Flatten an alert component tree to its rendered text."""
    return " ".join(str(c) for c in _components(component))


@pytest.mark.regression
@pytest.mark.unit
class TestG3EmptySetRecovery:
    """G3 — an empty compatible ∩ available set renders a recovery state, never ``no_update``."""

    def test_the_empty_set_clears_the_dataset_instead_of_parking_on_it(self, manager):
        # The old code returned ``no_update`` here, so the dropdown kept showing a dataset its OWN
        # list disables — a committed state the gate had already judged unusable.
        _options, value, notice = manager._gate_dataset_options_handler("recurrence", "equities_seq", generators=NONE_AVAILABLE)
        assert value is None
        assert notice is not None

    def test_the_empty_set_notice_is_persistent_not_transient(self, manager):
        # N12: "persistent until resolved" applies to THIS event and only this one. A duration
        # would auto-dismiss a blocking state the operator has not resolved.
        _options, _value, notice = manager._gate_dataset_options_handler("recurrence", "equities_seq", generators=NONE_AVAILABLE)
        assert getattr(notice, "duration", None) is None
        assert "No dataset is available" in _alert_text(notice)

    def test_the_empty_set_notice_names_the_model_and_the_remedy(self, manager):
        _options, _value, notice = manager._gate_dataset_options_handler("recurrence", "equities_seq", generators=NONE_AVAILABLE)
        text = _alert_text(notice)
        assert "Recurrence (LMU)" in text
        assert "juniper-data" in text

    def test_clearing_the_dataset_here_disables_start_and_apply(self, manager):
        # The recovery state must not merely be legible; it must be safe. Clearing to ⊥ reaches the
        # gates that already exist rather than adding a third one.
        _options, value, _notice = manager._gate_dataset_options_handler("recurrence", "equities_seq", generators=NONE_AVAILABLE)
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        appearance = manager._update_button_appearance_handler(button_states=states, model_key="recurrence", dataset_value=value)
        assert appearance[0] is True
        assert appearance[-1] is True


@pytest.mark.regression
@pytest.mark.unit
class TestDatasetRepairNotice:
    """§4.3 / D5 — the notice the snap was always specified to render and never did."""

    def test_a_repaired_gate_names_the_old_and_the_new_value(self, manager):
        _options, value, notice = manager._gate_dataset_options_handler("recurrence", "spirals", generators=ALL_AVAILABLE)
        # §12 moved the snap target: the five synthetic rank-3 seeds precede equities_seq, so the
        # first compatible entry is now multi_sine. The NOTICE's contract is unchanged — it must
        # still name both ends of the move and the model that caused it.
        assert value == "multi_sine"
        text = _alert_text(notice)
        # "The dataset changed" without saying from what to what is an alarm, not a notice.
        assert "Spirals" in text
        assert "Multi-Sine (sequence)" in text
        assert "Recurrence (LMU)" in text

    def test_the_repair_notice_is_transient(self, manager):
        # N12's other half: a successful repair is informational — there is nothing to resolve.
        _options, _value, notice = manager._gate_dataset_options_handler("recurrence", "spirals", generators=ALL_AVAILABLE)
        assert getattr(notice, "duration", None) is not None
        assert notice.dismissable is True

    def test_no_notice_when_the_gate_changes_nothing(self, manager):
        # And it must CLEAR a stale one rather than leaving the last repair on screen forever.
        _options, value, notice = manager._gate_dataset_options_handler("cascor", "spirals", generators=ALL_AVAILABLE)
        assert value is dash.no_update
        assert notice is None


@pytest.mark.regression
@pytest.mark.unit
class TestG1dNothingAvailable:
    """G1d — with nothing available, assert the RECOVERY state, not reachability.

    The design filed G1d under "must pass after" with a reachability assertion, which is
    unsatisfiable: with no dataset available there is nothing to reach. It asserts §4.7 instead.
    """

    def test_no_pair_is_reachable_and_that_is_correct(self, manager):
        reach = _explore(manager, generators=NONE_AVAILABLE)
        # Every reachable state is incomplete on the dataset axis — there is no available dataset
        # to complete it with. This is a vacuous pass FOR REACHABILITY and a real assertion about ⊥.
        assert all(dataset is None for _model, dataset in reach), sorted(map(repr, reach))

    def test_i_safe_still_holds_with_nothing_available(self, manager):
        # G1b's assertion must survive the degenerate case: incomplete, never invalid.
        allowed = {(m.key, None) for m in MODELS} | {(None, None)}
        assert _explore(manager, generators=NONE_AVAILABLE) - allowed == set()

    def test_every_model_still_reports_the_recovery_state(self, manager):
        for model in MODELS:
            _options, value, notice = manager._gate_dataset_options_handler(model.key, DEFAULT_DATASET_TYPE, generators=NONE_AVAILABLE)
            assert value is None, model.key
            assert notice is not None, model.key


# ---------------------------------------------------------------------------
# G1c — the invariants over a synthetic >=3-component registry
# ---------------------------------------------------------------------------

# Three models over four datasets, partitioned into THREE components by rank and task. The shipped
# registry has exactly two, so the Confinement Lemma's reach is only ever exercised at n=2 there —
# and a fix that happened to work for two components could pass every other guardrail while leaving
# a three-component registry trapped. §12.2 argues the seeded expansion keeps the component count
# at two; this is the case that argument does NOT cover.
SYNTH_MODELS = (
    ModelSpec(key="m_flat", label="Flat", category="c", input_ndim=frozenset({2}), supported_task_types=frozenset({"classification"}), family="f", status="live", provider="in-process", description=""),
    ModelSpec(key="m_seq", label="Seq", category="c", input_ndim=frozenset({3}), supported_task_types=frozenset({"regression"}), family="f", status="live", provider="in-process", description=""),
    ModelSpec(key="m_vol", label="Vol", category="c", input_ndim=frozenset({4}), supported_task_types=frozenset({"regression"}), family="f", status="live", provider="in-process", description=""),
)
SYNTH_DATASETS = (
    DatasetTypeSpec(value="d_flat_a", label="Flat A", task_type="classification", ndim=2),
    DatasetTypeSpec(value="d_flat_b", label="Flat B", task_type="classification", ndim=2),
    DatasetTypeSpec(value="d_seq", label="Seq", task_type="regression", ndim=3),
    DatasetTypeSpec(value="d_vol", label="Vol", task_type="regression", ndim=4),
)
SYNTH_START = ("m_flat", "d_flat_a")


def _synth_explore(manager, **kwargs):
    return _explore(manager, models=SYNTH_MODELS, dataset_types=SYNTH_DATASETS, start=SYNTH_START, **kwargs)


@pytest.mark.regression
@pytest.mark.unit
class TestG1cThreeComponents:
    """G1c — I-cover and I-safe over a registry with three disjoint components."""

    def test_the_fixture_really_has_three_components(self, manager):
        # Guard the guard. If a future edit collapses these into two, G1c silently stops testing
        # the thing it exists for while still passing.
        pairs = {(m.key, d.value) for m in SYNTH_MODELS for d in SYNTH_DATASETS if compatible(d, m)}
        by_model = {m.key: {d for mk, d in pairs if mk == m.key} for m in SYNTH_MODELS}
        assert by_model["m_flat"] == {"d_flat_a", "d_flat_b"}
        assert by_model["m_seq"] == {"d_seq"}
        assert by_model["m_vol"] == {"d_vol"}
        # Disjoint: no dataset accepts two models.
        assert len({d for ds in by_model.values() for d in ds}) == 4

    def test_g1c_every_compatible_pair_is_reachable(self, manager):
        reach = _synth_explore(manager)
        compatible_pairs = {(m.key, d.value) for m in SYNTH_MODELS for d in SYNTH_DATASETS if compatible(d, m)}
        assert not compatible_pairs - reach, f"unreachable: {sorted(compatible_pairs - reach)}"

    def test_g1c_no_reachable_state_is_invalid(self, manager):
        allowed = {(m.key, d.value) for m in SYNTH_MODELS for d in SYNTH_DATASETS if compatible(d, m)}
        allowed |= {(m.key, None) for m in SYNTH_MODELS} | {(None, d.value) for d in SYNTH_DATASETS} | {(None, None)}
        assert not _synth_explore(manager) - allowed

    def test_g1c_is_the_case_the_shipped_registry_cannot_produce(self, manager):
        # Without BOTH clears, a three-component registry strands TWO components, not one — which
        # is the whole reason a synthetic case is needed: the shipped two-component registry can
        # only ever strand one, so it cannot distinguish a fix that generalises from one that does
        # not.
        trapped = _synth_explore(manager, clearable=False, model_clearable=False)
        assert trapped == {("m_flat", "d_flat_a"), ("m_flat", "d_flat_b")}
        stranded = {("m_seq", "d_seq"), ("m_vol", "d_vol")}
        assert not (trapped & stranded)


# ---------------------------------------------------------------------------
# N5 — Start requires the selected model to be the one that would RUN
# ---------------------------------------------------------------------------
#
# G5 (above) made the sidebar tell the truth about ``X1_PAYLOAD``; nothing stopped the run. The
# Start gate read ``model_is_trainable`` (registry lifecycle, "live" for both shipped models) plus
# both axes being set, and ``(recurrence, equities_seq)`` passes every one of those -- so with
# ``recurrence_service_url`` unset a user selected Recurrence, read "NOT ACTIVE", pressed Start,
# and got a cascor/demo run filed under Recurrence (LMU). Handoff item 1; design N5 / §4.4.

# The healthy no-op re-select: ``swapped`` is False here too. Any predicate that disables Start on
# this payload has re-introduced the false positive G5's ``test_noop_reselect...`` guards.
LIVE_RESELECT_PAYLOAD = {"nn_model": "cascor", "backend": "demo", "execution": "continuous", "status": "live", "swapped": False}
RECURRENCE_LIVE_PAYLOAD = {"nn_model": "recurrence", "backend": "recurrence", "execution": "one_shot", "status": "live", "swapped": True}


def _text_of(component):
    """Concatenate every string reachable through ``.children`` of a Dash component tree."""
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return "".join(_text_of(child) for child in component)
    return _text_of(getattr(component, "children", None))


def _callback_writing(manager, output_ref):
    """The single ``callback_map`` entry whose output key mentions ``output_ref`` (``"<id>.<prop>"``)."""
    keys = [key for key in manager.app.callback_map if output_ref in key]
    assert len(keys) == 1, f"expected exactly one writer of {output_ref!r}, found {keys}"
    return keys[0], manager.app.callback_map[keys[0]]


def _string_input_ids(callback_info):
    return {entry.get("id") for entry in callback_info.get("inputs", []) if isinstance(entry.get("id"), str)}


@pytest.mark.regression
@pytest.mark.unit
class TestN5StartRequiresBackendAgreement:
    """N5 — a model that is selected but not ACTIVE must not be startable: the gate, not the label."""

    @staticmethod
    def _appearance(manager, model_key, dataset_value, model_state):
        states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        return manager._update_button_appearance_handler(button_states=states, model_key=model_key, dataset_value=dataset_value, model_state=model_state)

    def test_the_predicate_is_provider_agreement_over_the_real_backend_domain(self):
        # The full truth table over {"service", "demo", "recurrence"} -- no "cascor".
        assert selection_is_live("recurrence", "demo") is False
        assert selection_is_live("recurrence", "service") is False
        assert selection_is_live("recurrence", "recurrence") is True
        assert selection_is_live("cascor", "demo") is True
        assert selection_is_live("cascor", "service") is True
        assert selection_is_live("cascor", "recurrence") is False

    def test_unknown_on_either_side_is_not_disagreement(self):
        assert selection_is_live("cascor", None) is None
        assert selection_is_live("cascor", "") is None
        assert selection_is_live(None, "demo") is None
        assert selection_is_live("", "demo") is None

    def test_the_sidebar_and_the_gate_share_the_predicate(self):
        # canopy#592 fixed the label with a private predicate the gate never saw. The summary now
        # delegates to the registry function, so the two cannot answer differently again.
        assert DashboardManager._selection_is_live(X1_PAYLOAD) is False
        assert DashboardManager._selection_is_live(LIVE_RESELECT_PAYLOAD) is True
        assert DashboardManager._selection_is_live(None) is None
        assert DashboardManager.RECURRENCE_BACKEND_TYPE == "recurrence"

    def test_start_is_disabled_for_a_selected_but_inactive_model(self, manager):
        # THE defect. (recurrence, equities_seq) is complete, compatible and lifecycle-live --
        # every gate that existed passes -- and the backend that would run is demo.
        assert self._appearance(manager, "recurrence", "equities_seq", X1_PAYLOAD)[0] is True

    def test_start_stays_enabled_on_the_noop_reselect(self, manager):
        # The false-positive guard: ``swapped`` is False here as well.
        assert self._appearance(manager, "cascor", "spirals", LIVE_RESELECT_PAYLOAD)[0] is False

    def test_start_is_enabled_when_the_recurrence_backend_really_runs(self, manager):
        assert self._appearance(manager, "recurrence", "equities_seq", RECURRENCE_LIVE_PAYLOAD)[0] is False

    def test_first_paint_is_unknown_and_stays_enabled(self, manager):
        # Nothing has round-tripped; the boot backend serves the default model by construction.
        assert self._appearance(manager, "cascor", "spirals", None)[0] is False

    def test_the_other_controls_are_untouched(self, manager):
        out = self._appearance(manager, "recurrence", "equities_seq", X1_PAYLOAD)
        assert out[0] is True
        # pause / stop / resume / reset follow button-states untouched.
        assert (out[2], out[4], out[6], out[8]) == (False, False, False, False)
        # Apply Dataset follows the same gate as Start since the staging fix (X6 / §4.9): staging
        # toward a backend the selection does not target is exactly how a rank-3 dataset reached
        # cascor. Pinned in full in test_recurrence_staging.py.
        assert out[-1] is True

    def test_the_notice_names_the_model_the_backend_and_the_consequence(self):
        notice = DashboardManager._train_gate_notice_handler("recurrence", model_state=X1_PAYLOAD)
        assert notice is not None
        text = _text_of(notice)
        assert "Recurrence (LMU)" in text
        assert "demo" in text
        assert "Start and Apply Dataset are disabled" in text
        assert "filed under Recurrence (LMU)" in text

    def test_the_notice_is_hidden_while_the_two_agree(self):
        assert DashboardManager._train_gate_notice_handler("cascor", model_state=LIVE_RESELECT_PAYLOAD) is None
        assert DashboardManager._train_gate_notice_handler("recurrence", model_state=RECURRENCE_LIVE_PAYLOAD) is None
        assert DashboardManager._train_gate_notice_handler("cascor", model_state=None) is None
        assert DashboardManager._train_gate_notice_handler("cascor") is None

    def test_the_select_handler_mirrors_the_whole_payload(self, manager):
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            post.return_value = mock.Mock(ok=True, json=lambda: dict(X1_PAYLOAD))
            store, model_class, summary, state = manager._select_model_handler("recurrence")
        assert store == "recurrence"
        assert state == X1_PAYLOAD
        assert "NOT ACTIVE" in summary

    def test_the_state_store_has_one_writer_and_it_is_the_selection_writer(self, manager):
        # The duplicate-writer hazard N11 names: the key and the payload must come from the same
        # callback, or a stale payload could gate a fresh key (or the reverse).
        key, _info = _callback_writing(manager, "model-state-store.data")
        assert "model-selection-store.data" in key

    def test_both_gate_callbacks_read_the_state_store_as_an_input(self, manager):
        # An Input, not a State: State does not trigger, so the gate would be real in the handler
        # and absent in the UI (the X5 lesson on the dataset axis).
        _key, start_gate = _callback_writing(manager, "start-button.disabled")
        assert {"model-selection-store", "model-state-store", "nn-dataset-type-dropdown"} <= _string_input_ids(start_gate)
        _key, notice = _callback_writing(manager, "train-gate-notice.children")
        assert {"model-selection-store", "model-state-store"} <= _string_input_ids(notice)

    def test_the_store_is_seeded_unknown(self, manager):
        stores = [c for c in _components(manager.app.layout) if getattr(c, "id", None) == "model-state-store"]
        assert len(stores) == 1
        assert stores[0].data is None
        assert stores[0].storage_type == "memory"


@pytest.mark.regression
@pytest.mark.unit
class TestN5TheServerRefusesAnInactiveSelection:
    """The gate is at the control; this is what stops the run when anything else sends it.

    Both transports the Start button uses (REST fallback and ``/ws/control``), plus the restart
    orchestration the dataset modal uses, and ``curl``. The condition is recorded on the server
    exactly as the D-8 tests record it: Recurrence selected over the demo backend with no service
    URL, which ``/api/model/select`` accepts with 200.
    """

    @pytest.fixture
    def demo_over_recurrence(self, monkeypatch):
        with TestClient(main.app) as client:
            monkeypatch.setattr(main.settings, "recurrence_service_url", None, raising=False)
            fake = mock.MagicMock()
            fake.backend_type = "demo"
            fake.execution = "continuous"
            fake.is_training_active.return_value = False
            fake.start_training.return_value = {"ok": True}
            fake.stop_training.return_value = {"ok": True}
            monkeypatch.setattr(main, "backend", fake, raising=False)
            monkeypatch.setattr(main, "current_nn_model", None, raising=False)
            resp = client.post("/api/model/select", json={"nn_model": "recurrence"})
            assert resp.status_code == 200, resp.text
            assert resp.json()["swapped"] is False and resp.json()["backend"] == "demo"
            yield client, fake
            # Hand the real backend back before the lifespan shuts it down.
            monkeypatch.undo()

    def test_rest_start_is_refused_and_nothing_starts(self, demo_over_recurrence):
        client, fake = demo_over_recurrence
        resp = client.post("/api/train/start")
        assert resp.status_code == 409, resp.text
        detail = resp.json()["detail"]
        assert "Recurrence (LMU)" in detail
        assert "demo" in detail
        fake.start_training.assert_not_called()

    def test_restart_is_refused_before_anything_is_stopped(self, demo_over_recurrence):
        client, fake = demo_over_recurrence
        fake.is_training_active.return_value = True
        resp = client.post("/api/train/restart", json={"start_fresh": True, "reset": True})
        assert resp.status_code == 409, resp.text
        body = resp.json()
        assert body["success"] is False
        assert body["was_active"] is True  # reported truthfully...
        fake.stop_training.assert_not_called()  # ...and NOT acted on
        fake.start_training.assert_not_called()
        assert [step["step"] for step in body["steps"]] == ["start"]
        assert "demo" in body["message"]

    def test_ws_start_is_refused_with_an_error_envelope(self, demo_over_recurrence):
        client, fake = demo_over_recurrence
        with client.websocket_connect("/ws/control") as websocket:
            assert websocket.receive_json().get("type") == "connection_established"
            websocket.send_json({"command": "start", "command_id": "n5-1", "reset": True})
            for _ in range(100):
                response = websocket.receive_json()
                if response.get("type") == "command_response":
                    break
            else:
                raise AssertionError("no command_response")
        assert response["data"]["status"] == "error"
        assert response["data"]["command_id"] == "n5-1"
        assert "demo" in response["data"]["error"]
        assert response["ok"] is False
        fake.start_training.assert_not_called()

    def test_a_live_selection_still_starts(self, demo_over_recurrence):
        # The false-positive guard at the server: re-selecting cascor over demo is a no-op swap
        # (``swapped`` False) and must start normally.
        client, fake = demo_over_recurrence
        assert client.post("/api/model/select", json={"nn_model": "cascor"}).status_code == 200
        resp = client.post("/api/train/start")
        assert resp.status_code == 200, resp.text
        fake.start_training.assert_called_once()

    def test_nothing_selected_yet_is_not_a_refusal(self, monkeypatch):
        fake = mock.MagicMock()
        fake.backend_type = "demo"
        monkeypatch.setattr(main, "backend", fake, raising=False)
        monkeypatch.setattr(main, "current_nn_model", None, raising=False)
        assert main._selection_inactive_reason() is None
        monkeypatch.setattr(main, "current_nn_model", "cascor", raising=False)
        assert main._selection_inactive_reason() is None
        monkeypatch.setattr(main, "current_nn_model", "recurrence", raising=False)
        reason = main._selection_inactive_reason()
        assert reason is not None and "demo" in reason and "Recurrence (LMU)" in reason

    def test_the_selection_does_not_leak_into_the_next_test(self):
        # conftest resets ``main.current_nn_model`` between tests; without that, the two D-8 tests
        # that select Recurrence over demo would 409 every later ``/api/train/start``.
        assert main.current_nn_model is None
