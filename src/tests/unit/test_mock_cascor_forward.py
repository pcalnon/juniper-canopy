"""
Tests for MockCascorNetwork.forward() cascade-correlation architecture.

Verifies that the mock network properly cascades data through hidden units
and produces output that changes as hidden units are added and weights evolve.
"""

import pytest
import torch

from demo_mode import MockCascorNetwork


@pytest.fixture
def network():
    """Create a MockCascorNetwork with known seed for reproducibility."""
    torch.manual_seed(42)
    return MockCascorNetwork(input_size=2, output_size=1)


@pytest.fixture
def sample_input():
    """Sample input batch for testing."""
    return torch.tensor([[1.0, 2.0], [-1.0, 0.5], [0.0, 0.0]])


class TestForwardNoHiddenUnits:
    """Forward pass with no hidden units (input-to-output only)."""

    def test_output_shape(self, network, sample_input):
        """Output shape must be (batch_size, output_size)."""
        output = network.forward(sample_input)
        assert output.shape == (3, 1)

    def test_output_is_sigmoid(self, network, sample_input):
        """Output must be in (0, 1) range (sigmoid activation)."""
        output = network.forward(sample_input)
        assert (output > 0).all()
        assert (output < 1).all()

    def test_output_uses_output_weights(self, network, sample_input):
        """Modifying output_weights should change the output."""
        out_before = network.forward(sample_input).clone()
        network.output_weights = torch.ones_like(network.output_weights) * 5.0
        out_after = network.forward(sample_input)
        assert not torch.allclose(out_before, out_after)

    def test_output_uses_output_bias(self, network, sample_input):
        """Modifying output_bias should change the output."""
        out_before = network.forward(sample_input).clone()
        network.output_bias = torch.ones_like(network.output_bias) * 5.0
        out_after = network.forward(sample_input)
        assert not torch.allclose(out_before, out_after)


class TestForwardWithHiddenUnits:
    """Forward pass with hidden units (cascade architecture)."""

    def test_adding_hidden_unit_changes_output(self, network, sample_input):
        """Adding a hidden unit must change the forward() output."""
        out_before = network.forward(sample_input).clone()
        network.add_hidden_unit()
        out_after = network.forward(sample_input)
        assert not torch.allclose(out_before, out_after)

    def test_output_shape_unchanged_with_hidden_units(self, network, sample_input):
        """Output shape must remain (batch_size, output_size) regardless of hidden count."""
        network.add_hidden_unit()
        network.add_hidden_unit()
        output = network.forward(sample_input)
        assert output.shape == (3, 1)

    def test_multiple_hidden_units_all_contribute(self, network, sample_input):
        """Each additional hidden unit must change the output."""
        outputs = [network.forward(sample_input).clone()]
        for _ in range(3):
            network.add_hidden_unit()
            outputs.append(network.forward(sample_input).clone())

        # Each output should differ from the previous
        for i in range(1, len(outputs)):
            assert not torch.allclose(outputs[i - 1], outputs[i]), f"Output unchanged after adding hidden unit {i}"

    def test_hidden_unit_weights_affect_output(self, network, sample_input):
        """Modifying a hidden unit's weights should change the output."""
        network.add_hidden_unit()
        out_before = network.forward(sample_input).clone()
        network.hidden_units[0]["weights"] = torch.ones_like(network.hidden_units[0]["weights"]) * 2.0
        out_after = network.forward(sample_input)
        assert not torch.allclose(out_before, out_after)

    def test_hidden_unit_receives_correct_input_dimension(self, network):
        """Hidden unit k must receive (input_size + k) dimensional input."""
        # Unit 0 receives inputs only: dim = input_size = 2
        assert network.input_size == 2

        network.add_hidden_unit()
        assert network.hidden_units[0]["weights"].shape == (2,)  # input_size + 0

        network.add_hidden_unit()
        assert network.hidden_units[1]["weights"].shape == (3,)  # input_size + 1

        network.add_hidden_unit()
        assert network.hidden_units[2]["weights"].shape == (4,)  # input_size + 2

    def test_output_weights_expand_with_hidden_units(self, network):
        """output_weights columns must grow as hidden units are added."""
        assert network.output_weights.shape == (1, 2)  # (output_size, input_size)
        network.add_hidden_unit()
        assert network.output_weights.shape == (1, 3)
        network.add_hidden_unit()
        assert network.output_weights.shape == (1, 4)

    def test_output_in_sigmoid_range_with_many_hidden_units(self, network, sample_input):
        """Output must stay in (0, 1) with many hidden units."""
        for _ in range(10):
            network.add_hidden_unit()
        output = network.forward(sample_input)
        assert (output > 0).all()
        assert (output < 1).all()


class TestForwardDeterminism:
    """Forward pass should be deterministic given fixed weights."""

    def test_same_input_same_output(self, network, sample_input):
        """Same input must produce identical output."""
        out1 = network.forward(sample_input)
        out2 = network.forward(sample_input)
        assert torch.allclose(out1, out2)

    def test_deterministic_with_hidden_units(self, network, sample_input):
        """Same input must produce identical output with hidden units."""
        network.add_hidden_unit()
        network.add_hidden_unit()
        out1 = network.forward(sample_input)
        out2 = network.forward(sample_input)
        assert torch.allclose(out1, out2)
