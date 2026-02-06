"""
Unit Tests for CascorIntegration Topology Extraction

Tests network topology extraction, serialization, and thread safety.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest
import torch

from backend.cascor_integration import CascorIntegration


class FakeHiddenUnit:
    """Fake hidden unit for topology testing."""

    def __init__(self, unit_id, weights_size=3, bias_val=0.5):
        """Initialize fake hidden unit."""
        self.weights = torch.randn(weights_size)
        self.bias = bias_val
        self.activation_fn = torch.sigmoid


@pytest.mark.unit
class TestCascorIntegrationTopology:
    """Test suite for CascorIntegration topology extraction."""

    def test_get_network_topology_happy_path(self):
        """Test get_network_topology extracts complete topology."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                # Create fake network with realistic structure
                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 3)  # 1 output, 3 inputs (2 input + 1 hidden)
                network.output_bias = torch.randn(1)
                network.hidden_units = [{"weights": torch.randn(2), "bias": 0.5, "activation_fn": torch.sigmoid}]

                integration.network = network

                topology = integration.get_network_topology()

                assert topology is not None
                assert topology["input_size"] == 2
                assert topology["output_size"] == 1
                assert len(topology["hidden_units"]) == 1
                assert isinstance(topology["output_weights"], list)
                assert isinstance(topology["output_bias"], list)

    def test_get_network_topology_multiple_hidden_units(self):
        """Test get_network_topology with multiple hidden units."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 3
                network.output_size = 2
                network.output_weights = torch.randn(2, 5)  # 2 outputs, 5 inputs (3 input + 2 hidden)
                network.output_bias = torch.randn(2)
                network.hidden_units = [
                    {"weights": torch.randn(3), "bias": 0.3, "activation_fn": torch.sigmoid},
                    {"weights": torch.randn(4), "bias": 0.7, "activation_fn": torch.tanh},
                ]

                integration.network = network

                topology = integration.get_network_topology()

                assert len(topology["hidden_units"]) == 2
                assert topology["hidden_units"][0]["id"] == 0
                assert topology["hidden_units"][1]["id"] == 1
                assert topology["hidden_units"][0]["bias"] == 0.3
                assert topology["hidden_units"][1]["bias"] == 0.7

    def test_get_network_topology_activation_function_names(self):
        """Test get_network_topology extracts activation function names."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 4)
                network.output_bias = torch.randn(1)
                network.hidden_units = [
                    {"weights": torch.randn(2), "bias": 0.5, "activation_fn": torch.sigmoid},
                    {"weights": torch.randn(3), "bias": 0.5, "activation_fn": torch.relu},
                ]

                integration.network = network

                topology = integration.get_network_topology()

                assert topology["hidden_units"][0]["activation"] == "sigmoid"
                assert topology["hidden_units"][1]["activation"] == "relu"

    def test_get_network_topology_missing_activation_defaults_to_sigmoid(self):
        """Test get_network_topology uses sigmoid as default activation."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 3)
                network.output_bias = torch.randn(1)
                network.hidden_units = [{"weights": torch.randn(2), "bias": 0.5}]  # No activation_fn

                integration.network = network

                topology = integration.get_network_topology()

                # Should use default sigmoid
                assert topology["hidden_units"][0]["activation"] == "sigmoid"

    def test_get_network_topology_no_network_returns_none(self):
        """Test get_network_topology returns None when no network connected."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()
                integration.network = None

                topology = integration.get_network_topology()

                assert topology is None
                integration.logger.warning.assert_called_with("No network connected")

    def test_get_network_topology_handles_exception(self):
        """Test get_network_topology handles exceptions and returns None."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                # Network that raises exception
                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = MagicMock()
                network.output_weights.detach.side_effect = RuntimeError("Tensor error")

                integration.network = network

                topology = integration.get_network_topology()

                assert topology is None
                integration.logger.error.assert_called()

    def test_get_network_topology_tensor_serialization(self):
        """Test get_network_topology converts tensors to lists."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.tensor([[1.0, 2.0, 3.0]])
                network.output_bias = torch.tensor([0.5])
                network.hidden_units = [{"weights": torch.tensor([0.1, 0.2]), "bias": 0.3, "activation_fn": torch.sigmoid}]

                integration.network = network

                topology = integration.get_network_topology()

                # All tensors should be converted to lists
                assert isinstance(topology["output_weights"], list)
                assert isinstance(topology["output_bias"], list)
                assert isinstance(topology["hidden_units"][0]["weights"], list)
                assert isinstance(topology["hidden_units"][0]["bias"], float)

    def test_get_network_topology_thread_safe(self):
        """Test get_network_topology is thread-safe."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 2)
                network.output_bias = torch.randn(1)
                network.hidden_units = []

                integration.network = network

                results = []

                def extract_topology():
                    topology = integration.get_network_topology()
                    results.append(topology)

                # Run multiple threads extracting topology
                threads = [threading.Thread(target=extract_topology) for _ in range(5)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                # All should succeed
                assert len(results) == 5
                assert all(r is not None for r in results)

    def test_get_network_topology_empty_hidden_units(self):
        """Test get_network_topology with no hidden units (initial network)."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 2)
                network.output_bias = torch.randn(1)
                network.hidden_units = []

                integration.network = network

                topology = integration.get_network_topology()

                assert topology["hidden_units"] == []
                assert topology["input_size"] == 2
                assert topology["output_size"] == 1

    def test_extract_network_topology_alias(self):
        """Test extract_network_topology is an alias for get_network_topology."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 2)
                network.output_bias = torch.randn(1)
                network.hidden_units = []

                integration.network = network

                # Both methods should return the same result
                topology1 = integration.get_network_topology()
                topology2 = integration.extract_network_topology()

                assert topology1 == topology2

    def test_get_network_topology_with_malformed_unit(self):
        """Test get_network_topology handles malformed hidden units."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 2)
                network.output_bias = torch.randn(1)
                network.hidden_units = [{"weights": "invalid", "bias": 0.5}]  # Invalid weights

                integration.network = network

                # Should handle exception and return None
                topology = integration.get_network_topology()

                assert topology is None
                integration.logger.error.assert_called()

    def test_get_network_topology_gpu_tensors(self):
        """Test get_network_topology handles GPU tensors (if CUDA available)."""
        if not torch.cuda.is_available():
            pytest.skip("CUDA not available")

        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.topology_lock = threading.Lock()

                network = MagicMock()
                network.input_size = 2
                network.output_size = 1
                network.output_weights = torch.randn(1, 2).cuda()
                network.output_bias = torch.randn(1).cuda()
                network.hidden_units = []

                integration.network = network

                topology = integration.get_network_topology()

                # Should convert GPU tensors to CPU lists
                assert isinstance(topology["output_weights"], list)
                assert isinstance(topology["output_bias"], list)
