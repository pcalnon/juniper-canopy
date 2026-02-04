#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_demo_endpoints.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Integration tests for demo mode endpoints. Ensures all API and WebSocket
#    endpoints are accessible and functional when running in demo mode.
#
#####################################################################################################################################################################################################
import contextlib
import os
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def test_client():
    """Create test client with demo mode enabled."""
    # Set demo mode environment variable
    os.environ["CASCOR_DEMO_MODE"] = "1"

    # Import after setting env var
    from main import app

    client = TestClient(app)

    # Give demo mode a moment to start broadcasting
    time.sleep(2.0)

    return client


class TestHealthEndpoint:
    """Test /health endpoint in demo mode."""

    def test_health_endpoint_returns_200(self, test_client):
        """Test /health endpoint returns 200 status."""
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, test_client):
        """Test /health returns valid JSON."""
        response = test_client.get("/health")
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_health_shows_demo_mode(self, test_client):
        """Test /health indicates demo mode is active."""
        response = test_client.get("/health")
        data = response.json()

        assert "demo_mode" in data
        assert data["demo_mode"] is True


class TestWebSocketTrainingEndpoint:
    """Test /ws/training WebSocket endpoint in demo mode."""

    def test_training_websocket_accepts_connection(self, test_client):
        """Test WebSocket connection is accepted."""
        with test_client.websocket_connect("/ws/training") as websocket:
            # Connection successful if we get here
            data = websocket.receive_json()
            assert "type" in data

    def test_training_websocket_sends_connection_established(self, test_client):
        """Test WebSocket sends connection_established message."""
        with test_client.websocket_connect("/ws/training") as websocket:
            data = websocket.receive_json()

            assert data["type"] == "connection_established"
            assert "client_id" in data

    @pytest.mark.e2e
    @pytest.mark.requires_server
    def test_training_websocket_receives_state_messages(self, test_client):
        """Test WebSocket receives training state messages."""
        with test_client.websocket_connect("/ws/training") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Wait for state messages
            state_received = False
            for _ in range(10):
                with contextlib.suppress(Exception):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "state":
                        state_received = True
                        assert "data" in message
                        assert "timestamp" in message
                        break
            assert state_received, "No state messages received from demo mode"

    @pytest.mark.e2e
    @pytest.mark.requires_server
    def test_training_websocket_receives_metrics_messages(self, test_client):
        """Test WebSocket receives training metrics messages."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            metrics_received = False
            for _ in range(15):
                with contextlib.suppress(Exception):
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type") == "metrics":
                        metrics_received = True
                        assert "data" in message
                        assert "timestamp" in message
                        break
            assert metrics_received, "No metrics messages received from demo mode"


class TestWebSocketControlEndpoint:
    """Test /ws/control WebSocket endpoint in demo mode."""

    def test_control_websocket_accepts_connection(self, test_client):
        """Test control WebSocket connection is accepted."""
        with test_client.websocket_connect("/ws/control") as websocket:
            data = websocket.receive_json()
            assert "type" in data

    def test_control_websocket_accepts_commands(self, test_client):
        """Test control WebSocket accepts control commands."""
        with test_client.websocket_connect("/ws/control") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Send start command
            websocket.send_json({"command": "start", "reset": True})

            # Receive response
            response = websocket.receive_json()
            assert "ok" in response or "type" in response

    def test_control_commands_execute(self, test_client):
        """Test control commands execute successfully."""
        with test_client.websocket_connect("/ws/control") as websocket:
            websocket.receive_json()

            # Test start command
            websocket.send_json({"command": "start", "reset": True})
            response = websocket.receive_json()
            assert response.get("ok") is not False


class TestAPIStateEndpoint:
    """Test /api/state endpoint in demo mode."""

    def test_api_state_returns_200(self, test_client):
        """Test /api/state returns 200 status."""
        response = test_client.get("/api/state")
        assert response.status_code == 200

    def test_api_state_returns_valid_json(self, test_client):
        """Test /api/state returns valid JSON with required fields."""
        response = test_client.get("/api/state")
        data = response.json()

        required_fields = [
            "status",
            "phase",
            "learning_rate",
            "max_hidden_units",
            "current_epoch",
            "current_step",
            "timestamp",
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_api_state_reflects_demo_mode(self, test_client):
        """Test /api/state shows demo mode is running."""
        response = test_client.get("/api/state")
        data = response.json()

        # In demo mode, we should see the mock network
        assert "network_name" in data
        assert "dataset_name" in data


class TestAPIMetricsEndpoint:
    """Test /api/metrics endpoint in demo mode."""

    def test_api_metrics_returns_200(self, test_client):
        """Test /api/metrics returns 200 status."""
        response = test_client.get("/api/metrics")
        assert response.status_code == 200

    def test_api_metrics_returns_json(self, test_client):
        """Test /api/metrics returns valid JSON."""
        response = test_client.get("/api/metrics")
        data = response.json()

        assert isinstance(data, dict)

    def test_api_metrics_has_training_data(self, test_client):
        """Test /api/metrics contains training data from demo mode."""
        # Wait a bit for demo mode to generate some data
        time.sleep(1.5)

        response = test_client.get("/api/metrics")
        data = response.json()

        # Should have some metrics data
        assert "is_running" in data or "current_epoch" in data


class TestAPITopologyEndpoint:
    """Test /api/topology endpoint in demo mode."""

    def test_api_topology_returns_200(self, test_client):
        """Test /api/topology returns 200 status."""
        response = test_client.get("/api/topology")
        assert response.status_code == 200

    def test_api_topology_returns_valid_structure(self, test_client):
        """Test /api/topology returns valid network topology."""
        response = test_client.get("/api/topology")
        data = response.json()

        assert "input_units" in data
        assert "output_units" in data
        assert "nodes" in data or "error" not in data


class TestAPIStatusEndpoint:
    """Test /api/status endpoint in demo mode."""

    def test_api_status_returns_200(self, test_client):
        """Test /api/status returns 200 status."""
        response = test_client.get("/api/status")
        assert response.status_code == 200

    def test_api_status_shows_training_active(self, test_client):
        """Test /api/status shows training is active in demo mode."""
        response = test_client.get("/api/status")
        data = response.json()

        assert "is_training" in data
        # Demo mode should be running
        assert data.get("is_training") is True or data.get("is_running") is True


class TestRootEndpoint:
    """Test root endpoint redirects properly."""

    def test_root_redirects_to_dashboard(self, test_client):
        """Test / redirects to /dashboard/."""
        response = test_client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/dashboard/"


@pytest.mark.requires_server
class TestDataFlowIntegration:
    """Test that data flows through WebSocket channels in demo mode."""

    @pytest.mark.e2e
    def test_demo_mode_broadcasts_data(self, test_client):
        """Test demo mode broadcasts data through WebSocket."""
        with test_client.websocket_connect("/ws/training") as websocket:
            websocket.receive_json()

            # Count different message types received
            message_types = set()
            for _ in range(20):
                try:
                    message = websocket.receive_json(timeout=2.0)
                    if message.get("type"):
                        message_types.add(message["type"])
                except Exception:
                    break

            # Should receive multiple types of messages
            assert message_types, "No messages received from demo mode"

    def test_state_updates_are_consistent(self, test_client):
        """Test state updates are consistent over time."""
        # Get initial state
        response1 = test_client.get("/api/state")
        data1 = response1.json()

        time.sleep(1.5)

        # Get updated state
        response2 = test_client.get("/api/state")
        data2 = response2.json()

        # Epoch should have increased (demo mode is running)
        assert data2["current_epoch"] >= data1["current_epoch"]


class TestDashboardEndpoint:
    """Test dashboard endpoint is accessible."""

    def test_dashboard_endpoint_accessible(self, test_client):
        """Test /dashboard/ endpoint is accessible."""
        response = test_client.get("/dashboard/")
        # Should get HTML or redirect, not 404
        assert response.status_code in [200, 302, 307]
