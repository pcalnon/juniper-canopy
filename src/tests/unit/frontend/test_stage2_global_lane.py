#!/usr/bin/env python
"""Stage 2 of the F-CANOPY-027 remediation: global-lane consolidation + no-op-write suppression.

Design of record: juniper-ml notes/JUNIPER_2026-08-23_JUNIPER-CANOPY_CALLBACK-STARVATION-REMEDIATION-DESIGN.md
§13 (per-call-site table). Three levers:

1. consolidate the global lane — the /api/status pair (status bar + training-status
   store) share one fast-lane callback; network info / details / stream health /
   pending banner share one slow-lane callback;
2. suppress no-op store writes — an unchanged write still fires every downstream
   consumer, so the swap-events / metrics / boundary pollers return ``no_update``
   when the fetch equals the store;
3. un-block the Decision Boundary chain — its tabpoll rides the SLOW cadence
   (a ~1 s feeder whose round-trip covers its period permanently blocks the
   panel's render callback: 80 fills vs 1 render / 115 s, run 20260824T080426Z).

Every test here fails on the parent commit (f9defb4).
"""

from unittest.mock import MagicMock, patch

import dash
import pytest
import requests

from canopy_constants import DashboardConstants
from frontend.dashboard_manager import DashboardManager


@pytest.fixture(scope="module")
def dm():
    return DashboardManager({})


def _resp(*, status=200, json_value=None):
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 400
    r.json.return_value = json_value if json_value is not None else {}
    return r


def _walk(component):
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if hasattr(child, "id") or hasattr(child, "children"):
            yield from _walk(child)


def _callback_names(dm):
    names = set()
    for entry in dm.app.callback_map.values():
        cb = entry.get("callback")
        if cb is None:
            continue
        raw = getattr(cb, "__wrapped__", cb)
        n = getattr(raw, "__name__", None)
        if n:
            names.add(n)
    return names


class TestLever1Consolidation:
    def test_merged_callbacks_exist_and_old_pollers_are_gone(self, dm):
        names = _callback_names(dm)
        assert "update_unified_status_bar" in names
        assert "update_system_panels" in names
        for gone in ("update_training_status_store", "update_network_info", "update_network_info_details", "update_stream_health", "reconcile_pending_dataset_banner"):
            assert gone not in names, f"{gone} should have merged into a consolidated callback (design §13 rows 1-2)"
        # F-CANOPY-025: the standalone gate merged into the status-bar feeder —
        # as a separate callback it could never win promotion against the
        # feeder's in-flight claim on training-status-store during a run.
        assert "gate_live_switch_button" not in names, "gate_live_switch_button must stay merged into update_unified_status_bar (F-CANOPY-025)"

    def test_global_lane_shape_is_pinned(self, dm):
        """Exactly 3 fast-lane and 2 slow-lane server-side global riders remain."""
        fast, slow = [], []
        for entry in dm.app.callback_map.values():
            cb = entry.get("callback")
            if cb is None:
                continue
            raw = getattr(cb, "__wrapped__", cb)
            name = getattr(raw, "__name__", None)
            input_ids = {i.get("id") for i in entry.get("inputs", []) if isinstance(i, dict)}
            if "fast-update-interval" in input_ids:
                fast.append(name)
            if "slow-update-interval" in input_ids:
                slow.append(name)
        assert sorted(fast) == sorted(["update_unified_status_bar", "update_metrics_store", "handle_button_timeout_and_acks"]), f"fast lane drifted: {sorted(fast)}"
        assert sorted(slow) == sorted(["update_system_panels", "poll_dataset_swap_events"]), f"slow lane drifted: {sorted(slow)}"


class TestLever2Suppression:
    @patch("requests.get")
    def test_swap_events_identical_fetch_is_no_update(self, mock_get, dm):
        events = [{"timestamp": "t1", "pre_swap_snapshot_id": "a"}]
        mock_get.return_value = _resp(json_value={"data": {"events": events}})
        assert dm._poll_dataset_swap_events_handler(1, current_store={"events": list(events)}) is dash.no_update

    @patch("requests.get")
    def test_swap_events_changed_fetch_still_writes(self, mock_get, dm):
        events = [{"timestamp": "t2", "pre_swap_snapshot_id": "b"}]
        mock_get.return_value = _resp(json_value={"data": {"events": events}})
        assert dm._poll_dataset_swap_events_handler(1, current_store={"events": []}) == {"events": events}

    @patch("requests.get")
    def test_metrics_identical_fetch_is_no_update(self, mock_get, dm):
        history = [{"epoch": 1, "metrics": {"loss": 0.5}}]
        mock_get.return_value = _resp(json_value={"history": list(history)})
        result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100}, current_metrics=list(history), trigger="fast-update-interval.n_intervals", ws_live=False)
        assert result is dash.no_update

    @patch("requests.get")
    def test_metrics_changed_fetch_still_writes(self, mock_get, dm):
        history = [{"epoch": 1, "metrics": {"loss": 0.5}}, {"epoch": 2, "metrics": {"loss": 0.4}}]
        mock_get.return_value = _resp(json_value={"history": list(history)})
        result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100}, current_metrics=history[:1], trigger="fast-update-interval.n_intervals", ws_live=False)
        assert result == history

    @patch("requests.get")
    def test_boundary_identical_fetch_is_no_update(self, mock_get, dm):
        mesh = {"xx": [[0, 1]], "yy": [[0, 1]], "zz": [[0.5, 0.5]]}
        mock_get.return_value = _resp(json_value=dict(mesh))
        assert dm._update_boundary_store_handler(n=1, active_tab="boundaries", resolution=100, current_data=dict(mesh)) is dash.no_update

    @patch("requests.get")
    def test_boundary_changed_fetch_still_writes(self, mock_get, dm):
        mesh = {"xx": [[0, 1, 2]], "yy": [[0, 1, 2]], "zz": [[0.5, 0.5, 0.5]]}
        mock_get.return_value = _resp(json_value=dict(mesh))
        assert dm._update_boundary_store_handler(n=1, active_tab="boundaries", resolution=125, current_data={"xx": [[0, 1]]}) == mesh

    @patch("requests.get")
    def test_boundary_dataset_identical_fetch_is_no_update(self, mock_get, dm):
        ds = {"num_samples": 1000, "inputs": [[0.1, 0.2]], "targets": [0]}
        mock_get.return_value = _resp(json_value=dict(ds))
        assert dm._update_boundary_dataset_store_handler(n=1, active_tab="boundaries", current_data=dict(ds)) is dash.no_update

    def test_boundary_tab_gate_still_holds(self, dm):
        assert dm._update_boundary_store_handler(n=1, active_tab="metrics", resolution=100, current_data=None) is dash.no_update


class TestF039TopologyIdentitySuppression:
    """F-CANOPY-039 — lever 2, applied to the topology store.

    The topology poll rewrote a byte-identical 7,059 B payload every 5 s. Dash
    fires every consumer of a store on any write, identical or not, so that
    rewrite put THREE triggers on ``update_network_graph`` each cycle:

        tabpoll-topology.n_intervals
        network-visualizer-topology-store.data
        network-visualizer-depth-slider.value

    The third is the store's own doing — the slider's clientside bounds-sync
    (``network_visualizer.py:706``) takes the topology store as its ONLY Input
    and re-emits ``value`` unchanged on every write. Measured on the live trio:
    8 invocations of the rebuild, 7 of them carrying the correct topology, and
    the DOM never leaving its mount-time render.

    Two consequences this class pins:

    1. the 1.5-5 s rebuild was superseded before its response could be applied;
    2. canopy#537's ``len(ctx.triggered) == 1`` short-circuit could NEVER fire,
       because a poll cycle is never a bare tick. Suppressing the identical
       write is what leaves a bare tick for that guard to catch — the two are
       only effective together, which is why each measured 0-of-N alone.
    """

    STORE = "network-visualizer-topology-store"

    TOPO = {
        "input_units": 2,
        "hidden_units": 10,
        "output_units": 1,
        "connections": [{"from": "input_0", "to": "hidden_0", "weight": 0.5}],
        "nodes": [{"id": "input_0", "layer": 0}],
    }

    @patch("requests.get")
    def test_identical_fetch_is_no_update(self, mock_get, dm):
        mock_get.return_value = _resp(json_value={"data": dict(self.TOPO)})
        assert dm._update_topology_store_handler(n=1, active_tab="topology", current=dict(self.TOPO)) is dash.no_update

    @patch("requests.get")
    def test_changed_fetch_still_writes(self, mock_get, dm):
        mock_get.return_value = _resp(json_value={"data": dict(self.TOPO)})
        stale = dict(self.TOPO, hidden_units=9)
        assert dm._update_topology_store_handler(n=1, active_tab="topology", current=stale) == self.TOPO

    @patch("requests.get")
    def test_key_reordered_payload_is_still_suppressed(self, mock_get, dm):
        """Canonical (sorted-key) comparison, not ``==`` on insertion order.

        A re-serialised payload whose dict keys come back in a different order
        is the same topology and must not re-trigger the rebuild.
        """
        reordered = {k: self.TOPO[k] for k in reversed(list(self.TOPO))}
        mock_get.return_value = _resp(json_value={"data": reordered})
        assert dm._update_topology_store_handler(n=1, active_tab="topology", current=dict(self.TOPO)) is dash.no_update

    @patch("requests.get")
    def test_mount_with_no_prior_value_still_writes(self, mock_get, dm):
        """``current=None`` means "store empty" — the mount fetch must land.

        This is also the shape every direct unit-test call site uses, so the
        default must never suppress.
        """
        mock_get.return_value = _resp(json_value={"data": dict(self.TOPO)})
        assert dm._update_topology_store_handler(n=1, active_tab="topology") == self.TOPO

    def test_tab_gate_still_holds(self, dm):
        assert dm._update_topology_store_handler(n=1, active_tab="metrics", current=None) is dash.no_update

    @patch("requests.get")
    def test_non_200_leaves_the_store_alone(self, mock_get, dm):
        """The last-known-good posture survives the new guard."""
        mock_get.return_value = _resp(status=503)
        assert dm._update_topology_store_handler(n=1, active_tab="topology", current=dict(self.TOPO)) is dash.no_update

    def test_store_is_declared_as_state_not_input(self, dm):
        """The suppression's operand must be reachable, and must not self-trigger.

        Declaring the callback's own Output as an Input would make it re-fire on
        its own write; dropping the State entirely would silently disable the
        guard (``current`` would be ``None`` forever, which never suppresses) and
        the failure would be invisible to every other test in this file.
        """
        entry = None
        for key, value in dm.app.callback_map.items():
            if key.startswith(f"{self.STORE}.data"):
                entry = value
                break
        assert entry is not None, f"no callback writes {self.STORE}"

        state_ids = {s["id"] for s in entry.get("state", [])}
        input_ids = {i["id"] for i in entry.get("inputs", [])}
        assert self.STORE in state_ids, f"{self.STORE} must ride as State so the handler can compare against it"
        assert self.STORE not in input_ids, f"{self.STORE} must NOT be an Input of its own writer"


@pytest.mark.unit
class TestF043RawTopologyIdentitySuppression:
    """F-CANOPY-043: ``-raw-topology-store`` must not rewrite an unchanged payload.

    This is F-CANOPY-039's starvation mechanism on a second store, and it was
    CREATED by the fix for F-CANOPY-040. Before #557 the raw-topology poll gated on
    the 2D/3D toggle, so its ``!= "weight_matrix"`` comparison was always true and it
    returned ``dash.no_update`` on every tick — dead code that could not starve
    anything. #557 corrected the control, which made the poll a live 5 s writer of a
    store that is an ``Input`` of the topology rebuild.

    Dash fires every consumer of a store on any write, identical or not, and
    dash-renderer's ``getUniqueIdentifier`` (``dash_renderer.dev.js:1715``) hashes a
    callback's inputs/outputs/state and NOT its trigger — so the re-request retires
    the IN-FLIGHT rebuild instead of queueing behind it. Measured paints on this
    fixture are 7.1-31.1 s against a 5 s tick, so an unchanged weight payload is
    enough to keep the heatmap permanently unpainted.

    The suppression and the Weight-Matrix gate are only effective together, exactly
    as ``-topology-store``'s suppression and canopy#537's bare-tick guard were.
    """

    STORE = "network-visualizer-raw-topology-store"

    RAW = {
        "hidden_units": 3,
        "layers": [{"index": 0, "weights": [[0.1, 0.2], [0.3, 0.4]]}],
        "input_units": 2,
    }

    @patch("requests.get")
    def test_identical_fetch_is_no_update(self, mock_get, dm):
        mock_get.return_value = _resp(json_value=dict(self.RAW))
        assert dm._update_raw_topology_store_handler(n=1, active_tab="topology", display_mode="weight_matrix", current=dict(self.RAW)) is dash.no_update

    @patch("requests.get")
    def test_changed_fetch_still_writes(self, mock_get, dm):
        """A real weight change must land — suppression must not freeze the heatmap."""
        mock_get.return_value = _resp(json_value=dict(self.RAW))
        stale = dict(self.RAW, hidden_units=2)
        assert dm._update_raw_topology_store_handler(n=1, active_tab="topology", display_mode="weight_matrix", current=stale) == self.RAW

    @patch("requests.get")
    def test_key_reordered_payload_is_still_suppressed(self, mock_get, dm):
        """Canonical (sorted-key) comparison, not ``==`` on insertion order."""
        reordered = {k: self.RAW[k] for k in reversed(list(self.RAW))}
        mock_get.return_value = _resp(json_value=reordered)
        assert dm._update_raw_topology_store_handler(n=1, active_tab="topology", display_mode="weight_matrix", current=dict(self.RAW)) is dash.no_update

    @patch("requests.get")
    def test_mount_with_no_prior_value_still_writes(self, mock_get, dm):
        """``current=None`` means "store empty" — the mount fetch must land.

        This is also the shape every pre-existing direct call site uses, so the
        default must never suppress.
        """
        mock_get.return_value = _resp(json_value=dict(self.RAW))
        assert dm._update_raw_topology_store_handler(n=1, active_tab="topology", display_mode="weight_matrix") == self.RAW

    def test_the_store_rides_as_state_not_as_its_own_input(self, dm):
        """Threading the store's value in must not make it trigger itself."""
        entry = None
        for key, candidate in dm.app.callback_map.items():
            if key.startswith(f"{self.STORE}.data"):
                entry = candidate
                break
        assert entry is not None, f"no callback writes {self.STORE}"

        state_ids = {s["id"] for s in entry.get("state", [])}
        input_ids = {i["id"] for i in entry.get("inputs", [])}
        assert self.STORE in state_ids, f"{self.STORE} must ride as State so the handler can compare against it"
        assert self.STORE not in input_ids, f"{self.STORE} must NOT be an Input of its own writer"


class TestLever3BoundariesCadence:
    def test_tabpoll_boundaries_rides_the_slow_lane(self, dm):
        intervals = {getattr(c, "id", None): c for c in _walk(dm.app.layout) if type(c).__name__ == "Interval"}
        boundaries = intervals.get("tabpoll-boundaries")
        assert boundaries is not None, "tabpoll-boundaries interval missing from the layout"
        assert boundaries.interval == DashboardConstants.SLOW_UPDATE_INTERVAL_MS, "tabpoll-boundaries must ride the SLOW cadence: at FAST its two feeders' round-trips cover their own period, so the panel's render callback is never promoted after mount (design §12.6 / §13 row 5)"


class TestLever1StoreHiccupNeverBlanks:
    """Stage 2 (design §13 row 1): the LIVE writer of ``training-status-store``
    is ``_update_unified_status_bar_handler`` element [9], not the leftover
    ``_update_training_status_store_handler``. A hiccup must leave the store
    alone — writing ``None`` / ``{is_running: False, phase: idle}`` would
    re-fire ``gate_live_switch_button`` and every other consumer, which is the
    exact F-CANOPY-027 class Stage 2 was written to close.

    Existing error-path tests assert tuple length and the status *label*; they
    do not pin that the store element is ``no_update``.
    """

    STORE = 9

    @patch("requests.get")
    def test_non_200_leaves_the_store_alone(self, mock_get, dm):
        mock_get.return_value = _resp(status=503)
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "output"})
        # 11 Outputs, not 10: Stage-2 appended live-dataset-switch-button.disabled
        # at index 10 (after training-status-store.data at STORE=9), so the store
        # index this class asserts against is unchanged.
        assert len(result) == 11
        assert result[self.STORE] is dash.no_update

    @patch("requests.get")
    def test_rate_limit_leaves_the_store_alone(self, mock_get, dm):
        mock_get.return_value = _resp(status=429)
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "output"})
        assert result[3] == "Rate Limited"
        assert result[self.STORE] is dash.no_update

    @patch("requests.get", side_effect=requests.Timeout("slow"))
    def test_timeout_leaves_the_store_alone(self, _mock_get, dm):
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "output"})
        assert result[3] == "Backend Timeout"
        assert result[self.STORE] is dash.no_update

    @patch("requests.get", side_effect=requests.ConnectionError("down"))
    def test_connection_error_leaves_the_store_alone(self, _mock_get, dm):
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "output"})
        assert result[3] == "Unreachable"
        assert result[self.STORE] is dash.no_update

    @patch("requests.get", side_effect=RuntimeError("boom"))
    def test_generic_exception_leaves_the_store_alone(self, _mock_get, dm):
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "output"})
        assert result[3] == "Error"
        assert result[self.STORE] is dash.no_update


class TestLever1StatusCoercionThenSuppress:
    """``bool(is_running)`` / ``str(phase)`` run BEFORE the equality check, so a
    truthy-int / missing-phase payload must normalize once and then suppress.
    Without the coercion a later ``{True, \"idle\"}`` prev would never match
    ``{1, missing}`` and the store would rewrite every tick.
    """

    STORE = 9

    @patch("requests.get")
    def test_truthy_int_and_missing_phase_normalize(self, mock_get, dm):
        mock_get.return_value = _resp(json_value={"is_running": 1})
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status=None)
        assert result[self.STORE] == {"is_running": True, "phase": "idle"}

    @patch("requests.get")
    def test_normalized_payload_suppresses_against_typed_prev(self, mock_get, dm):
        mock_get.return_value = _resp(json_value={"is_running": 1})
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "idle"})
        assert result[self.STORE] is dash.no_update

    @patch("requests.get")
    def test_real_transition_still_writes(self, mock_get, dm):
        mock_get.return_value = _resp(json_value={"is_running": False, "phase": "idle"})
        result = dm._update_unified_status_bar_handler(n_intervals=1, prev_training_status={"is_running": True, "phase": "output"})
        assert result[self.STORE] == {"is_running": False, "phase": "idle"}


class TestLever1SystemPanelsFailureIsolation:
    """Stage 2 (design §13 row 2): one ``/api/status`` fetch serves network-info
    + the pending banner, but details and stream-health keep their own handlers.
    A status-fetch failure must degrade those two surfaces independently —
    wrapping the whole 4-tuple in one ``try`` would turn a /api/status timeout
    into a blank Network Stats panel and a stale stream-health badge.
    """

    def _run_status_failure(self, dm, mock_get):
        details_sentinel = object()
        health_sentinel = {"stream": "ok"}
        with patch.object(dm, "_update_network_info_details_handler", return_value=details_sentinel) as mock_details, patch.object(dm, "_update_stream_health_handler", return_value=health_sentinel) as mock_health:
            info, details, health, banner = dm._update_system_panels_handler(n=1)
        mock_details.assert_called_once_with(n=1)
        mock_health.assert_called_once_with(1)
        return info, details, health, banner, details_sentinel, health_sentinel

    @staticmethod
    def _info_text(info):
        texts = []
        for child in getattr(info, "children", []) or []:
            texts.append(str(getattr(child, "children", child)))
        return " ".join(texts)

    @patch("requests.get", side_effect=requests.Timeout("slow"))
    def test_timeout_isolates_banner_and_info_from_details_health(self, mock_get, dm):
        info, details, health, banner, details_sentinel, health_sentinel = self._run_status_failure(dm, mock_get)
        assert banner is dash.no_update
        assert "Backend Timeout" in self._info_text(info)
        assert details is details_sentinel
        assert health is health_sentinel

    @patch("requests.get")
    def test_non_200_isolates_banner_and_info_from_details_health(self, mock_get, dm):
        mock_get.return_value = _resp(status=503)
        info, details, health, banner, details_sentinel, health_sentinel = self._run_status_failure(dm, mock_get)
        assert banner is dash.no_update
        assert "Backend Error" in self._info_text(info)
        assert details is details_sentinel
        assert health is health_sentinel

    @patch("requests.get")
    def test_json_decode_failure_isolates_banner_and_info(self, mock_get, dm):
        broken = _resp(status=200, json_value={"pending_dataset": {"nn_dataset_type": "xor"}})
        broken.json.side_effect = ValueError("not json")
        mock_get.return_value = broken
        info, details, health, banner, details_sentinel, health_sentinel = self._run_status_failure(dm, mock_get)
        assert banner is dash.no_update
        assert "ValueError" in self._info_text(info)
        assert details is details_sentinel
        assert health is health_sentinel
