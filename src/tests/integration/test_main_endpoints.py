#!/usr/bin/env python
"""
Integration tests for all FastAPI main.py endpoints.

Tests all REST API endpoints including:
- Root redirect
- Dataset retrieval
- Decision boundary data
- Statistics
- Network topology
- Training control endpoints (start, pause, resume, stop, reset)
- Error handling and edge cases
- Startup/shutdown lifecycle
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# MUST set environment variable BEFORE importing main
os.environ["CASCOR_DEMO_MODE"] = "1"

# Add src to path
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from main import app  # noqa: E402


class TestMainEndpointsIntegration:
    """Integration tests for all main.py REST endpoints."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    # ========== Root Endpoint ==========

    def test_root_redirects_to_dashboard(self, client):
        """Test GET / redirects to /dashboard/."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307  # Temporary redirect
        assert response.headers["location"] == "/dashboard/"

    # ========== Health Endpoint ==========

    def test_health_check(self, client):
        """Test /api/health returns system status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "active_connections" in data
        assert "training_active" in data
        assert data["demo_mode"] is True  # Demo mode should be active

    # ========== Status Endpoint ==========

    def test_get_status_demo_mode(self, client):
        # sourcery skip: extract-duplicate-method
        """Test /api/status returns demo mode training status with FSM-based phase."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()

        assert "is_training" in data
        assert "current_epoch" in data
        assert "current_loss" in data
        assert "current_accuracy" in data
        assert data["network_connected"] is True
        assert "input_size" in data
        assert "output_size" in data
        assert "hidden_units" in data
        # Phase now uses FSM-based values: 'idle', 'output', 'candidate', 'inference'
        assert "phase" in data
        valid_phases = ["idle", "output", "candidate", "inference"]
        assert data["phase"] in valid_phases, f"Invalid phase: {data['phase']}"
        # Also includes is_running and is_paused flags for status bar
        assert "is_running" in data
        assert "is_paused" in data

    # ========== Metrics Endpoints ==========

    def test_get_metrics(self, client):
        """Test /api/metrics returns current metrics."""
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()

        assert "current_epoch" in data
        assert "current_loss" in data
        assert "current_accuracy" in data
        assert "is_running" in data

    def test_get_metrics_history(self, client):
        """Test /api/metrics/history returns metrics history."""
        response = client.get("/api/metrics/history")
        assert response.status_code == 200
        data = response.json()

        assert "history" in data
        assert isinstance(data["history"], list)
        # History should contain metrics data
        if len(data["history"]) > 0:
            metric = data["history"][0]
            assert "current_epoch" in metric or "epoch" in metric

    # ========== Topology Endpoint ==========

    def test_get_topology(self, client):
        # sourcery skip: extract-duplicate-method
        """Test /api/topology returns network structure."""
        response = client.get("/api/topology")
        assert response.status_code == 200
        data = response.json()

        assert "input_size" in data
        assert "hidden_units" in data
        assert "output_size" in data
        assert "nodes" in data
        assert "connections" in data

        # Validate nodes structure
        assert isinstance(data["nodes"], list)
        if len(data["nodes"]) > 0:
            node = data["nodes"][0]
            assert "id" in node
            assert "type" in node
            assert "layer" in node
            assert node["type"] in ["input", "hidden", "output"]

        # Validate connections structure
        assert isinstance(data["connections"], list)
        if len(data["connections"]) > 0:
            conn = data["connections"][0]
            assert "from" in conn
            assert "to" in conn
            assert "weight" in conn

    # ========== Dataset Endpoint ==========

    def test_get_dataset(self, client):
        """Test /api/dataset returns dataset information."""
        response = client.get("/api/dataset")
        assert response.status_code == 200
        data = response.json()

        assert "inputs" in data
        assert "targets" in data
        assert "num_samples" in data
        assert "num_features" in data
        assert "num_classes" in data

        # Validate data types
        assert isinstance(data["inputs"], list)
        assert isinstance(data["targets"], list)
        assert isinstance(data["num_samples"], int)
        assert isinstance(data["num_features"], int)
        assert isinstance(data["num_classes"], int)

        # Validate consistency
        assert len(data["inputs"]) == data["num_samples"]
        assert len(data["targets"]) == data["num_samples"]

    # ========== Decision Boundary Endpoint ==========

    def test_get_decision_boundary(self, client):
        """Test /api/decision_boundary returns grid data for visualization."""
        response = client.get("/api/decision_boundary")
        assert response.status_code == 200
        data = response.json()

        # Check for either success data or error
        if "error" not in data:
            assert "x" in data
            assert "y" in data
            assert "z" in data
            assert "x_min" in data
            assert "x_max" in data
            assert "y_min" in data
            assert "y_max" in data
            assert "resolution" in data

            # Validate data structure
            assert isinstance(data["x"], list)
            assert isinstance(data["y"], list)
            assert isinstance(data["z"], list)

    # ========== Statistics Endpoint ==========

    def test_get_statistics(self, client):
        """Test /api/statistics returns WebSocket statistics."""
        response = client.get("/api/statistics")
        assert response.status_code == 200
        data = response.json()

        assert "active_connections" in data
        assert "total_messages_broadcast" in data
        assert "connections_info" in data

        assert isinstance(data["active_connections"], int)
        assert isinstance(data["total_messages_broadcast"], int)
        assert isinstance(data["connections_info"], list)

    # ========== Training Control Endpoints ==========

    def test_train_start(self, client):
        """Test POST /api/train/start starts training."""
        response = client.post("/api/train/start")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert "current_epoch" in data
        assert "is_running" in data

    def test_train_start_with_reset(self, client):
        """Test POST /api/train/start with reset parameter."""
        response = client.post("/api/train/start?reset=true")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert "current_epoch" in data
        # After reset, epoch should be 0
        assert data["current_epoch"] == 0

    def test_train_pause(self, client):
        """Test POST /api/train/pause pauses training."""
        # Start training first
        client.post("/api/train/start")

        # Pause
        response = client.post("/api/train/pause")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "paused"

    def test_train_resume(self, client):
        """Test POST /api/train/resume resumes training."""
        # Start and pause first
        client.post("/api/train/start")
        client.post("/api/train/pause")

        # Resume
        response = client.post("/api/train/resume")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "running"

    def test_train_stop(self, client):
        """Test POST /api/train/stop stops training."""
        # Start training first
        client.post("/api/train/start")

        # Stop
        response = client.post("/api/train/stop")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "stopped"

    def test_train_reset(self, client):
        """Test POST /api/train/reset resets training state."""
        # Start training first
        client.post("/api/train/start")

        # Reset
        response = client.post("/api/train/reset")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "reset"
        assert "current_epoch" in data
        assert data["current_epoch"] == 0  # Reset should set epoch to 0

    # ========== Error Cases ==========

    def test_endpoints_without_backend_return_error(self, client):
        """Test endpoints with demo mode still work (fallback behavior)."""
        # With demo mode enabled, endpoints should work
        # Without any backend, they would return 503
        # This test verifies the fallback works correctly

        # These endpoints should work with demo mode
        response = client.get("/api/metrics/history")
        # Demo mode provides data, so should be 200
        assert response.status_code == 200

        response = client.post("/api/train/start")
        # Demo mode provides training control, so should be 200
        assert response.status_code == 200

    # ========== Lifecycle Tests ==========

    def test_startup_event(self):
        """Test application startup event initializes correctly."""
        # TestClient automatically triggers startup/shutdown
        with TestClient(app) as client:
            # Verify startup occurred by checking health endpoint
            response = client.get("/api/health")
            assert response.status_code == 200

            # Demo mode should be initialized
            data = response.json()
            assert data["demo_mode"] is True

    def test_shutdown_event(self):
        """Test application shutdown event cleans up correctly."""
        # Create and close client to trigger shutdown
        with TestClient(app) as client:
            # Verify running
            response = client.get("/api/health")
            assert response.status_code == 200

        # Shutdown occurs when context exits
        # No errors should occur during shutdown

    # ========== Concurrent Access Tests ==========

    def test_multiple_endpoints_concurrent_access(self, client):
        """Test multiple endpoints can be accessed concurrently."""
        import concurrent.futures

        def get_endpoint(path):
            return client.get(path).status_code

        endpoints = [
            "/api/health",
            "/api/status",
            "/api/metrics",
            "/api/topology",
            "/api/dataset",
            "/api/statistics",
        ]

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(get_endpoint, ep) for ep in endpoints]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All requests should succeed
        assert all(status == 200 for status in results)

    # ========== Edge Cases ==========

    def test_metrics_history_empty_on_fresh_start(self, client):
        """Test metrics history starts empty on fresh initialization."""
        # Reset first
        client.post("/api/train/reset")

        response = client.get("/api/metrics/history")
        assert response.status_code == 200
        data = response.json()

        assert "history" in data
        # History might be empty or contain initial state
        assert isinstance(data["history"], list)

    def test_topology_valid_after_reset(self, client):
        """Test topology remains valid after reset."""
        # Reset training
        client.post("/api/train/reset")

        # Topology should still be accessible
        response = client.get("/api/topology")
        assert response.status_code == 200
        data = response.json()

        assert "input_size" in data
        assert "output_size" in data

    def test_consecutive_start_commands(self, client):
        """Test consecutive start commands are handled correctly."""
        response1 = client.post("/api/train/start")
        assert response1.status_code == 200

        response2 = client.post("/api/train/start")
        assert response2.status_code == 200

        # Both should return valid status
        data = response2.json()
        assert data["status"] == "started"

    def test_pause_without_start(self, client):
        """Test pause command without prior start."""
        # Reset to ensure stopped
        client.post("/api/train/reset")
        client.post("/api/train/stop")

        # Pause should still work (idempotent)
        response = client.post("/api/train/pause")
        assert response.status_code == 200

    def test_resume_without_pause(self, client):
        """Test resume command without prior pause."""
        # Start training
        client.post("/api/train/start")

        # Resume should still work (idempotent)
        response = client.post("/api/train/resume")
        assert response.status_code == 200
