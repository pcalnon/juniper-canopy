#!/usr/bin/env python
"""
Coverage completion tests for TrainingStateMachine.

Targets specific uncovered lines to reach 95% coverage:
- Lines 147-148: handle_command with unknown command
- Line 161: _handle_start returning False from COMPLETED/FAILED state
- Line 203: _handle_pause returning False from COMPLETED/FAILED state
- Line 219: _handle_resume returning False from COMPLETED/FAILED state
- Lines 227-228: _check_for_paused_state with no paused_phase
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.training_state_machine import (
    Command,
    TrainingPhase,
    TrainingStateMachine,
    TrainingStatus,
)


class TestUnknownCommandHandling:
    """Test handle_command with unknown/invalid command types (lines 147-148)."""

    def test_handle_command_with_mock_unknown_command(self):
        """Test handle_command returns False for unknown command type."""
        fsm = TrainingStateMachine()

        # Create a mock that doesn't match any known Command
        mock_command = MagicMock()
        mock_command.name = "UNKNOWN"

        # Patch the comparison to ensure we hit the else branch
        result = fsm.handle_command(mock_command)

        assert result is False

    def test_handle_command_with_none_bypassing_enum_check(self):
        """Test handle_command with None (falls through to else branch)."""
        fsm = TrainingStateMachine()

        # None doesn't match any Command enum, so hits else branch
        result = fsm.handle_command(None)

        assert result is False


class TestHandleStartFromTerminalStates:
    """Test _handle_start returning False from COMPLETED/FAILED states (line 161)."""

    def test_start_from_completed_state_returns_false(self):
        """Test START command from COMPLETED state returns False."""
        fsm = TrainingStateMachine()

        # Get to COMPLETED state
        fsm.handle_command(Command.START)
        fsm.mark_completed()

        assert fsm.is_completed()

        # START from COMPLETED should return False (line 161)
        result = fsm.handle_command(Command.START)

        assert result is False
        assert fsm.is_completed()  # State unchanged

    def test_start_from_failed_state_returns_false(self):
        """Test START command from FAILED state returns False."""
        fsm = TrainingStateMachine()

        # Get to FAILED state
        fsm.handle_command(Command.START)
        fsm.mark_failed("Test failure")

        assert fsm.is_failed()

        # START from FAILED should return False (line 161)
        result = fsm.handle_command(Command.START)

        assert result is False
        assert fsm.is_failed()  # State unchanged


class TestHandlePauseFromTerminalStates:
    """Test _handle_pause returning False from COMPLETED/FAILED states (line 203)."""

    def test_pause_from_completed_state_returns_false(self):
        """Test PAUSE command from COMPLETED state returns False."""
        fsm = TrainingStateMachine()

        # Get to COMPLETED state
        fsm.handle_command(Command.START)
        fsm.mark_completed()

        assert fsm.is_completed()

        # PAUSE from COMPLETED should return False (line 203)
        result = fsm.handle_command(Command.PAUSE)

        assert result is False
        assert fsm.is_completed()  # State unchanged

    def test_pause_from_failed_state_returns_false(self):
        """Test PAUSE command from FAILED state returns False."""
        fsm = TrainingStateMachine()

        # Get to FAILED state
        fsm.handle_command(Command.START)
        fsm.mark_failed("Test failure")

        assert fsm.is_failed()

        # PAUSE from FAILED should return False (line 203)
        result = fsm.handle_command(Command.PAUSE)

        assert result is False
        assert fsm.is_failed()  # State unchanged


class TestHandleResumeFromTerminalStates:
    """Test _handle_resume returning False from COMPLETED/FAILED states (line 219)."""

    def test_resume_from_completed_state_returns_false(self):
        """Test RESUME command from COMPLETED state returns False."""
        fsm = TrainingStateMachine()

        # Get to COMPLETED state
        fsm.handle_command(Command.START)
        fsm.mark_completed()

        assert fsm.is_completed()

        # RESUME from COMPLETED should return False (line 219)
        result = fsm.handle_command(Command.RESUME)

        assert result is False
        assert fsm.is_completed()  # State unchanged

    def test_resume_from_failed_state_returns_false(self):
        """Test RESUME command from FAILED state returns False."""
        fsm = TrainingStateMachine()

        # Get to FAILED state
        fsm.handle_command(Command.START)
        fsm.mark_failed("Test failure")

        assert fsm.is_failed()

        # RESUME from FAILED should return False (line 219)
        result = fsm.handle_command(Command.RESUME)

        assert result is False
        assert fsm.is_failed()  # State unchanged


class TestCheckForPausedStateWithNoPausedPhase:
    """Test _check_for_paused_state when __paused_phase is None (lines 227-228)."""

    def test_resume_with_no_saved_paused_phase(self):
        """Test RESUME when paused_phase is None defaults to OUTPUT phase."""
        fsm = TrainingStateMachine()

        # Start and pause to get into PAUSED state
        fsm.handle_command(Command.START)
        fsm.handle_command(Command.PAUSE)

        assert fsm.is_paused()
        assert fsm.get_paused_phase() == TrainingPhase.OUTPUT

        # Manually clear the paused_phase to simulate edge case
        # Access private attribute to set up the edge case
        fsm._TrainingStateMachine__paused_phase = None

        assert fsm.get_paused_phase() is None  # Verify it's None

        # RESUME with no paused_phase should default to OUTPUT (lines 227-228)
        result = fsm.handle_command(Command.RESUME)

        assert result is True
        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.OUTPUT

    def test_start_from_paused_with_no_saved_paused_phase(self):
        """Test START from PAUSED when paused_phase is None defaults to OUTPUT."""
        fsm = TrainingStateMachine()

        # Start and pause
        fsm.handle_command(Command.START)
        fsm.handle_command(Command.PAUSE)

        # Manually clear paused_phase
        fsm._TrainingStateMachine__paused_phase = None

        # START from PAUSED with no paused_phase
        result = fsm.handle_command(Command.START)

        assert result is True
        assert fsm.is_started()
        assert fsm.get_phase() == TrainingPhase.OUTPUT


class TestTerminalStateTransitions:
    """Additional tests for COMPLETED and FAILED terminal states."""

    def test_stop_from_completed_state_returns_false(self):
        """Test STOP from COMPLETED state returns False."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.mark_completed()

        result = fsm.handle_command(Command.STOP)

        assert result is False
        assert fsm.is_completed()

    def test_stop_from_failed_state_returns_false(self):
        """Test STOP from FAILED state returns False."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.mark_failed("Error")

        result = fsm.handle_command(Command.STOP)

        assert result is False
        assert fsm.is_failed()

    def test_reset_from_completed_state(self):
        """Test RESET from COMPLETED state transitions to STOPPED."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.mark_completed()

        assert fsm.is_completed()

        result = fsm.handle_command(Command.RESET)

        assert result is True
        assert fsm.is_stopped()
        assert fsm.get_phase() == TrainingPhase.IDLE

    def test_reset_from_failed_state(self):
        """Test RESET from FAILED state transitions to STOPPED."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.mark_failed("Error")

        assert fsm.is_failed()

        result = fsm.handle_command(Command.RESET)

        assert result is True
        assert fsm.is_stopped()
        assert fsm.get_phase() == TrainingPhase.IDLE

    def test_mark_completed_from_paused_fails(self):
        """Test mark_completed from PAUSED state returns False."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.handle_command(Command.PAUSE)

        result = fsm.mark_completed()

        assert result is False
        assert fsm.is_paused()

    def test_mark_completed_from_stopped_fails(self):
        """Test mark_completed from STOPPED state returns False."""
        fsm = TrainingStateMachine()

        result = fsm.mark_completed()

        assert result is False
        assert fsm.is_stopped()

    def test_mark_failed_from_stopped_fails(self):
        """Test mark_failed from STOPPED state returns False."""
        fsm = TrainingStateMachine()

        result = fsm.mark_failed("Error")

        assert result is False
        assert fsm.is_stopped()

    def test_mark_failed_from_completed_fails(self):
        """Test mark_failed from COMPLETED state returns False."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.mark_completed()

        result = fsm.mark_failed("Error")

        assert result is False
        assert fsm.is_completed()

    def test_mark_failed_from_failed_fails(self):
        """Test mark_failed from FAILED state returns False."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.mark_failed("First error")

        result = fsm.mark_failed("Second error")

        assert result is False
        assert fsm.is_failed()


class TestStateSummaryForTerminalStates:
    """Test get_state_summary for terminal states."""

    def test_state_summary_completed(self):
        """Test state summary in COMPLETED state."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.INFERENCE)
        fsm.mark_completed()

        summary = fsm.get_state_summary()

        assert summary["status"] == "COMPLETED"
        assert summary["phase"] == "INFERENCE"
        assert summary["paused_phase"] is None
        assert summary["has_candidate_state"] is False

    def test_state_summary_failed(self):
        """Test state summary in FAILED state."""
        fsm = TrainingStateMachine()

        fsm.handle_command(Command.START)
        fsm.set_phase(TrainingPhase.CANDIDATE)
        fsm.save_candidate_state({"epoch": 10})
        fsm.mark_failed("Out of memory")

        summary = fsm.get_state_summary()

        assert summary["status"] == "FAILED"
        assert summary["phase"] == "CANDIDATE"
        assert summary["paused_phase"] is None
        # Candidate state is cleared on mark_failed
        assert summary["has_candidate_state"] is False
