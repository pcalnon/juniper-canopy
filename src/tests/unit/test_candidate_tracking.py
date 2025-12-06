#!/usr/bin/env python
"""
Unit tests for candidate pool tracking functionality.

Tests CandidatePool class methods for tracking, sorting, and aggregating
candidate unit metrics during cascade correlation training.
"""
import pytest

from backend.training_monitor import CandidatePool


class TestCandidatePoolBasics:
    """Test basic candidate pool operations."""

    def test_pool_initialization(self):
        """Test candidate pool initializes with correct defaults."""
        pool = CandidatePool()
        state = pool.get_state()

        assert state["status"] == "Inactive"
        assert state["phase"] == "Idle"
        assert state["size"] == 0
        assert state["iterations"] == 0
        assert state["progress"] == 0.0
        assert state["target"] == 0.0

    def test_update_pool_status(self):
        """Test updating pool status."""
        pool = CandidatePool()
        pool.update_pool(status="Active", phase="Training", size=8)
        state = pool.get_state()

        assert state["status"] == "Active"
        assert state["phase"] == "Training"
        assert state["size"] == 8

    def test_add_candidate(self):
        """Test adding a candidate to pool."""
        pool = CandidatePool()
        pool.add_candidate(candidate_id="cand_1", name="Candidate_1", correlation=0.85, loss=0.25, accuracy=0.90)

        top_candidates = pool.get_top_n_candidates(n=1)
        assert len(top_candidates) == 1
        assert top_candidates[0]["id"] == "cand_1"
        assert top_candidates[0]["correlation"] == 0.85


class TestGetTopNCandidates:
    """Test get_top_n_candidates logic."""

    def test_top_n_with_empty_pool(self):
        """Test getting top N from empty pool."""
        pool = CandidatePool()
        top_candidates = pool.get_top_n_candidates(n=2)

        assert top_candidates == []

    def test_top_n_with_single_candidate(self):
        """Test getting top N with only one candidate."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "Candidate_1", correlation=0.75)

        top_candidates = pool.get_top_n_candidates(n=2)
        assert len(top_candidates) == 1
        assert top_candidates[0]["id"] == "cand_1"

    def test_top_n_sorts_by_correlation(self):
        """Test that candidates are sorted by correlation score."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "Candidate_1", correlation=0.60)
        pool.add_candidate("cand_2", "Candidate_2", correlation=0.85)
        pool.add_candidate("cand_3", "Candidate_3", correlation=0.75)

        top_candidates = pool.get_top_n_candidates(n=2)
        assert len(top_candidates) == 2
        assert top_candidates[0]["id"] == "cand_2"  # Highest correlation
        assert top_candidates[0]["correlation"] == 0.85
        assert top_candidates[1]["id"] == "cand_3"  # Second highest
        assert top_candidates[1]["correlation"] == 0.75

    def test_top_n_returns_exactly_n_candidates(self):
        """Test that exactly N candidates are returned when available."""
        pool = CandidatePool()
        for i in range(10):
            pool.add_candidate(f"cand_{i}", f"Candidate_{i}", correlation=0.5 + i * 0.05)

        top_3 = pool.get_top_n_candidates(n=3)
        assert len(top_3) == 3

        top_5 = pool.get_top_n_candidates(n=5)
        assert len(top_5) == 5


class TestPoolMetrics:
    """Test pool aggregation functions."""

    def test_pool_metrics_with_empty_pool(self):
        """Test metrics calculation with empty pool."""
        pool = CandidatePool()
        metrics = pool.get_pool_metrics()

        assert metrics["avg_loss"] == 0.0
        assert metrics["avg_accuracy"] == 0.0
        assert metrics["avg_precision"] == 0.0
        assert metrics["avg_recall"] == 0.0
        assert metrics["avg_f1_score"] == 0.0

    def test_pool_metrics_single_candidate(self):
        """Test metrics with single candidate."""
        pool = CandidatePool()
        pool.add_candidate(
            "cand_1",
            "Candidate_1",
            correlation=0.80,
            loss=0.25,
            accuracy=0.85,
            precision=0.82,
            recall=0.88,
            f1_score=0.85,
        )

        metrics = pool.get_pool_metrics()
        assert metrics["avg_loss"] == 0.25
        assert metrics["avg_accuracy"] == 0.85
        assert metrics["avg_precision"] == 0.82
        assert metrics["avg_recall"] == 0.88
        assert metrics["avg_f1_score"] == 0.85

    def test_pool_metrics_multiple_candidates(self):
        """Test average metrics calculation across multiple candidates."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "C1", loss=0.2, accuracy=0.8, precision=0.75, recall=0.85, f1_score=0.80)
        pool.add_candidate("cand_2", "C2", loss=0.4, accuracy=0.6, precision=0.65, recall=0.75, f1_score=0.70)

        metrics = pool.get_pool_metrics()
        assert metrics["avg_loss"] == pytest.approx(0.3)
        assert metrics["avg_accuracy"] == pytest.approx(0.7)
        assert metrics["avg_precision"] == pytest.approx(0.7)
        assert metrics["avg_recall"] == pytest.approx(0.8)
        assert metrics["avg_f1_score"] == pytest.approx(0.75)


class TestCandidateUpdate:
    """Test updating existing candidates."""

    def test_update_existing_candidate(self):
        """Test that adding same candidate ID updates rather than duplicates."""
        pool = CandidatePool()
        pool.add_candidate("cand_1", "Candidate_1", correlation=0.70, loss=0.5)
        pool.add_candidate("cand_1", "Candidate_1", correlation=0.85, loss=0.3)

        top_candidates = pool.get_top_n_candidates(n=10)
        assert len(top_candidates) == 1  # No duplicate
        assert top_candidates[0]["correlation"] == 0.85  # Updated value
        assert top_candidates[0]["loss"] == 0.3


class TestPoolClear:
    """Test clearing pool state."""

    def test_clear_removes_all_candidates(self):
        """Test that clear() removes all candidates."""
        pool = CandidatePool()
        for i in range(5):
            pool.add_candidate(f"cand_{i}", f"C{i}", correlation=0.5 + i * 0.1)

        pool.update_pool(status="Active", size=5, iterations=100)
        pool.clear()

        state = pool.get_state()
        assert state["status"] == "Inactive"
        assert state["size"] == 0
        assert state["iterations"] == 0

        top_candidates = pool.get_top_n_candidates(n=10)
        assert len(top_candidates) == 0


class TestThreadSafety:
    """Test thread safety of CandidatePool."""

    def test_concurrent_access(self):
        """Test thread-safe concurrent access to pool."""
        import threading

        pool = CandidatePool()
        errors = []

        def add_candidates():
            try:
                for i in range(10):
                    pool.add_candidate(f"cand_{i}", f"C{i}", correlation=0.5)
            except Exception as e:
                errors.append(e)

        def read_candidates():
            try:
                for _ in range(20):
                    pool.get_top_n_candidates(n=5)
                    pool.get_pool_metrics()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=add_candidates),
            threading.Thread(target=read_candidates),
            threading.Thread(target=read_candidates),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
