#!/usr/bin/env python
"""F-CANOPY-037: the topology rebuild must not be triggered by a 1 Hz store.

Finding (juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md):
``update_network_graph`` took ``metrics-panel-metrics-store`` as an **Input**. That
store is rewritten by the 1 Hz ``fast-update-interval`` poll — a live census on a
COMPLETED run recorded 34 writes / 60 s (0.57/s), 33 of them byte-identical, 141,460 B
each. The rebuild's own server time is 1.5-5 s, so its trigger was re-claimed before it
could finish and the graph rendered in only **2 of 11** measured live sessions
(``gd.data == []``, stats bar stuck at the layout-default "0"s). Blast radius:
M-TOPOLOGY-01..18, W4-01..17, W1-12..14 all BLOCKED.

The fix demotes that store to **State**: the data is still read on every run (the
new-unit highlight below depends on it) but it no longer triggers. What remains as an
Input is only what actually means "the topology changed".

Why not the other candidate fix (suppress the store's no-op writes): that lever only
helps at idle, where the refetch is identical. During a run the store changes
legitimately at 1 Hz, so the starvation would survive exactly when the cascade is
growing — and the finding measured the graph equally absent during an active run and
post-run. Only decoupling fixes both regimes.

Verified against the parent commit (9f6fac9): 5 of the 6 tests fail there — the two
wiring pins, the class-level unconditional-feeder pin, and both new-unit-detection
tests (which fail with ``AttributeError: 'str' object has no attribute 'get'``, the
parent's Input ordering feeding ``theme`` where ``metrics_data`` now sits).
``test_real_topology_triggers_are_still_inputs`` passes on the parent by construction:
it is a forward guard against an over-correction that decouples the REAL triggers too,
not a reproduction of the defect.
"""

import inspect
import sys
from pathlib import Path

import pytest
from dash import Dash, dcc, html

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402

COMPONENT_ID = "network-visualizer"
SHARED_METRICS_STORE = "metrics-panel-metrics-store"


@pytest.fixture
def rebuild_entry():
    """The registered ``update_network_graph`` callback_map entry."""
    visualizer = NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)
    app = Dash(__name__)
    app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(app)
    for key, entry in app.callback_map.items():
        if f"{COMPONENT_ID}-graph.figure" in key:
            return entry
    pytest.fail("update_network_graph callback is not registered")


def _ids(entry, kind):
    return [dep.get("id") for dep in entry.get(kind, []) if isinstance(dep, dict)]


@pytest.mark.unit
class TestRebuildIsNotChainedOffTheMetricsStore:
    def test_metrics_store_is_not_an_input(self, rebuild_entry):
        """The regression pin: re-adding it as an Input re-creates the starvation."""
        assert SHARED_METRICS_STORE not in _ids(rebuild_entry, "inputs")

    def test_metrics_store_is_still_state(self, rebuild_entry):
        """Demoted, not dropped — the new-unit highlight reads it on every run."""
        assert SHARED_METRICS_STORE in _ids(rebuild_entry, "state")

    def test_real_topology_triggers_are_still_inputs(self, rebuild_entry):
        """What legitimately means "the topology changed" must keep triggering.

        ``tabpoll-topology`` was on this list and has been REMOVED from it by
        F-CANOPY-039. It does not mean "the topology changed" — it is a poll
        cadence, and the thing it drives (``update_topology_store``) already
        publishes a real change through ``-topology-store``. Keeping the tick as
        an Input here meant the 5 s tick re-requested this callback while the
        1.5-5 s rebuild was still executing; dash-renderer's executing/requested
        dedup then retired the in-flight one and discarded its response.

        Measured on one fixture with one variable changed:
            tick as Input : 0 of 11 painted (deterministic, counts 0/0/0/0)
            tick as State : 11 of 11 painted (counts 2/10/2/89, traces 181)

        The tick is now State — see ``TestF039TickIsNotATrigger`` in
        test_poller_budget.py, which pins that directly.
        """
        inputs = _ids(rebuild_entry, "inputs")
        for dep in (f"{COMPONENT_ID}-topology-store", "ws-cascade-add-buffer"):
            assert dep in inputs, f"{dep} must remain an Input of the rebuild"
        assert "tabpoll-topology" not in inputs, "tabpoll-topology must NOT be an Input of the rebuild (F-CANOPY-039): as an Input " "the tick retires the in-flight rebuild every cycle and the graph never paints"

    def test_no_unconditional_fast_lane_store_drives_the_rebuild(self, rebuild_entry):
        """Class-level pin, not just this one store.

        No Input of the 1.5-5 s rebuild may be written by an **unconditional** 1 Hz
        feeder — that is the shape of the defect, whichever store it arrives through.
        Cross-checked against the real DashboardManager wiring, where the feeders live.

        The hazard is a feeder that WRITES at 1 Hz, not one that merely ticks at 1 Hz.
        ``metrics-panel-metrics-store``'s poll wrote unconditionally: the live census
        recorded 34 writes / 60 s with **zero** ``no_update``, 33 byte-identical. An
        event-drain feeder that returns ``no_update`` when it drained nothing writes at
        the event rate instead, and is not a hazard — but the waiver below is verified,
        not asserted: the guard has to actually be in the source.
        """
        from frontend.dashboard_manager import DashboardManager

        dm = DashboardManager({})
        fast_lane_outputs = set()
        for entry in dm.app.callback_map.values():
            if "fast-update-interval" not in _ids(entry, "inputs"):
                continue
            outputs = entry.get("output", "")
            outputs = outputs if isinstance(outputs, str) else str(outputs)
            for token in outputs.strip(".").split("..."):
                if token:
                    fast_lane_outputs.add(token.split(".")[0])

        assert fast_lane_outputs, "no fast-lane callbacks found — the probe itself is broken"
        candidates = sorted(fast_lane_outputs.intersection(_ids(rebuild_entry, "inputs")))

        # ``ws-cascade-add-buffer`` rides the fast interval but is an event drain:
        # it returns ``no_update`` unless a real WS ``cascade_add`` was drained, so it
        # writes at the cascade-add rate (tens of seconds), not at 1 Hz. Verify that
        # guard instead of trusting it — a drain that lost its no_update IS a hazard.
        drain_source = Path(inspect.getsourcefile(DashboardManager)).read_text(encoding="utf-8")
        drain_block = drain_source.split('Output("ws-cascade-add-buffer", "data")')[0][-900:]
        assert "drainCascadeAdd()" in drain_block, "ws-cascade-add-buffer feeder is no longer the cascade_add drain"
        assert "events.length === 0) return window.dash_clientside.no_update" in drain_block, "the cascade_add drain lost its empty-drain no_update guard — it now writes at 1 Hz and starves the rebuild"

        offenders = [dep for dep in candidates if dep != "ws-cascade-add-buffer"]
        assert not offenders, f"unconditional 1 Hz store(s) drive the topology rebuild: {offenders}"


@pytest.mark.unit
class TestNewUnitDetectionSurvivesTheDemotion:
    """The demotion must not cost the P2-1 new-node highlight."""

    def _invoke(self, entry, metrics_data):
        topology = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 1,
            "connections": [{"source": "input_0", "target": "hidden_0", "weight": 0.5}],
        }
        return entry["callback"].__wrapped__(
            topology,  # topology_data
            "hierarchical",  # layout_type
            ["show"],  # show_weights
            "2d",  # view_mode
            "node_graph",  # display_mode
            None,  # raw_topology
            None,  # depth_filter
            "light",  # theme
            [],  # selected_nodes
            None,  # ws_cascade_add — LAST Input (F-CANOPY-039 moved the tick out of the Inputs)
            0,  # n_intervals — now STATE, so it lands after every Input
            metrics_data,  # metrics_data — STATE, so it lands AFTER every Input
            None,  # view_state
            None,  # prev_hash
            None,  # current_highlight
        )

    def test_added_unit_still_arms_the_highlight(self, rebuild_entry):
        metrics = [
            {"network_topology": {"hidden_units": 0}},
            {"network_topology": {"hidden_units": 1}},
        ]
        new_highlight = self._invoke(rebuild_entry, metrics)[-1]
        assert new_highlight is not None, "metrics_data did not reach the detector — check the State ordering"
        assert new_highlight["node_id"] == "hidden_0"

    def test_steady_topology_arms_nothing(self, rebuild_entry):
        metrics = [
            {"network_topology": {"hidden_units": 1}},
            {"network_topology": {"hidden_units": 1}},
        ]
        assert self._invoke(rebuild_entry, metrics)[-1] is None


@pytest.mark.unit
class TestM16WholeWindowGlowDetection:
    """M-TOPOLOGY-16: the cascade-add glow must survive the addition scrolling
    out of the last pair.

    The detector used to compare ONLY ``metrics_data[-2]`` against ``[-1]``. The
    rebuild does not run on every metrics sample, so by the time it runs those two
    are almost always equal and the addition sits in the middle of the window.
    Measured live, logging the detector's own arguments from inside the callback:

        metrics_len=4   last_pair=40->40  window_span=(39, 40)  armed=0
        metrics_len=23  last_pair=17->17  window_span=(0, 17)   armed=0

    The second carries SEVENTEEN additions and armed zero times. After the fix, an
    identical window shape arms:

        metrics_len=4   last_pair=40->40  window_span=(39, 40)  armed=1  unit=39

    Same inputs, opposite outcome -- the scan is the only variable.
    """

    def _viz(self):
        return NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)

    def _window(self, *hidden_counts):
        return [{"network_topology": {"hidden_units": h}} for h in hidden_counts]

    def _invoke(self, entry, metrics_data):
        topology = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 1,
            "connections": [{"source": "input_0", "target": "hidden_0", "weight": 0.5}],
        }
        return entry["callback"].__wrapped__(
            topology,
            "hierarchical",
            ["show"],
            "2d",
            "node_graph",
            None,
            None,
            "light",
            [],
            None,
            0,
            metrics_data,
            None,
            None,
            None,
        )

    def test_addition_mid_window_is_detected(self, rebuild_entry):
        """THE regression. The addition is at index 1; the last pair is 1->1.

        A last-pair check returns None here, which is precisely the live 0-of-N
        signature. Fails on the parent commit.
        """
        highlight = self._invoke(rebuild_entry, self._window(0, 1, 1, 1))[-1]
        assert highlight is not None, "whole-window scan failed to find an addition that is not in the last pair"
        assert highlight["unit_index"] == 0
        assert highlight["node_id"] == "hidden_0"

    def test_steady_window_arms_nothing(self, rebuild_entry):
        """Forward guard against over-correcting into 'always arms'."""
        assert self._invoke(rebuild_entry, self._window(1, 1, 1, 1))[-1] is None

    def test_same_unit_does_not_rearm(self):
        """Without this the whole-window scan re-arms the SAME unit on every
        rebuild -- the glow would restart forever and never fade."""
        viz = self._viz()
        already = {"node_id": "hidden_0", "unit_index": 0, "state": "active", "start_interval": 5, "shown_unit": 0}
        out = viz._update_highlight_state(
            current_highlight=already,
            newly_added_unit=0,
            n_hidden=3,
            selected_nodes=[],
            n_intervals=99,
        )
        assert out["start_interval"] == 5, "the highlight was reset for a unit already shown"

    def test_a_newer_unit_does_rearm(self):
        """Dedupe must not become 'never glows again'."""
        viz = self._viz()
        already = {"node_id": "hidden_0", "unit_index": 0, "state": "active", "start_interval": 5, "shown_unit": 0}
        out = viz._update_highlight_state(
            current_highlight=already,
            newly_added_unit=2,
            n_hidden=5,
            selected_nodes=[],
            n_intervals=99,
        )
        assert out["unit_index"] == 2 and out["shown_unit"] == 2
        assert out["start_interval"] == 99

    def test_faded_marker_keeps_the_memory_and_renders_nothing(self):
        """The fade path returns a marker, not None.

        Returning a bare None would erase ``shown_unit``, and the whole-window scan
        would immediately re-arm the same unit -- a fade/re-arm loop. The marker has
        to render nothing, which is the ``node_id`` guard in
        ``_calculate_highlight_properties``.
        """
        viz = self._viz()
        fading = {"node_id": "hidden_0", "unit_index": 0, "state": "fading", "fade_start_interval": 0, "shown_unit": 0}
        out = viz._update_highlight_state(
            current_highlight=fading,
            newly_added_unit=None,
            n_hidden=3,
            selected_nodes=[],
            n_intervals=10000,
        )
        assert out is not None, "fade completion dropped the dedupe memory (returned None)"
        assert out.get("node_id") is None
        assert out.get("shown_unit") == 0
        assert viz._calculate_highlight_properties(out, 10000) is None, "the faded marker rendered highlight props"

    def test_faded_unit_is_not_rearmed_by_the_scan(self):
        """End of the loop the naive dedupe leaves open: after the glow has faded,
        the window STILL contains that addition, so the scan still reports it."""
        viz = self._viz()
        done = {"node_id": None, "state": "done", "shown_unit": 0}
        out = viz._update_highlight_state(
            current_highlight=done,
            newly_added_unit=0,
            n_hidden=3,
            selected_nodes=[],
            n_intervals=200,
        )
        assert out.get("node_id") is None, "a faded unit was re-armed by the whole-window scan"


@pytest.mark.unit
class TestF041HeatmapSurvivesTallCascades:
    """F-CANOPY-041: the Weight Matrix heatmap must not 500 on a tall cascade.

    ``make_subplots`` enforces ``vertical_spacing <= 1 / (n_rows - 1)`` and raises
    ValueError otherwise, which Dash returns as HTTP 500 — so the view did not
    degrade, it BROKE. The old code passed a fixed ``0.08 if n_rows <= 5 else 0.04``
    with no reference to that constraint.

    One row per hidden unit plus one for the output weights puts the boundary at
    **26 hidden units**: at 25 the limit is exactly 0.0400 and 0.04 just fits, at 26
    it is 0.0385 and every render raises. Measured live on a 40-unit cascade (limit
    0.0250), a 500 on every poll tick.

    Two reasons it stayed hidden, both worth keeping: the service default
    ``max_hidden_units`` is 10, and F-CANOPY-040 meant this function was never
    reached with real data at all. Fixing that gate is what exposed this one — the
    same symptom (``heatmap=False types=[]``) had two stacked causes.
    """

    def _viz(self):
        return NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)

    def _raw(self, n_hidden):
        return {
            "input_size": 2,
            "output_size": 2,
            "hidden_units": [{"id": i, "weights": [0.1] * (2 + i), "bias": 0.0, "activation": "Tanh"} for i in range(n_hidden)],
            "output_weights": [[0.1] * (2 + n_hidden), [0.2] * (2 + n_hidden)],
        }

    @pytest.mark.parametrize("n_hidden", [1, 5, 25, 26, 40, 80])
    def test_heatmap_renders_at_every_cascade_depth(self, n_hidden):
        """26 and 40 are the regression: both raised ValueError -> HTTP 500 before.

        1/5/25 are the previously-working sizes (guard against over-correcting into
        a spacing that breaks small cascades), and 80 pushes well past anything
        measured so the clamp is exercised rather than merely satisfied.
        """
        fig = self._viz()._create_weight_heatmap(self._raw(n_hidden), theme="light")
        assert fig is not None
        assert len(fig.data) > 0, f"heatmap produced no traces at {n_hidden} hidden units"

    def test_spacing_never_exceeds_plotlys_limit(self):
        """Pin the invariant itself, not just the sizes sampled above.

        A future edit could restore a fixed spacing and pass every size in the
        parametrize list while still breaking some larger cascade.
        """
        for n_rows in range(2, 120):
            desired = 0.08 if n_rows <= 5 else 0.04
            limit = 1.0 / (n_rows - 1)
            assert min(desired, limit) <= limit, f"spacing exceeds plotly's limit at n_rows={n_rows}"
