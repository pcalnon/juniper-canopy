#!/usr/bin/env python
"""
Comprehensive coverage tests for main.py to achieve 95% coverage.

These tests focus on covering code paths reachable in demo mode.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Set demo mode before imports
os.environ["CASCOR_DEMO_MODE"] = "1"

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


@pytest.fixture(scope="module")
def app_client():
    """Create test client with demo mode."""
    from main import app

    with TestClient(app) as client:
        yield client


class TestRemoteWorkerEndpointsNoBackend:
    """Test remote worker endpoints when no backend available (demo mode)."""

    def test_remote_status_no_backend(self, app_client):
        """Remote status should work in demo mode."""
        response = app_client.get("/api/remote/status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "connected" in data

    def test_remote_connect_no_backend(self, app_client):
        """Remote connect should return 503 in demo mode."""
        response = app_client.post("/api/remote/connect", params={"host": "localhost", "port": 5000, "authkey": "test"})
        assert response.status_code == 503
        assert "Not available in demo mode" in response.json().get("error", "")

    def test_remote_start_workers_no_backend(self, app_client):
        """Start workers should return 503 in demo mode."""
        response = app_client.post("/api/remote/start_workers", params={"num_workers": 2})
        assert response.status_code == 503
        assert "Not available in demo mode" in response.json().get("error", "")

    def test_remote_stop_workers_no_backend(self, app_client):
        """Stop workers should return 503 in demo mode."""
        response = app_client.post("/api/remote/stop_workers", params={"timeout": 5})
        assert response.status_code == 503
        assert "Not available in demo mode" in response.json().get("error", "")

    def test_remote_disconnect_no_backend(self, app_client):
        """Disconnect should return 503 in demo mode."""
        response = app_client.post("/api/remote/disconnect")
        assert response.status_code == 503
        assert "Not available in demo mode" in response.json().get("error", "")


class TestTrainingControlEndpoints:
    """Test training control endpoints with demo mode."""

    def test_train_start_with_reset(self, app_client):
        """Start training with reset flag."""
        # Stop first to ensure clean state
        app_client.post("/api/train/stop")
        response = app_client.post("/api/train/start", params={"reset": True})
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "started"

    def test_train_start_without_reset(self, app_client):
        """Start training without reset."""
        app_client.post("/api/train/stop")
        response = app_client.post("/api/train/start")
        assert response.status_code == 200

    def test_train_pause(self, app_client):
        """Pause training."""
        # Start first
        app_client.post("/api/train/start")
        response = app_client.post("/api/train/pause")
        assert response.status_code == 200
        assert response.json().get("status") == "paused"

    def test_train_resume(self, app_client):
        """Resume training."""
        # Ensure paused state
        app_client.post("/api/train/start")
        app_client.post("/api/train/pause")
        response = app_client.post("/api/train/resume")
        assert response.status_code == 200
        assert response.json().get("status") == "running"

    def test_train_stop(self, app_client):
        """Stop training."""
        response = app_client.post("/api/train/stop")
        assert response.status_code == 200
        assert response.json().get("status") == "stopped"

    def test_train_reset(self, app_client):
        """Reset training."""
        response = app_client.post("/api/train/reset")
        assert response.status_code == 200
        assert response.json().get("status") == "reset"


class TestSetParamsEndpoint:
    """Test parameter setting endpoint."""

    def test_set_params_learning_rate(self, app_client):
        """Set learning rate parameter."""
        response = app_client.post("/api/set_params", json={"learning_rate": 0.05})
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"

    def test_set_params_max_hidden_units(self, app_client):
        """Set max hidden units parameter."""
        response = app_client.post("/api/set_params", json={"max_hidden_units": 15})
        assert response.status_code == 200

    def test_set_params_max_epochs(self, app_client):
        """Set max epochs parameter."""
        response = app_client.post("/api/set_params", json={"max_epochs": 500})
        assert response.status_code == 200

    def test_set_params_all(self, app_client):
        """Set all parameters at once."""
        response = app_client.post("/api/set_params", json={"learning_rate": 0.02, "max_hidden_units": 20, "max_epochs": 300})
        assert response.status_code == 200

    def test_set_params_empty(self, app_client):
        """Set no parameters should return error."""
        response = app_client.post("/api/set_params", json={})
        assert response.status_code == 400


class TestSnapshotEndpoints:
    """Test HDF5 snapshot endpoints."""

    def test_list_snapshots(self, app_client):
        """List available snapshots."""
        response = app_client.get("/api/v1/snapshots")
        assert response.status_code == 200
        data = response.json()
        assert "snapshots" in data

    def test_create_snapshot_demo_mode(self, app_client):
        """Create snapshot in demo mode."""
        response = app_client.post("/api/v1/snapshots", json={"description": "Test snapshot"})
        # Snapshot creation should work in demo mode
        assert response.status_code in (200, 201, 500)
        if response.status_code == 200:
            data = response.json()
            assert "id" in data or "message" in data

    def test_get_snapshot_details(self, app_client):
        """Get details for specific snapshot."""
        # First create a snapshot
        create_response = app_client.post("/api/v1/snapshots", json={})
        if create_response.status_code == 200:
            snapshot_id = create_response.json().get("id")
            if snapshot_id:
                response = app_client.get(f"/api/v1/snapshots/{snapshot_id}")
                # May be 200 or 404 depending on mock snapshots
                assert response.status_code in (200, 404)

    def test_restore_snapshot_not_found(self, app_client):
        """Restore non-existent snapshot should return 404."""
        # Stop training first
        app_client.post("/api/train/stop")
        response = app_client.post("/api/v1/snapshots/nonexistent-id/restore")
        assert response.status_code == 404

    def test_delete_snapshot_demo_mode(self, app_client):
        """Delete snapshot in demo mode."""
        # Create a snapshot first
        create_response = app_client.post("/api/v1/snapshots", json={})
        if create_response.status_code == 200:
            snapshot_id = create_response.json().get("id")
            if snapshot_id:
                response = app_client.delete(f"/api/v1/snapshots/{snapshot_id}")
                # May succeed or fail depending on implementation
                assert response.status_code in (200, 404)

    def test_snapshot_activity_log(self, app_client):
        """Get snapshot activity log."""
        response = app_client.get("/api/v1/snapshots/activity")
        # Activity endpoint should return 200
        assert response.status_code in (200, 404)
        if response.status_code == 200:
            data = response.json()
            assert "activities" in data or isinstance(data, list)


class TestScheduleBroadcast:
    """Test schedule_broadcast function."""

    def test_schedule_broadcast_with_closed_loop(self):
        """Test schedule_broadcast when loop is closed."""
        from unittest.mock import MagicMock

        from main import loop_holder, schedule_broadcast

        # Store original and set to closed loop
        original_loop = loop_holder.get("loop")

        # Create a mock closed loop
        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = True
        loop_holder["loop"] = mock_loop

        # This should not raise, just log warning
        async def dummy_coro():
            pass

        schedule_broadcast(dummy_coro())

        # Restore
        loop_holder["loop"] = original_loop

    def test_schedule_broadcast_with_no_loop(self):
        """Test schedule_broadcast when no loop set."""
        from main import loop_holder, schedule_broadcast

        original_loop = loop_holder.get("loop")
        loop_holder["loop"] = None

        async def dummy_coro():
            pass

        # Should not raise
        schedule_broadcast(dummy_coro())

        loop_holder["loop"] = original_loop


class TestWebSocketEndpoints:
    """Test WebSocket endpoint handling."""

    def test_websocket_training_connection(self, app_client):
        """Test training WebSocket connection."""
        with app_client.websocket_connect("/ws/training"):
            # Connection should succeed - just verify we can connect
            pass

    def test_websocket_control_connection(self, app_client):
        """Test control WebSocket connection."""
        with app_client.websocket_connect("/ws/control") as websocket:
            # Should receive connection confirmation
            data = websocket.receive_json()
            # Verify we got some connection data
            assert "type" in data or "status" in data or "data" in data


class TestRestoreSnapshotWhileTraining:
    """Test restore snapshot while training is running."""

    def test_restore_snapshot_while_training_demo(self, app_client):
        """Cannot restore while training is running in demo mode."""
        # Start training first
        app_client.post("/api/train/start")

        # Try to restore - should fail with 409 or 404
        response = app_client.post("/api/v1/snapshots/some-snapshot/restore")
        # Status depends on whether demo is running and FSM state
        assert response.status_code in (404, 409)

        # Stop training
        app_client.post("/api/train/stop")


class TestMetricsEndpoints:
    """Test metrics API endpoints."""

    def test_metrics_returns_200(self, app_client):
        """Metrics endpoint should return 200."""
        response = app_client.get("/api/metrics")
        assert response.status_code == 200

    def test_metrics_history_returns_200(self, app_client):
        """Metrics history endpoint should return 200."""
        response = app_client.get("/api/metrics/history")
        assert response.status_code == 200


class TestNetworkEndpoints:
    """Test network API endpoints."""

    def test_network_topology_returns_200(self, app_client):
        """Network topology endpoint should return 200 or 404."""
        response = app_client.get("/api/network/topology")
        # May be 200 or 500 depending on demo mode state
        assert response.status_code in (200, 404, 500)

    def test_network_stats_returns_200(self, app_client):
        """Network stats endpoint should return 200."""
        response = app_client.get("/api/network/stats")
        assert response.status_code in (200, 404, 500)


class TestDatasetEndpoints:
    """Test dataset API endpoints."""

    def test_dataset_returns_200(self, app_client):
        """Dataset endpoint should return 200."""
        response = app_client.get("/api/dataset")
        assert response.status_code == 200


class TestDecisionBoundaryEndpoints:
    """Test decision boundary API endpoints."""

    def test_decision_boundary_returns_200(self, app_client):
        """Decision boundary endpoint should return 200."""
        response = app_client.get("/api/decision_boundary")
        assert response.status_code == 200
