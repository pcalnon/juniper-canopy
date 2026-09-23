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

F-CANOPY-054 (2026-09-23) moved the replay block to the browser. The merged callback is now the
clientside ``REPLAY_CONTROLS_JS`` -- the only writer of ``replay-state``, with the tick folded in
and the metrics store read as State -- and the server ``replay_tick`` and play-label callbacks are
gone. Its semantics, including the differential against the old callbacks, are exercised under
node in ``test_f054_replay_block_clientside.py``. This file keeps the invariants F-CANOPY-048
established that still apply: one slider writer, which reads the slider; no multi-callback cycle
anywhere in the built app; no replay callback blocking itself. The readiness pin moved from "only
a pending metrics-store writer can hold the controls" to "nothing pending can".
"""

import json
from collections import defaultdict

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
# SEMANTICS moved with the callback (F-CANOPY-054). The differential against the pre-merge
# callbacks, the named per-control behaviours and the merged-request order now run on the
# registered JavaScript under node, in ``test_f054_replay_block_clientside.py``, against a
# verbatim copy of the merged server handler this file used to exercise.
# ---------------------------------------------------------------------------------------------


# ---------------------------------------------------------------------------------------------
# WIRING
# ---------------------------------------------------------------------------------------------
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

    def test_mount_call_is_kept(self, panel_app):
        """PERF-CN-01: the initial slider and "0 / 0" are rendered on mount."""
        assert _merged_entry(panel_app)["prevent_initial_call"] is False


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
        # F-CANOPY-054: the container's visibility, the clientside controls, and the clientside
        # refill of the position text. The server ``replay_tick`` and play label are gone.
        assert len(block) == 3, f"replay block not found in the served dependencies: {[cb['label'] for cb in block]}"
        blocked = {cb["label"]: sorted(set(_checked_inputs(cb)) & _closure(cb, callbacks, by_input)) for cb in block}
        assert not {k: v for k, v in blocked.items() if v}, f"self-blocked replay callbacks: {blocked}"

    def test_nothing_pending_can_hold_the_replay_controls(self, dependencies):
        """F-CANOPY-054 tightened the condition canopy#658 depended on. Its merged callback read
        ``metrics-store.data`` as an Input, so it was held while the store's primary writer was
        pending -- most of the time, against a ~5 s delivery latency. The store is State now, so
        no pending callback's downstream closure reaches ANY of the controls' checked Inputs: a
        click or a tick is promoted on the next renderer pass, whatever else is in flight."""
        callbacks = _callbacks(dependencies)
        by_input = _consumers(callbacks)
        merged = [cb for cb in callbacks if SLIDER_VALUE in cb["outputs"]]
        assert len(merged) == 1
        checked = set(_checked_inputs(merged[0]))
        assert f"{CID}-replay-interval.n_intervals" in checked and METRICS_DATA not in checked
        reaches = set()
        for cb in callbacks:
            reaches |= checked & _closure(cb, callbacks, by_input)
        assert reaches == set(), f"a pending callback can hold the replay controls through: {sorted(reaches)}"
