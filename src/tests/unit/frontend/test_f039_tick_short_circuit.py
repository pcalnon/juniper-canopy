#!/usr/bin/env python
"""F-CANOPY-039: the poll tick must not TRIGGER the topology rebuild at all.

ROOT CAUSE FOUND AND FIXED 2026-08-31. This module's original subject — canopy#537's
bare-tick short-circuit — has been REMOVED, and everything below the next horizontal rule
is retained only as the record of a wrong turn. Read this part first.

The rebuild's response was never applied because **dash-renderer retires the in-flight
invocation whenever the same callback identity is re-requested**:

* ``getUniqueIdentifier`` (``dash_renderer.dev.js:1715``) hashes a pending callback's
  inputs + outputs + state — **not** what triggered it. A rebuild triggered by the
  topology store and one triggered by a bare tick are therefore the SAME identity.
* ``:3026`` computes ``eDuplicates = concat(executing, requested)``, grouped by that
  identity, each group sliced ``[0:-1]``, and passes the result to
  ``removeExecutingCallbacks``. ``requested`` is concatenated LAST, so the newly
  requested invocation survives and the **in-flight** one is dropped.
* Its response then arrives for a callback no longer in ``executing`` and is discarded
  rather than applied.

The rebuild takes 1.5-5 s; ``tabpoll-topology`` ticked every 5 s. As an Input, the tick
retired the populated rebuild on essentially every cycle.

**canopy#537's guard made this worse, not better.** Before it, a bare tick ran a full
rebuild that at least computed a correct figure (the measured "7 responses carrying the
graph"). With the guard, the tick's invocation returned ``no_update`` for all 8 outputs —
so it still displaced the in-flight rebuild and then contributed nothing in its place,
turning an intermittent miss into a deterministic never-paint.

Census, one fixture, one variable changed:

    tick as Input : **0 of 11** painted — identical signatures, counts 0/0/0/0, sig 2
    tick as State : **11 of 11** painted — counts 2/10/2/89, traces 181, sig 30850

The fix is the Input -> State demotion, the same move F-CANOPY-037 applied to
``metrics-panel-metrics-store`` one layer up. The durable rule: **a server-side
``no_update`` does not save a renderer slot and does not prevent the invocation** — the
round trip already happened and the invocation had already displaced its predecessor.
Suppress the TRIGGER, not the work.

WHERE THE OLD TESTS WENT (sequence-safety record). ``TestTheGuardNamesTheLiveLane`` and
its four methods were deleted by canopy#549, because they pinned properties of the guard
that PR removes — and ``State`` can never appear in ``ctx.triggered``, so the guard is
unreachable rather than merely unused. Their coverage is not lost, it is INVERTED:
``TestTheGuardIsGoneAndTheTickIsNotATrigger`` below pins the guard's absence and the tick's
demotion, and ``TestF039TickIsNotATrigger`` in ``test_poller_budget.py`` fails on the
parent with the exact diagnostic. The symbol-loss screen cannot infer that (both the names
and the bodies changed), so the removals are waived by name with ``Allow-Symbol-Loss``
trailers. canopy#549 merged without them and turned ``main`` red; this note and those
trailers are the repair.

---

HISTORICAL, AND WRONG IN ITS CONCLUSION — retained because the reasoning was plausible at
every step. In particular the duplicate-instance root cause asserted below was REFUTED by
direct measurement (exactly one instance of every store id on all three tabs, with three
control ids), and the claim that this module "does NOT fix F-CANOPY-039" was correct about
the guard but wrong about where the defect lived.

F-CANOPY-039: the topology rebuild's poll-tick short-circuit must name the LIVE lane.

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
        # Returns the callback's PRELUDE — everything before the first helper
        # definition. It used to be sliced from the short-circuit block's own
        # marker text, which meant removing that block made the fixture itself
        # error out (F-CANOPY-039: the guard is now gone by design, and a fixture
        # that cannot represent its absence cannot test for it).
        src = inspect.getsource(entry["callback"].__wrapped__)
        end = src.find("_dynamic_graph_config")
        assert end != -1, "could not bound the callback prelude"
        return src[:end]
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
class TestTheGuardIsGoneAndTheTickIsNotATrigger:
    """SUPERSEDES ``TestTheGuardNamesTheLiveLane``, which pinned canopy#537's
    bare-tick short-circuit. That guard has been removed and this class pins the
    replacement invariant, because live measurement refuted the guard's premise.

    The guard assumed a bare tick SHOULD reach this callback and merely needed to
    be cheap. It could not fire in practice (a poll cycle delivered three
    triggers, never one, so ``len(ctx.triggered) == 1`` was never true), and once
    the identical-store-write was suppressed and it COULD fire, it made things
    worse rather than better:

      * dash-renderer identifies a pending callback by inputs+outputs+state, not
        by trigger (``getUniqueIdentifier``, dash_renderer.dev.js:1715);
      * ``:3026`` drops the IN-FLIGHT invocation when the same identity is
        re-requested, so its response arrives orphaned and is discarded;
      * the tick's own invocation then returned ``no_update`` for all 8 outputs,
        contributing nothing in place of what it displaced.

    Net: a deterministic never-paint. 0 of 11 sessions with the tick as an Input,
    11 of 11 once it became State — same fixture, one variable.

    The durable rule: **a server-side ``no_update`` does not save a renderer slot
    and does not prevent the invocation.** Suppress the TRIGGER, not the work.
    """

    def test_the_tick_is_not_an_input_of_the_rebuild(self, rebuild_entry):
        input_ids = [d.get("id") for d in rebuild_entry.get("inputs", []) if isinstance(d, dict)]
        intervals = [i for i in input_ids if isinstance(i, str) and ("interval" in i or i.startswith("tabpoll"))]
        assert not intervals, f"an interval-style Input is back on the topology rebuild: {intervals}. " "It will retire the in-flight rebuild every tick and the graph will stop painting " "(F-CANOPY-039, measured 0 of 11)."

    def test_the_tick_survives_as_state_for_the_pulse(self, rebuild_entry):
        """Removing it entirely would break ``_calculate_highlight_properties``,
        which reads ``n_intervals`` to time the P2-1 pulse."""
        state_ids = [d.get("id") for d in rebuild_entry.get("state", []) if isinstance(d, dict)]
        assert "tabpoll-topology" in state_ids, "tabpoll-topology must remain as STATE so the pulse can still read n_intervals"

    def test_the_dead_short_circuit_is_gone(self, rebuild_source):
        """The guard is unreachable once the tick is State; leaving it in place
        would be dead code that reads as protection."""
        assert "(dash.no_update,) * 8" not in rebuild_source, "canopy#537's bare-tick short-circuit is back; it is unreachable while the tick is State"
        assert "len(ctx.triggered) == 1" not in rebuild_source, "the lone-trigger short-circuit is back; see this class's docstring for why it made the failure deterministic"


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
