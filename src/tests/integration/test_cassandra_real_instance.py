#!/usr/bin/env python
"""
Integration tests for Cassandra client against a real Cassandra instance (CAN-DEF-002).

These tests require a running Cassandra cluster and are gated behind the
CASSANDRA_INTEGRATION_TEST=1 environment variable. Configure contact points
via CASSANDRA_CONTACT_POINTS (default: 127.0.0.1) and port via
CASSANDRA_PORT (default: 9042).

Run:
    CASSANDRA_INTEGRATION_TEST=1 CASSANDRA_CONTACT_POINTS=127.0.0.1 \
        pytest tests/integration/test_cassandra_real_instance.py -v
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

CASSANDRA_INTEGRATION = os.environ.get("CASSANDRA_INTEGRATION_TEST", "0") == "1"
CASSANDRA_CONTACT_POINTS = os.environ.get("CASSANDRA_CONTACT_POINTS", "127.0.0.1").split(",")
CASSANDRA_PORT = int(os.environ.get("CASSANDRA_PORT", "9042"))

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_cassandra,
    pytest.mark.skipif(not CASSANDRA_INTEGRATION, reason="Set CASSANDRA_INTEGRATION_TEST=1 to enable"),
]


def _make_cassandra_config_manager():
    """Create a ConfigManager mock that enables Cassandra with test settings."""
    config = {
        "cassandra.enabled": True,
        "cassandra.contact_points": CASSANDRA_CONTACT_POINTS,
        "cassandra.port": CASSANDRA_PORT,
        "cassandra.keyspace": "",  # Don't target a specific keyspace
        "cassandra.username": None,
        "cassandra.password": None,
        "cassandra.connect_timeout": 10,
    }
    mgr = MagicMock()
    mgr.get.side_effect = lambda key, default=None: config.get(key, default)
    return mgr


@pytest.fixture()
def cassandra_client():
    """Create a CassandraClient connected to the real Cassandra instance."""
    from settings import get_settings

    with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
        get_settings.cache_clear()
        try:
            from backend.cassandra_client import CassandraClient

            client = CassandraClient(config_manager=_make_cassandra_config_manager())
            yield client
            client.close()
        finally:
            get_settings.cache_clear()


class TestCassandraRealConnection:
    """Tests that verify real Cassandra connection and data retrieval."""

    def test_is_connected(self, cassandra_client):
        """Cassandra client connects successfully to real cluster."""
        assert cassandra_client._is_connected() is True

    def test_get_status_returns_up(self, cassandra_client):
        """get_status() returns UP/LIVE when connected."""
        status = cassandra_client.get_status()
        assert status["status"] == "UP"
        assert status["mode"] == "LIVE"

    def test_get_status_has_required_fields(self, cassandra_client):
        """Status response contains all required fields."""
        status = cassandra_client.get_status()
        assert "status" in status
        assert "mode" in status
        assert "message" in status
        assert "timestamp" in status
        assert "details" in status

    def test_get_status_details_has_hosts(self, cassandra_client):
        """Status details include host list from real cluster."""
        status = cassandra_client.get_status()
        details = status["details"]
        assert "hosts" in details
        assert isinstance(details["hosts"], list)
        assert len(details["hosts"]) >= 1

        host = details["hosts"][0]
        assert "address" in host
        assert "is_up" in host
        assert host["is_up"] is True

    def test_get_status_details_has_contact_points(self, cassandra_client):
        """Status details include contact points."""
        status = cassandra_client.get_status()
        details = status["details"]
        assert "contact_points" in details
        assert isinstance(details["contact_points"], list)

    def test_get_status_details_has_cluster_name(self, cassandra_client):
        """Status details include cluster name from real cluster."""
        status = cassandra_client.get_status()
        details = status["details"]
        assert "cluster_name" in details
        assert isinstance(details["cluster_name"], str)
        assert len(details["cluster_name"]) > 0

    def test_get_status_details_has_protocol_version(self, cassandra_client):
        """Status details include protocol version."""
        status = cassandra_client.get_status()
        details = status["details"]
        assert "protocol_version" in details
        assert isinstance(details["protocol_version"], int)

    def test_get_status_timestamp_format(self, cassandra_client):
        """Status timestamp is ISO 8601 format."""
        status = cassandra_client.get_status()
        ts = status["timestamp"]
        assert "T" in ts


class TestCassandraRealMetrics:
    """Tests that verify real Cassandra metrics retrieval."""

    def test_get_metrics_returns_up(self, cassandra_client):
        """get_metrics() returns UP/LIVE when connected."""
        metrics = cassandra_client.get_metrics()
        assert metrics["status"] == "UP"
        assert metrics["mode"] == "LIVE"

    def test_get_metrics_has_required_fields(self, cassandra_client):
        """Metrics response contains all required top-level fields."""
        metrics = cassandra_client.get_metrics()
        assert "status" in metrics
        assert "mode" in metrics
        assert "message" in metrics
        assert "timestamp" in metrics
        assert "metrics" in metrics

    def test_get_metrics_has_keyspaces(self, cassandra_client):
        """Metrics include keyspace list from real cluster."""
        result = cassandra_client.get_metrics()
        metrics = result["metrics"]
        assert "keyspaces" in metrics
        assert isinstance(metrics["keyspaces"], list)
        # Real Cassandra always has system keyspaces (filtered out) but may have user keyspaces
        # Just verify the list is present and well-formed

    def test_get_metrics_has_cluster_stats(self, cassandra_client):
        """Metrics include cluster stats from real cluster."""
        result = cassandra_client.get_metrics()
        metrics = result["metrics"]
        assert "cluster_stats" in metrics
        stats = metrics["cluster_stats"]
        assert "total_nodes" in stats
        assert isinstance(stats["total_nodes"], int)
        assert stats["total_nodes"] >= 1
        assert "live_nodes" in stats
        assert isinstance(stats["live_nodes"], int)
        assert stats["live_nodes"] >= 1

    def test_get_metrics_keyspace_structure(self, cassandra_client):
        """Each keyspace has expected structure when present."""
        result = cassandra_client.get_metrics()
        keyspaces = result["metrics"]["keyspaces"]
        for ks in keyspaces:
            assert "name" in ks
            assert "replication_strategy" in ks
            assert "tables" in ks
            assert isinstance(ks["tables"], list)


class TestCassandraRealLifecycle:
    """Tests for connection lifecycle against real Cassandra."""

    def test_close_disconnects(self):
        """Client disconnects cleanly on close."""
        from settings import get_settings

        with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
            get_settings.cache_clear()
            try:
                from backend.cassandra_client import CassandraClient

                client = CassandraClient(config_manager=_make_cassandra_config_manager())
                assert client._is_connected() is True
                client.close()
                assert client._is_connected() is False
            finally:
                get_settings.cache_clear()

    def test_status_after_close(self):
        """Status returns UNAVAILABLE after close and reconnects."""
        from settings import get_settings

        with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
            get_settings.cache_clear()
            try:
                from backend.cassandra_client import CassandraClient

                client = CassandraClient(config_manager=_make_cassandra_config_manager())
                assert client._is_connected() is True
                client.close()
                # After close, get_status should attempt reconnection
                status = client.get_status()
                # Either it reconnected (UP) or couldn't (UNAVAILABLE)
                assert status["status"] in ("UP", "UNAVAILABLE")
                client.close()
            finally:
                get_settings.cache_clear()

    def test_status_caching(self):
        """Status is cached for 5 seconds (same timestamp on rapid calls)."""
        from settings import get_settings

        with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
            get_settings.cache_clear()
            try:
                from backend.cassandra_client import CassandraClient

                client = CassandraClient(config_manager=_make_cassandra_config_manager())
                status1 = client.get_status()
                status2 = client.get_status()
                # Cached: same timestamp
                assert status1["timestamp"] == status2["timestamp"]
                client.close()
            finally:
                get_settings.cache_clear()
