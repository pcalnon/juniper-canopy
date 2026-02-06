"""
Unit Tests for TrainingMonitor

Tests callback registration, event triggers, metrics buffering, and thread safety.
"""

import queue
import threading
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.data_adapter import NetworkTopology, TrainingMetrics
from backend.training_monitor import TrainingMonitor


class FakeDataAdapter:
    """Fake DataAdapter for testing."""

    def extract_training_metrics(
        self,
        epoch,
        loss,
        accuracy,
        learning_rate,
        hidden_units=0,
        cascade_phase="output",
        validation_loss=None,
        validation_accuracy=None,
    ):
        """Create fake training metrics."""
        return TrainingMetrics(
            epoch=epoch,
            loss=loss,
            accuracy=accuracy,
            learning_rate=learning_rate,
            timestamp=datetime.now(),
            validation_loss=validation_loss,
            validation_accuracy=validation_accuracy,
            hidden_units=hidden_units,
            cascade_phase=cascade_phase,
        )


@pytest.mark.unit
class TestTrainingMonitor:
    """Test suite for TrainingMonitor class."""

    def test_initialization(self):
        """Test TrainingMonitor initialization."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        assert monitor.data_adapter == adapter
        assert monitor.metrics_buffer == []
        assert monitor.is_training is False
        assert monitor.current_epoch == 0
        assert monitor.current_hidden_units == 0
        assert monitor.current_phase == "output"
        assert isinstance(monitor.metrics_queue, queue.Queue)
        assert isinstance(monitor.lock, type(threading.Lock()))

    def test_register_callback_valid_event(self):
        """Test register_callback for valid event types."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("epoch_start", callback)

        assert callback in monitor.callbacks["epoch_start"]

    def test_register_callback_multiple_callbacks(self):
        """Test register_callback allows multiple callbacks per event."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback1 = MagicMock()
        callback2 = MagicMock()

        monitor.register_callback("epoch_end", callback1)
        monitor.register_callback("epoch_end", callback2)

        assert len(monitor.callbacks["epoch_end"]) == 2
        assert callback1 in monitor.callbacks["epoch_end"]
        assert callback2 in monitor.callbacks["epoch_end"]

    def test_register_callback_unknown_event_type(self):
        """Test register_callback warns for unknown event types."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)
        monitor.logger = MagicMock()

        callback = MagicMock()
        monitor.register_callback("unknown_event", callback)

        monitor.logger.warning.assert_called_with("Unknown event type: unknown_event")

    def test_on_training_start(self):
        """Test on_training_start sets state and triggers callbacks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("training_start", callback)

        monitor.on_training_start()

        assert monitor.is_training is True
        assert monitor.current_epoch == 0
        assert len(monitor.metrics_buffer) == 0
        callback.assert_called_once()

    def test_on_training_start_clears_buffer(self):
        """Test on_training_start clears existing metrics buffer."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        # Add some metrics to buffer
        monitor.metrics_buffer = [MagicMock(), MagicMock()]

        monitor.on_training_start()

        assert not monitor.metrics_buffer

    def test_on_training_end(self):
        """Test on_training_end sets state and triggers callbacks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("training_end", callback)

        monitor.is_training = True
        final_metrics = {"loss": 0.1, "accuracy": 0.95}

        monitor.on_training_end(final_metrics)

        assert not monitor.is_training
        callback.assert_called_once_with(final_metrics=final_metrics)

    def test_on_epoch_start(self):
        """Test on_epoch_start updates state and triggers callbacks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("epoch_start", callback)

        monitor.on_epoch_start(epoch=5, phase="candidate")

        assert monitor.current_epoch == 5
        assert monitor.current_phase == "candidate"
        callback.assert_called_once_with(epoch=5, phase="candidate")

    def test_on_epoch_start_default_phase(self):
        """Test on_epoch_start uses default phase."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        monitor.on_epoch_start(epoch=3)

        assert monitor.current_phase == "output"

    def test_on_epoch_end(self):
        """Test on_epoch_end collects metrics and triggers callbacks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("epoch_end", callback)

        monitor.on_epoch_end(epoch=1, loss=0.5, accuracy=0.8, learning_rate=0.01, validation_loss=0.6, validation_accuracy=0.75)

        assert len(monitor.metrics_buffer) == 1
        assert monitor.metrics_buffer[0].epoch == 1
        assert monitor.metrics_buffer[0].loss == 0.5
        assert monitor.metrics_buffer[0].accuracy == 0.8
        callback.assert_called_once()

    def test_on_epoch_end_adds_to_queue(self):
        """Test on_epoch_end adds metrics to queue."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        monitor.on_epoch_end(epoch=1, loss=0.5, accuracy=0.8, learning_rate=0.01)

        # Should be able to get from queue
        metrics = monitor.metrics_queue.get(timeout=1.0)
        assert metrics.epoch == 1
        assert metrics.loss == 0.5

    def test_on_epoch_end_respects_max_buffer_size(self):
        """Test on_epoch_end respects max_buffer_size limit."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)
        monitor.max_buffer_size = 5

        # Add more metrics than buffer size
        for i in range(10):
            monitor.on_epoch_end(epoch=i, loss=0.5 - i * 0.01, accuracy=0.7 + i * 0.01, learning_rate=0.01)

        # Buffer should not exceed max size
        assert len(monitor.metrics_buffer) == 5
        # Should keep most recent metrics
        assert monitor.metrics_buffer[-1].epoch == 9

    def test_on_cascade_add(self):
        """Test on_cascade_add increments hidden units and triggers callbacks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("cascade_add", callback)

        monitor.on_cascade_add(hidden_unit_index=0, correlation=0.85, weights={"input": [0.1, 0.2]})

        assert monitor.current_hidden_units == 1
        callback.assert_called_once()

        # Check event structure
        call_args = callback.call_args[1]
        event = call_args["event"]
        assert event["hidden_unit_index"] == 0
        assert event["correlation"] == 0.85
        assert event["total_hidden_units"] == 1

    def test_on_cascade_add_multiple_units(self):
        """Test on_cascade_add correctly increments for multiple units."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        monitor.on_cascade_add(0, 0.8)
        monitor.on_cascade_add(1, 0.9)
        monitor.on_cascade_add(2, 0.85)

        assert monitor.current_hidden_units == 3

    def test_on_topology_change(self):
        """Test on_topology_change triggers callbacks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        callback = MagicMock()
        monitor.register_callback("topology_change", callback)

        topology = MagicMock(spec=NetworkTopology)
        monitor.on_topology_change(topology)

        callback.assert_called_once_with(topology=topology)

    def test_get_recent_metrics(self):
        """Test get_recent_metrics returns recent metrics."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        # Add 10 metrics
        for i in range(10):
            monitor.on_epoch_end(epoch=i, loss=0.5, accuracy=0.8, learning_rate=0.01)

        # Get last 5 metrics
        recent = monitor.get_recent_metrics(count=5)

        assert len(recent) == 5
        assert recent[0].epoch == 5
        assert recent[-1].epoch == 9

    def test_get_recent_metrics_fewer_than_count(self):
        """Test get_recent_metrics when buffer has fewer than requested."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        # Add only 3 metrics
        for i in range(3):
            monitor.on_epoch_end(epoch=i, loss=0.5, accuracy=0.8, learning_rate=0.01)

        # Request 10 - should return all 3
        recent = monitor.get_recent_metrics(count=10)

        assert len(recent) == 3

    def test_get_all_metrics(self):
        """Test get_all_metrics returns copy of all metrics."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        for i in range(5):
            monitor.on_epoch_end(epoch=i, loss=0.5, accuracy=0.8, learning_rate=0.01)

        all_metrics = monitor.get_all_metrics()

        assert len(all_metrics) == 5
        # Should be a copy, not the original
        assert all_metrics is not monitor.metrics_buffer

    def test_get_current_state(self):
        """Test get_current_state returns current training state."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        monitor.is_training = True
        monitor.current_epoch = 10
        monitor.current_hidden_units = 3
        monitor.current_phase = "candidate"

        state = monitor.get_current_state()

        assert state["is_training"] is True
        assert state["current_epoch"] == 10
        assert state["current_hidden_units"] == 3
        assert state["current_phase"] == "candidate"
        assert state["total_metrics"] == 0

    def test_clear_metrics(self):
        """Test clear_metrics empties the buffer."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        # Add metrics
        for i in range(5):
            monitor.on_epoch_end(epoch=i, loss=0.5, accuracy=0.8, learning_rate=0.01)

        assert len(monitor.metrics_buffer) == 5

        monitor.clear_metrics()

        assert len(monitor.metrics_buffer) == 0

    def test_poll_metrics_queue_success(self):
        """Test poll_metrics_queue returns metrics from queue."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        # Add metric to trigger queue update
        monitor.on_epoch_end(epoch=1, loss=0.5, accuracy=0.8, learning_rate=0.01)

        metrics = monitor.poll_metrics_queue(timeout=1.0)

        assert metrics is not None
        assert metrics.epoch == 1

    def test_poll_metrics_queue_empty_returns_none(self):
        """Test poll_metrics_queue returns None when queue empty."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        metrics = monitor.poll_metrics_queue(timeout=0.1)

        assert metrics is None

    def test_thread_safety_concurrent_epoch_end(self):
        """Test on_epoch_end is thread-safe with concurrent access."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        def add_metrics(start_epoch):
            for i in range(10):
                monitor.on_epoch_end(epoch=start_epoch + i, loss=0.5, accuracy=0.8, learning_rate=0.01)

        # Run multiple threads adding metrics
        threads = [threading.Thread(target=add_metrics, args=(i * 100,)) for i in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all metrics without corruption
        assert len(monitor.metrics_buffer) == 50

    def test_trigger_callbacks_handles_exceptions(self):
        """Test _trigger_callbacks handles callback exceptions."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)
        monitor.logger = MagicMock()

        # Register callback that raises exception
        bad_callback = MagicMock(side_effect=RuntimeError("Callback error"))
        good_callback = MagicMock()

        monitor.register_callback("epoch_end", bad_callback)
        monitor.register_callback("epoch_end", good_callback)

        # Trigger callbacks - should handle exception and continue
        monitor._trigger_callbacks("epoch_end", epoch=1)

        # Good callback should still be called
        good_callback.assert_called_once()
        monitor.logger.error.assert_called()

    def test_metrics_buffer_bounded(self):
        """Test metrics buffer is properly bounded to prevent memory leaks."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)
        monitor.max_buffer_size = 100

        # Add many more metrics than buffer size
        for i in range(1000):
            monitor.on_epoch_end(epoch=i, loss=0.5, accuracy=0.8, learning_rate=0.01)

        # Buffer should never exceed max size
        assert len(monitor.metrics_buffer) <= 100
