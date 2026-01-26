"""
Unit Tests for CascorIntegration Monitoring

Tests monitoring thread, metric extraction, and WebSocket broadcasting.
"""

import threading
import time
from collections import deque

# from datetime import datetime
# from unittest.mock import MagicMock, call, patch
from unittest.mock import MagicMock, patch

import pytest

from backend.cascor_integration import CascorIntegration


def create_mock_integration(network=None):
    """
    Create a CascorIntegration instance without calling __init__.

    This helper properly initializes all required attributes that __init__
    would set, avoiding AttributeError in tests that use __new__.

    Args:
        network: Optional network instance to attach

    Returns:
        CascorIntegration instance with minimal required attributes
    """
    integration = CascorIntegration.__new__(CascorIntegration)
    integration.logger = MagicMock()
    integration.network = network
    integration.monitoring_thread = None
    integration.monitoring_active = False
    integration.metrics_lock = threading.Lock()  # CANOPY-P1-003 thread safety
    integration.topology_lock = threading.Lock()
    integration._shutdown_called = False
    return integration


class FakeNetwork:
    """Fake network for testing monitoring."""

    def __init__(self, with_history=True):
        """Initialize fake network with optional history."""
        self.input_size = 2
        self.output_size = 1
        self.hidden_units = []

        if with_history:
            # Use deque with maxlen for bounded history
            self.history = {
                "train_loss": deque([0.5, 0.4, 0.3], maxlen=100),
                "train_accuracy": deque([0.6, 0.7, 0.8], maxlen=100),
                "value_loss": deque([0.55, 0.45, 0.35], maxlen=100),
                "value_accuracy": deque([0.58, 0.68, 0.78], maxlen=100),
            }
        else:
            self.history = {}

    def fit(self, *args, **kwargs):
        """Mock fit method."""
        return {"train_loss": [0.5, 0.4], "train_accuracy": [0.6, 0.7]}

    def train_output_layer(self, *args, **kwargs):
        """Mock train_output_layer method."""
        return {"loss": 0.3, "accuracy": 0.8}

    def train_candidates(self, *args, **kwargs):
        """Mock train_candidates method."""
        return {"correlation": 0.9}


@pytest.mark.unit
class TestCascorIntegrationMonitoring:
    """Test suite for CascorIntegration monitoring functionality."""

    def test_start_monitoring_thread_success(self):
        """Test start_monitoring_thread creates and starts thread."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork())

                integration.start_monitoring_thread(interval=0.1)

                # Give thread time to start
                time.sleep(0.05)

                # trunk-ignore(bandit/B101)
                assert integration.monitoring_thread is not None
                # trunk-ignore(bandit/B101)
                assert integration.monitoring_active

                # Cleanup
                integration.stop_monitoring()

    def test_start_monitoring_thread_idempotent(self):
        """Test start_monitoring_thread is idempotent (doesn't create duplicate threads)."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork())

                # Start first thread
                integration.start_monitoring_thread(interval=0.1)
                first_thread = integration.monitoring_thread

                # Try to start again - should warn and not create new thread
                integration.start_monitoring_thread(interval=0.1)
                second_thread = integration.monitoring_thread

                # trunk-ignore(bandit/B101)
                assert first_thread is second_thread
                integration.logger.warning.assert_called_with("Monitoring thread already running")

                # Cleanup
                integration.stop_monitoring()

    def test_stop_monitoring_success(self):
        """Test stop_monitoring cleanly stops the monitoring thread."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork())

                integration.start_monitoring_thread(interval=0.1)
                # trunk-ignore(bandit/B101)
                assert integration.monitoring_active

                integration.stop_monitoring()

                # trunk-ignore(bandit/B101)
                assert not integration.monitoring_active
                # trunk-ignore(bandit/B101)
                assert integration.monitoring_thread is None or not integration.monitoring_thread.is_alive()

    def test_stop_monitoring_idempotent(self):
        """Test stop_monitoring is idempotent."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration()

                # Call stop_monitoring when not active - should return early
                integration.stop_monitoring()
                integration.stop_monitoring()

                # Should not raise any errors
                # trunk-ignore(bandit/B101)
                assert not integration.monitoring_active

    def test_extract_current_metrics_with_history(self):
        """Test _extract_current_metrics extracts metrics from network history."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork(with_history=True))

                metrics = integration._extract_current_metrics()

                # trunk-ignore(bandit/B101)
                assert metrics["epoch"] == 3
                # trunk-ignore(bandit/B101)
                assert metrics["train_loss"] == 0.3
                # trunk-ignore(bandit/B101)
                assert metrics["train_accuracy"] == 0.8
                # trunk-ignore(bandit/B101)
                assert metrics["value_loss"] == 0.35
                # trunk-ignore(bandit/B101)
                assert metrics["value_accuracy"] == 0.78
                # trunk-ignore(bandit/B101)
                assert metrics["hidden_units"] == 0
                # trunk-ignore(bandit/B101)
                assert "timestamp" in metrics

    def test_extract_current_metrics_empty_history(self):
        """Test _extract_current_metrics with empty history."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork(with_history=False))

                metrics = integration._extract_current_metrics()

                # trunk-ignore(bandit/B101)
                assert metrics["epoch"] == 0
                # trunk-ignore(bandit/B101)
                assert metrics["train_loss"] is None
                # trunk-ignore(bandit/B101)
                assert metrics["train_accuracy"] is None

    def test_extract_current_metrics_no_network(self):
        """Test _extract_current_metrics returns empty dict when no network."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=None)

                metrics = integration._extract_current_metrics()

                # trunk-ignore(bandit/B101)
                assert metrics == {}

    def test_extract_current_metrics_network_without_history(self):
        """Test _extract_current_metrics when network has no history attribute."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                # Network without history attribute
                network = MagicMock(spec=["input_size", "output_size"])
                integration = create_mock_integration(network=network)

                metrics = integration._extract_current_metrics()

                # trunk-ignore(bandit/B101)
                assert metrics == {}

    def test_broadcast_message_calls_websocket(self):
        """Test _broadcast_message calls WebSocket broadcast."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration()

                # Mock the websocket_manager module
                mock_websocket = MagicMock()

                with patch("communication.websocket_manager.websocket_manager", mock_websocket):
                    message = {"type": "test", "data": "value"}
                    integration._broadcast_message(message)

                    mock_websocket.broadcast_sync.assert_called_once_with(message)

    def test_broadcast_message_handles_exception(self):
        """Test _broadcast_message handles exceptions gracefully."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration()

                # Mock websocket_manager to raise exception
                mock_websocket = MagicMock()
                mock_websocket.broadcast_sync.side_effect = RuntimeError("WebSocket error")

                with patch("communication.websocket_manager.websocket_manager", mock_websocket):
                    # Should not raise - exception should be logged
                    integration._broadcast_message({"type": "test"})

                    integration.logger.warning.assert_called()

    def test_monitoring_loop_broadcasts_metrics(self):
        """Test _monitoring_loop extracts and broadcasts metrics periodically."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork(with_history=True))
                integration.monitoring_active = True
                integration._broadcast_message = MagicMock()

                # Run monitoring loop in background
                loop_thread = threading.Thread(target=integration._monitoring_loop, args=(0.05,), daemon=True)
                loop_thread.start()

                # Let it run for a bit
                time.sleep(0.2)

                # Stop monitoring
                integration.monitoring_active = False
                loop_thread.join(timeout=1.0)

                # Should have broadcast metrics
                # trunk-ignore(bandit/B101)
                assert integration._broadcast_message.call_count >= 2

    def test_monitoring_loop_handles_exceptions(self):
        """Test _monitoring_loop continues running after exceptions."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork(with_history=True))
                integration.monitoring_active = True

                # Make _broadcast_message raise exception first time, then work
                call_count = [0]

                def broadcast_side_effect(msg):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        raise RuntimeError("Broadcast error")

                integration._broadcast_message = MagicMock(side_effect=broadcast_side_effect)

                # Run monitoring loop
                loop_thread = threading.Thread(target=integration._monitoring_loop, args=(0.05,), daemon=True)
                loop_thread.start()

                time.sleep(0.2)

                # Stop monitoring
                integration.monitoring_active = False
                loop_thread.join(timeout=1.0)

                # Should have logged error but continued
                integration.logger.error.assert_called()

    def test_monitoring_loop_stops_when_network_removed(self):
        """Test _monitoring_loop stops when network is set to None."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork(with_history=True))
                integration.monitoring_active = True
                integration._broadcast_message = MagicMock()

                loop_thread = threading.Thread(target=integration._monitoring_loop, args=(0.05,), daemon=True)
                loop_thread.start()

                time.sleep(0.1)

                # Remove network - loop should stop
                integration.network = None

                time.sleep(0.2)

                # Thread should have exited
                # trunk-ignore(bandit/B101)
                assert not loop_thread.is_alive()

    def test_monitoring_thread_custom_interval(self):
        """Test start_monitoring_thread uses custom interval."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = create_mock_integration(network=FakeNetwork())

                custom_interval = 0.25
                integration.start_monitoring_thread(interval=custom_interval)

                # trunk-ignore(bandit/B101)
                assert integration.monitoring_interval == custom_interval

                # Cleanup
                integration.stop_monitoring()
