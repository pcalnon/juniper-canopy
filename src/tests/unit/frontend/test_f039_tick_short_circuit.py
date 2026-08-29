#!/usr/bin/env python
"""F-CANOPY-039: the topology rebuild's poll-tick short-circuit must name the LIVE lane.

Ledger: juniper-ml notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md

``update_network_graph`` has always carried a guard: a bare poll tick with no highlight
animation running has nothing to redraw, so return ``(no_update,) * 8``. The guard named
``fast-update-interval`` — the trigger **F-CANOPY-027 replaced with
``tabpoll-topology``**. It has therefore been dead code ever since, and every 5 s tick
started a full **1.5-5 s** rebuild whose invocation the *next* tick retired before its
response could land. The renderer discarded a correct **39,319 B** figure ~every time.

Live evidence for the mechanism, all on merged main:

* the callback's whole lifecycle completes — ``Callbacks.AddRequested`` -> ``LOADING``
  -> ``RemoveExecuted`` -> ``LOADED``, carrying the exact ``paths.strs`` itempath —
  while **no dispatched action ever carries the figure**;
* the graph painted in **0 of 5** census sessions, and 0 of 1 on *pre-merge* canopy, so
  it was never a regression from the F-CANOPY-037 fix;
* the component is provably healthy: a hand-written ``figure`` via ``setProps`` renders
  instantly (traces 0 -> 1);
* disabling ``tabpoll-topology`` at runtime made the pending response land immediately —
  traces 0 -> **181**, sig 2 -> **31152**, byte-identical to the signature F-CANOPY-037
  recorded for the two sessions that *did* paint.

**That last observation looked decisive and was NOT.** It motivated a supersession
hypothesis; two fixes built on it — this short-circuit, and a no-op-write suppression on
the topology store — each still failed a live census, and the suppression was reverted.
The actual root cause is upstream of this callback and is recorded in the ledger: over one
71 s window a server-side probe inside the store's WRITER saw the CLIENT's copy of
``network-visualizer-topology-store`` converge to the correct 7,059-byte topology and hold
it for 11 consecutive ticks — while over that same window the rebuild rendered empty, which
it can only do via its own ``input_units == 0`` fast path, i.e. on an EMPTY store. One store
id, two different values, simultaneously: the duplicate-instance signature. **This module
therefore fixes a real dead guard and does NOT fix F-CANOPY-039** — see the PR description.

The class is worth naming because this session hit it three times: **a guard that exists,
reads as correct, and never fires because it names an identifier that moved.** F-CANOPY-038
(a Stage 2 lever present but not biting) and F-CANOPY-018 (keys compared but never written)
are the same shape.

Every test in this module fails on the parent commit (27af847).
"""

import inspect
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402

COMPONENT_ID = "network-visualizer"


@pytest.fixture(scope="module")
def rebuild_source():
    """JUST the tick short-circuit block — not the whole callback source.

    ``inspect.getsource`` on a decorated callback includes its DECORATOR, which
    declares ``Input("tabpoll-topology", "n_intervals")``. Asserting "the source
    mentions the interval id" therefore passes on the broken parent too: the first
    version of this module did exactly that and was vacuous. Slice to the guard.
    """
    visualizer = NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)

    from dash import Dash, dcc, html

    app = Dash(__name__)
    app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(app)
    for key, entry in app.callback_map.items():
        if f"{COMPONENT_ID}-graph.figure" not in key:
            continue
        src = inspect.getsource(entry["callback"].__wrapped__)
        start = src.find("Short-circuit")
        assert start != -1, "the tick short-circuit block is gone entirely"
        end = src.find("_dynamic_graph_config", start)
        assert end != -1, "could not bound the short-circuit block"
        return src[start:end]
    # ``raise`` rather than ``pytest.fail`` so the function has no implicit
    # fall-through return: CodeQL cannot see that pytest.fail is NoReturn and
    # flags the mix as py/mixed-returns, which blocks the merge while the
    # check rollup still reads green.
    raise AssertionError("update_network_graph is not registered")


@pytest.fixture(scope="module")
def rebuild_entry():
    visualizer = NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)

    from dash import Dash, dcc, html

    app = Dash(__name__)
    app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(app)
    for key, entry in app.callback_map.items():
        if f"{COMPONENT_ID}-graph.figure" in key:
            return entry
    raise AssertionError("update_network_graph is not registered")  # see rebuild_source


@pytest.mark.unit
class TestTheGuardNamesTheLiveLane:
    def test_short_circuit_matches_the_actual_interval_input(self, rebuild_source, rebuild_entry):
        """THE regression, and the reason it is written this way.

        Asserting the literal string ``tabpoll-topology`` would pass while the callback
        listened to something else entirely. This derives the interval id from the
        callback's OWN Input list and requires the guard to name it — so renaming the
        lane without updating the guard fails here instead of silently going dead for
        another arc.
        """
        input_ids = [d.get("id") for d in rebuild_entry.get("inputs", []) if isinstance(d, dict)]
        intervals = [i for i in input_ids if isinstance(i, str) and ("interval" in i or i.startswith("tabpoll"))]
        assert intervals, f"the rebuild has no interval-style Input; guard is unanchored (inputs: {input_ids})"
        for interval_id in intervals:
            assert interval_id in rebuild_source, f"the tick short-circuit does not name {interval_id!r}, which IS an Input of this callback — the guard is dead code and every tick will start a full rebuild (F-CANOPY-039)"

    def test_guard_returns_no_update_for_all_eight_outputs(self, rebuild_source):
        """A partial short-circuit would still write some outputs and keep the
        supersession window open."""
        assert "(dash.no_update,) * 8" in rebuild_source, "the tick short-circuit no longer returns no_update for all 8 outputs"

    def test_guard_still_yields_to_an_active_highlight(self, rebuild_source):
        """Forward guard: the P2-1 pulse animates off the tick, so the short-circuit
        must NOT swallow ticks while a highlight is running."""
        assert "not current_highlight" in rebuild_source, "the tick short-circuit no longer defers to an active highlight; the new-node pulse will freeze"

    def test_guard_only_fires_for_a_lone_trigger(self, rebuild_source):
        """A real change arriving in the same dispatch must still rebuild."""
        assert "len(ctx.triggered) == 1" in rebuild_source, "the short-circuit no longer requires a lone trigger; a real topology change batched with a tick would be skipped"


@pytest.mark.unit
class TestTheRebuildStillHasRealTriggers:
    """Forward guard against over-correcting into 'never rebuilds'."""

    def test_real_change_inputs_survive(self, rebuild_entry):
        input_ids = {d.get("id") for d in rebuild_entry.get("inputs", []) if isinstance(d, dict)}
        for dep in (f"{COMPONENT_ID}-topology-store", "ws-cascade-add-buffer"):
            assert dep in input_ids, f"{dep} must remain an Input — with ticks short-circuited it is how a real topology change reaches the graph"

    def test_metrics_store_is_still_state_not_input(self, rebuild_entry):
        """F-CANOPY-037's fix must not be undone by this one."""
        input_ids = {d.get("id") for d in rebuild_entry.get("inputs", []) if isinstance(d, dict)}
        state_ids = {d.get("id") for d in rebuild_entry.get("state", []) if isinstance(d, dict)}
        assert "metrics-panel-metrics-store" not in input_ids
        assert "metrics-panel-metrics-store" in state_ids
