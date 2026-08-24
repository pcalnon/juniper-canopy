"""F-CANOPY-027: the poller gate that keeps canopy under dash-renderer's 12-slot cap.

dash-renderer runs at most **12** callbacks concurrently — a hard-coded literal in the
renderer bundle (``dash_renderer.dev.js:2846``)::

    available = Math.max(0, 12 - executing.length - watched.length);

and it will not promote a queued callback while any of its Inputs is an output claimed by
a still-pending callback. Canopy ran **22 perpetual pollers** against those 12 slots
(~10.8 callback-starts/s against a measured 3.7 completions/s), so the pool sat full
**83.6 %** of the time and the lowest-priority callbacks never got a slot at all: the
Candidate Metrics, Decision Boundary and Dataset View panels held their mount defaults
through entire live runs while the backend advanced.

The load-bearing properties pinned here — each of which FAILS on the parent commit:

1. panel-scoped pollers do not ride the shared ``fast``/``slow`` lanes, because those
   lanes cannot be tab-gated (they carry global consumers such as the status bar);
2. the per-tab lanes are declared ``disabled=True`` so an inactive tab costs zero slots;
3. exactly ONE callback writes each gated interval's ``disabled`` prop (two writers would
   race, and Dash would need ``allow_duplicate``);
4. that single writer still honours the CAN-000 apply-in-flight clamp — the tab gate was
   fused into it rather than competing with it;
5. the dead ``fetch_network_stats`` poller is gone (it wrote a store with no consumer).

Server-side gating is NOT sufficient and is the trap this defect came from: a handler
that returns ``dash.no_update`` because its tab is inactive has already spent the
round-trip and the slot to decide that. The gate must be clientside.

Design of record: ``notes/JUNIPER_2026-08-23_JUNIPER-CANOPY_CALLBACK-STARVATION-REMEDIATION-DESIGN.md``
(juniper-ml). End-to-end behaviour is measured by ``util/ad-hoc/e2e_f027_slots.py`` there.
"""

import sys
from pathlib import Path

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.dashboard_manager import DashboardManager  # noqa: E402

# The registry is imported DEFENSIVELY and only to cross-check it against the
# specification below. Importing it unconditionally would turn a missing-constant
# regression into a collection ImportError, and every behavioural assertion in this
# module would be skipped rather than failed — which is precisely the "test that does
# not actually exercise the defect" trap F-CANOPY-029 was shipped to close.
try:
    from frontend.dashboard_manager import _GATED_POLL_INTERVALS  # noqa: E402
except ImportError:  # pragma: no cover - only on a pre-fix tree
    _GATED_POLL_INTERVALS = None

SHARED_LANES = ("fast-update-interval", "slow-update-interval")

# The SPECIFICATION, stated independently of the source. Every poller interval whose
# ``disabled`` prop the dashboard owns, and the tab that arms it (``None`` = a shared
# lane with global consumers, apply-clamped only per CAN-000).
EXPECTED_GATED_INTERVALS = (
    ("fast-update-interval", None),
    ("slow-update-interval", None),
    ("tabpoll-topology", "topology"),
    ("tabpoll-dataset", "dataset"),
    ("tabpoll-workers", "workers"),
    ("tabpoll-boundaries", "boundaries"),
    ("candidate-metrics-panel-update-interval", "candidates"),
    ("metrics-panel-stats-update-interval", "metrics"),
    ("cassandra-panel-interval", "cassandra"),
    ("redis-panel-refresh-interval", "redis"),
    ("hdf5-snapshots-panel-refresh-interval", "snapshots"),
    ("network-editor-panel-fsm-poll", "network-editor"),
)

# Every poller that is scoped to one panel and therefore must NOT ride a shared lane.
# (output id, the tab it belongs to)
PANEL_SCOPED_POLLERS = (
    ("network-visualizer-topology-store.data", "topology"),
    ("network-visualizer-raw-topology-store.data", "topology"),
    ("dataset-plotter-dataset-store.data", "dataset"),
    ("worker-panel-workers-store.data", "workers"),
    ("decision-boundary-boundary-data.data", "boundaries"),
    ("decision-boundary-dataset-data.data", "boundaries"),
)


@pytest.fixture(scope="module")
def dashboard():
    return DashboardManager({"title": "Test Dashboard", "update_interval": 1000, "server": {"host": "localhost", "port": 8050}})


def _walk(component):
    """Yield every component in a Dash layout tree."""
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
    out = {}
    for comp in _walk(dashboard.app.layout):
        cid = getattr(comp, "id", None)
        if isinstance(cid, str):
            out[cid] = comp
    return out


def _output_specs(entry):
    """Exact ``id.property`` outputs of one ``app._callback_list`` entry.

    EXACT parsing, never substring matching: ``dataset-plotter-dataset-store.data`` is a
    substring of four other callbacks' multi-output keys, and this arc has been misled by
    id substring matching repeatedly. Dash renders a multi-output key as
    ``..a.prop...b.prop..`` and appends ``@<hash>`` to allow_duplicate outputs.
    """
    raw = str(entry["output"])
    if raw.startswith("..") and raw.endswith(".."):
        parts = raw[2:-2].split("...")
    else:
        parts = [raw]
    return {part.split("@", 1)[0] for part in parts}


def _deps_of(entry, key):
    out = set()
    for dep in entry.get(key) or []:
        dep_id = dep["id"] if isinstance(dep, dict) else getattr(dep, "component_id", None)
        prop = dep["property"] if isinstance(dep, dict) else getattr(dep, "component_property", None)
        if isinstance(dep_id, str):
            out.add(f"{dep_id}.{prop}")
    return out


def _entries_writing(dashboard, output):
    return [e for e in dashboard.app._callback_list if output in _output_specs(e)]


def _interval_writer(dashboard, output):
    """The single INTERVAL-DRIVEN writer of ``output``.

    A store may legitimately have several ``allow_duplicate`` writers (buttons, WS drains);
    only the polling one is in scope here.
    """
    candidates = [e for e in _entries_writing(dashboard, output) if any(d.endswith(".n_intervals") for d in _deps_of(e, "inputs"))]
    assert len(candidates) == 1, f"expected exactly 1 interval-driven writer of {output}, found {len(candidates)}"
    return candidates[0]


def _gate_entry(dashboard):
    """The single writer of the shared lanes' ``disabled`` prop."""
    writers = _entries_writing(dashboard, "fast-update-interval.disabled")
    assert len(writers) == 1, f"expected exactly 1 writer of fast-update-interval.disabled, found {len(writers)}"
    return writers[0]


class TestGatedIntervalRegistry:
    def test_registry_ids_all_exist_in_layout(self, dashboard):
        """A typo in the registry would create a callback Output to a component that
        does not exist — Dash would not complain, and the gate would silently not apply."""
        present = _components_by_id(dashboard)
        missing = [iid for iid, _tab in EXPECTED_GATED_INTERVALS if iid not in present]
        assert not missing, f"gated interval ids absent from the layout: {missing}"

    def test_exactly_one_writer_per_disabled_prop(self, dashboard):
        """Two writers of the same ``disabled`` prop would race; Dash would also require
        ``allow_duplicate``. The tab gate is fused into the CAN-000 clamp for this reason."""
        for interval_id, _tab in EXPECTED_GATED_INTERVALS:
            target = f"{interval_id}.disabled"
            writers = _entries_writing(dashboard, target)
            assert len(writers) == 1, f"{target} has {len(writers)} writers"

    def test_shared_lanes_are_not_tab_gated(self):
        """``fast``/``slow`` carry global consumers (status bar, training status, button
        acks). Tab-gating them would silence the whole dashboard on most tabs."""
        for interval_id, tab in EXPECTED_GATED_INTERVALS:
            if interval_id in SHARED_LANES:
                assert tab is None, f"{interval_id} must never be tab-gated, got {tab!r}"


class TestPerTabLanes:
    @pytest.mark.parametrize("interval_id", [i for i, t in EXPECTED_GATED_INTERVALS if i.startswith("tabpoll-")])
    def test_tabpoll_lane_starts_disabled(self, dashboard, interval_id):
        """FAILS ON PARENT: these lanes do not exist there.

        They must start disabled so an inactive tab costs zero slots from first paint;
        the clientside gate arms the active one on mount."""
        present = _components_by_id(dashboard)
        assert interval_id in present, f"{interval_id} is not in the layout at all"
        assert getattr(present[interval_id], "disabled", False) is True, f"{interval_id} must be declared disabled=True"

    @pytest.mark.parametrize("output,tab", PANEL_SCOPED_POLLERS)
    def test_panel_scoped_poller_is_off_the_shared_lanes(self, dashboard, output, tab):
        """FAILS ON PARENT: every one of these rode ``slow-`` or ``fast-update-interval``.

        A shared lane cannot be tab-gated, so a poller on it burns a renderer slot on every
        tick from every tab — which is what starved the three dead panels."""
        inputs = _deps_of(_interval_writer(dashboard, output), "inputs")
        riding = {f"{lane}.n_intervals" for lane in SHARED_LANES} & inputs
        assert not riding, f"{output} still rides a shared lane: {sorted(riding)}"

    @pytest.mark.parametrize("output,tab", PANEL_SCOPED_POLLERS)
    def test_panel_scoped_poller_rides_its_own_tab_lane(self, dashboard, output, tab):
        """FAILS ON PARENT. The lane it rides must be the one gated to its own tab."""
        inputs = _deps_of(_interval_writer(dashboard, output), "inputs")
        lanes = {iid for iid, gate_tab in EXPECTED_GATED_INTERVALS if gate_tab == tab and f"{iid}.n_intervals" in inputs}
        assert lanes, f"{output} rides no interval gated to tab {tab!r}; inputs={sorted(inputs)}"


class TestGateSemantics:
    def test_gate_reads_both_the_apply_clamp_and_the_active_tab(self, dashboard):
        """FAILS ON PARENT: the callback there reads only ``apply-in-flight``.

        CAN-000 must survive the change — the clamp still silences every poller while the
        Apply Parameters roundtrip is in flight — so both signals feed one writer."""
        gate = _gate_entry(dashboard)
        inputs = _deps_of(gate, "inputs")
        assert "apply-in-flight.data" in inputs, "CAN-000 apply clamp was dropped"
        assert "visualization-tabs.active_tab" in inputs, "tab gate is not wired"

    def test_gate_writes_every_registered_interval(self, dashboard):
        """One writer, and it must cover the whole registry — a lane left out of the gate
        would poll forever."""
        gate = _gate_entry(dashboard)
        written = _output_specs(gate)
        for interval_id, _tab in EXPECTED_GATED_INTERVALS:
            assert f"{interval_id}.disabled" in written, f"{interval_id} is not written by the gate"

    def test_gate_is_clientside(self, dashboard):
        """A server-side gate would consume one of the 12 slots it exists to conserve."""
        gate = _gate_entry(dashboard)
        assert gate.get("clientside_function") is not None, "the poll gate must be clientside"


class TestDeadPollerRemoved:
    def test_network_stats_store_has_no_writer(self, dashboard):
        """FAILS ON PARENT: ``fetch_network_stats`` polled /api/network/stats every 5 s and
        wrote this store, which has no Input or State consumer anywhere in src/."""
        writers = _entries_writing(dashboard, "metrics-panel-network-stats-store.data")
        assert not writers, f"dead network-stats poller is back: {len(writers)} writer(s)"

    def test_network_stats_store_still_has_no_consumer(self, dashboard):
        """If someone later wires a consumer, the poller must come back with it — this
        test is the tripwire that says so."""
        target = "metrics-panel-network-stats-store"
        for entry in dashboard.app._callback_list:
            deps = _deps_of(entry, "inputs") | _deps_of(entry, "state")
            offenders = {d for d in deps if d.split(".", 1)[0] == target}
            assert not offenders, f"{_output_specs(entry)} consumes {target}; restore its writer"


class TestRegistryMatchesSpecification:
    def test_source_registry_matches_the_spec(self):
        """The module constant and this file's specification must agree.

        Kept as its OWN test so that a drifted (or missing) registry fails here loudly
        rather than silently weakening every other assertion in this module.
        """
        assert _GATED_POLL_INTERVALS is not None, "frontend.dashboard_manager._GATED_POLL_INTERVALS is missing"
        assert tuple(_GATED_POLL_INTERVALS) == EXPECTED_GATED_INTERVALS
