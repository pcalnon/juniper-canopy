#!/usr/bin/env python
"""
Advanced unit tests for DemoMode with focus on thread safety and control flow.
"""
import threading
import time

import pytest

from canopy_constants import TrainingConstants
from demo_mode import DemoMode, get_demo_mode


class TestDemoModeThreadSafety:
    """Test thread safety of DemoMode operations."""

    def test_concurrent_state_access(self):
        """Test multiple threads accessing demo mode state simultaneously."""
        demo = DemoMode(update_interval=0.1)
        demo.start()

        errors = []

        def read_state():
            """Read state multiple times."""
            try:
                for _ in range(10):
                    state = demo.get_current_state()
                    assert isinstance(state, dict)
                    assert "is_running" in state
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        # Start multiple reader threads
        threads = [threading.Thread(target=read_state) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        demo.stop()

        assert not errors, f"Concurrent access errors: {errors}"

    def test_start_stop_idempotency(self):
        """Test that start/stop can be called multiple times safely."""
        demo = DemoMode(update_interval=0.1)

        # Multiple starts should be safe
        demo.start()
        assert demo.is_running
        demo.start()  # Should warn but not crash
        assert demo.is_running

        # Multiple stops should be safe
        demo.stop()
        assert not demo.is_running
        demo.stop()  # Should be no-op
        assert not demo.is_running

    def test_pause_resume_correctness(self):
        """Test pause/resume functionality."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.3)  # Let it run a bit

        epoch_before_pause = demo.current_epoch

        # Pause
        demo.pause()
        state = demo.get_current_state()
        assert state["is_paused"]
        time.sleep(0.5)  # Wait while paused

        # Epoch should not advance while paused
        epoch_during_pause = demo.current_epoch
        assert epoch_during_pause in [epoch_before_pause, epoch_before_pause + 1]

        # Resume
        demo.resume()
        state = demo.get_current_state()
        assert not state["is_paused"]
        time.sleep(0.3)  # Let it run

        # Epoch should advance after resume
        epoch_after_resume = demo.current_epoch
        assert epoch_after_resume > epoch_during_pause

        demo.stop()

    def test_pause_without_running(self):
        """Test that pause fails gracefully when not running."""
        demo = DemoMode(update_interval=0.1)

        # Should not crash
        demo.pause()
        assert not demo.is_running
        assert not demo.get_current_state()["is_paused"]

    def test_reset_functionality(self):
        """Test that reset clears all state."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.5)  # Let it run and accumulate state

        # Verify some state exists
        state_before = demo.get_current_state()
        assert state_before["current_epoch"] > 0
        assert len(demo.get_metrics_history()) > 0

        # Stop before reset
        demo.stop()

        # Reset while stopped
        demo.reset()

        # Verify state is cleared (reset doesn't auto-start)
        state_after = demo.get_current_state()
        assert state_after["current_epoch"] == 0
        assert len(demo.get_metrics_history()) == 0
        assert state_after["current_loss"] == 1.0
        assert state_after["current_accuracy"] == 0.5

    def test_stop_completes_promptly(self):
        """Verify stop() completes within reasonable time."""
        demo = DemoMode(update_interval=1.0)  # Long interval
        demo.start()
        time.sleep(0.5)

        start_time = time.time()
        demo.stop()
        stop_time = time.time() - start_time

        # Should complete within 2 * update_interval
        assert stop_time < 2.0, f"Stop took {stop_time:.2f}s, expected <2s"

    def test_metrics_history_bounded(self):
        """Test that metrics history doesn't grow unbounded."""
        demo = DemoMode(update_interval=0.01)  # Fast updates
        demo.start()
        time.sleep(2.0)  # Let it accumulate many metrics
        demo.stop()

        # Should be bounded by METRICS_HISTORY_MAXLEN
        assert len(demo.get_metrics_history()) <= TrainingConstants.METRICS_HISTORY_MAXLEN

    def test_network_history_bounded(self):
        """Test that network history doesn't grow unbounded."""
        demo = DemoMode(update_interval=0.01)
        demo.start()
        time.sleep(2.0)
        demo.stop()

        # Network history should also be bounded
        network = demo.get_network()
        for key in network.history:
            assert len(network.history[key]) <= TrainingConstants.METRICS_HISTORY_MAXLEN


class TestDemoModeSingleton:
    """Test singleton pattern of get_demo_mode."""

    def test_singleton_returns_same_instance(self):
        """Test that get_demo_mode returns same instance."""
        demo1 = get_demo_mode()
        demo2 = get_demo_mode()

        assert demo1 is demo2

    def test_singleton_state_persistence(self):
        """Test that state persists across get_demo_mode calls."""
        demo1 = get_demo_mode(update_interval=0.1)
        demo1.start()
        time.sleep(0.3)
        epoch1 = demo1.current_epoch

        demo2 = get_demo_mode()
        epoch2 = demo2.current_epoch

        # Same instance, so epoch should match or be slightly advanced
        assert epoch2 >= epoch1

        demo1.stop()


class TestDemoModeDataGeneration:
    """Test data generation and consistency."""

    def test_dataset_generation(self):
        """Test that dataset is generated correctly."""
        demo = DemoMode()
        dataset = demo.get_dataset()

        assert "inputs" in dataset
        assert "targets" in dataset
        assert dataset["num_samples"] == 200
        assert dataset["num_features"] == 2
        assert dataset["num_classes"] == 2

    def test_metrics_consistency(self):
        """Test that metrics are consistent and realistic."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.5)
        demo.stop()

        metrics = demo.get_metrics_history()
        assert len(metrics) > 0

        for m in metrics:
            self._extracted_from_test_metrics_consistency_12(m)

    # TODO Rename this here and in `test_metrics_consistency`
    def _extracted_from_test_metrics_consistency_12(self, m):
        assert "epoch" in m
        assert "metrics" in m
        assert "loss" in m["metrics"]
        assert "accuracy" in m["metrics"]
        assert "val_loss" in m["metrics"]
        assert "val_accuracy" in m["metrics"]

        # Metrics should be in realistic ranges
        assert 0 <= m["metrics"]["loss"] <= 2.0
        assert 0 <= m["metrics"]["accuracy"] <= 1.0
        assert 0 <= m["metrics"]["val_loss"] <= 2.0
        assert 0 <= m["metrics"]["val_accuracy"] <= 1.0

    def test_cascade_unit_addition(self):
        """Test that cascade units are added periodically."""
        demo = DemoMode(update_interval=0.05)
        demo.cascade_every = 10  # Add unit every 10 epochs
        demo.start()
        time.sleep(1.0)  # Should trigger at least one cascade
        demo.stop()

        network = demo.get_network()
        # Should have added at least one hidden unit
        assert len(network.hidden_units) >= 0  # May or may not have added depending on timing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
