#!/usr/bin/env python
"""
Unit tests for CassandraClient (P3-7).

Tests:
- Disabled by config: returns DISABLED status
- Driver missing: mocks Cluster=None, returns DISABLED
- Demo mode: returns UP with DEMO mode and synthetic cluster data
- Connection failure: mocks connection error, returns UNAVAILABLE
- get_status() returns proper structure with hosts
- get_metrics() returns proper structure with keyspaces
- close() cleanup
- Singleton pattern via get_cassandra_client()
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))


@pytest.fixture
def mock_config_manager():
    """Create mock ConfigManager."""
    mock_cm = Mock()
    mock_cm.get = Mock(
        side_effect=lambda key, default=None: {
            "cassandra.enabled": False,
            "cassandra.contact_points": ["127.0.0.1"],
            "cassandra.port": 9042,
            "cassandra.keyspace": "test_keyspace",
            "cassandra.username": None,
            "cassandra.password": None,
            "cassandra.connect_timeout": 10,
        }.get(key, default)
    )
    return mock_cm


@pytest.fixture
def enabled_config_manager():
    """Create mock ConfigManager with Cassandra enabled."""
    mock_cm = Mock()
    mock_cm.get = Mock(
        side_effect=lambda key, default=None: {
            "cassandra.enabled": True,
            "cassandra.contact_points": ["192.168.1.100"],
            "cassandra.port": 9042,
            "cassandra.keyspace": "juniper_canopy",
            "cassandra.username": "testuser",
            "cassandra.password": "testpass",
            "cassandra.connect_timeout": 5,
        }.get(key, default)
    )
    return mock_cm


@pytest.fixture(autouse=True)
def reset_cassandra_singleton():
    """Reset the Cassandra client singleton before each test."""
    import backend.cassandra_client as cc_module

    cc_module._cassandra_client_instance = None
    yield
    cc_module._cassandra_client_instance = None


class TestCassandraClientDisabled:
    """Test CassandraClient when disabled by config."""

    @pytest.mark.unit
    def test_disabled_by_config_returns_disabled_status(self, mock_config_manager, monkeypatch):
        """Should return DISABLED status when cassandra.enabled is False."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        from backend.cassandra_client import CassandraClient

        client = CassandraClient(config_manager=mock_config_manager)
        status = client.get_status()

        assert status["status"] == "DISABLED"
        assert status["mode"] == "DISABLED"
        assert "disabled by configuration" in status["message"].lower()
        assert "timestamp" in status
        assert "details" in status

    @pytest.mark.unit
    def test_disabled_status_details_contains_config_info(self, mock_config_manager, monkeypatch):
        """Disabled status should include config key/value in details."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        from backend.cassandra_client import CassandraClient

        client = CassandraClient(config_manager=mock_config_manager)
        status = client.get_status()

        assert status["details"]["config_key"] == "cassandra.enabled"
        assert status["details"]["config_value"] is False

    @pytest.mark.unit
    def test_disabled_metrics_returns_empty_metrics(self, mock_config_manager, monkeypatch):
        """get_metrics should return empty metrics when disabled."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        from backend.cassandra_client import CassandraClient

        client = CassandraClient(config_manager=mock_config_manager)
        metrics = client.get_metrics()

        assert metrics["status"] == "DISABLED"
        assert metrics["mode"] == "DISABLED"
        assert metrics["metrics"] == {}


class TestCassandraClientDriverMissing:
    """Test CassandraClient when Cassandra driver is not installed."""

    @pytest.mark.unit
    def test_driver_missing_returns_unavailable_status(self, enabled_config_manager, monkeypatch):
        """Should return UNAVAILABLE when driver is not available."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        original_available = cc_module.CASSANDRA_AVAILABLE
        cc_module.CASSANDRA_AVAILABLE = False

        try:
            client = cc_module.CassandraClient(config_manager=enabled_config_manager)
            status = client.get_status()

            assert status["status"] == "UNAVAILABLE"
            assert status["mode"] == "LIVE"
            assert "driver not installed" in status["message"].lower()
            assert status["details"]["driver_available"] is False
        finally:
            cc_module.CASSANDRA_AVAILABLE = original_available

    @pytest.mark.unit
    def test_driver_missing_metrics_returns_unavailable(self, enabled_config_manager, monkeypatch):
        """get_metrics should return UNAVAILABLE when driver is missing."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        original_available = cc_module.CASSANDRA_AVAILABLE
        cc_module.CASSANDRA_AVAILABLE = False

        try:
            client = cc_module.CassandraClient(config_manager=enabled_config_manager)
            metrics = client.get_metrics()

            assert metrics["status"] == "UNAVAILABLE"
            assert metrics["metrics"] == {}
        finally:
            cc_module.CASSANDRA_AVAILABLE = original_available


class TestCassandraClientDemoMode:
    """Test CassandraClient in demo mode."""

    @pytest.mark.unit
    def test_demo_mode_returns_up_status(self, mock_config_manager, monkeypatch):
        """Should return UP status in demo mode."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        status = client.get_status()

        assert status["status"] == "UP"
        assert status["mode"] == "DEMO"
        assert "demo mode" in status["message"].lower()

    @pytest.mark.unit
    def test_demo_mode_returns_synthetic_cluster_data(self, mock_config_manager, monkeypatch):
        """Demo mode should return synthetic cluster information."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        status = client.get_status()

        details = status["details"]
        assert "contact_points" in details
        assert len(details["contact_points"]) > 0
        assert "hosts" in details
        assert len(details["hosts"]) > 0
        assert "cluster_name" in details
        assert "protocol_version" in details

    @pytest.mark.unit
    def test_demo_mode_hosts_have_required_fields(self, mock_config_manager, monkeypatch):
        """Demo mode hosts should have address, rack, and is_up."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        status = client.get_status()

        hosts = status["details"]["hosts"]
        for host in hosts:
            assert "address" in host
            assert "rack" in host
            assert "is_up" in host

    @pytest.mark.unit
    def test_demo_mode_metrics_returns_synthetic_data(self, mock_config_manager, monkeypatch):
        """Demo mode should return synthetic metrics data."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        metrics = client.get_metrics()

        assert metrics["status"] == "UP"
        assert metrics["mode"] == "DEMO"
        assert "keyspaces" in metrics["metrics"]
        assert len(metrics["metrics"]["keyspaces"]) > 0

    @pytest.mark.unit
    def test_demo_mode_keyspaces_have_tables(self, mock_config_manager, monkeypatch):
        """Demo mode keyspaces should include table information."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        metrics = client.get_metrics()

        keyspaces = metrics["metrics"]["keyspaces"]
        for ks in keyspaces:
            assert "name" in ks
            assert "replication_strategy" in ks
            assert "tables" in ks

    @pytest.mark.unit
    def test_demo_mode_cluster_stats(self, mock_config_manager, monkeypatch):
        """Demo mode should include cluster statistics."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        metrics = client.get_metrics()

        cluster_stats = metrics["metrics"]["cluster_stats"]
        assert "total_nodes" in cluster_stats
        assert "live_nodes" in cluster_stats


class TestCassandraClientConnectionFailure:
    """Test CassandraClient connection failure handling."""

    @pytest.mark.unit
    def test_connection_failure_returns_unavailable(self, enabled_config_manager, monkeypatch):
        """Should return UNAVAILABLE when connection fails."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            with patch.object(cc_module, "Cluster") as mock_cluster:
                mock_cluster.side_effect = Exception("Connection refused")

                client = cc_module.CassandraClient(config_manager=enabled_config_manager)
                status = client.get_status()

                assert status["status"] == "UNAVAILABLE"
                assert status["mode"] == "LIVE"
                assert "unable to connect" in status["message"].lower()

    @pytest.mark.unit
    def test_try_connect_returns_false_on_exception(self, enabled_config_manager, monkeypatch):
        """_try_connect should return False when connection raises exception."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            with patch.object(cc_module, "Cluster") as mock_cluster:
                mock_cluster.side_effect = RuntimeError("Timeout connecting to cluster")

                client = cc_module.CassandraClient(config_manager=enabled_config_manager)

                result = client._try_connect()
                assert result is False
                assert client._cluster is None
                assert client._session is None


class TestCassandraClientStatusStructure:
    """Test get_status() returns proper structure."""

    @pytest.mark.unit
    def test_status_has_required_fields(self, mock_config_manager, monkeypatch):
        """Status response should have all required fields."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        status = client.get_status()

        required_fields = ["status", "mode", "message", "timestamp", "details"]
        for field in required_fields:
            assert field in status, f"Missing field: {field}"

    @pytest.mark.unit
    def test_status_cached_within_ttl(self, mock_config_manager, monkeypatch):
        """Status should be cached within TTL."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)

        status1 = client.get_status()
        status2 = client.get_status()

        assert status1["timestamp"] == status2["timestamp"]


class TestCassandraClientMetricsStructure:
    """Test get_metrics() returns proper structure."""

    @pytest.mark.unit
    def test_metrics_has_required_fields(self, mock_config_manager, monkeypatch):
        """Metrics response should have all required fields."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        metrics = client.get_metrics()

        required_fields = ["status", "mode", "message", "timestamp", "metrics"]
        for field in required_fields:
            assert field in metrics, f"Missing field: {field}"


class TestCassandraClientClose:
    """Test close() cleanup."""

    @pytest.mark.unit
    def test_close_cleans_up_resources(self, mock_config_manager, monkeypatch):
        """close() should clean up cluster and session."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            with patch.object(cc_module, "Cluster") as mock_cluster_cls:
                mock_cluster = Mock()
                mock_session = Mock()
                mock_session.is_shutdown = False
                mock_cluster.connect.return_value = mock_session
                mock_cluster_cls.return_value = mock_cluster

                client = cc_module.CassandraClient(config_manager=mock_config_manager)
                client._cluster = mock_cluster
                client._session = mock_session

                client.close()

                mock_cluster.shutdown.assert_called_once()
                assert client._cluster is None
                assert client._session is None

    @pytest.mark.unit
    def test_close_handles_shutdown_exception(self, mock_config_manager, monkeypatch):
        """close() should handle exception during shutdown."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)

        mock_cluster = Mock()
        mock_cluster.shutdown.side_effect = Exception("Shutdown error")
        client._cluster = mock_cluster
        client._session = Mock()

        client.close()

        assert client._cluster is None
        assert client._session is None


class TestCassandraClientSingleton:
    """Test singleton pattern via get_cassandra_client()."""

    @pytest.mark.unit
    def test_get_cassandra_client_returns_same_instance(self, mock_config_manager, monkeypatch):
        """get_cassandra_client should return the same instance."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client1 = cc_module.get_cassandra_client(config_manager=mock_config_manager)
        client2 = cc_module.get_cassandra_client(config_manager=mock_config_manager)

        assert client1 is client2

    @pytest.mark.unit
    def test_get_cassandra_client_creates_instance_with_config(self, monkeypatch):
        """get_cassandra_client should use provided config_manager."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_cm = Mock()
        mock_cm.get = Mock(return_value=None)

        client = cc_module.get_cassandra_client(config_manager=mock_cm)

        assert client is not None
        assert cc_module._cassandra_client_instance is client


class TestCassandraClientLiveStatus:
    """Test live cluster status extraction."""

    @pytest.mark.unit
    def test_live_status_extracts_host_info(self, enabled_config_manager, monkeypatch):
        """Live status should extract host information from cluster metadata."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_host = Mock()
        mock_host.address = "192.168.1.100"
        mock_host.rack = "rack1"
        mock_host.datacenter = "dc1"
        mock_host.is_up = True

        mock_metadata = Mock()
        mock_metadata.cluster_name = "TestCluster"
        mock_metadata.all_hosts.return_value = [mock_host]

        mock_cluster = Mock()
        mock_cluster.metadata = mock_metadata
        mock_cluster.protocol_version = 4

        mock_session = Mock()
        mock_session.is_shutdown = False

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = mock_session

        status = client._get_live_status()

        assert status["status"] == "UP"
        assert status["mode"] == "LIVE"
        assert len(status["details"]["hosts"]) == 1
        assert status["details"]["hosts"][0]["address"] == "192.168.1.100"


class TestCassandraClientIsConnected:
    """Test _is_connected() method."""

    @pytest.mark.unit
    def test_is_connected_returns_false_when_no_session(self, mock_config_manager, monkeypatch):
        """_is_connected should return False when session is None."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        client._session = None

        assert client._is_connected() is False

    @pytest.mark.unit
    def test_is_connected_returns_true_when_session_active(self, mock_config_manager, monkeypatch):
        """_is_connected should return True when session is active."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        mock_session = Mock()
        mock_session.is_shutdown = False
        client._session = mock_session

        assert client._is_connected() is True

    @pytest.mark.unit
    def test_is_connected_returns_false_when_session_shutdown(self, mock_config_manager, monkeypatch):
        """_is_connected should return False when session is shutdown."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        mock_session = Mock()
        mock_session.is_shutdown = True
        client._session = mock_session

        assert client._is_connected() is False

    @pytest.mark.unit
    def test_is_connected_returns_false_on_exception(self, mock_config_manager, monkeypatch):
        """_is_connected should return False when accessing is_shutdown raises exception."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        client = cc_module.CassandraClient(config_manager=mock_config_manager)
        mock_session = Mock()
        type(mock_session).is_shutdown = property(lambda self: (_ for _ in ()).throw(RuntimeError("Connection lost")))
        client._session = mock_session

        assert client._is_connected() is False


class TestCassandraClientTryConnectWithAuth:
    """Test _try_connect() with authentication."""

    @pytest.mark.unit
    def test_try_connect_with_auth_provider(self, enabled_config_manager, monkeypatch):
        """_try_connect should use PlainTextAuthProvider when username/password configured."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_session = Mock()
        mock_session.is_shutdown = False
        mock_cluster_instance = Mock()
        mock_cluster_instance.connect.return_value = mock_session

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            with patch.object(cc_module, "Cluster") as mock_cluster_cls:
                with patch.object(cc_module, "PlainTextAuthProvider") as mock_auth_cls:
                    mock_auth_instance = Mock()
                    mock_auth_cls.return_value = mock_auth_instance
                    mock_cluster_cls.return_value = mock_cluster_instance

                    cc_module.CassandraClient(config_manager=enabled_config_manager)

                    mock_auth_cls.assert_called_once_with(
                        username="testuser",
                        password="testpass",
                    )
                    mock_cluster_cls.assert_called_once()
                    call_kwargs = mock_cluster_cls.call_args[1]
                    assert call_kwargs["auth_provider"] is mock_auth_instance

    @pytest.mark.unit
    def test_try_connect_sets_keyspace(self, enabled_config_manager, monkeypatch):
        """_try_connect should set keyspace after connecting."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_session = Mock()
        mock_session.is_shutdown = False
        mock_cluster_instance = Mock()
        mock_cluster_instance.connect.return_value = mock_session

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            with patch.object(cc_module, "Cluster") as mock_cluster_cls:
                with patch.object(cc_module, "PlainTextAuthProvider"):
                    mock_cluster_cls.return_value = mock_cluster_instance

                    cc_module.CassandraClient(config_manager=enabled_config_manager)

                    mock_session.set_keyspace.assert_called_once_with("juniper_canopy")

    @pytest.mark.unit
    def test_try_connect_returns_false_when_driver_unavailable(self, enabled_config_manager, monkeypatch):
        """_try_connect should return False when CASSANDRA_AVAILABLE is False."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        original_available = cc_module.CASSANDRA_AVAILABLE
        cc_module.CASSANDRA_AVAILABLE = False

        try:
            client = cc_module.CassandraClient(config_manager=enabled_config_manager)
            result = client._try_connect()
            assert result is False
        finally:
            cc_module.CASSANDRA_AVAILABLE = original_available


class TestCassandraClientGetStatusRetryConnect:
    """Test get_status() retry connect flow."""

    @pytest.mark.unit
    def test_get_status_retries_connect_when_not_connected(self, enabled_config_manager, monkeypatch):
        """get_status should try to connect when not connected and return live status on success."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_host = Mock()
        mock_host.address = "192.168.1.100"
        mock_host.rack = "rack1"
        mock_host.datacenter = "dc1"
        mock_host.is_up = True

        mock_metadata = Mock()
        mock_metadata.cluster_name = "TestCluster"
        mock_metadata.all_hosts.return_value = [mock_host]

        mock_cluster_instance = Mock()
        mock_cluster_instance.metadata = mock_metadata
        mock_cluster_instance.protocol_version = 4

        mock_session = Mock()
        mock_session.is_shutdown = False

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            with patch.object(cc_module, "Cluster") as mock_cluster_cls:
                with patch.object(cc_module, "PlainTextAuthProvider"):
                    mock_cluster_cls.return_value = mock_cluster_instance
                    mock_cluster_instance.connect.return_value = mock_session

                    client = cc_module.CassandraClient(config_manager=enabled_config_manager)
                    client._cluster = None
                    client._session = None
                    client._cached_status = None

                    status = client.get_status()

                    assert status["status"] == "UP"
                    assert status["mode"] == "LIVE"


class TestCassandraClientGetLiveStatusException:
    """Test _get_live_status() exception handling."""

    @pytest.mark.unit
    def test_get_live_status_returns_down_on_exception(self, enabled_config_manager, monkeypatch):
        """_get_live_status should return DOWN status when exception occurs."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_cluster = Mock()
        type(mock_cluster).metadata = property(lambda self: (_ for _ in ()).throw(RuntimeError("Cluster error")))

        mock_session = Mock()
        mock_session.is_shutdown = False

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = mock_session

        status = client._get_live_status()

        assert status["status"] == "DOWN"
        assert status["mode"] == "LIVE"
        assert "error" in status["message"].lower()
        assert "error" in status["details"]

    @pytest.mark.unit
    def test_get_live_status_includes_error_details(self, enabled_config_manager, monkeypatch):
        """_get_live_status error response should include contact points and port."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_cluster = Mock()
        type(mock_cluster).metadata = property(lambda self: (_ for _ in ()).throw(ValueError("Test error")))

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = Mock()

        status = client._get_live_status()

        assert status["details"]["contact_points"] == ["192.168.1.100"]
        assert status["details"]["port"] == 9042
        assert "Test error" in status["details"]["error"]


class TestCassandraClientGetLiveMetrics:
    """Test _get_live_metrics() with cluster metadata."""

    @pytest.mark.unit
    def test_get_live_metrics_extracts_keyspace_info(self, enabled_config_manager, monkeypatch):
        """_get_live_metrics should extract keyspace information from cluster metadata."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_column = Mock()
        mock_column.name = "id"

        mock_table = Mock()
        mock_table.columns = {"id": mock_column, "name": Mock()}
        mock_table.partition_key = [mock_column]
        mock_table.clustering_key = []

        mock_replication = Mock()
        mock_replication.replication_factor = 3

        mock_keyspace = Mock()
        mock_keyspace.replication_strategy = mock_replication
        mock_keyspace.tables = {"users": mock_table}

        mock_host = Mock()
        mock_host.is_up = True

        mock_metadata = Mock()
        mock_metadata.keyspaces = {
            "juniper_canopy": mock_keyspace,
            "system": Mock(),
        }
        mock_metadata.all_hosts.return_value = [mock_host]

        mock_cluster = Mock()
        mock_cluster.metadata = mock_metadata

        mock_session = Mock()
        mock_session.is_shutdown = False

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = mock_session

        metrics = client._get_live_metrics()

        assert metrics["status"] == "UP"
        assert metrics["mode"] == "LIVE"
        keyspaces = metrics["metrics"]["keyspaces"]
        assert len(keyspaces) == 1
        assert keyspaces[0]["name"] == "juniper_canopy"
        assert keyspaces[0]["replication_factor"] == 3
        assert len(keyspaces[0]["tables"]) == 1
        assert keyspaces[0]["tables"][0]["name"] == "users"
        assert keyspaces[0]["tables"][0]["columns"] == 2

    @pytest.mark.unit
    def test_get_live_metrics_counts_live_nodes(self, enabled_config_manager, monkeypatch):
        """_get_live_metrics should count total and live nodes."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_host1 = Mock()
        mock_host1.is_up = True
        mock_host2 = Mock()
        mock_host2.is_up = False
        mock_host3 = Mock()
        mock_host3.is_up = True

        mock_metadata = Mock()
        mock_metadata.keyspaces = {}
        mock_metadata.all_hosts.return_value = [mock_host1, mock_host2, mock_host3]

        mock_cluster = Mock()
        mock_cluster.metadata = mock_metadata

        mock_session = Mock()
        mock_session.is_shutdown = False

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = mock_session

        metrics = client._get_live_metrics()

        assert metrics["metrics"]["cluster_stats"]["total_nodes"] == 3
        assert metrics["metrics"]["cluster_stats"]["live_nodes"] == 2

    @pytest.mark.unit
    def test_get_live_metrics_returns_down_on_exception(self, enabled_config_manager, monkeypatch):
        """_get_live_metrics should return DOWN status when exception occurs."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_cluster = Mock()
        type(mock_cluster).metadata = property(lambda self: (_ for _ in ()).throw(RuntimeError("Metadata error")))

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = Mock()

        metrics = client._get_live_metrics()

        assert metrics["status"] == "DOWN"
        assert metrics["mode"] == "LIVE"
        assert "error" in metrics["message"].lower()
        assert metrics["metrics"] == {}

    @pytest.mark.unit
    def test_get_live_metrics_skips_system_keyspaces(self, enabled_config_manager, monkeypatch):
        """_get_live_metrics should skip system keyspaces."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_metadata = Mock()
        mock_metadata.keyspaces = {
            "system": Mock(),
            "system_schema": Mock(),
            "system_auth": Mock(),
        }
        mock_metadata.all_hosts.return_value = []

        mock_cluster = Mock()
        mock_cluster.metadata = mock_metadata

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = Mock()

        metrics = client._get_live_metrics()

        assert len(metrics["metrics"]["keyspaces"]) == 0

    @pytest.mark.unit
    def test_get_live_metrics_handles_no_replication_factor(self, enabled_config_manager, monkeypatch):
        """_get_live_metrics should handle keyspace without replication_factor attribute."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        mock_replication = Mock(spec=[])

        mock_keyspace = Mock()
        mock_keyspace.replication_strategy = mock_replication
        mock_keyspace.tables = {}

        mock_metadata = Mock()
        mock_metadata.keyspaces = {"my_keyspace": mock_keyspace}
        mock_metadata.all_hosts.return_value = []

        mock_cluster = Mock()
        mock_cluster.metadata = mock_metadata

        client = cc_module.CassandraClient(config_manager=enabled_config_manager)
        client._cluster = mock_cluster
        client._session = Mock()

        metrics = client._get_live_metrics()

        assert len(metrics["metrics"]["keyspaces"]) == 1
        assert metrics["metrics"]["keyspaces"][0]["replication_factor"] is None


class TestCassandraClientGetMetricsNotConnected:
    """Test get_metrics() when not connected."""

    @pytest.mark.unit
    def test_get_metrics_returns_unavailable_when_not_connected(self, enabled_config_manager, monkeypatch):
        """get_metrics should return UNAVAILABLE when not connected."""
        monkeypatch.delenv("CASCOR_DEMO_MODE", raising=False)

        import backend.cassandra_client as cc_module

        cc_module._cassandra_client_instance = None

        with patch.object(cc_module, "CASSANDRA_AVAILABLE", True):
            client = cc_module.CassandraClient(config_manager=enabled_config_manager)
            client._cluster = None
            client._session = None

            metrics = client.get_metrics()

            assert metrics["status"] == "UNAVAILABLE"
            assert metrics["mode"] == "LIVE"
            assert "not connected" in metrics["message"].lower()
            assert metrics["metrics"] == {}
