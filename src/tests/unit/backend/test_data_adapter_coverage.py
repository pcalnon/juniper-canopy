#!/usr/bin/env python
"""
Comprehensive coverage tests for data_adapter.py
Target: Raise coverage from 54% to 80%+

Tests cover:
- DataAdapter initialization
- Training metrics extraction
- Network topology conversion
- Dataset preparation for visualization
- State serialization
- Statistics computation
- Type coercion (floats, ints, strings)
- Missing value handling
- Edge cases
"""
import numpy as np
import pytest  # noqa: F401 - needed for pytest fixtures
import torch


class TestDataAdapterInit:
    """Test DataAdapter initialization."""

    def test_init_creates_instance(self):
        """Test basic initialization."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        assert adapter is not None
        assert adapter._cached_topology is None
        assert adapter._cached_stats is None


class TestTrainingMetricsExtraction:
    """Test training metrics extraction and formatting."""

    def test_extract_training_metrics_minimal(self):
        """Test extracting metrics with minimal parameters."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        metrics = adapter.extract_training_metrics(epoch=10, loss=0.5, accuracy=0.9, learning_rate=0.01)

        assert metrics.epoch == 10
        assert metrics.loss == 0.5
        assert metrics.accuracy == 0.9
        assert metrics.learning_rate == 0.01
        assert metrics.hidden_units == 0
        assert metrics.cascade_phase == "output"

    def test_extract_training_metrics_with_validation(self):
        """Test extracting metrics with validation data."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        metrics = adapter.extract_training_metrics(epoch=5, loss=0.3, accuracy=0.85, learning_rate=0.02, validation_loss=0.4, validation_accuracy=0.82)

        assert metrics.validation_loss == 0.4
        assert metrics.validation_accuracy == 0.82

    def test_extract_training_metrics_with_cascade_info(self):
        """Test extracting metrics with cascade phase info."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        metrics = adapter.extract_training_metrics(epoch=20, loss=0.2, accuracy=0.95, learning_rate=0.01, hidden_units=5, cascade_phase="candidate")

        assert metrics.hidden_units == 5
        assert metrics.cascade_phase == "candidate"

    def test_training_metrics_to_dict(self):
        """Test converting training metrics to dictionary."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        metrics = adapter.extract_training_metrics(epoch=1, loss=1.0, accuracy=0.5, learning_rate=0.01)

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert "epoch" in result
        assert "loss" in result
        assert "timestamp" in result
        assert isinstance(result["timestamp"], str)  # ISO format


class TestNetworkTopologyConversion:
    """Test network topology conversion."""

    def test_convert_network_topology_simple(self):
        """Test converting simple network topology."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        # Simple network: 2 inputs -> 1 output
        input_weights = torch.randn(2, 1)
        output_weights = torch.randn(1, 2)
        output_biases = torch.randn(1)

        topology = adapter.convert_network_topology(
            input_weights=input_weights,
            hidden_weights=None,
            output_weights=output_weights,
            hidden_biases=None,
            output_biases=output_biases,
            cascade_history=[],
            current_epoch=0,
        )

        assert topology.current_epoch == 0
        assert topology.hidden_units_count == 0
        assert len(topology.nodes) > 0
        assert len(topology.connections) > 0

    def test_convert_network_topology_with_hidden_units(self):
        """Test converting topology with hidden units."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        # Network: 2 inputs -> 3 hidden -> 1 output
        input_weights = torch.randn(2, 1)
        hidden_weights = torch.randn(3, 2)
        output_weights = torch.randn(1, 5)  # 2 inputs + 3 hidden
        hidden_biases = torch.randn(3)
        output_biases = torch.randn(1)

        topology = adapter.convert_network_topology(
            input_weights=input_weights,
            hidden_weights=hidden_weights,
            output_weights=output_weights,
            hidden_biases=hidden_biases,
            output_biases=output_biases,
            cascade_history=[{"epoch": 10, "unit_id": 0}],
            current_epoch=15,
        )

        assert topology.hidden_units_count == 3
        assert topology.current_epoch == 15
        assert len(topology.cascade_history) == 1

    def test_convert_network_topology_to_dict(self):
        """Test converting topology to dictionary."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        input_weights = torch.randn(2, 1)
        output_weights = torch.randn(1, 2)
        output_biases = torch.randn(1)

        topology = adapter.convert_network_topology(
            input_weights=input_weights,
            hidden_weights=None,
            output_weights=output_weights,
            hidden_biases=None,
            output_biases=output_biases,
            cascade_history=[],
            current_epoch=5,
        )

        result = topology.to_dict()

        assert isinstance(result, dict)
        assert "nodes" in result
        assert "connections" in result
        assert "cascade_history" in result
        assert "current_epoch" in result


class TestNodeCreation:
    """Test node creation methods."""

    def test_create_input_nodes(self):
        """Test creating input nodes."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        nodes = adapter.create_input_nodes(input_size=3)

        assert len(nodes) == 3
        assert all(node.node_type == "input" for node in nodes)
        assert all(node.layer == 0 for node in nodes)

    def test_create_hidden_nodes(self):
        """Test creating hidden nodes."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        hidden_biases = torch.randn(4)
        nodes = adapter.create_hidden_nodes(hidden_size=4, hidden_biases=hidden_biases)

        assert len(nodes) == 4
        assert all(node.node_type == "cascade" for node in nodes)
        assert all(node.layer == 1 for node in nodes)

    def test_create_hidden_nodes_without_biases(self):
        """Test creating hidden nodes without biases."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        nodes = adapter.create_hidden_nodes(hidden_size=2, hidden_biases=None)

        assert len(nodes) == 2
        assert all(node.bias == 0.0 for node in nodes)

    def test_create_output_nodes(self):
        """Test creating output nodes."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        output_biases = torch.randn(2)
        nodes = adapter.create_output_nodes(output_size=2, output_biases=output_biases)

        assert len(nodes) == 2
        assert all(node.node_type == "output" for node in nodes)
        assert all(node.layer == 2 for node in nodes)


class TestDatasetPreparation:
    """Test dataset preparation for visualization."""

    def test_prepare_dataset_numpy_arrays(self):
        """Test preparing dataset with numpy arrays."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        features = np.random.randn(100, 2)
        labels = np.random.randint(0, 2, 100)

        result = adapter.prepare_dataset_for_visualization(features, labels, "training")

        assert result["dataset_name"] == "training"
        assert result["num_samples"] == 100
        assert result["num_features"] == 2
        assert result["num_classes"] == 2
        assert isinstance(result["inputs"], list)
        assert isinstance(result["targets"], list)

    def test_prepare_dataset_with_lists(self):
        """Test preparing dataset with Python lists."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        features = [[0, 0], [1, 1], [2, 2]]
        labels = [0, 1, 0]

        result = adapter.prepare_dataset_for_visualization(np.array(features), np.array(labels), "test")

        assert result["dataset_name"] == "test"
        assert result["num_samples"] == 3

    def test_prepare_dataset_1d_features(self):
        """Test preparing dataset with 1D features."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        features = np.random.randn(50)
        labels = np.random.randint(0, 2, 50)

        result = adapter.prepare_dataset_for_visualization(features, labels, "1d_data")

        assert result["num_features"] == 1

    def test_prepare_dataset_multi_class(self):
        """Test preparing dataset with multiple classes."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        features = np.random.randn(60, 3)
        labels = np.random.randint(0, 5, 60)  # 5 classes

        result = adapter.prepare_dataset_for_visualization(features, labels)

        assert result["num_classes"] == 5


class TestStateSerialization:
    """Test network state serialization."""

    def test_serialize_network_state_with_tensors(self):
        """Test serializing state with torch tensors."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        state = {"weights": torch.randn(3, 2), "bias": torch.randn(3), "epoch": 10}

        result = adapter.serialize_network_state(state)

        assert isinstance(result["weights"], list)
        assert isinstance(result["bias"], list)
        assert result["epoch"] == 10

    def test_serialize_network_state_with_numpy(self):
        """Test serializing state with numpy arrays."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        state = {"data": np.array([[1, 2], [3, 4]]), "count": 5}

        result = adapter.serialize_network_state(state)

        assert isinstance(result["data"], list)
        assert result["count"] == 5

    def test_serialize_network_state_with_mixed_types(self):
        """Test serializing state with mixed data types."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        state = {
            "tensor": torch.randn(2, 2),
            "array": np.array([1, 2, 3]),
            "int": 42,
            "float": 3.14,
            "string": "test",
            "bool": True,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
        }

        result = adapter.serialize_network_state(state)

        assert isinstance(result["tensor"], list)
        assert isinstance(result["array"], list)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["string"] == "test"
        assert result["bool"] is True

    def test_serialize_network_state_with_unsupported_type(self):
        """Test serializing state with unsupported type."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        class CustomClass:
            pass

        state = {"custom": CustomClass(), "normal": 123}

        result = adapter.serialize_network_state(state)

        # Unsupported type should be converted to string
        assert isinstance(result["custom"], str)
        assert result["normal"] == 123


class TestNetworkStatistics:
    """Test network statistics computation."""

    def test_get_network_statistics_simple(self):
        """Test getting statistics for simple network."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        input_weights = torch.randn(2, 1)
        output_weights = torch.randn(1, 2)

        stats = adapter.get_network_statistics(
            input_weights=input_weights,
            output_weights=output_weights,
            threshold_function="sigmoid",
            optimizer_name="adam",
        )

        assert "threshold_function" in stats
        assert stats["threshold_function"] == "sigmoid"
        assert stats["optimizer"] == "adam"
        assert "weight_statistics" in stats

    def test_get_network_statistics_with_hidden_units(self):
        """Test getting statistics with hidden units."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        input_weights = torch.randn(3, 2)
        hidden_weights = torch.randn(4, 3)
        output_weights = torch.randn(2, 7)

        stats = adapter.get_network_statistics(input_weights=input_weights, hidden_weights=hidden_weights, output_weights=output_weights)

        assert "weight_statistics" in stats
        assert "total_nodes" in stats
        assert "total_edges" in stats

    def test_get_network_statistics_with_topology(self):
        """Test getting statistics with pre-computed topology."""
        from backend.data_adapter import DataAdapter, NetworkConnection, NetworkNode, NetworkTopology

        adapter = DataAdapter()

        # Create mock topology
        nodes = [
            NetworkNode("input_0", 0, "input", (0, 0), "linear", 0.0),
            NetworkNode("input_1", 0, "input", (1, 0), "linear", 0.0),
            NetworkNode("output_0", 2, "output", (0, 2), "sigmoid", 0.1),
        ]
        connections = [
            NetworkConnection("input_0", "output_0", 0.5, "feedforward"),
            NetworkConnection("input_1", "output_0", -0.3, "feedforward"),
        ]
        topology = NetworkTopology(nodes, connections, [], 0, 0)

        input_weights = torch.randn(2, 1)
        output_weights = torch.randn(1, 2)

        stats = adapter.get_network_statistics(input_weights=input_weights, output_weights=output_weights, topology=topology)

        assert stats["total_nodes"] == 3
        assert stats["total_connections"] == 2

    def test_invalidate_stats_cache(self):
        """Test invalidating statistics cache."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        # Set some cached values
        adapter._cached_stats = {"test": "data"}
        adapter._cached_topology = {"topology": "data"}

        adapter.invalidate_stats_cache()

        assert adapter._cached_stats is None
        assert adapter._cached_topology is None


class TestDataStructures:
    """Test data structure classes."""

    def test_network_node_to_dict(self):
        """Test NetworkNode to_dict conversion."""
        from backend.data_adapter import NetworkNode

        node = NetworkNode(id="test_node", layer=1, node_type="hidden", position=(10, 20), activation_function="relu", bias=0.5)

        result = node.to_dict()

        assert isinstance(result, dict)
        assert result["id"] == "test_node"
        assert result["layer"] == 1
        assert result["bias"] == 0.5

    def test_network_connection_to_dict(self):
        """Test NetworkConnection to_dict conversion."""
        from backend.data_adapter import NetworkConnection

        conn = NetworkConnection(source_id="node_1", target_id="node_2", weight=0.75, connection_type="feedforward")

        result = conn.to_dict()

        assert isinstance(result, dict)
        assert result["source_id"] == "node_1"
        assert result["target_id"] == "node_2"
        assert result["weight"] == 0.75


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_convert_topology_with_zero_sized_network(self):
        """Test converting topology with zero-sized components."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        # Minimal network
        input_weights = torch.randn(1, 1)
        output_weights = torch.randn(1, 1)
        output_biases = torch.randn(1)

        topology = adapter.convert_network_topology(
            input_weights=input_weights,
            hidden_weights=None,
            output_weights=output_weights,
            hidden_biases=None,
            output_biases=output_biases,
            cascade_history=[],
            current_epoch=0,
        )

        assert topology is not None

    def test_extract_metrics_with_none_validation(self):
        """Test extracting metrics with None validation values."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        metrics = adapter.extract_training_metrics(epoch=1, loss=0.5, accuracy=0.8, learning_rate=0.01, validation_loss=None, validation_accuracy=None)

        assert metrics.validation_loss is None
        assert metrics.validation_accuracy is None

    def test_prepare_dataset_empty_arrays(self):
        """Test preparing dataset with empty arrays."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        features = np.array([]).reshape(0, 2)
        labels = np.array([])

        result = adapter.prepare_dataset_for_visualization(features, labels)

        assert result["num_samples"] == 0

    def test_serialize_empty_state(self):
        """Test serializing empty state."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        state = {}

        result = adapter.serialize_network_state(state)

        assert result == {}

    def test_create_nodes_with_zero_size(self):
        """Test creating nodes with zero size."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        nodes = adapter.create_input_nodes(input_size=0)

        assert len(nodes) == 0

    def test_get_statistics_with_no_weights(self):
        """Test getting statistics with no weights."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        stats = adapter.get_network_statistics()

        assert "weight_statistics" in stats
        # Should handle empty weights gracefully

    def test_network_topology_large_cascade_history(self):
        """Test topology with large cascade history."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()

        input_weights = torch.randn(2, 1)
        output_weights = torch.randn(1, 2)
        output_biases = torch.randn(1)

        # Large cascade history
        cascade_history = [{"epoch": i, "unit_id": i} for i in range(100)]

        topology = adapter.convert_network_topology(
            input_weights=input_weights,
            hidden_weights=None,
            output_weights=output_weights,
            hidden_biases=None,
            output_biases=output_biases,
            cascade_history=cascade_history,
            current_epoch=100,
        )

        assert len(topology.cascade_history) == 100
