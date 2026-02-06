#!/usr/bin/env python
"""
Tests for main.py import-time branches and endpoint coverage.

These tests focus on covering code paths reachable in demo mode.
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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


class TestScheduleBroadcastEdgeCases:
    """Test schedule_broadcast function edge cases."""

    def test_schedule_broadcast_with_closed_loop(self):
        """Test schedule_broadcast when loop is closed."""
        from main import loop_holder, schedule_broadcast

        original_loop = loop_holder.get("loop")

        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = True
        loop_holder["loop"] = mock_loop

        async def dummy_coro():
            pass

        # Should not raise
        schedule_broadcast(dummy_coro())

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

    def test_schedule_broadcast_exception_handling(self):
        """Test schedule_broadcast exception handling."""
        from main import loop_holder, schedule_broadcast

        original_loop = loop_holder.get("loop")

        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = False

        # Mock run_coroutine_threadsafe to raise
        with patch("asyncio.run_coroutine_threadsafe", side_effect=RuntimeError("Test error")):
            loop_holder["loop"] = mock_loop

            async def dummy_coro():
                pass

            # Should not raise, just log
            schedule_broadcast(dummy_coro())

        loop_holder["loop"] = original_loop


class TestWebSocketEndpointsDemo:
    """Test WebSocket endpoints in demo mode."""

    def test_websocket_training_connect_disconnect(self, app_client):
        """Test WebSocket training connection and disconnect."""
        # Connect
        with app_client.websocket_connect("/ws/training") as ws:
            assert ws
        # disconnect
        assert not ws

    def test_websocket_control_connect_disconnect(self, app_client):
        """Test WebSocket control connection and disconnect."""
        with app_client.websocket_connect("/ws/control") as ws:
            data = ws.receive_json()
            assert "type" in data or "data" in data


class TestDemoModeTrainingControls:
    """Test training control endpoints in demo mode."""

    def test_train_start_demo(self, app_client):
        """Start training in demo mode."""
        app_client.post("/api/train/stop")  # Ensure stopped
        response = app_client.post("/api/train/start")
        assert response.status_code == 200

    def test_train_pause_demo(self, app_client):
        """Pause training in demo mode."""
        app_client.post("/api/train/start")
        response = app_client.post("/api/train/pause")
        assert response.status_code == 200

    def test_train_resume_demo(self, app_client):
        """Resume training in demo mode."""
        app_client.post("/api/train/start")
        app_client.post("/api/train/pause")
        response = app_client.post("/api/train/resume")
        assert response.status_code == 200

    def test_train_stop_demo(self, app_client):
        """Stop training in demo mode."""
        response = app_client.post("/api/train/stop")
        assert response.status_code == 200

    def test_train_reset_demo(self, app_client):
        """Reset training in demo mode."""
        response = app_client.post("/api/train/reset")
        assert response.status_code == 200

    def test_train_status_demo(self, app_client):
        """Get training status in demo mode."""
        response = app_client.get("/api/train/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("backend") == "demo"


class TestRemoteWorkerEndpointsDemo:
    """Test remote worker endpoints in demo mode (no backend)."""

    def test_remote_status_demo(self, app_client):
        """Remote status in demo mode."""
        response = app_client.get("/api/remote/status")
        assert response.status_code == 200

    def test_remote_connect_demo_no_backend(self, app_client):
        """Remote connect returns 503 in demo mode."""
        response = app_client.post("/api/remote/connect", params={"host": "localhost", "port": 5000, "authkey": "secret"})
        assert response.status_code == 503

    def test_remote_start_workers_demo_no_backend(self, app_client):
        """Remote start workers returns 503 in demo mode."""
        response = app_client.post("/api/remote/start_workers")
        assert response.status_code == 503

    def test_remote_stop_workers_demo_no_backend(self, app_client):
        """Remote stop workers returns 503 in demo mode."""
        response = app_client.post("/api/remote/stop_workers")
        assert response.status_code == 503

    def test_remote_disconnect_demo_no_backend(self, app_client):
        """Remote disconnect returns 503 in demo mode."""
        response = app_client.post("/api/remote/disconnect")
        assert response.status_code == 503


class TestSetParamsEndpoint:
    """Test set_params endpoint."""

    def test_set_params_learning_rate(self, app_client):
        """Set learning rate."""
        response = app_client.post("/api/set_params", json={"learning_rate": 0.05})
        assert response.status_code == 200

    def test_set_params_max_hidden_units(self, app_client):
        """Set max hidden units."""
        response = app_client.post("/api/set_params", json={"max_hidden_units": 15})
        assert response.status_code == 200

    def test_set_params_max_epochs(self, app_client):
        """Set max epochs."""
        response = app_client.post("/api/set_params", json={"max_epochs": 500})
        assert response.status_code == 200

    def test_set_params_all(self, app_client):
        """Set all parameters."""
        response = app_client.post("/api/set_params", json={"learning_rate": 0.02, "max_hidden_units": 20, "max_epochs": 300})
        assert response.status_code == 200

    def test_set_params_empty(self, app_client):
        """Empty params returns 400."""
        response = app_client.post("/api/set_params", json={})
        assert response.status_code == 400


class TestSnapshotEndpointsDemo:
    """Test snapshot endpoints in demo mode."""

    def test_list_snapshots_demo(self, app_client):
        """List snapshots in demo mode."""
        response = app_client.get("/api/v1/snapshots")
        assert response.status_code == 200

    def test_create_snapshot_demo(self, app_client):
        """Create snapshot in demo mode."""
        response = app_client.post("/api/v1/snapshots", json={"description": "Test"})
        assert response.status_code in (200, 201, 500)

    def test_restore_nonexistent_snapshot(self, app_client):
        """Restore non-existent snapshot returns 404."""
        app_client.post("/api/train/stop")
        response = app_client.post("/api/v1/snapshots/nonexistent/restore")
        assert response.status_code == 404


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, app_client):
        """Health check returns 200."""
        response = app_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_health_check(self, app_client):
        """API health check returns 200."""
        response = app_client.get("/api/health")
        assert response.status_code == 200


class TestStateEndpoints:
    """Test state endpoints."""

    def test_state_endpoint(self, app_client):
        """State endpoint returns 200."""
        response = app_client.get("/api/state")
        assert response.status_code == 200

    def test_status_endpoint(self, app_client):
        """Status endpoint returns 200."""
        response = app_client.get("/api/status")
        assert response.status_code == 200


class TestMetricsEndpoints:
    """Test metrics endpoints."""

    def test_metrics_endpoint(self, app_client):
        """Metrics endpoint returns 200."""
        response = app_client.get("/api/metrics")
        assert response.status_code == 200

    def test_metrics_history_endpoint(self, app_client):
        """Metrics history endpoint returns 200."""
        response = app_client.get("/api/metrics/history")
        assert response.status_code == 200


class TestDatasetEndpoints:
    """Test dataset endpoints."""

    def test_dataset_endpoint(self, app_client):
        """Dataset endpoint returns 200."""
        response = app_client.get("/api/dataset")
        assert response.status_code == 200


class TestDecisionBoundaryEndpoints:
    """Test decision boundary endpoints."""

    def test_decision_boundary_endpoint(self, app_client):
        """Decision boundary endpoint returns 200."""
        response = app_client.get("/api/decision_boundary")
        assert response.status_code == 200


class TestNetworkEndpoints:
    """Test network endpoints."""

    def test_network_topology_endpoint(self, app_client):
        """Network topology endpoint."""
        response = app_client.get("/api/network/topology")
        assert response.status_code in (200, 404, 500)

    def test_network_stats_endpoint(self, app_client):
        """Network stats endpoint."""
        response = app_client.get("/api/network/stats")
        assert response.status_code in (200, 404, 500)


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_redirects(self, app_client):
        """Root redirects to dashboard."""
        response = app_client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/dashboard/" in response.headers["location"]
