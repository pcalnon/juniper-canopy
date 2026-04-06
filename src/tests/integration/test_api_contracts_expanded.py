"""Expanded API contract tests.

Covers health endpoints (v1), training status/state, statistics,
network stats, training control, non-existent endpoints, and
response header contracts not in test_api_contracts.py.
"""

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"
from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """FastAPI test client."""
    with TestClient(app) as client:
        yield client


class TestHealthEndpointContracts:
    """Contract tests for v1 health endpoints."""

    def test_liveness_returns_alive(self, client):
        """Contract: /v1/health/live returns {"status": "alive"}."""
        resp = client.get("/v1/health/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"

    def test_health_returns_required_fields(self, client):
        """Contract: /v1/health returns status, timestamp, version, demo_mode."""
        resp = client.get("/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "demo_mode" in data
        assert "active_connections" in data
        assert "training_active" in data

    def test_health_timestamp_is_recent(self, client):
        """Contract: timestamp is a recent Unix timestamp."""
        resp = client.get("/v1/health")
        data = resp.json()
        now = time.time()
        assert abs(now - data["timestamp"]) < 10, "Timestamp should be within 10 seconds of now"

    def test_health_version_is_string(self, client):
        """Contract: version field is a non-empty string."""
        resp = client.get("/v1/health")
        data = resp.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_readiness_returns_structured_response(self, client):
        """Contract: /v1/health/ready returns status, version, service, dependencies, details."""
        resp = client.get("/v1/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "service" in data
        assert data["service"] == "juniper-canopy"
        assert "dependencies" in data
        assert "details" in data

    def test_readiness_dependencies_structure(self, client):
        """Contract: dependencies has juniper_data and juniper_cascor entries."""
        resp = client.get("/v1/health/ready")
        data = resp.json()
        deps = data["dependencies"]
        assert "juniper_data" in deps
        assert "juniper_cascor" in deps
        for dep in deps.values():
            assert "name" in dep
            assert "status" in dep

    def test_readiness_details_structure(self, client):
        """Contract: details has mode, active_connections, training_active."""
        resp = client.get("/v1/health/ready")
        data = resp.json()
        details = data["details"]
        assert "mode" in details
        assert "active_connections" in details
        assert "training_active" in details

    def test_deprecated_health_endpoint(self, client):
        """Contract: /api/health still works (deprecated)."""
        resp = client.get("/api/health")
        assert resp.status_code == 200


class TestStatusAndStateContracts:
    """Contract tests for training status and state endpoints."""

    def test_status_returns_dict(self, client):
        """Contract: /api/status returns a dict."""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_state_returns_dict(self, client):
        """Contract: /api/state returns a dict."""
        resp = client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_statistics_returns_dict(self, client):
        """Contract: /api/statistics returns WebSocket statistics."""
        resp = client.get("/api/statistics")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestNetworkEndpointContracts:
    """Contract tests for network-related endpoints."""

    def test_network_stats_returns_dict(self, client):
        """Contract: /api/network/stats returns a dict."""
        resp = client.get("/api/network/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_topology_raw_returns_dict(self, client):
        """Contract: /api/topology/raw returns a dict."""
        resp = client.get("/api/topology/raw")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestTrainingControlContracts:
    """Contract tests for training control endpoints."""

    def test_train_status_returns_dict(self, client):
        """Contract: /api/train/status returns training status."""
        resp = client.get("/api/train/status")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_train_start_returns_response(self, client):
        """Contract: /api/train/start returns a response dict."""
        resp = client.post("/api/train/start")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_train_stop_returns_response(self, client):
        """Contract: /api/train/stop returns a response dict."""
        resp = client.post("/api/train/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_train_pause_returns_response(self, client):
        """Contract: /api/train/pause returns a response dict."""
        resp = client.post("/api/train/pause")
        # May return 200 or 409 (can't pause if not training)
        assert resp.status_code in [200, 409]

    def test_train_resume_returns_response(self, client):
        """Contract: /api/train/resume returns a response dict."""
        resp = client.post("/api/train/resume")
        # May return 200 or 409 (can't resume if not paused)
        assert resp.status_code in [200, 409]

    def test_train_reset_returns_response(self, client):
        """Contract: /api/train/reset returns a response dict."""
        resp = client.post("/api/train/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestDatasetEndpointContracts:
    """Contract tests for dataset endpoints."""

    def test_dataset_generators_returns_list(self, client):
        """Contract: /api/dataset/generators returns list of available generators."""
        resp = client.get("/api/dataset/generators")
        assert resp.status_code == 200
        data = resp.json()
        # Should be a list or dict with generators info
        assert data is not None

    def test_decision_boundary_resolution_param(self, client):
        """Contract: /api/decision_boundary accepts resolution parameter."""
        resp = client.get("/api/decision_boundary?resolution=50")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestNonExistentEndpoints:
    """Test 404 behavior for non-existent endpoints."""

    def test_unknown_api_path_returns_404(self, client):
        """Non-existent API path returns 404."""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_unknown_v1_path_returns_404(self, client):
        """Non-existent v1 path returns 404."""
        resp = client.get("/v1/nonexistent")
        assert resp.status_code == 404

    def test_wrong_method_returns_405(self, client):
        """Wrong HTTP method on existing endpoint returns 405."""
        resp = client.delete("/api/status")
        assert resp.status_code == 405


class TestResponseHeaders:
    """Tests for response header contracts."""

    def test_json_content_type_on_api_endpoints(self, client):
        """All API endpoints return application/json content type."""
        endpoints = ["/v1/health", "/v1/health/live", "/api/status", "/api/metrics"]
        for endpoint in endpoints:
            resp = client.get(endpoint)
            assert "application/json" in resp.headers["content-type"], f"{endpoint} should return JSON"

    def test_security_headers_present(self, client):
        """Security headers are present on API responses."""
        resp = client.get("/v1/health")
        assert "x-content-type-options" in resp.headers
        assert "x-frame-options" in resp.headers

    def test_request_id_header_present(self, client):
        """X-Request-ID is included in responses."""
        resp = client.get("/v1/health")
        assert "x-request-id" in resp.headers

    def test_provided_request_id_echoed(self, client):
        """Provided X-Request-ID is echoed back in response."""
        resp = client.get("/v1/health", headers={"X-Request-ID": "test-id-12345"})
        assert resp.headers.get("x-request-id") == "test-id-12345"


class TestParameterValidation:
    """Extended parameter validation contract tests."""

    def test_metrics_history_zero_limit(self, client):
        """Contract: limit=0 returns all history (up to internal max)."""
        resp = client.get("/api/metrics/history?limit=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data

    def test_metrics_history_large_limit(self, client):
        """Contract: Very large limit does not error."""
        resp = client.get("/api/metrics/history?limit=999999")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data

    def test_decision_boundary_default_resolution(self, client):
        """Contract: /api/decision_boundary works with default resolution."""
        resp = client.get("/api/decision_boundary")
        assert resp.status_code == 200

    def test_metrics_history_limit_1(self, client):
        """Contract: limit=1 returns at most 1 entry."""
        resp = client.get("/api/metrics/history?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["history"]) <= 1
