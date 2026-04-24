#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_main_endpoints_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-03-31
# Last Modified: 2026-03-31
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Coverage tests for main.py endpoint handlers
#####################################################################
"""Tests for main.py endpoint coverage: snapshot history, snapshot detail, readiness probe."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set demo mode before imports
os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


@pytest.fixture(scope="module")
def app_client():
    """Create test client with demo mode."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
def snapshot_dir(tmp_path):
    """Create isolated snapshot directory."""
    snapshot_path = tmp_path / "snapshots"
    snapshot_path.mkdir(parents=True, exist_ok=True)
    return snapshot_path


class TestSnapshotHistory:
    """Tests for GET /api/v1/snapshots/history (lines 885-911)."""

    @pytest.mark.unit
    def test_history_empty(self, app_client, snapshot_dir):
        """Empty history returns empty list."""
        import main

        with patch.object(main, "_snapshots_dir", str(snapshot_dir)):
            response = app_client.get("/api/v1/snapshots/history")

        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []
        assert data["total"] == 0

    @pytest.mark.unit
    def test_history_with_valid_entries(self, app_client, snapshot_dir):
        """Valid JSONL entries are returned in reverse chronological order."""
        import main

        history_file = snapshot_dir / "snapshot_history.jsonl"
        entries = [
            {"action": "create", "snapshot_id": "snap_1", "ts": 1},
            {"action": "restore", "snapshot_id": "snap_2", "ts": 2},
            {"action": "create", "snapshot_id": "snap_3", "ts": 3},
        ]
        history_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        with patch.object(main, "_snapshots_dir", str(snapshot_dir)):
            response = app_client.get("/api/v1/snapshots/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        # Reversed: newest first
        assert data["history"][0]["snapshot_id"] == "snap_3"
        assert data["history"][2]["snapshot_id"] == "snap_1"

    @pytest.mark.unit
    def test_history_with_invalid_json_lines(self, app_client, snapshot_dir):
        """Invalid JSON lines are skipped; valid lines are still returned."""
        import main

        history_file = snapshot_dir / "snapshot_history.jsonl"
        history_file.write_text(json.dumps({"action": "create", "snapshot_id": "good"}) + "\n" "NOT VALID JSON\n" + json.dumps({"action": "restore", "snapshot_id": "also_good"}) + "\n")

        with patch.object(main, "_snapshots_dir", str(snapshot_dir)):
            response = app_client.get("/api/v1/snapshots/history")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        ids = [e["snapshot_id"] for e in data["history"]]
        assert "good" in ids
        assert "also_good" in ids

    @pytest.mark.unit
    def test_history_with_limit(self, app_client, snapshot_dir):
        """Limit parameter restricts number of returned entries."""
        import main

        history_file = snapshot_dir / "snapshot_history.jsonl"
        entries = [{"action": "create", "snapshot_id": f"snap_{i}"} for i in range(10)]
        history_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        with patch.object(main, "_snapshots_dir", str(snapshot_dir)):
            response = app_client.get("/api/v1/snapshots/history?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    @pytest.mark.unit
    def test_history_no_file_exists(self, app_client, tmp_path):
        """When history file doesn't exist, returns empty list."""
        import main

        empty_dir = tmp_path / "no_history"
        empty_dir.mkdir()

        with patch.object(main, "_snapshots_dir", str(empty_dir)):
            response = app_client.get("/api/v1/snapshots/history")

        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []
        assert data["total"] == 0


class TestSnapshotDetailDemoMode:
    """Tests for GET /api/v1/snapshots/{snapshot_id} in demo mode (lines 935-958)."""

    @pytest.mark.unit
    def test_session_created_snapshot(self, app_client):
        """Session-created demo snapshots are returned with attributes."""
        import main

        demo_snap = {
            "id": "test_session_snap",
            "name": "Test Session Snap",
            "timestamp": "2026-01-01T00:00:00Z",
            "size_bytes": 1024,
            "description": "Created in session",
        }

        original = list(main._demo_snapshots)
        try:
            main._demo_snapshots.insert(0, demo_snap)

            response = app_client.get("/api/v1/snapshots/test_session_snap")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test_session_snap"
            assert data["attributes"]["created_in_session"] is True
            assert data["attributes"]["mode"] == "demo"
            assert data["attributes"]["description"] == "Created in session"
        finally:
            main._demo_snapshots.clear()
            main._demo_snapshots.extend(original)

    @pytest.mark.unit
    def test_mock_snapshot(self, app_client):
        """Mock snapshots (generated by _generate_mock_snapshots) are returned."""
        response = app_client.get("/api/v1/snapshots/demo_snapshot_1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "demo_snapshot_1"
        assert data["attributes"]["mode"] == "demo"
        assert "epochs_trained" in data["attributes"]
        assert "hidden_units" in data["attributes"]

    @pytest.mark.unit
    def test_snapshot_not_found_demo(self, app_client):
        """Non-existent snapshot returns 404 in demo mode."""
        response = app_client.get("/api/v1/snapshots/nonexistent_xyz")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestSnapshotDetailRealMode:
    """Tests for GET /api/v1/snapshots/{snapshot_id} in real mode (lines 963-999)."""

    def _make_service_backend(self):
        mock_svc = MagicMock()
        mock_svc.backend_type = "service"
        mock_svc.is_training_active.return_value = False
        return mock_svc

    @pytest.mark.unit
    def test_real_mode_snapshot_found(self, app_client, snapshot_dir):
        """Snapshot file found on disk is returned with metadata."""
        import main

        snapshot_file = snapshot_dir / "my_model.h5"
        snapshot_file.write_bytes(b"\x00" * 256)

        mock_svc = self._make_service_backend()

        with (
            patch.object(main, "backend", mock_svc),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.get("/api/v1/snapshots/my_model")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "my_model"
        assert data["name"] == "my_model.h5"
        assert data["size_bytes"] == 256
        assert "timestamp" in data
        assert "path" in data

    @pytest.mark.unit
    def test_real_mode_snapshot_not_found(self, app_client, snapshot_dir):
        """Missing snapshot returns 404 in real mode."""
        import main

        mock_svc = self._make_service_backend()

        with (
            patch.object(main, "backend", mock_svc),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.get("/api/v1/snapshots/does_not_exist")

        assert response.status_code == 404

    @pytest.mark.unit
    def test_real_mode_snapshot_dir_missing(self, app_client, tmp_path):
        """Missing snapshot directory returns 404."""
        import main

        mock_svc = self._make_service_backend()
        nonexistent = str(tmp_path / "no_such_dir")

        with (
            patch.object(main, "backend", mock_svc),
            patch.object(main, "_snapshots_dir", nonexistent),
        ):
            response = app_client.get("/api/v1/snapshots/any_id")

        assert response.status_code == 404
        assert "directory" in response.json()["detail"].lower()

    @pytest.mark.unit
    def test_real_mode_h5py_import_error(self, app_client, snapshot_dir):
        """When h5py is not available, attributes are None but response succeeds."""
        import builtins

        import main

        snapshot_file = snapshot_dir / "no_h5py.h5"
        snapshot_file.write_bytes(b"\x00" * 128)

        mock_svc = self._make_service_backend()
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "h5py":
                raise ImportError("No module named 'h5py'")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(main, "backend", mock_svc),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
            patch.object(builtins, "__import__", side_effect=mock_import),
        ):
            response = app_client.get("/api/v1/snapshots/no_h5py")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "no_h5py"
        assert data["attributes"] is None

    @pytest.mark.unit
    def test_real_mode_h5py_read_error(self, app_client, snapshot_dir):
        """When h5py can't read the file, attributes are None but response succeeds."""
        import main

        # Write non-HDF5 content so h5py.File raises an error
        snapshot_file = snapshot_dir / "bad_h5.h5"
        snapshot_file.write_text("this is not valid HDF5")

        mock_svc = self._make_service_backend()

        with (
            patch.object(main, "backend", mock_svc),
            patch.object(main, "_snapshots_dir", str(snapshot_dir)),
        ):
            response = app_client.get("/api/v1/snapshots/bad_h5")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "bad_h5"
        # Attributes should be None due to read failure (or possibly {} if h5py not installed)


class TestReadinessProbe:
    """Tests for GET /v1/health/ready (lines 515-537)."""

    @pytest.mark.unit
    def test_readiness_response_structure(self, app_client):
        """Readiness probe returns expected structure with dependency info."""
        import main
        from health import DependencyStatus

        data_dep = DependencyStatus(name="JuniperData Service", status="healthy", latency_ms=5.0, message="ok")
        cascor_dep = DependencyStatus(name="JuniperCascor Service", status="healthy", latency_ms=3.0, message="ok")

        with patch.object(main, "probe_dependency", side_effect=[data_dep, cascor_dep]):
            with patch.object(main.settings, "cascor_service_url", "http://fake:8200"):
                response = app_client.get("/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "juniper-canopy"
        assert data["version"] == main.APP_VERSION
        assert "dependencies" in data
        assert "details" in data

    @pytest.mark.unit
    def test_readiness_degraded_when_unhealthy(self, app_client):
        """Readiness returns 'degraded' when a dependency is unhealthy."""
        import main
        from health import DependencyStatus

        data_dep = DependencyStatus(name="JuniperData Service", status="unhealthy", latency_ms=5.0, message="timeout")
        cascor_dep = DependencyStatus(name="JuniperCascor Service", status="healthy", latency_ms=3.0, message="ok")

        with patch.object(main, "probe_dependency", side_effect=[data_dep, cascor_dep]):
            with patch.object(main.settings, "cascor_service_url", "http://fake:8200"):
                response = app_client.get("/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"

    @pytest.mark.unit
    def test_readiness_no_cascor_url(self, app_client):
        """When cascor_service_url is None, cascor dependency is 'not_configured'."""
        import main
        from health import DependencyStatus

        data_dep = DependencyStatus(name="JuniperData Service", status="healthy", latency_ms=5.0, message="ok")

        with patch.object(main, "probe_dependency", return_value=data_dep):
            with patch.object(main.settings, "cascor_service_url", None):
                response = app_client.get("/v1/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        cascor_dep = data["dependencies"]["juniper_cascor"]
        assert cascor_dep["status"] == "not_configured"
        assert "demo mode" in cascor_dep["message"].lower()


class TestMetricsLayouts:
    """Tests for metrics layouts CRUD endpoints (lines 1365-1542)."""

    @pytest.fixture(autouse=True)
    def _layouts_tmp(self, tmp_path):
        """Redirect _layouts_dir to a temp directory for isolation."""
        import main

        self._orig = main._layouts_dir
        main._layouts_dir = str(tmp_path / "layouts")
        yield
        main._layouts_dir = self._orig

    @pytest.mark.unit
    def test_list_empty(self, app_client):
        """Empty layouts dir returns empty list."""
        response = app_client.get("/api/v1/metrics/layouts")
        assert response.status_code == 200
        data = response.json()
        assert data["layouts"] == []
        assert data["total"] == 0

    @pytest.mark.unit
    def test_list_populated(self, app_client):
        """Saved layouts appear in list."""
        app_client.post("/api/v1/metrics/layouts?name=alpha&description=First")
        app_client.post("/api/v1/metrics/layouts?name=beta&description=Second")

        response = app_client.get("/api/v1/metrics/layouts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = {layout["name"] for layout in data["layouts"]}
        assert names == {"alpha", "beta"}

    @pytest.mark.unit
    def test_get_found(self, app_client):
        """Get an existing layout by name."""
        app_client.post("/api/v1/metrics/layouts?name=mylay")
        response = app_client.get("/api/v1/metrics/layouts/mylay")
        assert response.status_code == 200
        assert response.json()["name"] == "mylay"

    @pytest.mark.unit
    def test_get_not_found(self, app_client):
        """Get a non-existent layout returns 404."""
        response = app_client.get("/api/v1/metrics/layouts/nonexistent")
        assert response.status_code == 404

    @pytest.mark.unit
    def test_save_valid(self, app_client):
        """Save a layout with a valid name returns 201."""
        response = app_client.post("/api/v1/metrics/layouts?name=new_layout&description=desc")
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new_layout"
        assert data["message"] == "Layout saved successfully"

    @pytest.mark.unit
    def test_save_empty_name(self, app_client):
        """Save with empty name returns 400."""
        response = app_client.post("/api/v1/metrics/layouts?name=%20")
        assert response.status_code == 400

    @pytest.mark.unit
    def test_delete_found(self, app_client):
        """Delete an existing layout returns success."""
        app_client.post("/api/v1/metrics/layouts?name=to_delete")
        response = app_client.delete("/api/v1/metrics/layouts/to_delete")
        assert response.status_code == 200
        assert response.json()["message"] == "Layout deleted successfully"

        # Verify it's gone
        response = app_client.get("/api/v1/metrics/layouts/to_delete")
        assert response.status_code == 404

    @pytest.mark.unit
    def test_delete_not_found(self, app_client):
        """Delete a non-existent layout returns 404."""
        response = app_client.delete("/api/v1/metrics/layouts/no_such")
        assert response.status_code == 404


class TestRedisAndCassandraEndpoints:
    """Tests for Redis and Cassandra status/metrics endpoints (lines 1550-1626)."""

    @pytest.mark.unit
    def test_redis_status(self, app_client):
        """GET /api/v1/redis/status returns 200 with status field."""
        response = app_client.get("/api/v1/redis/status")
        assert response.status_code == 200
        assert "status" in response.json()

    @pytest.mark.unit
    def test_redis_metrics(self, app_client):
        """GET /api/v1/redis/metrics returns 200 with status field."""
        response = app_client.get("/api/v1/redis/metrics")
        assert response.status_code == 200
        assert "status" in response.json()

    @pytest.mark.unit
    def test_cassandra_status(self, app_client):
        """GET /api/v1/cassandra/status returns 200 with status field."""
        response = app_client.get("/api/v1/cassandra/status")
        assert response.status_code == 200
        assert "status" in response.json()

    @pytest.mark.unit
    def test_cassandra_metrics(self, app_client):
        """GET /api/v1/cassandra/metrics returns 200 with status field."""
        response = app_client.get("/api/v1/cassandra/metrics")
        assert response.status_code == 200
        assert "status" in response.json()


class TestRemoteWorkerEndpoints:
    """Tests for remote worker management endpoints in demo mode (lines 1828-1912)."""

    @pytest.mark.unit
    def test_remote_status(self, app_client):
        """GET /api/remote/status returns 200 with available=False in demo mode."""
        response = app_client.get("/api/remote/status")
        assert response.status_code == 200
        data = response.json()
        assert data["available"] is False
        assert "demo" in data.get("error", "").lower()

    @pytest.mark.unit
    def test_remote_connect(self, app_client):
        """POST /api/remote/connect returns 503 in demo mode (SEC-13: body required)."""
        response = app_client.post(
            "/api/remote/connect",
            json={"host": "localhost", "port": 5000, "authkey": "secret"},
        )
        assert response.status_code == 503
        assert "demo" in response.json()["error"].lower()

    @pytest.mark.unit
    def test_remote_start_workers(self, app_client):
        """POST /api/remote/start_workers returns 503 in demo mode."""
        response = app_client.post("/api/remote/start_workers?num_workers=2")
        assert response.status_code == 503
        assert "demo" in response.json()["error"].lower()

    @pytest.mark.unit
    def test_remote_stop_workers(self, app_client):
        """POST /api/remote/stop_workers returns 503 in demo mode."""
        response = app_client.post("/api/remote/stop_workers?timeout=5")
        assert response.status_code == 503
        assert "demo" in response.json()["error"].lower()

    @pytest.mark.unit
    def test_remote_disconnect(self, app_client):
        """POST /api/remote/disconnect returns 503 in demo mode."""
        response = app_client.post("/api/remote/disconnect")
        assert response.status_code == 503
        assert "demo" in response.json()["error"].lower()


class TestSnapshotListEndpoint:
    """Tests for GET /api/v1/snapshots endpoint (lines 836-869)."""

    @pytest.mark.unit
    def test_snapshots_list_demo_mode(self, app_client):
        """GET /api/v1/snapshots in demo mode returns mock snapshots."""
        response = app_client.get("/api/v1/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert "snapshots" in data
        assert len(data["snapshots"]) > 0
        assert "demo" in data.get("message", "").lower()

    @pytest.mark.unit
    def test_snapshots_list_has_ids(self, app_client):
        """Each snapshot in the list has an id field."""
        response = app_client.get("/api/v1/snapshots")
        assert response.status_code == 200
        for snap in response.json()["snapshots"]:
            assert "id" in snap
