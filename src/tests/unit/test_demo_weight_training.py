"""
Tests for MockCascorNetwork weight training and DemoMode boundary evolution.

Verifies that:
- train_output_step() actually modifies output weights
- Training reduces loss over multiple steps
- Decision boundary data changes as training progresses
- Adding hidden units changes boundary shape
"""

import numpy as np
import pytest
import torch

from demo_mode import DemoMode, MockCascorNetwork


@pytest.fixture
def network_with_data():
    """Create a MockCascorNetwork with XOR-like training data."""
    torch.manual_seed(42)
    net = MockCascorNetwork(input_size=2, output_size=1)

    # Simple XOR-like data
    inputs = torch.tensor([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
    targets = torch.tensor([[0.0], [1.0], [1.0], [0.0]])
    net.train_x = inputs
    net.train_y = targets
    return net


@pytest.fixture
def demo():
    """Create a DemoMode instance for boundary evolution tests."""
    demo = DemoMode(update_interval=0.01)
    yield demo
    demo.stop()


class TestTrainOutputStep:
    """Tests for MockCascorNetwork.train_output_step()."""

    def test_modifies_output_weights(self, network_with_data):
        """Training step must change output_weights."""
        weights_before = network_with_data.output_weights.clone()
        network_with_data.train_output_step()
        assert not torch.allclose(weights_before, network_with_data.output_weights)

    def test_modifies_output_bias(self, network_with_data):
        """Training step must change output_bias."""
        bias_before = network_with_data.output_bias.clone()
        network_with_data.train_output_step()
        assert not torch.allclose(bias_before, network_with_data.output_bias)

    def test_does_not_modify_hidden_weights(self, network_with_data):
        """Hidden unit weights must remain frozen during output training."""
        network_with_data.add_hidden_unit()
        hidden_weights_before = network_with_data.hidden_units[0]["weights"].clone()
        network_with_data.train_output_step()
        assert torch.allclose(hidden_weights_before, network_with_data.hidden_units[0]["weights"])

    def test_reduces_loss_over_steps(self, network_with_data):
        """Loss must decrease over multiple training steps."""
        with torch.no_grad():
            pred = network_with_data.forward(network_with_data.train_x)
            initial_loss = torch.nn.functional.mse_loss(pred, network_with_data.train_y).item()

        for _ in range(50):
            network_with_data.train_output_step()

        with torch.no_grad():
            pred = network_with_data.forward(network_with_data.train_x)
            final_loss = torch.nn.functional.mse_loss(pred, network_with_data.train_y).item()

        assert final_loss < initial_loss

    def test_noop_without_training_data(self):
        """Training step with no data should not crash."""
        net = MockCascorNetwork(input_size=2, output_size=1)
        weights_before = net.output_weights.clone()
        net.train_output_step()  # Should not raise
        assert torch.allclose(weights_before, net.output_weights)

    def test_gradients_disabled_after_step(self, network_with_data):
        """output_weights.requires_grad must be False after training step."""
        network_with_data.train_output_step()
        assert not network_with_data.output_weights.requires_grad
        assert not network_with_data.output_bias.requires_grad

    def test_works_with_hidden_units(self, network_with_data):
        """Training step must work after hidden units are added."""
        network_with_data.add_hidden_unit(candidate_steps=50, pool_size=4)
        network_with_data.add_hidden_unit(candidate_steps=50, pool_size=4)
        # Re-initialize output optimizer so the next step starts fresh
        # (the retrain inside add_hidden_unit may have converged the Adam state)
        network_with_data.output_optimizer = torch.optim.Adam(network_with_data.output_layer.parameters(), lr=0.01)
        weights_before = network_with_data.output_weights.clone()
        network_with_data.train_output_step()
        assert not torch.allclose(weights_before, network_with_data.output_weights)


class TestBoundaryEvolution:
    """Tests for decision boundary changes during training."""

    def test_boundary_changes_after_training(self, demo):
        """Decision boundary data must differ after training steps."""
        from backend.demo_backend import DemoBackend

        backend = DemoBackend(demo)
        boundary_before = backend.get_decision_boundary(resolution=10)

        # Run sufficient training steps for MSE output to cross 0.5 threshold
        for _ in range(100):
            demo._simulate_training_step()

        boundary_after = backend.get_decision_boundary(resolution=10)

        assert boundary_before is not None
        assert boundary_after is not None

        Z_before = np.array(boundary_before["Z"])
        Z_after = np.array(boundary_after["Z"])
        assert not np.allclose(Z_before, Z_after), "Boundary unchanged after training"

    def test_boundary_evolves_with_hidden_units(self, demo):
        """Adding hidden units must change boundary shape."""
        from backend.demo_backend import DemoBackend

        backend = DemoBackend(demo)
        boundary_before = backend.get_decision_boundary(resolution=10)

        with demo._lock:
            demo.network.add_hidden_unit()

        # Train the new output weights
        for _ in range(10):
            demo._simulate_training_step()

        boundary_after = backend.get_decision_boundary(resolution=10)

        assert boundary_before is not None
        assert boundary_after is not None

        Z_before = np.array(boundary_before["Z"])
        Z_after = np.array(boundary_after["Z"])
        assert not np.allclose(Z_before, Z_after), "Boundary unchanged after adding hidden unit"

    def test_simulate_training_step_returns_metrics(self, demo):
        """_simulate_training_step must return valid loss and accuracy."""
        loss, accuracy = demo._simulate_training_step()
        assert isinstance(loss, float)
        assert isinstance(accuracy, float)
        assert 0 <= accuracy <= 1.0
        assert loss > 0
