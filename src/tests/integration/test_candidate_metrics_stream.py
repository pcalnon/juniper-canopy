#!/usr/bin/env python
"""
Integration tests for candidate metrics streaming via WebSocket.

Tests that candidate pool data is correctly:
- Streamed via WebSocket state messages
- Updated during candidate phase
- Stabilized when pool inactive
"""

import time

import pytest

from backend.training_monitor import CandidatePool, TrainingState


class TestCandidateMetricsStream:
    """Test candidate metrics streaming via WebSocket."""

    def test_training_state_includes_candidate_data(self):
        """Test that TrainingState serializes candidate data."""
        state = TrainingState()
        state.update_state(
            candidate_pool_status="Active",
            candidate_pool_phase="Training",
            candidate_pool_size=8,
            top_candidate_id="cand_5",
            top_candidate_score=0.92,
            second_candidate_id="cand_2",
            second_candidate_score=0.88,
            pool_metrics={
                "avg_loss": 0.22,
                "avg_accuracy": 0.85,
                "avg_precision": 0.83,
                "avg_recall": 0.87,
                "avg_f1_score": 0.85,
            },
        )

        state_dict = state.get_state()

        assert state_dict["candidate_pool_status"] == "Active"
        assert state_dict["candidate_pool_phase"] == "Training"
        assert state_dict["candidate_pool_size"] == 8
        assert state_dict["top_candidate_id"] == "cand_5"
        assert state_dict["top_candidate_score"] == 0.92
        assert state_dict["second_candidate_id"] == "cand_2"
        assert state_dict["second_candidate_score"] == 0.88
        assert state_dict["pool_metrics"]["avg_loss"] == 0.22

    def test_state_serialization_to_json(self):
        """Test that candidate data serializes to JSON correctly."""
        import json

        state = TrainingState()
        state.update_state(
            candidate_pool_status="Active",
            top_candidate_id="cand_1",
            top_candidate_score=0.95,
            pool_metrics={"avg_loss": 0.15},
        )

        json_str = state.to_json()
        parsed = json.loads(json_str)

        assert parsed["candidate_pool_status"] == "Active"
        assert parsed["top_candidate_id"] == "cand_1"
        assert parsed["top_candidate_score"] == 0.95
        assert parsed["pool_metrics"]["avg_loss"] == 0.15


class TestCandidatePhaseUpdates:
    """Test values update during candidate phase."""

    def test_candidate_pool_integration_with_state(self):
        """Test CandidatePool integrates with TrainingState."""
        pool = CandidatePool()
        state = TrainingState()

        # Activate pool and add candidates
        pool.update_pool(status="Active", phase="Training", size=3)
        pool.add_candidate("cand_1", "C1", correlation=0.85, loss=0.20, accuracy=0.88)
        pool.add_candidate("cand_2", "C2", correlation=0.92, loss=0.15, accuracy=0.93)
        pool.add_candidate("cand_3", "C3", correlation=0.78, loss=0.25, accuracy=0.82)

        # Get top candidates and metrics
        top_candidates = pool.get_top_n_candidates(n=2)
        pool_metrics = pool.get_pool_metrics()
        pool_state = pool.get_state()

        # Update TrainingState
        state.update_state(
            phase="CANDIDATE",
            candidate_pool_status=pool_state["status"],
            candidate_pool_phase=pool_state["phase"],
            candidate_pool_size=pool_state["size"],
            top_candidate_id=top_candidates[0]["id"] if len(top_candidates) > 0 else "",
            top_candidate_score=top_candidates[0]["correlation"] if len(top_candidates) > 0 else 0.0,
            second_candidate_id=top_candidates[1]["id"] if len(top_candidates) > 1 else "",
            second_candidate_score=top_candidates[1]["correlation"] if len(top_candidates) > 1 else 0.0,
            pool_metrics=pool_metrics,
        )

        state_dict = state.get_state()

        assert state_dict["phase"] == "CANDIDATE"
        assert state_dict["candidate_pool_status"] == "Active"
        assert state_dict["candidate_pool_size"] == 3
        assert state_dict["top_candidate_id"] == "cand_2"  # Highest correlation
        assert state_dict["top_candidate_score"] == 0.92
        assert state_dict["second_candidate_id"] == "cand_1"
        assert state_dict["second_candidate_score"] == 0.85
        assert "avg_loss" in state_dict["pool_metrics"]

    def test_pool_metrics_update_dynamically(self):
        """Test that pool metrics update as candidates are added/updated."""
        pool = CandidatePool()

        # Initial state - no candidates
        metrics_1 = pool.get_pool_metrics()
        assert metrics_1["avg_loss"] == 0.0

        # Add first candidate
        pool.add_candidate("cand_1", "C1", loss=0.3, accuracy=0.7)
        metrics_2 = pool.get_pool_metrics()
        assert metrics_2["avg_loss"] == 0.3
        assert metrics_2["avg_accuracy"] == 0.7

        # Add second candidate - metrics should average
        pool.add_candidate("cand_2", "C2", loss=0.5, accuracy=0.5)
        metrics_3 = pool.get_pool_metrics()
        assert metrics_3["avg_loss"] == pytest.approx(0.4)
        assert metrics_3["avg_accuracy"] == pytest.approx(0.6)


class TestInactivePoolStability:
    """Test values stable when pool inactive."""

    def test_inactive_pool_returns_empty_values(self):
        """Test that inactive pool has stable empty values."""
        state = TrainingState()
        # Default initialization should have inactive pool
        state_dict = state.get_state()

        assert state_dict["candidate_pool_status"] == "Inactive"
        assert state_dict["candidate_pool_phase"] == "Idle"
        assert state_dict["candidate_pool_size"] == 0
        assert state_dict["top_candidate_id"] == ""
        assert state_dict["top_candidate_score"] == 0.0
        assert state_dict["second_candidate_id"] == ""
        assert state_dict["second_candidate_score"] == 0.0
        assert state_dict["pool_metrics"] == {}

    def test_pool_clear_resets_to_inactive(self):
        """Test that clearing pool returns to inactive state."""
        pool = CandidatePool()

        # Activate and populate
        pool.update_pool(status="Active", phase="Training", size=5)
        pool.add_candidate("cand_1", "C1", correlation=0.85)

        # Clear pool
        pool.clear()

        state = pool.get_state()
        assert state["status"] == "Inactive"
        assert state["size"] == 0

        top_candidates = pool.get_top_n_candidates(n=2)
        assert len(top_candidates) == 0

        metrics = pool.get_pool_metrics()
        assert metrics["avg_loss"] == 0.0

    def test_transition_from_active_to_inactive(self):
        """Test smooth transition from active to inactive pool."""
        pool = CandidatePool()
        state = TrainingState()

        # Start active
        pool.update_pool(status="Active", phase="Evaluating", size=3)
        pool.add_candidate("cand_1", "C1", correlation=0.90)

        top_before = pool.get_top_n_candidates(n=2)
        assert len(top_before) > 0

        # Transition to inactive
        pool.update_pool(status="Inactive")
        pool.clear()

        pool_state = pool.get_state()
        assert pool_state["status"] == "Inactive"

        top_after = pool.get_top_n_candidates(n=2)
        assert len(top_after) == 0

        # Update TrainingState to reflect inactive pool
        state.update_state(
            phase="OUTPUT",
            candidate_pool_status="Inactive",
            candidate_pool_size=0,
            top_candidate_id="",
            top_candidate_score=0.0,
            pool_metrics={},
        )

        state_dict = state.get_state()
        assert state_dict["candidate_pool_status"] == "Inactive"
        assert state_dict["top_candidate_id"] == ""


class TestWebSocketBroadcastIntegration:
    """Test WebSocket broadcast integration (if available)."""

    def test_state_message_format(self):
        """Test that state messages have correct format for WebSocket."""
        state = TrainingState()
        state.update_state(
            status="Training",
            phase="CANDIDATE",
            current_epoch=25,
            candidate_pool_status="Active",
            candidate_pool_phase="Training",
            candidate_pool_size=8,
            top_candidate_id="cand_3",
            top_candidate_score=0.94,
        )

        # Get state dict (this is what gets broadcast)
        state_dict = state.get_state()

        # Verify all required fields present
        required_fields = [
            "status",
            "phase",
            "current_epoch",
            "candidate_pool_status",
            "candidate_pool_phase",
            "candidate_pool_size",
            "top_candidate_id",
            "top_candidate_score",
            "second_candidate_id",
            "second_candidate_score",
            "pool_metrics",
        ]

        for field in required_fields:
            assert field in state_dict, f"Missing field: {field}"


class TestEdgeCases:
    """Test edge cases in candidate tracking."""

    def test_zero_candidates_requested(self):
        """Test requesting zero candidates."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "C1", correlation=0.85)

        top_candidates = pool.get_top_n_candidates(n=0)
        assert len(top_candidates) == 0

    def test_negative_n_candidates(self):
        """Test requesting negative number of candidates."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "C1", correlation=0.85)

        # Negative slice should return empty list
        top_candidates = pool.get_top_n_candidates(n=-1)
        assert len(top_candidates) == 0

    def test_candidates_with_same_correlation(self):
        """Test handling candidates with identical correlation scores."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "C1", correlation=0.85)
        pool.add_candidate("cand_2", "C2", correlation=0.85)
        pool.add_candidate("cand_3", "C3", correlation=0.85)

        top_candidates = pool.get_top_n_candidates(n=2)
        assert len(top_candidates) == 2
        # Both should have same correlation
        assert top_candidates[0]["correlation"] == 0.85
        assert top_candidates[1]["correlation"] == 0.85

    def test_pool_progress_tracking(self):
        """Test progress and target tracking in pool state."""
        pool = CandidatePool()
        pool.update_pool(status="Active", phase="Training", iterations=50, progress=0.75, target=0.90)

        state = pool.get_state()
        assert state["iterations"] == 50
        assert state["progress"] == 0.75
        assert state["target"] == 0.90

    def test_elapsed_time_tracking(self):
        """Test that elapsed time is tracked when pool is active."""
        pool = CandidatePool()

        # Initially no time should have elapsed
        state_1 = pool.get_state()
        assert state_1["elapsed_time"] == 0.0

        # Activate pool
        pool.update_pool(status="Active")
        time.sleep(0.1)  # Small delay

        state_2 = pool.get_state()
        assert state_2["elapsed_time"] > 0.0

        # Deactivate pool should reset timer
        pool.update_pool(status="Inactive")
        state_3 = pool.get_state()
        assert state_3["elapsed_time"] == 0.0
