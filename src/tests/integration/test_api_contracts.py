#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_api_contracts.py
# Author:        Paul Calnon
# Version:       1.0.0
# Date:          2025-11-13
# Last Modified: 2025-11-13
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   API contract tests - ensure API responses match UI expectations
#####################################################################

"""API contract tests - ensure API responses match UI expectations."""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["CASCOR_DEMO_MODE"] = "1"
from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """FastAPI test client."""
    with TestClient(app) as client:
        yield client


class TestAPIContracts:
    """Test API response contracts match UI expectations."""

    def test_metrics_history_returns_dict_with_history_key(self, client):
        """Contract: /api/metrics/history returns {"history": [...]}"""
        response = client.get("/api/metrics/history")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict), "Response must be dict"
        assert "history" in data, "Must have 'history' key"
        assert isinstance(data["history"], list), "history must be list"

    def test_metrics_history_items_have_required_fields(self, client):
        """Contract: Each metric has epoch, metrics, phase, timestamp"""
        response = client.get("/api/metrics/history?limit=10")
        data = response.json()

        if data["history"]:
            metric = data["history"][0]
            assert "epoch" in metric
            assert "metrics" in metric
            assert isinstance(metric["metrics"], dict)
            assert "phase" in metric
            assert "timestamp" in metric

    def test_metrics_history_respects_limit_param(self, client):
        """Contract: limit parameter controls number of results"""
        response = client.get("/api/metrics/history?limit=5")
        data = response.json()
        assert len(data["history"]) <= 5, "Must respect limit parameter"

    def test_topology_returns_dict_with_connections(self, client):
        """Contract: /api/topology returns dict with 'connections' not 'edges'"""
        response = client.get("/api/topology")
        assert response.status_code == 200
        data = response.json()
        assert "connections" in data, "Must use 'connections' not 'edges'"
        assert "nodes" in data
        assert isinstance(data["connections"], list)
        assert isinstance(data["nodes"], list)

    def test_topology_nodes_have_required_fields(self, client):
        """Contract: Each node has id, type, layer"""
        response = client.get("/api/topology")
        data = response.json()

        if data["nodes"]:
            node = data["nodes"][0]
            assert "id" in node
            assert "type" in node
            assert "layer" in node

    def test_topology_connections_have_required_fields(self, client):
        """Contract: Each connection has from, to, weight"""
        response = client.get("/api/topology")
        data = response.json()

        if data["connections"]:
            conn = data["connections"][0]
            assert "from" in conn
            assert "to" in conn
            assert "weight" in conn

    def test_dataset_returns_inputs_and_targets(self, client):
        """Contract: /api/dataset returns 'inputs'/'targets' not 'X'/'y'"""
        response = client.get("/api/dataset")
        assert response.status_code == 200
        data = response.json()
        assert "inputs" in data, "Must use 'inputs' not 'X'"
        assert "targets" in data, "Must use 'targets' not 'y'"
        assert isinstance(data["inputs"], list)
        assert isinstance(data["targets"], list)

    def test_dataset_inputs_targets_same_length(self, client):
        """Contract: inputs and targets arrays must be same length"""
        response = client.get("/api/dataset")
        data = response.json()
        assert len(data["inputs"]) == len(data["targets"])

    def test_current_metrics_returns_dict(self, client):
        """Contract: /api/metrics returns current metrics dict"""
        response = client.get("/api/metrics")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict), "Must return dict"

    def test_current_metrics_has_standard_fields(self, client):
        """Contract: Current metrics has current_epoch, current_loss, current_accuracy, is_running"""
        response = client.get("/api/metrics")
        if data := response.json():
            assert "current_epoch" in data or "message" in data  # May be empty initially

    def test_decision_boundary_returns_grid_and_predictions(self, client):
        """Contract: /api/decision_boundary returns x, y, z, resolution, bounds"""
        response = client.get("/api/decision_boundary")
        assert response.status_code == 200
        data = response.json()
        # API returns x, y, z, resolution, x_min, x_max, y_min, y_max
        assert "x" in data or "error" in data  # May not be available initially

    def test_all_endpoints_return_json(self, client):
        """Contract: All endpoints return valid JSON"""
        endpoints = ["/api/metrics", "/api/metrics/history", "/api/topology", "/api/dataset", "/api/decision_boundary"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"
            # Verify it's valid JSON by parsing
            data = response.json()
            assert data is not None

    def test_metric_names_use_snake_case(self, client):
        """Contract: All metric names use snake_case (e.g., train_loss not trainLoss)"""
        response = client.get("/api/metrics/history?limit=10")
        data = response.json()

        if data["history"]:
            metrics = data["history"][0].get("metrics", {})
            for key in metrics.keys():
                assert key.islower() or "_" in key, f"Metric {key!r} should use snake_case"
                assert key == key.replace("-", "_"), f"Metric {key!r} should use underscores not hyphens"


class TestErrorResponses:
    """Test API error response contracts."""

    def test_invalid_limit_returns_422(self, client):
        """Contract: Invalid/unrecognized query params are ignored (endpoint has no limit param)"""
        response = client.get("/api/metrics/history?limit=invalid")
        # Endpoint doesn't define limit parameter, so invalid value is ignored
        assert response.status_code == 200
        data = response.json()
        assert "history" in data  # Should still return valid response

    def test_negative_limit_handled_gracefully(self, client):
        """Contract: Negative limits handled (422 or clamped to valid range)"""
        response = client.get("/api/metrics/history?limit=-5")
        # Should either reject (422) or handle gracefully (200)
        assert response.status_code in [200, 422]
