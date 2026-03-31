#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_worker_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
# Date:          2026-03-31
# Last Modified: 2026-03-31
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for WorkerPanel component and worker API endpoints
#####################################################################
"""Unit tests for WorkerPanel component and /api/v1/workers/* endpoints (CAN-HIGH-005)."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

from frontend.components.worker_panel import (  # noqa: E402
    DEFAULT_API_TIMEOUT,
    DEFAULT_REFRESH_INTERVAL_MS,
    WorkerPanel,
)

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


@pytest.fixture
def custom_panel():
    """Create WorkerPanel instance with custom interval."""
    return WorkerPanel({"interval_ms": 10000, "api_timeout": 5}, component_id="custom-worker")


# ---------------------------------------------------------------------------
# TestWorkerPanelInitialization
# ---------------------------------------------------------------------------


class TestWorkerPanelInitialization:
    """Test WorkerPanel initialization."""

    @pytest.mark.unit
    def test_init_with_default_config(self):
        """Should initialize with empty config and use defaults."""
        panel = WorkerPanel({})
        assert panel is not None
        assert panel.component_id == "worker-panel"
        assert panel.interval_ms == DEFAULT_REFRESH_INTERVAL_MS
        assert panel.api_timeout == DEFAULT_API_TIMEOUT

    @pytest.mark.unit
    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        panel = WorkerPanel(config, component_id="my-workers")
        assert panel.component_id == "my-workers"

    @pytest.mark.unit
    def test_init_with_custom_interval(self):
        """Should use interval_ms from config when provided."""
        panel = WorkerPanel({"interval_ms": 15000})
        assert panel.interval_ms == 15000

    @pytest.mark.unit
    def test_init_with_custom_api_timeout(self):
        """Should use api_timeout from config when provided."""
        panel = WorkerPanel({"api_timeout": 10})
        assert panel.api_timeout == 10

    @pytest.mark.unit
    def test_init_env_var_override(self):
        """Should override interval_ms from JUNIPER_CANOPY_WORKER_REFRESH_INTERVAL_MS env var."""
        with patch.dict(os.environ, {"JUNIPER_CANOPY_WORKER_REFRESH_INTERVAL_MS": "7000"}):
            panel = WorkerPanel({})
        assert panel.interval_ms == 7000

    @pytest.mark.unit
    def test_init_env_var_invalid_falls_back_to_default(self):
        """Should fall back to default when env var is not a valid integer."""
        with patch.dict(os.environ, {"JUNIPER_CANOPY_WORKER_REFRESH_INTERVAL_MS": "not_a_number"}):
            panel = WorkerPanel({})
        assert panel.interval_ms == DEFAULT_REFRESH_INTERVAL_MS

    @pytest.mark.unit
    def test_init_config_takes_priority_over_env(self):
        """Config interval_ms should take priority over env var."""
        with patch.dict(os.environ, {"JUNIPER_CANOPY_WORKER_REFRESH_INTERVAL_MS": "7000"}):
            panel = WorkerPanel({"interval_ms": 3000})
        assert panel.interval_ms == 3000


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


class TestWorkerPanelLayout:
    """Test WorkerPanel layout generation."""

    @pytest.mark.unit
    def test_get_layout_returns_div(self, worker_panel):
        """get_layout should return a Dash Div."""
        layout = worker_panel.get_layout()
        assert layout is not None
        from dash import html

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
            "test-worker-status-badge",
            "test-worker-error-display",
            "test-worker-total",
            "test-worker-idle",
            "test-worker-busy",
            "test-worker-stale",
            "test-worker-tasks-done",
            "test-worker-avg-health",
            "test-worker-worker-list",
            "test-worker-refresh-interval",
        ]

        def collect_ids(component):
            ids = []
            if hasattr(component, "id") and component.id:
                ids.append(component.id)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        ids.extend(collect_ids(child))
                elif component.children is not None:
                    ids.extend(collect_ids(component.children))
            return ids

        found_ids = collect_ids(layout)
        for expected_id in expected_ids:
            assert expected_id in found_ids, f"Expected ID '{expected_id}' not found in layout"

    @pytest.mark.unit
    def test_layout_contains_interval(self, worker_panel):
        """Layout should contain a dcc.Interval component for refresh."""
        from dash import dcc

        layout = worker_panel.get_layout()

        def find_intervals(component):
            intervals = []
            if isinstance(component, dcc.Interval):
                intervals.append(component)
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    for child in component.children:
                        intervals.extend(find_intervals(child))
                elif component.children is not None:
                    intervals.extend(find_intervals(component.children))
            return intervals

        intervals = find_intervals(layout)
        assert len(intervals) == 1
        assert intervals[0].interval == worker_panel.interval_ms

    @pytest.mark.unit
    def test_layout_custom_interval_reflected(self, custom_panel):
        """Layout interval should match the custom interval_ms config."""
        from dash import dcc

        layout = custom_panel.get_layout()

        # Interval is a direct child of the root Div
        intervals = [child for child in layout.children if isinstance(child, dcc.Interval)]
        assert len(intervals) == 1
        assert intervals[0].interval == 10000


# ---------------------------------------------------------------------------
# TestWorkerPanelCallbacks
# ---------------------------------------------------------------------------


class TestWorkerPanelCallbacks:
    """Test WorkerPanel callback registration."""

    @pytest.mark.unit
    def test_register_callbacks_sets_attribute(self, worker_panel):
        """register_callbacks should set _cb_update_worker_panel attribute."""
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)
        assert hasattr(worker_panel, "_cb_update_worker_panel")
        assert callable(worker_panel._cb_update_worker_panel)

    @pytest.mark.unit
    def test_register_callbacks_returns_none(self, worker_panel):
        """register_callbacks should return None."""
        from dash import Dash

        app = Dash(__name__)
        result = worker_panel.register_callbacks(app)
        assert result is None

    @pytest.mark.unit
    def test_callback_returns_defaults_on_connection_error(self, worker_panel):
        """Callback should return safe defaults when API is unreachable."""
        import requests
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)

        with patch("frontend.components.worker_panel.requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
            result = worker_panel._cb_update_worker_panel(0)

        assert len(result) == 10
        status_text, status_color, error_children, total, idle, busy, stale, tasks_done, avg_health, worker_list = result

        # Should show UNAVAILABLE with safe default values
        assert status_text == "UNAVAILABLE"
        assert status_color == "secondary"
        assert total == "--"
        assert idle == "--"
        assert busy == "--"
        assert stale == "--"
        assert tasks_done == "--"
        assert avg_health == "--"

    @pytest.mark.unit
    def test_callback_returns_defaults_on_timeout(self, worker_panel):
        """Callback should return safe defaults when API times out."""
        import requests
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)

        with patch("frontend.components.worker_panel.requests.get", side_effect=requests.exceptions.Timeout("Timeout")):
            result = worker_panel._cb_update_worker_panel(0)

        assert len(result) == 10
        status_text = result[0]
        error_children = result[2]

        assert status_text == "UNAVAILABLE"
        # Should show a timeout warning alert
        assert error_children is not None

    @pytest.mark.unit
    def test_callback_handles_successful_stats_response(self, worker_panel):
        """Callback should parse successful stats response correctly."""
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)

        mock_stats_response = MagicMock()
        mock_stats_response.status_code = 200
        mock_stats_response.json.return_value = {
            "data": {
                "total": 3,
                "idle": 2,
                "busy": 1,
                "stale": 0,
                "total_tasks_completed": 100,
                "total_tasks_failed": 2,
                "average_health_score": 0.95,
            }
        }

        mock_list_response = MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.json.return_value = {"data": {"workers": []}}

        def mock_get(url, **kwargs):
            if "stats" in url:
                return mock_stats_response
            return mock_list_response

        with patch("frontend.components.worker_panel.requests.get", side_effect=mock_get):
            result = worker_panel._cb_update_worker_panel(1)

        status_text, status_color, error_children, total, idle, busy, stale, tasks_done, avg_health, worker_list = result

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
    def test_callback_shows_degraded_when_stale_workers(self, worker_panel):
        """Callback should show DEGRADED status when stale workers exist."""
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)

        mock_stats_response = MagicMock()
        mock_stats_response.status_code = 200
        mock_stats_response.json.return_value = {
            "data": {
                "total": 3,
                "idle": 1,
                "busy": 1,
                "stale": 1,
                "total_tasks_completed": 50,
                "total_tasks_failed": 0,
                "average_health_score": 0.8,
            }
        }

        mock_list_response = MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.json.return_value = {"data": {"workers": []}}

        def mock_get(url, **kwargs):
            if "stats" in url:
                return mock_stats_response
            return mock_list_response

        with patch("frontend.components.worker_panel.requests.get", side_effect=mock_get):
            result = worker_panel._cb_update_worker_panel(1)

        assert result[0] == "DEGRADED"
        assert result[1] == "warning"

    @pytest.mark.unit
    def test_callback_shows_no_workers_when_total_zero(self, worker_panel):
        """Callback should show NO WORKERS when total is 0."""
        from dash import Dash

        app = Dash(__name__)
        worker_panel.register_callbacks(app)

        mock_stats_response = MagicMock()
        mock_stats_response.status_code = 200
        mock_stats_response.json.return_value = {
            "data": {
                "total": 0,
                "idle": 0,
                "busy": 0,
                "stale": 0,
                "total_tasks_completed": 0,
                "total_tasks_failed": 0,
                "average_health_score": 0,
            }
        }

        mock_list_response = MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.json.return_value = {"data": {"workers": []}}

        def mock_get(url, **kwargs):
            if "stats" in url:
                return mock_stats_response
            return mock_list_response

        with patch("frontend.components.worker_panel.requests.get", side_effect=mock_get):
            result = worker_panel._cb_update_worker_panel(1)

        assert result[0] == "NO WORKERS"
        assert result[1] == "warning"

    @pytest.mark.unit
    def test_callback_renders_worker_cards_from_list(self, worker_panel):
        """Callback should render worker cards when workers are returned."""
        from dash import Dash, html

        app = Dash(__name__)
        worker_panel.register_callbacks(app)

        mock_stats_response = MagicMock()
        mock_stats_response.status_code = 200
        mock_stats_response.json.return_value = {
            "data": {
                "total": 1,
                "idle": 1,
                "busy": 0,
                "stale": 0,
                "total_tasks_completed": 5,
                "total_tasks_failed": 0,
                "average_health_score": 1.0,
            }
        }

        mock_list_response = MagicMock()
        mock_list_response.status_code = 200
        mock_list_response.json.return_value = {
            "data": {
                "workers": [
                    {
                        "worker_id": "worker-001",
                        "idle": True,
                        "health_score": 1.0,
                        "capabilities": {"cpu_cores": 8},
                        "tasks_completed": 5,
                        "tasks_failed": 0,
                    }
                ]
            }
        }

        def mock_get(url, **kwargs):
            if "stats" in url:
                return mock_stats_response
            return mock_list_response

        with patch("frontend.components.worker_panel.requests.get", side_effect=mock_get):
            result = worker_panel._cb_update_worker_panel(1)

        worker_list = result[9]
        assert isinstance(worker_list, html.Div)


# ---------------------------------------------------------------------------
# TestRenderWorkerCard
# ---------------------------------------------------------------------------


class TestRenderWorkerCard:
    """Test WorkerPanel._render_worker_card() static method."""

    @pytest.mark.unit
    def test_render_idle_worker(self):
        """Should render card for an idle worker with IDLE badge."""
        import dash_bootstrap_components as dbc

        worker = {
            "worker_id": "worker-idle-01",
            "idle": True,
            "health_score": 1.0,
            "capabilities": {"cpu_cores": 8, "gpu": False, "python": "3.13"},
            "tasks_completed": 10,
            "tasks_failed": 0,
            "connected_at": 1711900000,
            "active_task_id": None,
        }

        card = WorkerPanel._render_worker_card(worker)
        assert isinstance(card, dbc.Card)

        # Find the status badge in the card header
        header = card.children[0]  # CardHeader
        header_div = header.children  # inner Div
        badge = header_div.children[1]  # second child is the badge
        assert isinstance(badge, dbc.Badge)
        assert badge.children == "IDLE"
        assert badge.color == "success"

    @pytest.mark.unit
    def test_render_busy_worker(self):
        """Should render card for a busy worker with BUSY badge and active task."""
        import dash_bootstrap_components as dbc

        worker = {
            "worker_id": "worker-busy-01",
            "idle": False,
            "health_score": 0.95,
            "capabilities": {"cpu_cores": 4, "gpu": True, "python": "3.13"},
            "tasks_completed": 17,
            "tasks_failed": 1,
            "connected_at": 1711900000,
            "active_task_id": "task-cn-round-7-cand-3",
        }

        card = WorkerPanel._render_worker_card(worker)
        assert isinstance(card, dbc.Card)

        # Check BUSY badge
        header = card.children[0]
        header_div = header.children
        badge = header_div.children[1]
        assert badge.children == "BUSY"
        assert badge.color == "primary"

        # Card body should have an active task row
        body = card.children[1]  # CardBody
        body_rows = body.children
        # Should have 3 rows: capabilities, stats, active task
        assert len(body_rows) == 3

    @pytest.mark.unit
    def test_render_worker_no_active_task(self):
        """Should render card without active task row when no task is active."""
        worker = {
            "worker_id": "worker-no-task",
            "idle": True,
            "health_score": 0.85,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
            "active_task_id": None,
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        body_rows = body.children
        # Should have 2 rows: capabilities and stats (no active task row)
        assert len(body_rows) == 2

    @pytest.mark.unit
    def test_render_worker_health_color_success(self):
        """Health score >= 0.9 should use 'success' color."""
        import dash_bootstrap_components as dbc

        worker = {
            "worker_id": "healthy",
            "idle": True,
            "health_score": 0.95,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        stats_row = body.children[1]  # second row has health badge
        health_col = stats_row.children[1]  # second column
        health_badge = health_col.children[1]  # Badge is second child in col
        assert isinstance(health_badge, dbc.Badge)
        assert health_badge.color == "success"

    @pytest.mark.unit
    def test_render_worker_health_color_warning(self):
        """Health score >= 0.7 and < 0.9 should use 'warning' color."""
        import dash_bootstrap_components as dbc

        worker = {
            "worker_id": "warning-health",
            "idle": True,
            "health_score": 0.75,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        stats_row = body.children[1]
        health_col = stats_row.children[1]
        health_badge = health_col.children[1]
        assert isinstance(health_badge, dbc.Badge)
        assert health_badge.color == "warning"

    @pytest.mark.unit
    def test_render_worker_health_color_danger(self):
        """Health score < 0.7 should use 'danger' color."""
        import dash_bootstrap_components as dbc

        worker = {
            "worker_id": "danger-health",
            "idle": True,
            "health_score": 0.5,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        stats_row = body.children[1]
        health_col = stats_row.children[1]
        health_badge = health_col.children[1]
        assert isinstance(health_badge, dbc.Badge)
        assert health_badge.color == "danger"

    @pytest.mark.unit
    def test_render_worker_capabilities_display(self):
        """Should display CPU, GPU, and Python version capabilities."""
        worker = {
            "worker_id": "caps-worker",
            "idle": True,
            "health_score": 1.0,
            "capabilities": {"cpu_cores": 16, "gpu": True, "python": "3.14"},
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        cap_row = body.children[0]  # first row is capabilities
        cap_col = cap_row.children[0]
        cap_text = cap_col.children.children  # Small -> text

        assert "16 CPU" in cap_text
        assert "GPU" in cap_text
        assert "Py 3.14" in cap_text

    @pytest.mark.unit
    def test_render_worker_empty_capabilities(self):
        """Should show 'No capability data' when capabilities dict is empty."""
        worker = {
            "worker_id": "no-caps",
            "idle": True,
            "health_score": 1.0,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        cap_row = body.children[0]
        cap_col = cap_row.children[0]
        cap_text = cap_col.children.children

        assert "No capability data" in cap_text

    @pytest.mark.unit
    def test_render_worker_unknown_id(self):
        """Should default worker_id to 'unknown' when not provided."""
        worker = {
            "idle": True,
            "health_score": 0.5,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
        }

        card = WorkerPanel._render_worker_card(worker)
        header = card.children[0]
        header_div = header.children
        worker_name = header_div.children[0]  # Strong element
        assert worker_name.children == "unknown"

    @pytest.mark.unit
    def test_render_worker_connected_at_formatting(self):
        """Should format connected_at timestamp as HH:MM:SS UTC."""
        worker = {
            "worker_id": "time-worker",
            "idle": True,
            "health_score": 1.0,
            "capabilities": {},
            "tasks_completed": 0,
            "tasks_failed": 0,
            "connected_at": 1711929600,  # 2024-04-01 00:00:00 UTC
        }

        card = WorkerPanel._render_worker_card(worker)
        body = card.children[1]
        stats_row = body.children[1]
        connected_col = stats_row.children[2]  # third column
        connected_text = connected_col.children[1]  # Small text element
        assert "UTC" in connected_text.children


# ---------------------------------------------------------------------------
# TestWorkerAPIEndpoints (demo mode)
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
    """Tests for GET /api/v1/workers/list in demo mode (CAN-HIGH-005)."""

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
        """Each demo worker should have all required fields."""
        response = app_client.get("/api/v1/workers/list")
        data = response.json()

        required_fields = [
            "worker_id",
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
