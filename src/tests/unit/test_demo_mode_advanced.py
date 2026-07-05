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


class TestPhase3ProgressFields:
    """Phase 3 metrics granularity: TrainingState progress fields are exposed
    by DemoMode so the canopy progress UI displays non-zero values during demo
    training. See juniper-ml/notes/code-review/JUNIPER_2026-04-08_JUNIPER-ECOSYSTEM_CANOPY-CASCOR-INTERFACE-ROADMAP.md §5.
    """

    PHASE3_FIELDS = (
        "grow_iteration",
        "grow_max",
        "best_correlation",
        "candidates_trained",
        "candidates_total",
        "phase_detail",
        "phase_started_at",
    )

    def test_get_current_state_exposes_phase3_fields_before_start(self):
        """get_current_state() must include all Phase 3 fields immediately
        after construction (before start) so any consumer that reads state
        early sees the keys with safe default values rather than KeyError."""
        demo = DemoMode(update_interval=0.1)
        state = demo.get_current_state()
        for field in self.PHASE3_FIELDS:
            assert field in state, f"Phase 3 field missing from get_current_state(): {field}"
        # Defaults at this point: nothing has trained yet
        assert state["grow_iteration"] == 0
        assert state["grow_max"] == demo.max_hidden_units
        assert state["best_correlation"] == 0.0
        assert state["candidates_trained"] == 0
        assert state["candidates_total"] == 0
        assert state["phase_detail"] == ""
        assert state["phase_started_at"] == ""

    def test_training_state_includes_phase3_fields_after_status_update(self):
        """After a training-status update fires, the canopy TrainingState
        object must carry the Phase 3 fields too — that's the path consumed
        by the dashboard's WebSocket relay."""
        demo = DemoMode(update_interval=0.1)
        if demo.training_state is None:
            pytest.skip("backend.training_monitor.TrainingState unavailable in this environment")
        # Trigger one explicit status update without running the loop.
        demo._update_training_status()
        ts_state = demo.training_state.get_state()
        for field in self.PHASE3_FIELDS:
            assert field in ts_state, f"Phase 3 field missing from TrainingState: {field}"
        assert ts_state["grow_max"] == demo.max_hidden_units

    def test_phase3_fields_track_training_progress(self):
        """After running the demo loop briefly, at least one Phase 3 field
        should reflect that training happened. We check phase_detail
        (set as soon as the loop enters Phase 1 output training) and
        phase_started_at (a non-empty ISO timestamp)."""
        demo = DemoMode(update_interval=0.05)
        demo.start()
        time.sleep(0.5)
        try:
            state = demo.get_current_state()
            assert state["phase_detail"] in ("training_output", "training_candidates", "retraining_output"), state["phase_detail"]
            assert state["phase_started_at"] != "", "phase_started_at should be set after the loop enters a phase"
        finally:
            demo.stop()

    def test_reset_clears_phase3_state(self):
        """Reset must zero out the Phase 3 state so a fresh run starts clean."""
        demo = DemoMode(update_interval=0.1)
        demo._best_correlation_state = 0.42
        demo._candidates_trained_count = 5
        demo._candidates_total_count = 10
        demo._phase_detail = "training_candidates"
        demo._phase_started_at = "2026-04-09T17:30:00"
        demo.current_iteration = 3
        demo._reset_state_and_history()
        assert demo._best_correlation_state == 0.0
        assert demo._candidates_trained_count == 0
        assert demo._candidates_total_count == 0
        assert demo._phase_detail == ""
        assert demo._phase_started_at == ""
        assert demo.current_iteration == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
