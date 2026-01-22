#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     data_adapter.py
# Author:        Paul Calnon
# Version:       0.1.5 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2026-01-22
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This module provides data adaptation functionalities to convert Cascade Correlation
#    Network data formats between the backend and frontend components.
#
#####################################################################################################################################################################################################
# Notes:
#
# Data Adapter Module
#
# Standardizes data formats between CasCor backend and frontend visualization components.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from .statistics import compute_weight_statistics


@dataclass
class TrainingMetrics:
    """Training metrics data structure."""

    epoch: int
    loss: float
    accuracy: float
    learning_rate: float
    timestamp: datetime
    validation_loss: Optional[float] = None
    validation_accuracy: Optional[float] = None
    hidden_units: int = 0
    cascade_phase: str = "output"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class NetworkNode:
    """Network node data structure."""

    id: str
    layer: int
    node_type: str  # 'input', 'hidden', 'output', 'cascade'
    position: Tuple[float, float]
    activation_function: str
    bias: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class NetworkConnection:
    """Network connection data structure."""

    source_id: str
    target_id: str
    weight: float
    connection_type: str  # 'feedforward', 'cascade'

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class NetworkTopology:
    """Complete network topology data structure."""

    nodes: List[NetworkNode]
    connections: List[NetworkConnection]
    cascade_history: List[Dict[str, Any]]
    current_epoch: int
    hidden_units_count: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "connections": [conn.to_dict() for conn in self.connections],
            "cascade_history": self.cascade_history,
            "current_epoch": self.current_epoch,
            "hidden_units_count": self.hidden_units_count,
        }


class DataAdapter:
    """
    Adapter for converting CasCor backend data to frontend-compatible formats.

    Handles:
    - Training metrics extraction and formatting
    - Network topology conversion
    - Dataset preparation for visualization
    - State serialization
    """

    def __init__(self):
        """Initialize data adapter."""
        self.logger = logging.getLogger(__name__)
        self._cached_topology = None
        self._cached_stats = None

    def extract_training_metrics(
        self,
        epoch: int,
        loss: float,
        accuracy: float,
        learning_rate: float,
        hidden_units: int = 0,
        cascade_phase: str = "output",
        validation_loss: Optional[float] = None,
        validation_accuracy: Optional[float] = None,
    ) -> TrainingMetrics:
        """
        Extract and format training metrics.

        Args:
            epoch: Current epoch number
            loss: Training loss value
            accuracy: Training accuracy value
            learning_rate: Current learning rate
            hidden_units: Number of hidden units
            cascade_phase: Current training phase
            validation_loss: Validation loss (optional)
            validation_accuracy: Validation accuracy (optional)

        Returns:
            TrainingMetrics object
        """
        return TrainingMetrics(
            epoch=epoch,
            loss=loss,
            accuracy=accuracy,
            learning_rate=learning_rate,
            timestamp=datetime.now(),
            validation_loss=(float(validation_loss) if validation_loss is not None else None),
            validation_accuracy=(float(validation_accuracy) if validation_accuracy is not None else None),
            hidden_units=hidden_units,
            cascade_phase=cascade_phase,
        )

    def convert_network_topology(
        self,
        input_weights: torch.Tensor,
        hidden_weights: Optional[torch.Tensor],
        output_weights: torch.Tensor,
        hidden_biases: Optional[torch.Tensor],
        output_biases: torch.Tensor,
        cascade_history: List[Dict[str, Any]],
        current_epoch: int,
    ) -> NetworkTopology:
        """
        Convert CasCor network structure to topology format.

        Args:
            input_weights: Input layer weights
            hidden_weights: Hidden layer weights (if any)
            output_weights: Output layer weights
            hidden_biases: Hidden layer biases (if any)
            output_biases: Output layer biases
            cascade_history: History of cascade additions
            current_epoch: Current training epoch

        Returns:
            NetworkTopology object
        """
        connections = []

        # Extract dimensions
        input_size = input_weights.shape[0]
        output_size = output_weights.shape[0]
        hidden_size = hidden_weights.shape[0] if hidden_weights is not None else 0

        # Create input nodes
        nodes = self.create_input_nodes(input_size=input_size, nodes=None)

        # Create hidden nodes (cascade units)
        nodes = self.create_hidden_nodes(hidden_size=hidden_size, hidden_biases=hidden_biases, nodes=nodes)

        # Create output nodes
        nodes = self.create_output_nodes(output_size=output_size, output_biases=output_biases, nodes=nodes)

        # Create connections from inputs to hidden units
        if hidden_size > 0 and hidden_weights is not None:
            for i in range(input_size):
                for h in range(hidden_size):
                    weight = float(hidden_weights[h, i].item())
                    connections.append(
                        NetworkConnection(
                            source_id=f"input_{i}", target_id=f"hidden_{h}", weight=weight, connection_type="cascade"
                        )
                    )

        # Create connections from inputs to outputs
        for i in range(input_size):
            for o in range(output_size):
                weight = float(input_weights[i, o].item())
                connections.append(
                    NetworkConnection(
                        source_id=f"input_{i}", target_id=f"output_{o}", weight=weight, connection_type="feedforward"
                    )
                )

        # Create connections from hidden to outputs
        if hidden_size > 0:
            for h in range(hidden_size):
                for o in range(output_size):
                    weight = float(output_weights[o, input_size + h].item())
                    connections.append(
                        NetworkConnection(
                            source_id=f"hidden_{h}",
                            target_id=f"output_{o}",
                            weight=weight,
                            connection_type="feedforward",
                        )
                    )

        return NetworkTopology(
            nodes=nodes,
            connections=connections,
            cascade_history=cascade_history,
            current_epoch=current_epoch,
            hidden_units_count=hidden_size,
        )

    # Create input nodes
    def create_input_nodes(self, input_size: int = None, nodes: list = None):
        if nodes is None:
            nodes = []
        # Add input nodes to the list
        nodes.extend(
            NetworkNode(
                id=f"input_{i}",
                layer=0,
                node_type="input",
                position=(i * 100, 0),
                activation_function="linear",
                bias=0.0,
            )
            for i in range(input_size)
        )
        return nodes

    # Create hidden nodes (cascade units)
    def create_hidden_nodes(
        self, hidden_size: int = None, hidden_biases: Optional[torch.Tensor] = None, nodes: list = None
    ):
        if nodes is None:
            nodes = []
        # Add hidden nodes to the list
        if hidden_size > 0:
            for i in range(hidden_size):
                bias = float(hidden_biases[i].item()) if hidden_biases is not None else 0.0
                nodes.append(
                    NetworkNode(
                        id=f"hidden_{i}",
                        layer=1,
                        node_type="cascade",
                        position=(i * 100, 200),
                        activation_function="sigmoid",
                        bias=bias,
                    )
                )
        return nodes

    # Create output nodes
    def create_output_nodes(
        self, output_size: int = None, output_biases: Optional[torch.Tensor] = None, nodes: list = None
    ):
        if nodes is None:
            nodes = []
        # Add output nodes to the list
        for i in range(output_size):
            bias = float(output_biases[i].item())
            nodes.append(
                NetworkNode(
                    id=f"output_{i}",
                    layer=2,
                    node_type="output",
                    position=(i * 100, 400),
                    activation_function="sigmoid",
                    bias=bias,
                )
            )
        return nodes

    def prepare_dataset_for_visualization(
        self, features: np.ndarray, labels: np.ndarray, dataset_name: str = "training"
    ) -> Dict[str, Any]:
        """
        Prepare dataset for visualization.

        Args:
            features: Feature array (N x D)
            labels: Label array (N,)
            dataset_name: Name of dataset

        Returns:
            Dictionary with visualization data
        """
        return {
            "name": dataset_name,
            "features": features.tolist() if isinstance(features, np.ndarray) else features,
            "labels": labels.tolist() if isinstance(labels, np.ndarray) else labels,
            "num_samples": len(features),
            "num_features": features.shape[1] if len(features.shape) > 1 else 1,
            "num_classes": len(np.unique(labels)),
        }

    def serialize_network_state(self, network_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize network state for transmission.

        Args:
            network_state: Raw network state dictionary

        Returns:
            Serialized state dictionary
        """
        serialized = {}

        for key, value in network_state.items():
            if isinstance(value, torch.Tensor):
                serialized[key] = value.cpu().detach().numpy().tolist()
            elif isinstance(value, np.ndarray):
                serialized[key] = value.tolist()
            elif isinstance(value, (int, float, str, bool, list, dict)):
                serialized[key] = value
            else:
                serialized[key] = str(value)

        return serialized

    def get_network_statistics(
        self,
        input_weights: Optional[torch.Tensor] = None,
        hidden_weights: Optional[torch.Tensor] = None,
        output_weights: Optional[torch.Tensor] = None,
        hidden_biases: Optional[torch.Tensor] = None,
        output_biases: Optional[torch.Tensor] = None,
        threshold_function: str = "sigmoid",
        optimizer_name: str = "sgd",
        topology: Optional[NetworkTopology] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive network statistics including weight statistics and metadata.

        Args:
            input_weights: Input layer weights
            hidden_weights: Hidden layer weights (optional)
            output_weights: Output layer weights
            hidden_biases: Hidden layer biases (optional)
            output_biases: Output layer biases (optional)
            threshold_function: Name of activation/threshold function
            optimizer_name: Name of optimizer
            topology: Pre-computed NetworkTopology object (optional)

        Returns:
            Dictionary containing comprehensive network statistics
        """
        # Collect all weights into single array
        all_weights = []

        if input_weights is not None:
            weights_np = (
                input_weights.cpu().detach().numpy()
                if isinstance(input_weights, torch.Tensor)
                else np.array(input_weights)
            )
            all_weights.append(weights_np.flatten())

        if hidden_weights is not None:
            weights_np = (
                hidden_weights.cpu().detach().numpy()
                if isinstance(hidden_weights, torch.Tensor)
                else np.array(hidden_weights)
            )
            all_weights.append(weights_np.flatten())

        if output_weights is not None:
            weights_np = (
                output_weights.cpu().detach().numpy()
                if isinstance(output_weights, torch.Tensor)
                else np.array(output_weights)
            )
            all_weights.append(weights_np.flatten())

        # Combine all weights
        combined_weights = np.concatenate(all_weights) if all_weights else np.array([])
        # Compute weight statistics
        weight_stats = compute_weight_statistics(combined_weights)

        # Compute node/edge counts
        total_nodes = 0
        total_edges = 0
        total_connections = 0

        if topology is not None:
            total_nodes = len(topology.nodes)
            total_connections = len(topology.connections)
            total_edges = total_connections
        else:
            # Estimate from weight matrices
            if input_weights is not None:
                input_size = input_weights.shape[0]
                output_size = input_weights.shape[1] if len(input_weights.shape) > 1 else 1
                total_nodes += input_size + output_size
                total_edges += input_size * output_size

            if hidden_weights is not None:
                hidden_size = hidden_weights.shape[0]
                total_nodes += hidden_size
                if input_weights is not None:
                    total_edges += input_size * hidden_size
                if output_weights is not None:
                    total_edges += hidden_size * output_size

            total_connections = total_edges

        # Compile comprehensive statistics
        stats = {
            "threshold_function": threshold_function,
            "optimizer": optimizer_name,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_connections": total_connections,
            "weight_statistics": weight_stats,
        }

        # Cache for performance
        self._cached_stats = stats

        return stats

    def invalidate_stats_cache(self):
        """Invalidate cached statistics (call when topology changes)."""
        self._cached_stats = None
        self._cached_topology = None

    def normalize_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Cascor backend metrics to Canopy frontend format.

        Handles key naming differences between applications:
        - Cascor uses 'value_loss'/'value_accuracy'
        - Canopy expects 'val_loss'/'val_accuracy'

        Also handles legacy formats where 'loss' and 'accuracy' may be
        provided without 'train_' prefix.

        Args:
            raw_metrics: Raw metrics dictionary from Cascor backend

        Returns:
            Normalized metrics dictionary for Canopy frontend

        Example:
            raw = {'epoch': 5, 'value_loss': 0.3, 'value_accuracy': 0.9}
            normalized = adapter.normalize_metrics(raw)
            # Returns: {'epoch': 5, 'val_loss': 0.3, 'val_accuracy': 0.9}
        """
        if raw_metrics is None:
            return {}

        normalized = {}

        # Key mapping from Cascor format to Canopy format
        key_mapping = {
            # Cascor 'value_' prefix → Canopy 'val_' prefix
            "value_loss": "val_loss",
            "value_accuracy": "val_accuracy",
            # Legacy format: bare 'loss'/'accuracy' → 'train_loss'/'train_accuracy'
            "loss": "train_loss",
            "accuracy": "train_accuracy",
        }

        for key, value in raw_metrics.items():
            # Apply key mapping if applicable
            normalized_key = key_mapping.get(key, key)

            # Skip if we already have the normalized version (avoid overwriting)
            # e.g., if both 'train_loss' and 'loss' are present, keep 'train_loss'
            if normalized_key in normalized and key in key_mapping:
                continue

            normalized[normalized_key] = value

        return normalized

    def denormalize_metrics(self, normalized_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Canopy frontend metrics back to Cascor backend format.

        Inverse of normalize_metrics() for bidirectional communication.

        Args:
            normalized_metrics: Normalized metrics dictionary from Canopy frontend

        Returns:
            Denormalized metrics dictionary for Cascor backend
        """
        if normalized_metrics is None:
            return {}

        denormalized = {}

        # Reverse key mapping: Canopy format → Cascor format
        key_mapping = {
            "val_loss": "value_loss",
            "val_accuracy": "value_accuracy",
        }

        for key, value in normalized_metrics.items():
            denormalized_key = key_mapping.get(key, key)
            denormalized[denormalized_key] = value

        return denormalized
