"""
Unit Tests for TrainingMonitor - 95% Coverage Target

Tests for missing coverage lines:
- Lines 90->96, 94->96: CandidatePool.update_pool branch coverage for status/start_time logic
- Lines 327, 331->325: TrainingState.update_state branch for mangled_name lookup
- Lines 612-625: TrainingMonitor.apply_params method

Author: Amp
Date: 2025-01-29
"""

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.data_adapter import TrainingMetrics
from backend.training_monitor import CandidatePool, TrainingMonitor, TrainingState


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
class TestCandidatePoolUpdatePoolBranches:
    """Test CandidatePool.update_pool branch coverage for status/start_time logic."""

    def test_update_pool_status_active_initializes_start_time(self):
        """Test status='Active' initializes start_time when None (line 90->92->93)."""
        pool = CandidatePool()

        # Verify start_time is None initially
        state = pool.get_state()
        assert state["elapsed_time"] == 0.0

        # Set status to Active - should initialize start_time
        pool.update_pool(status="Active")

        state = pool.get_state()
        assert state["status"] == "Active"
        # elapsed_time should now be non-zero (start_time was set)
        # Allow for some time to pass
        time.sleep(0.01)
        state = pool.get_state()
        assert state["elapsed_time"] > 0.0

    def test_update_pool_status_active_preserves_existing_start_time(self):
        """Test status='Active' when start_time already set (line 92 false branch)."""
        pool = CandidatePool()

        # First activation - sets start_time
        pool.update_pool(status="Active")
        time.sleep(0.05)
        first_state = pool.get_state()
        first_elapsed = first_state["elapsed_time"]

        # Second activation - should NOT reset start_time
        time.sleep(0.05)
        pool.update_pool(status="Active")
        second_state = pool.get_state()
        second_elapsed = second_state["elapsed_time"]

        # Second elapsed should be greater (start_time preserved)
        assert second_elapsed > first_elapsed

    def test_update_pool_status_inactive_resets_start_time(self):
        """Test status='Inactive' resets start_time to None (line 94->95)."""
        pool = CandidatePool()

        # Activate first
        pool.update_pool(status="Active")
        time.sleep(0.01)
        active_state = pool.get_state()
        assert active_state["elapsed_time"] > 0.0

        # Deactivate - should reset start_time
        pool.update_pool(status="Inactive")
        inactive_state = pool.get_state()
        assert inactive_state["status"] == "Inactive"
        assert inactive_state["elapsed_time"] == 0.0

    def test_update_pool_status_inactive_when_already_inactive(self):
        """Test status='Inactive' when already inactive (line 94->95)."""
        pool = CandidatePool()

        # Should be inactive by default
        state = pool.get_state()
        assert state["status"] == "Inactive"
        assert state["elapsed_time"] == 0.0

        # Setting inactive again should be safe
        pool.update_pool(status="Inactive")
        state = pool.get_state()
        assert state["status"] == "Inactive"
        assert state["elapsed_time"] == 0.0

    def test_update_pool_phase_only(self):
        """Test update_pool with phase only (line 96->97)."""
        pool = CandidatePool()

        pool.update_pool(phase="Training")
        state = pool.get_state()
        assert state["phase"] == "Training"
        assert state["status"] == "Inactive"  # unchanged

    def test_update_pool_size_only(self):
        """Test update_pool with size only (line 98->99)."""
        pool = CandidatePool()

        pool.update_pool(size=5)
        state = pool.get_state()
        assert state["size"] == 5

    def test_update_pool_iterations_only(self):
        """Test update_pool with iterations only (line 100->101)."""
        pool = CandidatePool()

        pool.update_pool(iterations=42)
        state = pool.get_state()
        assert state["iterations"] == 42

    def test_update_pool_progress_only(self):
        """Test update_pool with progress only (line 102->103)."""
        pool = CandidatePool()

        pool.update_pool(progress=0.75)
        state = pool.get_state()
        assert state["progress"] == 0.75

    def test_update_pool_target_only(self):
        """Test update_pool with target only (line 104->105)."""
        pool = CandidatePool()

        pool.update_pool(target=0.95)
        state = pool.get_state()
        assert state["target"] == 0.95

    def test_update_pool_all_parameters(self):
        """Test update_pool with all parameters at once."""
        pool = CandidatePool()

        pool.update_pool(
            status="Active",
            phase="Evaluating",
            size=10,
            iterations=100,
            progress=0.5,
            target=0.99,
        )

        state = pool.get_state()
        assert state["status"] == "Active"
        assert state["phase"] == "Evaluating"
        assert state["size"] == 10
        assert state["iterations"] == 100
        assert state["progress"] == 0.5
        assert state["target"] == 0.99
        assert state["elapsed_time"] > 0.0  # start_time was set

    def test_update_pool_status_transitions(self):
        """Test multiple status transitions Active -> Inactive -> Active."""
        pool = CandidatePool()

        # Inactive -> Active
        pool.update_pool(status="Active")
        time.sleep(0.01)
        state = pool.get_state()
        assert state["status"] == "Active"
        first_elapsed = state["elapsed_time"]
        assert first_elapsed > 0.0

        # Active -> Inactive
        pool.update_pool(status="Inactive")
        state = pool.get_state()
        assert state["status"] == "Inactive"
        assert state["elapsed_time"] == 0.0

        # Inactive -> Active again
        pool.update_pool(status="Active")
        time.sleep(0.01)
        state = pool.get_state()
        assert state["status"] == "Active"
        assert state["elapsed_time"] > 0.0

    def test_update_pool_none_values_ignored(self):
        """Test update_pool ignores None values."""
        pool = CandidatePool()

        pool.update_pool(status="Active", phase="Training", size=5)
        pool.get_state()

        # Update with None - should not change values
        pool.update_pool(status=None, phase=None, size=None)
        state_after = pool.get_state()

        assert state_after["status"] == "Active"
        assert state_after["phase"] == "Training"
        assert state_after["size"] == 5


@pytest.mark.unit
class TestTrainingStateUpdateStateBranches:
    """Test TrainingState.update_state branch coverage for mangled_name lookup."""

    def test_update_state_with_valid_field(self):
        """Test update_state with valid state field (line 327, 331->332)."""
        state = TrainingState()

        state.update_state(status="Running")
        result = state.get_state()
        assert result["status"] == "Running"

    def test_update_state_with_unknown_field_ignored(self):
        """Test update_state ignores unknown field (line 326 false branch)."""
        state = TrainingState()

        initial_state = state.get_state()
        state.update_state(unknown_field="value")
        after_state = state.get_state()

        # State should be unchanged (except timestamp if other fields were updated)
        assert initial_state["status"] == after_state["status"]
        assert initial_state["phase"] == after_state["phase"]

    def test_update_state_with_none_value_ignored(self):
        """Test update_state ignores None values (line 326)."""
        state = TrainingState()

        state.update_state(status="Running")
        state.update_state(status=None)

        result = state.get_state()
        assert result["status"] == "Running"  # unchanged

    def test_update_state_multiple_fields(self):
        """Test update_state with multiple valid fields."""
        state = TrainingState()

        state.update_state(
            status="Training",
            phase="Output",
            learning_rate=0.01,
            max_hidden_units=10,
            current_epoch=5,
        )

        result = state.get_state()
        assert result["status"] == "Training"
        assert result["phase"] == "Output"
        assert result["learning_rate"] == 0.01
        assert result["max_hidden_units"] == 10
        assert result["current_epoch"] == 5

    def test_update_state_updates_timestamp_automatically(self):
        """Test update_state updates timestamp when fields change (line 335->336)."""
        state = TrainingState()

        initial_timestamp = state.get_state()["timestamp"]
        time.sleep(0.01)

        state.update_state(status="Running")

        new_timestamp = state.get_state()["timestamp"]
        assert new_timestamp > initial_timestamp

    def test_update_state_preserves_timestamp_when_provided(self):
        """Test update_state uses provided timestamp (line 335 false branch)."""
        state = TrainingState()

        custom_timestamp = 1234567890.0
        state.update_state(status="Running", timestamp=custom_timestamp)

        result = state.get_state()
        assert result["timestamp"] == custom_timestamp

    def test_update_state_no_update_when_no_valid_fields(self):
        """Test update_state doesn't update timestamp when no fields changed."""
        state = TrainingState()

        initial_timestamp = state.get_state()["timestamp"]
        time.sleep(0.01)

        # Only unknown/None fields - no actual update
        state.update_state(unknown_field="value", another_unknown=123)

        # Timestamp should not change (updated flag is False)
        new_timestamp = state.get_state()["timestamp"]
        assert new_timestamp == initial_timestamp

    def test_update_state_all_state_fields(self):
        """Test update_state with all valid state fields."""
        state = TrainingState()

        state.update_state(
            status="Training",
            phase="Candidate",
            learning_rate=0.025,
            max_hidden_units=15,
            max_epochs=500,
            current_epoch=42,
            current_step=1000,
            network_name="TestNetwork",
            dataset_name="TestDataset",
            threshold_function="sigmoid",
            optimizer_name="Adam",
            candidate_pool_status="Active",
            candidate_pool_phase="Training",
            candidate_pool_size=8,
            top_candidate_id="cand_1",
            top_candidate_score=0.95,
            second_candidate_id="cand_2",
            second_candidate_score=0.92,
            pool_metrics={"avg_loss": 0.1},
        )

        result = state.get_state()
        assert result["status"] == "Training"
        assert result["phase"] == "Candidate"
        assert result["learning_rate"] == 0.025
        assert result["max_hidden_units"] == 15
        assert result["max_epochs"] == 500
        assert result["current_epoch"] == 42
        assert result["current_step"] == 1000
        assert result["network_name"] == "TestNetwork"
        assert result["dataset_name"] == "TestDataset"
        assert result["threshold_function"] == "sigmoid"
        assert result["optimizer_name"] == "Adam"
        assert result["candidate_pool_status"] == "Active"
        assert result["candidate_pool_phase"] == "Training"
        assert result["candidate_pool_size"] == 8
        assert result["top_candidate_id"] == "cand_1"
        assert result["top_candidate_score"] == 0.95
        assert result["second_candidate_id"] == "cand_2"
        assert result["second_candidate_score"] == 0.92
        assert result["pool_metrics"] == {"avg_loss": 0.1}

    def test_update_state_mixed_valid_and_invalid_fields(self):
        """Test update_state handles mix of valid and invalid fields."""
        state = TrainingState()

        state.update_state(
            status="Running",
            invalid_field="ignored",
            phase="Output",
            another_invalid=None,
        )

        result = state.get_state()
        assert result["status"] == "Running"
        assert result["phase"] == "Output"

    def test_update_state_thread_safety(self):
        """Test update_state is thread-safe."""
        state = TrainingState()
        errors = []

        def update_status(prefix, count):
            try:
                for i in range(count):
                    state.update_state(status=f"{prefix}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=update_status, args=(f"thread_{t}", 50)) for t in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # State should be valid (last update wins)
        result = state.get_state()
        assert result["status"] is not None


@pytest.mark.unit
class TestTrainingMonitorApplyParams:
    """Test TrainingMonitor.apply_params method (lines 612-625)."""

    def test_apply_params_learning_rate_only(self):
        """Test apply_params with learning_rate only (lines 615-618)."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        result = monitor.apply_params(learning_rate=0.05)

        assert result == {"learning_rate": 0.05}

    def test_apply_params_max_hidden_units_only(self):
        """Test apply_params with max_hidden_units only (lines 620-623)."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        result = monitor.apply_params(max_hidden_units=20)

        assert result == {"max_hidden_units": 20}

    def test_apply_params_both_parameters(self):
        """Test apply_params with both parameters (lines 615-623)."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        result = monitor.apply_params(learning_rate=0.025, max_hidden_units=15)

        assert result == {"learning_rate": 0.025, "max_hidden_units": 15}

    def test_apply_params_no_parameters(self):
        """Test apply_params with no parameters returns empty dict."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        result = monitor.apply_params()

        assert result == {}

    def test_apply_params_none_values_ignored(self):
        """Test apply_params ignores None values."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        result = monitor.apply_params(learning_rate=None, max_hidden_units=None)

        assert result == {}

    def test_apply_params_mixed_none_and_valid(self):
        """Test apply_params with mix of None and valid values."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        result = monitor.apply_params(learning_rate=0.01, max_hidden_units=None)

        assert result == {"learning_rate": 0.01}

    def test_apply_params_logs_applied_values(self):
        """Test apply_params logs the applied parameter values."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)
        monitor.logger = MagicMock()

        monitor.apply_params(learning_rate=0.02, max_hidden_units=25)

        # Verify logging calls
        monitor.logger.info.assert_any_call("Applied learning_rate: 0.02")
        monitor.logger.info.assert_any_call("Applied max_hidden_units: 25")

    def test_apply_params_thread_safety(self):
        """Test apply_params is thread-safe."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)
        results = []
        errors = []

        def apply_params(lr, units):
            try:
                result = monitor.apply_params(learning_rate=lr, max_hidden_units=units)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=apply_params, args=(0.01 * i, i)) for i in range(1, 6)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 5

    def test_apply_params_boundary_values(self):
        """Test apply_params with boundary values."""
        adapter = FakeDataAdapter()
        monitor = TrainingMonitor(adapter)

        # Very small learning rate
        result = monitor.apply_params(learning_rate=0.0001)
        assert result == {"learning_rate": 0.0001}

        # Very large learning rate
        result = monitor.apply_params(learning_rate=1.0)
        assert result == {"learning_rate": 1.0}

        # Zero hidden units
        result = monitor.apply_params(max_hidden_units=0)
        assert result == {"max_hidden_units": 0}

        # Large hidden units
        result = monitor.apply_params(max_hidden_units=1000)
        assert result == {"max_hidden_units": 1000}


@pytest.mark.unit
class TestCandidatePoolAdditionalCoverage:
    """Additional tests for CandidatePool to ensure complete coverage."""

    def test_add_candidate_update_existing(self):
        """Test add_candidate updates existing candidate."""
        pool = CandidatePool()

        pool.add_candidate("cand_1", "Candidate 1", correlation=0.5)
        pool.add_candidate("cand_1", "Candidate 1 Updated", correlation=0.9)

        top = pool.get_top_n_candidates(1)
        assert len(top) == 1
        assert top[0]["name"] == "Candidate 1 Updated"
        assert top[0]["correlation"] == 0.9

    def test_get_top_n_candidates_empty_pool(self):
        """Test get_top_n_candidates with empty pool."""
        pool = CandidatePool()

        top = pool.get_top_n_candidates(5)
        assert top == []

    def test_get_pool_metrics_empty_pool(self):
        """Test get_pool_metrics with empty pool returns zeros."""
        pool = CandidatePool()

        metrics = pool.get_pool_metrics()
        assert metrics["avg_loss"] == 0.0
        assert metrics["avg_accuracy"] == 0.0
        assert metrics["avg_precision"] == 0.0
        assert metrics["avg_recall"] == 0.0
        assert metrics["avg_f1_score"] == 0.0

    def test_get_pool_metrics_with_candidates(self):
        """Test get_pool_metrics calculates correct averages."""
        pool = CandidatePool()

        pool.add_candidate("c1", "C1", loss=0.1, accuracy=0.9, precision=0.85, recall=0.8, f1_score=0.82)
        pool.add_candidate("c2", "C2", loss=0.2, accuracy=0.8, precision=0.75, recall=0.7, f1_score=0.72)

        metrics = pool.get_pool_metrics()
        assert abs(metrics["avg_loss"] - 0.15) < 1e-9
        assert abs(metrics["avg_accuracy"] - 0.85) < 1e-9
        assert abs(metrics["avg_precision"] - 0.80) < 1e-9
        assert abs(metrics["avg_recall"] - 0.75) < 1e-9
        assert abs(metrics["avg_f1_score"] - 0.77) < 1e-9

    def test_clear_resets_all_state(self):
        """Test clear resets all pool state."""
        pool = CandidatePool()

        pool.update_pool(status="Active", phase="Training", size=5, iterations=100, progress=0.5, target=0.9)
        pool.add_candidate("c1", "C1", correlation=0.9)

        pool.clear()

        state = pool.get_state()
        assert state["status"] == "Inactive"
        assert state["size"] == 0
        assert state["iterations"] == 0
        assert state["progress"] == 0.0
        assert state["elapsed_time"] == 0.0
        assert pool.get_top_n_candidates(10) == []


@pytest.mark.unit
class TestTrainingStateAdditionalCoverage:
    """Additional tests for TrainingState to ensure complete coverage."""

    def test_to_json_returns_valid_json(self):
        """Test to_json returns valid JSON string."""
        import json

        state = TrainingState()
        state.update_state(status="Running", phase="Output")

        json_str = state.to_json()
        parsed = json.loads(json_str)

        assert parsed["status"] == "Running"
        assert parsed["phase"] == "Output"

    def test_get_state_returns_all_fields(self):
        """Test get_state returns all expected fields."""
        state = TrainingState()

        result = state.get_state()

        expected_fields = {
            "status",
            "phase",
            "learning_rate",
            "max_hidden_units",
            "max_epochs",
            "current_epoch",
            "current_step",
            "network_name",
            "dataset_name",
            "threshold_function",
            "optimizer_name",
            "timestamp",
            "candidate_pool_status",
            "candidate_pool_phase",
            "candidate_pool_size",
            "top_candidate_id",
            "top_candidate_score",
            "second_candidate_id",
            "second_candidate_score",
            "pool_metrics",
        }

        assert set(result.keys()) == expected_fields
