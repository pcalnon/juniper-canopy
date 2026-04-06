#!/usr/bin/env python
"""
Unit tests for TrainingStateMachine.

Tests all valid and invalid state transitions using table-driven approach.
"""

import pytest

from backend.training_state_machine import Command, TrainingPhase, TrainingStateMachine, TrainingStatus


class TestTrainingStateMachineBasics:
    """Basic state machine functionality tests."""

    def test_initial_state(self):
        """Test state machine starts in Stopped state."""
        fsm = TrainingStateMachine()
        assert fsm.is_stopped()
        assert not fsm.is_started()
        assert not fsm.is_paused()
        assert fsm.get_status() == TrainingStatus.STOPPED
        assert fsm.get_phase() == TrainingPhase.IDLE
        assert fsm.get_paused_phase() is None

    def test_get_state_summary(self):
        """Test state summary returns correct dictionary."""
        fsm = TrainingStateMachine()
        summary = fsm.get_state_summary()
        assert summary["status"] == "STOPPED"
        assert summary["phase"] == "IDLE"
        assert summary["paused_phase"] is None
        assert summary["has_candidate_state"] is False


class TestValidTransitions:
    """Test all valid state transitions."""

    @pytest.mark.parametrize(
        "initial_status,command,expected_status,expected_phase",
        [
            # From STOPPED
            (TrainingStatus.STOPPED, Command.START, TrainingStatus.STARTED, TrainingPhase.OUTPUT),
            (TrainingStatus.STOPPED, Command.RESET, TrainingStatus.STOPPED, TrainingPhase.IDLE),
            # From STARTED
            (TrainingStatus.STARTED, Command.PAUSE, TrainingStatus.PAUSED, TrainingPhase.OUTPUT),
            (TrainingStatus.STARTED, Command.STOP, TrainingStatus.STOPPED, TrainingPhase.IDLE),
            (TrainingStatus.STARTED, Command.RESET, TrainingStatus.STOPPED, TrainingPhase.IDLE),
            # From PAUSED
            (TrainingStatus.PAUSED, Command.RESUME, TrainingStatus.STARTED, TrainingPhase.OUTPUT),
            (
                TrainingStatus.PAUSED,
                Command.START,
                TrainingStatus.STARTED,
                TrainingPhase.OUTPUT,
            ),  # START acts as RESUME
            (TrainingStatus.PAUSED, Command.STOP, TrainingStatus.STOPPED, TrainingPhase.IDLE),
            (TrainingStatus.PAUSED, Command.RESET, TrainingStatus.STOPPED, TrainingPhase.IDLE),
        ],
    )
    def test_valid_transition(self, initial_status, command, expected_status, expected_phase):
        """Test valid state transitions."""
        fsm = TrainingStateMachine()

        # Set up initial state
        if initial_status == TrainingStatus.STARTED:
            fsm.handle_command(Command.START)
        elif initial_status == TrainingStatus.PAUSED:
            fsm.handle_command(Command.START)
            fsm.handle_command(Command.PAUSE)

        # Execute transition
        result = fsm.handle_command(command)

        # Verify transition succeeded
        assert result is True
        assert fsm.get_status() == expected_status
        assert fsm.get_phase() == expected_phase


class TestInvalidTransitions:
    """Test all invalid state transitions are rejected."""

    @pytest.mark.parametrize(
        "initial_status,command",
        [
            # From STOPPED - invalid commands
            (TrainingStatus.STOPPED, Command.PAUSE),
            (TrainingStatus.STOPPED, Command.RESUME),
            (TrainingStatus.STOPPED, Command.STOP),
            # From STARTED - invalid commands
            (TrainingStatus.STARTED, Command.START),
            (TrainingStatus.STARTED, Command.RESUME),
            # From PAUSED - invalid commands
            (TrainingStatus.PAUSED, Command.PAUSE),
        ],
    )
    def test_invalid_transition(self, initial_status, command):
        """Test invalid transitions are rejected."""
        fsm = TrainingStateMachine()

        # Set up initial state
        if initial_status == TrainingStatus.STARTED:
            fsm.handle_command(Command.START)
        elif initial_status == TrainingStatus.PAUSED:
            fsm.handle_command(Command.START)
            fsm.handle_command(Command.PAUSE)

        # Execute invalid transition
        result = fsm.handle_command(command)

        # Verify transition rejected
        assert result is False
        # State should remain unchanged
        assert fsm.get_status() == initial_status


class TestPauseResumeBehavior:
    """Test pause/resume preserves phase state."""

    def test_pause_saves_output_phase(self):
        """Test pausing in Output phase saves state."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.OUTPUT)

        fsm.handle_command(Command.PAUSE)

        assert fsm.is_paused()
        assert fsm.get_paused_phase() == TrainingPhase.OUTPUT

    def test_pause_saves_candidate_phase(self):
        """Test pausing in Candidate phase saves state."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)

        fsm.handle_command(Command.PAUSE)

        assert fsm.is_paused()
        assert fsm.get_paused_phase() == TrainingPhase.CANDIDATE

    def test_resume_restores_output_phase(self):
        """Test resuming from Output phase restores state."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.OUTPUT)
        fsm.handle_command(Command.PAUSE)

        fsm.handle_command(Command.RESUME)

        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.OUTPUT
        assert fsm.get_paused_phase() is None

    def test_resume_restores_candidate_phase(self):
        """Test resuming from Candidate phase restores state."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)
        fsm.handle_command(Command.PAUSE)

        fsm.handle_command(Command.RESUME)

        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.CANDIDATE
        assert fsm.get_paused_phase() is None

    def test_start_when_paused_acts_as_resume(self):
        """Test START command when paused acts as RESUME."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)
        fsm.handle_command(Command.PAUSE)

        # START should act as RESUME
        result = fsm.handle_command(Command.START)

        assert result is True
        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.CANDIDATE
        assert fsm.get_paused_phase() is None


class TestCandidatePhaseHandling:
    """Test special handling for Candidate phase."""

    def test_save_candidate_state(self):
        """Test saving candidate sub-state."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)

        candidate_state = {"epoch": 42, "loss": 0.5, "accuracy": 0.8}
        fsm.save_candidate_state(candidate_state)

        retrieved_state = fsm.get_candidate_state()
        assert retrieved_state is not None
        assert retrieved_state["epoch"] == 42
        assert retrieved_state["loss"] == 0.5
        assert retrieved_state["accuracy"] == 0.8

    def test_candidate_state_persists_across_pause_resume(self):
        """Test candidate state persists through pause/resume."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)

        candidate_state = {"epoch": 42, "loss": 0.5}
        fsm.save_candidate_state(candidate_state)

        # Pause and resume
        fsm.handle_command(Command.PAUSE)
        fsm.handle_command(Command.RESUME)

        # Candidate state should persist
        retrieved_state = fsm.get_candidate_state()
        assert retrieved_state is not None
        assert retrieved_state["epoch"] == 42

    def test_candidate_state_cleared_on_reset(self):
        """Test candidate state cleared on reset."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)

        candidate_state = {"epoch": 42}
        fsm.save_candidate_state(candidate_state)

        # Reset
        fsm.handle_command(Command.RESET)

        # Candidate state should be cleared
        assert fsm.get_candidate_state() is None

    def test_candidate_state_cleared_on_stop(self):
        """Test candidate state cleared on stop."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)

        candidate_state = {"epoch": 42}
        fsm.save_candidate_state(candidate_state)

        # Stop
        fsm.handle_command(Command.STOP)

        # Candidate state should be cleared
        assert fsm.get_candidate_state() is None


class TestPhaseTransitions:
    """Test phase change behavior."""

    def test_set_phase_when_started(self):
        """Test setting phase when started."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)

        fsm.set_phase(TrainingPhase.CANDIDATE)
        assert fsm.get_phase() == TrainingPhase.CANDIDATE

        fsm.set_phase(TrainingPhase.OUTPUT)
        assert fsm.get_phase() == TrainingPhase.OUTPUT

        fsm.set_phase(TrainingPhase.INFERENCE)
        assert fsm.get_phase() == TrainingPhase.INFERENCE

    def test_set_phase_when_not_started_ignored(self):
        """Test setting phase when not started is ignored."""
        fsm = TrainingStateMachine()

        fsm.set_phase(TrainingPhase.CANDIDATE)
        # Should remain IDLE
        assert fsm.get_phase() == TrainingPhase.IDLE


class TestRapidCommandSequences:
    """Test rapid command sequences."""

    def test_rapid_start_stop_start(self):
        """Test rapid start-stop-start sequence."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        assert fsm.is_started()

        fsm.handle_command(Command.STOP)
        assert fsm.is_stopped()

        fsm.handle_command(Command.START)
        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.OUTPUT

    def test_rapid_pause_resume_pause(self):
        """Test rapid pause-resume-pause sequence."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)

        fsm.handle_command(Command.PAUSE)
        assert fsm.is_paused()

        fsm.handle_command(Command.RESUME)
        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.CANDIDATE

        fsm.handle_command(Command.PAUSE)
        assert fsm.is_paused()
        assert fsm.get_paused_phase() == TrainingPhase.CANDIDATE

    def test_reset_from_any_state(self):
        """Test reset works from any state."""
        fsm = TrainingStateMachine()

        # Reset from STOPPED
        fsm.handle_command(Command.RESET)
        assert fsm.is_stopped()

        # Reset from STARTED
        fsm.handle_command(Command.START)
        fsm.handle_command(Command.RESET)
        assert fsm.is_stopped()

        # Reset from PAUSED
        fsm.handle_command(Command.START)
        fsm.handle_command(Command.PAUSE)
        fsm.handle_command(Command.RESET)
        assert fsm.is_stopped()


class TestResetBehavior:
    """Test RESET command behavior."""

    def test_reset_clears_all_state(self):
        """Test reset clears all state."""
        fsm = TrainingStateMachine()
        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)
        fsm.save_candidate_state({"epoch": 42})
        fsm.handle_command(Command.PAUSE)

        fsm.handle_command(Command.RESET)

        assert fsm.is_stopped()
        assert fsm.get_phase() == TrainingPhase.IDLE
        assert fsm.get_paused_phase() is None
        assert fsm.get_candidate_state() is None

    def test_reset_always_succeeds(self):
        """Test reset always succeeds regardless of current state."""
        states_to_test = [
            TrainingStatus.STOPPED,
            TrainingStatus.STARTED,
            TrainingStatus.PAUSED,
        ]

        for state in states_to_test:
            fsm = TrainingStateMachine()

            # Set up state
            if state == TrainingStatus.STARTED:
                fsm.handle_command(Command.START)
            elif state == TrainingStatus.PAUSED:
                fsm.handle_command(Command.START)
                fsm.handle_command(Command.PAUSE)

            # Reset should always succeed
            result = fsm.handle_command(Command.RESET)
            assert result is True
            assert fsm.is_stopped()
