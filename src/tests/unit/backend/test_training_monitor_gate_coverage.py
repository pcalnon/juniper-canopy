#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_training_monitor_gate_coverage.py
# Author:        Paul Calnon
# License:       MIT License
# Description:   Per-file coverage-gate tests for backend.training_monitor
#####################################################################
"""Statement-coverage tests for ``TrainingMonitor`` event handlers.

The existing ``test_training_monitor_95.py`` covers ``CandidatePool``,
``TrainingState``, and ``TrainingMonitor.apply_params`` but leaves the
event-dispatch surface of ``TrainingMonitor`` (register_callback,
_trigger_callbacks, on_training_start/end, on_epoch_start/end,
on_cascade_add, on_topology_change, and the metrics getters) uncovered.
These are real behavioural tests with meaningful assertions, added to
push the per-file gate over threshold.
"""

import pytest

from backend.data_adapter import DataAdapter, NetworkTopology, TrainingMetrics
from backend.training_monitor import TrainingMonitor


@pytest.fixture
def monitor():
    """A TrainingMonitor wired to a real (pure) DataAdapter."""
    return TrainingMonitor(DataAdapter())


@pytest.mark.unit
class TestCallbackRegistration:
    def test_register_known_event_appends_callback(self, monitor):
        """register_callback stores the callback for a recognized event."""
        received = []
        monitor.register_callback("training_start", lambda **kw: received.append(kw))
        monitor.on_training_start()
        assert received == [{}]

    def test_register_unknown_event_is_ignored(self, monitor):
        """An unknown event type is logged and NOT registered (no raise)."""
        monitor.register_callback("does_not_exist", lambda **kw: None)
        # The unknown bucket must not have been created.
        assert "does_not_exist" not in monitor.callbacks

    def test_trigger_callbacks_swallows_callback_errors(self, monitor):
        """A raising callback must not break dispatch to the others."""
        good = []

        def _boom(**kw):
            raise RuntimeError("callback boom")

        monitor.register_callback("training_start", _boom)
        monitor.register_callback("training_start", lambda **kw: good.append(1))
        # Must not raise despite the first callback blowing up.
        monitor.on_training_start()
        assert good == [1]


@pytest.mark.unit
class TestTrainingLifecycleEvents:
    def test_on_training_start_resets_state_and_fires(self, monitor):
        monitor.current_epoch = 42
        fired = []
        monitor.register_callback("training_start", lambda **kw: fired.append(kw))

        monitor.on_training_start()

        assert monitor.is_training is True
        assert monitor.current_epoch == 0
        assert monitor.metrics_buffer == []
        assert fired == [{}]

    def test_on_training_end_clears_flag_and_passes_final_metrics(self, monitor):
        monitor.on_training_start()
        captured = {}
        monitor.register_callback("training_end", lambda **kw: captured.update(kw))

        monitor.on_training_end(final_metrics={"loss": 0.01})

        assert monitor.is_training is False
        assert captured["final_metrics"] == {"loss": 0.01}

    def test_on_epoch_start_updates_epoch_and_phase(self, monitor):
        captured = {}
        monitor.register_callback("epoch_start", lambda **kw: captured.update(kw))

        monitor.on_epoch_start(7, phase="candidate")

        assert monitor.current_epoch == 7
        assert monitor.current_phase == "candidate"
        assert captured == {"epoch": 7, "phase": "candidate"}


@pytest.mark.unit
class TestEpochEndMetrics:
    def test_on_epoch_end_buffers_metrics_and_fires(self, monitor):
        captured = {}
        monitor.register_callback("epoch_end", lambda **kw: captured.update(kw))

        monitor.on_epoch_end(epoch=1, loss=0.5, accuracy=0.75, learning_rate=0.01)

        assert len(monitor.metrics_buffer) == 1
        metric = monitor.metrics_buffer[0]
        assert isinstance(metric, TrainingMetrics)
        assert metric.epoch == 1 and metric.loss == 0.5 and metric.accuracy == 0.75
        assert captured["epoch"] == 1 and captured["loss"] == 0.5

    def test_on_epoch_end_respects_buffer_cap(self, monitor):
        """Oldest metric is evicted once the buffer exceeds max_buffer_size."""
        monitor.max_buffer_size = 2
        for e in range(4):
            monitor.on_epoch_end(epoch=e, loss=1.0 / (e + 1), accuracy=0.1 * e, learning_rate=0.01)

        assert len(monitor.metrics_buffer) == 2
        # The two most-recent epochs (2 and 3) survive.
        assert [m.epoch for m in monitor.metrics_buffer] == [2, 3]

    def test_on_epoch_end_carries_validation_and_hidden_units(self, monitor):
        monitor.current_hidden_units = 3
        monitor.current_phase = "candidate"
        monitor.on_epoch_end(
            epoch=2,
            loss=0.2,
            accuracy=0.9,
            learning_rate=0.05,
            validation_loss=0.3,
            validation_accuracy=0.85,
        )
        m = monitor.metrics_buffer[-1]
        assert m.hidden_units == 3
        assert m.cascade_phase == "candidate"
        assert m.validation_loss == 0.3 and m.validation_accuracy == 0.85


@pytest.mark.unit
class TestCascadeAndTopologyEvents:
    def test_on_cascade_add_increments_hidden_units_and_fires(self, monitor):
        events = []
        monitor.register_callback("cascade_add", lambda **kw: events.append(kw))

        monitor.on_cascade_add(hidden_unit_index=0, correlation=0.9)

        assert monitor.current_hidden_units == 1
        assert len(events) == 1
        event = events[0]["event"]
        assert event["hidden_unit_index"] == 0
        assert event["correlation"] == 0.9
        assert event["total_hidden_units"] == 1
        assert "timestamp" in event

    def test_on_topology_change_forwards_topology(self, monitor):
        topo = NetworkTopology(
            nodes=[],
            connections=[],
            cascade_history=[],
            current_epoch=5,
            hidden_units_count=2,
        )
        received = []
        monitor.register_callback("topology_change", lambda **kw: received.append(kw["topology"]))

        monitor.on_topology_change(topo)

        assert received == [topo]


@pytest.mark.unit
class TestMetricsAccessorsAndClear:
    def test_get_recent_metrics_returns_tail(self, monitor):
        for e in range(5):
            monitor.on_epoch_end(epoch=e, loss=0.1, accuracy=0.5, learning_rate=0.01)

        recent = monitor.get_recent_metrics(count=2)
        assert [m.epoch for m in recent] == [3, 4]

    def test_get_all_metrics_returns_copy(self, monitor):
        monitor.on_epoch_end(epoch=0, loss=0.1, accuracy=0.5, learning_rate=0.01)
        allm = monitor.get_all_metrics()
        assert len(allm) == 1
        # Must be a copy — mutating the returned list does not touch the buffer.
        allm.clear()
        assert len(monitor.metrics_buffer) == 1

    def test_get_current_state_shape(self, monitor):
        monitor.on_training_start()
        monitor.on_epoch_start(3, phase="output")
        state = monitor.get_current_state()
        assert state == {
            "is_training": True,
            "current_epoch": 3,
            "current_hidden_units": 0,
            "current_phase": "output",
            "total_metrics": 0,
        }

    def test_clear_metrics_empties_buffer(self, monitor):
        monitor.on_epoch_end(epoch=0, loss=0.1, accuracy=0.5, learning_rate=0.01)
        assert monitor.metrics_buffer
        monitor.clear_metrics()
        assert monitor.metrics_buffer == []
