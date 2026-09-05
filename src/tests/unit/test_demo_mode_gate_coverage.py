#!/usr/bin/env python
"""Per-file coverage-gate tests for ``demo_mode.py`` (part 1 of 2).

These tests raise statement coverage of ``src/demo_mode.py`` toward the
per-file gate threshold by exercising branches the existing demo_mode suite
does not reach:

* ``MockCascorNetwork`` early-return guards (empty pool / below-threshold
  correlation / no-training-data candidate path).
* ``DemoMode`` simulation helpers (``_simulate_training_step`` no-data
  fallback, ``_simulate_candidate_pool`` populated path,
  ``_update_candidate_pool_state`` candidate branches).
* JuniperData generation error/metadata paths.
* ``apply_params`` prefixed-parameter mapping and the generic nn_/cn_ store loop.
* Guard branches in ``pause`` / ``regenerate_dataset`` / ``import_dataset`` /
  ``regenerate_dataset_from_generator`` and the ``_training_loop`` max-hidden
  stopping criterion (driven synchronously).

Every test asserts observable behaviour — no bare-line execution.
Companion file: ``test_demo_mode_gate_coverage_datasets.py``.
"""

from unittest.mock import patch

import numpy as np
import pytest
import torch

from backend.training_state_machine import Command, TrainingPhase
from canopy_constants import TrainingConstants
from demo_mode import DemoMode, MockCascorNetwork

pytestmark = pytest.mark.unit


def _valid_npz(n: int = 12) -> dict:
    """Return a minimal valid 2-D classification NPZ dict, partitioned train / val / test.

    It returned only ``X_full`` / ``y_full`` until decision 11 removed that family from
    the contract. Partitioning it here is not cosmetic: a fixture that still shipped the
    old shape would keep exercising the tolerance path and never the one every new
    artifact takes.
    """
    rng = np.random.RandomState(0)
    X = rng.randn(n, 2).astype(np.float32)
    y = np.zeros((n, 2), dtype=np.float32)
    idx = np.arange(n)
    y[idx % 2 == 0, 0] = 1.0
    y[idx % 2 == 1, 1] = 1.0
    train_end = max(1, int(n * 0.8))
    val_end = max(train_end + 1, int(n * 0.9))
    return {
        "X_train": X[:train_end],
        "y_train": y[:train_end],
        "X_val": X[train_end:val_end],
        "y_val": y[train_end:val_end],
        "X_test": X[val_end:],
        "y_test": y[val_end:],
    }


# ---------------------------------------------------------------------------
# MockCascorNetwork early-return guards
# ---------------------------------------------------------------------------
class TestMockCascorNetworkGuards:
    def test_add_hidden_unit_empty_pool_returns_none(self):
        """pool_size=0 leaves best_unit unset -> add_hidden_unit returns None (line 241)."""
        net = MockCascorNetwork(input_size=2, output_size=1)
        before = len(net.hidden_units)

        result = net.add_hidden_unit(pool_size=0)

        assert result is None
        # Nothing installed when the pool was empty.
        assert len(net.hidden_units) == before

    def test_add_hidden_unit_below_threshold_returns_none(self):
        """A best correlation below MIN_CANDIDATE_CORRELATION is rejected (line 247)."""
        net = MockCascorNetwork(input_size=2, output_size=1)
        net.train_x = torch.randn(20, 2)
        net.train_y = torch.randint(0, 2, (20, 1)).float()

        # Force every trained candidate to look like noise-level correlation.
        net._train_candidate = lambda unit, steps=600, lr=0.01: 0.0

        assert 0.0 < TrainingConstants.MIN_CANDIDATE_CORRELATION  # guard premise
        result = net.add_hidden_unit(pool_size=3, candidate_steps=1)

        assert result is None
        assert len(net.hidden_units) == 0  # rejected candidate not installed

    def test_train_candidate_pool_no_training_data_break(self):
        """With no training data the pool loop takes the else/break path (lines 309-310)."""
        net = MockCascorNetwork(input_size=2, output_size=1)
        net.train_x = None
        net.train_y = None

        result = net.train_candidate_pool(pool_size=5)

        assert result is not None
        unit, correlation = result
        assert isinstance(unit, dict)
        assert unit["activation_fn"] is torch.tanh
        # No data means correlation stays at the sentinel -1.0.
        assert correlation == -1.0

    def test_train_candidate_pool_empty_pool_returns_none(self):
        """pool_size=0 -> best_unit stays None -> returns None (line 316)."""
        net = MockCascorNetwork(input_size=2, output_size=1)
        net.train_x = torch.randn(10, 2)
        net.train_y = torch.randint(0, 2, (10, 1)).float()

        assert net.train_candidate_pool(pool_size=0) is None


# ---------------------------------------------------------------------------
# DemoMode simulation helpers
# ---------------------------------------------------------------------------
class TestDemoSimulationHelpers:
    def test_simulate_training_step_no_data_fallback(self):
        """No training data -> the (1.0, 0.5) fallback branch (lines 1082-1083)."""
        demo = DemoMode()
        demo.network.train_x = None
        demo.network.train_y = None

        loss, accuracy = demo._simulate_training_step()

        assert loss == 1.0
        assert accuracy == 0.5
        assert demo.current_loss == 1.0
        assert demo.current_accuracy == 0.5

    def test_simulate_candidate_pool_populates_pool(self):
        """With a real candidate pool the synthetic-candidate loop runs (lines 1093-1121)."""
        demo = DemoMode()
        assert demo.candidate_pool is not None  # backend.training_monitor available

        demo._simulate_candidate_pool()

        state = demo.candidate_pool.get_state()
        assert state["status"] == "Active"
        assert state["size"] == TrainingConstants.CANDIDATE_POOL_SIZE
        top = demo.candidate_pool.get_top_n_candidates(n=TrainingConstants.CANDIDATE_POOL_SIZE)
        assert len(top) == TrainingConstants.CANDIDATE_POOL_SIZE
        # Synthetic correlations are drawn from U(0.4, 0.9).
        assert all(0.4 <= c["correlation"] <= 0.9 for c in top)

    def test_update_candidate_pool_state_top_two_candidates(self):
        """CANDIDATE phase + populated pool exposes top/second candidates (lines 716-720)."""
        demo = DemoMode()
        # Drive the FSM into a STARTED/CANDIDATE state (set_phase is a no-op unless STARTED).
        assert demo.state_machine.handle_command(Command.START) is True
        demo.state_machine.set_phase(TrainingPhase.CANDIDATE)
        assert demo.state_machine.get_state_summary()["phase"] == "CANDIDATE"

        demo.candidate_pool.add_candidate("cand_hi", "Hi", correlation=0.9)
        demo.candidate_pool.add_candidate("cand_lo", "Lo", correlation=0.3)

        demo._update_candidate_pool_state()

        snap = demo.training_state.get_state()
        assert snap["top_candidate_id"] == "cand_hi"
        assert snap["top_candidate_score"] == pytest.approx(0.9)
        assert snap["second_candidate_id"] == "cand_lo"
        assert snap["second_candidate_score"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# JuniperData generation: error mapping + metadata
# ---------------------------------------------------------------------------
class TestJuniperDataGenerationPaths:
    def test_generation_includes_algorithm_and_metadata(self, mock_juniper_data_client):
        """algorithm param + response meta populate the result (lines 933, 995, 997)."""
        demo = DemoMode()
        npz = _valid_npz(14)

        with patch.object(mock_juniper_data_client, "create_dataset", return_value={"dataset_id": "d-meta", "meta": {"dataset_name": "GateDS", "dataset_version": 9}}) as mock_create, patch.object(mock_juniper_data_client, "download_artifact_npz", return_value=npz):
            result = demo._generate_spiral_dataset_from_juniper_data(
                n_samples=14,
                juniper_data_url="http://localhost:8100",
                algorithm="test-algorithm",
                n_rotations=2.0,
            )

        # create_dataset must have received the algorithm param (line 933).
        _, kwargs = mock_create.call_args
        assert kwargs["params"]["algorithm"] == "test-algorithm"
        # Metadata copied out of response.meta (lines 995, 997).
        assert result["dataset_name"] == "GateDS"
        assert result["dataset_version"] == 9
        assert result["num_samples"] == 14

    def test_create_dataset_error_is_mapped_and_reraised(self, mock_juniper_data_client):
        """A create_dataset failure is user-mapped, logged, and re-raised (lines 944-947)."""
        from juniper_data_client.exceptions import JuniperDataClientError

        demo = DemoMode()
        with patch.object(mock_juniper_data_client, "create_dataset", side_effect=JuniperDataClientError("create boom")):
            with pytest.raises(JuniperDataClientError, match="create boom"):
                demo._generate_spiral_dataset_from_juniper_data(n_samples=10, juniper_data_url="http://localhost:8100")

    def test_download_error_is_mapped_and_reraised(self, mock_juniper_data_client):
        """A download failure after a successful create is mapped and re-raised (lines 958-961)."""
        from juniper_data_client.exceptions import JuniperDataClientError

        demo = DemoMode()
        with patch.object(mock_juniper_data_client, "download_artifact_npz", side_effect=JuniperDataClientError("download boom")):
            with pytest.raises(JuniperDataClientError, match="download boom"):
                demo._generate_spiral_dataset_from_juniper_data(n_samples=10, juniper_data_url="http://localhost:8100")


# ---------------------------------------------------------------------------
# apply_params: prefixed aliasing + generic store loop
# ---------------------------------------------------------------------------
class TestApplyParamsPrefixed:
    def test_nn_spiral_rotations_alias_pop(self, mock_juniper_data_client):
        """nn_spiral_rotations is folded into the positional spiral_rotations arg (line 2108)."""
        demo = DemoMode()
        # Default spiral_rotations is 1.5; pick a different, in-range value so the
        # aliasing path is unambiguous.
        assert demo.spiral_rotations != 3.0
        demo.apply_params(nn_spiral_rotations=3.0)

        assert demo.spiral_rotations == pytest.approx(3.0)
        assert demo.nn_spiral_rotations == pytest.approx(3.0)

    def test_generic_nn_cn_param_store_loop(self):
        """Unmapped nn_/cn_ params are cast and stored via the generic loop (lines 2207-2209)."""
        demo = DemoMode()
        result = demo.apply_params(nn_patience=7, cn_pool_size=16, cn_multi_candidate=True)

        assert demo.nn_patience == 7
        assert isinstance(demo.nn_patience, int)
        assert demo.cn_pool_size == 16
        assert demo.cn_multi_candidate is True
        # All keys are recognised demo params, so nothing is reported skipped.
        assert result["ok"] is True
        assert result["skipped"] == []


# ---------------------------------------------------------------------------
# Guard branches: pause / regenerate / import / generator
# ---------------------------------------------------------------------------
class TestGuardBranches:
    def test_pause_when_started_but_not_running(self):
        """FSM PAUSE succeeds but is_running False -> the not-running guard (lines 1588-1589)."""
        demo = DemoMode()
        # STARTED lets the PAUSE command succeed, but we never launched the thread,
        # so is_running stays False.
        assert demo.state_machine.handle_command(Command.START) is True
        assert demo.running is False

        demo.pause()

        # Guard returns before setting the pause event.
        assert demo._pause.is_set() is False

    def test_regenerate_dataset_stops_when_running(self, mock_juniper_data_client):
        """regenerate_dataset stops an active run before swapping (lines 1739-1740)."""
        demo = DemoMode()
        demo.state_machine.handle_command(Command.START)
        demo._set_running(True)
        assert demo.running is True

        new_ds = demo.regenerate_dataset(n_samples=20)

        assert demo.running is False  # stop() ran
        assert "inputs_tensor" in new_ds
        assert demo.current_epoch == 0

    def test_import_dataset_stops_when_running(self):
        """import_dataset stops an active run before installing (lines 1868-1869)."""
        demo = DemoMode()
        demo.state_machine.handle_command(Command.START)
        demo._set_running(True)
        inputs = np.random.RandomState(1).randn(8, 2).astype(np.float32)
        targets = (np.arange(8) % 2).astype(np.int64)

        result = demo.import_dataset(inputs, targets, source_label="unit-test")

        assert demo.running is False
        assert result["n_samples"] == 8
        assert result["n_features"] == 2
        assert result["source"] == "unit-test"

    def test_import_dataset_uncoercible_targets_raise(self):
        """Non-integer targets raise a wrapped ValueError (lines 1865-1866)."""
        demo = DemoMode()
        inputs = np.zeros((3, 2), dtype=np.float32)
        targets = np.array(["a", "b", "c"], dtype=object)

        with pytest.raises(ValueError, match="could not be coerced to integer labels"):
            demo.import_dataset(inputs, targets)

    def test_generator_requires_data_url(self, monkeypatch):
        """regenerate_dataset_from_generator raises without a data URL (line 1792)."""
        from juniper_data_client.exceptions import JuniperDataConfigurationError

        demo = DemoMode()

        class _NoUrlSettings:
            juniper_data_url = ""
            juniper_data_api_key = None

        monkeypatch.setattr("demo_mode.get_settings", lambda: _NoUrlSettings())

        with pytest.raises(JuniperDataConfigurationError):
            demo.regenerate_dataset_from_generator(generator="xor")

    def test_generator_missing_dataset_id_raises(self, mock_juniper_data_client):
        """A response without dataset_id raises ValueError (line 1804)."""
        demo = DemoMode()
        with patch.object(mock_juniper_data_client, "create_dataset", return_value={}):
            with pytest.raises(ValueError, match="missing dataset_id"):
                demo.regenerate_dataset_from_generator(generator="xor")

    def test_generator_client_error_reraised(self, mock_juniper_data_client):
        """A JuniperData client error inside the generator path is re-raised (lines 1806-1808)."""
        from juniper_data_client.exceptions import JuniperDataClientError

        demo = DemoMode()
        with patch.object(mock_juniper_data_client, "create_dataset", side_effect=JuniperDataClientError("gen boom")):
            with pytest.raises(JuniperDataClientError, match="gen boom"):
                demo.regenerate_dataset_from_generator(generator="xor")

    def test_generator_artifact_missing_x_raises(self, mock_juniper_data_client):
        """An artifact with neither X_full nor X_train raises after the fallback.

        The X_full arm of that fallback is now the LEGACY one -- decision 11 stopped
        producers emitting it -- so this pins that both arms are still consulted.
        """
        demo = DemoMode()
        with patch.object(mock_juniper_data_client, "create_dataset", return_value={"dataset_id": "d-nox"}), patch.object(mock_juniper_data_client, "download_artifact_npz", return_value={}):
            with pytest.raises(ValueError, match="missing required key: X_full"):
                demo.regenerate_dataset_from_generator(generator="xor")


# ---------------------------------------------------------------------------
# _training_loop synchronous drive: max-hidden stopping criterion
# ---------------------------------------------------------------------------
class TestTrainingLoopStoppingCriterion:
    def test_training_loop_breaks_on_max_hidden_units(self, monkeypatch):
        """Phase 2 exits immediately when hidden units already meet the cap (lines 1234-1236)."""
        # Keep Phase 1 tiny so the synchronous drive is fast.
        monkeypatch.setattr(TrainingConstants, "OUTPUT_RETRAIN_STEPS", 3)

        demo = DemoMode(update_interval=0.0)
        demo.max_hidden_units = 0  # 0 installed >= 0 cap -> immediate Phase-2 break
        demo.state_machine.handle_command(Command.START)
        demo._set_running(True)
        demo._stop.clear()

        # Runs entirely in this thread (no background thread spawned).
        demo._training_loop()

        assert demo.running is False  # loop set running False on completion
        assert len(demo.network.hidden_units) == 0  # never grew past the cap
