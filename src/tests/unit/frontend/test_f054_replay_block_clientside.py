#!/usr/bin/env python
"""F-CANOPY-054: a late ``replay_tick`` response undid a pause -- the replay block is now clientside.

Finding: juniper-ml ``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md``
(F-CANOPY-054, P2). Clean room: juniper-ml ``util/ad-hoc/2026-09-23_f054_replay_tick_cleanroom.py``.

After F-CANOPY-048 (canopy#658) the replay state had two writers, each a server round trip away:
the merged controls callback, and ``replay_tick`` (an ``allow_duplicate`` writer that computed the
next state from the State read when its request was SENT). With the page's delivery latency at ~5 s
against a 250-1000 ms tick, the tick in flight when the user paused was never evicted -- the pause
had disabled the interval -- and its response, computed from ``playing``, restored ``playing`` with
the interval off. Moving only the tick clientside was not a fix either: the server controls callback
read ``replay-state.data`` as an Input, so every clientside tick re-requested it and dash-renderer
evicted any click still in flight.

The fix: ONE clientside callback (``REPLAY_CONTROLS_JS``) is the only writer of the state. It
handles the eight controls, the slider and the tick, and renders the slider, the position and the
play label from the state it just computed. ``metrics-store.data`` is State, so no pending callback
can hold it. A second clientside callback re-renders the "/ max" half of the position on a refill.

Events come from the Inputs' VALUES, not only from ``ctx.triggered``. A request waiting for one of
the renderer's 12 slots is replaced by the next tick's request of the same callback, and its
trigger is lost (round-1 review: PAUSE-LOST 3/3 under forced saturation). The state keeps each
button's applied click count (``clicks``) and the slider value it last wrote (``slider_w``), so a
lost click or seek is applied at the next run.

What these tests prove:
  * WIRING (everywhere) -- one writer of the state, clientside; no server callback writes the replay
    block; the Inputs, State and Outputs are the ones the design needs; the registered controls,
    ``MetricsPanel.REPLAY_CONTROL_IDS`` and the JavaScript agree.
  * SEMANTICS (under node, on the REGISTERED JavaScript) -- one click of every control returns
    exactly what the merged server callback of canopy#658 returned (verbatim copy below) plus the old
    play label; a tick advances exactly as the old ``replay_tick`` did; and the documented
    differences hold: merged ticks are counted, the end stops the interval, a tick writes nothing
    when not playing, lost clicks and seeks apply at the next run, a NaN slider is not a seek, and
    the refill writes the max alone.
  * THE F-054 SEQUENCE at the logic level -- a tick that arrives after a pause cannot undo it, and a
    pause whose trigger was lost still applies.

What they cannot prove: that the live renderer applies it. That is the verify leg's job
(M-METRICS-13 on a canopy leg serving this branch); the clean room above shows the mechanism.

Falsified against the parent (2f973ca2): the wiring tests fail there, because the controls callback
is server-side, ``replay_tick`` is a second writer and the store is an Input. The node tests fail at
``_controls_entry`` (no clientside writer of the state), except ``TestRefillPosition``, which fails at
``_refill_entry`` (no refill callback).
"""

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dash import Dash, dcc, html

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402

CID = "metrics-panel"
STATE_DATA = f"{CID}-replay-state.data"
METRICS_DATA = f"{CID}-metrics-store.data"
SLIDER_VALUE = f"{CID}-replay-slider.value"
TICK = f"{CID}-replay-interval.n_intervals"
POSITION_INDEX = f"{CID}-replay-position-index.children"
POSITION_MAX = f"{CID}-replay-position-max.children"
PLAY_LABEL = f"{CID}-replay-play.children"

CONTROL_PROPS = {
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
BUTTONS = [c for c in CONTROL_PROPS if c != "replay-slider"]

NODE = shutil.which("node") or shutil.which("nodejs")
NO_UPDATE = "__NO_UPDATE__"
NAN = "__NAN__"  # JSON cannot carry NaN; the driver turns this into one
N_INTERVALS = 17  # an arbitrary interval count for the control cases
ADDED_KEYS = ("tick_n", "clicks", "slider_w")  # keys the clientside state carries beyond the old one


def _prop(suffix):
    return f"{CID}-{suffix}.{CONTROL_PROPS[suffix]}"


# ---------------------------------------------------------------------------------------------
# The ORACLES, verbatim from canopy main 2f973ca2 (src/frontend/components/metrics_panel.py):
# ``_handle_replay_controls_handler`` (:1505-1586, as a module function taking the component id),
# ``replay_tick`` (:1065-1080) and ``update_play_button`` (:1093-1095).
# ---------------------------------------------------------------------------------------------
def _old_controls(component_id, triggered, slider_value, current_state, metrics_data):
    prefix = f"{component_id}-"
    fired = [cid[len(prefix) :] for cid, _, _ in (prop_id.rpartition(".") for prop_id in (triggered or [])) if cid.startswith(prefix) and cid[len(prefix) :] in MetricsPanel.REPLAY_CONTROL_IDS]
    max_index = len(metrics_data) - 1 if metrics_data else 0

    if fired:
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
        state["end_index"] = state.get("end_index") or max_index

        for control in fired:
            if control == "replay-play":
                state["mode"] = "paused" if state["mode"] == "playing" else "playing"
            elif control == "replay-step-back":
                state["mode"] = "paused"
                state["current_index"] = max(0, state["current_index"] - 1)
            elif control == "replay-step-forward":
                state["mode"] = "paused"
                state["current_index"] = min(max_index, state["current_index"] + 1)
            elif control == "replay-start":
                state["current_index"] = state["start_index"]
                state["mode"] = "paused"
            elif control == "replay-end":
                state["current_index"] = state["end_index"] or max_index
                state["mode"] = "paused"
            elif control == "speed-1x":
                state["speed"] = 1.0
            elif control == "speed-2x":
                state["speed"] = 2.0
            elif control == "speed-4x":
                state["speed"] = 4.0
            elif control == "replay-slider":
                state["current_index"] = int((slider_value / 100) * max_index) if max_index > 0 else 0
                state["mode"] = "paused"

        base_interval = 1000
        state_out = state
        disabled_out = state["mode"] != "playing"
        interval_out = int(base_interval / state["speed"])
    else:
        state = current_state
        state_out = disabled_out = interval_out = NO_UPDATE

    current_index = state.get("current_index", 0) if state else 0
    slider_out = (current_index / max_index * 100) if max_index > 0 else 0
    return state_out, disabled_out, interval_out, slider_out, 100, f"{current_index} / {max_index}"


def _old_replay_tick(state, metrics_data):
    if not state or state["mode"] != "playing":
        return state

    max_index = len(metrics_data) - 1 if metrics_data else 0
    end_index = state.get("end_index") or max_index

    new_index = state["current_index"] + 1
    if new_index > end_index:
        state["mode"] = "stopped"
        state["current_index"] = end_index
    else:
        state["current_index"] = new_index

    return state


def _old_play_label(state):
    return "⏸" if state and state.get("mode") == "playing" else "▶"


STATES = [
    None,
    {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None},
    {"mode": "playing", "speed": 2.0, "current_index": 7, "start_index": 0, "end_index": None},
    {"mode": "paused", "speed": 4.0, "current_index": 49, "start_index": 3, "end_index": 20},
    {"mode": "playing", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": 0},
]
METRICS = [None, [], [{"epoch": 0}], [{"epoch": i} for i in range(2)], [{"epoch": i} for i in range(50)]]
SLIDER_VALUES = [0, 33, 50, 100, 42.857142857142854]


# ---------------------------------------------------------------------------------------------
# Registration and the node harness
# ---------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def app():
    dash_app = Dash(__name__)
    dash_app.layout = html.Div([dcc.Store(id=f"{CID}-metrics-store")])
    MetricsPanel({}, component_id=CID).register_callbacks(dash_app)
    return dash_app


def _split_outputs(output):
    return output[2:-2].split("...") if output.startswith("..") else [output]


def _base(prop):
    component_id, _, prop_name = prop.rpartition(".")
    return f"{component_id}.{prop_name.split('@', 1)[0]}"


def _deps(entry, kind):
    return [f"{d['id']}.{d['property']}" for d in entry.get(kind, [])]


def _writers_of(app, prop):
    return [e for e in app._callback_list if prop in [_base(o) for o in _split_outputs(e["output"])]]


def _controls_entry(app):
    primary = [e for e in _writers_of(app, STATE_DATA) if STATE_DATA in _split_outputs(e["output"])]
    assert len(primary) == 1, f"exactly one PRIMARY writer of {STATE_DATA}; found {len(primary)}"
    assert primary[0].get("clientside_function"), "the replay state's writer is served by the server, not clientside"
    return primary[0]


def _refill_entry(app):
    matches = [e for e in app._callback_list if any(o.startswith(f"{POSITION_MAX}@") for o in _split_outputs(e["output"]))]
    assert len(matches) == 1, f"expected one allow_duplicate writer of {POSITION_MAX}; found {len(matches)}"
    return matches[0]


def _js_for(app, entry):
    name = entry["clientside_function"]["function_name"]
    hits = [s for s in app._inline_scripts if name in s]
    assert len(hits) == 1, f"expected one inline script registering {name}, found {len(hits)}"
    return name, hits[0]


def _run_js(app, entry, cases, tmp_path):
    """Run the registered function once per ``(triggered prop_ids, args)`` case, in one node process.

    Returns the return values, with ``no_update`` as NO_UPDATE. Fails if an argument was mutated.
    """
    name, script = _js_for(app, entry)
    payload = tmp_path / "cases.json"
    payload.write_text(json.dumps([{"triggered": t, "args": a} for t, a in cases]), encoding="utf-8")
    driver = tmp_path / "driver.js"
    driver.write_text(
        "globalThis.window = globalThis.window || {};\n"
        "window.dash_clientside = window.dash_clientside || {};\n"
        "const NO_UPDATE = {description: 'no_update'};\n"
        "window.dash_clientside.no_update = NO_UPDATE;\n"
        + script
        + "\n"
        + f'const fn = window.dash_clientside["_dashprivate_clientside_funcs"]["{name}"];\n'
        + "const cases = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
        + "const out = cases.map(function (c) {\n"
        + f"  const args = c.args.map(function (a) {{ return a === '{NAN}' ? NaN : a; }});\n"
        + "  const before = JSON.stringify(args);\n"
        + "  window.dash_clientside.callback_context = {triggered: c.triggered.map(function (p) { return {prop_id: p, value: null}; })};\n"
        + "  const r = fn.apply(null, args);\n"
        + "  delete window.dash_clientside.callback_context;\n"
        + f"  const enc = JSON.parse(JSON.stringify(r, function (k, v) {{ return v === NO_UPDATE ? '{NO_UPDATE}' : v; }}));\n"
        + "  return {out: enc, mutated: JSON.stringify(args) !== before};\n"
        + "});\n"
        + "console.log(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    proc = subprocess.run([NODE, str(driver), str(payload)], capture_output=True, text=True, timeout=120, check=False)  # nosec B603 - fixed interpreter, test-authored script
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    got = json.loads(proc.stdout)
    assert len(got) == len(cases)
    assert not [i for i, g in enumerate(got) if g["mutated"]], "the function mutated an argument (the store's State object)"
    return [g["out"] for g in got]


def _controls_args(slider=0, n=N_INTERVALS, state=None, metrics=None, clicks=None):
    """Positional args in registration order: eight click counts, slider, n_intervals, then state,
    metrics. ``clicks`` maps a button to its current ``n_clicks``; unnamed buttons are at 0."""
    clicks = clicks or {}
    return [clicks.get(b, 0) for b in BUTTONS] + [slider, n, state, metrics]


def _one_click(control):
    """The Inputs of a single click on ``control``: its count at 1, the others at 0."""
    return {control: 1} if control in BUTTONS else {}


def _strip(state):
    if not isinstance(state, dict):
        return state
    return {k: v for k, v in state.items() if k not in ADDED_KEYS}


def _position(out):
    """The "<index> / <max>" text the two position spans render."""
    return f"{out[5]} / {out[6]}"


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed; the wiring and source tests still run")


# ---------------------------------------------------------------------------------------------
# WIRING
# ---------------------------------------------------------------------------------------------
@pytest.mark.unit
class TestWiring:
    def test_one_writer_of_the_replay_state_and_it_is_clientside(self, app):
        """F-054's precondition was a SECOND writer (``replay_tick``, allow_duplicate). None may remain."""
        writers = _writers_of(app, STATE_DATA)
        assert len(writers) == 1, f"{len(writers)} writers of {STATE_DATA}: {[w['output'][:80] for w in writers]}"
        assert writers[0] is _controls_entry(app)

    def test_no_server_callback_writes_the_replay_block(self, app):
        """Only the container's visibility (``toggle_replay_visibility``) stays server-side."""
        allowed = {f"{CID}-replay-controls.style"}
        offenders = [o for e in app._callback_list if not e.get("clientside_function") for o in _split_outputs(e["output"]) if (o.startswith(f"{CID}-replay-") or o.startswith(f"{CID}-speed-")) and _base(o) not in allowed]
        assert not offenders, f"server callbacks still write the replay block: {offenders}"

    def test_inputs_are_the_controls_the_slider_and_the_tick(self, app):
        expected = [_prop(s) for s in CONTROL_PROPS] + [TICK]
        assert _deps(_controls_entry(app), "inputs") == expected

    def test_the_state_and_the_metrics_store_are_state(self, app):
        """The metrics store is STATE: its primary writer is pending most of the time, and
        ``getReadyCallbacks`` holds a callback while any INPUT is downstream of a pending one."""
        entry = _controls_entry(app)
        assert _deps(entry, "state") == [STATE_DATA, METRICS_DATA]
        assert METRICS_DATA not in _deps(entry, "inputs")
        assert STATE_DATA not in _deps(entry, "inputs")

    def test_outputs_are_primary_and_in_order(self, app):
        """The slider must be a PRIMARY output: an allow_duplicate one keeps its @hash and is not
        exempt from the callback's own readiness check."""
        expected = [STATE_DATA, f"{CID}-replay-interval.disabled", f"{CID}-replay-interval.interval", SLIDER_VALUE, f"{CID}-replay-slider.max", POSITION_INDEX, POSITION_MAX, PLAY_LABEL]
        assert _split_outputs(_controls_entry(app)["output"]) == expected

    def test_mount_call_is_kept(self, app):
        """PERF-CN-01: the initial slider, the "0 / 0" position and the "▶" label render on mount."""
        assert _controls_entry(app)["prevent_initial_call"] is False

    def test_the_refill_callback(self, app):
        """It writes the max ALONE, so it can never write a stale index."""
        entry = _refill_entry(app)
        assert entry.get("clientside_function"), "the refill re-render is served by the server"
        assert _deps(entry, "inputs") == [METRICS_DATA]
        assert _deps(entry, "state") == []
        assert entry["prevent_initial_call"] is True
        assert not [e for e in _writers_of(app, POSITION_INDEX) if e is not _controls_entry(app)], "only the controls callback may write the position index"

    def test_the_position_renders_index_slash_max(self):
        """M-METRICS-17 reads "<current> / <max>" off the outer span; it ships "0 / 0"."""
        layout = MetricsPanel({}, component_id=CID).get_layout()
        found = []

        def walk(node):
            if isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)
                return
            if getattr(node, "id", None) == f"{CID}-replay-position":
                found.append(node)
            children = getattr(node, "children", None)
            if children is not None and not isinstance(children, str):
                walk(children)

        walk(layout)
        assert len(found) == 1
        kids = found[0].children
        assert [getattr(k, "id", k) for k in kids] == [f"{CID}-replay-position-index", " / ", f"{CID}-replay-position-max"]
        assert "".join(k if isinstance(k, str) else k.children for k in kids) == "0 / 0"

    def test_registered_controls_match_the_class_constant(self, app):
        controls = [p.rpartition(".")[0][len(CID) + 1 :] for p in _deps(_controls_entry(app), "inputs") if p != TICK]
        assert tuple(controls) == MetricsPanel.REPLAY_CONTROL_IDS

    def test_the_server_callbacks_are_gone(self):
        callbacks = {}

        class _App:
            def callback(self, *args, **kwargs):
                def decorator(func):
                    callbacks[func.__name__] = func
                    return func

                return decorator

            def clientside_callback(self, *args, **kwargs):
                return None

        MetricsPanel({}, component_id=CID).register_callbacks(_App())
        for gone in ("handle_replay_controls", "replay_tick", "update_play_button", "update_replay_ui"):
            assert gone not in callbacks, gone
        assert "toggle_replay_visibility" in callbacks
        assert not hasattr(MetricsPanel, "_handle_replay_controls_handler")


@pytest.mark.unit
class TestSourceBackstop:
    """Runs everywhere, including without node."""

    def test_every_control_is_dispatched_by_name(self, app):
        _, script = _js_for(app, _controls_entry(app))
        for control in MetricsPanel.REPLAY_CONTROL_IDS:
            assert f'ev === "{control}"' in script, f"{control} is registered but the JavaScript never dispatches it"

    def test_the_prefix_and_the_control_list_are_injected(self, app):
        _, script = _js_for(app, _controls_entry(app))
        assert "__PREFIX__" not in script and "__CONTROLS__" not in script
        assert f'var prefix = "{CID}-";' in script
        assert f"var controls = {json.dumps(list(MetricsPanel.REPLAY_CONTROL_IDS))};" in script

    def test_events_are_derived_from_values(self, app):
        """The recovery of a lost trigger rests on these; a regression to trigger-only dispatch fails here."""
        _, script = _js_for(app, _controls_entry(app))
        assert "state.clicks = seen;" in script
        assert "state.slider_w = sliderOut;" in script
        assert "order = lost.concat(order);" in script
        assert "state.tick_n = tickN;" in script


# ---------------------------------------------------------------------------------------------
# SEMANTICS -- the registered JavaScript, under node
# ---------------------------------------------------------------------------------------------
@pytest.mark.unit
@needs_node
class TestControlsMatchTheMergedServerCallback:
    def test_every_control_matches_canopy_658(self, app, tmp_path):
        """Differential over the whole grid: one click of each control. State (less the added keys),
        interval flag and period, slider, max, position -- and the old play label."""
        cases, expected, meta = [], [], []
        for control in CONTROL_PROPS:
            for state in STATES:
                for metrics in METRICS:
                    for slider in SLIDER_VALUES:
                        cases.append(([_prop(control)], _controls_args(slider=slider, state=copy.deepcopy(state), metrics=metrics, clicks=_one_click(control))))
                        old = _old_controls(CID, [_prop(control)], slider, copy.deepcopy(state), metrics)
                        expected.append((*old, _old_play_label(old[0])))
                        meta.append((control, state, None if metrics is None else len(metrics), slider))
        got = _run_js(app, _controls_entry(app), cases, tmp_path)
        for out, exp, (control, state, n_metrics, slider) in zip(got, expected, meta):
            where = f"{control} state={state} metrics_len={n_metrics} slider={slider}"
            assert len(out) == 8, where
            assert _strip(out[0]) == exp[0], where
            assert out[1:5] == list(exp[1:5]), where
            assert _position(out) == exp[5], where
            assert out[7] == exp[6], where
            if control == "replay-play" and exp[0]["mode"] == "playing":
                assert out[0]["tick_n"] == N_INTERVALS, f"play must record the interval count it starts from: {where}"
        assert len(cases) == len(CONTROL_PROPS) * len(STATES) * len(METRICS) * len(SLIDER_VALUES)

    @pytest.mark.parametrize("triggered", [[], ["."], [STATE_DATA], [METRICS_DATA]], ids=["mount", "falsy-placeholder", "not-an-input", "metrics-refill"])
    def test_no_event_renders_and_changes_nothing(self, app, tmp_path, triggered):
        """No control and no tick: the slider, the position and the label render from the state,
        and the mode, index, speed and range are what they were. The state is written only to
        record ``slider_w`` and ``clicks``."""
        cases = [(triggered, _controls_args(state=copy.deepcopy(s), metrics=m)) for s in STATES for m in METRICS]
        got = _run_js(app, _controls_entry(app), cases, tmp_path)
        for out, (_, args) in zip(got, cases):
            state, metrics = args[-2], args[-1]
            old = _old_controls(CID, triggered, 50, copy.deepcopy(state), metrics)
            assert out[1:3] == [NO_UPDATE, NO_UPDATE]
            assert out[3:5] == list(old[3:5])
            assert _position(out) == old[5]
            assert out[7] == _old_play_label(state)
            before = _strip(state) if state else {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None}
            assert _strip(out[0]) == before
            assert out[0]["slider_w"] == out[3]

    def test_dispatch_is_exact_not_substring(self, app, tmp_path):
        bogus = [f"other-{CID}-replay-play.n_clicks", f"{CID}-replay-play-extra.n_clicks", f"{CID}-step-back.n_clicks", "replay-slider.value", f"other-{CID}-replay-interval.n_intervals"]
        state = {"mode": "playing", "speed": 1.0, "current_index": 3, "start_index": 0, "end_index": None, "tick_n": 2}
        got = _run_js(app, _controls_entry(app), [([b], _controls_args(slider=90, n=3, state=copy.deepcopy(state), metrics=[{}] * 10)) for b in bogus], tmp_path)
        for b, out in zip(bogus, got):
            assert (out[0]["mode"], out[0]["current_index"], out[0]["tick_n"]) == ("playing", 3, 2), b
            assert out[1:3] == [NO_UPDATE, NO_UPDATE], b

    def test_several_controls_apply_in_trigger_order(self, app, tmp_path):
        state = {"mode": "paused", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None}
        clicks = {"replay-step-forward": 1, "speed-2x": 1, "replay-play": 1}
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-step-forward"), _prop("speed-2x"), _prop("replay-play")], _controls_args(state=state, metrics=[{}] * 50, clicks=clicks))], tmp_path)
        assert (out[0]["current_index"], out[0]["speed"], out[0]["mode"], out[1], out[2], out[7]) == (11, 2.0, "playing", False, 500, "⏸")


@pytest.mark.unit
@needs_node
class TestEachControl:
    """The behaviours the replay matrix rows drive (M-METRICS-11..16 and -18), named."""

    METRICS_50 = [{"epoch": i} for i in range(50)]

    def _run(self, app, tmp_path, control, state, slider=None):
        (out,) = _run_js(app, _controls_entry(app), [([_prop(control)], _controls_args(slider=slider, state=state, metrics=self.METRICS_50, clicks=_one_click(control)))], tmp_path)
        return out

    def test_play_toggles_and_arms_the_interval(self, app, tmp_path):
        out = self._run(app, tmp_path, "replay-play", {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None})
        assert (out[0]["mode"], out[1], out[2], out[7]) == ("playing", False, 1000, "⏸")
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-play")], _controls_args(state=out[0], metrics=self.METRICS_50, clicks={"replay-play": 2}))], tmp_path)
        assert (out[0]["mode"], out[1], out[7]) == ("paused", True, "▶")

    def test_step_back_pauses_and_clamps_at_zero(self, app, tmp_path):
        out = self._run(app, tmp_path, "replay-step-back", {"mode": "playing", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None})
        assert (out[0]["mode"], out[0]["current_index"]) == ("paused", 9)
        out = self._run(app, tmp_path, "replay-step-back", {"mode": "stopped", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None})
        assert out[0]["current_index"] == 0

    def test_step_forward_pauses_and_clamps_at_max(self, app, tmp_path):
        out = self._run(app, tmp_path, "replay-step-forward", {"mode": "playing", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None})
        assert (out[0]["mode"], out[0]["current_index"]) == ("paused", 11)
        out = self._run(app, tmp_path, "replay-step-forward", {"mode": "stopped", "speed": 1.0, "current_index": 49, "start_index": 0, "end_index": None})
        assert out[0]["current_index"] == 49

    def test_start_and_end_jump_and_pause(self, app, tmp_path):
        out = self._run(app, tmp_path, "replay-start", {"mode": "playing", "speed": 1.0, "current_index": 25, "start_index": 4, "end_index": None})
        assert (out[0]["mode"], out[0]["current_index"]) == ("paused", 4)
        out = self._run(app, tmp_path, "replay-end", {"mode": "playing", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None})
        assert (out[0]["mode"], out[0]["current_index"], out[0]["end_index"]) == ("paused", 49, 49)

    @pytest.mark.parametrize("control, speed, interval", [("speed-1x", 1.0, 1000), ("speed-2x", 2.0, 500), ("speed-4x", 4.0, 250)])
    def test_speed_sets_the_interval_without_touching_mode_or_index(self, app, tmp_path, control, speed, interval):
        out = self._run(app, tmp_path, control, {"mode": "playing", "speed": 1.0, "current_index": 12, "start_index": 0, "end_index": None})
        assert (out[0]["speed"], out[2], out[1], out[0]["mode"], out[0]["current_index"]) == (speed, interval, False, "playing", 12)

    def test_slider_maps_percent_to_index_and_pauses(self, app, tmp_path):
        out = self._run(app, tmp_path, "replay-slider", {"mode": "playing", "speed": 1.0, "current_index": 0, "start_index": 0, "end_index": None}, slider=50)
        assert (out[0]["current_index"], out[0]["mode"], out[1]) == (int((50 / 100) * 49), "paused", True)
        assert (out[3], out[4], _position(out)) == (24 / 49 * 100, 100, "24 / 49")

    def test_the_click_renders_in_the_same_call(self, app, tmp_path):
        """One hop: the slider, the position and the label already reflect the click."""
        out = self._run(app, tmp_path, "replay-step-forward", {"mode": "paused", "speed": 1.0, "current_index": 9, "start_index": 0, "end_index": None})
        assert (out[3], _position(out), out[7]) == (10 / 49 * 100, "10 / 49", "▶")


@pytest.mark.unit
@needs_node
class TestTick:
    METRICS_50 = [{"epoch": i} for i in range(50)]

    def _tick(self, app, tmp_path, state, n, metrics=None, clicks=None, slider=0):
        (out,) = _run_js(app, _controls_entry(app), [([TICK], _controls_args(slider=slider, n=n, state=state, metrics=self.METRICS_50 if metrics is None else metrics, clicks=clicks))], tmp_path)
        return out

    def test_one_tick_advances_like_the_old_replay_tick(self, app, tmp_path):
        cases, expected = [], []
        for state in STATES:
            if not state or state["mode"] != "playing":
                continue
            for metrics in METRICS:
                s = dict(copy.deepcopy(state), tick_n=4)
                cases.append(([TICK], _controls_args(n=5, state=s, metrics=metrics)))
                expected.append((_old_replay_tick(copy.deepcopy(state), metrics), metrics))
        got = _run_js(app, _controls_entry(app), cases, tmp_path)
        assert got, "no playing state in the grid"
        for out, (old_state, metrics) in zip(got, expected):
            assert (out[0]["mode"], out[0]["current_index"], out[0]["tick_n"]) == (old_state["mode"], old_state["current_index"], 5)
            max_index = len(metrics) - 1 if metrics else 0
            idx = old_state["current_index"]
            assert out[3] == ((idx / max_index * 100) if max_index > 0 else 0)
            assert _position(out) == f"{idx} / {max_index}"
            assert out[7] == _old_play_label(old_state)

    def test_merged_ticks_advance_by_the_ticks_consumed(self, app, tmp_path):
        """Two timer firings queued before one renderer pass arrive as ONE request."""
        out = self._tick(app, tmp_path, {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "tick_n": 5}, n=8)
        assert (out[0]["current_index"], out[0]["tick_n"], out[0]["mode"]) == (10, 8, "playing")
        assert out[1] is False and out[2] == NO_UPDATE and out[4] == NO_UPDATE

    def test_a_state_without_tick_n_advances_one(self, app, tmp_path):
        out = self._tick(app, tmp_path, {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None}, n=40)
        assert (out[0]["current_index"], out[0]["tick_n"]) == (8, 40)

    def test_an_already_consumed_tick_writes_nothing(self, app, tmp_path):
        out = self._tick(app, tmp_path, {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "tick_n": 9}, n=9)
        assert out == [NO_UPDATE] * 8

    @pytest.mark.parametrize("state", [None, {"mode": "paused", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None}, {"mode": "stopped", "speed": 1.0, "current_index": 49, "start_index": 0, "end_index": 49}], ids=["none", "paused", "stopped"])
    def test_a_tick_when_not_playing_writes_nothing(self, app, tmp_path, state):
        """The old ``replay_tick`` returned the state unchanged -- a write, and two refreshes."""
        assert self._tick(app, tmp_path, copy.deepcopy(state), n=12) == [NO_UPDATE] * 8

    def test_the_end_stops_playback_and_the_interval(self, app, tmp_path):
        """The old ``replay_tick`` set ``stopped`` and left the interval running."""
        out = self._tick(app, tmp_path, {"mode": "playing", "speed": 1.0, "current_index": 48, "start_index": 0, "end_index": None, "tick_n": 3}, n=6)
        assert (out[0]["mode"], out[0]["current_index"], out[1], _position(out), out[7]) == ("stopped", 49, True, "49 / 49", "▶")

    def test_the_end_index_is_honoured(self, app, tmp_path):
        out = self._tick(app, tmp_path, {"mode": "playing", "speed": 1.0, "current_index": 19, "start_index": 0, "end_index": 20, "tick_n": 1}, n=4)
        assert (out[0]["mode"], out[0]["current_index"], out[1]) == ("stopped", 20, True)

    def test_play_then_the_first_tick_advances_exactly_one(self, app, tmp_path):
        paused = {"mode": "paused", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "tick_n": 2}
        (played,) = _run_js(app, _controls_entry(app), [([_prop("replay-play")], _controls_args(n=30, state=paused, metrics=self.METRICS_50, clicks={"replay-play": 1}))], tmp_path)
        assert (played[0]["mode"], played[0]["tick_n"], played[1]) == ("playing", 30, False)
        out = self._tick(app, tmp_path, played[0], n=31, clicks={"replay-play": 1}, slider=played[3])
        assert out[0]["current_index"] == 8

    def test_a_speed_change_keeps_playing_and_the_tick_count(self, app, tmp_path):
        playing = {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "tick_n": 11}
        (out,) = _run_js(app, _controls_entry(app), [([_prop("speed-4x")], _controls_args(n=11, state=playing, metrics=self.METRICS_50, clicks={"speed-4x": 1}))], tmp_path)
        assert (out[0]["mode"], out[0]["tick_n"], out[0]["speed"], out[1], out[2]) == ("playing", 11, 4.0, False, 250)


@pytest.mark.unit
@needs_node
class TestTheF054Sequence:
    """The race the finding measured, at the logic level: nothing computed before a pause can undo it."""

    PLAYING = {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "tick_n": 3, "clicks": {"replay-play": 1}}

    def test_a_tick_after_the_pause_cannot_undo_it(self, app, tmp_path):
        entry = _controls_entry(app)
        (paused,) = _run_js(app, entry, [([_prop("replay-play")], _controls_args(n=4, state=copy.deepcopy(self.PLAYING), metrics=[{}] * 50, clicks={"replay-play": 2}))], tmp_path)
        assert (paused[0]["mode"], paused[1], paused[7]) == ("paused", True, "▶")
        # The tick in flight at the click: it reads the state as it is NOW, when it executes.
        (late,) = _run_js(app, entry, [([TICK], _controls_args(n=5, state=paused[0], metrics=[{}] * 50, clicks={"replay-play": 2}, slider=paused[3]))], tmp_path)
        assert late == [NO_UPDATE] * 8

    def test_a_tick_merged_before_the_pause_advances_then_pauses(self, app, tmp_path):
        (out,) = _run_js(app, _controls_entry(app), [([TICK, _prop("replay-play")], _controls_args(n=5, state=copy.deepcopy(self.PLAYING), metrics=[{}] * 50, clicks={"replay-play": 2}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"], out[1], out[7]) == ("paused", 9, True, "▶")

    def test_a_tick_merged_after_the_pause_is_ignored(self, app, tmp_path):
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-play"), TICK], _controls_args(n=5, state=copy.deepcopy(self.PLAYING), metrics=[{}] * 50, clicks={"replay-play": 2}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"], out[1]) == ("paused", 7, True)


@pytest.mark.unit
@needs_node
class TestLostTriggers:
    """Round-1 review: a request waiting for a renderer slot is replaced by the next tick's request
    of the same callback, and its trigger is lost. The click count and the slider value survive."""

    METRICS_50 = [{"epoch": i} for i in range(50)]
    PLAYING = {"mode": "playing", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "tick_n": 3, "clicks": {"replay-play": 1}, "slider_w": 7 / 49 * 100}

    def test_a_lost_pause_applies_at_the_next_tick(self, app, tmp_path):
        """The pause's trigger is gone; only the tick triggers. The pause applies FIRST (it predates
        the tick), so the tick finds the replay paused and does not advance."""
        (out,) = _run_js(app, _controls_entry(app), [([TICK], _controls_args(n=5, slider=self.PLAYING["slider_w"], state=copy.deepcopy(self.PLAYING), metrics=self.METRICS_50, clicks={"replay-play": 2}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"], out[1], out[7]) == ("paused", 7, True, "▶")
        assert out[0]["clicks"]["replay-play"] == 2

    def test_an_applied_click_is_not_applied_again(self, app, tmp_path):
        state = dict(copy.deepcopy(self.PLAYING), clicks={"replay-play": 2}, mode="paused")
        (out,) = _run_js(app, _controls_entry(app), [([TICK], _controls_args(n=5, slider=state["slider_w"], state=state, metrics=self.METRICS_50, clicks={"replay-play": 2}))], tmp_path)
        assert out == [NO_UPDATE] * 8

    def test_two_clicks_in_one_request_apply_twice(self, app, tmp_path):
        state = {"mode": "paused", "speed": 1.0, "current_index": 10, "start_index": 0, "end_index": None}
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-step-forward")], _controls_args(state=state, metrics=self.METRICS_50, clicks={"replay-step-forward": 2}))], tmp_path)
        assert out[0]["current_index"] == 12

    def test_repeated_play_clicks_toggle_once(self, app, tmp_path):
        """A lost pause, then the user clicking pause again because nothing showed: two pending
        clicks, ONE toggle. By parity they would cancel and the replay would keep playing."""
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-play")], _controls_args(n=5, slider=self.PLAYING["slider_w"], state=copy.deepcopy(self.PLAYING), metrics=self.METRICS_50, clicks={"replay-play": 3}))], tmp_path)
        assert (out[0]["mode"], out[1]) == ("paused", True)
        assert out[0]["clicks"]["replay-play"] == 3

    def test_a_lost_click_while_paused_applies_behind_another(self, app, tmp_path):
        """Paused, no ticks: the only replacement is another click of this callback."""
        state = {"mode": "paused", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "clicks": {"replay-step-forward": 3, "replay-step-back": 0}}
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-step-back")], _controls_args(state=state, metrics=self.METRICS_50, clicks={"replay-step-forward": 4, "replay-step-back": 1}))], tmp_path)
        assert (out[0]["current_index"], out[0]["clicks"]["replay-step-forward"], out[0]["clicks"]["replay-step-back"]) == (7, 4, 1)

    def test_a_recreated_button_restarts_its_count(self, app, tmp_path):
        state = {"mode": "paused", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "clicks": {"replay-step-forward": 5}}
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-step-forward")], _controls_args(state=state, metrics=self.METRICS_50, clicks={"replay-step-forward": 1}))], tmp_path)
        assert (out[0]["current_index"], out[0]["clicks"]["replay-step-forward"]) == (8, 1)

    def test_a_recreated_buttons_lost_click_applies(self, app, tmp_path):
        """The count restarts below the recorded one AND the trigger is lost. Only the restart
        (a count below the recorded one reads as a new button) shows the click is pending: the
        step forward applies, and the step back that triggered applies behind it."""
        state = {"mode": "paused", "speed": 1.0, "current_index": 7, "start_index": 0, "end_index": None, "clicks": {"replay-step-forward": 5, "replay-step-back": 0}}
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-step-back")], _controls_args(state=state, metrics=self.METRICS_50, clicks={"replay-step-forward": 1, "replay-step-back": 1}))], tmp_path)
        assert (out[0]["current_index"], out[0]["clicks"]["replay-step-forward"], out[0]["clicks"]["replay-step-back"]) == (7, 1, 1)

    def test_a_click_applied_from_its_count_is_not_applied_again(self, app, tmp_path):
        """D1 (Lane B2, round 2). A tick waiting for a slot runs AFTER the click wrote
        ``n_clicks`` and BEFORE the click's own request, so it applies the pause from the count.
        When the click's own request then runs, its trigger must apply nothing: applying it again
        toggles the replay back to playing, F-054's symptom by a new path."""
        entry = _controls_entry(app)
        (first,) = _run_js(app, entry, [([TICK], _controls_args(n=5, slider=self.PLAYING["slider_w"], state=copy.deepcopy(self.PLAYING), metrics=self.METRICS_50, clicks={"replay-play": 2}))], tmp_path)
        assert (first[0]["mode"], first[0]["clicks"]["replay-play"]) == ("paused", 2)
        (second,) = _run_js(app, entry, [([_prop("replay-play")], _controls_args(n=5, slider=first[3], state=first[0], metrics=self.METRICS_50, clicks={"replay-play": 2}))], tmp_path)
        assert second == [NO_UPDATE] * 8

    def test_a_step_applied_from_its_count_moves_once(self, app, tmp_path):
        """D2: the same sequence for a step moved the index two rows for one click."""
        entry = _controls_entry(app)
        playing = dict(copy.deepcopy(self.PLAYING), current_index=20, slider_w=20 / 49 * 100, clicks={"replay-play": 1, "replay-step-forward": 0})
        (first,) = _run_js(app, entry, [([TICK], _controls_args(n=5, slider=playing["slider_w"], state=playing, metrics=self.METRICS_50, clicks={"replay-play": 1, "replay-step-forward": 1}))], tmp_path)
        assert (first[0]["mode"], first[0]["current_index"]) == ("paused", 21)
        (second,) = _run_js(app, entry, [([_prop("replay-step-forward")], _controls_args(n=5, slider=first[3], state=first[0], metrics=self.METRICS_50, clicks={"replay-play": 1, "replay-step-forward": 1}))], tmp_path)
        assert second == [NO_UPDATE] * 8

    def test_the_sliders_own_value_is_not_a_seek_when_it_triggers(self, app, tmp_path):
        """D3: a slider trigger carrying the value this callback last wrote. Read as a seek,
        trunc(v / 100 * max) lands one row low for some rows (row 27 of 49 reads back as 26) and
        pauses the replay."""
        state = dict(copy.deepcopy(self.PLAYING), current_index=27, slider_w=27 / 49 * 100)
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-slider")], _controls_args(n=5, slider=state["slider_w"], state=state, metrics=self.METRICS_50, clicks={"replay-play": 1}))], tmp_path)
        assert out == [NO_UPDATE] * 8

    def test_a_lost_seek_applies(self, app, tmp_path):
        """The slider moved (its value differs from the one last written), but only a tick triggers."""
        (out,) = _run_js(app, _controls_entry(app), [([TICK], _controls_args(n=5, slider=50, state=copy.deepcopy(self.PLAYING), metrics=self.METRICS_50, clicks={"replay-play": 1}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"], out[1]) == ("paused", int(0.5 * 49), True)

    def test_the_written_slider_value_is_not_a_seek(self, app, tmp_path):
        (out,) = _run_js(app, _controls_entry(app), [([TICK], _controls_args(n=5, slider=self.PLAYING["slider_w"], state=copy.deepcopy(self.PLAYING), metrics=self.METRICS_50, clicks={"replay-play": 1}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"]) == ("playing", 9)
        assert out[0]["slider_w"] == out[3] == 9 / 49 * 100

    def test_a_grown_history_is_not_a_seek(self, app, tmp_path):
        """A refill changes the max but never writes the slider, so the slider still holds the value
        last written. The next tick must not read that as a seek."""
        (out,) = _run_js(app, _controls_entry(app), [([TICK], _controls_args(n=5, slider=self.PLAYING["slider_w"], state=copy.deepcopy(self.PLAYING), metrics=[{}] * 80, clicks={"replay-play": 1}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"]) == ("playing", 9)

    def test_a_cleared_slider_box_is_not_a_seek(self, app, tmp_path):
        """dcc.Slider's number box sends NaN when cleared. The state keeps its index and mode, and
        the slider is written back from it."""
        (out,) = _run_js(app, _controls_entry(app), [([_prop("replay-slider")], _controls_args(n=5, slider=NAN, state=copy.deepcopy(self.PLAYING), metrics=self.METRICS_50, clicks={"replay-play": 1}))], tmp_path)
        assert (out[0]["mode"], out[0]["current_index"]) == ("playing", 7)
        assert out[3] == 7 / 49 * 100 and _position(out) == "7 / 49"
        assert out[1:3] == [NO_UPDATE, NO_UPDATE]


@pytest.mark.unit
@needs_node
class TestRefillPosition:
    def test_a_refill_renders_the_max_alone(self, app, tmp_path):
        cases = [([METRICS_DATA], [m]) for m in METRICS]
        got = _run_js(app, _refill_entry(app), cases, tmp_path)
        for out, (_, (metrics,)) in zip(got, cases):
            assert out == str(len(metrics) - 1 if metrics else 0)
