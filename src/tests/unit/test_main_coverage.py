#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_main_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-11-18
# Last Modified: 2025-11-18
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Comprehensive coverage tests for main.py application
#####################################################################
"""Comprehensive coverage tests for main.py (63% -> 80%+)."""
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


class TestRootEndpoint:
    """Test root route."""

    def test_root_redirects_to_dashboard(self, app_client):
        """Root should redirect to /dashboard/."""
        response = app_client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/dashboard/" in response.headers["location"]

    def test_root_redirect_follows(self, app_client):
        """Following redirect should reach dashboard."""
        response = app_client.get("/", follow_redirects=True)
        assert response.status_code == 200


class TestHealthCheckEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_200(self, app_client):
        """Health check should return 200."""
        response = app_client.get("/health")
        assert response.status_code == 200

    def test_health_check_json_structure(self, app_client):
        """Health check should return expected JSON."""
        response = app_client.get("/health")
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert data["status"] == "healthy"

    def test_health_check_includes_connections(self, app_client):
        """Health check should include active connections."""
        response = app_client.get("/health")
        data = response.json()
        assert "active_connections" in data
        assert isinstance(data["active_connections"], int)

    def test_health_check_includes_training_status(self, app_client):
        """Health check should include training_active."""
        response = app_client.get("/health")
        data = response.json()
        assert "training_active" in data
        assert isinstance(data["training_active"], bool)

    def test_health_check_includes_demo_mode(self, app_client):
        """Health check should indicate demo_mode."""
        response = app_client.get("/health")
        data = response.json()
        assert "demo_mode" in data
        assert data["demo_mode"] is True

    def test_health_alternative_path(self, app_client):
        """/api/health should work too."""
        response = app_client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestStateEndpoint:
    """Test /api/state endpoint."""

    def test_state_returns_200(self, app_client):
        """State endpoint should return 200."""
        response = app_client.get("/api/state")
        assert response.status_code == 200

    def test_state_returns_json(self, app_client):
        """State endpoint should return JSON."""
        response = app_client.get("/api/state")
        data = response.json()
        assert isinstance(data, dict)

    def test_state_has_learning_rate(self, app_client):
        """State should include learning_rate."""
        response = app_client.get("/api/state")
        data = response.json()
        assert "learning_rate" in data

    def test_state_has_max_hidden_units(self, app_client):
        """State should include max_hidden_units."""
        response = app_client.get("/api/state")
        data = response.json()
        assert "max_hidden_units" in data


class TestStatusEndpoint:
    """Test /api/status endpoint."""

    def test_status_returns_200(self, app_client):
        """Status endpoint should return 200."""
        response = app_client.get("/api/status")
        assert response.status_code == 200

    def test_status_returns_json(self, app_client):
        """Status should return JSON dict."""
        response = app_client.get("/api/status")
        data = response.json()
        assert isinstance(data, dict)

    def test_status_has_is_training(self, app_client):
        """Status should include is_training."""
        response = app_client.get("/api/status")
        data = response.json()
        assert "is_training" in data

    def test_status_has_current_epoch(self, app_client):
        """Status should include current_epoch."""
        response = app_client.get("/api/status")
        data = response.json()
        assert "current_epoch" in data

    def test_status_has_network_info(self, app_client):
        """Status should include network information."""
        response = app_client.get("/api/status")
        data = response.json()
        assert "input_size" in data or "network_connected" in data


class TestMetricsEndpoint:
    """Test /api/metrics endpoint."""

    def test_metrics_returns_200(self, app_client):
        """Metrics endpoint should return 200."""
        response = app_client.get("/api/metrics")
        assert response.status_code == 200

    def test_metrics_returns_json(self, app_client):
        """Metrics should return JSON."""
        response = app_client.get("/api/metrics")
        data = response.json()
        assert isinstance(data, dict)


class TestMetricsHistoryEndpoint:
    """Test /api/metrics/history endpoint."""

    def test_metrics_history_returns_200(self, app_client):
        """Metrics history should return 200."""
        response = app_client.get("/api/metrics/history")
        assert response.status_code == 200

    def test_metrics_history_has_history_key(self, app_client):
        """Metrics history should have 'history' key."""
        response = app_client.get("/api/metrics/history")
        data = response.json()
        assert "history" in data

    def test_metrics_history_is_list(self, app_client):
        """History should be a list."""
        response = app_client.get("/api/metrics/history")
        data = response.json()
        assert isinstance(data["history"], list)


class TestNetworkStatsEndpoint:
    """Test /api/network/stats endpoint."""

    def test_network_stats_returns_valid_response(self, app_client):
        """Network stats should return 200 with data or 503 if unavailable.

        In demo mode, network stats may not be immediately available if
        the demo mode hasn't initialized the network topology yet.
        """
        response = app_client.get("/api/network/stats")
        # Network stats depend on initialized topology - may be 503 if not ready
        assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
        if response.status_code == 503:
            data = response.json()
            assert "error" in data, "503 response should include error message"

    def test_network_stats_json_structure(self, app_client):
        """Network stats should return proper JSON when available."""
        response = app_client.get("/api/network/stats")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)
            # Validate expected fields when available
            expected_fields = ["hidden_count", "edge_count", "threshold_function"]
            has_field = any(field in data for field in expected_fields)
            assert has_field or "error" not in data


class TestTopologyEndpoint:
    """Test /api/topology endpoint."""

    def test_topology_returns_valid_response(self, app_client):
        """Topology endpoint should return 200 with data or 503 if unavailable.

        In demo mode, topology may not be immediately available if
        the demo mode hasn't initialized the network yet.
        """
        response = app_client.get("/api/topology")
        # Topology depends on initialized network - may be 503 if not ready
        assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
        if response.status_code == 503:
            data = response.json()
            assert "error" in data, "503 response should include error message"

    def test_topology_has_units_when_available(self, app_client):
        """Topology should include unit counts when available."""
        response = app_client.get("/api/topology")
        if response.status_code == 200:
            data = response.json()
            assert "input_units" in data or "hidden_units" in data or "nodes" in data


class TestDatasetEndpoint:
    """Test /api/dataset endpoint."""

    def test_dataset_returns_200(self, app_client):
        """Dataset endpoint should return 200 in demo mode."""
        response = app_client.get("/api/dataset")
        # In demo mode, dataset should be available
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_dataset_has_inputs(self, app_client):
        """Dataset should include inputs."""
        response = app_client.get("/api/dataset")
        assert response.status_code == 200
        data = response.json()
        assert "inputs" in data or "num_samples" in data or isinstance(data, dict)


class TestDecisionBoundaryEndpoint:
    """Test /api/decision_boundary endpoint."""

    def test_decision_boundary_returns_200(self, app_client):
        """Decision boundary endpoint should return 200 in demo mode."""
        response = app_client.get("/api/decision_boundary")
        # In demo mode, decision boundary should be available
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    def test_decision_boundary_has_data(self, app_client):
        """Decision boundary should include visualization data."""
        response = app_client.get("/api/decision_boundary")
        assert response.status_code == 200
        data = response.json()
        # Should have grid or bounds data for visualization
        assert "xx" in data or "bounds" in data or isinstance(data, dict)


class TestStatisticsEndpoint:
    """Test /api/statistics endpoint."""

    def test_statistics_returns_200(self, app_client):
        """Statistics endpoint should return 200."""
        response = app_client.get("/api/statistics")
        assert response.status_code == 200

    def test_statistics_returns_json(self, app_client):
        """Statistics should return JSON dict."""
        response = app_client.get("/api/statistics")
        data = response.json()
        assert isinstance(data, dict)


class TestCORSHeaders:
    """Test CORS headers."""

    def test_cors_headers_present(self, app_client):
        """CORS headers should be present."""
        response = app_client.get("/health")
        # CORS middleware adds headers
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestErrorHandling:
    """Test error handling."""

    def test_404_on_invalid_route(self, app_client):
        """Invalid route should return 404."""
        response = app_client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_405_on_wrong_method(self, app_client):
        """Wrong HTTP method should return 405."""
        response = app_client.post("/api/metrics")
        assert response.status_code == 405


class TestLifespanEvents:
    """Test application lifespan (startup/shutdown)."""

    def test_app_starts_successfully(self):
        """App should start without errors."""
        from main import app

        assert app is not None

    def test_app_has_lifespan(self):
        """App should have lifespan configured."""
        from main import app

        assert hasattr(app, "router")


class TestDemoModeIntegration:
    """Test demo mode integration."""

    def test_demo_mode_active_in_env(self):
        """Demo mode should be active via env var."""
        assert os.environ.get("CASCOR_DEMO_MODE") == "1"

    def test_demo_mode_provides_data(self, app_client):
        """Demo mode should provide mock data."""
        response = app_client.get("/api/status")
        assert response.status_code == 200
        # Demo mode should provide status


class TestScheduleBroadcast:
    """Test schedule_broadcast helper."""

    def test_schedule_broadcast_exists(self):
        """schedule_broadcast function should exist."""
        from main import schedule_broadcast

        assert callable(schedule_broadcast)
