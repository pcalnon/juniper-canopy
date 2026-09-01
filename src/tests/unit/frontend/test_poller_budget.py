"""F-CANOPY-027 Stage 3: the poller budget guard.

dash-renderer runs at most **12** callbacks concurrently — a hard-coded literal in the
renderer bundle (``dash_renderer.dev.js:2846``, dash 4.2.0)::

    available = Math.max(0, 12 - executing.length - watched.length);

Exceed that steadily and the renderer stops promoting queued callbacks; the lowest-priority
ones — terminal render callbacks, which is what every stat tile and figure is — then starve
indefinitely. That is F-CANOPY-027: three panels held their mount defaults through entire
live runs while their stores filled on the wire.

Stage 1 fixed the instance. THIS FILE is what stops it coming back: without a budget check,
the next panel added to the dashboard silently re-creates the defect, and the symptom looks
like broken wiring rather than overload (it cost this arc twenty refuted mechanisms before
the real cause was found).

Two rules:

1. **Budget** — the worst-case number of perpetual server-side pollers that can be in flight
   on any single tab must stay within the renderer's pool.
2. **Shape** — a poller that is scoped to one panel must not ride a SHARED interval lane.
   Shared lanes cannot be tab-gated (they carry global consumers such as the status bar), so
   a panel-scoped poller on one burns a slot on every tick from every tab. This is the exact
   shape that produced F-CANOPY-027.

The census reads the BUILT app (``app._callback_list``), not the source, so it sees all
registered callbacks including pattern-matching and dynamically-registered ones.

Design of record: ``notes/JUNIPER_2026-08-23_JUNIPER-CANOPY_CALLBACK-STARVATION-REMEDIATION-DESIGN.md``
(juniper-ml).
"""

import collections
import re
import sys
from pathlib import Path

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.dashboard_manager import _GATED_POLL_INTERVALS, DashboardManager  # noqa: E402

# dash_renderer.dev.js:2846 — hard-coded, not configurable, not raisable.
RENDERER_SLOT_CAP = 12

# Worst-case concurrent perpetual pollers allowed on any one tab.
#
# Pinned AT the renderer cap rather than below it: the measured value when this guard was
# written was 12, and the remaining headroom depends on Stage 2 (panel work chained off
# global stores, which interval gating cannot silence). Lower this as Stage 2 lands; never
# raise it without re-measuring saturation with juniper-ml's util/ad-hoc/e2e_f027_slots.py.
POLLER_BUDGET = RENDERER_SLOT_CAP

SHARED_LANES = ("fast-update-interval", "slow-update-interval")


@pytest.fixture(scope="module")
def dashboard():
    return DashboardManager({})


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "children") or hasattr(child, "id"):
            yield from _walk(child)


def _components_by_id(dashboard):
    return {getattr(c, "id", None): c for c in _walk(dashboard.app.layout) if isinstance(getattr(c, "id", None), str)}


def _deps(entry, key):
    out = set()
    for dep in entry.get(key) or []:
        if isinstance(dep, dict) and isinstance(dep.get("id"), str):
            out.add(f"{dep['id']}.{dep['property']}")
    return out


def _perpetual_pollers(dashboard):
    """(interval_id, gate_tab, output) for every perpetual SERVER-side interval poller.

    Excluded, with reasons:
      * clientside callbacks — they never occupy a renderer slot;
      * one-shot intervals (``max_intervals`` set) — they fire at mount and stop, so they
        cost nothing at steady state;
      * MODE-gated intervals — declared ``disabled=True`` and absent from
        ``_GATED_POLL_INTERVALS``, i.e. armed by something other than the tab gate. The
        replay tick is the live example: it ships disabled and runs only while a replay
        session is scrubbing, so counting it as always-on would overstate the steady state.
        Note this is NOT a blanket "ignore disabled intervals" rule — the ``tabpoll-*`` lanes
        also ship ``disabled=True`` but ARE in the registry, so they count against their tab.
    """
    comps = _components_by_id(dashboard)
    gate = dict(_GATED_POLL_INTERVALS)
    rows = []
    for entry in dashboard.app._callback_list:
        if entry.get("clientside_function"):
            continue
        for dep in _deps(entry, "inputs"):
            if not dep.endswith(".n_intervals"):
                continue
            interval_id = dep.split(".")[0]
            comp = comps.get(interval_id)
            if getattr(comp, "max_intervals", None) not in (None, -1):
                continue
            if interval_id not in gate and getattr(comp, "disabled", False) is True:
                continue
            rows.append((interval_id, gate.get(interval_id, "UNGATED"), str(entry["output"])))
    return rows


def _worst_case_concurrent(rows):
    by_gate = collections.Counter(gate_tab for _iv, gate_tab, _out in rows)
    global_n = sum(n for k, n in by_gate.items() if k in (None, "UNGATED"))
    per_tab = {k: n for k, n in by_gate.items() if k not in (None, "UNGATED")}
    worst_tab, worst_n = max(per_tab.items(), key=lambda kv: kv[1], default=("-", 0))
    return global_n, worst_tab, worst_n, global_n + worst_n


class TestPollerBudget:
    def test_worst_case_concurrent_pollers_within_budget(self, dashboard):
        """The whole point of the fix, guarded.

        If this fails, a new poller was added on an ungated lane. The fix is almost never to
        raise POLLER_BUDGET — it is to gate the new poller to its tab (add it to
        ``_GATED_POLL_INTERVALS``) or to fold it into an existing poll.
        """
        rows = _perpetual_pollers(dashboard)
        global_n, worst_tab, worst_n, total = _worst_case_concurrent(rows)
        assert total <= POLLER_BUDGET, f"worst-case {total} concurrent perpetual pollers " f"({global_n} global + {worst_n} on the '{worst_tab}' tab) " f"exceeds the budget of {POLLER_BUDGET} (renderer cap {RENDERER_SLOT_CAP}). " f"Gate the new poller to its tab instead of raising the budget."

    def test_budget_never_exceeds_the_renderer_cap(self):
        """The budget is meaningless above the cap the renderer actually enforces."""
        assert POLLER_BUDGET <= RENDERER_SLOT_CAP


class TestPollerShape:
    def test_no_panel_scoped_poller_rides_a_shared_lane(self, dashboard):
        """The exact shape that produced F-CANOPY-027.

        A callback that references ``visualization-tabs.active_tab`` is panel-scoped by
        construction. Riding a shared lane means it cannot be silenced off-tab, so it spends
        a renderer slot on every tick from every tab merely to return ``dash.no_update``.
        """
        offenders = []
        for entry in dashboard.app._callback_list:
            if entry.get("clientside_function"):
                continue
            inputs = _deps(entry, "inputs")
            all_deps = inputs | _deps(entry, "state")
            rides_shared = any(f"{lane}.n_intervals" in inputs for lane in SHARED_LANES)
            is_panel_scoped = "visualization-tabs.active_tab" in all_deps
            if rides_shared and is_panel_scoped:
                offenders.append(str(entry["output"])[:90])
        assert not offenders, "panel-scoped pollers on an ungateable shared lane:\n  " + "\n  ".join(offenders)

    def test_every_gated_interval_is_actually_used(self, dashboard):
        """A registry entry for an interval no callback reads is dead config that will
        quietly rot — and worse, it makes the budget look better than it is."""
        used = {interval_id for interval_id, _gate, _out in _perpetual_pollers(dashboard)}
        # Shared lanes and the replay interval are legitimately absent from the perpetual
        # census at times (replay ships disabled=True and only runs during a replay).
        exempt = set(SHARED_LANES)
        unused = [iid for iid, _tab in _GATED_POLL_INTERVALS if iid not in used and iid not in exempt]
        assert not unused, f"gated intervals no perpetual poller reads: {unused}"


class TestF039TickIsNotATrigger:
    """F-CANOPY-039: ``tabpoll-topology`` must ride the topology rebuild as STATE.

    dash-renderer identifies a pending callback by ``getUniqueIdentifier``
    (``dash_renderer.dev.js:1715``) = its inputs + outputs + state, and NOT by
    what triggered it. So a rebuild triggered by the topology store and one
    triggered by a bare interval tick are the SAME identity. At ``:3026`` the
    renderer computes

        eDuplicates = concat(executing, requested), grouped by identity,
                      each group sliced [0:-1]

    and hands those to ``removeExecutingCallbacks``. Because ``requested`` is
    concatenated last, the newly-requested invocation survives and the IN-FLIGHT
    one is dropped — its response then arrives for a callback no longer in
    ``executing`` and is discarded rather than applied.

    The topology rebuild takes 1.5-5 s and the tab poll ticks every 5 s, so as an
    Input the tick retired the populated rebuild on essentially every cycle and
    the graph never painted. Measured on one fixture, one variable changed:

        tabpoll as Input : 0 of 11 painted (deterministic, counts 0/0/0/0)
        tabpoll as State : 11 of 11 painted (counts 2/10/2/89, traces 181)

    State keeps ``n_intervals`` readable for the P2-1 pulse timing while removing
    the trigger — the same Input -> State demotion F-CANOPY-037 applied to
    ``metrics-panel-metrics-store`` one layer up.

    Promoting it back to an Input would silently restore the defect, and every
    other test in this repo would still pass.
    """

    REBUILD_OUTPUT = "network-visualizer-graph.figure"
    TICK = "tabpoll-topology.n_intervals"

    def _rebuild_entry(self, dashboard):
        for entry in dashboard.app._callback_list:
            if entry.get("clientside_function"):
                continue
            if self.REBUILD_OUTPUT in str(entry.get("output") or ""):
                return entry
        return None

    def test_topology_rebuild_exists(self, dashboard):
        assert self._rebuild_entry(dashboard) is not None, f"no server callback outputs {self.REBUILD_OUTPUT}"

    def test_tabpoll_is_state_not_input_on_the_rebuild(self, dashboard):
        entry = self._rebuild_entry(dashboard)
        assert entry is not None
        inputs = _deps(entry, "inputs")
        state = _deps(entry, "state")

        assert self.TICK not in inputs, f"{self.TICK} is an INPUT of the topology rebuild. dash-renderer will retire the " "in-flight rebuild every tick and discard its response (F-CANOPY-039, 0 of 11 painted)."
        assert self.TICK in state, f"{self.TICK} must remain as STATE so the P2-1 pulse can still read n_intervals; " "dropping it entirely would break _calculate_highlight_properties."


@pytest.mark.unit
class TestF040RawTopologyGateIsWiredToTheRightControl:
    """F-CANOPY-040: the raw-topology poll must read the DISPLAY mode, not the 2D/3D toggle.

    The handler gates on ``display_mode != "weight_matrix"``. ``weight_matrix`` is a
    value of ``network-visualizer-display-mode`` (Node Graph / Weight Matrix). The
    callback used to pass ``network-visualizer-view-mode``, whose only values are
    ``"2d"`` and ``"3d"`` — so the comparison was ALWAYS true, the poll returned
    ``dash.no_update`` on every tick, the raw-topology store was never populated, and
    the Weight Matrix heatmap could never render. Measured live: ``/api/topology/raw``
    served a full 40-unit weight payload while the heatmap drew zero traces.

    WHY NO EXISTING TEST CAUGHT IT, which is the point of this class. Every handler
    test calls ``_update_raw_topology_store_handler(..., display_mode="weight_matrix")``
    DIRECTLY. The handler was always correct; only the wiring was wrong, and nothing
    asserted the wiring. Unit coverage of a correct function cannot see a caller that
    never supplies the value — so this pins the CALLBACK's dependency, not the handler.
    """

    STORE = "network-visualizer-raw-topology-store"
    DISPLAY_MODE = "network-visualizer-display-mode"
    VIEW_MODE = "network-visualizer-view-mode"

    def _entry(self, dashboard):
        for key, entry in dashboard.app.callback_map.items():
            if key.startswith(f"{self.STORE}.data"):
                return entry
        return None

    def test_the_raw_topology_poll_exists(self, dashboard):
        assert self._entry(dashboard) is not None, f"no callback writes {self.STORE}"

    def test_it_reads_display_mode_and_not_the_2d_3d_toggle(self, dashboard):
        entry = self._entry(dashboard)
        assert entry is not None
        dep_ids = {d["id"] for d in (entry.get("state") or []) + (entry.get("inputs") or []) if isinstance(d, dict)}

        assert self.DISPLAY_MODE in dep_ids, f"{self.STORE}'s poll does not read {self.DISPLAY_MODE}. Its gate compares against " '"weight_matrix", which only that control ever holds — so the heatmap gets no data.'
        assert self.VIEW_MODE not in dep_ids, f"{self.STORE}'s poll reads {self.VIEW_MODE} (the 2D/3D toggle, values '2d'/'3d'). " 'Its gate compares against "weight_matrix", so the comparison is always true and the ' "raw-topology store is never populated (F-CANOPY-040)."

    def test_the_gate_value_is_reachable_from_the_control_it_reads(self, dashboard):
        """Class-level pin, not just these two ids.

        Whatever control the poll gates on must actually be able to hold the value the
        gate tests for. This is the invariant the original bug violated, and it would
        catch the same mistake against a third control.
        """
        import inspect

        from frontend.dashboard_manager import DashboardManager

        handler_src = inspect.getsource(DashboardManager._update_raw_topology_store_handler)
        gate_values = set(re.findall(r'!=\s*"([a-z_]+)"', handler_src))
        gate_values.discard("topology")  # the active_tab half of the gate
        assert gate_values, "could not read the gate's expected value out of the handler"

        entry = self._entry(dashboard)
        dep_ids = {d["id"] for d in (entry.get("state") or []) + (entry.get("inputs") or []) if isinstance(d, dict)}
        components = _components_by_id(dashboard)
        reachable = set()
        for dep in dep_ids:
            comp = components.get(dep)
            for opt in getattr(comp, "options", None) or []:
                if isinstance(opt, dict) and "value" in opt:
                    reachable.add(str(opt["value"]))

        missing = gate_values - reachable
        assert not missing, f"the raw-topology gate tests for {sorted(missing)}, which none of the controls it reads " f"({sorted(dep_ids)}) can ever hold — the gate can never pass (F-CANOPY-040 class)"
