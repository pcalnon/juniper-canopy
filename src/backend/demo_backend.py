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
from typing import Any, Dict, List, Optional

import numpy as np
import torch

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

    def start_training(self, reset: bool = True, **kwargs: Any) -> Dict[str, Any]:
        return self._demo.start(reset=reset)

    def stop_training(self) -> Dict[str, Any]:
        self._demo.stop()
        return self._demo.get_current_state()

    def pause_training(self) -> Dict[str, Any]:
        self._demo.pause()
        return self._demo.get_current_state()

    def resume_training(self) -> Dict[str, Any]:
        self._demo.resume()
        return self._demo.get_current_state()

    def reset_training(self) -> Dict[str, Any]:
        return self._demo.reset()

    def is_training_active(self) -> bool:
        return self._demo.get_current_state().get("is_running", False)

    # --- Status and metrics ---

    def get_status(self) -> Dict[str, Any]:
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
        return state

    def get_metrics(self) -> Dict[str, Any]:
        return self._demo.get_current_state()

    def get_metrics_history(self, count: int = 100) -> List[Dict[str, Any]]:
        history = self._demo.get_metrics_history()
        if count and len(history) > count:
            return history[-count:]
        return history

    # --- Network and data ---

    def has_network(self) -> bool:
        return self._demo.get_network() is not None

    def get_network_topology(self) -> Optional[Dict[str, Any]]:
        network = self._demo.get_network()
        if network is None:
            return None

        nodes = []
        connections = []

        # Input nodes
        for i in range(network.input_size):
            nodes.append({"id": f"input_{i}", "type": "input", "layer": 0})

        # Hidden nodes
        for i, unit in enumerate(network.hidden_units):
            nodes.append({"id": f"hidden_{i}", "type": "hidden", "layer": 1})
            # Connections from inputs to hidden
            for j in range(network.input_size):
                weight = unit["weights"][j].item() if j < len(unit["weights"]) else 0.0
                connections.append({"from": f"input_{j}", "to": f"hidden_{i}", "weight": weight})

        # Output nodes
        for i in range(network.output_size):
            nodes.append({"id": f"output_{i}", "type": "output", "layer": 2})
            # Connections from inputs to output
            for j in range(network.input_size):
                weight = network.output_weights[i, j].item() if j < network.output_weights.shape[1] else 0.0
                connections.append({"from": f"input_{j}", "to": f"output_{i}", "weight": weight})
            # Connections from hidden to output
            for h_idx in range(len(network.hidden_units)):
                col = network.input_size + h_idx
                weight = network.output_weights[i, col].item() if col < network.output_weights.shape[1] else 0.0
                connections.append({"from": f"hidden_{h_idx}", "to": f"output_{i}", "weight": weight})

        return {
            "nodes": nodes,
            "connections": connections,
            "input_size": network.input_size,
            "output_size": network.output_size,
            "hidden_units": len(network.hidden_units),
        }

    def get_network_stats(self) -> Dict[str, Any]:
        network = self._demo.get_network()
        state = self._demo.get_current_state()
        return {
            "hidden_units": len(network.hidden_units) if network else 0,
            "current_epoch": state.get("current_epoch", 0),
            "input_size": network.input_size if network else 0,
            "output_size": network.output_size if network else 0,
            **state,
        }

    def get_dataset(self) -> Optional[Dict[str, Any]]:
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
        return result

    def get_decision_boundary(self, resolution: int = 50) -> Optional[Dict[str, Any]]:
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

        with torch.no_grad():
            grid_tensor = torch.from_numpy(grid_points).float()
            predictions = network.forward(grid_tensor)
            z = predictions.numpy().flatten()

        return {
            "x": xx.tolist(),
            "y": yy.tolist(),
            "z": z.reshape(resolution, resolution).tolist(),
            "x_min": x_min,
            "x_max": x_max,
            "y_min": y_min,
            "y_max": y_max,
            "resolution": resolution,
        }

    # --- Parameters ---

    def apply_params(self, **params: Any) -> Dict[str, Any]:
        self._demo.apply_params(
            learning_rate=params.get("learning_rate"),
            max_hidden_units=params.get("max_hidden_units"),
            max_epochs=params.get("max_epochs"),
        )
        return params

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        self._demo.start()
        logger.info("DemoBackend initialized and started")
        return True

    async def shutdown(self) -> None:
        self._demo.stop()
        logger.info("DemoBackend shut down")
