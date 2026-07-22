#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_worker_panel.py
# Author:        Paul Calnon
# Version:       1.1.0
# Date:          2026-03-31
# Last Modified: 2026-07-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for WorkerPanel component and worker API endpoints
#####################################################################
"""Unit tests for the store-driven WorkerPanel and /api/v1/workers/* endpoints.

CAN-HIGH-005 (aggregate stats + roster) and N10 / U-5 (local/remote kind column,
tab-gated worker store, honest "local not individually reported" note).
"""

import sys
from pathlib import Path

import dash_bootstrap_components as dbc
import pytest
from dash import dcc, html

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

from frontend.components.worker_panel import WorkerPanel  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    """Basic config for worker panel."""
    return {}


@pytest.fixture
def worker_panel(config):
    """Create WorkerPanel instance with default config."""
    return WorkerPanel(config, component_id="test-worker")


def _worker(**overrides):
    """A canonical worker record (roster shape), overridable per test."""
    base = {
        "worker_id": "worker-001",
        "kind": "remote",
        "capabilities": {"cpu_cores": 8, "gpu": False, "python": "3.13"},
        "connected_at": 1711900000,
        "last_heartbeat": 1711900100,
        "tasks_completed": 10,
        "tasks_failed": 0,
        "active_task_id": None,
        "health_score": 1.0,
        "idle": True,
    }
    base.update(overrides)
    return base


def _store(workers=None, stats=None, local_reported=False, error=None):
    """A worker-store payload as filled by _update_workers_store_handler."""
    workers = workers if workers is not None else []
    payload = {"workers": workers, "count": len(workers), "local_reported": local_reported, "error": error, "stats": stats or {}}
    return payload


# ---------------------------------------------------------------------------
# TestWorkerPanelInitialization
# ---------------------------------------------------------------------------


class TestWorkerPanelInitialization:
    """Test WorkerPanel initialization."""

    @pytest.mark.unit
    def test_init_with_default_config(self):
        """Should initialize with empty config and the default component id."""
        panel = WorkerPanel({})
        assert panel is not None
        assert panel.component_id == "worker-panel"

    @pytest.mark.unit
    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        panel = WorkerPanel(config, component_id="my-workers")
        assert panel.component_id == "my-workers"

    @pytest.mark.unit
    def test_init_ignores_legacy_interval_config(self):
        """Legacy interval_ms/api_timeout config is inert (panel is store-driven now)."""
        panel = WorkerPanel({"interval_ms": 15000, "api_timeout": 10}, component_id="legacy")
        # No self-owned interval anymore; the config keys are simply ignored.
        assert not hasattr(panel, "interval_ms")
        assert panel.component_id == "legacy"


# ---------------------------------------------------------------------------
# TestWorkerPanelInheritance
# ---------------------------------------------------------------------------


class TestWorkerPanelInheritance:
    """Test BaseComponent inheritance."""

    @pytest.mark.unit
    def test_inherits_from_base_component(self, worker_panel):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(worker_panel, BaseComponent)

    @pytest.mark.unit
    def test_has_logger(self, worker_panel):
        """Should have logger from BaseComponent."""
        assert hasattr(worker_panel, "logger")
        assert worker_panel.logger is not None

    @pytest.mark.unit
    def test_has_config(self, worker_panel):
        """Should have config from BaseComponent."""
        assert hasattr(worker_panel, "config")

    @pytest.mark.unit
    def test_has_component_id(self, worker_panel):
        """Should have component_id from BaseComponent."""
        assert hasattr(worker_panel, "component_id")
        assert worker_panel.component_id == "test-worker"


# ---------------------------------------------------------------------------
# TestWorkerPanelLayout
# ---------------------------------------------------------------------------


def _collect_ids(component):
    ids = []
    if hasattr(component, "id") and component.id:
        ids.append(component.id)
    if hasattr(component, "children"):
        if isinstance(component.children, list):
            for child in component.children:
                ids.extend(_collect_ids(child))
        elif component.children is not None:
            ids.extend(_collect_ids(component.children))
    return ids


def _find_of_type(component, cls):
    found = []
    if isinstance(component, cls):
        found.append(component)
    if hasattr(component, "children"):
        if isinstance(component.children, list):
            for child in component.children:
                found.extend(_find_of_type(child, cls))
        elif component.children is not None:
            found.extend(_find_of_type(component.children, cls))
    return found


class TestWorkerPanelLayout:
    """Test WorkerPanel layout generation."""

    @pytest.mark.unit
    def test_get_layout_returns_div(self, worker_panel):
        """get_layout should return a Dash Div."""
        layout = worker_panel.get_layout()
        assert layout is not None
        assert isinstance(layout, html.Div)

    @pytest.mark.unit
    def test_layout_has_root_id(self, worker_panel):
        """Layout root div should have the component_id as its id."""
        layout = worker_panel.get_layout()
        assert layout.id == "test-worker"

    @pytest.mark.unit
    def test_layout_contains_children(self, worker_panel):
        """Layout should contain children elements."""
        layout = worker_panel.get_layout()
        assert hasattr(layout, "children")
        assert len(layout.children) > 0

    @pytest.mark.unit
    def test_layout_contains_expected_ids(self, worker_panel):
        """Layout should contain expected component IDs for all dynamic elements."""
        layout = worker_panel.get_layout()

        expected_ids = [
            "test-worker-workers-store",
            "test-worker-status-badge",
            "test-worker-error-display",
            "test-worker-total",
            "test-worker-idle",
            "test-worker-busy",
            "test-worker-stale",
            "test-worker-tasks-done",
            "test-worker-avg-health",
            "test-worker-worker-list",
        ]

        found_ids = _collect_ids(layout)
        for expected_id in expected_ids:
            assert expected_id in found_ids, f"Expected ID '{expected_id}' not found in layout"

    @pytest.mark.unit
    def test_layout_contains_store_not_interval(self, worker_panel):
        """The panel is store-driven: it holds a dcc.Store and owns NO dcc.Interval.

        Tab-gated polling is the dashboard's shared slow interval (N10); a
        panel-owned interval would poll unconditionally and defeat the gating.
        """
        layout = worker_panel.get_layout()
        stores = _find_of_type(layout, dcc.Store)
        intervals = _find_of_type(layout, dcc.Interval)
        assert len(stores) == 1
        assert stores[0].id == "test-worker-workers-store"
        assert len(intervals) == 0


# ---------------------------------------------------------------------------
# TestRenderFromStore (panel state rendering)
# ---------------------------------------------------------------------------


class TestRenderFromStore:
    """WorkerPanel._render_from_store maps a store payload to the 10 panel outputs."""

    @pytest.mark.unit
    def test_none_store_shows_loading(self):
        """A None store (tab not yet visited) yields a LOADING placeholder."""
        result = WorkerPanel._render_from_store(None)
        status_text, status_color = result[0], result[1]
        assert status_text == "LOADING"
        assert status_color == "secondary"
        # counts remain placeholders
        assert result[3] == "--"

    @pytest.mark.unit
    def test_healthy_stats(self):
        """Non-stale, populated stats render HEALTHY with formatted aggregates."""
        stats = {"total": 3, "idle": 2, "busy": 1, "stale": 0, "total_tasks_completed": 100, "total_tasks_failed": 2, "average_health_score": 0.95}
        result = WorkerPanel._render_from_store(_store(workers=[_worker()], stats=stats))
        status_text, status_color, error_children, total, idle, busy, stale, tasks_done, avg_health, _ = result
        assert status_text == "HEALTHY"
        assert status_color == "success"
        assert error_children is None
        assert total == "3"
        assert idle == "2"
        assert busy == "1"
        assert stale == "0"
        assert tasks_done == "100 / 2 fail"
        assert avg_health == "95.0%"

    @pytest.mark.unit
    def test_degraded_when_stale(self):
        """A stale worker in the aggregate flips status to DEGRADED."""
        stats = {"total": 3, "idle": 1, "busy": 1, "stale": 1, "total_tasks_completed": 50, "total_tasks_failed": 0, "average_health_score": 0.8}
        result = WorkerPanel._render_from_store(_store(workers=[_worker()], stats=stats))
        assert result[0] == "DEGRADED"
        assert result[1] == "warning"

    @pytest.mark.unit
    def test_no_workers_when_total_zero(self):
        """Zero total workers renders NO WORKERS."""
        stats = {"total": 0, "idle": 0, "busy": 0, "stale": 0, "total_tasks_completed": 0, "total_tasks_failed": 0, "average_health_score": 0}
        result = WorkerPanel._render_from_store(_store(workers=[], stats=stats, local_reported=False))
        assert result[0] == "NO WORKERS"
        assert result[1] == "warning"

    @pytest.mark.unit
    def test_roster_without_stats_still_renders(self):
        """If the stats endpoint was down but a roster exists, still show HEALTHY + count."""
        result = WorkerPanel._render_from_store(_store(workers=[_worker(), _worker(worker_id="w2")], stats={}))
        assert result[0] == "HEALTHY"
        assert result[3] == "2"  # total derived from roster length

    @pytest.mark.unit
    def test_upstream_error_surfaces_alert(self):
        """An upstream error string is surfaced as a dismissable degraded alert."""
        result = WorkerPanel._render_from_store(_store(workers=[], stats={}, error="Upstream error"))
        error_children = result[2]
        assert isinstance(error_children, dbc.Alert)

    @pytest.mark.unit
    def test_worker_list_is_div(self):
        """The worker-list output is always a Div (table + optional note, or empty-state)."""
        result = WorkerPanel._render_from_store(_store(workers=[_worker()], stats={}))
        assert isinstance(result[9], html.Div)


# ---------------------------------------------------------------------------
# TestRenderWorkerList (roster container + honest local note)
# ---------------------------------------------------------------------------


class TestRenderWorkerList:
    """WorkerPanel._render_worker_list: table-or-empty plus the local-scope note."""

    @pytest.mark.unit
    def test_empty_roster_shows_alert(self):
        div = WorkerPanel._render_worker_list([], local_reported=True)
        alerts = _find_of_type(div, dbc.Alert)
        assert len(alerts) == 1

    @pytest.mark.unit
    def test_populated_roster_shows_table(self):
        div = WorkerPanel._render_worker_list([_worker()], local_reported=True)
        tables = _find_of_type(div, dbc.Table)
        assert len(tables) == 1

    @pytest.mark.unit
    def test_local_not_reported_appends_note(self):
        """When the backend does not report local workers, an honest note is shown."""
        div = WorkerPanel._render_worker_list([_worker()], local_reported=False)
        ids = _collect_ids(div)
        assert "worker-panel-local-note" in ids

    @pytest.mark.unit
    def test_local_reported_omits_note(self):
        """When local workers ARE reported (demo), no scope caveat is shown."""
        div = WorkerPanel._render_worker_list([_worker(kind="local")], local_reported=True)
        ids = _collect_ids(div)
        assert "worker-panel-local-note" not in ids


# ---------------------------------------------------------------------------
# TestRenderWorkersTable / TestRenderWorkerRow
# ---------------------------------------------------------------------------


class TestRenderWorkersTable:
    """WorkerPanel._render_workers_table builds a bordered roster table."""

    @pytest.mark.unit
    def test_returns_table(self):
        table = WorkerPanel._render_workers_table([_worker()])
        assert isinstance(table, dbc.Table)

    @pytest.mark.unit
    def test_header_has_kind_and_heartbeat_columns(self):
        table = WorkerPanel._render_workers_table([_worker()])
        thead = table.children[0]
        header_cells = [th.children for th in thead.children.children]
        assert "Worker ID" in header_cells
        assert "Kind" in header_cells
        assert "Status" in header_cells
        assert "Health" in header_cells
        assert "Last Heartbeat" in header_cells
        assert "Current Task" in header_cells

    @pytest.mark.unit
    def test_one_row_per_worker(self):
        table = WorkerPanel._render_workers_table([_worker(worker_id="a"), _worker(worker_id="b")])
        tbody = table.children[1]
        assert len(tbody.children) == 2


class TestRenderWorkerRow:
    """WorkerPanel._render_worker_row: one <tr> with id, kind, status, health, hb, task."""

    @pytest.mark.unit
    def test_remote_kind_badge(self):
        row = WorkerPanel._render_worker_row(_worker(kind="remote"))
        kind_badge = row.children[1].children
        assert isinstance(kind_badge, dbc.Badge)
        assert kind_badge.children == "REMOTE"
        assert kind_badge.color == "secondary"

    @pytest.mark.unit
    def test_local_kind_badge(self):
        row = WorkerPanel._render_worker_row(_worker(kind="local"))
        kind_badge = row.children[1].children
        assert kind_badge.children == "LOCAL"
        assert kind_badge.color == "info"

    @pytest.mark.unit
    def test_missing_kind_defaults_to_remote(self):
        w = _worker()
        del w["kind"]
        row = WorkerPanel._render_worker_row(w)
        assert row.children[1].children.children == "REMOTE"

    @pytest.mark.unit
    def test_idle_worker_status_badge(self):
        row = WorkerPanel._render_worker_row(_worker(idle=True))
        status_badge = row.children[2].children
        assert status_badge.children == "IDLE"
        assert status_badge.color == "success"

    @pytest.mark.unit
    def test_busy_worker_status_badge(self):
        row = WorkerPanel._render_worker_row(_worker(idle=False, active_task_id="task-cn-7"))
        status_badge = row.children[2].children
        assert status_badge.children == "BUSY"
        assert status_badge.color == "primary"

    @pytest.mark.unit
    def test_health_color_success(self):
        row = WorkerPanel._render_worker_row(_worker(health_score=0.95))
        health_badge = row.children[3].children
        assert health_badge.color == "success"

    @pytest.mark.unit
    def test_health_color_warning(self):
        row = WorkerPanel._render_worker_row(_worker(health_score=0.75))
        assert row.children[3].children.color == "warning"

    @pytest.mark.unit
    def test_health_color_danger(self):
        row = WorkerPanel._render_worker_row(_worker(health_score=0.5))
        assert row.children[3].children.color == "danger"

    @pytest.mark.unit
    def test_unknown_id_defaults(self):
        w = _worker()
        del w["worker_id"]
        row = WorkerPanel._render_worker_row(w)
        # first cell -> html.Code -> "unknown"
        assert row.children[0].children.children == "unknown"

    @pytest.mark.unit
    def test_active_task_rendered(self):
        row = WorkerPanel._render_worker_row(_worker(idle=False, active_task_id="task-abc"))
        task_cell = row.children[5].children
        assert task_cell.children == "task-abc"

    @pytest.mark.unit
    def test_no_active_task_shows_dash(self):
        row = WorkerPanel._render_worker_row(_worker(active_task_id=None))
        task_cell = row.children[5].children
        assert task_cell.children == "—"

    @pytest.mark.unit
    def test_heartbeat_cell_present(self):
        row = WorkerPanel._render_worker_row(_worker(last_heartbeat=1711900100))
        hb_cell = row.children[4].children
        assert hb_cell.children is not None


# ---------------------------------------------------------------------------
# TestFormatHeartbeat
# ---------------------------------------------------------------------------


class TestFormatHeartbeat:
    """WorkerPanel._format_heartbeat: relative age when recent, else UTC clock."""

    @pytest.mark.unit
    def test_recent_heartbeat_relative(self):
        import time

        assert WorkerPanel._format_heartbeat(time.time() - 3).endswith("s ago")

    @pytest.mark.unit
    def test_future_heartbeat_clamped_to_zero(self):
        import time

        assert WorkerPanel._format_heartbeat(time.time() + 50) == "0s ago"

    @pytest.mark.unit
    def test_old_heartbeat_absolute_utc(self):
        # A fixed epoch far in the past -> absolute UTC clock (HH:MM:SS UTC).
        assert WorkerPanel._format_heartbeat(1711929600).endswith("UTC")


# ---------------------------------------------------------------------------
# TestWorkerPanelCallbacks (registration wiring)
# ---------------------------------------------------------------------------


class TestWorkerPanelCallbacks:
    """Callback registration wires the store-driven render callback."""

    @pytest.mark.unit
    def test_register_callbacks_sets_attribute(self, worker_panel):
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)
        assert hasattr(worker_panel, "_cb_render_worker_panel")

    @pytest.mark.unit
    def test_register_callbacks_returns_none(self, worker_panel):
        from dash import Dash

        app = Dash(__name__)
        assert worker_panel.register_callbacks(app) is None

    @pytest.mark.unit
    def test_registered_callback_renders_from_store(self, worker_panel):
        """The registered callback maps a store payload to the panel outputs."""
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)
        stats = {"total": 1, "idle": 1, "busy": 0, "stale": 0, "total_tasks_completed": 5, "total_tasks_failed": 0, "average_health_score": 1.0}
        result = worker_panel._cb_render_worker_panel(_store(workers=[_worker()], stats=stats, local_reported=False))
        assert result[0] == "HEALTHY"
        assert isinstance(result[9], html.Div)


# ---------------------------------------------------------------------------
# TestWorkerStoreHandler (dashboard tab-gated poll)
# ---------------------------------------------------------------------------


class TestWorkerStoreHandler:
    """DashboardManager._update_workers_store_handler: tab-gated + empty-guarded."""

    @pytest.fixture
    def dm(self):
        from frontend.dashboard_manager import DashboardManager

        return DashboardManager({})

    @pytest.mark.unit
    def test_inactive_tab_returns_no_update(self, dm):
        import dash

        assert dm._update_workers_store_handler(n=1, active_tab="metrics") is dash.no_update

    @pytest.mark.unit
    def test_active_tab_fetches_and_annotates(self, dm, mocker):
        list_resp = mocker.MagicMock(ok=True)
        list_resp.json.return_value = {"workers": [_worker(kind="remote")], "count": 1, "local_reported": False}
        stats_resp = mocker.MagicMock(ok=True)
        stats_resp.json.return_value = {"total": 1, "idle": 1, "busy": 0, "stale": 0}

        def fake_get(url, **kwargs):
            return stats_resp if "stats" in url else list_resp

        mocker.patch("frontend.dashboard_manager.requests.get", side_effect=fake_get)
        payload = dm._update_workers_store_handler(n=1, active_tab="workers")
        assert payload["count"] == 1
        assert payload["local_reported"] is False
        assert payload["workers"][0]["kind"] == "remote"
        assert payload["stats"]["total"] == 1

    @pytest.mark.unit
    def test_list_error_returns_no_update(self, dm, mocker):
        import dash

        err_resp = mocker.MagicMock(ok=False, status_code=502)
        mocker.patch("frontend.dashboard_manager.requests.get", return_value=err_resp)
        assert dm._update_workers_store_handler(n=1, active_tab="workers") is dash.no_update

    @pytest.mark.unit
    def test_list_exception_returns_no_update(self, dm, mocker):
        import dash

        mocker.patch("frontend.dashboard_manager.requests.get", side_effect=RuntimeError("boom"))
        assert dm._update_workers_store_handler(n=1, active_tab="workers") is dash.no_update

    @pytest.mark.unit
    def test_stats_failure_is_non_fatal(self, dm, mocker):
        """If /stats is down but the roster succeeds, still return the roster."""
        list_resp = mocker.MagicMock(ok=True)
        list_resp.json.return_value = {"workers": [_worker()], "count": 1, "local_reported": False}

        def fake_get(url, **kwargs):
            if "stats" in url:
                raise RuntimeError("stats down")
            return list_resp

        mocker.patch("frontend.dashboard_manager.requests.get", side_effect=fake_get)
        payload = dm._update_workers_store_handler(n=1, active_tab="workers")
        assert payload["count"] == 1
        assert payload["stats"] == {}


# ---------------------------------------------------------------------------
# TestWorkerStatsEndpoint (demo mode)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app_client():
    """Create test client with demo mode."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        yield client


class TestWorkerStatsEndpoint:
    """Tests for GET /api/v1/workers/stats in demo mode (CAN-HIGH-005)."""

    @pytest.mark.unit
    def test_stats_returns_200(self, app_client):
        """GET /api/v1/workers/stats should return 200."""
        response = app_client.get("/api/v1/workers/stats")
        assert response.status_code == 200

    @pytest.mark.unit
    def test_stats_contains_required_fields(self, app_client):
        """Stats response should contain all required aggregate fields."""
        response = app_client.get("/api/v1/workers/stats")
        data = response.json()

        required_fields = [
            "total",
            "idle",
            "busy",
            "stale",
            "total_tasks_completed",
            "total_tasks_failed",
            "average_health_score",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @pytest.mark.unit
    def test_stats_demo_values(self, app_client):
        """Demo mode should return synthetic worker statistics."""
        response = app_client.get("/api/v1/workers/stats")
        data = response.json()

        assert data["total"] == 2
        assert data["idle"] == 1
        assert data["busy"] == 1
        assert data["stale"] == 0
        assert data["total_tasks_completed"] == 42
        assert data["total_tasks_failed"] == 1
        assert isinstance(data["average_health_score"], float)

    @pytest.mark.unit
    def test_stats_has_timestamp(self, app_client):
        """Demo mode stats should include a timestamp."""
        response = app_client.get("/api/v1/workers/stats")
        data = response.json()
        assert "timestamp" in data


class TestWorkerListEndpoint:
    """Tests for GET /api/v1/workers/list in demo mode (CAN-HIGH-005 + N10/U-5)."""

    @pytest.mark.unit
    def test_list_returns_200(self, app_client):
        """GET /api/v1/workers/list should return 200."""
        response = app_client.get("/api/v1/workers/list")
        assert response.status_code == 200

    @pytest.mark.unit
    def test_list_contains_workers_array(self, app_client):
        """List response should contain 'workers' array and 'count'."""
        response = app_client.get("/api/v1/workers/list")
        data = response.json()
        assert "workers" in data
        assert isinstance(data["workers"], list)
        assert "count" in data

    @pytest.mark.unit
    def test_list_demo_worker_count(self, app_client):
        """Demo mode should return 2 synthetic workers."""
        response = app_client.get("/api/v1/workers/list")
        data = response.json()
        assert data["count"] == 2
        assert len(data["workers"]) == 2

    @pytest.mark.unit
    def test_list_worker_has_required_fields(self, app_client):
        """Each demo worker should have all required fields including kind (N10)."""
        response = app_client.get("/api/v1/workers/list")
        data = response.json()

        required_fields = [
            "worker_id",
            "kind",
            "capabilities",
            "connected_at",
            "last_heartbeat",
            "tasks_completed",
            "tasks_failed",
            "active_task_id",
            "health_score",
            "idle",
        ]

        for worker in data["workers"]:
            for field in required_fields:
                assert field in worker, f"Worker missing required field: {field}"

    @pytest.mark.unit
    def test_list_local_reported_true_in_demo(self, app_client):
        """Demo mode synthesizes both kinds, so it advertises local_reported=True."""
        response = app_client.get("/api/v1/workers/list")
        data = response.json()
        assert data["local_reported"] is True

    @pytest.mark.unit
    def test_list_demo_has_one_local_one_remote(self, app_client):
        """Demo roster exercises both kinds: exactly one local and one remote."""
        response = app_client.get("/api/v1/workers/list")
        kinds = sorted(w["kind"] for w in response.json()["workers"])
        assert kinds == ["local", "remote"]

    @pytest.mark.unit
    def test_list_demo_worker_states(self, app_client):
        """Demo workers should include one idle and one busy worker."""
        response = app_client.get("/api/v1/workers/list")
        workers = response.json()["workers"]

        idle_states = [w["idle"] for w in workers]
        assert True in idle_states, "Expected at least one idle worker"
        assert False in idle_states, "Expected at least one busy worker"

    @pytest.mark.unit
    def test_list_busy_worker_has_active_task(self, app_client):
        """Busy demo worker should have an active_task_id set."""
        response = app_client.get("/api/v1/workers/list")
        workers = response.json()["workers"]

        busy_workers = [w for w in workers if not w["idle"]]
        assert len(busy_workers) > 0
        for worker in busy_workers:
            assert worker["active_task_id"] is not None

    @pytest.mark.unit
    def test_list_idle_worker_has_no_active_task(self, app_client):
        """Idle demo worker should have active_task_id as None."""
        response = app_client.get("/api/v1/workers/list")
        workers = response.json()["workers"]

        idle_workers = [w for w in workers if w["idle"]]
        assert len(idle_workers) > 0
        for worker in idle_workers:
            assert worker["active_task_id"] is None

    @pytest.mark.unit
    def test_list_worker_capabilities_structure(self, app_client):
        """Worker capabilities should have cpu_cores, gpu, and python fields."""
        response = app_client.get("/api/v1/workers/list")
        workers = response.json()["workers"]

        for worker in workers:
            caps = worker["capabilities"]
            assert "cpu_cores" in caps
            assert "gpu" in caps
            assert "python" in caps


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
