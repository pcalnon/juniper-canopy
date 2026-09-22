#!/usr/bin/env python
"""F-CANOPY-048: the replay controls never applied -- and a guard for the whole cycle class.

Finding: juniper-ml ``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md``
(F-CANOPY-048, P2). Clean room: juniper-ml
``util/ad-hoc/2026-09-22_f048_replay_cycle_cleanroom.py``.

``handle_replay_controls`` (Input ``replay-slider.value`` -> Output ``replay-state.data``) and
``update_replay_ui`` (Input ``replay-state.data`` -> Output ``replay-slider.value``) formed a
cycle across two callbacks. dash-renderer promotes a requested callback only when none of its
Inputs, less its own Outputs, lies in the downstream closure of any pending callback, itself
included (``getReadyCallbacks``, dash_renderer.dev.js:1633-1665, dash 4.2.0). Each covered its
own Input through the other, so neither was ever ready; the circular-dependency breaker (:3064)
fires only when nothing else is pending, which canopy's pollers never allow. A live census found
all three replay callbacks in ``requested`` in 6471 of 6471 samples, and zero ``replay-state``
writes across ten clicks. The clean room locked 3/3 with the cycle plus an always-pending
feeder, was live 3/3 with the slider as State, and did not lock without the feeder.

The fix merges the two into one callback that reads AND writes ``replay-slider.value``.

What these tests prove:
  * SEMANTICS -- for every control, the merged handler returns exactly what the old
    controls callback returned, followed by what the old UI callback rendered from that state
    (a differential check against verbatim copies of both, below). A refresh trigger (a
    ``replay_tick`` write, a metrics refill, the mount call) never rewrites the state, so it
    cannot pause playback or move the index.
  * WIRING -- the registered callback is the only writer of the slider and reads it too, and
    every control Input it registers is one the handler dispatches on.
  * ACYCLICITY -- no cycle spanning two or more distinct callbacks exists anywhere in the BUILT
    app (the served ``/_dash-dependencies``), bar two named, pre-existing exemptions; and no
    replay-block callback's own readiness closure covers one of its own Inputs.

What they cannot prove: that the LIVE renderer now promotes the merged callback. That depends
on runtime pendingness -- it is not ready while a primary writer of the metrics store is
pending -- and is left to a live verify leg.

Verified against the parent commit (886147b5): the two graph tests below that encode the
defect FAIL there (the whole-app scan finds the replay SCC; both old callbacks are
self-blocked), and so do the handler and wiring tests (no merged handler; two slider writers).
"""

import copy
import json
from collections import defaultdict

import dash
import pytest
from dash import Dash, dcc, html

from frontend.components.metrics_panel import MetricsPanel

CID = "metrics-panel"
SLIDER_VALUE = f"{CID}-replay-slider.value"
STATE_DATA = f"{CID}-replay-state.data"
METRICS_DATA = f"{CID}-metrics-store.data"

CONTROL_INPUTS = {
    "replay-play": "n_clicks",
    "replay-step-back": "n_clicks",
    "replay-step-forward": "n_clicks",
    "replay-start": "n_clicks",
    "replay-end": "n_clicks",
    "speed-1x": "n_clicks",
    "speed-2x": "n_clicks",
    "speed-4x": "n_clicks",
    "replay-slider": "value",
}


def _prop(suffix):
    return f"{CID}-{suffix}.{CONTROL_INPUTS[suffix]}"


# ---------------------------------------------------------------------------------------------
# The pre-merge callbacks, VERBATIM from canopy main 886147b5
# (src/frontend/components/metrics_panel.py:995-1044 and :1086-1094), with one change: the
# trigger is passed in rather than read from ``dash.callback_context``. They are the oracle.
# ---------------------------------------------------------------------------------------------
def _old_handle_replay_controls(trigger, slider_value, current_state, metrics_data):
    state = (
        current_state.copy()
        if current_state
        else {
            "mode": "stopped",
            "speed": 1.0,
            "current_index": 0,
            "start_index": 0,
            "end_index": None,
        }
    )

    max_index = len(metrics_data) - 1 if metrics_data else 0
    state["end_index"] = state.get("end_index") or max_index

    if "replay-play" in trigger:
        state["mode"] = "paused" if state["mode"] == "playing" else "playing"
    elif "step-back" in trigger:
        state["mode"] = "paused"
        state["current_index"] = max(0, state["current_index"] - 1)
    elif "step-forward" in trigger:
        state["mode"] = "paused"
        state["current_index"] = min(max_index, state["current_index"] + 1)
    elif "replay-start" in trigger:
        state["current_index"] = state["start_index"]
        state["mode"] = "paused"
    elif "replay-end" in trigger:
        state["current_index"] = state["end_index"] or max_index
        state["mode"] = "paused"
    elif "speed-1x" in trigger:
        state["speed"] = 1.0
    elif "speed-2x" in trigger:
        state["speed"] = 2.0
    elif "speed-4x" in trigger:
        state["speed"] = 4.0
    elif "replay-slider" in trigger:
        state["current_index"] = int((slider_value / 100) * max_index) if max_index > 0 else 0
        state["mode"] = "paused"

    base_interval = 1000
    interval = int(base_interval / state["speed"])
    disabled = state["mode"] != "playing"

    return state, disabled, interval


def _old_update_replay_ui(state, metrics_data):
    max_index = len(metrics_data) - 1 if metrics_data else 0
    current_index = state.get("current_index", 0) if state else 0

    slider_value = (current_index / max_index * 100) if max_index > 0 else 0
    position_text = f"{current_index} / {max_index}"

    return slider_value, 100, position_text


STATES = [
    None,
    {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None},
    {"mode": "playing", "speed": 2.0, "current_index": 7, "start_index": 0, "end_index": None},
    {"mode": "paused", "speed": 4.0, "current_index": 49, "start_index": 3, "end_index": 20},
    {"mode": "playing", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": 0},
]
METRICS = [None, [], [{"epoch": 0}], [{"epoch": i} for i in range(2)], [{"epoch": i} for i in range(50)]]
SLIDER_VALUES = [0, 33, 50, 100, 42.857142857142854]


@pytest.fixture
def panel():
    return MetricsPanel({}, component_id=CID)


# ---------------------------------------------------------------------------------------------
# SEMANTICS
# ---------------------------------------------------------------------------------------------
@pytest.mark.unit
class TestMergedHandlerMatchesTheOldCallbacks:
    @pytest.mark.parametrize("control", sorted(CONTROL_INPUTS))
    def test_each_control_matches_old_controls_then_old_ui(self, panel, control):
        """Differential: new(control) == old_controls(control) followed by old_ui(that state)."""
        cases = 0
        for state in STATES:
            for metrics in METRICS:
                for slider in SLIDER_VALUES:
                    old_state, old_disabled, old_interval = _old_handle_replay_controls(f"{CID}-{control}", slider, copy.deepcopy(state), metrics)
                    expected = (old_state, old_disabled, old_interval, *_old_update_replay_ui(old_state, metrics))
                    got = panel._handle_replay_controls_handler(triggered=[_prop(control)], slider_value=slider, current_state=copy.deepcopy(state), metrics_data=metrics)
                    assert got == expected, f"{control} state={state} metrics_len={None if metrics is None else len(metrics)} slider={slider}"
                    cases += 1
        assert cases == len(STATES) * len(METRICS) * len(SLIDER_VALUES)

    @pytest.mark.parametrize("trigger", [[], ["."], [STATE_DATA], [METRICS_DATA], [STATE_DATA, METRICS_DATA]], ids=["mount", "falsy-placeholder", "replay-tick-write", "metrics-refill", "both-refreshes"])
    def test_a_refresh_renders_the_old_ui_and_never_writes_state(self, panel, trigger):
        """No control fired: the state, interval flag and period are ``no_update``."""
        for state in STATES:
            for metrics in METRICS:
                got = panel._handle_replay_controls_handler(triggered=trigger, slider_value=50, current_state=copy.deepcopy(state), metrics_data=metrics)
                assert got[:3] == (dash.no_update, dash.no_update, dash.no_update)
                assert got[3:] == _old_update_replay_ui(state, metrics)

    def test_the_input_state_is_not_mutated(self, panel):
        state = {"mode": "playing", "speed": 1.0, "current_index": 5, "start_index": 0, "end_index": None}
        before = copy.deepcopy(state)
        panel._handle_replay_controls_handler(triggered=[_prop("replay-step-forward")], current_state=state, metrics_data=[{}] * 10)
        assert state == before


@pytest.mark.unit
class TestEachControl:
    """The behaviours the replay matrix rows drive (M-METRICS-11..16 and -18), named."""

    METRICS_50 = [{"epoch": i} for i in range(50)]

    def _run(self, panel, control, state, slider=None, metrics=None):
        return panel._handle_replay_controls_handler(triggered=[_prop(control)], slider_value=slider, current_state=state, metrics_data=self.METRICS_50 if metrics is None else metrics)

    def test_play_toggles_and_arms_the_interval(self, panel):
        state, disabled, interval, *_ = self._run(panel, "replay-play", {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None})
        assert (state["mode"], disabled, interval) == ("playing", False, 1000)
        state, disabled, _interval, *_ = self._run(panel, "replay-play", state)
        assert (state["mode"], disabled) == ("paused", True)

    def test_step_back_pauses_and_clamps_at_zero(self, panel):
        state, *_ = self._run(panel, "replay-step-back", {"mode": "playing", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None})
        assert (state["mode"], state["current_index"]) == ("paused", 9)
        state, *_ = self._run(panel, "replay-step-back", {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None})
        assert state["current_index"] == 0

    def test_step_forward_pauses_and_clamps_at_max(self, panel):
        state, *_ = self._run(panel, "replay-step-forward", {"mode": "playing", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None})
        assert (state["mode"], state["current_index"]) == ("paused", 11)
        state, *_ = self._run(panel, "replay-step-forward", {"mode": "stopped", "speed": 1.0, "current_index": 49, "start_index": 0, "end_index": None})
        assert state["current_index"] == 49

    def test_start_and_end_jump_and_pause(self, panel):
        state, *_ = self._run(panel, "replay-start", {"mode": "playing", "speed": 1.0, "current_index": 25, "start_index": 4, "end_index": None})
        assert (state["mode"], state["current_index"]) == ("paused", 4)
        state, *_ = self._run(panel, "replay-end", {"mode": "playing", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None})
        assert (state["mode"], state["current_index"], state["end_index"]) == ("paused", 49, 49)

    @pytest.mark.parametrize("control, speed, interval", [("speed-1x", 1.0, 1000), ("speed-2x", 2.0, 500), ("speed-4x", 4.0, 250)])
    def test_speed_sets_the_interval_without_touching_mode_or_index(self, panel, control, speed, interval):
        state, disabled, got_interval, *_ = self._run(panel, control, {"mode": "playing", "speed": 1.0, "current_index": 12, "start_index": 0, "end_index": None})
        assert (state["speed"], got_interval, disabled, state["mode"], state["current_index"]) == (speed, interval, False, "playing", 12)

    def test_slider_maps_percent_to_index_and_pauses(self, panel):
        state, disabled, _interval, slider, slider_max, position = self._run(panel, "replay-slider", {"mode": "playing", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None}, slider=50)
        assert (state["current_index"], state["mode"], disabled) == (int((50 / 100) * 49), "paused", True)
        assert (slider, slider_max, position) == (24 / 49 * 100, 100, "24 / 49")

    def test_the_click_renders_in_the_same_response(self, panel):
        """One hop: the slider and position already reflect the click's new index."""
        *_, slider, _max, position = self._run(panel, "replay-step-forward", {"mode": "paused", "speed": 1.0, "current_index": 9, "start_index": 0, "end_index": None})
        assert (slider, position) == (10 / 49 * 100, "10 / 49")


@pytest.mark.unit
class TestProgrammaticWritesAreNotSeeks:
    """The latent defect the lock was hiding (independent Lane B review).

    Pre-merge, a chain that STARTED at ``replay_tick`` or at a store write reached the controls
    callback through ``update_replay_ui``'s slider write with neither callback in the chain's
    ``predecessors``, so the renderer did not prune it -- and the slider branch paused playback
    on every such write. In the merged callback those chains arrive as ``replay-state`` or
    ``metrics-store`` triggers, and neither may change ``mode`` or ``current_index``.
    """

    def test_a_metrics_refill_changes_neither_mode_nor_index(self, panel):
        playing = {"mode": "playing", "speed": 2.0, "current_index": 7, "start_index": 0, "end_index": None}
        state_out, disabled_out, interval_out, slider, _max, position = panel._handle_replay_controls_handler(triggered=[METRICS_DATA], slider_value=11, current_state=copy.deepcopy(playing), metrics_data=[{}] * 66)
        assert (state_out, disabled_out, interval_out) == (dash.no_update,) * 3
        assert (slider, position) == (7 / 65 * 100, "7 / 65")

    def test_a_replay_tick_neither_pauses_nor_moves_the_index(self, panel):
        """Drive the real ``replay_tick`` callback, then the merged callback on its write."""
        callbacks = _registered(panel)
        playing = {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": 49}
        ticked = callbacks["replay_tick"](1, copy.deepcopy(playing), [{}] * 50)
        assert (ticked["mode"], ticked["current_index"]) == ("playing", 8)
        state_out, disabled_out, interval_out, slider, _max, position = panel._handle_replay_controls_handler(triggered=[STATE_DATA], slider_value=7 / 49 * 100, current_state=ticked, metrics_data=[{}] * 50)
        assert (state_out, disabled_out, interval_out) == (dash.no_update,) * 3
        assert (ticked["mode"], ticked["current_index"]) == ("playing", 8)
        assert (slider, position) == (8 / 49 * 100, "8 / 49")

    def test_dispatch_is_exact_not_substring(self, panel):
        """A component id that merely CONTAINS a control's name is not that control."""
        state = {"mode": "stopped", "speed": 1.0, "current_index": 3, "start_index": 0, "end_index": None}
        for bogus in (f"other-{CID}-replay-play.n_clicks", f"{CID}-replay-play-extra.n_clicks", f"{CID}-step-back.n_clicks", "replay-slider.value"):
            got = panel._handle_replay_controls_handler(triggered=[bogus], slider_value=90, current_state=copy.deepcopy(state), metrics_data=[{}] * 10)
            assert got[0] is dash.no_update, bogus


@pytest.mark.unit
class TestMergedRequests:
    """dash-renderer merges queued requests of one callback into ONE request whose
    ``changedPropIds`` keep first-requested order (dash_renderer.dev.js:3004-3007), and the
    server builds ``ctx.triggered`` in that order (dash.py:1492). ``ctx.triggered_id`` is only
    the first entry. A click queued behind a pending refresh must still apply."""

    def test_a_click_queued_behind_a_tick_refresh_applies(self, panel):
        playing = {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None}
        state_out, disabled_out, *_ = panel._handle_replay_controls_handler(triggered=[STATE_DATA, _prop("replay-play")], current_state=copy.deepcopy(playing), metrics_data=[{}] * 50)
        assert (state_out["mode"], disabled_out) == ("paused", True)

    def test_a_click_queued_behind_a_refill_applies(self, panel):
        state = {"mode": "paused", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None}
        state_out, *_ = panel._handle_replay_controls_handler(triggered=[METRICS_DATA, _prop("speed-4x")], current_state=copy.deepcopy(state), metrics_data=[{}] * 50)
        assert (state_out["speed"], state_out["mode"], state_out["current_index"]) == (4.0, "paused", 7)

    def test_several_controls_apply_in_trigger_order(self, panel):
        state = {"mode": "paused", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None}
        state_out, disabled_out, interval_out, *_ = panel._handle_replay_controls_handler(triggered=[_prop("replay-step-forward"), _prop("speed-2x"), _prop("replay-play")], current_state=copy.deepcopy(state), metrics_data=[{}] * 50)
        assert (state_out["current_index"], state_out["speed"], state_out["mode"], disabled_out, interval_out) == (11, 2.0, "playing", False, 500)


# ---------------------------------------------------------------------------------------------
# WIRING
# ---------------------------------------------------------------------------------------------
def _registered(panel):
    callbacks = {}

    class _App:
        def callback(self, *args, **kwargs):
            def decorator(func):
                callbacks[func.__name__] = func
                return func

            return decorator

        def clientside_callback(self, *args, **kwargs):
            return None

    panel.register_callbacks(_App())
    return callbacks


def _split_outputs(output):
    return output[2:-2].split("...") if output.startswith("..") else [output]


def _base(prop):
    component_id, _, prop_name = prop.rpartition(".")
    return f"{component_id}.{prop_name.split('@', 1)[0]}"


def _dep_ids(entry, kind):
    # Dash serialises every dependency id to a string (``component_id_str``); a
    # pattern-matching id arrives as its JSON spelling, e.g. '{"index":["ALL"],"type":"x"}'.
    return [f"{d['id']}.{d['property']}" for d in entry.get(kind, [])]


@pytest.fixture
def panel_app():
    app = Dash(__name__)
    app.layout = html.Div([dcc.Store(id=f"{CID}-metrics-store")])
    MetricsPanel({}, component_id=CID).register_callbacks(app)
    return app


def _merged_entry(app):
    writers = [e for e in app._callback_list if SLIDER_VALUE in [_base(o) for o in _split_outputs(e["output"])]]
    assert len(writers) == 1, f"exactly one callback may write {SLIDER_VALUE}; found {len(writers)}"
    return writers[0]


@pytest.mark.unit
class TestWiring:
    def test_the_slider_writer_also_reads_the_slider(self, panel_app):
        entry = _merged_entry(panel_app)
        assert SLIDER_VALUE in _dep_ids(entry, "inputs")
        assert SLIDER_VALUE in _split_outputs(entry["output"]), "the slider must be a PRIMARY output (an allow_duplicate one keeps its @hash and is not exempt from readiness)"

    def test_refresh_inputs_and_outputs(self, panel_app):
        entry = _merged_entry(panel_app)
        inputs = _dep_ids(entry, "inputs")
        outputs = _split_outputs(entry["output"])
        assert STATE_DATA in inputs and METRICS_DATA in inputs
        for out in (STATE_DATA, f"{CID}-replay-interval.disabled", f"{CID}-replay-interval.interval", SLIDER_VALUE, f"{CID}-replay-slider.max", f"{CID}-replay-position.children"):
            assert out in outputs, out
        assert entry["state"] == [], "everything the merged callback reads is an Input"

    def test_positional_signature_is_the_old_one(self, panel_app):
        """Old Inputs, then the old States in their old order -- so positional callers keep working."""
        expected = [_prop(s) for s in ("replay-play", "replay-step-back", "replay-step-forward", "replay-start", "replay-end", "speed-1x", "speed-2x", "speed-4x", "replay-slider")] + [STATE_DATA, METRICS_DATA]
        assert _dep_ids(_merged_entry(panel_app), "inputs") == expected

    def test_mount_call_is_kept(self, panel_app):
        """PERF-CN-01: the initial slider and "0 / 0" are rendered on mount."""
        assert _merged_entry(panel_app)["prevent_initial_call"] is False

    def test_every_registered_control_input_is_dispatched(self, panel_app, panel):
        """``REPLAY_CONTROL_IDS`` and the registered Inputs must not drift apart."""
        refreshes = {STATE_DATA, METRICS_DATA}
        controls = [p for p in _dep_ids(_merged_entry(panel_app), "inputs") if p not in refreshes]
        assert len(controls) == len(MetricsPanel.REPLAY_CONTROL_IDS)
        for prop_id in controls:
            got = panel._handle_replay_controls_handler(triggered=[prop_id], slider_value=50, current_state=None, metrics_data=[{}] * 10)
            assert got[0] is not dash.no_update, f"{prop_id} is registered but not dispatched"

    def test_update_replay_ui_is_gone_and_the_neighbours_are_unchanged(self, panel):
        callbacks = _registered(panel)
        assert "update_replay_ui" not in callbacks
        for name in ("handle_replay_controls", "replay_tick", "update_play_button", "toggle_replay_visibility"):
            assert name in callbacks, name

    def test_replay_tick_and_play_label_keep_their_shape(self, panel_app):
        entries = {tuple(_split_outputs(e["output"])): e for e in panel_app._callback_list}
        tick = [e for outs, e in entries.items() if any(o.startswith(f"{STATE_DATA}@") for o in outs)]
        assert len(tick) == 1 and _dep_ids(tick[0], "inputs") == [f"{CID}-replay-interval.n_intervals"]
        assert _dep_ids(tick[0], "state") == [STATE_DATA, METRICS_DATA]
        label = entries[(f"{CID}-replay-play.children",)]
        assert _dep_ids(label, "inputs") == [STATE_DATA]

    def test_callback_reads_the_trigger_from_callback_context(self, panel):
        """The registered function hands ``ctx.triggered``'s prop_ids to the handler."""
        from unittest.mock import patch

        func = _registered(panel)["handle_replay_controls"]
        with patch("dash.callback_context") as ctx:
            ctx.triggered = [{"prop_id": _prop("replay-play"), "value": 1}]
            got = func(1, 0, 0, 0, 0, 0, 0, 0, 0, None, [{}] * 10)
        assert (got[0]["mode"], got[1], got[5]) == ("playing", False, "0 / 9")

    def test_callback_outside_a_callback_context_is_the_mount_call(self, panel):
        func = _registered(panel)["handle_replay_controls"]
        got = func(None, None, None, None, None, None, None, None, 0, None, [])
        assert got == (dash.no_update, dash.no_update, dash.no_update, 0, 100, "0 / 0")


# ---------------------------------------------------------------------------------------------
# ACYCLICITY -- on the BUILT app, from the served /_dash-dependencies
# ---------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def dependencies():
    """Exactly what the browser's renderer receives."""
    from frontend.dashboard_manager import DashboardManager

    response = DashboardManager({}).app.server.test_client().get("/_dash-dependencies")
    assert response.status_code == 200
    return json.loads(response.data)


def _callbacks(dependencies):
    out = []
    for i, entry in enumerate(dependencies):
        outputs = [] if entry.get("no_output") else _split_outputs(entry["output"])
        label = entry["output"] if not entry.get("clientside_function") else f"clientside -> {entry['output']}"
        out.append({"i": i, "label": label, "outputs": outputs, "inputs": _dep_ids(entry, "inputs")})
    return out


def _consumers(callbacks):
    by_input = defaultdict(list)
    for cb in callbacks:
        for prop in cb["inputs"]:
            by_input[prop].append(cb["i"])
    return by_input


def _multi_callback_sccs(callbacks):
    """Strongly connected components of size >= 2 of the TRIGGER graph.

    Edge A -> B when an Output of A is an Input of B and A != B. An ``allow_duplicate``
    Output's ``@<hash>`` is stripped: at runtime its response re-triggers the base prop's
    consumers like any other write (the renderer applies CLEAN prop names). A callback's own
    self-edge is excluded -- that is the supported synchronised-component shape.
    """
    by_input = _consumers(callbacks)
    succ = defaultdict(set)
    for cb in callbacks:
        for out in cb["outputs"]:
            for j in by_input.get(_base(out), []):
                if j != cb["i"]:
                    succ[cb["i"]].add(j)
    index, low, on_stack, stack, sccs = {}, {}, set(), [], []
    counter = [0]

    def visit(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on_stack.add(v)
        for w in succ[v]:
            if w not in index:
                visit(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.append(w)
                if w == v:
                    break
            if len(component) > 1:
                sccs.append(component)

    for cb in callbacks:
        if cb["i"] not in index:
            visit(cb["i"])
    return sccs


def _scc_props(callbacks, component):
    """The props every internal edge of an SCC passes through -- its stable identity."""
    members = set(component)
    by_input = _consumers(callbacks)
    return frozenset(_base(out) for i in component for out in callbacks[i]["outputs"] if any(j in members and j != i for j in by_input.get(_base(out), [])))


# Pre-existing multi-callback cycles, found by this test on 886147b5 and deliberately NOT fixed
# here. Each is identified by the props its internal edges pass through; if a cycle gains or
# loses an edge its identity changes and the test fails, and ``test_every_exemption_still_
# matches_a_cycle`` fails when one is fixed, so an exemption cannot outlive its cycle. Neither is
# a readiness deadlock like F-CANOPY-048: each closes through an ``allow_duplicate`` Output,
# whose ``@<hash>`` property matches no Input in ``getAllSubsequentOutputsForCallback``
# (dash_renderer.dev.js:1617), so ``getReadyCallbacks`` never sees the loop.
EXEMPT_CYCLES = {
    # CAN-016a tab persistence (dashboard_manager.py, two clientside callbacks): "restore the
    # persisted active tab" (Input layout-state-store.data -> active_tab, allow_duplicate) and
    # "stamp the layout-state-store" (Input active_tab -> layout-state-store.data,
    # allow_duplicate). Both sides return no_update on equality (the #1 tab-feedback-loop fix).
    "can016a-tab-restore-and-stamp": frozenset({"visualization-tabs.active_tab", "layout-state-store.data"}),
    # CAN-015 HDF5 replay player (replay_player_panel.py): render_session -> scrubber/range/speed
    # .value -> queue_control -> control-trigger.data -> dispatch_control -> replay-player-
    # session.data (allow_duplicate) -> render_session. Unmeasured: render_session's
    # programmatic scrubber/range/speed writes are Inputs of queue_control, so a chain that
    # starts at a session write made elsewhere is not pruned before it reaches queue_control
    # -- the trigger shape F-CANOPY-048's review found latent in the metrics replay block.
    "can015-replay-player-control-loop": frozenset(
        {
            "replay-player-session.data",
            "replay-player-panel-scrubber.value",
            "replay-player-panel-range.value",
            "replay-player-panel-speed.value",
            "replay-player-panel-control-trigger.data",
        }
    ),
}


@pytest.mark.unit
class TestNoMultiCallbackCycles:
    def test_no_cycle_spans_two_or_more_distinct_callbacks(self, dependencies):
        """The dev-tools "Circular Dependencies" check never runs in canopy (dev tools are off,
        and it needs ``validate_callbacks``), so this is the only thing that sees the class."""
        callbacks = _callbacks(dependencies)
        exempt = set(EXEMPT_CYCLES.values())
        offenders = []
        for component in _multi_callback_sccs(callbacks):
            props = _scc_props(callbacks, component)
            if props in exempt:
                continue
            members = sorted(callbacks[i]["label"] for i in component)
            offenders.append(f"{members} via {sorted(props)}")
        assert not offenders, "Input-graph cycles across distinct callbacks (dash-renderer can never promote a member whose own closure covers its Input; merge them into one callback):\n  " + "\n  ".join(offenders)

    def test_every_exemption_still_matches_a_cycle(self, dependencies):
        callbacks = _callbacks(dependencies)
        present = {_scc_props(callbacks, component) for component in _multi_callback_sccs(callbacks)}
        stale = [name for name, props in EXEMPT_CYCLES.items() if props not in present]
        assert not stale, f"exempted cycles that no longer exist -- remove them from EXEMPT_CYCLES: {stale}"

    def test_the_scan_is_complete_for_pattern_matching_ids(self, dependencies):
        """The scan matches a pattern-matching Input only to an Output spelled identically; it
        does not expand ALL / MATCH / ALLSMALLER. That is exact while no callback OUTPUTS a
        pattern-matching id. Today four Inputs listen on one (dynamically rendered buttons
        and the pin checkboxes, written by the user alone) and nothing writes one. The day
        something does, extend ``_multi_callback_sccs`` to wildcard matching first."""
        callbacks = _callbacks(dependencies)
        assert any(p.startswith("{") for cb in callbacks for p in cb["inputs"]), "no pattern-matching Input found -- is the dependency list being read?"
        pattern_outputs = [o for cb in callbacks for o in cb["outputs"] if o.startswith("{")]
        assert not pattern_outputs, f"pattern-matching Outputs now exist; the cycle scan would miss edges through them: {pattern_outputs}"

    def test_the_detector_sees_a_two_callback_cycle(self):
        """Mutation guard for the scan itself: the pre-fix replay shape must be flagged."""
        callbacks = [
            {"i": 0, "label": "controls", "outputs": [STATE_DATA], "inputs": [_prop("replay-play"), SLIDER_VALUE]},
            {"i": 1, "label": "ui", "outputs": [SLIDER_VALUE, f"{CID}-replay-position.children"], "inputs": [STATE_DATA, METRICS_DATA]},
            {"i": 2, "label": "tick", "outputs": [f"{STATE_DATA}@abc123"], "inputs": [f"{CID}-replay-interval.n_intervals"]},
            {"i": 3, "label": "merged", "outputs": [f"{CID}-x.value", f"{CID}-y.data"], "inputs": [f"{CID}-x.value", f"{CID}-y.data"]},
        ]
        assert [sorted(c) for c in _multi_callback_sccs(callbacks)] == [[0, 1]]
        assert _scc_props(callbacks, [0, 1]) == frozenset({STATE_DATA, SLIDER_VALUE})


def _closure(callback, callbacks, by_input):
    """``getAllSubsequentOutputsForCallback`` (dash_renderer.dev.js:1617-1632): Outputs, then the
    Outputs of every callback those trigger, transitively. The ``@<hash>`` is KEPT, as the
    renderer's ``splitIdAndProp`` keeps it, so an allow_duplicate Output is a dead end."""
    touched = set()
    frontier = [callback]
    while frontier:
        outputs = [o for cb in frontier for o in cb["outputs"] if o not in touched]
        touched.update(outputs)
        frontier = [callbacks[j] for o in outputs for j in by_input.get(o, [])]
    return touched


def _checked_inputs(callback):
    """``getReadyCallbacks`` (:1664): the Inputs, less the callback's own Outputs."""
    return [p for p in callback["inputs"] if p not in callback["outputs"]]


def _replay_block(callbacks):
    return [cb for cb in callbacks if any(p.startswith(f"{CID}-replay-") or p.startswith(f"{CID}-speed-") for p in cb["inputs"] + [_base(o) for o in cb["outputs"]])]


@pytest.mark.unit
class TestReplayBlockReadiness:
    def test_no_replay_callback_blocks_itself(self, dependencies):
        """The exact F-CANOPY-048 condition: a checked Input inside the callback's OWN closure.

        Such a callback is never ready by the normal rule while it is itself pending, which it
        is whenever it is requested; only the breaker (:3064) could run it, and that needs
        ``requested.length === pendingCallbacks.length``.
        """
        callbacks = _callbacks(dependencies)
        by_input = _consumers(callbacks)
        block = _replay_block(callbacks)
        assert len(block) >= 4, "replay block not found in the served dependencies"
        blocked = {cb["label"]: sorted(set(_checked_inputs(cb)) & _closure(cb, callbacks, by_input)) for cb in block}
        assert not {k: v for k, v in blocked.items() if v}, f"self-blocked replay callbacks: {blocked}"

    def test_only_a_pending_metrics_store_writer_can_hold_the_controls(self, dependencies):
        """The condition the fix depends on, pinned: whatever else is pending, the only way into
        the merged callback's checked Inputs is ``metrics-store.data`` -- so it is held exactly
        while a PRIMARY writer of that store (or something upstream of one) is pending."""
        callbacks = _callbacks(dependencies)
        by_input = _consumers(callbacks)
        merged = [cb for cb in callbacks if SLIDER_VALUE in cb["outputs"]]
        assert len(merged) == 1
        checked = set(_checked_inputs(merged[0]))
        reaches = set()
        for cb in callbacks:
            reaches |= checked & _closure(cb, callbacks, by_input)
        assert reaches == {METRICS_DATA}
