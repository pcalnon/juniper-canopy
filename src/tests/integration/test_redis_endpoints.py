#!/usr/bin/env python
"""
Integration tests for Redis API endpoints (P3-6).

Tests cover:
- GET /api/v1/redis/status returns 200
- GET /api/v1/redis/metrics returns 200
- Response structure contains required fields
- Demo mode returns synthetic data
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def reset_redis_singleton():
    """Reset Redis client singleton before each test."""
    import backend.redis_client as redis_module

    redis_module._redis_client_instance = None
    yield
    redis_module._redis_client_instance = None


@pytest.mark.integration
class TestRedisStatusEndpoint:
    """Integration tests for /api/v1/redis/status endpoint."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    def test_status_endpoint_returns_200(self, client):
        """GET /api/v1/redis/status returns 200 OK."""
        response = client.get("/api/v1/redis/status")
        assert response.status_code == 200

    def test_status_endpoint_returns_json(self, client):
        """GET /api/v1/redis/status returns JSON content type."""
        response = client.get("/api/v1/redis/status")
        assert "application/json" in response.headers.get("content-type", "")

    def test_status_contains_status_field(self, client):
        """Response contains 'status' field."""
        response = client.get("/api/v1/redis/status")
        data = response.json()
        assert "status" in data

    def test_status_contains_mode_field(self, client):
        """Response contains 'mode' field."""
        response = client.get("/api/v1/redis/status")
        data = response.json()
        assert "mode" in data

    def test_status_contains_message_field(self, client):
        """Response contains 'message' field."""
        response = client.get("/api/v1/redis/status")
        data = response.json()
        assert "message" in data

    def test_status_contains_timestamp_field(self, client):
        """Response contains 'timestamp' field."""
        response = client.get("/api/v1/redis/status")
        data = response.json()
        assert "timestamp" in data

    def test_status_valid_status_values(self, client):
        """Status field contains valid enum value."""
        response = client.get("/api/v1/redis/status")
        data = response.json()

        valid_statuses = ["UP", "DOWN", "DISABLED", "UNAVAILABLE"]
        assert data["status"] in valid_statuses

    def test_status_valid_mode_values(self, client):
        """Mode field contains valid enum value."""
        response = client.get("/api/v1/redis/status")
        data = response.json()

        valid_modes = ["DEMO", "LIVE", "DISABLED"]
        assert data["mode"] in valid_modes

    def test_status_timestamp_iso_format(self, client):
        """Timestamp is in ISO 8601 format."""
        response = client.get("/api/v1/redis/status")
        data = response.json()

        timestamp = data["timestamp"]
        assert "T" in timestamp
        assert timestamp.endswith("Z")


@pytest.mark.integration
class TestRedisMetricsEndpoint:
    """Integration tests for /api/v1/redis/metrics endpoint."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    def test_metrics_endpoint_returns_200(self, client):
        """GET /api/v1/redis/metrics returns 200 OK."""
        response = client.get("/api/v1/redis/metrics")
        assert response.status_code == 200

    def test_metrics_endpoint_returns_json(self, client):
        """GET /api/v1/redis/metrics returns JSON content type."""
        response = client.get("/api/v1/redis/metrics")
        assert "application/json" in response.headers.get("content-type", "")

    def test_metrics_contains_status_field(self, client):
        """Response contains 'status' field."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()
        assert "status" in data

    def test_metrics_contains_mode_field(self, client):
        """Response contains 'mode' field."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()
        assert "mode" in data

    def test_metrics_contains_message_field(self, client):
        """Response contains 'message' field."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()
        assert "message" in data

    def test_metrics_contains_timestamp_field(self, client):
        """Response contains 'timestamp' field."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()
        assert "timestamp" in data

    def test_metrics_contains_metrics_field(self, client):
        """Response contains 'metrics' field."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()
        assert "metrics" in data


@pytest.mark.integration
class TestRedisEndpointsDemoMode:
    """Integration tests for Redis endpoints in demo mode."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    def test_demo_mode_status_returns_up(self, client):
        """In demo mode, status is UP."""
        response = client.get("/api/v1/redis/status")
        data = response.json()

        assert data["status"] == "UP"
        assert data["mode"] == "DEMO"

    def test_demo_mode_metrics_has_data(self, client):
        """In demo mode, metrics contains synthetic data."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        assert data["status"] == "UP"
        assert data["mode"] == "DEMO"
        assert data["metrics"] is not None

    def test_demo_mode_metrics_memory_section(self, client):
        """In demo mode, metrics has memory section."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        metrics = data["metrics"]
        assert "memory" in metrics

        memory = metrics["memory"]
        assert "used_memory_bytes" in memory
        assert "used_memory_human" in memory
        assert "used_memory_peak_human" in memory
        assert "mem_fragmentation_ratio" in memory

    def test_demo_mode_metrics_stats_section(self, client):
        """In demo mode, metrics has stats section."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        metrics = data["metrics"]
        assert "stats" in metrics

        stats = metrics["stats"]
        assert "total_connections_received" in stats
        assert "total_commands_processed" in stats
        assert "instantaneous_ops_per_sec" in stats
        assert "keyspace_hits" in stats
        assert "keyspace_misses" in stats
        assert "hit_rate_percent" in stats

    def test_demo_mode_metrics_clients_section(self, client):
        """In demo mode, metrics has clients section."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        metrics = data["metrics"]
        assert "clients" in metrics

        clients = metrics["clients"]
        assert "connected_clients" in clients
        assert "blocked_clients" in clients

    def test_demo_mode_metrics_keyspace_section(self, client):
        """In demo mode, metrics has keyspace section."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        metrics = data["metrics"]
        assert "keyspace" in metrics

    def test_demo_mode_status_message_indicates_demo(self, client):
        """In demo mode, message indicates simulated/demo data."""
        response = client.get("/api/v1/redis/status")
        data = response.json()

        message = data["message"].lower()
        assert "demo" in message or "simulated" in message

    def test_demo_mode_metrics_message_indicates_demo(self, client):
        """In demo mode, metrics message indicates simulated/demo data."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        message = data["message"].lower()
        assert "demo" in message or "simulated" in message


@pytest.mark.integration
class TestRedisEndpointsResponseStructure:
    """Test response structure validation."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    def test_status_details_present(self, client):
        """Status response includes details section."""
        response = client.get("/api/v1/redis/status")
        data = response.json()

        assert "details" in data

    def test_metrics_hit_rate_is_numeric(self, client):
        """Hit rate is a numeric value."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        if data["metrics"]:
            hit_rate = data["metrics"]["stats"]["hit_rate_percent"]
            assert isinstance(hit_rate, (int, float))

    def test_metrics_memory_bytes_is_integer(self, client):
        """Memory bytes is an integer value."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        if data["metrics"]:
            memory_bytes = data["metrics"]["memory"]["used_memory_bytes"]
            assert isinstance(memory_bytes, int)

    def test_metrics_ops_per_sec_is_integer(self, client):
        """Ops per second is an integer value."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        if data["metrics"]:
            ops = data["metrics"]["stats"]["instantaneous_ops_per_sec"]
            assert isinstance(ops, int)

    def test_metrics_connected_clients_is_integer(self, client):
        """Connected clients is an integer value."""
        response = client.get("/api/v1/redis/metrics")
        data = response.json()

        if data["metrics"]:
            clients = data["metrics"]["clients"]["connected_clients"]
            assert isinstance(clients, int)


@pytest.mark.integration
class TestRedisEndpointsConcurrency:
    """Test concurrent access to Redis endpoints."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    def test_concurrent_status_requests(self, client):
        """Multiple concurrent status requests succeed."""
        import concurrent.futures

        def get_status():
            return client.get("/api/v1/redis/status").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_status) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(status == 200 for status in results)

    def test_concurrent_metrics_requests(self, client):
        """Multiple concurrent metrics requests succeed."""
        import concurrent.futures

        def get_metrics():
            return client.get("/api/v1/redis/metrics").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_metrics) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(status == 200 for status in results)

    def test_interleaved_status_and_metrics(self, client):
        """Interleaved status and metrics requests succeed."""
        import concurrent.futures

        def get_endpoint(path):
            return client.get(path).status_code

        endpoints = ["/api/v1/redis/status", "/api/v1/redis/metrics"] * 5

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_endpoint, ep) for ep in endpoints]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert all(status == 200 for status in results)


@pytest.mark.integration
class TestRedisEndpointsIdempotency:
    """Test endpoint idempotency."""

    @pytest.fixture(autouse=True)
    def client(self):
        """Create test client with demo mode."""
        with TestClient(app) as client:
            yield client

    def test_status_idempotent(self, client):
        """Multiple status calls return consistent structure."""
        response1 = client.get("/api/v1/redis/status")
        response2 = client.get("/api/v1/redis/status")

        data1 = response1.json()
        data2 = response2.json()

        assert data1["status"] == data2["status"]
        assert data1["mode"] == data2["mode"]
        assert set(data1.keys()) == set(data2.keys())

    def test_metrics_idempotent(self, client):
        """Multiple metrics calls return consistent structure."""
        response1 = client.get("/api/v1/redis/metrics")
        response2 = client.get("/api/v1/redis/metrics")

        data1 = response1.json()
        data2 = response2.json()

        assert data1["status"] == data2["status"]
        assert data1["mode"] == data2["mode"]
        assert set(data1.keys()) == set(data2.keys())
