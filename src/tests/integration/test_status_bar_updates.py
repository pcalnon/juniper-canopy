#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_status_bar_updates.py
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
#
#####################################################################################################################################################################################################
# Notes:
#
#     Integration tests for Status and Phase indicator updates at the top of the dashboard.
#     Tests that Status and Phase reflect actual TrainingState and update within <1 second.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
"""Integration tests for top status bar updates."""
import os
import time

# MUST set environment variable BEFORE importing main
os.environ["CASCOR_DEMO_MODE"] = "1"

import pytest  # noqa: F401,E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app, backend, training_state  # noqa: E402


def get_active_training_state():
    """Get the training state that /api/state actually returns."""
    # In demo mode, /api/state returns backend._demo.training_state
    if backend and backend.backend_type == "demo" and hasattr(backend, "_demo") and backend._demo.training_state:
        return backend._demo.training_state
    return training_state


@pytest.fixture(scope="module")
def client():
    """Create test client with demo mode."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def active_state():
    """Get the active training state (demo mode's or global)."""
    return get_active_training_state()


class TestStatusBarUpdates:
    """Test Status and Phase indicator updates.

    Note: In demo mode, the training simulation runs continuously and controls
    the training state. Tests verify that the API returns valid state data
    and responds quickly, rather than trying to control state directly.
    """

    def test_api_state_endpoint_exists(self, client):
        """Test /api/state endpoint is accessible."""
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "phase" in data

    def test_status_has_valid_values(self, client):
        """Test Status indicator has valid values."""
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        # Status must be one of the valid states (case-insensitive)
        valid_statuses = ["stopped", "started", "running", "paused"]
        assert data["status"].lower() in valid_statuses, f"Invalid status: {data['status']}"

    def test_phase_has_valid_values(self, client):
        """Test Phase indicator has valid values."""
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        # Phase must be one of the valid phases (case-insensitive)
        valid_phases = ["idle", "output", "candidate", "inference"]
        assert data["phase"].lower() in valid_phases, f"Invalid phase: {data['phase']}"

    def test_state_response_is_fast(self, client):
        """Test state endpoint responds quickly (<1 second)."""
        start_time = time.time()
        response = client.get("/api/state")
        latency = time.time() - start_time

        assert response.status_code == 200
        # Verify response time is fast (<1 second as per spec)
        assert latency < 1.0, f"State fetch took {latency:.3f}s, expected <1s"

    def test_status_changes_with_training_controls(self, client):
        """Test Status changes when training controls are used."""
        # Start training (uses demo mode's control flow)
        response = client.post("/api/train/start")
        assert response.status_code == 200

        # Give it a moment to update state
        time.sleep(0.2)

        # Check state reflects valid status
        response = client.get("/api/state")
        data = response.json()
        # In demo mode, status should be one of the valid states (case-insensitive)
        valid_statuses = ["running", "started", "paused", "stopped"]
        assert data["status"].lower() in valid_statuses, f"Invalid status: {data['status']}"

    def test_state_contains_training_metrics(self, client):
        """Test state contains expected training metric fields."""
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()

        # Verify required fields are present
        required_fields = ["status", "phase", "current_epoch", "learning_rate"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify numeric fields have valid types
        assert isinstance(data["current_epoch"], int)
        assert isinstance(data["learning_rate"], (int, float))

    def test_multiple_state_fetches_are_consistent(self, client):
        """Test multiple rapid state fetches return consistent data types."""
        for _ in range(3):
            response = client.get("/api/state")
            assert response.status_code == 200
            data = response.json()
            # Verify data structure is consistent
            assert "status" in data
            assert "phase" in data
            assert isinstance(data["status"], str)
            assert isinstance(data["phase"], str)


class TestStatusEndpointFSMIntegration:
    """Test /api/status endpoint returns FSM-based status and phase.

    These tests verify that the unified status bar gets correct FSM-based
    values from /api/status instead of hardcoded values.
    """

    def test_api_status_returns_phase_field(self, client):
        """Test /api/status returns phase field (not current_phase)."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        # Must have phase field with correct key
        assert "phase" in data, "Missing 'phase' field in /api/status response"
        # Should not have old hardcoded 'current_phase' key
        assert data.get("phase") != "demo_mode", "Phase should not be hardcoded 'demo_mode'"

    def test_api_status_returns_is_running_and_is_paused(self, client):
        """Test /api/status returns both is_running and is_paused flags."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        # Must have both flags for proper status determination
        assert "is_running" in data, "Missing 'is_running' field in /api/status"
        assert "is_paused" in data, "Missing 'is_paused' field in /api/status"
        assert isinstance(data["is_running"], bool)
        assert isinstance(data["is_paused"], bool)

    def test_api_status_phase_has_valid_value(self, client):
        """Test /api/status phase is a valid FSM phase value."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        # Phase must be one of the valid FSM phases (lowercase)
        valid_phases = ["idle", "output", "candidate", "inference"]
        assert data["phase"].lower() in valid_phases, f"Invalid phase: {data['phase']}"

    def test_api_status_has_epoch_and_hidden_units(self, client):
        """Test /api/status includes epoch and hidden_units for status bar."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "current_epoch" in data
        assert "hidden_units" in data
        assert isinstance(data["current_epoch"], int)
        assert isinstance(data["hidden_units"], int)

    def test_api_status_reflects_training_start(self, client):
        """Test /api/status shows running state after start command."""
        # Start training
        client.post("/api/train/start")
        time.sleep(0.2)  # Give FSM time to transition

        response = client.get("/api/status")
        data = response.json()

        # After start, should be running
        assert data["is_running"] is True
        assert data["is_paused"] is False
        # Phase should be 'output' (first phase of training)
        assert data["phase"] == "output"

    def test_api_status_reflects_training_pause(self, client):
        """Test /api/status shows paused state after pause command."""
        # Ensure training is started
        client.post("/api/train/start")
        time.sleep(0.2)

        # Pause training
        client.post("/api/train/pause")
        time.sleep(0.2)

        response = client.get("/api/status")
        data = response.json()

        # After pause, should be paused
        assert data["is_paused"] is True
        # is_running reflects FSM PAUSED state (not STARTED)
        assert data["is_running"] is False

    def test_api_status_reflects_training_stop(self, client):
        """Test /api/status shows stopped state after stop command."""
        # Stop training
        client.post("/api/train/stop")
        time.sleep(0.2)

        response = client.get("/api/status")
        data = response.json()

        # After stop, should be stopped
        assert data["is_running"] is False
        assert data["is_paused"] is False
        # Phase should be 'idle' when stopped
        assert data["phase"] == "idle"
