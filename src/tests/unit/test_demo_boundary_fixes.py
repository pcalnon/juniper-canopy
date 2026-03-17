"""
Tests for decision boundary fixes in demo mode.

Validates:
- Hidden unit candidate training (RC-D1)
- Inline weight training — no deferred step loss (RC-D2)
- Real metrics from network predictions (RC-D3)
- Binary class labels via threshold (RC-D4)
- Decision boundary evolution during training (RC-D5)
"""

import threading

import numpy as np
import pytest
import torch

from demo_mode import DemoMode, MockCascorNetwork

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def network():
    """Create a MockCascorNetwork with training data."""
    net = MockCascorNetwork(input_size=2, output_size=1)
    # Simple linearly-separable dataset for fast tests
    np.random.seed(42)
    n = 100
    x0 = np.random.randn(n // 2, 2) + np.array([1.0, 1.0])
    x1 = np.random.randn(n // 2, 2) + np.array([-1.0, -1.0])
    inputs = np.vstack([x0, x1]).astype(np.float32)
    targets = np.concatenate([np.zeros(n // 2), np.ones(n // 2)]).astype(np.float32)
    idx = np.random.permutation(n)
    net.train_x = torch.from_numpy(inputs[idx])
    net.train_y = torch.from_numpy(targets[idx]).unsqueeze(1)
    return net


# ─── RC-D1: Candidate Training ──────────────────────────────────────────────


class TestCandidateTraining:
    """Tests for hidden unit candidate training (RC-D1)."""

    def test_hidden_unit_weights_are_trained_not_random(self, network):
        """After add_hidden_unit, weights should differ from random init."""
        torch.manual_seed(99)
        random_weights = torch.randn(network.input_size) * 0.1

        network.add_hidden_unit()
        trained_weights = network.hidden_units[0]["weights"]

        # Trained weights should NOT match a fresh random init
        assert not torch.allclose(trained_weights, random_weights, atol=0.01), "Hidden unit weights appear untrained (still match random init)"

    def test_candidate_training_improves_correlation(self, network):
        """Trained candidate should have higher correlation with residual than random."""
        # Get residual before adding unit
        with torch.no_grad():
            pred = network.forward(network.train_x)
            residual = network.train_y - pred

        # Create a random (untrained) candidate
        random_unit = {
            "weights": torch.randn(network.input_size) * 0.1,
            "bias": torch.randn(1) * 0.1,
            "activation_fn": torch.sigmoid,
        }
        with torch.no_grad():
            random_out = torch.sigmoid(torch.sum(network.train_x * random_unit["weights"], dim=1) + random_unit["bias"])
            random_corr = abs(float(torch.corrcoef(torch.stack([random_out, residual.squeeze()]))[0, 1]))

        # Now add a trained unit
        network.add_hidden_unit()
        trained_unit = network.hidden_units[0]
        with torch.no_grad():
            trained_out = torch.sigmoid(torch.sum(network.train_x * trained_unit["weights"][: network.input_size], dim=1) + trained_unit["bias"])
            trained_corr = abs(float(torch.corrcoef(torch.stack([trained_out, residual.squeeze()]))[0, 1]))

        # Trained correlation should be higher than random (or at least non-trivial)
        assert trained_corr > 0.1, f"Trained correlation too low: {trained_corr}"
        assert trained_corr >= random_corr, f"Trained corr {trained_corr} < random corr {random_corr}"

    def test_multiple_hidden_units_have_different_weights(self, network):
        """Each hidden unit should learn different features."""
        network.add_hidden_unit()
        network.add_hidden_unit()

        w0 = network.hidden_units[0]["weights"]
        w1 = network.hidden_units[1]["weights"]

        # They should not be identical (different input dims anyway)
        assert w0.shape != w1.shape or not torch.allclose(w0, w1)

    def test_add_hidden_unit_retrains_output_weights(self, network):
        """After adding a hidden unit, output weights should be retrained."""
        # Train baseline
        for _ in range(20):
            network.train_output_step()
        old_weights = network.output_weights.clone()

        network.add_hidden_unit()
        new_weights = network.output_weights

        # Shape should have expanded
        assert new_weights.shape[1] == old_weights.shape[1] + 1
        # Weights should differ (retrained)
        assert not torch.allclose(new_weights[:, : old_weights.shape[1]], old_weights, atol=1e-6)


# ─── RC-D2: Inline Training ─────────────────────────────────────────────────


class TestInlineTraining:
    """Tests for inline weight training (RC-D2)."""

    def test_simulate_training_step_modifies_weights(self):
        """Each _simulate_training_step should result in actual weight changes."""
        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()

        net = MockCascorNetwork(input_size=2, output_size=1)
        np.random.seed(42)
        inputs = np.random.randn(50, 2).astype(np.float32)
        targets = (inputs[:, 0] > 0).astype(np.float32)
        net.train_x = torch.from_numpy(inputs)
        net.train_y = torch.from_numpy(targets).unsqueeze(1)
        demo.network = net
        demo.current_loss = 1.0
        demo.current_accuracy = 0.5

        old_weights = net.output_weights.clone()
        demo._simulate_training_step()
        new_weights = net.output_weights

        assert not torch.allclose(old_weights, new_weights), "Weights unchanged after _simulate_training_step — training is not inline"

    def test_no_pending_train_steps_counter(self):
        """The deferred _pending_train_steps counter should not be used."""
        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()

        net = MockCascorNetwork(input_size=2, output_size=1)
        inputs = np.random.randn(50, 2).astype(np.float32)
        targets = (inputs[:, 0] > 0).astype(np.float32)
        net.train_x = torch.from_numpy(inputs)
        net.train_y = torch.from_numpy(targets).unsqueeze(1)
        demo.network = net
        demo.current_loss = 1.0
        demo.current_accuracy = 0.5

        demo._simulate_training_step()
        # Should NOT increment a pending counter
        assert getattr(demo, "_pending_train_steps", 0) == 0


# ─── RC-D3: Real Metrics ────────────────────────────────────────────────────


class TestRealMetrics:
    """Tests for real metric computation (RC-D3)."""

    def test_accuracy_reflects_network_predictions(self):
        """Accuracy should be computed from actual network forward pass."""
        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()

        net = MockCascorNetwork(input_size=2, output_size=1)
        # Perfect dataset: all class 0
        net.train_x = torch.zeros(10, 2)
        net.train_y = torch.zeros(10, 1)
        # Force network to predict ~0 by setting large negative weights
        net.output_weights = torch.tensor([[-10.0, -10.0]])
        net.output_bias = torch.tensor([-10.0])
        demo.network = net
        demo.current_loss = 1.0
        demo.current_accuracy = 0.5

        loss, accuracy = demo._simulate_training_step()

        # With all targets=0 and predictions~0, accuracy should be ~1.0
        assert accuracy > 0.9, f"Expected high accuracy for trivial dataset, got {accuracy}"

    def test_loss_is_not_synthetic_decay(self):
        """Loss should NOT follow the old synthetic decay formula."""
        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()

        net = MockCascorNetwork(input_size=2, output_size=1)
        inputs = np.random.randn(50, 2).astype(np.float32)
        targets = (inputs[:, 0] > 0).astype(np.float32)
        net.train_x = torch.from_numpy(inputs)
        net.train_y = torch.from_numpy(targets).unsqueeze(1)
        demo.network = net
        demo.current_loss = 1.0
        demo.current_accuracy = 0.5

        loss, _ = demo._simulate_training_step()

        # Old synthetic formula: loss = target + (1.0 - target) * 0.95 ≈ 0.95 + target * 0.05
        # With target_loss=0.1: ≈ 0.955. Real BCE loss would be different.
        synthetic_loss = 0.1 + (1.0 - 0.1) * (1 - 0.05)  # 0.955
        assert abs(loss - synthetic_loss) > 0.01, f"Loss {loss} matches synthetic decay formula {synthetic_loss} — still using fake metrics"


# ─── RC-D4: Binary Class Labels ─────────────────────────────────────────────


class TestBinaryClassLabels:
    """Tests for argmax/threshold in boundary output (RC-D4)."""

    def test_boundary_Z_contains_integers(self, network):
        """Decision boundary Z values should be integer class labels."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()
        demo.network = network
        demo.dataset = {
            "inputs": network.train_x.numpy(),
            "targets": network.train_y.numpy().flatten(),
        }

        backend = DemoBackend.__new__(DemoBackend)
        backend._demo = demo

        result = backend.get_decision_boundary(resolution=10)
        assert result is not None

        Z = np.array(result["Z"])
        unique_vals = np.unique(Z)
        for val in unique_vals:
            assert val in (0, 1), f"Expected integer class label (0 or 1), got {val}"

    def test_boundary_Z_not_continuous(self, network):
        """Z should not contain continuous sigmoid values."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()
        demo.network = network
        demo.dataset = {
            "inputs": network.train_x.numpy(),
            "targets": network.train_y.numpy().flatten(),
        }

        backend = DemoBackend.__new__(DemoBackend)
        backend._demo = demo

        result = backend.get_decision_boundary(resolution=20)
        Z = np.array(result["Z"])

        # If continuous, there would be many unique values. With binary labels, at most 2.
        assert len(np.unique(Z)) <= 2, f"Z has {len(np.unique(Z))} unique values — expected at most 2 (binary class labels)"


# ─── RC-D5: Boundary Evolution ──────────────────────────────────────────────


class TestBoundaryEvolution:
    """Tests for boundary evolution during training (RC-D5)."""

    def test_boundary_changes_after_training(self, network):
        """Decision boundary should change as weights are trained."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()
        demo.network = network
        demo.dataset = {
            "inputs": network.train_x.numpy(),
            "targets": network.train_y.numpy().flatten(),
        }

        backend = DemoBackend.__new__(DemoBackend)
        backend._demo = demo

        # Get initial boundary
        result1 = backend.get_decision_boundary(resolution=10)
        Z1 = np.array(result1["Z"])

        # Train for several steps
        for _ in range(50):
            network.train_output_step()

        # Get updated boundary
        result2 = backend.get_decision_boundary(resolution=10)
        Z2 = np.array(result2["Z"])

        # Boundaries should differ after training
        assert not np.array_equal(Z1, Z2), "Boundary unchanged after 50 training steps"

    def test_accuracy_improves_with_training(self, network):
        """Network accuracy should improve over training steps."""
        with torch.no_grad():
            pred_before = network.forward(network.train_x)
            acc_before = float(((pred_before > 0.5).float() == network.train_y).float().mean())

        for _ in range(200):
            network.train_output_step()

        with torch.no_grad():
            pred_after = network.forward(network.train_x)
            acc_after = float(((pred_after > 0.5).float() == network.train_y).float().mean())

        assert acc_after > acc_before, f"Accuracy did not improve: before={acc_before:.3f}, after={acc_after:.3f}"

    def test_hidden_unit_improves_boundary(self, network):
        """Adding a trained hidden unit should improve classification."""
        # Train output weights to convergence first
        for _ in range(200):
            network.train_output_step()

        with torch.no_grad():
            pred_before = network.forward(network.train_x)
            acc_before = float(((pred_before > 0.5).float() == network.train_y).float().mean())

        # Add a hidden unit (with candidate training + output retraining)
        network.add_hidden_unit()

        # Train output weights more
        for _ in range(200):
            network.train_output_step()

        with torch.no_grad():
            pred_after = network.forward(network.train_x)
            acc_after = float(((pred_after > 0.5).float() == network.train_y).float().mean())

        # Should be at least as good (hidden unit adds capacity)
        assert acc_after >= acc_before - 0.05, f"Accuracy degraded after adding hidden unit: before={acc_before:.3f}, after={acc_after:.3f}"


# ─── Thread Safety ───────────────────────────────────────────────────────────


class TestThreadSafety:
    """Tests for thread safety during concurrent access."""

    def test_concurrent_boundary_and_hidden_unit_add(self, network):
        """Boundary computation during add_hidden_unit should not crash."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode.__new__(DemoMode)
        demo.logger = __import__("logging").getLogger("test")
        demo._lock = threading.Lock()
        demo.network = network
        demo.dataset = {
            "inputs": network.train_x.numpy(),
            "targets": network.train_y.numpy().flatten(),
        }

        backend = DemoBackend.__new__(DemoBackend)
        backend._demo = demo

        errors = []

        def add_units():
            try:
                for _ in range(3):
                    with demo._lock:
                        network.add_hidden_unit()
            except Exception as e:
                errors.append(e)

        def compute_boundary():
            try:
                for _ in range(5):
                    backend.get_decision_boundary(resolution=5)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=add_units)
        t2 = threading.Thread(target=compute_boundary)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(errors) == 0, f"Concurrent access errors: {errors}"
