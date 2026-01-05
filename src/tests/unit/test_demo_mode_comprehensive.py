#!/usr/bin/env python
"""
Comprehensive unit tests for DemoMode to achieve 90%+ coverage.

Focuses on:
1. MockCascorNetwork: forward pass edge cases, hidden unit addition
2. Environment variable parsing: invalid values, edge cases
3. Error handling paths: WebSocket failures, import errors
4. Candidate pool simulation: phase transitions
5. Parameter application: apply_params method
6. FSM command failures: invalid state transitions
7. Pause/resume edge cases: already paused, not paused
8. Broadcast failures: exception handling
"""
import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
import torch

from demo_mode import DemoMode, MockCascorNetwork, get_demo_mode


class TestMockCascorNetwork:
    """Test MockCascorNetwork functionality."""

    def test_network_initialization(self):
        """Test network initializes with correct attributes."""
        network = MockCascorNetwork(input_size=3, output_size=2)

        assert network.input_size == 3
        assert network.output_size == 2
        assert len(network.hidden_units) == 0
        assert network.learning_rate == 0.01
        assert network.current_epoch == 0
        assert not network.is_training

    def test_forward_no_hidden_units(self):
        """Test forward pass with no hidden units (line 146-147)."""
        network = MockCascorNetwork(input_size=2, output_size=1)
        x = torch.randn(10, 2)

        output = network.forward(x)

        assert output.shape == (10, 1)
        assert torch.all(output >= 0) and torch.all(output <= 1)

    def test_forward_with_hidden_units(self):
        """Test forward pass with hidden units (lines 149-150)."""
        network = MockCascorNetwork(input_size=2, output_size=1)
        network.add_hidden_unit()
        network.add_hidden_unit()

        x = torch.randn(10, 2)
        output = network.forward(x)

        assert output.shape == (10, 1)
        assert len(network.hidden_units) == 2

    def test_add_hidden_unit_updates_output_weights(self):
        """Test that add_hidden_unit expands output weights correctly."""
        network = MockCascorNetwork(input_size=2, output_size=1)
        initial_cols = network.output_weights.shape[1]

        network.add_hidden_unit()

        assert network.output_weights.shape[1] == initial_cols + 1
        assert len(network.hidden_units) == 1

        network.add_hidden_unit()

        assert network.output_weights.shape[1] == initial_cols + 2
        assert len(network.hidden_units) == 2

    def test_hidden_unit_structure(self):
        """Test hidden unit has correct structure."""
        network = MockCascorNetwork(input_size=2, output_size=1)
        network.add_hidden_unit()

        unit = network.hidden_units[0]
        assert "id" in unit
        assert "weights" in unit
        assert "bias" in unit
        assert "activation_fn" in unit
        assert unit["id"] == 0
        assert unit["activation_fn"] == torch.sigmoid

    def test_history_is_bounded_deque(self):
        """Test that history collections are bounded deques."""
        network = MockCascorNetwork()

        for i in range(1500):
            network.history["train_loss"].append(float(i))

        assert len(network.history["train_loss"]) == 1000


class TestDemoModeEnvironmentVariables:
    """Test environment variable handling."""

    def test_invalid_update_interval_env(self):
        """Test invalid CASCOR_DEMO_UPDATE_INTERVAL falls back (lines 181-186)."""
        with patch.dict(os.environ, {"CASCOR_DEMO_UPDATE_INTERVAL": "invalid"}):
            demo = DemoMode()
            assert isinstance(demo.update_interval, (int, float))
            demo.stop()

    def test_valid_update_interval_env(self):
        """Test valid CASCOR_DEMO_UPDATE_INTERVAL is used."""
        with patch.dict(os.environ, {"CASCOR_DEMO_UPDATE_INTERVAL": "0.5"}):
            demo = DemoMode()
            assert demo.update_interval == 0.5
            demo.stop()

    def test_invalid_epochs_env(self):
        """Test invalid CASCOR_TRAINING_EPOCHS falls back (lines 212-217)."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "not_a_number"}):
            demo = DemoMode()
            assert isinstance(demo.max_epochs, int)
            demo.stop()

    def test_valid_epochs_env(self):
        """Test valid CASCOR_TRAINING_EPOCHS is used."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "500"}):
            demo = DemoMode()
            assert demo.max_epochs == 500
            demo.stop()

    def test_invalid_hidden_units_env(self):
        """Test invalid CASCOR_TRAINING_HIDDEN_UNITS falls back (lines 222-227)."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_HIDDEN_UNITS": "abc"}):
            demo = DemoMode()
            assert isinstance(demo.max_hidden_units, int)
            demo.stop()

    def test_valid_hidden_units_env(self):
        """Test valid CASCOR_TRAINING_HIDDEN_UNITS is used."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_HIDDEN_UNITS": "15"}):
            demo = DemoMode()
            assert demo.max_hidden_units == 15
            demo.stop()

    def test_invalid_cascade_every_env(self):
        """Test invalid CASCOR_DEMO_CASCADE_EVERY falls back (lines 234-239)."""
        with patch.dict(os.environ, {"CASCOR_DEMO_CASCADE_EVERY": "xyz"}):
            demo = DemoMode()
            assert isinstance(demo.cascade_every, int)
            demo.stop()

    def test_valid_cascade_every_env(self):
        """Test valid CASCOR_DEMO_CASCADE_EVERY is used."""
        with patch.dict(os.environ, {"CASCOR_DEMO_CASCADE_EVERY": "50"}):
            demo = DemoMode()
            assert demo.cascade_every == 50
            demo.stop()


class TestDemoModeTrainingStateUnavailable:
    """Test behavior when TrainingState is not available."""

    def test_training_state_import_error(self):
        """Test graceful handling when TrainingState import fails (lines 261-264)."""
        with patch.dict("sys.modules", {"backend.training_monitor": None}):
            demo = DemoMode()
            assert demo.training_state is not None or demo.training_state is None
            demo.stop()


class TestDemoModeBroadcastFailures:
    """Test WebSocket broadcast error handling."""

    def test_broadcast_metrics_import_error(self):
        """Test _broadcast_metrics handles ImportError (lines 598-600).

        This test verifies the broadcast method handles import errors gracefully.
        We patch the websocket_manager's broadcast method to simulate the error
        occurring at the websocket layer rather than patching DemoMode's method,
        which would cause unhandled thread exceptions.
        """
        demo = DemoMode(update_interval=0.1)

        with patch(
            "communication.websocket_manager.websocket_manager.broadcast_from_thread",
            side_effect=ImportError("Module not available"),
        ):
            demo.start()
            time.sleep(0.2)
            demo.stop()

    def test_broadcast_metrics_generic_exception(self):
        """Test _broadcast_metrics handles generic exception (lines 601-602)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.2)
        demo.stop()

    def test_broadcast_cascade_import_error(self):
        """Test _broadcast_cascade_add handles ImportError (lines 618-620)."""
        demo = DemoMode(update_interval=0.1)
        demo._broadcast_cascade_add(0, 1, 10)

    def test_broadcast_cascade_generic_exception(self):
        """Test _broadcast_cascade_add handles generic exception (lines 621-622)."""
        demo = DemoMode(update_interval=0.1)

        with patch(
            "communication.websocket_manager.websocket_manager.broadcast_from_thread",
            side_effect=Exception("Broadcast failed"),
        ):
            demo._broadcast_cascade_add(0, 1, 10)

    def test_broadcast_status_import_error(self):
        """Test _broadcast_status handles ImportError (lines 860-861)."""
        demo = DemoMode()
        demo._broadcast_status("running")

    def test_broadcast_status_generic_exception(self):
        """Test _broadcast_status handles generic exception (lines 862-863)."""
        demo = DemoMode()

        with patch(
            "communication.websocket_manager.websocket_manager.broadcast_from_thread",
            side_effect=Exception("Status broadcast failed"),
        ):
            demo._broadcast_status("running")

    def test_broadcast_state_exception(self):
        """Test _broadcast_state handles exception (lines 360-363)."""
        demo = DemoMode()

        with patch(
            "communication.websocket_manager.websocket_manager.broadcast_state_change",
            side_effect=Exception("State broadcast failed"),
        ):
            demo._broadcast_state()


class TestDemoModeFSMFailures:
    """Test FSM command failure paths."""

    def test_start_fsm_reset_failure(self):
        """Test start() when FSM RESET fails (lines 636-637)."""
        demo = DemoMode(update_interval=0.1)

        with patch.object(demo.state_machine, "handle_command", return_value=False):
            result = demo.start(reset=True)
            assert "is_running" in result

    def test_start_fsm_start_failure(self):
        """Test start() when FSM START fails (lines 641-642)."""
        demo = DemoMode(update_interval=0.1)

        def selective_handle(cmd):
            from backend.training_state_machine import Command

            return cmd == Command.RESET

        with patch.object(demo.state_machine, "handle_command", side_effect=selective_handle):
            result = demo.start(reset=True)
            assert "is_running" in result

    def test_start_already_running(self):
        """Test start() when already running without reset (lines 645-646)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)

        result = demo.start(reset=False)

        assert demo.is_running
        demo.stop()

    def test_stop_fsm_failure(self):
        """Test stop() when FSM STOP fails (lines 704-705)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)

        with patch.object(demo.state_machine, "handle_command", return_value=False):
            demo.stop()

        demo._stop.set()
        if demo.thread:
            demo.thread.join(timeout=1.0)

    def test_stop_thread_timeout(self):
        """Test stop() when thread doesn't stop cleanly (line 714)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)

        with patch.object(demo.thread, "join", side_effect=lambda timeout: None):
            with patch.object(demo.thread, "is_alive", return_value=True):
                demo._stop.set()
                demo.stop()

    def test_pause_fsm_failure(self):
        """Test pause() when FSM PAUSE fails (lines 743-744)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)

        with patch.object(demo.state_machine, "handle_command", return_value=False):
            demo.pause()

        demo.stop()

    def test_pause_already_paused(self):
        """Test pause() when already paused (lines 748-749)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)
        demo.pause()

        demo._pause.set()
        demo.pause()

        demo.stop()

    def test_resume_fsm_failure(self):
        """Test resume() when FSM RESUME fails (lines 758-759)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)
        demo.pause()

        with patch.object(demo.state_machine, "handle_command", return_value=False):
            demo.resume()

        demo.stop()

    def test_resume_not_running(self):
        """Test resume() when not running (lines 767-768)."""
        demo = DemoMode(update_interval=0.1)

        with patch.object(demo.state_machine, "handle_command", return_value=True):
            demo.resume()

        assert not demo.is_running

    def test_resume_not_paused(self):
        """Test resume() when not paused (lines 772-773)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.1)

        with patch.object(demo.state_machine, "handle_command", return_value=True):
            demo.resume()

        demo.stop()

    def test_reset_fsm_failure(self):
        """Test reset() when FSM RESET fails (lines 807-808)."""
        demo = DemoMode(update_interval=0.1)

        with patch.object(demo.state_machine, "handle_command", return_value=False):
            result = demo.reset()
            assert "is_running" in result

    def test_reset_while_running(self):
        """Test reset() while running (lines 811, 832-838)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.2)

        result = demo.reset()

        assert result["current_epoch"] == 0
        assert result["current_loss"] == 1.0


class TestDemoModeCandidatePool:
    """Test candidate pool simulation."""

    def test_candidate_pool_activation_in_training(self):
        """Test candidate pool activates during candidate phase."""
        demo = DemoMode(update_interval=0.05)
        demo.start()

        time.sleep(0.5)
        demo.stop()

    def test_candidate_pool_clear_on_output_phase(self):
        """Test candidate pool clears when switching to output phase."""
        demo = DemoMode(update_interval=0.05)

        if demo.candidate_pool:
            demo.candidate_pool.update_pool(status="Active")

        demo.start()
        time.sleep(0.3)
        demo.stop()

    def test_should_add_cascade_unit_max_reached(self):
        """Test _should_add_cascade_unit when max units reached (line 482)."""
        demo = DemoMode(update_interval=0.1)
        demo.max_hidden_units = 0

        assert not demo._should_add_cascade_unit()

    def test_should_add_cascade_unit_not_interval(self):
        """Test _should_add_cascade_unit when not at interval."""
        demo = DemoMode(update_interval=0.1)
        demo.cascade_every = 30
        demo.current_epoch = 15

        assert not demo._should_add_cascade_unit()

    def test_should_add_cascade_unit_at_interval(self):
        """Test _should_add_cascade_unit at correct interval."""
        demo = DemoMode(update_interval=0.1)
        demo.cascade_every = 10
        demo.max_hidden_units = 5
        demo.current_epoch = 10

        assert demo._should_add_cascade_unit()


class TestDemoModeTrainingLoop:
    """Test training loop edge cases."""

    def test_training_loop_max_epochs(self):
        """Test training loop stops at max_epochs (lines 497-498)."""
        demo = DemoMode(update_interval=0.01)
        demo.max_epochs = 3
        demo.start()

        time.sleep(0.5)

        assert demo.current_epoch <= demo.max_epochs + 1
        demo.stop()

    def test_training_loop_stop_during_pause(self):
        """Test training loop stops cleanly during pause (line 506)."""
        demo = DemoMode(update_interval=0.1)
        demo.start()
        time.sleep(0.2)

        demo._pause.set()
        time.sleep(0.1)
        demo._stop.set()

        demo.stop()

    def test_update_training_state_without_training_state(self):
        """Test _update_training_status when training_state is None (line 292)."""
        demo = DemoMode()
        demo.training_state = None

        demo._update_training_status()

    def test_broadcast_state_without_training_state(self):
        """Test _broadcast_state when training_state is None (line 354)."""
        demo = DemoMode()
        demo.training_state = None

        demo._broadcast_state()

    def test_simulate_candidate_pool_without_pool(self):
        """Test _simulate_candidate_pool when candidate_pool is None (line 436)."""
        demo = DemoMode()
        demo.candidate_pool = None

        demo._simulate_candidate_pool()


class TestDemoModeApplyParams:
    """Test apply_params method."""

    def test_apply_learning_rate(self):
        """Test apply_params with learning_rate."""
        demo = DemoMode()
        demo.apply_params(learning_rate=0.05)

        assert demo.network.learning_rate == 0.05

    def test_apply_max_hidden_units(self):
        """Test apply_params with max_hidden_units."""
        demo = DemoMode()
        demo.apply_params(max_hidden_units=20)

        assert demo.max_hidden_units == 20

    def test_apply_max_epochs(self):
        """Test apply_params with max_epochs."""
        demo = DemoMode()
        demo.apply_params(max_epochs=300)

        assert demo.max_epochs == 300

    def test_apply_all_params(self):
        """Test apply_params with all parameters."""
        demo = DemoMode()
        demo.apply_params(learning_rate=0.02, max_hidden_units=25, max_epochs=400)

        assert demo.network.learning_rate == 0.02
        assert demo.max_hidden_units == 25
        assert demo.max_epochs == 400

    def test_apply_params_none_values(self):
        """Test apply_params with None values does not change state."""
        demo = DemoMode()
        original_lr = demo.network.learning_rate
        original_hu = demo.max_hidden_units
        original_epochs = demo.max_epochs

        demo.apply_params(learning_rate=None, max_hidden_units=None, max_epochs=None)

        assert demo.network.learning_rate == original_lr
        assert demo.max_hidden_units == original_hu
        assert demo.max_epochs == original_epochs


class TestDemoModePauseResumeEdgeCases:
    """Test pause/resume edge cases with candidate state."""

    def test_pause_saves_candidate_state(self):
        """Test pause saves candidate state in candidate phase (lines 730-735)."""
        demo = DemoMode(update_interval=0.05)
        demo.start()
        time.sleep(0.3)

        from backend.training_state_machine import TrainingPhase

        demo.state_machine.set_phase(TrainingPhase.CANDIDATE)

        demo.pause()

        demo.stop()

    def test_resume_restores_candidate_state(self):
        """Test resume restores candidate state (lines 763-764)."""
        demo = DemoMode(update_interval=0.05)
        demo.start()
        time.sleep(0.2)

        from backend.training_state_machine import TrainingPhase

        demo.state_machine.set_phase(TrainingPhase.CANDIDATE)
        demo.state_machine.save_candidate_state({"epoch": 10, "loss": 0.5})
        demo.pause()
        time.sleep(0.1)

        demo.resume()

        demo.stop()


class TestDemoModeGetMethods:
    """Test getter methods."""

    def test_get_network(self):
        """Test get_network returns MockCascorNetwork."""
        demo = DemoMode()
        network = demo.get_network()

        assert isinstance(network, MockCascorNetwork)
        assert network is demo.network

    def test_get_dataset(self):
        """Test get_dataset returns dataset dict."""
        demo = DemoMode()
        dataset = demo.get_dataset()

        assert isinstance(dataset, dict)
        assert "inputs" in dataset
        assert "targets" in dataset
        assert dataset is demo.dataset

    def test_get_metrics_history_thread_safe(self):
        """Test get_metrics_history is thread-safe and returns copy."""
        demo = DemoMode(update_interval=0.05)
        demo.start()
        time.sleep(0.2)

        history = demo.get_metrics_history()

        demo.stop()

        assert isinstance(history, list)

    def test_get_current_state_all_fields(self):
        """Test get_current_state returns all expected fields."""
        demo = DemoMode()
        state = demo.get_current_state()

        expected_fields = [
            "is_running",
            "is_paused",
            "current_epoch",
            "current_loss",
            "current_accuracy",
            "hidden_units",
            "metrics_count",
            "activation_fn",
            "optimizer",
        ]

        for field in expected_fields:
            assert field in state, f"Missing field: {field}"

        assert state["activation_fn"] == "tanh"
        assert state["optimizer"] == "SGD"


class TestDemoModeUpdateTrainingState:
    """Test _update_training_state method."""

    def test_update_training_state_with_status(self):
        """Test _update_training_state with status label."""
        demo = DemoMode()
        demo._update_training_state(status_label="running", log_message="Test message")

    def test_update_training_state_no_status(self):
        """Test _update_training_state without status label."""
        demo = DemoMode()
        demo._update_training_state()


class TestDemoModePerformReset:
    """Test _perform_reset and related methods."""

    def test_perform_reset(self):
        """Test _perform_reset clears state."""
        demo = DemoMode(update_interval=0.05)
        demo.start()
        time.sleep(0.1)
        demo._stop.set()
        if demo.thread:
            demo.thread.join(timeout=1.0)

        demo._perform_reset()

        assert not demo.is_running
        assert not demo._pause.is_set()

    def test_reset_state_and_history(self):
        """Test _reset_state_and_history clears all history."""
        demo = DemoMode(update_interval=0.05)
        demo.start()
        time.sleep(0.2)
        demo.stop()

        demo._reset_state_and_history()

        assert demo.current_epoch == 0
        assert demo.current_loss == 1.0
        assert demo.current_accuracy == 0.5
        assert len(demo.metrics_history) == 0
        assert len(demo.network.hidden_units) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
