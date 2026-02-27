#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_api_state_endpoint.py
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
#    Integration tests for GET /api/state endpoint.
#
#####################################################################################################################################################################################################
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from main import app

    return TestClient(app)


class TestStateEndpoint:
    """Test GET /api/state endpoint."""

    def test_state_endpoint_exists(self, test_client):
        """Test /api/state endpoint is accessible."""
        response = test_client.get("/api/state")
        assert response.status_code == 200

    def test_state_endpoint_returns_json(self, test_client):
        """Test /api/state returns JSON."""
        response = test_client.get("/api/state")
        assert response.headers["content-type"] == "application/json"

    def test_state_endpoint_has_required_fields(self, test_client):
        """Test /api/state returns all required fields."""
        response = test_client.get("/api/state")
        data = response.json()

        required_fields = [
            "status",
            "phase",
            "learning_rate",
            "max_hidden_units",
            "current_epoch",
            "current_step",
            "network_name",
            "dataset_name",
            "threshold_function",
            "optimizer_name",
            "timestamp",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_state_endpoint_field_types(self, test_client):
        """Test /api/state returns correct field types."""
        response = test_client.get("/api/state")
        data = response.json()

        assert isinstance(data["status"], str)
        assert isinstance(data["phase"], str)
        assert isinstance(data["learning_rate"], (int, float))
        assert isinstance(data["max_hidden_units"], int)
        assert isinstance(data["current_epoch"], int)
        assert isinstance(data["current_step"], int)
        assert isinstance(data["network_name"], str)
        assert isinstance(data["dataset_name"], str)
        assert isinstance(data["threshold_function"], str)
        assert isinstance(data["optimizer_name"], str)
        assert isinstance(data["timestamp"], (int, float))

    def test_state_endpoint_default_values(self, test_client):
        """Test /api/state returns expected default values."""
        response = test_client.get("/api/state")
        data = response.json()

        # After initialization, state should have default values
        # Note: In demo mode, some values may be different
        # Status and phase are case-insensitive
        valid_statuses = ["stopped", "started", "paused", "running"]
        valid_phases = ["idle", "output", "candidate", "inference"]
        assert data["status"].lower() in valid_statuses, f"Invalid status: {data['status']}"
        assert data["phase"].lower() in valid_phases, f"Invalid phase: {data['phase']}"
        assert data["learning_rate"] >= 0.0
        assert data["max_hidden_units"] >= 0
        assert data["current_epoch"] >= 0
        assert data["current_step"] >= 0

    def test_state_endpoint_timestamp_is_recent(self, test_client):
        """Test /api/state timestamp is recent."""
        import time

        current_time = time.time()

        response = test_client.get("/api/state")
        data = response.json()

        # Timestamp should be within a reasonable window (allows for CI/coverage overhead)
        assert abs(data["timestamp"] - current_time) < 30.0

    def test_state_endpoint_multiple_calls(self, test_client):
        """Test /api/state can be called multiple times."""
        for _ in range(5):
            response = test_client.get("/api/state")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data


class TestStateEndpointWithDemoMode:
    """Test /api/state endpoint with demo mode active."""

    def test_state_reflects_demo_mode_when_active(self, test_client):
        """Test /api/state reflects demo mode state when active."""
        # Note: This requires demo mode to be running
        # The test may need to be skipped if demo mode is not active
        response = test_client.get("/api/state")
        data = response.json()

        # Demo mode should populate some fields
        if data["network_name"] == "MockCascorNetwork":
            # Demo mode is active
            assert data["dataset_name"] == "Spiral2D"
            assert data["threshold_function"] == "tanh"
            assert data["optimizer_name"] == "SGD"

    def test_state_consistency_across_calls(self, test_client):
        """Test /api/state returns consistent data across multiple calls."""
        response1 = test_client.get("/api/state")
        data1 = response1.json()

        response2 = test_client.get("/api/state")
        data2 = response2.json()

        # Most fields should be consistent (timestamp may differ slightly)
        assert data1["status"] == data2["status"]
        assert data1["phase"] == data2["phase"]
        assert data1["network_name"] == data2["network_name"]
        assert data1["dataset_name"] == data2["dataset_name"]
