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


class TestLever3BoundariesCadence:
    def test_tabpoll_boundaries_rides_the_slow_lane(self, dm):
        intervals = {getattr(c, "id", None): c for c in _walk(dm.app.layout) if type(c).__name__ == "Interval"}
        boundaries = intervals.get("tabpoll-boundaries")
        assert boundaries is not None, "tabpoll-boundaries interval missing from the layout"
        assert boundaries.interval == DashboardConstants.SLOW_UPDATE_INTERVAL_MS, "tabpoll-boundaries must ride the SLOW cadence: at FAST its two feeders' round-trips cover their own period, so the panel's render callback is never promoted after mount (design §12.6 / §13 row 5)"
