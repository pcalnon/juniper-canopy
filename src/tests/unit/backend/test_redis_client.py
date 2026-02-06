#!/usr/bin/env python
"""
Unit tests for Redis client wrapper (P3-6).

Tests cover:
- Disabled by config: returns DISABLED status
- Driver missing: mocks redis=None, returns DISABLED
- Demo mode: returns UP with DEMO mode and synthetic data
- Connection failure: mocks ConnectionError, returns UNAVAILABLE
- get_status() returns proper structure
- get_metrics() returns proper structure
- is_available() behavior
- close() cleanup
- Singleton pattern via get_redis_client()
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

src_dir = Path(__file__).parents[3]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


@pytest.fixture
def mock_config_manager():
    """Create mock config manager."""
    mock_config = Mock()
    mock_config.get.return_value = {
        "enabled": False,
        "type": "memory",
    }
    return mock_config


@pytest.fixture
def enabled_redis_config():
    """Config with Redis enabled."""
    mock_config = Mock()
    mock_config.get.return_value = {
        "enabled": True,
        "type": "redis",
        "redis_url": "redis://localhost:6379/0",
        "ttl_seconds": 3600,
        "max_memory_mb": 100,
    }
    return mock_config


@pytest.fixture(autouse=True)
def reset_redis_singleton():
    """Reset Redis client singleton before each test."""
    import backend.redis_client as redis_module

    redis_module._redis_client_instance = None
    yield
    redis_module._redis_client_instance = None


@pytest.fixture(autouse=True)
def ensure_demo_mode_off(monkeypatch):
    """Ensure demo mode is off for most tests."""
    monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)


@pytest.mark.unit
class TestRedisClientDisabledByConfig:
    """Test Redis client when disabled in configuration."""

    def test_disabled_config_returns_disabled_status(self, mock_config_manager):
        """When cache.enabled=False, get_status returns DISABLED."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        status = client.get_status()

        assert status["status"] == "DISABLED"
        assert status["mode"] == "DISABLED"
        assert "timestamp" in status
        assert "message" in status

    def test_disabled_config_returns_disabled_metrics(self, mock_config_manager):
        """
        When cache.enabled=False,
        get_metrics returns DISABLED with no metrics.
        """
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()

        assert metrics["status"] == "DISABLED"
        assert metrics["mode"] == "DISABLED"
        assert metrics["metrics"] is None

    def test_disabled_config_is_available_false(self, mock_config_manager):
        """When cache.enabled=False, is_available returns False."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)

        assert client.is_available() is False


@pytest.mark.unit
class TestRedisClientDriverMissing:
    """Test Redis client when redis-py library is not installed."""

    def test_missing_driver_returns_disabled_status(self, enabled_redis_config):
        """When redis library is None, get_status returns DISABLED."""
        with patch("backend.redis_client.REDIS_AVAILABLE", False):
            with patch("backend.redis_client.redis", None):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                status = client.get_status()

                assert status["status"] == "DISABLED"
                assert "redis-py library not installed" in status["message"]
                assert status["details"]["redis_available"] is False
                assert "install_hint" in status["details"]

    def test_missing_driver_is_available_false(self, enabled_redis_config):
        """When redis library is None, is_available returns False."""
        with patch("backend.redis_client.REDIS_AVAILABLE", False):
            with patch("backend.redis_client.redis", None):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)

                assert client.is_available() is False


@pytest.mark.unit
class TestRedisClientDemoMode:
    """Test Redis client in demo mode."""

    def test_demo_mode_returns_up_status(self, mock_config_manager, monkeypatch):
        """In demo mode, get_status returns UP with DEMO mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        status = client.get_status()

        assert status["status"] == "UP"
        assert status["mode"] == "DEMO"
        assert "simulated" in (status["message"].lower()) or "demo" in (status["message"].lower())
        assert "timestamp" in status

    def test_demo_mode_returns_synthetic_metrics(self, mock_config_manager, monkeypatch):
        """In demo mode, get_metrics returns synthetic data."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()
        assert metrics["status"] == "UP"
        assert metrics["mode"] == "DEMO"
        assert metrics["metrics"] is not None
        memory = metrics["metrics"]["memory"]
        assert "used_memory_bytes" in memory
        assert "used_memory_human" in memory
        stats = metrics["metrics"]["stats"]
        assert "total_connections_received" in stats
        assert "keyspace_hits" in stats
        assert "hit_rate_percent" in stats
        clients = metrics["metrics"]["clients"]
        assert "connected_clients" in clients
        assert "keyspace" in metrics["metrics"]

    def test_demo_mode_is_available_true(self, mock_config_manager, monkeypatch):
        """In demo mode, is_available returns True."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        assert client.is_available() is True

    def test_demo_mode_true_values(self, mock_config_manager, monkeypatch):
        """Demo mode recognizes various truthy values."""
        for demo_val in ["1", "true", "yes", "on"]:
            monkeypatch.setenv("CASCOR_DEMO_MODE", demo_val)
            from backend.redis_client import RedisClient

            client = RedisClient(mock_config_manager)

            assert client._demo_mode is True, f"Failed for CASCOR_DEMO_MODE={demo_val}"


@pytest.mark.unit
class TestRedisClientConnectionFailure:
    """Test Redis client when connection fails."""

    def test_connection_error_returns_unavailable_status(self, enabled_redis_config):
        """When connection fails, get_status returns UNAVAILABLE or DOWN."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool
        mock_redis.Redis.return_value.ping.side_effect = Exception("Connection refused")

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                status = client.get_status()

                assert status["status"] in ["UNAVAILABLE", "DOWN"]
                assert status["mode"] == "LIVE"
                assert "host" in status["details"]
                assert "port" in status["details"]

    def test_connection_timeout_handles_gracefully(self, enabled_redis_config):
        """When connection times out, client handles gracefully."""
        mock_redis = MagicMock()
        mock_redis.ConnectionPool.return_value = MagicMock()

        timeout_error = type("RedisTimeoutError", (Exception,), {})
        mock_redis.Redis.return_value.ping.side_effect = timeout_error("Connection timed out")

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                with patch("backend.redis_client.RedisTimeoutError", timeout_error):
                    from backend.redis_client import RedisClient

                    client = RedisClient(enabled_redis_config)
                    status = client.get_status()

                    assert status["status"] in ["UNAVAILABLE", "DOWN"]


@pytest.mark.unit
class TestGetStatus:
    """Test get_status() response structure."""

    def test_status_contains_required_fields(self, mock_config_manager, monkeypatch):
        """get_status returns all required fields."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        status = client.get_status()

        required_fields = ["status", "mode", "message", "timestamp"]
        for field in required_fields:
            assert field in status, f"Missing required field: {field}"

    def test_status_valid_status_values(self, mock_config_manager):
        """Status field contains valid enum values."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        status = client.get_status()

        valid_statuses = ["UP", "DOWN", "DISABLED", "UNAVAILABLE"]
        assert status["status"] in valid_statuses

    def test_status_valid_mode_values(self, mock_config_manager):
        """Mode field contains valid enum values."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        status = client.get_status()

        valid_modes = ["DEMO", "LIVE", "DISABLED"]
        assert status["mode"] in valid_modes

    def test_status_timestamp_iso_format(self, mock_config_manager, monkeypatch):
        """Timestamp is in ISO 8601 format."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        status = client.get_status()

        timestamp = status["timestamp"]
        assert timestamp.endswith("Z")
        assert "T" in timestamp


@pytest.mark.unit
class TestGetMetrics:
    """Test get_metrics() response structure."""

    def test_metrics_contains_required_fields(self, mock_config_manager, monkeypatch):
        """get_metrics returns all required fields."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()

        required_fields = ["status", "mode", "message", "timestamp", "metrics"]
        for field in required_fields:
            assert field in metrics, f"Missing required field: {field}"

    def test_metrics_memory_structure(self, mock_config_manager, monkeypatch):
        """Metrics memory section has correct structure."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()

        memory = metrics["metrics"]["memory"]
        assert "used_memory_bytes" in memory
        assert "used_memory_human" in memory
        assert "used_memory_peak_human" in memory
        assert "mem_fragmentation_ratio" in memory

    def test_metrics_stats_structure(self, mock_config_manager, monkeypatch):
        """Metrics stats section has correct structure."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()

        stats = metrics["metrics"]["stats"]
        assert "total_connections_received" in stats
        assert "total_commands_processed" in stats
        assert "instantaneous_ops_per_sec" in stats
        assert "keyspace_hits" in stats
        assert "keyspace_misses" in stats
        assert "hit_rate_percent" in stats

    def test_metrics_clients_structure(self, mock_config_manager, monkeypatch):
        """Metrics clients section has correct structure."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()

        clients = metrics["metrics"]["clients"]
        assert "connected_clients" in clients
        assert "blocked_clients" in clients

    def test_metrics_disabled_returns_null_metrics(self, mock_config_manager):
        """When disabled, metrics field is None."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        metrics = client.get_metrics()

        assert metrics["metrics"] is None


@pytest.mark.unit
class TestIsAvailable:
    """Test is_available() behavior."""

    def test_is_available_demo_mode_true(self, mock_config_manager, monkeypatch):
        """is_available returns True in demo mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)

        assert client.is_available() is True

    def test_is_available_disabled_false(self, mock_config_manager):
        """is_available returns False when disabled."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)

        assert client.is_available() is False

    def test_is_available_no_client_false(self, enabled_redis_config):
        """is_available returns False when client is None."""
        with patch("backend.redis_client.REDIS_AVAILABLE", False):
            from backend.redis_client import RedisClient

            client = RedisClient(enabled_redis_config)
            client._client = None

            assert client.is_available() is False


@pytest.mark.unit
class TestClose:
    """Test close() cleanup behavior."""

    def test_close_disconnects_pool(self, mock_config_manager, monkeypatch):
        """close() disconnects the connection pool."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        mock_pool = MagicMock()
        client._connection_pool = mock_pool
        client._client = MagicMock()

        client.close()

        mock_pool.disconnect.assert_called_once()
        assert client._client is None
        assert client._connection_pool is None

    def test_close_handles_none_pool(self, mock_config_manager):
        """close() handles None connection pool gracefully."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        client._connection_pool = None
        client._client = None

        client.close()

    def test_close_handles_disconnect_error(self, mock_config_manager, monkeypatch):
        """close() handles disconnect errors gracefully."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        mock_pool = MagicMock()
        mock_pool.disconnect.side_effect = Exception("Disconnect failed")
        client._connection_pool = mock_pool
        client._client = MagicMock()

        client.close()

        assert client._client is None
        assert client._connection_pool is None


@pytest.mark.unit
class TestSingletonPattern:
    """Test get_redis_client() singleton behavior."""

    def test_get_redis_client_returns_same_instance(self, mock_config_manager, monkeypatch):
        """get_redis_client returns same instance on repeated calls."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import get_redis_client

        client1 = get_redis_client(mock_config_manager)
        client2 = get_redis_client(mock_config_manager)

        assert client1 is client2

    def test_get_redis_client_force_new_creates_new(self, mock_config_manager, monkeypatch):
        """get_redis_client(force_new=True) creates new instance."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import get_redis_client

        client1 = get_redis_client(mock_config_manager)
        client2 = get_redis_client(mock_config_manager, force_new=True)

        assert client1 is not client2

    def test_get_redis_client_uses_default_config(self, monkeypatch):
        """get_redis_client uses ConfigManager if none provided."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import get_redis_client

        client = get_redis_client(force_new=True)

        assert client is not None


@pytest.mark.unit
class TestConfigParsing:
    """Test configuration parsing."""

    def test_parses_redis_url(self, monkeypatch):
        """Correctly parses redis:// URL."""
        mock_config = Mock()
        mock_config.get.return_value = {
            "enabled": True,
            "type": "redis",
            "redis_url": "redis://myhost:6380/2",
        }

        with patch("backend.redis_client.REDIS_AVAILABLE", False):
            from backend.redis_client import RedisClient

            client = RedisClient(mock_config)
            config = client._get_redis_config()

            assert config["enabled"] is True
            assert config["host"] == "myhost"
            assert config["port"] == 6380
            assert config["db"] == 2

    def test_redis_url_env_override(self, monkeypatch):
        """REDIS_URL env var overrides config."""
        monkeypatch.setenv("REDIS_URL", "redis://envhost:6381/3")

        mock_config = Mock()
        mock_config.get.return_value = {
            "enabled": True,
            "type": "redis",
            "redis_url": "redis://confighost:6379/0",
        }

        with patch("backend.redis_client.REDIS_AVAILABLE", False):
            from backend.redis_client import RedisClient

            client = RedisClient(mock_config)
            config = client._get_redis_config()

            assert config["host"] == "envhost"
            assert config["port"] == 6381
            assert config["db"] == 3

    def test_non_redis_cache_type_disabled(self):
        """Cache type != 'redis' returns disabled config."""
        mock_config = Mock()
        mock_config.get.return_value = {
            "enabled": True,
            "type": "memory",
        }

        from backend.redis_client import RedisClient

        client = RedisClient(mock_config)
        config = client._get_redis_config()

        assert config["enabled"] is False


@pytest.mark.unit
class TestStatusConstants:
    """Test status constant values."""

    def test_status_constants_defined(self):
        """RedisClient has correct status constants."""
        from backend.redis_client import RedisClient

        assert RedisClient.STATUS_UP == "UP"
        assert RedisClient.STATUS_DOWN == "DOWN"
        assert RedisClient.STATUS_DISABLED == "DISABLED"
        assert RedisClient.STATUS_UNAVAILABLE == "UNAVAILABLE"

    def test_mode_constants_defined(self):
        """RedisClient has correct mode constants."""
        from backend.redis_client import RedisClient

        assert RedisClient.MODE_DEMO == "DEMO"
        assert RedisClient.MODE_LIVE == "LIVE"
        assert RedisClient.MODE_DISABLED == "DISABLED"


@pytest.mark.unit
class TestPingErrorHandling:
    """Test _ping() error handling paths."""

    def test_ping_returns_false_when_client_is_none(self, mock_config_manager):
        """_ping() returns False when client is None (line 239)."""
        from backend.redis_client import RedisClient

        client = RedisClient(mock_config_manager)
        client._client = None

        result = client._ping()

        assert result is False

    def test_ping_handles_timeout_error(self, enabled_redis_config):
        """
        _ping() handles RedisTimeoutError and returns False (lines 243-246)
        """
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        timeout_error = type("RedisTimeoutError", (Exception,), {})

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                with patch("backend.redis_client.RedisTimeoutError", timeout_error):
                    from backend.redis_client import RedisClient

                    client = RedisClient(enabled_redis_config)
                    mock_client.ping.side_effect = timeout_error("Connection timed out")

                    result = client._ping()

                    assert result is False
                    assert client._last_ping_success is False
                    assert "timed out" in client._last_error

    def test_ping_handles_connection_error(self, enabled_redis_config):
        """_ping() handles RedisConnectionError and returns False."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        connection_error = type("RedisConnectionError", (Exception,), {})

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                with patch("backend.redis_client.RedisConnectionError", connection_error):
                    from backend.redis_client import RedisClient

                    client = RedisClient(enabled_redis_config)
                    mock_client.ping.side_effect = connection_error("Connection refused")

                    result = client._ping()

                    assert result is False
                    assert client._last_ping_success is False


@pytest.mark.unit
class TestGetStatusInfoRetrievalError:
    """Test get_status() when info retrieval fails (lines 330-354)."""

    def test_get_status_returns_limited_info_on_info_error(self, enabled_redis_config):
        """
        get_status returns limited info
          when info() raises exception (lines 352-364).
        """
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.side_effect = Exception("INFO command failed")
        mock_redis.Redis.return_value = mock_client

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                status = client.get_status()

                assert status["status"] == "UP"
                assert status["mode"] == "LIVE"
                assert "limited info" in status["message"]
                assert "info_error" in status["details"]
                assert "INFO command failed" in status["details"]["info_error"]

    def test_get_status_with_full_info_success(self, enabled_redis_config):
        """
        get_status returns full info when all info() calls succeed
        (lines 330-351).
        """
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        def info_side_effect(section=None):
            if section == "server":
                return {"redis_version": "7.0.0", "uptime_in_seconds": 12345}
            elif section == "memory":
                return {"used_memory_human": "10.5M"}
            elif section == "clients":
                return {"connected_clients": 5}
            return {}

        mock_client.info.side_effect = info_side_effect
        mock_redis.Redis.return_value = mock_client

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                status = client.get_status()

                assert status["status"] == "UP"
                assert status["mode"] == "LIVE"
                assert "healthy" in status["message"]
                assert status["details"]["version"] == "7.0.0"
                assert status["details"]["uptime_seconds"] == 12345
                assert status["details"]["connected_clients"] == 5
                assert status["details"]["used_memory_human"] == "10.5M"

    def test_get_status_unavailable_when_client_none_but_enabled(self, enabled_redis_config):
        """
        get_status returns UNAVAILABLE when client is None
        but config enabled (lines 312-325).
        """
        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            mock_redis = MagicMock()
            mock_redis.ConnectionPool.side_effect = Exception("Pool creation failed")

            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                client._client = None
                client._last_error = "Connection refused"

                status = client.get_status()

                assert status["status"] == "UNAVAILABLE"
                assert status["mode"] == "LIVE"
                assert "Connection refused" in status["message"]
                assert status["details"]["last_error"] == "Connection refused"


@pytest.mark.unit
class TestGetMetricsLivePath:
    """Test get_metrics() live metrics retrieval (lines 435-477)."""

    def test_get_metrics_live_success(self, enabled_redis_config):
        """get_metrics returns live metrics when connected (lines 435-473)."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        def info_side_effect(section=None):
            if section == "memory":
                return {
                    "used_memory": 2097152,
                    "used_memory_human": "2.00M",
                    "used_memory_peak_human": "3.00M",
                    "mem_fragmentation_ratio": 1.1,
                }
            elif section == "stats":
                return {
                    "total_connections_received": 100,
                    "total_commands_processed": 5000,
                    "instantaneous_ops_per_sec": 50,
                    "keyspace_hits": 4000,
                    "keyspace_misses": 1000,
                }
            elif section == "clients":
                return {"connected_clients": 3, "blocked_clients": 0}
            elif section == "keyspace":
                return {"db0": {"keys": 100, "expires": 50, "avg_ttl": 3600000}}
            return {}

        mock_client.info.side_effect = info_side_effect
        mock_redis.Redis.return_value = mock_client

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                metrics = client.get_metrics()

                assert metrics["status"] == "UP"
                assert metrics["mode"] == "LIVE"
                assert metrics["message"] == "Redis metrics retrieved successfully"
                assert metrics["metrics"] is not None

                memory = metrics["metrics"]["memory"]
                assert memory["used_memory_bytes"] == 2097152
                assert memory["used_memory_human"] == "2.00M"

                stats = metrics["metrics"]["stats"]
                assert stats["keyspace_hits"] == 4000
                assert stats["keyspace_misses"] == 1000
                assert stats["hit_rate_percent"] == 80.0

                clients = metrics["metrics"]["clients"]
                assert clients["connected_clients"] == 3

    def test_get_metrics_live_with_zero_hits(self, enabled_redis_config):
        """get_metrics handles zero hits/misses for hit rate calculation."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        def info_side_effect(section=None):
            if section == "memory":
                return {"used_memory": 0, "used_memory_human": "0B"}
            elif section == "stats":
                return {"keyspace_hits": 0, "keyspace_misses": 0}
            elif section == "clients":
                return {}
            elif section == "keyspace":
                return {}
            return {}

        mock_client.info.side_effect = info_side_effect
        mock_redis.Redis.return_value = mock_client

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                metrics = client.get_metrics()

                assert metrics["metrics"]["stats"]["hit_rate_percent"] == 0.0

    def test_get_metrics_live_failure(self, enabled_redis_config):
        """get_metrics returns DOWN when info() fails (lines 475-483)."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.info.side_effect = Exception("Redis connection lost")
        mock_redis.Redis.return_value = mock_client

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)
                metrics = client.get_metrics()

                assert metrics["status"] == "DOWN"
                assert metrics["mode"] == "LIVE"
                assert "Failed to retrieve" in metrics["message"]
                assert metrics["metrics"] is None


@pytest.mark.unit
class TestGetRedisClientForceNew:
    """Test get_redis_client() force_new parameter (line 498)."""

    def test_force_new_creates_fresh_instance(self, mock_config_manager, monkeypatch):
        """force_new=True always creates a new instance."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        from backend.redis_client import get_redis_client

        client1 = get_redis_client(mock_config_manager)
        client2 = get_redis_client(mock_config_manager, force_new=True)
        client3 = get_redis_client(mock_config_manager, force_new=True)

        assert client1 is not client2
        assert client2 is not client3
        assert client1 is not client3

    def test_force_new_replaces_global_instance(self, mock_config_manager, monkeypatch):
        """force_new=True replaces the global singleton."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.redis_client as redis_module
        from backend.redis_client import get_redis_client

        client1 = get_redis_client(mock_config_manager)
        assert redis_module._redis_client_instance is client1

        client2 = get_redis_client(mock_config_manager, force_new=True)
        assert redis_module._redis_client_instance is client2
        assert redis_module._redis_client_instance is not client1


@pytest.mark.unit
class TestIsAvailableWithPing:
    """Test is_available() when ping is called (line 498)."""

    def test_is_available_calls_ping_when_client_exists(self, enabled_redis_config):
        """is_available calls _ping when client exists and returns result."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                from backend.redis_client import RedisClient

                client = RedisClient(enabled_redis_config)

                result = client.is_available()

                assert result is True
                assert mock_client.ping.call_count >= 1

    def test_is_available_returns_false_when_ping_fails(self, enabled_redis_config):
        """is_available returns False when ping fails."""
        mock_redis = MagicMock()
        mock_pool = MagicMock()
        mock_redis.ConnectionPool.return_value = mock_pool

        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.Redis.return_value = mock_client

        connection_error = type("RedisConnectionError", (Exception,), {})

        with patch("backend.redis_client.REDIS_AVAILABLE", True):
            with patch("backend.redis_client.redis", mock_redis):
                with patch("backend.redis_client.RedisConnectionError", connection_error):
                    from backend.redis_client import RedisClient

                    client = RedisClient(enabled_redis_config)
                    mock_client.ping.side_effect = connection_error("Connection lost")

                    result = client.is_available()

                    assert result is False
