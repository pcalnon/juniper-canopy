#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Unified backend protocol for Cascade Correlation Neural Network monitoring frontend
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     protocol.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-02-26
# Last Modified: 2026-02-26
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Defines BackendProtocol — a typing.Protocol that captures the full set of
#     operations main.py calls on either DemoMode or CascorServiceAdapter.
#     Both DemoBackend and ServiceBackend implement this protocol, enabling
#     main.py to hold a single `backend: BackendProtocol` reference and
#     eliminating all if-demo/if-service branching.
#
#####################################################################################################################################################################################################
# Notes:
#     Phase 5 of the Microservices Architecture Development Roadmap.
#     See: juniper-ml/notes/MICROSERVICES-ARCHITECTURE_DEVELOPMENT-ROADMAP.md
#
#####################################################################################################################################################################################################
# References:
#     - PEP 544 — Protocols: Structural subtyping (static duck typing)
#     - juniper-ml/notes/MICROSERVICES-ARCHITECTURE_DEVELOPMENT-ROADMAP.md §5.4
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################

from typing import Any, Dict, List, Optional, Protocol, TypedDict, runtime_checkable

# ---------------------------------------------------------------------------
# TypedDict return types
# ---------------------------------------------------------------------------


class StatusResult(TypedDict, total=False):
    """Return type for get_status()."""

    is_training: bool
    is_running: bool
    is_paused: bool
    completed: bool
    failed: bool
    fsm_status: str
    phase: str
    current_epoch: int
    hidden_units: int
    network_connected: bool
    monitoring_active: bool
    input_size: int
    output_size: int
    learning_rate: float
    max_hidden_units: int
    max_epochs: int


class MetricsResult(TypedDict, total=False):
    """Return type for get_metrics()."""

    epoch: int
    loss: float
    accuracy: float
    learning_rate: float
    timestamp: str
    validation_loss: float
    validation_accuracy: float
    hidden_units: int
    cascade_phase: str
    train_loss: float
    train_accuracy: float
    val_loss: float
    val_accuracy: float


class TopologyResult(TypedDict, total=False):
    """Return type for get_network_topology()."""

    nodes: List[Dict[str, Any]]
    connections: List[Dict[str, Any]]
    input_units: int
    output_units: int
    hidden_units: int
    cascade_history: List[Dict[str, Any]]
    current_epoch: int
    hidden_units_count: int


class DatasetResult(TypedDict, total=False):
    """Return type for get_dataset()."""

    num_samples: int
    num_features: int
    num_classes: int
    inputs: Any
    targets: Any
    loaded: bool
    train_samples: int
    test_samples: int
    dataset_name: str


@runtime_checkable
class BackendProtocol(Protocol):
    """
    Unified backend interface for JuniperCanopy.

    Both DemoBackend and ServiceBackend implement this protocol.
    Route handlers in main.py call these methods without knowing
    which backend is active.
    """

    # --- Training control ---

    def start_training(self, reset: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """Start or restart training. Returns new training state."""
        ...

    def stop_training(self) -> Dict[str, Any]:
        """Stop training gracefully. Returns final state."""
        ...

    def pause_training(self) -> Dict[str, Any]:
        """Pause training (retaining state). Returns paused state."""
        ...

    def resume_training(self) -> Dict[str, Any]:
        """Resume paused training. Returns resumed state."""
        ...

    def reset_training(self) -> Dict[str, Any]:
        """Reset training to initial state. Returns reset state."""
        ...

    def is_training_active(self) -> bool:
        """Return True if training is currently in progress."""
        ...

    # --- Status and metrics ---

    def get_status(self) -> StatusResult:
        """Return current backend status (training state, phase, epoch, etc.)."""
        ...

    def get_metrics(self) -> MetricsResult:
        """Return current training metrics snapshot."""
        ...

    def get_metrics_history(self, count: int = 100) -> List[MetricsResult]:
        """Return recent training metrics history."""
        ...

    # --- Network and data ---

    def has_network(self) -> bool:
        """Return True if a neural network exists."""
        ...

    def get_network_topology(self) -> Optional[TopologyResult]:
        """Return network topology for visualization, or None."""
        ...

    def get_raw_topology(self) -> Optional[Dict[str, Any]]:
        """Return raw weight-oriented topology without graph transformation, or None."""
        ...

    def get_network_stats(self) -> Dict[str, Any]:
        """Return network statistics (weights, unit counts, etc.)."""
        ...

    def get_dataset(self) -> Optional[DatasetResult]:
        """Return current dataset info, or None."""
        ...

    def get_decision_boundary(self, resolution: int = 50) -> Optional[Dict[str, Any]]:
        """Return decision boundary grid data, or None if unavailable."""
        ...

    # --- Parameters ---

    def apply_params(self, **params: Any) -> Dict[str, Any]:
        """Apply training parameter changes. Returns updated params."""
        ...

    # --- Lifecycle ---

    async def initialize(self) -> bool:
        """Initialize the backend (connect, start simulation, etc.)."""
        ...

    async def shutdown(self) -> None:
        """Clean shutdown of the backend."""
        ...

    # --- Identity ---

    @property
    def backend_type(self) -> str:
        """Return 'demo' or 'service' for logging/status."""
        ...
