"""
Tests for CascorServiceAdapter — Phase 4 Canopy/CasCor decoupling.

Verifies that the adapter:
1. Exposes all methods/attributes required by main.py
2. Delegates REST calls to JuniperCascorClient
3. Returns graceful fallbacks on connection errors
4. _ServiceTrainingMonitor works correctly
5. Async WS relay broadcasts messages
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")

from backend.cascor_service_adapter import CascorServiceAdapter, _ServiceTrainingMonitor

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_client():
    """Create a mock JuniperCascorClient."""
    client = MagicMock()
    client.is_ready.return_value = True
    client.get_training_status.return_value = {"is_training": False, "status": "idle"}
    client.get_metrics.return_value = {"loss": 0.5, "accuracy": 0.8}
    client.get_metrics_history.return_value = {"history": [{"epoch": 1, "loss": 0.5}]}
    client.get_network.return_value = {"input_size": 2, "output_size": 1}
    client.get_topology.return_value = {"input_units": 2, "hidden_units": 0, "output_units": 1}
    client.get_statistics.return_value = {"total_weights": 3}
    client.get_dataset.return_value = {"num_samples": 100}
    client.create_network.return_value = {"status": "created"}
    client.start_training.return_value = {"status": "started"}
    client.stop_training.return_value = {"status": "stopped"}
    client.close.return_value = None
    return client


@pytest.fixture
def adapter(mock_client):
    """Create a CascorServiceAdapter with a mocked client."""
    a = CascorServiceAdapter(service_url="http://localhost:8200")
    a._client = mock_client
    a.training_monitor = _ServiceTrainingMonitor(mock_client)
    return a


# =========================================================================
# Interface compatibility — verify all required attributes/methods exist
# =========================================================================


class TestInterfaceCompatibility:
    """Verify the adapter exposes all methods and attributes used by main.py."""

    def test_has_network_property(self, adapter):
        assert hasattr(adapter, "network")

    def test_has_training_monitor(self, adapter):
        assert hasattr(adapter, "training_monitor")

    def test_has_training_stop_requested(self, adapter):
        assert hasattr(adapter, "_training_stop_requested")

    @pytest.mark.parametrize(
        "method_name",
        [
            "create_network",
            "start_training_background",
            "is_training_in_progress",
            "request_training_stop",
            "get_training_status",
            "get_network_data",
            "extract_network_topology",
            "get_network_topology",
            "get_dataset_info",
            "get_prediction_function",
            "install_monitoring_hooks",
            "start_monitoring_thread",
            "stop_monitoring",
            "restore_original_methods",
            "create_monitoring_callback",
            "get_remote_worker_status",
            "connect_remote_workers",
            "start_remote_workers",
            "stop_remote_workers",
            "disconnect_remote_workers",
            "shutdown",
        ],
    )
    def test_has_required_method(self, adapter, method_name):
        assert hasattr(adapter, method_name), f"Missing method: {method_name}"
        assert callable(getattr(adapter, method_name))


# =========================================================================
# REST delegation — verify methods call the client correctly
# =========================================================================


class TestRESTDelegation:
    """Verify adapter methods delegate to JuniperCascorClient."""

    def test_create_network(self, adapter, mock_client):
        config = {"input_size": 2, "output_size": 1}
        result = adapter.create_network(config)
        mock_client.create_network.assert_called_once_with(input_size=2, output_size=1)
        assert result == {"status": "created"}

    def test_create_network_none_config(self, adapter, mock_client):
        adapter.create_network(None)
        mock_client.create_network.assert_called_once_with()

    def test_start_training_background(self, adapter, mock_client):
        result = adapter.start_training_background()
        assert result is True
        mock_client.start_training.assert_called_once()

    def test_is_training_in_progress(self, adapter, mock_client):
        assert adapter.is_training_in_progress() is False
        mock_client.get_training_status.assert_called()

    def test_is_training_in_progress_when_training(self, adapter, mock_client):
        mock_client.get_training_status.return_value = {"is_training": True}
        assert adapter.is_training_in_progress() is True

    def test_request_training_stop(self, adapter, mock_client):
        assert adapter.request_training_stop() is True
        mock_client.stop_training.assert_called_once()

    def test_get_training_status(self, adapter, mock_client):
        result = adapter.get_training_status()
        assert result == {"is_training": False, "status": "idle"}

    def test_get_network_data(self, adapter, mock_client):
        result = adapter.get_network_data()
        mock_client.get_statistics.assert_called_once()
        assert result == {"total_weights": 3}

    def test_extract_network_topology(self, adapter, mock_client):
        result = adapter.extract_network_topology()
        mock_client.get_topology.assert_called_once()
        assert result["input_units"] == 2

    def test_get_network_topology_alias(self, adapter, mock_client):
        result = adapter.get_network_topology()
        assert result == adapter.extract_network_topology()

    def test_get_dataset_info(self, adapter, mock_client):
        result = adapter.get_dataset_info()
        mock_client.get_dataset.assert_called_once()
        assert result == {"num_samples": 100}

    def test_get_prediction_function_returns_none(self, adapter):
        assert adapter.get_prediction_function() is None


# =========================================================================
# Network property
# =========================================================================


class TestNetworkProperty:
    """Verify the network property returns sentinel or None."""

    def test_network_truthy_when_exists(self, adapter, mock_client):
        network = adapter.network
        assert network is not None
        assert bool(network) is True

    def test_network_none_when_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_network.side_effect = JuniperCascorConnectionError("no conn")
        assert adapter.network is None

    def test_network_none_when_empty_response(self, adapter, mock_client):
        mock_client.get_network.return_value = {}
        # Empty dict is falsy so should return None
        assert adapter.network is None


# =========================================================================
# _training_stop_requested
# =========================================================================


class TestTrainingStopRequested:
    def test_always_false(self, adapter):
        assert adapter._training_stop_requested is False


# =========================================================================
# No-op methods
# =========================================================================


class TestNoOpMethods:
    """Verify monitoring/worker stubs return expected values."""

    def test_install_monitoring_hooks(self, adapter):
        assert adapter.install_monitoring_hooks() is True

    def test_start_monitoring_thread(self, adapter):
        assert adapter.start_monitoring_thread(interval=2.0) is None

    def test_stop_monitoring(self, adapter):
        assert adapter.stop_monitoring() is None

    def test_restore_original_methods(self, adapter):
        assert adapter.restore_original_methods() is None

    def test_create_monitoring_callback(self, adapter):
        assert adapter.create_monitoring_callback("epoch_end", lambda: None) is None

    def test_get_remote_worker_status(self, adapter):
        status = adapter.get_remote_worker_status()
        assert status["available"] is False
        assert status["connected"] is False

    def test_connect_remote_workers(self, adapter):
        assert adapter.connect_remote_workers(("host", 5000), "key") is False

    def test_start_remote_workers(self, adapter):
        assert adapter.start_remote_workers(2) is False

    def test_stop_remote_workers(self, adapter):
        assert adapter.stop_remote_workers(10) is False

    def test_disconnect_remote_workers(self, adapter):
        assert adapter.disconnect_remote_workers() is False


# =========================================================================
# _ServiceTrainingMonitor
# =========================================================================


class TestServiceTrainingMonitor:
    """Verify the training monitor delegates to the client."""

    def test_is_training_false(self, mock_client):
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.is_training is False

    def test_is_training_true(self, mock_client):
        mock_client.get_training_status.return_value = {"is_training": True}
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.is_training is True

    def test_is_training_on_connection_error(self, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_status.side_effect = JuniperCascorConnectionError("fail")
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.is_training is False

    def test_get_current_metrics(self, mock_client):
        monitor = _ServiceTrainingMonitor(mock_client)
        metrics = monitor.get_current_metrics()
        assert metrics == {"loss": 0.5, "accuracy": 0.8}

    def test_get_current_metrics_on_error(self, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_metrics.side_effect = JuniperCascorConnectionError("fail")
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.get_current_metrics() == {}

    def test_get_recent_metrics(self, mock_client):
        monitor = _ServiceTrainingMonitor(mock_client)
        metrics = monitor.get_recent_metrics(50)
        mock_client.get_metrics_history.assert_called_with(count=50)
        assert isinstance(metrics, list)
        assert len(metrics) == 1

    def test_get_recent_metrics_on_error(self, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_metrics_history.side_effect = JuniperCascorConnectionError("fail")
        monitor = _ServiceTrainingMonitor(mock_client)
        assert monitor.get_recent_metrics(100) == []


# =========================================================================
# Error handling
# =========================================================================


class TestErrorHandling:
    """Verify graceful fallbacks when client raises exceptions."""

    def test_create_network_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.create_network.side_effect = JuniperCascorConnectionError("fail")
        result = adapter.create_network({"input_size": 2})
        assert "error" in result

    def test_start_training_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.start_training.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.start_training_background() is False

    def test_is_training_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_status.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.is_training_in_progress() is False

    def test_request_stop_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.stop_training.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.request_training_stop() is False

    def test_get_training_status_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_training_status.side_effect = JuniperCascorConnectionError("fail")
        result = adapter.get_training_status()
        assert result["is_training"] is False
        assert "error" in result

    def test_extract_topology_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_topology.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.extract_network_topology() is None

    def test_get_dataset_info_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_dataset.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.get_dataset_info() is None

    def test_get_network_data_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.get_statistics.side_effect = JuniperCascorConnectionError("fail")
        assert adapter.get_network_data() == {}


# =========================================================================
# Async connect
# =========================================================================


class TestAsyncConnect:
    """Verify async connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_success(self, adapter, mock_client):
        result = await adapter.connect()
        assert result is True
        mock_client.is_ready.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_not_ready(self, adapter, mock_client):
        mock_client.is_ready.return_value = False
        result = await adapter.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_on_error(self, adapter, mock_client):
        from juniper_cascor_client.exceptions import JuniperCascorConnectionError

        mock_client.is_ready.side_effect = JuniperCascorConnectionError("fail")
        result = await adapter.connect()
        assert result is False


# =========================================================================
# Shutdown
# =========================================================================


class TestShutdown:
    """Verify shutdown closes the client."""

    def test_shutdown_closes_client(self, adapter, mock_client):
        adapter.shutdown()
        mock_client.close.assert_called_once()

    def test_shutdown_handles_error(self, adapter, mock_client):
        mock_client.close.side_effect = Exception("close failed")
        # Should not raise
        adapter.shutdown()


# =========================================================================
# WebSocket URL derivation
# =========================================================================


class TestWebSocketURL:
    def test_ws_url_from_http(self):
        adapter = CascorServiceAdapter(service_url="http://localhost:8200")
        assert adapter._ws_url == "ws://localhost:8200"

    def test_ws_url_from_https(self):
        adapter = CascorServiceAdapter(service_url="https://cascor.example.com")
        assert adapter._ws_url == "wss://cascor.example.com"
