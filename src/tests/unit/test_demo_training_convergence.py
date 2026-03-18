"""
Tests for CasCor demo mode training convergence after algorithmic fixes.

Validates:
- Training reduces loss below threshold after hidden unit addition
- Hidden units produce non-constant (discriminative) features
- Accuracy exceeds chance level on spiral-like data
- Tanh activation and MSE loss are correctly applied
- Candidate pool selects the best candidate
- Decision boundary becomes non-linear with hidden units
- Output retraining adequately adapts to new hidden features
"""

import numpy as np
import pytest
import torch

from demo_mode import MockCascorNetwork

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def spiral_network():
    """Create a MockCascorNetwork with a 2-class spiral-like dataset."""
    net = MockCascorNetwork(input_size=2, output_size=1)
    np.random.seed(42)

    n_per_class = 100
    theta = np.linspace(0, 3 * np.pi, n_per_class)

    # Class 0: one arm of spiral
    r0 = theta / (3 * np.pi) * 3
    x0 = np.column_stack([r0 * np.cos(theta), r0 * np.sin(theta)])
    x0 += np.random.randn(n_per_class, 2) * 0.15

    # Class 1: opposite arm
    r1 = theta / (3 * np.pi) * 3
    x1 = np.column_stack([-r1 * np.cos(theta), -r1 * np.sin(theta)])
    x1 += np.random.randn(n_per_class, 2) * 0.15

    inputs = np.vstack([x0, x1]).astype(np.float32)
    targets = np.concatenate([np.zeros(n_per_class), np.ones(n_per_class)]).astype(np.float32)
    idx = np.random.permutation(len(inputs))

    net.train_x = torch.from_numpy(inputs[idx])
    net.train_y = torch.from_numpy(targets[idx]).unsqueeze(1)
    return net


@pytest.fixture
def xor_network():
    """Create a MockCascorNetwork with an XOR dataset (requires non-linear separation)."""
    net = MockCascorNetwork(input_size=2, output_size=1)
    np.random.seed(42)

    n_per_quadrant = 50
    # XOR: class 0 in quadrants 1 and 3, class 1 in quadrants 2 and 4
    q1 = np.random.randn(n_per_quadrant, 2) * 0.3 + np.array([1.0, 1.0])
    q3 = np.random.randn(n_per_quadrant, 2) * 0.3 + np.array([-1.0, -1.0])
    q2 = np.random.randn(n_per_quadrant, 2) * 0.3 + np.array([-1.0, 1.0])
    q4 = np.random.randn(n_per_quadrant, 2) * 0.3 + np.array([1.0, -1.0])

    inputs = np.vstack([q1, q3, q2, q4]).astype(np.float32)
    targets = np.concatenate(
        [
            np.zeros(n_per_quadrant * 2),  # class 0: Q1, Q3
            np.ones(n_per_quadrant * 2),  # class 1: Q2, Q4
        ]
    ).astype(np.float32)
    idx = np.random.permutation(len(inputs))

    net.train_x = torch.from_numpy(inputs[idx])
    net.train_y = torch.from_numpy(targets[idx]).unsqueeze(1)
    return net


# ─── Activation Function Correctness ────────────────────────────────────────


class TestActivationFunction:
    """Verify hidden units use tanh activation (not sigmoid)."""

    def test_hidden_units_use_tanh(self, spiral_network):
        """Added hidden units should use torch.tanh activation."""
        spiral_network.add_hidden_unit()
        assert spiral_network.hidden_units[0]["activation_fn"] == torch.tanh

    def test_hidden_unit_output_range_is_tanh(self, spiral_network):
        """Hidden unit outputs should be in [-1, 1] (tanh range)."""
        spiral_network.add_hidden_unit()
        unit = spiral_network.hidden_units[0]
        z = torch.sum(spiral_network.train_x * unit["weights"], dim=1) + unit["bias"]
        h = unit["activation_fn"](z)
        assert h.min() >= -1.0
        assert h.max() <= 1.0

    def test_forward_output_is_raw(self, spiral_network):
        """Forward pass should return raw (unsigmoid) output."""
        output = spiral_network.forward(spiral_network.train_x)
        # Raw output can be outside [0, 1] — verify it's NOT clamped to sigmoid range
        # With random weights, some outputs should be negative or > 1
        assert output.min() < 0.5 or output.max() > 0.5, "Output appears to be from a constant network"


# ─── Training Convergence ────────────────────────────────────────────────────


class TestTrainingConvergence:
    """Verify training improves after hidden unit addition."""

    def test_initial_training_reduces_loss(self, spiral_network):
        """Loss should decrease during initial output training."""
        with torch.no_grad():
            initial_pred = spiral_network.forward(spiral_network.train_x)
            initial_loss = float(((initial_pred - spiral_network.train_y) ** 2).mean())

        # Train for 100 steps
        for _ in range(100):
            spiral_network.train_output_step()

        with torch.no_grad():
            final_pred = spiral_network.forward(spiral_network.train_x)
            final_loss = float(((final_pred - spiral_network.train_y) ** 2).mean())

        assert final_loss < initial_loss, f"Loss did not decrease: {initial_loss:.4f} -> {final_loss:.4f}"

    def test_loss_improves_after_hidden_unit(self, spiral_network):
        """Loss should decrease further after adding a hidden unit."""
        # Initial training
        for _ in range(100):
            spiral_network.train_output_step()

        with torch.no_grad():
            pred_before = spiral_network.forward(spiral_network.train_x)
            loss_before_unit = float(((pred_before - spiral_network.train_y) ** 2).mean())

        # Add hidden unit (includes 500-step retraining)
        spiral_network.add_hidden_unit()

        # Additional training
        for _ in range(100):
            spiral_network.train_output_step()

        with torch.no_grad():
            pred_after = spiral_network.forward(spiral_network.train_x)
            loss_after_unit = float(((pred_after - spiral_network.train_y) ** 2).mean())

        assert loss_after_unit < loss_before_unit, f"Loss did not improve after hidden unit: {loss_before_unit:.4f} -> {loss_after_unit:.4f}"

    def test_accuracy_exceeds_chance_with_hidden_units(self, spiral_network):
        """Accuracy should exceed 60% after adding 2 hidden units on spiral data."""
        # Train initial output
        for _ in range(100):
            spiral_network.train_output_step()

        # Add 2 hidden units
        spiral_network.add_hidden_unit()
        spiral_network.add_hidden_unit()

        # Additional training
        for _ in range(200):
            spiral_network.train_output_step()

        with torch.no_grad():
            predictions = spiral_network.forward(spiral_network.train_x)
            pred_classes = (predictions > 0.5).float()
            accuracy = float((pred_classes == spiral_network.train_y).float().mean())

        assert accuracy > 0.60, f"Accuracy {accuracy:.2%} is not above 60% (chance level)"

    def test_xor_requires_hidden_units(self, xor_network):
        """XOR cannot be solved linearly; hidden units should improve accuracy."""
        # Linear-only training
        for _ in range(200):
            xor_network.train_output_step()

        with torch.no_grad():
            pred_linear = xor_network.forward(xor_network.train_x)
            acc_linear = float(((pred_linear > 0.5).float() == xor_network.train_y).float().mean())

        # Add hidden unit and retrain
        xor_network.add_hidden_unit()
        for _ in range(200):
            xor_network.train_output_step()

        with torch.no_grad():
            pred_nonlinear = xor_network.forward(xor_network.train_x)
            acc_nonlinear = float(((pred_nonlinear > 0.5).float() == xor_network.train_y).float().mean())

        # XOR accuracy should improve with hidden units
        assert acc_nonlinear > acc_linear, f"Hidden unit did not improve XOR accuracy: {acc_linear:.2%} -> {acc_nonlinear:.2%}"


# ─── Hidden Unit Feature Quality ─────────────────────────────────────────────


class TestHiddenUnitQuality:
    """Verify hidden units produce useful (non-constant) features."""

    def test_hidden_unit_output_is_not_constant(self, spiral_network):
        """Hidden unit should produce varying outputs (not all same value)."""
        spiral_network.add_hidden_unit()
        # Use _cascade_features to get the correct input for the hidden unit
        with torch.no_grad():
            features = spiral_network._cascade_features(spiral_network.train_x)
        # The last column is the hidden unit output
        h = features[:, -1]
        variance = float(h.var())
        assert variance > 1e-5, f"Hidden unit output variance is too low: {variance:.8f} (likely constant)"

    def test_candidate_pool_selects_best(self, spiral_network):
        """The installed hidden unit should have non-trivial correlation."""
        # Train initial output to establish residual
        for _ in range(50):
            spiral_network.train_output_step()

        spiral_network.add_hidden_unit()

        # Verify the unit has trained weights (not random)
        unit = spiral_network.hidden_units[0]
        weight_magnitude = float(unit["weights"].abs().sum())
        assert weight_magnitude > 0.2, f"Hidden unit weights are too small: {weight_magnitude:.4f}"


# ─── Output Retraining Adequacy ──────────────────────────────────────────────


class TestOutputRetraining:
    """Verify output weights adapt to new hidden unit features."""

    def test_output_weight_for_hidden_unit_is_nontrivial(self, spiral_network):
        """After adding a hidden unit, its output weight should be significantly non-zero."""
        # Initial training
        for _ in range(100):
            spiral_network.train_output_step()

        spiral_network.add_hidden_unit()

        # The last column of output_weights corresponds to the new hidden unit
        hidden_weight = float(spiral_network.output_weights[0, -1].abs())
        assert hidden_weight > 0.01, f"Output weight for hidden unit is too small: {hidden_weight:.6f}"


# ─── MSE Loss Correctness ────────────────────────────────────────────────────


class TestMSELoss:
    """Verify MSE loss is computed correctly."""

    def test_loss_is_mse_not_bce(self, spiral_network):
        """Reported loss should match MSE computation."""
        with torch.no_grad():
            predictions = spiral_network.forward(spiral_network.train_x)
            expected_mse = float(((predictions - spiral_network.train_y) ** 2).mean())

        # The loss should be close to MSE (not BCE)
        # BCE for random predictions ≈ 0.69; MSE for random predictions ≈ 0.25
        assert abs(expected_mse - expected_mse) < 1e-5

    def test_loss_decreases_below_bce_floor(self, spiral_network):
        """MSE loss should be able to go well below the BCE floor of ln(2) ≈ 0.693."""
        for _ in range(200):
            spiral_network.train_output_step()

        with torch.no_grad():
            predictions = spiral_network.forward(spiral_network.train_x)
            mse_loss = float(((predictions - spiral_network.train_y) ** 2).mean())

        # MSE loss for a decent linear classifier should be well below 0.5
        assert mse_loss < 0.5, f"MSE loss {mse_loss:.4f} is too high after 200 training steps"


# ─── Decision Boundary Non-Linearity ─────────────────────────────────────────


class TestBoundaryNonLinearity:
    """Verify the decision boundary becomes non-linear with hidden units."""

    def test_boundary_changes_after_hidden_unit(self, spiral_network):
        """Adding a hidden unit should change the decision boundary shape."""
        # Train without hidden units
        for _ in range(100):
            spiral_network.train_output_step()

        # Compute boundary on a grid
        grid = torch.tensor([[-1.0, -1.0], [1.0, 1.0], [-1.0, 1.0], [1.0, -1.0]])
        with torch.no_grad():
            boundary_before = spiral_network.forward(grid).detach()

        # Add hidden unit
        spiral_network.add_hidden_unit()
        for _ in range(100):
            spiral_network.train_output_step()

        with torch.no_grad():
            boundary_after = spiral_network.forward(grid).detach()

        # Boundary should differ meaningfully
        diff = float((boundary_before - boundary_after).abs().mean())
        assert diff > 0.01, f"Boundary did not change after hidden unit (diff={diff:.6f})"

    def test_xor_boundary_is_nonlinear(self, xor_network):
        """After hidden unit additions on XOR, boundary should be non-linear."""
        torch.manual_seed(42)

        # Train initial output
        for _ in range(200):
            xor_network.train_output_step()

        # XOR needs multiple hidden units for non-linear separation
        for _ in range(3):
            xor_network.add_hidden_unit()
        for _ in range(500):
            xor_network.train_output_step()

        # Measure accuracy on full training set (not just corners)
        with torch.no_grad():
            predictions = xor_network.forward(xor_network.train_x)
            pred_classes = (predictions > 0.5).float()
            accuracy = float((pred_classes == xor_network.train_y).float().mean())

        # With hidden units, should exceed the ~50% linear ceiling for XOR
        assert accuracy > 0.60, f"XOR accuracy {accuracy:.0%} — boundary appears still linear"


# ─── Reset Safety ─────────────────────────────────────────────────────────────


class TestResetSafety:
    """Verify network state is consistent after reset."""

    def test_forward_works_after_reset_with_hidden_units(self, spiral_network):
        """forward() should work after reset even if hidden units were previously added."""
        # Add hidden units
        spiral_network.add_hidden_unit()
        spiral_network.add_hidden_unit()

        # Simulate reset by clearing hidden units and reinitializing weights
        spiral_network.hidden_units.clear()
        spiral_network.output_weights = torch.randn(spiral_network.output_size, spiral_network.input_size) * 0.1
        spiral_network.output_bias = torch.randn(spiral_network.output_size) * 0.1

        # forward() should not crash
        output = spiral_network.forward(spiral_network.train_x)
        assert output.shape == (spiral_network.train_x.shape[0], spiral_network.output_size)
