"""
Tests for Phase 4 implementation: nn.Linear + Adam, Pearson correlation,
input normalization, convergence-based cascade addition, and related changes.

These tests verify the specific Phase 4 architectural changes to MockCascorNetwork
as documented in CASCOR_DEMO_TRAINING_ERROR_PLAN.md.
"""

import pytest
import torch

from canopy_constants import TrainingConstants
from demo_mode import MockCascorNetwork


@pytest.fixture
def network():
    """Create a MockCascorNetwork with default settings."""
    torch.manual_seed(42)
    return MockCascorNetwork(input_size=2, output_size=1)


@pytest.fixture
def network_with_data():
    """Create a MockCascorNetwork with spiral-like training data."""
    torch.manual_seed(42)
    net = MockCascorNetwork(input_size=2, output_size=1)
    # Simple spiral-like data in [-1, 1] range (normalized)
    n = 100
    theta = torch.linspace(0, 4 * 3.14159, n)
    r = theta / (4 * 3.14159)
    x0 = r * torch.cos(theta) + torch.randn(n) * 0.05
    y0 = r * torch.sin(theta) + torch.randn(n) * 0.05
    x1 = -r * torch.cos(theta) + torch.randn(n) * 0.05
    y1 = -r * torch.sin(theta) + torch.randn(n) * 0.05
    inputs = torch.cat([torch.stack([x0, y0], dim=1), torch.stack([x1, y1], dim=1)])
    targets = torch.cat([torch.zeros(n), torch.ones(n)]).unsqueeze(1)
    net.train_x = inputs
    net.train_y = targets
    return net


# ─── Output Layer Architecture ───────────────────────────────────────────────


class TestOutputLayerArchitecture:
    """Verify output layer uses nn.Linear + Adam optimizer."""

    def test_output_layer_is_nn_linear(self, network):
        assert isinstance(network.output_layer, torch.nn.Linear)
        assert network.output_layer.in_features == 2
        assert network.output_layer.out_features == 1

    def test_output_optimizer_is_adam(self, network):
        assert isinstance(network.output_optimizer, torch.optim.Adam)

    def test_loss_fn_is_mse(self, network):
        assert isinstance(network.loss_fn, torch.nn.MSELoss)


# ─── Input Normalization ─────────────────────────────────────────────────────


class TestInputNormalization:
    """Verify normalize_inputs() method."""

    def test_normalize_inputs_scales_to_minus_one_one(self, network):
        network._input_min = torch.tensor([0.0, -10.0])
        network._input_max = torch.tensor([10.0, 10.0])
        x = torch.tensor([[0.0, -10.0], [5.0, 0.0], [10.0, 10.0]])
        normalized = network.normalize_inputs(x)
        assert torch.allclose(normalized[0], torch.tensor([-1.0, -1.0]), atol=1e-5)
        assert torch.allclose(normalized[2], torch.tensor([1.0, 1.0]), atol=1e-5)
        assert (normalized >= -1.01).all() and (normalized <= 1.01).all()

    def test_normalize_inputs_passthrough_when_no_params(self, network):
        x = torch.tensor([[5.0, -3.0], [10.0, 7.0]])
        result = network.normalize_inputs(x)
        assert torch.equal(result, x)

    def test_normalize_inputs_handles_constant_feature(self, network):
        network._input_min = torch.tensor([5.0, 5.0])
        network._input_max = torch.tensor([5.0, 5.0])  # constant feature
        x = torch.tensor([[5.0, 5.0]])
        result = network.normalize_inputs(x)
        assert torch.isfinite(result).all()


# ─── Cascade Features ────────────────────────────────────────────────────────


class TestCascadeFeatures:
    """Verify _cascade_features() helper method."""

    def test_no_hidden_units_returns_input(self, network):
        x = torch.randn(10, 2)
        with torch.no_grad():
            features = network._cascade_features(x)
        assert torch.equal(features, x)

    def test_shape_with_one_hidden_unit(self, network_with_data):
        network_with_data.add_hidden_unit()
        with torch.no_grad():
            features = network_with_data._cascade_features(network_with_data.train_x)
        assert features.shape == (network_with_data.train_x.shape[0], 3)  # 2 inputs + 1 hidden

    def test_shape_with_multiple_hidden_units(self, network_with_data):
        network_with_data.add_hidden_unit()
        network_with_data.add_hidden_unit()
        with torch.no_grad():
            features = network_with_data._cascade_features(network_with_data.train_x)
        assert features.shape == (network_with_data.train_x.shape[0], 4)  # 2 inputs + 2 hidden

    def test_first_columns_are_original_inputs(self, network_with_data):
        network_with_data.add_hidden_unit()
        with torch.no_grad():
            features = network_with_data._cascade_features(network_with_data.train_x)
        assert torch.equal(features[:, :2], network_with_data.train_x)


# ─── Convergence-Based Cascade Addition ──────────────────────────────────────


class TestConvergenceBasedCascade:
    """Verify _should_add_cascade_unit() convergence detection."""

    def _make_demo(self):
        """Create a DemoMode-like object with minimal attributes."""
        import threading
        from unittest.mock import MagicMock, patch

        from demo_mode import DemoMode

        demo = DemoMode.__new__(DemoMode)
        demo.logger = MagicMock()
        demo._lock = threading.Lock()
        demo.network = MockCascorNetwork(input_size=2, output_size=1)
        demo.max_hidden_units = 10
        demo.cascade_every = 30
        demo.current_epoch = 15  # not at fixed interval
        demo.convergence_enabled = True
        demo.convergence_threshold = 0.001
        demo._cascade_cooldown_remaining = 0
        return demo

    def test_convergence_stall_triggers_addition(self):
        demo = self._make_demo()
        # Populate history with stagnant loss (improvement < 0.001)
        for _ in range(15):
            demo.network.history["train_loss"].append(0.25)
        assert demo._should_add_cascade_unit() is True

    def test_improving_loss_does_not_trigger(self):
        demo = self._make_demo()
        # Populate history with improving loss
        for i in range(15):
            demo.network.history["train_loss"].append(1.0 - i * 0.05)
        assert demo._should_add_cascade_unit() is False

    def test_insufficient_history_uses_fixed_schedule(self):
        demo = self._make_demo()
        # Only 5 entries — not enough for convergence check
        for _ in range(5):
            demo.network.history["train_loss"].append(0.25)
        demo.current_epoch = 15  # not at fixed interval (30)
        assert demo._should_add_cascade_unit() is False

    def test_fixed_schedule_fallback(self):
        demo = self._make_demo()
        demo.current_epoch = 30  # at fixed interval
        # Only a few loss entries (not enough for convergence check)
        for _ in range(3):
            demo.network.history["train_loss"].append(0.5)
        assert demo._should_add_cascade_unit() is True

    def test_max_units_blocks_addition(self):
        demo = self._make_demo()
        demo.max_hidden_units = 0
        for _ in range(15):
            demo.network.history["train_loss"].append(0.25)
        assert demo._should_add_cascade_unit() is False


# ─── Fresh Optimizer After Installation ──────────────────────────────────────


class TestFreshOptimizer:
    """Verify a fresh Adam optimizer is created after each hidden unit install."""

    def test_optimizer_changes_after_hidden_unit(self, network_with_data):
        old_optimizer = network_with_data.output_optimizer
        network_with_data.add_hidden_unit()
        assert network_with_data.output_optimizer is not old_optimizer

    def test_fresh_optimizer_discards_old_momentum(self, network_with_data):
        # Train to accumulate momentum in the old optimizer
        for _ in range(20):
            network_with_data.train_output_step()
        old_optimizer = network_with_data.output_optimizer
        assert len(old_optimizer.state) > 0

        # Add hidden unit — should create a fresh optimizer (different object)
        network_with_data.add_hidden_unit()
        new_optimizer = network_with_data.output_optimizer
        # The new optimizer is a different object from the old one
        assert new_optimizer is not old_optimizer
        # The new optimizer's param_groups reference the new layer's parameters
        new_params = {id(p) for pg in new_optimizer.param_groups for p in pg["params"]}
        old_params = {id(p) for pg in old_optimizer.param_groups for p in pg["params"]}
        assert new_params != old_params, "New optimizer should reference different parameters"

    def test_output_layer_expands_after_hidden_unit(self, network_with_data):
        assert network_with_data.output_layer.in_features == 2
        network_with_data.add_hidden_unit()
        assert network_with_data.output_layer.in_features == 3


# ─── Backward-Compatible Properties ──────────────────────────────────────────


class TestBackwardCompatibleProperties:
    """Verify output_weights/output_bias properties work with nn.Linear."""

    def test_output_weights_getter_returns_layer_data(self, network):
        assert torch.equal(network.output_weights, network.output_layer.weight.data)

    def test_output_bias_getter_returns_layer_data(self, network):
        assert torch.equal(network.output_bias, network.output_layer.bias.data)

    def test_output_weights_setter_rebuilds_layer(self, network):
        new_weights = torch.randn(1, 3) * 0.1  # different input size
        network.output_weights = new_weights
        assert network.output_layer.in_features == 3
        assert network.output_layer.out_features == 1
        assert torch.equal(network.output_layer.weight.data, new_weights)

    def test_output_weights_setter_creates_fresh_optimizer(self, network):
        old_optimizer = network.output_optimizer
        network.output_weights = torch.randn(1, 2) * 0.1
        assert network.output_optimizer is not old_optimizer

    def test_output_bias_setter_updates_layer(self, network):
        new_bias = torch.tensor([0.42])
        network.output_bias = new_bias
        assert torch.equal(network.output_layer.bias.data, new_bias)

    def test_round_trip_consistency(self, network):
        w = torch.randn(1, 2) * 0.5
        b = torch.tensor([0.3])
        network.output_weights = w
        network.output_bias = b
        assert torch.equal(network.output_weights, w)
        assert torch.equal(network.output_bias, b)


# ─── Full-Batch Training Default ─────────────────────────────────────────────


class TestFullBatchDefault:
    """Verify train_output_step defaults to full-batch."""

    def test_default_batch_size_is_none(self, network_with_data):
        """Calling train_output_step() without args uses full batch."""
        import inspect

        sig = inspect.signature(network_with_data.train_output_step)
        default = sig.parameters["batch_size"].default
        assert default is None

    def test_mini_batch_still_works(self, network_with_data):
        """Explicitly passing batch_size should use a subset."""
        with torch.no_grad():
            pred = network_with_data.forward(network_with_data.train_x)
            loss_before = float(((pred - network_with_data.train_y) ** 2).mean())

        for _ in range(50):
            network_with_data.train_output_step(batch_size=32)

        with torch.no_grad():
            pred = network_with_data.forward(network_with_data.train_x)
            loss_after = float(((pred - network_with_data.train_y) ** 2).mean())

        assert loss_after < loss_before


# ─── Candidate Training Hyperparameters ──────────────────────────────────────


class TestCandidateHyperparameters:
    """Verify candidate training uses correct hyperparameters."""

    def test_train_candidate_returns_positive_correlation(self, network_with_data):
        """_train_candidate should return a positive correlation value."""
        # Train initial output to establish a residual
        for _ in range(50):
            network_with_data.train_output_step()

        unit = {
            "id": 0,
            "weights": torch.randn(2) * 0.1,
            "bias": torch.randn(1) * 0.1,
            "activation_fn": torch.tanh,
        }
        correlation = network_with_data._train_candidate(unit, steps=50, lr=0.01)
        assert correlation > 0, f"Candidate correlation should be positive, got {correlation}"

    def test_add_hidden_unit_calls_train_candidate_with_200_steps(self, network_with_data):
        """add_hidden_unit should use 200 steps and lr=0.01 for candidate training."""
        from unittest.mock import patch

        calls = []
        original = network_with_data._train_candidate

        def spy(unit, steps=TrainingConstants.CANDIDATE_TRAINING_STEPS, lr=0.01):
            calls.append({"steps": steps, "lr": lr})
            return original(unit, steps=steps, lr=lr)

        with patch.object(network_with_data, "_train_candidate", side_effect=spy):
            network_with_data.add_hidden_unit(
                candidate_steps=TrainingConstants.CANDIDATE_TRAINING_STEPS,
                pool_size=TrainingConstants.CANDIDATE_POOL_SIZE,
            )

        assert len(calls) == TrainingConstants.CANDIDATE_POOL_SIZE
        for call in calls:
            assert call["steps"] == TrainingConstants.CANDIDATE_TRAINING_STEPS
            assert call["lr"] == 0.01


# ─── Retrain Steps After Installation ────────────────────────────────────────


class TestRetrainSteps:
    """Verify output retraining uses OUTPUT_RETRAIN_STEPS after hidden unit install."""

    def test_add_hidden_unit_runs_retrain_steps(self, network_with_data):
        """add_hidden_unit should call train_output_step OUTPUT_RETRAIN_STEPS times."""
        from unittest.mock import patch

        call_count = 0
        original = network_with_data.train_output_step

        def counting_step(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original(*args, **kwargs)

        # Patch after the candidate training phase (which also trains)
        # We need to count only the retrain calls
        with patch.object(network_with_data, "train_output_step", side_effect=counting_step):
            network_with_data.add_hidden_unit()

        expected = TrainingConstants.OUTPUT_RETRAIN_STEPS
        assert call_count == expected, f"Expected {expected} retrain steps, got {call_count}"
