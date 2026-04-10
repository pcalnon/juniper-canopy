#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       BackendProtocol adapter wrapping DemoMode for demo/development usage
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     demo_backend.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-02-26
# Last Modified: 2026-02-26
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     DemoBackend wraps the existing DemoMode class, adapting its interface to
#     BackendProtocol. This is a thin adapter — all operations delegate directly
#     to DemoMode with no data copying or additional overhead.
#
#####################################################################################################################################################################################################
# Notes:
#     Phase 5 of the Microservices Architecture Development Roadmap.
#     No changes to demo_mode.py are required — DemoBackend is purely an adapter.
#
#####################################################################################################################################################################################################
# References:
#     - juniper-ml/notes/MICROSERVICES-ARCHITECTURE_DEVELOPMENT-ROADMAP.md §5.5
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################

import logging
from typing import Any, List, Optional, cast

import numpy as np
import torch

from backend.protocol import (
    ApplyParamsResult,
    ControlResult,
    DatasetResult,
    DecisionBoundaryResult,
    MetricsResult,
    NetworkStatsResult,
    RawTopologyResult,
    StatusResult,
    TopologyResult,
)
from demo_mode import DemoMode

logger = logging.getLogger("juniper_canopy.backend.demo_backend")


class DemoBackend:
    """BackendProtocol implementation wrapping DemoMode."""

    def __init__(self, demo: DemoMode):
        self._demo = demo

    @property
    def backend_type(self) -> str:
        return "demo"

    # --- Training control ---

    def start_training(self, reset: bool = True, **kwargs: Any) -> ControlResult:
        return cast(ControlResult, self._demo.start(reset=reset))

    def stop_training(self) -> ControlResult:
        self._demo.stop()
        return cast(ControlResult, self._demo.get_current_state())

    def pause_training(self) -> ControlResult:
        self._demo.pause()
        return cast(ControlResult, self._demo.get_current_state())

    def resume_training(self) -> ControlResult:
        self._demo.resume()
        return cast(ControlResult, self._demo.get_current_state())

    def reset_training(self) -> ControlResult:
        return cast(ControlResult, self._demo.reset())

    def is_training_active(self) -> bool:
        return bool(self._demo.get_current_state().get("is_running", False))

    # --- Status and metrics ---

    def get_status(self) -> StatusResult:
        state = self._demo.get_current_state()
        network = self._demo.get_network()
        fsm = self._demo.state_machine.get_state_summary()
        status_name = fsm["status"]
        state.update(
            {
                "is_training": status_name == "STARTED",
                "is_running": status_name == "STARTED",
                "is_paused": status_name == "PAUSED",
                "completed": status_name == "COMPLETED",
                "failed": status_name == "FAILED",
                "fsm_status": status_name,
                "phase": fsm["phase"].lower(),
                "network_connected": True,
                "monitoring_active": status_name == "STARTED",
                "input_size": network.input_size if network else 0,
                "output_size": network.output_size if network else 0,
            }
        )
        # Include training params from training_state if available
        if hasattr(self._demo, "training_state") and self._demo.training_state:
            ts = self._demo.training_state.get_state()
            for k in ("learning_rate", "max_hidden_units", "max_epochs", "status", "phase"):
                if k in ts and k not in state:
                    state[k] = ts[k]
        return cast(StatusResult, state)

    def get_metrics(self) -> MetricsResult:
        return cast(MetricsResult, self._demo.get_current_state())

    def get_metrics_history(self, count: int = 100) -> List[MetricsResult]:
        history = self._demo.get_metrics_history()
        if count and len(history) > count:
            return cast(List[MetricsResult], history[-count:])
        return cast(List[MetricsResult], history)

    # --- Network and data ---

    def has_network(self) -> bool:
        return self._demo.get_network() is not None

    def get_network_topology(self) -> Optional[TopologyResult]:
        network = self._demo.get_network()
        if network is None:
            return None

        nodes = []
        connections = []

        # Input nodes
        for i in range(network.input_size):
            nodes.append({"id": f"input_{i}", "type": "input", "layer": 0})

        # Hidden nodes with cascade connections
        for i, unit in enumerate(network.hidden_units):
            nodes.append({"id": f"hidden_{i}", "type": "hidden", "layer": 1})
            weights = unit["weights"]
            w_idx = 0
            # Connections from inputs to hidden
            for j in range(network.input_size):
                weight = weights[w_idx].item() if w_idx < len(weights) else 0.0
                connections.append({"from": f"input_{j}", "to": f"hidden_{i}", "weight": weight})
                w_idx += 1
            # Cascade connections from prior hidden units
            for prior_h in range(i):
                weight = weights[w_idx].item() if w_idx < len(weights) else 0.0
                connections.append({"from": f"hidden_{prior_h}", "to": f"hidden_{i}", "weight": weight})
                w_idx += 1

        # Output nodes
        for i in range(network.output_size):
            nodes.append({"id": f"output_{i}", "type": "output", "layer": 2})
            # Connections from inputs to output
            output_weight = network.output_layer.weight.data
            for j in range(network.input_size):
                weight = output_weight[i, j].item() if j < output_weight.shape[1] else 0.0
                connections.append({"from": f"input_{j}", "to": f"output_{i}", "weight": weight})
            # Connections from hidden to output
            for h_idx in range(len(network.hidden_units)):
                col = network.input_size + h_idx
                weight = output_weight[i, col].item() if col < output_weight.shape[1] else 0.0
                connections.append({"from": f"hidden_{h_idx}", "to": f"output_{i}", "weight": weight})

        return {
            "nodes": nodes,
            "connections": connections,
            "input_units": network.input_size,
            "output_units": network.output_size,
            "hidden_units": len(network.hidden_units),
        }

    def get_raw_topology(self) -> Optional[RawTopologyResult]:
        """Get raw weight-oriented topology matching CasCor's native format."""
        network = self._demo.get_network()
        if network is None:
            return None

        hidden_units = []
        for unit in network.hidden_units:
            hidden_units.append(
                {
                    "weights": [w.item() for w in unit["weights"]],
                    "bias": unit.get("bias", 0.0),
                    "activation": unit.get("activation", "sigmoid"),
                }
            )

        output_weight = network.output_layer.weight.data
        num_inputs_plus_hidden = network.input_size + len(network.hidden_units)
        output_weights = []
        for col in range(num_inputs_plus_hidden):
            col_weights = []
            for row in range(network.output_size):
                w = output_weight[row, col].item() if col < output_weight.shape[1] else 0.0
                col_weights.append(w)
            output_weights.append(col_weights)

        output_bias = []
        if hasattr(network.output_layer, "bias") and network.output_layer.bias is not None:
            output_bias = [b.item() for b in network.output_layer.bias.data]

        return cast(
            RawTopologyResult,
            {
                "input_size": network.input_size,
                "output_size": network.output_size,
                "hidden_units": hidden_units,
                "output_weights": output_weights,
                "output_bias": output_bias,
            },
        )

    def get_network_stats(self) -> NetworkStatsResult:
        network = self._demo.get_network()
        state = self._demo.get_current_state()
        return cast(
            NetworkStatsResult,
            {
                "hidden_units": len(network.hidden_units) if network else 0,
                "current_epoch": state.get("current_epoch", 0),
                "input_size": network.input_size if network else 0,
                "output_size": network.output_size if network else 0,
                **state,
            },
        )

    def get_dataset(self) -> Optional[DatasetResult]:
        dataset = self._demo.get_dataset()
        if dataset is None:
            return None
        # Return JSON-serializable subset
        result = {
            "num_samples": dataset.get("num_samples", 0),
            "num_features": dataset.get("num_features", 0),
            "num_classes": dataset.get("num_classes", 0),
        }
        # Include numpy arrays as lists for REST responses
        if "inputs" in dataset and dataset["inputs"] is not None:
            inputs = dataset["inputs"]
            targets = dataset.get("targets")
            result["inputs"] = inputs.tolist() if isinstance(inputs, np.ndarray) else inputs
            if targets is not None:
                result["targets"] = targets.tolist() if isinstance(targets, np.ndarray) else targets
        # Include dataset versioning metadata when available
        if "dataset_name" in dataset:
            result["dataset_name"] = dataset["dataset_name"]
        if "dataset_version" in dataset:
            result["dataset_version"] = dataset["dataset_version"]
        return cast(DatasetResult, result)

    def regenerate_dataset(self, n_samples: int = 200, n_spirals: int = 2, noise: float = 0.1, n_rotations: float = 1.5) -> Optional[DatasetResult]:
        """Regenerate the dataset with new parameters."""
        self._demo.regenerate_dataset(n_samples=n_samples, n_spirals=n_spirals, noise=noise, n_rotations=n_rotations)
        return self.get_dataset()

    def get_decision_boundary(self, resolution: int = 50) -> Optional[DecisionBoundaryResult]:
        network = self._demo.get_network()
        if network is None:
            return None

        dataset = self._demo.get_dataset()
        if dataset is None or "inputs" not in dataset:
            return None

        inputs = dataset["inputs"]
        x_min, x_max = float(inputs[:, 0].min()) - 0.5, float(inputs[:, 0].max()) + 0.5
        y_min, y_max = float(inputs[:, 1].min()) - 0.5, float(inputs[:, 1].max()) + 0.5

        xx = np.linspace(x_min, x_max, resolution)
        yy = np.linspace(y_min, y_max, resolution)
        grid_x, grid_y = np.meshgrid(xx, yy)
        grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()]).astype(np.float32)

        with self._demo._lock, torch.no_grad():
            grid_tensor = torch.from_numpy(grid_points).float()
            grid_tensor = network.normalize_inputs(grid_tensor)
            predictions = network.forward(grid_tensor)
            # Apply threshold for binary class labels (matching real CasCor argmax)
            z = (predictions > 0.5).int().numpy().flatten()

        return cast(
            DecisionBoundaryResult,
            {
                "xx": grid_x.tolist(),
                "yy": grid_y.tolist(),
                "Z": z.reshape(resolution, resolution).tolist(),
                "x_min": x_min,
                "x_max": x_max,
                "y_min": y_min,
                "y_max": y_max,
                "resolution": resolution,
            },
        )

    # --- Parameters ---

    def apply_params(self, **params: Any) -> ApplyParamsResult:
        self._demo.apply_params(**params)
        return cast(ApplyParamsResult, {"ok": True, "data": params})

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        self._demo.start()
        logger.info("DemoBackend initialized and started")
        return True

    async def shutdown(self) -> None:
        self._demo.stop()
        logger.info("DemoBackend shut down")
