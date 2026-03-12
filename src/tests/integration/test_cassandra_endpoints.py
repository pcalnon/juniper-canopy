#!/usr/bin/env python
"""
Integration tests for Cassandra API endpoints (P3-7).

Tests:
- GET /api/v1/cassandra/status returns 200
- GET /api/v1/cassandra/metrics returns 200
- Response structure contains required fields
- Demo mode returns synthetic cluster/metrics data
"""
import os
import sys
from pathlib import Path

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture(scope="module")
def client():
    """FastAPI test client with demo mode enabled."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_cassandra_singleton():
    """Reset Cassandra client singleton before each test."""
    import backend.cassandra_client as cc_module

    cc_module._cassandra_client_instance = None
    yield
    cc_module._cassandra_client_instance = None


class TestCassandraStatusEndpoint:
    """Test GET /api/v1/cassandra/status endpoint."""

    @pytest.mark.integration
    def test_status_endpoint_returns_200(self, client):
        """Status endpoint should return HTTP 200."""
        response = client.get("/api/v1/cassandra/status")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_status_endpoint_returns_json(self, client):
        """Status endpoint should return valid JSON."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.integration
    def test_status_response_has_status_field(self, client):
        """Status response should contain 'status' field."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert "status" in data
        assert data["status"] in ("UP", "DOWN", "DISABLED", "UNAVAILABLE")

    @pytest.mark.integration
    def test_status_response_has_mode_field(self, client):
        """Status response should contain 'mode' field."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert "mode" in data
        assert data["mode"] in ("DEMO", "LIVE", "DISABLED")

    @pytest.mark.integration
    def test_status_response_has_message_field(self, client):
        """Status response should contain 'message' field."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert "message" in data
        assert isinstance(data["message"], str)

    @pytest.mark.integration
    def test_status_response_has_timestamp_field(self, client):
        """Status response should contain 'timestamp' field."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert "timestamp" in data

    @pytest.mark.integration
    def test_status_response_has_details_field(self, client):
        """Status response should contain 'details' field."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert "details" in data
        assert isinstance(data["details"], dict)


class TestCassandraMetricsEndpoint:
    """Test GET /api/v1/cassandra/metrics endpoint."""

    @pytest.mark.integration
    def test_metrics_endpoint_returns_200(self, client):
        """Metrics endpoint should return HTTP 200."""
        response = client.get("/api/v1/cassandra/metrics")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_metrics_endpoint_returns_json(self, client):
        """Metrics endpoint should return valid JSON."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.integration
    def test_metrics_response_has_status_field(self, client):
        """Metrics response should contain 'status' field."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert "status" in data
        assert data["status"] in ("UP", "DOWN", "DISABLED", "UNAVAILABLE")

    @pytest.mark.integration
    def test_metrics_response_has_mode_field(self, client):
        """Metrics response should contain 'mode' field."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert "mode" in data
        assert data["mode"] in ("DEMO", "LIVE", "DISABLED")

    @pytest.mark.integration
    def test_metrics_response_has_message_field(self, client):
        """Metrics response should contain 'message' field."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert "message" in data
        assert isinstance(data["message"], str)

    @pytest.mark.integration
    def test_metrics_response_has_timestamp_field(self, client):
        """Metrics response should contain 'timestamp' field."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert "timestamp" in data

    @pytest.mark.integration
    def test_metrics_response_has_metrics_field(self, client):
        """Metrics response should contain 'metrics' field."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert "metrics" in data


class TestCassandraDemoModeStatus:
    """Test demo mode returns synthetic cluster data in status."""

    @pytest.mark.integration
    def test_demo_status_is_up(self, client):
        """Demo mode should return UP status."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        assert data["status"] == "UP"
        assert data["mode"] == "DEMO"

    @pytest.mark.integration
    def test_demo_status_has_contact_points(self, client):
        """Demo mode should include contact_points in details."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        details = data["details"]
        assert "contact_points" in details
        assert isinstance(details["contact_points"], list)
        assert len(details["contact_points"]) > 0

    @pytest.mark.integration
    def test_demo_status_has_hosts(self, client):
        """Demo mode should include hosts in details."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        details = data["details"]
        assert "hosts" in details
        assert isinstance(details["hosts"], list)
        assert len(details["hosts"]) > 0

    @pytest.mark.integration
    def test_demo_status_hosts_have_required_fields(self, client):
        """Demo mode hosts should have address, rack, and is_up."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        hosts = data["details"]["hosts"]

        for host in hosts:
            assert "address" in host
            assert "rack" in host
            assert "is_up" in host

    @pytest.mark.integration
    def test_demo_status_has_keyspace(self, client):
        """Demo mode should include keyspace in details."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        details = data["details"]
        assert "keyspace" in details

    @pytest.mark.integration
    def test_demo_status_has_cluster_name(self, client):
        """Demo mode should include cluster_name in details."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        details = data["details"]
        assert "cluster_name" in details

    @pytest.mark.integration
    def test_demo_status_has_protocol_version(self, client):
        """Demo mode should include protocol_version in details."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()
        details = data["details"]
        assert "protocol_version" in details


class TestCassandraDemoModeMetrics:
    """Test demo mode returns synthetic metrics data."""

    @pytest.mark.integration
    def test_demo_metrics_is_up(self, client):
        """Demo mode should return UP status for metrics."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        assert data["status"] == "UP"
        assert data["mode"] == "DEMO"

    @pytest.mark.integration
    def test_demo_metrics_has_keyspaces(self, client):
        """Demo mode should include keyspaces in metrics."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        metrics = data["metrics"]
        assert "keyspaces" in metrics
        assert isinstance(metrics["keyspaces"], list)
        assert len(metrics["keyspaces"]) > 0

    @pytest.mark.integration
    def test_demo_metrics_keyspaces_have_required_fields(self, client):
        """Demo mode keyspaces should have name, replication_strategy, tables."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        keyspaces = data["metrics"]["keyspaces"]

        for ks in keyspaces:
            assert "name" in ks
            assert "replication_strategy" in ks
            assert "tables" in ks

    @pytest.mark.integration
    def test_demo_metrics_tables_have_info(self, client):
        """Demo mode tables should have name and row count info."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        keyspaces = data["metrics"]["keyspaces"]

        for ks in keyspaces:
            for table in ks["tables"]:
                assert "name" in table

    @pytest.mark.integration
    def test_demo_metrics_has_cluster_stats(self, client):
        """Demo mode should include cluster_stats in metrics."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        metrics = data["metrics"]
        assert "cluster_stats" in metrics

    @pytest.mark.integration
    def test_demo_metrics_cluster_stats_has_node_counts(self, client):
        """Demo mode cluster_stats should have node counts."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()
        cluster_stats = data["metrics"]["cluster_stats"]
        assert "total_nodes" in cluster_stats
        assert "live_nodes" in cluster_stats


class TestCassandraEndpointConsistency:
    """Test endpoint response consistency."""

    @pytest.mark.integration
    def test_status_and_metrics_have_same_status(self, client):
        """Status and metrics endpoints should report same status."""
        status_response = client.get("/api/v1/cassandra/status")
        metrics_response = client.get("/api/v1/cassandra/metrics")

        status_data = status_response.json()
        metrics_data = metrics_response.json()

        assert status_data["status"] == metrics_data["status"]
        assert status_data["mode"] == metrics_data["mode"]

    @pytest.mark.integration
    def test_multiple_status_calls_consistent(self, client):
        """Multiple status calls should return consistent structure."""
        response1 = client.get("/api/v1/cassandra/status")
        response2 = client.get("/api/v1/cassandra/status")

        data1 = response1.json()
        data2 = response2.json()

        assert data1["status"] == data2["status"]
        assert data1["mode"] == data2["mode"]
        assert set(data1.keys()) == set(data2.keys())

    @pytest.mark.integration
    def test_multiple_metrics_calls_consistent(self, client):
        """Multiple metrics calls should return consistent structure."""
        response1 = client.get("/api/v1/cassandra/metrics")
        response2 = client.get("/api/v1/cassandra/metrics")

        data1 = response1.json()
        data2 = response2.json()

        assert data1["status"] == data2["status"]
        assert data1["mode"] == data2["mode"]
        assert set(data1.keys()) == set(data2.keys())


class TestCassandraResponseFormat:
    """Test response format compliance."""

    @pytest.mark.integration
    def test_status_timestamp_is_iso_format(self, client):
        """Status timestamp should be in ISO format."""
        response = client.get("/api/v1/cassandra/status")
        data = response.json()

        timestamp = data["timestamp"]
        assert "T" in timestamp or "-" in timestamp

    @pytest.mark.integration
    def test_metrics_timestamp_is_iso_format(self, client):
        """Metrics timestamp should be in ISO format."""
        response = client.get("/api/v1/cassandra/metrics")
        data = response.json()

        timestamp = data["timestamp"]
        assert "T" in timestamp or "-" in timestamp

    @pytest.mark.integration
    def test_status_content_type_is_json(self, client):
        """Status endpoint should return application/json content type."""
        response = client.get("/api/v1/cassandra/status")
        assert "application/json" in response.headers.get("content-type", "")

    @pytest.mark.integration
    def test_metrics_content_type_is_json(self, client):
        """Metrics endpoint should return application/json content type."""
        response = client.get("/api/v1/cassandra/metrics")
        assert "application/json" in response.headers.get("content-type", "")
