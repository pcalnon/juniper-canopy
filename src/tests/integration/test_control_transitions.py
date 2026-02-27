#!/usr/bin/env python
"""
Integration tests for control command transitions with DemoMode.

Tests the full integration of FSM with demo mode training control.
"""
import time

import pytest

from backend.training_state_machine import Command, TrainingPhase
from demo_mode import DemoMode


class TestDemoModeControlTransitions:
    """Integration tests for demo mode control transitions."""

    @pytest.fixture
    def demo_mode(self):
        """Create DemoMode instance for testing."""
        demo = DemoMode(update_interval=0.1)
        yield demo
        # Cleanup
        if demo.is_running:
            demo.stop()

    def test_start_to_pause_in_output_to_resume(self, demo_mode):
        """Test: Start → Pause in Output → Resume → verify continues in Output."""
        # Start training
        demo_mode.start(reset=True)
        assert demo_mode.state_machine.is_started()

        # Wait briefly to enter Output phase
        time.sleep(0.2)
        demo_mode.state_machine.set_phase(TrainingPhase.OUTPUT)

        # Pause
        demo_mode.pause()
        assert demo_mode.state_machine.is_paused()
        assert demo_mode.state_machine.get_paused_phase() == TrainingPhase.OUTPUT

        # Resume
        demo_mode.resume()
        assert demo_mode.state_machine.is_started()
        assert demo_mode.state_machine.get_phase() == TrainingPhase.OUTPUT

        # Cleanup
        demo_mode.stop()

    def test_start_to_pause_in_candidate_to_resume(self, demo_mode):
        """Test: Start → Pause in Candidate → Resume → verify continues in Candidate."""
        # Start training
        demo_mode.start(reset=True)
        assert demo_mode.state_machine.is_started()

        # Wait and force Candidate phase
        time.sleep(0.2)
        demo_mode.state_machine.set_phase(TrainingPhase.CANDIDATE)

        # Save some candidate state
        candidate_state = {"epoch": 10, "loss": 0.5}
        demo_mode.state_machine.save_candidate_state(candidate_state)

        # Pause
        demo_mode.pause()
        assert demo_mode.state_machine.is_paused()
        assert demo_mode.state_machine.get_paused_phase() == TrainingPhase.CANDIDATE

        # Resume
        demo_mode.resume()
        assert demo_mode.state_machine.is_started()
        assert demo_mode.state_machine.get_phase() == TrainingPhase.CANDIDATE

        # Candidate state should persist
        restored_state = demo_mode.state_machine.get_candidate_state()
        assert restored_state is not None
        assert restored_state["epoch"] == 10

        # Cleanup
        demo_mode.stop()

    def test_start_to_pause_to_start_acts_as_resume(self, demo_mode):
        """Test: Start → Pause → Start → verify resumes (not restart)."""
        # Start training
        demo_mode.start(reset=True)
        initial_epoch = demo_mode.current_epoch

        # Wait for some epochs
        time.sleep(0.3)
        demo_mode.state_machine.set_phase(TrainingPhase.CANDIDATE)

        # Pause
        demo_mode.pause()
        paused_epoch = demo_mode.current_epoch
        assert paused_epoch > initial_epoch
        assert demo_mode.state_machine.is_paused()

        # Call start (should act as resume, not restart)
        demo_mode.start(reset=False)
        assert demo_mode.state_machine.is_started()
        assert demo_mode.state_machine.get_phase() == TrainingPhase.CANDIDATE

        # Epoch should not reset
        assert demo_mode.current_epoch >= paused_epoch

        # Cleanup
        demo_mode.stop()

    def test_start_to_stop_truly_stops(self, demo_mode):
        """Test: Start → Stop → verify truly stops (doesn't resume)."""
        # Start training
        demo_mode.start(reset=True)
        assert demo_mode.state_machine.is_started()
        assert demo_mode.is_running

        # Wait briefly
        time.sleep(0.2)

        # Stop
        demo_mode.stop()
        assert demo_mode.state_machine.is_stopped()

        # Wait to ensure it doesn't resume
        time.sleep(0.3)

        # Should remain stopped
        assert demo_mode.state_machine.is_stopped()
        assert not demo_mode.is_running
        assert demo_mode.state_machine.get_phase() == TrainingPhase.IDLE

    def test_invalid_transitions_rejected(self, demo_mode):
        """Test invalid transitions are rejected and logged."""
        # Try to pause when stopped
        demo_mode.pause()
        assert demo_mode.state_machine.is_stopped()

        # Try to resume when stopped
        demo_mode.resume()
        assert demo_mode.state_machine.is_stopped()

        # Start training
        demo_mode.start(reset=True)
        time.sleep(0.1)

        # Try to start when already started
        _ = demo_mode.state_machine.get_phase()
        result = demo_mode.state_machine.handle_command(Command.START)
        # Should fail but not crash
        assert result is False

        # Cleanup
        demo_mode.stop()

    def test_reset_clears_all_state(self, demo_mode):
        """Test reset command clears all training state."""
        # Start training and accumulate some state
        demo_mode.start(reset=True)
        time.sleep(0.3)

        # Force candidate phase and save state
        demo_mode.state_machine.set_phase(TrainingPhase.CANDIDATE)
        demo_mode.state_machine.save_candidate_state({"epoch": 20})

        epoch_before_reset = demo_mode.current_epoch
        assert epoch_before_reset > 0

        # Reset
        demo_mode.reset()

        # All state should be cleared
        assert demo_mode.state_machine.is_stopped()
        assert demo_mode.state_machine.get_phase() == TrainingPhase.IDLE
        assert demo_mode.state_machine.get_candidate_state() is None
        assert demo_mode.current_epoch == 0
        assert not demo_mode.is_running

    def test_rapid_start_pause_resume_stop(self, demo_mode):
        """Test rapid sequence of control commands."""
        # Rapid sequence
        demo_mode.start(reset=True)
        assert demo_mode.state_machine.is_started()

        time.sleep(0.1)

        demo_mode.pause()
        assert demo_mode.state_machine.is_paused()

        time.sleep(0.05)

        demo_mode.resume()
        assert demo_mode.state_machine.is_started()

        time.sleep(0.1)

        demo_mode.stop()
        assert demo_mode.state_machine.is_stopped()

    def test_pause_resume_preserves_training_progress(self, demo_mode):
        """Test pause/resume preserves training progress."""
        # Start training
        demo_mode.start(reset=True)
        time.sleep(0.3)

        # Pause and capture state after pause takes effect
        demo_mode.pause()
        epoch_at_pause = demo_mode.current_epoch
        loss_at_pause = demo_mode.current_loss

        # Wait while paused
        time.sleep(0.2)

        # Epoch should not advance during pause
        assert demo_mode.current_epoch == epoch_at_pause

        # Resume
        demo_mode.resume()
        time.sleep(0.3)

        # Training should continue from where it left off
        assert demo_mode.current_epoch > epoch_at_pause
        # Loss should continue to decrease
        assert demo_mode.current_loss <= loss_at_pause

        # Cleanup
        demo_mode.stop()

    def test_candidate_phase_state_persists_across_pause_resume(self, demo_mode):
        """Test candidate phase state is preserved through pause/resume cycle."""
        # Start training
        demo_mode.start(reset=True)
        time.sleep(0.2)

        # Enter candidate phase manually
        demo_mode.state_machine.set_phase(TrainingPhase.CANDIDATE)

        # Pause (should save candidate state)
        demo_mode.pause()
        saved_phase = demo_mode.state_machine.get_paused_phase()
        assert saved_phase == TrainingPhase.CANDIDATE

        # Resume (should restore candidate phase)
        demo_mode.resume()
        current_phase = demo_mode.state_machine.get_phase()
        assert current_phase == TrainingPhase.CANDIDATE

        # Cleanup
        demo_mode.stop()


class TestStateConsistency:
    """Test state consistency across components."""

    @pytest.fixture
    def demo_mode(self):
        """Create DemoMode instance for testing."""
        demo = DemoMode(update_interval=0.1)
        yield demo
        if demo.is_running:
            demo.stop()

    def test_fsm_and_demo_state_consistency(self, demo_mode):
        """Test FSM state matches demo mode state."""
        # Initially stopped
        assert demo_mode.state_machine.is_stopped()
        assert not demo_mode.is_running

        # Start
        demo_mode.start(reset=True)
        assert demo_mode.state_machine.is_started()
        assert demo_mode.is_running

        # Pause
        demo_mode.pause()
        assert demo_mode.state_machine.is_paused()
        assert demo_mode._pause.is_set()

        # Resume
        demo_mode.resume()
        assert demo_mode.state_machine.is_started()
        assert not demo_mode._pause.is_set()

        # Stop
        demo_mode.stop()
        assert demo_mode.state_machine.is_stopped()
        assert not demo_mode.is_running

    def test_training_state_reflects_fsm_state(self, demo_mode):
        """Test TrainingState reflects FSM state."""
        if not demo_mode.training_state:
            pytest.skip("TrainingState not available")

        # Start
        demo_mode.start(reset=True)
        time.sleep(0.1)
        state = demo_mode.training_state.get_state()
        assert state["status"] == "STARTED"

        # Pause
        demo_mode.pause()
        state = demo_mode.training_state.get_state()
        assert state["status"] == "PAUSED"

        # Resume
        demo_mode.resume()
        state = demo_mode.training_state.get_state()
        assert state["status"] == "STARTED"

        # Stop
        demo_mode.stop()
        state = demo_mode.training_state.get_state()
        assert state["status"] == "STOPPED"


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def demo_mode(self):
        """Create DemoMode instance for testing."""
        demo = DemoMode(update_interval=0.1)
        yield demo
        if demo.is_running:
            demo.stop()

    def test_double_start_idempotent(self, demo_mode):
        """Test calling start twice is handled gracefully."""
        demo_mode.start(reset=True)
        assert demo_mode.state_machine.is_started()

        # Second start without reset should be rejected by FSM
        result = demo_mode.state_machine.handle_command(Command.START)
        assert result is False

        # Cleanup
        demo_mode.stop()

    def test_double_stop_idempotent(self, demo_mode):
        """Test calling stop twice is handled gracefully."""
        demo_mode.start(reset=True)
        demo_mode.stop()
        assert demo_mode.state_machine.is_stopped()

        # Second stop should be handled gracefully
        demo_mode.stop()
        assert demo_mode.state_machine.is_stopped()

    def test_phase_transitions_during_training(self, demo_mode):
        """Test phase transitions occur naturally during training."""
        demo_mode.start(reset=True)

        # Let it run and check for phase transitions
        phases_seen = set()
        for _ in range(10):
            time.sleep(0.1)
            phase = demo_mode.state_machine.get_phase()
            phases_seen.add(phase)

        # Should see at least OUTPUT phase
        assert TrainingPhase.OUTPUT in phases_seen or TrainingPhase.CANDIDATE in phases_seen

        # Cleanup
        demo_mode.stop()
