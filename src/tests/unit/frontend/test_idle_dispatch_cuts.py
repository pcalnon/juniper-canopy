#!/usr/bin/env python
"""A timer that cost the idle page a third of its response latency, a dead one, and a guard for the class.

Evidence: juniper-ml ``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md`` (Phase 8,
"cheap cuts"); A/B instrument ``util/ad-hoc/2026-09-23_canopy_timer_park_ab.py``, static census
``util/ad-hoc/2026-09-23_canopy_interval_census.py``.

At idle the dashboard's main thread is ~0.1% idle, and response-delivery latency is 5-15 s. Every
``dcc.Interval`` tick is a store update that re-runs the page's selectors, and a consumed tick adds
a callback lifecycle. Two timers were half of the page's steady-state ticks:

  * ``metrics-panel-update-interval`` (1 Hz). No callback took it as an Input, in the built app or,
    as far as the history shows, ever. REMOVED.
  * ``replay-player-panel-weight-drain`` (2 Hz), on no tab gate. Its clientside callback drains the
    replay-weight ring buffer, which could fill only while a CAN-015 replay session streams weights,
    and which nothing fills today: cascor's replay frames carry no weights and canopy's metrics relay
    drops the key (F-CANOPY-057). GATED: it ships disabled and runs only once this page has started
    a replay; against cascor, a Stop does not close it again (F-CANOPY-056).

In a live idle page, the A/B above parked each timer and compared each window with its two
neighbouring baselines, over two runs in opposite orders. Parking the DRAIN cut the median
response-delivery latency by 42% and 32%, and parking both by 32% and 33%. Parking the dead timer
alone was not measurable (-1.6% in the clean run). Removing it is hygiene; the drain is the cost.

What these tests prove:
  * CLASS -- every ``dcc.Interval`` in the BUILT layout has at least one consumer: a callback that
    takes its ``n_intervals`` as an Input. A timer with none ticks forever for nothing.
  * WIRING -- the drain ships disabled; exactly one callback writes its ``disabled``, clientside,
    from ``replay-player-session.data``; the metrics panel has no ``-update-interval``.
  * READINESS PREMISE -- every writer of ``replay-player-session.data`` is an ``allow_duplicate``
    Output, so no pending callback's closure reaches the gate's Input and nothing can hold it.
  * RULE -- the gate, run under node: disabled unless the session holds a truthy ``snapshot_id``.

What they cannot prove: the latency effect. That is the A/B's job, on a live leg.

Falsified against the parent: 7 of the 9 fail. CLASS fails on ``metrics-panel-update-interval``,
and the drain tests fail because there is no gate and the drain ships enabled. The two premise
pins, "the drain is not in the tab gate" and "no primary writer of the session", hold on both, by
design.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dash import Dash, html

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components import replay_player_panel  # noqa: E402

DRAIN = "replay-player-panel-weight-drain"
SESSION = "replay-player-session.data"
NODE = shutil.which("node") or shutil.which("nodejs")


def _gate_js():
    """The gate's source. Looked up per test, so a module without it fails only the gate tests
    (and the CLASS test still runs on its own merits)."""
    js = getattr(replay_player_panel, "WEIGHT_DRAIN_GATE_JS", None)
    assert js, "replay_player_panel has no WEIGHT_DRAIN_GATE_JS -- the weight drain is not gated"
    return js


@pytest.fixture(scope="module")
def built():
    """The whole app: its served dependency list and its layout."""
    from frontend.dashboard_manager import DashboardManager

    app = DashboardManager({}).app
    deps = json.loads(app.server.test_client().get("/_dash-dependencies").data)
    layout = app.layout() if callable(app.layout) else app.layout
    return deps, layout


def _split_outputs(output):
    return output[2:-2].split("...") if output.startswith("..") else [output]


def _intervals(node, out):
    """Every dcc.Interval in a layout tree, by walking ``to_plotly_json``."""
    if isinstance(node, (list, tuple)):
        for child in node:
            _intervals(child, out)
        return out
    if node is None or not hasattr(node, "to_plotly_json"):
        return out
    j = node.to_plotly_json()
    props = j.get("props", {})
    if j.get("type") == "Interval" and j.get("namespace") == "dash_core_components":
        out.append(props)
    for value in props.values():
        if hasattr(value, "to_plotly_json") or isinstance(value, (list, tuple)):
            _intervals(value, out)
    return out


def _consumers(deps, component_id):
    return [e for e in deps if any(i["id"] == component_id and i["property"] == "n_intervals" for i in e.get("inputs", []))]


def _writers(deps, prop):
    return [(e, out) for e in deps if not e.get("no_output") for out in _split_outputs(e["output"]) if out.split("@", 1)[0] == prop]


@pytest.mark.unit
class TestEveryIntervalHasAConsumer:
    def test_every_interval_has_a_consumer(self, built):
        deps, layout = built
        intervals = _intervals(layout, [])
        assert len(intervals) >= 10, f"found only {len(intervals)} Intervals -- is the layout being walked?"
        # ``_consumers`` matches a layout id against the served dependency ids, where Dash
        # stores a pattern-matching id as a JSON string with wildcards. It cannot match a
        # dict id, so such an Interval would be reported dead when it is not: refuse it.
        pattern = [p["id"] for p in intervals if not isinstance(p["id"], str)]
        assert not pattern, f"pattern-matching Interval ids are not supported by this check; extend _consumers before adding one: {pattern}"
        dead = sorted(p["id"] for p in intervals if not _consumers(deps, p["id"]))
        assert not dead, f"Intervals with no consumer tick forever for nothing (each tick is a store update that re-runs the page's selectors): {dead}"

    def test_the_metrics_panel_has_no_update_interval(self, built):
        _deps, layout = built
        ids = {p["id"] for p in _intervals(layout, [])}
        assert "metrics-panel-update-interval" not in ids
        assert "metrics-panel-stats-update-interval" in ids, "the walk lost the metrics panel"


@pytest.mark.unit
class TestWeightDrainGate:
    def test_the_drain_ships_disabled(self, built):
        _deps, layout = built
        drain = [p for p in _intervals(layout, []) if p["id"] == DRAIN]
        assert len(drain) == 1
        assert drain[0].get("disabled") is True, "the weight drain must ship disabled; the gate enables it while a replay session exists"
        assert drain[0].get("interval") == 500

    def test_one_writer_of_disabled_and_it_is_the_clientside_gate(self, built):
        deps, _layout = built
        writers = _writers(deps, f"{DRAIN}.disabled")
        assert len(writers) == 1, f"{len(writers)} writers of {DRAIN}.disabled -- the gate must be the only one"
        entry, _out = writers[0]
        assert entry.get("clientside_function"), "the gate is served by the server"
        assert [f"{i['id']}.{i['property']}" for i in entry["inputs"]] == [SESSION]
        assert entry.get("state", []) == []
        assert entry["prevent_initial_call"] is False

    def test_the_drain_is_not_in_the_tab_gate(self):
        """Two writers of one ``disabled`` would fight; the tab gate owns the ones it lists."""
        from frontend.dashboard_manager import _GATED_POLL_INTERVALS

        assert DRAIN not in {interval_id for interval_id, _tab in _GATED_POLL_INTERVALS}

    def test_no_pending_callback_can_hold_the_gate(self, built):
        """Every writer of the session is ``allow_duplicate``: its ``@hash`` closure reaches no Input."""
        deps, _layout = built
        writers = _writers(deps, SESSION)
        assert writers, "no writer of the replay session found"
        primary = [out for _e, out in writers if "@" not in out]
        assert not primary, f"a PRIMARY writer of {SESSION} would put the gate's Input inside its closure: {primary}"

    def test_the_gate_is_the_registered_function(self):
        """The constant the node test runs is the one registered."""
        registered = []

        class _App:
            def callback(self, *args, **kwargs):
                return lambda func: func

            def clientside_callback(self, js, *args, **kwargs):
                registered.append(js)

        replay_player_panel.ReplayPlayerPanel({}).register_callbacks(_App())
        assert _gate_js() in registered


@pytest.mark.unit
@pytest.mark.skipif(NODE is None, reason="node is not installed; the wiring tests above still run")
class TestWeightDrainGateRule:
    CASES = [
        (None, True),
        ({}, True),
        ({"snapshot_id": None}, True),
        ({"snapshot_id": ""}, True),
        ({"snapshot_id": None, "playing": True}, True),
        ({"snapshot_id": "snap_1", "playing": False}, False),
        ({"snapshot_id": "snap_1", "playing": True, "speed": 2.0}, False),
    ]

    def test_disabled_unless_a_session_exists(self, tmp_path):
        driver = tmp_path / "gate.js"
        driver.write_text(
            "const fn = (" + _gate_js() + ");\n" "const cases = JSON.parse(process.argv[2]);\n" "console.log(JSON.stringify(cases.map(function (c) { return fn(c); })));\n",
            encoding="utf-8",
        )
        proc = subprocess.run([NODE, str(driver), json.dumps([c for c, _ in self.CASES])], capture_output=True, text=True, timeout=60, check=False)  # nosec B603 - fixed interpreter, test-authored script
        assert proc.returncode == 0, proc.stderr
        got = json.loads(proc.stdout)
        assert got == [want for _, want in self.CASES]


@pytest.mark.unit
def test_register_callbacks_still_builds_on_a_bare_app():
    """The panel registers into a fresh Dash app with the gate among its clientside callbacks."""
    app = Dash(__name__)
    app.layout = html.Div()
    replay_player_panel.ReplayPlayerPanel({}).register_callbacks(app)
    assert any(f"{DRAIN}.disabled" in str(entry.get("output", "")) for entry in app._callback_list)
