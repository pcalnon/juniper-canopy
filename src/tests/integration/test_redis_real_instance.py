#!/usr/bin/env python
"""
Integration tests for Redis client against a real Redis instance (CAN-DEF-003).

These tests require a running Redis server and are gated behind the
REDIS_INTEGRATION_TEST=1 environment variable. Configure the Redis URL
via REDIS_URL (default: redis://localhost:6379/0).

Run:
    REDIS_INTEGRATION_TEST=1 REDIS_URL=redis://localhost:6379/0 \
        pytest tests/integration/test_redis_real_instance.py -v
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

REDIS_INTEGRATION = os.environ.get("REDIS_INTEGRATION_TEST", "0") == "1"
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.requires_redis,
    pytest.mark.skipif(not REDIS_INTEGRATION, reason="Set REDIS_INTEGRATION_TEST=1 to enable"),
]


def _make_redis_config_manager():
    """Create a ConfigManager mock that enables Redis with the test URL."""
    config = {
        "backend.cache": {
            "enabled": True,
            "type": "redis",
            "redis_url": REDIS_URL,
            "ttl_seconds": 3600,
            "max_memory_mb": 100,
        },
    }
    mgr = MagicMock()
    mgr.get.side_effect = lambda key, default=None: config.get(key, default)
    return mgr


@pytest.fixture()
def redis_client():
    """Create a RedisClient connected to the real Redis instance."""
    from settings import get_settings

    # Clear cached settings so demo_mode=False takes effect
    with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
        get_settings.cache_clear()
        try:
            from backend.redis_client import RedisClient

            client = RedisClient(config_manager=_make_redis_config_manager())
            yield client
            client.close()
        finally:
            get_settings.cache_clear()


class TestRedisRealConnection:
    """Tests that verify real Redis connection and data retrieval."""

    def test_is_available(self, redis_client):
        """Redis client reports available when connected to real instance."""
        assert redis_client.is_available() is True

    def test_get_status_returns_up(self, redis_client):
        """get_status() returns UP/LIVE when connected."""
        status = redis_client.get_status()
        assert status["status"] == "UP"
        assert status["mode"] == "LIVE"

    def test_get_status_has_required_fields(self, redis_client):
        """Status response contains all required fields."""
        status = redis_client.get_status()
        assert "status" in status
        assert "mode" in status
        assert "message" in status
        assert "timestamp" in status
        assert "details" in status

    def test_get_status_details_has_version(self, redis_client):
        """Status details include Redis server version."""
        status = redis_client.get_status()
        details = status["details"]
        assert "version" in details
        assert isinstance(details["version"], str)

    def test_get_status_details_has_uptime(self, redis_client):
        """Status details include server uptime."""
        status = redis_client.get_status()
        details = status["details"]
        assert "uptime_seconds" in details
        assert isinstance(details["uptime_seconds"], int)
        assert details["uptime_seconds"] >= 0

    def test_get_status_details_has_connected_clients(self, redis_client):
        """Status details include connected client count."""
        status = redis_client.get_status()
        details = status["details"]
        assert "connected_clients" in details
        assert isinstance(details["connected_clients"], int)
        assert details["connected_clients"] >= 1  # at least our connection

    def test_get_status_timestamp_format(self, redis_client):
        """Status timestamp is ISO 8601 with Z suffix."""
        status = redis_client.get_status()
        ts = status["timestamp"]
        assert "T" in ts
        assert ts.endswith("Z")


class TestRedisRealMetrics:
    """Tests that verify real Redis metrics retrieval."""

    def test_get_metrics_returns_up(self, redis_client):
        """get_metrics() returns UP/LIVE when connected."""
        metrics = redis_client.get_metrics()
        assert metrics["status"] == "UP"
        assert metrics["mode"] == "LIVE"

    def test_get_metrics_has_required_fields(self, redis_client):
        """Metrics response contains all required top-level fields."""
        metrics = redis_client.get_metrics()
        assert "status" in metrics
        assert "mode" in metrics
        assert "message" in metrics
        assert "timestamp" in metrics
        assert "metrics" in metrics

    def test_get_metrics_memory_section(self, redis_client):
        """Metrics include memory section with real data."""
        result = redis_client.get_metrics()
        memory = result["metrics"]["memory"]
        assert "used_memory_bytes" in memory
        assert isinstance(memory["used_memory_bytes"], int)
        assert memory["used_memory_bytes"] > 0
        assert "used_memory_human" in memory
        assert "used_memory_peak_human" in memory
        assert "mem_fragmentation_ratio" in memory

    def test_get_metrics_stats_section(self, redis_client):
        """Metrics include stats section with real data."""
        result = redis_client.get_metrics()
        stats = result["metrics"]["stats"]
        assert "total_connections_received" in stats
        assert isinstance(stats["total_connections_received"], int)
        assert "total_commands_processed" in stats
        assert "instantaneous_ops_per_sec" in stats
        assert "keyspace_hits" in stats
        assert "keyspace_misses" in stats
        assert "hit_rate_percent" in stats
        assert isinstance(stats["hit_rate_percent"], (int, float))

    def test_get_metrics_clients_section(self, redis_client):
        """Metrics include clients section with real data."""
        result = redis_client.get_metrics()
        clients = result["metrics"]["clients"]
        assert "connected_clients" in clients
        assert isinstance(clients["connected_clients"], int)
        assert clients["connected_clients"] >= 1
        assert "blocked_clients" in clients

    def test_get_metrics_keyspace_section(self, redis_client):
        """Metrics include keyspace section."""
        result = redis_client.get_metrics()
        assert "keyspace" in result["metrics"]


class TestRedisRealLifecycle:
    """Tests for connection lifecycle against real Redis."""

    def test_close_and_reconnect(self):
        """Client can be closed and a new one created."""
        from settings import get_settings

        with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
            get_settings.cache_clear()
            try:
                from backend.redis_client import RedisClient

                client1 = RedisClient(config_manager=_make_redis_config_manager())
                assert client1.is_available() is True
                client1.close()

                client2 = RedisClient(config_manager=_make_redis_config_manager())
                assert client2.is_available() is True
                client2.close()
            finally:
                get_settings.cache_clear()

    def test_status_after_close(self):
        """Status returns DOWN or UNAVAILABLE after close."""
        from settings import get_settings

        with patch.dict(os.environ, {"JUNIPER_CANOPY_DEMO_MODE": "false"}, clear=False):
            get_settings.cache_clear()
            try:
                from backend.redis_client import RedisClient

                client = RedisClient(config_manager=_make_redis_config_manager())
                assert client.is_available() is True
                client.close()
                assert client.is_available() is False
            finally:
                get_settings.cache_clear()
