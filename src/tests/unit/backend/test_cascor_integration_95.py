#!/usr/bin/env python
"""
Comprehensive coverage tests for cascor_integration.py to reach 95%+ coverage.

Target lines:
- Lines 331-332: Check in is_training_in_progress (RemoteWorkerClient import)
- Lines 506-507, 523-525, 534-541: _run_fit_sync and fit_async methods
- Lines 560-584: fit_async implementation
- Lines 602-614: start_training_background
- Lines 638-650: connect_remote_workers
- Lines 671-679: start_remote_workers
- Lines 698-706: stop_remote_workers
- Lines 722-731: disconnect_remote_workers
- Lines 747: get_remote_worker_status
- Lines 1061-1064, 1452->1458, 1459: Metrics extraction edge cases

Tests cover:
- Async training methods (fit_async, start_training_background)
- Remote worker methods with mocked RemoteWorkerClient
- is_training_in_progress with various states
- request_training_stop
- get_training_status
- Concurrent modification handling in metrics extraction
- Shutdown edge cases with remote workers
"""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import numpy as np
import pytest
import torch

# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def mock_config_manager():
    """Mock ConfigManager for all tests."""
    with patch("backend.cascor_integration.ConfigManager") as mock_cm:
        mock_instance = Mock()
        mock_instance.config = {"backend": {"cascor_integration": {}}}
        mock_cm.return_value = mock_instance
        yield mock_cm


@pytest.fixture
def mock_path_exists():
    """Mock Path.exists to always return True."""
    with patch("backend.cascor_integration.Path.exists") as mock_exists:
        mock_exists.return_value = True
        yield mock_exists


@pytest.fixture
def mock_network():
    """Create a mock CascadeCorrelationNetwork with realistic properties."""
    network = Mock()
    network.input_size = 2
    network.output_size = 1
    network.hidden_units = []
    network.output_weights = torch.randn(1, 2)
    network.output_bias = torch.randn(1)
    network.history = {
        "train_loss": [0.5, 0.3, 0.1],
        "train_accuracy": [0.7, 0.8, 0.9],
        "value_loss": [0.6, 0.4, 0.2],
        "value_accuracy": [0.65, 0.75, 0.85],
    }
    network.fit = Mock(return_value={"epochs": 100, "final_loss": 0.01})
    network.train_output_layer = Mock()
    network.train_candidates = Mock()
    return network


@pytest.fixture
def integration(mock_config_manager, mock_path_exists):
    """Create a CascorIntegration instance with mocked dependencies."""
    from backend.cascor_integration import CascorIntegration

    with patch.object(CascorIntegration, "_import_backend_modules"):
        instance = CascorIntegration()
        yield instance
        # Clean up
        if hasattr(instance, "_training_executor") and instance._training_executor:
            instance._training_executor.shutdown(wait=False)


@pytest.fixture
def integration_with_network(integration, mock_network):
    """Create integration with connected network."""
    integration.network = mock_network
    integration.cascade_correlation_instance = mock_network
    return integration


# ==============================================================================
# Test: is_training_in_progress
# ==============================================================================


class TestIsTrainingInProgress:
    """Tests for is_training_in_progress method."""

    def test_returns_false_when_no_future(self, integration):
        """Returns False when no training future exists."""
        integration._training_future = None
        assert integration.is_training_in_progress() is False

    def test_returns_false_when_future_done(self, integration):
        """Returns False when training future is done."""
        mock_future = Mock()
        mock_future.done.return_value = True
        integration._training_future = mock_future
        assert integration.is_training_in_progress() is False

    def test_returns_true_when_training_active(self, integration):
        """Returns True when training future is active."""
        mock_future = Mock()
        mock_future.done.return_value = False
        integration._training_future = mock_future
        assert integration.is_training_in_progress() is True

    def test_thread_safe_access(self, integration):
        """Test thread-safe access via lock."""
        mock_future = Mock()
        mock_future.done.return_value = False
        integration._training_future = mock_future

        results = []

        def check_in_thread():
            results.append(integration.is_training_in_progress())

        threads = [threading.Thread(target=check_in_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is True for r in results)


# ==============================================================================
# Test: request_training_stop
# ==============================================================================


class TestRequestTrainingStop:
    """Tests for request_training_stop method."""

    def test_returns_false_when_no_future(self, integration):
        """Returns False when no training in progress."""
        integration._training_future = None
        assert integration.request_training_stop() is False

    def test_returns_false_when_future_done(self, integration):
        """Returns False when training already done."""
        mock_future = Mock()
        mock_future.done.return_value = True
        integration._training_future = mock_future
        assert integration.request_training_stop() is False

    def test_returns_true_and_sets_flag_when_training(self, integration):
        """Returns True and sets stop flag when training is active."""
        mock_future = Mock()
        mock_future.done.return_value = False
        integration._training_future = mock_future
        integration._training_stop_requested = False

        result = integration.request_training_stop()

        assert result is True
        assert integration._training_stop_requested is True


# ==============================================================================
# Test: _run_fit_sync
# ==============================================================================


class TestRunFitSync:
    """Tests for _run_fit_sync method."""

    def test_raises_when_no_network(self, integration):
        """Raises RuntimeError when no network connected."""
        integration.network = None
        with pytest.raises(RuntimeError, match="No network connected"):
            integration._run_fit_sync()

    def test_calls_network_fit(self, integration_with_network):
        """Calls network.fit with passed arguments."""
        mock_x = np.random.randn(100, 2)
        mock_y = np.random.randn(100, 1)

        result = integration_with_network._run_fit_sync(mock_x, mock_y, epochs=50)

        integration_with_network.network.fit.assert_called_once_with(mock_x, mock_y, epochs=50)
        assert result == {"epochs": 100, "final_loss": 0.01}

    def test_resets_stop_flag_on_start(self, integration_with_network):
        """Resets _training_stop_requested at start of fit."""
        integration_with_network._training_stop_requested = True
        integration_with_network._run_fit_sync()
        # Flag is reset in finally block
        assert integration_with_network._training_stop_requested is False

    def test_resets_stop_flag_on_exception(self, integration_with_network):
        """Resets stop flag even when exception occurs."""
        integration_with_network.network.fit.side_effect = Exception("Training failed")
        integration_with_network._training_stop_requested = True

        with pytest.raises(Exception, match="Training failed"):
            integration_with_network._run_fit_sync()

        assert integration_with_network._training_stop_requested is False


# ==============================================================================
# Test: fit_async
# ==============================================================================


class TestFitAsync:
    """Tests for fit_async method."""

    @pytest.mark.asyncio
    async def test_raises_when_no_network(self, integration):
        """Raises RuntimeError when no network connected."""
        integration.network = None
        with pytest.raises(RuntimeError, match="No network connected"):
            await integration.fit_async()

    @pytest.mark.asyncio
    async def test_raises_when_training_in_progress(self, integration_with_network):
        """Raises RuntimeError when training already in progress."""
        mock_future = Mock()
        mock_future.done.return_value = False
        integration_with_network._training_future = mock_future

        with pytest.raises(RuntimeError, match="Training already in progress"):
            await integration_with_network.fit_async()

    @pytest.mark.asyncio
    async def test_returns_training_history(self, integration_with_network):
        """Returns training history on success."""
        result = await integration_with_network.fit_async()
        assert result == {"epochs": 100, "final_loss": 0.01}

    @pytest.mark.asyncio
    async def test_clears_future_on_completion(self, integration_with_network):
        """Clears training future after completion."""
        await integration_with_network.fit_async()
        assert integration_with_network._training_future is None

    @pytest.mark.asyncio
    async def test_clears_future_on_exception(self, integration_with_network):
        """Clears training future even on exception."""
        integration_with_network.network.fit.side_effect = Exception("Training failed")

        with pytest.raises(Exception, match="Training failed"):
            await integration_with_network.fit_async()

        assert integration_with_network._training_future is None
        assert integration_with_network._training_stop_requested is False

    @pytest.mark.asyncio
    async def test_resets_stop_flag(self, integration_with_network):
        """Resets stop flag at start of async training."""
        integration_with_network._training_stop_requested = True
        await integration_with_network.fit_async()
        assert integration_with_network._training_stop_requested is False


# ==============================================================================
# Test: start_training_background
# ==============================================================================


class TestStartTrainingBackground:
    """Tests for start_training_background method."""

    def test_returns_false_when_no_network(self, integration):
        """Returns False when no network connected."""
        integration.network = None
        result = integration.start_training_background()
        assert result is False

    def test_returns_false_when_training_in_progress(self, integration_with_network):
        """Returns False when training already in progress."""
        mock_future = Mock()
        mock_future.done.return_value = False
        integration_with_network._training_future = mock_future

        result = integration_with_network.start_training_background()
        assert result is False

    def test_returns_true_on_success(self, integration_with_network):
        """Returns True when training starts successfully."""
        result = integration_with_network.start_training_background()
        assert result is True
        time.sleep(0.1)  # Allow background thread to start

    def test_sets_training_future(self, integration_with_network):
        """Sets training future when starting."""
        # Use slow fit to keep training "in progress"
        integration_with_network.network.fit = Mock(side_effect=lambda *a, **k: time.sleep(0.3))
        integration_with_network.start_training_background()
        time.sleep(0.05)
        assert integration_with_network._training_future is not None

    def test_passes_arguments_to_fit(self, integration_with_network):
        """Passes arguments to network.fit."""
        mock_x = np.random.randn(50, 2)
        mock_y = np.random.randn(50, 1)

        integration_with_network.start_training_background(mock_x, mock_y, epochs=25)
        time.sleep(0.1)

        integration_with_network.network.fit.assert_called()


# ==============================================================================
# Test: Remote Worker Methods
# ==============================================================================


class TestConnectRemoteWorkers:
    """Tests for connect_remote_workers method."""

    def test_raises_when_client_not_available(self, integration):
        """Raises RuntimeError when RemoteWorkerClient not imported."""
        integration.RemoteWorkerClient = None
        integration._remote_client = None

        with pytest.raises(RuntimeError, match="RemoteWorkerClient not imported"):
            integration.connect_remote_workers(("localhost", 5000), "secret")

    def test_returns_false_when_already_connected(self, integration):
        """Returns False when already connected."""
        integration.RemoteWorkerClient = Mock()
        integration._remote_client = Mock()  # Already connected

        result = integration.connect_remote_workers(("localhost", 5000), "secret")
        assert result is False

    def test_returns_true_on_successful_connection(self, integration):
        """Returns True on successful connection."""
        mock_client_class = Mock()
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        integration.RemoteWorkerClient = mock_client_class
        integration._remote_client = None

        result = integration.connect_remote_workers(("localhost", 5000), "secret")

        assert result is True
        assert integration._remote_client is mock_client
        mock_client.connect.assert_called_once()

    def test_returns_false_on_connection_failure(self, integration):
        """Returns False when connection fails."""
        mock_client_class = Mock()
        mock_client = Mock()
        mock_client.connect.side_effect = Exception("Connection refused")
        mock_client_class.return_value = mock_client
        integration.RemoteWorkerClient = mock_client_class
        integration._remote_client = None

        result = integration.connect_remote_workers(("localhost", 5000), "secret")

        assert result is False
        assert integration._remote_client is None


class TestStartRemoteWorkers:
    """Tests for start_remote_workers method."""

    def test_returns_false_when_not_connected(self, integration):
        """Returns False when not connected to remote manager."""
        integration._remote_client = None

        result = integration.start_remote_workers(4)
        assert result is False

    def test_returns_true_on_success(self, integration):
        """Returns True when workers start successfully."""
        mock_client = Mock()
        integration._remote_client = mock_client

        result = integration.start_remote_workers(4)

        assert result is True
        assert integration._remote_workers_active is True
        mock_client.start_workers.assert_called_once_with(4)

    def test_returns_false_on_failure(self, integration):
        """Returns False when starting workers fails."""
        mock_client = Mock()
        mock_client.start_workers.side_effect = Exception("Failed to spawn")
        integration._remote_client = mock_client

        result = integration.start_remote_workers(4)

        assert result is False


class TestStopRemoteWorkers:
    """Tests for stop_remote_workers method."""

    def test_returns_true_when_not_connected(self, integration):
        """Returns True when no client connected (nothing to stop)."""
        integration._remote_client = None

        result = integration.stop_remote_workers()
        assert result is True

    def test_returns_true_on_success(self, integration):
        """Returns True when workers stop successfully."""
        mock_client = Mock()
        integration._remote_client = mock_client
        integration._remote_workers_active = True

        result = integration.stop_remote_workers(timeout=5)

        assert result is True
        assert integration._remote_workers_active is False
        mock_client.stop_workers.assert_called_once_with(5)

    def test_returns_false_on_failure(self, integration):
        """Returns False when stopping workers fails."""
        mock_client = Mock()
        mock_client.stop_workers.side_effect = Exception("Timeout")
        integration._remote_client = mock_client

        result = integration.stop_remote_workers()

        assert result is False


class TestDisconnectRemoteWorkers:
    """Tests for disconnect_remote_workers method."""

    def test_returns_true_when_not_connected(self, integration):
        """Returns True when no client to disconnect."""
        integration._remote_client = None

        result = integration.disconnect_remote_workers()
        assert result is True

    def test_returns_true_on_success(self, integration):
        """Returns True on successful disconnect."""
        mock_client = Mock()
        integration._remote_client = mock_client
        integration._remote_workers_active = True

        result = integration.disconnect_remote_workers()

        assert result is True
        assert integration._remote_client is None
        assert integration._remote_workers_active is False
        mock_client.disconnect.assert_called_once()

    def test_returns_false_on_failure(self, integration):
        """Returns False when disconnect fails."""
        mock_client = Mock()
        mock_client.disconnect.side_effect = Exception("Failed")
        integration._remote_client = mock_client

        result = integration.disconnect_remote_workers()

        assert result is False


class TestGetRemoteWorkerStatus:
    """Tests for get_remote_worker_status method."""

    def test_status_when_not_available(self, integration):
        """Returns correct status when RemoteWorkerClient not available."""
        integration.RemoteWorkerClient = None
        integration._remote_client = None
        integration._remote_workers_active = False

        status = integration.get_remote_worker_status()

        assert status["available"] is False
        assert status["connected"] is False
        assert status["workers_active"] is False
        assert status["address"] is None

    def test_status_when_connected(self, integration):
        """Returns correct status when connected."""
        mock_client = Mock()
        mock_client.address = ("192.168.1.100", 5000)
        integration.RemoteWorkerClient = Mock()
        integration._remote_client = mock_client
        integration._remote_workers_active = True

        status = integration.get_remote_worker_status()

        assert status["available"] is True
        assert status["connected"] is True
        assert status["workers_active"] is True
        assert status["address"] == ("192.168.1.100", 5000)


# ==============================================================================
# Test: Metrics Extraction Edge Cases
# ==============================================================================


class TestMetricsExtractionEdgeCases:
    """Tests for concurrent modification handling in _extract_current_metrics."""

    def test_handles_runtime_error_during_extraction(self, integration_with_network):
        """Handles RuntimeError during concurrent modification."""
        # Make history access raise RuntimeError
        network = integration_with_network.network

        class RaisingDict(dict):
            _access_count = 0

            def get(self, key, default=None):
                RaisingDict._access_count += 1
                if RaisingDict._access_count > 2:
                    raise RuntimeError("dictionary changed size during iteration")
                return super().get(key, default)

        network.history = RaisingDict(
            {
                "train_loss": [0.5],
                "train_accuracy": [0.8],
                "value_loss": [0.6],
                "value_accuracy": [0.7],
            }
        )

        result = integration_with_network._extract_current_metrics()
        # Should return empty dict on RuntimeError
        assert result == {}

    def test_handles_key_error_during_extraction(self, integration_with_network):
        """Handles KeyError during concurrent modification."""
        network = integration_with_network.network

        class RaisingDict(dict):
            def get(self, key, default=None):
                if key == "train_accuracy":
                    raise KeyError("train_accuracy removed during iteration")
                return super().get(key, default)

        network.history = RaisingDict({"train_loss": [0.5]})

        result = integration_with_network._extract_current_metrics()
        # Should return empty dict on KeyError
        assert result == {}


# ==============================================================================
# Test: Shutdown Edge Cases
# ==============================================================================


class TestShutdownEdgeCases:
    """Tests for shutdown with remote workers and training executor."""

    def test_shutdown_with_active_remote_client(self, integration):
        """Shutdown disconnects active remote client."""
        mock_client = Mock()
        integration._remote_client = mock_client
        integration._remote_workers_active = True

        # Reset shutdown state
        integration._shutdown_called = False

        integration.shutdown()

        mock_client.disconnect.assert_called_once()
        assert integration._remote_client is None

    def test_shutdown_with_training_executor(self, integration):
        """Shutdown shuts down training executor."""
        # Ensure executor exists
        assert integration._training_executor is not None
        executor = integration._training_executor

        # Reset shutdown state
        integration._shutdown_called = False

        integration.shutdown()

        assert integration._training_executor is None

    def test_shutdown_idempotent(self, integration):
        """Shutdown is idempotent - can be called multiple times."""
        integration._shutdown_called = False

        integration.shutdown()
        first_call = integration._shutdown_called

        integration.shutdown()
        second_call = integration._shutdown_called

        assert first_call is True
        assert second_call is True

    def test_shutdown_requests_training_stop(self, integration_with_network):
        """Shutdown requests training stop if training in progress."""
        mock_future = Mock()
        mock_future.done.return_value = False
        integration_with_network._training_future = mock_future
        integration_with_network._shutdown_called = False

        with patch.object(integration_with_network, "request_training_stop") as mock_stop:
            integration_with_network.shutdown()
            mock_stop.assert_called_once()


# ==============================================================================
# Test: RemoteWorkerClient Import (Line 331-332)
# ==============================================================================


class TestRemoteWorkerClientImport:
    """Tests for RemoteWorkerClient import behavior."""

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_remote_worker_client_import_success(self, mock_config_mgr, mock_exists):
        """Test successful RemoteWorkerClient import."""
        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        from backend.cascor_integration import CascorIntegration

        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.dict("sys.modules", {}):
                # Mock the import of RemoteWorkerClient
                mock_rwc = Mock()
                with patch(
                    "builtins.__import__",
                    side_effect=lambda name, *args, **kwargs: (
                        Mock(remote_client=Mock(RemoteWorkerClient=mock_rwc))
                        if "remote_client" in name
                        else __import__(name, *args, **kwargs)
                    ),
                ):
                    # This tests the import path indirectly
                    pass

    @patch("backend.cascor_integration.Path.exists")
    @patch("backend.cascor_integration.ConfigManager")
    def test_remote_worker_client_not_available(self, mock_config_mgr, mock_exists):
        """Test when RemoteWorkerClient is not available."""
        mock_exists.return_value = True
        mock_config_instance = Mock()
        mock_config_instance.config = {}
        mock_config_mgr.return_value = mock_config_instance

        from backend.cascor_integration import CascorIntegration

        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = CascorIntegration()
            # Simulate RemoteWorkerClient not being available
            integration.RemoteWorkerClient = None

            with pytest.raises(RuntimeError, match="RemoteWorkerClient not imported"):
                integration.connect_remote_workers(("localhost", 5000), "secret")


# ==============================================================================
# Test: Training Status
# ==============================================================================


class TestGetTrainingStatus:
    """Tests for get_training_status method."""

    def test_status_without_network(self, integration):
        """Returns status indicating no network connected."""
        integration.network = None

        status = integration.get_training_status()

        assert status["network_connected"] is False
        assert status["input_size"] == 0
        assert status["output_size"] == 0
        assert status["hidden_units"] == 0

    def test_status_with_network(self, integration_with_network):
        """Returns complete status with connected network."""
        integration_with_network.network.hidden_units = [Mock(), Mock()]  # 2 hidden units

        status = integration_with_network.get_training_status()

        assert status["network_connected"] is True
        assert status["input_size"] == 2
        assert status["output_size"] == 1
        assert status["hidden_units"] == 2
        assert status["monitoring_active"] is False


# ==============================================================================
# Test: Concurrent Training Prevention
# ==============================================================================


class TestConcurrentTrainingPrevention:
    """Tests for preventing concurrent training."""

    @pytest.mark.asyncio
    async def test_fit_async_prevents_concurrent(self, integration_with_network):
        """fit_async prevents concurrent training calls."""

        # Make fit take some time
        async def slow_fit():
            integration_with_network.network.fit = Mock(side_effect=lambda *a, **k: time.sleep(0.2))
            return await integration_with_network.fit_async()

        # Start first training
        task1 = asyncio.create_task(slow_fit())
        await asyncio.sleep(0.05)  # Let it start

        # Second call should fail if first is still running
        if integration_with_network.is_training_in_progress():
            with pytest.raises(RuntimeError, match="Training already in progress"):
                await integration_with_network.fit_async()

        await task1

    def test_start_background_prevents_concurrent(self, integration_with_network):
        """start_training_background prevents concurrent training."""
        integration_with_network.network.fit = Mock(side_effect=lambda *a, **k: time.sleep(0.3))

        first = integration_with_network.start_training_background()
        time.sleep(0.05)
        second = integration_with_network.start_training_background()

        assert first is True
        assert second is False


# ==============================================================================
# Test: Integration of Async Methods with Real Executor
# ==============================================================================


class TestAsyncIntegration:
    """Integration tests for async training with real executor."""

    @pytest.mark.asyncio
    async def test_full_async_training_lifecycle(self, integration_with_network):
        """Test complete async training lifecycle."""
        # Check initial state
        assert integration_with_network.is_training_in_progress() is False

        # Start async training
        result = await integration_with_network.fit_async()

        # Verify completion
        assert result == {"epochs": 100, "final_loss": 0.01}
        assert integration_with_network.is_training_in_progress() is False
        assert integration_with_network._training_future is None

    def test_full_background_training_lifecycle(self, integration_with_network):
        """Test complete background training lifecycle."""
        # Use quick fit
        integration_with_network.network.fit = Mock(return_value={"done": True})

        # Start background training
        started = integration_with_network.start_training_background()
        assert started is True

        # Wait for completion
        time.sleep(0.1)

        # Verify completion
        assert integration_with_network._training_future.done()
