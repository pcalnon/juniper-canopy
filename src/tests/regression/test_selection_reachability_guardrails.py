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
from demo_mode import DemoMode
from frontend.dashboard_manager import DashboardManager
from model_registry import DATASET_TYPES, DEFAULT_DATASET_TYPE, DEFAULT_MODEL_KEY, MODELS, compatible_datasets, model_requirement


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


def _selectable_models(manager, dataset_value):
    """Model keys whose table Select button is ENABLED for ``dataset_value`` (the real gate)."""
    enabled = set()
    for component in _components(manager._build_model_selection_table(dataset_value, None)):
        cid = getattr(component, "id", None)
        if isinstance(cid, dict) and cid.get("type") == "model-select-btn" and not getattr(component, "disabled", False):
            enabled.add(cid["index"])
    return enabled


def _pickable_datasets(manager, model_key, dataset_value):
    """Dataset values the dropdown will actually let the user choose, given the current model."""
    options, _value = manager._gate_dataset_options_handler(model_key, dataset_value)
    if options is dash.no_update:
        return set()
    return {opt["value"] for opt in options if not opt.get("disabled")}


def _model_clear_is_offered(manager):
    """Whether the shipped layout actually offers the model-clear control (N11 / OQ-N6).

    Read from the layout for the same reason ``_dataset_dropdown_is_clearable`` is: it keeps the
    BFS a description of what the UI admits, not a restatement of what this PR changed.
    """
    return any(getattr(c, "id", None) == "model-selection-clear" for c in _components(manager.app.layout))


def _explore(manager, *, clearable=None, model_clearable=None):
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
    start = (DEFAULT_MODEL_KEY, DEFAULT_DATASET_TYPE)
    seen = {start}
    queue = [start]
    while queue:
        model_key, dataset_value = queue.pop()
        successors = {(model_key, ds) for ds in _pickable_datasets(manager, model_key, dataset_value)}
        if clearable:
            successors.add((model_key, None))
        if model_clearable:
            # The clear writes None to the store, which re-fires the gate exactly as a Select does.
            _options, snapped = manager._gate_dataset_options_handler(None, dataset_value)
            successors.add((None, dataset_value if snapped is dash.no_update else snapped))
        for target in _selectable_models(manager, dataset_value):
            _options, snapped = manager._gate_dataset_options_handler(target, dataset_value)
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
        options, _value = manager._gate_dataset_options_handler(empty, "spirals")
        assert options is not dash.no_update
        enabled = {o["value"] for o in options if not o.get("disabled")}
        # Ungated means the union of both models' datasets is offered — in particular the one the
        # deadlock hid, which no single model's gate would enable alongside the others.
        assert "equities_seq" in enabled
        assert "spirals" in enabled

    def test_clearing_the_model_keeps_the_dataset(self, manager):
        # §5.6's dataset-primary conflict policy, expressible for the first time now that BOTH
        # axes can be cleared.
        _options, value = manager._gate_dataset_options_handler(None, "equities_seq")
        assert value is dash.no_update

    def test_the_clear_writes_none_and_does_not_post(self, manager):
        # Clearing is a statement about the UI's filter, not a request to change the live backend,
        # and there is no "no model" for /api/model/select to select.
        with mock.patch("frontend.dashboard_manager.requests.post") as post:
            store, model_class, summary, is_open = manager._select_model_from_table_handler([], "model-selection-clear", 1)
        post.assert_not_called()
        assert store is None
        assert model_class is dash.no_update
        assert is_open is False
        assert "No model selected" in summary

    def test_the_clear_is_inert_before_it_is_clicked(self, manager):
        # The button is in the DOM from first paint; its callback must not fire on the no-click.
        assert manager._select_model_from_table_handler([], "model-selection-clear", None) == (dash.no_update,) * 4

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
