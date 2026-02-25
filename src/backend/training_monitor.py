#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     training_monitor.py
# Author:        Paul Calnon
# Version:       0.2.0
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This script monitors the training process of the CasCor model, collecting metrics and
#    providing real-time feedback on the training state. Includes TrainingState class for
#    thread-safe state management.
#
#####################################################################################################################################################################################################
# Notes:
#
#     Training Monitor Module
#
#     Interfaces with CasCor training process to collect metrics, state changes,
#     and progress information in real-time.
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
import json
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .data_adapter import DataAdapter, NetworkTopology, TrainingMetrics


class CandidatePool:
    """
    Tracks candidate pool state during candidate training phase.

    Manages candidate units being trained and evaluated for addition to network.
    Thread-safe with internal locking.
    """

    def __init__(self):
        """Initialize candidate pool."""
        self.__lock: Any = threading.Lock()
        self.__status: str = "Inactive"
        self.__phase: str = "Idle"
        self.__size: int = 0
        self.__candidates: List[Dict[str, Any]] = []
        self.__iterations: int = 0
        self.__start_time: Optional[float] = None
        self.__progress: float = 0.0
        self.__target: float = 0.0

    def update_pool(
        self,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        size: Optional[int] = None,
        iterations: Optional[int] = None,
        progress: Optional[float] = None,
        target: Optional[float] = None,
    ) -> None:
        """
        Update pool state atomically.

        Args:
            status: Pool status ("Active", "Inactive")
            phase: Training phase ("Training", "Evaluating", "Selecting")
            size: Number of candidates in pool
            iterations: Training iterations completed
            progress: Training progress (0.0-1.0)
            target: Target metric value
        """
        with self.__lock:
            if status is not None:
                self.__status = status
                if status == "Active" and self.__start_time is None:
                    self.__start_time = time.time()
                elif status == "Inactive":
                    self.__start_time = None
            if phase is not None:
                self.__phase = phase
            if size is not None:
                self.__size = size
            if iterations is not None:
                self.__iterations = iterations
            if progress is not None:
                self.__progress = progress
            if target is not None:
                self.__target = target

    def add_candidate(
        self,
        candidate_id: str,
        name: str,
        correlation: float = 0.0,
        loss: float = 0.0,
        accuracy: float = 0.0,
        precision: float = 0.0,
        recall: float = 0.0,
        f1_score: float = 0.0,
    ) -> None:
        """
        Add or update candidate in pool.

        Args:
            candidate_id: Unique candidate identifier
            name: Candidate name/descriptor
            correlation: Correlation score
            loss: Training loss
            accuracy: Training accuracy
            precision: Precision metric
            recall: Recall metric
            f1_score: F1 score
        """
        with self.__lock:
            candidate = {
                "id": candidate_id,
                "name": name,
                "correlation": correlation,
                "loss": loss,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
            }

            # Update existing or append new
            for i, c in enumerate(self.__candidates):
                if c["id"] == candidate_id:
                    self.__candidates[i] = candidate
                    return
            self.__candidates.append(candidate)

    def get_top_n_candidates(self, n: int = 2) -> List[Dict[str, Any]]:
        """
        Get top N candidates by correlation score.

        Args:
            n: Number of top candidates to return

        Returns:
            List of top N candidate dictionaries
        """
        with self.__lock:
            sorted_candidates = sorted(self.__candidates, key=lambda c: c.get("correlation", 0.0), reverse=True)
            return sorted_candidates[:n]

    def get_pool_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated pool metrics.

        Returns:
            Dictionary of pool-wide metrics
        """
        with self.__lock:
            if not self.__candidates:
                return {
                    "avg_loss": 0.0,
                    "avg_accuracy": 0.0,
                    "avg_precision": 0.0,
                    "avg_recall": 0.0,
                    "avg_f1_score": 0.0,
                }

            n = len(self.__candidates)
            return {
                "avg_loss": sum(c.get("loss", 0.0) for c in self.__candidates) / n,
                "avg_accuracy": sum(c.get("accuracy", 0.0) for c in self.__candidates) / n,
                "avg_precision": sum(c.get("precision", 0.0) for c in self.__candidates) / n,
                "avg_recall": sum(c.get("recall", 0.0) for c in self.__candidates) / n,
                "avg_f1_score": sum(c.get("f1_score", 0.0) for c in self.__candidates) / n,
            }

    def get_state(self) -> Dict[str, Any]:
        """
        Get current pool state.

        Returns:
            Dictionary with pool state
        """
        with self.__lock:
            elapsed_time = 0.0
            if self.__start_time is not None:
                elapsed_time = time.time() - self.__start_time

            return {
                "status": self.__status,
                "phase": self.__phase,
                "size": self.__size,
                "iterations": self.__iterations,
                "progress": self.__progress,
                "target": self.__target,
                "elapsed_time": elapsed_time,
            }

    def clear(self) -> None:
        """Clear all candidates from pool."""
        with self.__lock:
            self.__candidates.clear()
            self.__size = 0
            self.__iterations = 0
            self.__progress = 0.0
            self.__status = "Inactive"
            self.__start_time = None


class TrainingState:
    """
    Thread-safe single source of truth for all training state.

    Provides atomic state updates and serialization for REST/WebSocket broadcasting.
    All state modifications are protected by threading.Lock for thread safety.
    """

    _STATE_FIELDS = {
        "status",
        "phase",
        "learning_rate",
        "max_hidden_units",
        "max_epochs",
        "current_epoch",
        "current_step",
        "network_name",
        "dataset_name",
        "threshold_function",
        "optimizer_name",
        "timestamp",
        "candidate_pool_status",
        "candidate_pool_phase",
        "candidate_pool_size",
        "top_candidate_id",
        "top_candidate_score",
        "second_candidate_id",
        "second_candidate_score",
        "pool_metrics",
    }

    def __init__(self):
        """Initialize TrainingState with default values."""
        self.__lock = threading.Lock()
        self.__status: str = "Stopped"
        self.__phase: str = "Idle"
        self.__learning_rate: float = 0.0
        self.__max_hidden_units: int = 0
        self.__max_epochs: int = 200
        self.__current_epoch: int = 0
        self.__current_step: int = 0
        self.__network_name: str = ""
        self.__dataset_name: str = ""
        self.__threshold_function: str = ""
        self.__optimizer_name: str = ""
        self.__timestamp: float = time.time()

        self.__candidate_pool_status: str = "Inactive"
        self.__candidate_pool_phase: str = "Idle"
        self.__candidate_pool_size: int = 0
        self.__top_candidate_id: str = ""
        self.__top_candidate_score: float = 0.0
        self.__second_candidate_id: str = ""
        self.__second_candidate_score: float = 0.0
        self.__pool_metrics: Dict[str, Any] = {}

    def get_state(self) -> Dict[str, Any]:
        """
        Get current state as dictionary.

        Returns:
            Dictionary containing all state fields
        """
        with self.__lock:
            return {
                "status": self.__status,
                "phase": self.__phase,
                "learning_rate": self.__learning_rate,
                "max_hidden_units": self.__max_hidden_units,
                "max_epochs": self.__max_epochs,
                "current_epoch": self.__current_epoch,
                "current_step": self.__current_step,
                "network_name": self.__network_name,
                "dataset_name": self.__dataset_name,
                "threshold_function": self.__threshold_function,
                "optimizer_name": self.__optimizer_name,
                "timestamp": self.__timestamp,
                "candidate_pool_status": self.__candidate_pool_status,
                "candidate_pool_phase": self.__candidate_pool_phase,
                "candidate_pool_size": self.__candidate_pool_size,
                "top_candidate_id": self.__top_candidate_id,
                "top_candidate_score": self.__top_candidate_score,
                "second_candidate_id": self.__second_candidate_id,
                "second_candidate_score": self.__second_candidate_score,
                "pool_metrics": self.__pool_metrics,
            }

    def update_state(self, **kwargs) -> None:
        """
        Update state fields atomically.

        Accepts keyword arguments using public field names
        (e.g., status="Started", phase="Output", ...).
        Unknown fields are ignored. Passing None leaves the field unchanged.

        Args:
            **kwargs: State fields to update (status, phase, learning_rate, etc.)
        """
        cls_name = self.__class__.__name__
        updated = False

        with self.__lock:
            for key, value in kwargs.items():
                if value is None or key not in self._STATE_FIELDS:
                    continue

                mangled_name = f"_{cls_name}__{key}"

                if mangled_name in self.__dict__:
                    self.__dict__[mangled_name] = value
                    updated = True

            if updated and "timestamp" not in kwargs:
                self.__timestamp = time.time()

    def to_json(self) -> str:
        """
        Serialize state to JSON string.

        Returns:
            JSON string representation of current state
        """
        return json.dumps(self.get_state())


class TrainingMonitor:
    """
    Monitors CasCor training process and collects real-time metrics.

    Provides callbacks for training events:
    - Epoch start/end
    - Cascade unit addition
    - Training state changes
    - Network topology updates
    """

    def __init__(self, data_adapter: DataAdapter):
        """
        Initialize training monitor.

        Args:
            data_adapter: DataAdapter instance for format conversion
        """
        self.logger = logging.getLogger(__name__)
        self.data_adapter = data_adapter

        # Metrics storage
        self.metrics_buffer: List[TrainingMetrics] = []
        self.max_buffer_size = 10000

        # State tracking
        self.is_training = False
        self.current_epoch = 0
        self.current_hidden_units = 0
        self.current_phase = "output"

        # Callback registration
        self.callbacks: Dict[str, List[Callable]] = {
            "epoch_start": [],
            "epoch_end": [],
            "cascade_add": [],
            "training_start": [],
            "training_end": [],
            "topology_change": [],
        }

        # Thread-safe queue for metrics
        self.metrics_queue = queue.Queue()

        # Lock for thread safety
        self.lock = threading.Lock()

        self.logger.info("TrainingMonitor initialized")

    def register_callback(self, event_type: str, callback: Callable):
        """
        Register callback for training event.

        Args:
            event_type: Type of event ('epoch_start', 'epoch_end', etc.)
            callback: Callback function
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            self.logger.debug(f"Registered callback for {event_type}")
        else:
            self.logger.warning(f"Unknown event type: {event_type}")

    def _trigger_callbacks(self, event_type: str, **kwargs):
        """
        Trigger all callbacks for an event type.

        Args:
            event_type: Type of event
            **kwargs: Event data
        """
        for callback in self.callbacks.get(event_type, []):
            try:
                callback(**kwargs)
            except Exception as e:
                self.logger.error(f"Callback error for {event_type}: {e}")

    def on_training_start(self):
        """Handle training start event."""
        with self.lock:
            self.is_training = True
            self.current_epoch = 0
            self.metrics_buffer.clear()

        self.logger.info("Training started")
        self._trigger_callbacks("training_start")

    def on_training_end(self, final_metrics: Optional[Dict[str, Any]] = None):
        """
        Handle training end event.

        Args:
            final_metrics: Optional final training metrics
        """
        with self.lock:
            self.is_training = False

        self.logger.info("Training ended")
        self._trigger_callbacks("training_end", final_metrics=final_metrics)

    def on_epoch_start(self, epoch: int, phase: str = "output"):
        """
        Handle epoch start event.

        Args:
            epoch: Epoch number
            phase: Training phase ('output' or 'candidate')
        """
        with self.lock:
            self.current_epoch = epoch
            self.current_phase = phase

        self.logger.debug(f"Epoch {epoch} started (phase: {phase})")
        self._trigger_callbacks("epoch_start", epoch=epoch, phase=phase)

    def on_epoch_end(
        self,
        epoch: int,
        loss: float,
        accuracy: float,
        learning_rate: float,
        validation_loss: Optional[float] = None,
        validation_accuracy: Optional[float] = None,
    ):
        """
        Handle epoch end event and collect metrics.

        Args:
            epoch: Epoch number
            loss: Training loss
            accuracy: Training accuracy
            learning_rate: Current learning rate
            validation_loss: Validation loss (optional)
            validation_accuracy: Validation accuracy (optional)
        """
        # Create metrics object
        metrics = self.data_adapter.extract_training_metrics(
            epoch=epoch,
            loss=loss,
            accuracy=accuracy,
            learning_rate=learning_rate,
            hidden_units=self.current_hidden_units,
            cascade_phase=self.current_phase,
            validation_loss=validation_loss,
            validation_accuracy=validation_accuracy,
        )

        # Add to buffer
        with self.lock:
            self.metrics_buffer.append(metrics)
            if len(self.metrics_buffer) > self.max_buffer_size:
                self.metrics_buffer.pop(0)

        # Add to queue for async processing
        self.metrics_queue.put(metrics)

        self.logger.debug(f"Epoch {epoch} ended: loss={loss:.4f}, accuracy={accuracy:.4f}")
        self._trigger_callbacks("epoch_end", metrics=metrics, epoch=epoch, loss=loss, accuracy=accuracy)

    def on_cascade_add(self, hidden_unit_index: int, correlation: float, weights: Optional[Dict[str, Any]] = None):
        """
        Handle cascade unit addition event.

        Args:
            hidden_unit_index: Index of new hidden unit
            correlation: Correlation value that triggered addition
            weights: Optional weight information
        """
        with self.lock:
            self.current_hidden_units += 1

        cascade_event = {
            "timestamp": datetime.now().isoformat(),
            "hidden_unit_index": hidden_unit_index,
            "correlation": correlation,
            "total_hidden_units": self.current_hidden_units,
        }

        self.logger.info(f"Cascade unit {hidden_unit_index} added " f"(correlation={correlation:.4f})")
        self._trigger_callbacks("cascade_add", event=cascade_event)

    def on_topology_change(self, topology: NetworkTopology):
        """
        Handle network topology change event.

        Args:
            topology: New network topology
        """
        self.logger.debug("Network topology changed")
        self._trigger_callbacks("topology_change", topology=topology)

    def get_recent_metrics(self, count: int = 100) -> List[TrainingMetrics]:
        """
        Get recent training metrics.

        Args:
            count: Number of recent metrics to retrieve

        Returns:
            List of TrainingMetrics objects
        """
        with self.lock:
            return self.metrics_buffer[-count:]

    def get_all_metrics(self) -> List[TrainingMetrics]:
        """
        Get all stored training metrics.

        Returns:
            List of all TrainingMetrics objects
        """
        with self.lock:
            return self.metrics_buffer.copy()

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current training state.

        Returns:
            Dictionary with current state information
        """
        with self.lock:
            return {
                "is_training": self.is_training,
                "current_epoch": self.current_epoch,
                "current_hidden_units": self.current_hidden_units,
                "current_phase": self.current_phase,
                "total_metrics": len(self.metrics_buffer),
            }

    def clear_metrics(self):
        """Clear metrics buffer."""
        with self.lock:
            self.metrics_buffer.clear()
        self.logger.info("Metrics buffer cleared")

    def poll_metrics_queue(self, timeout: float = 0.1) -> Optional[TrainingMetrics]:
        """
        Poll metrics queue for new metrics (non-blocking).

        Args:
            timeout: Timeout in seconds

        Returns:
            TrainingMetrics object or None if queue empty
        """
        try:
            return self.metrics_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def apply_params(self, learning_rate: Optional[float] = None, max_hidden_units: Optional[int] = None) -> Dict[str, Any]:
        """
        Apply parameter changes to training configuration.

        Args:
            learning_rate: New learning rate value
            max_hidden_units: New max hidden units constraint

        Returns:
            Dictionary with applied parameter values
        """
        applied = {}

        with self.lock:
            if learning_rate is not None:
                # Apply to monitoring state (actual trainer would be updated via callback)
                applied["learning_rate"] = learning_rate
                self.logger.info(f"Applied learning_rate: {learning_rate}")

            if max_hidden_units is not None:
                # Apply max hidden units constraint
                applied["max_hidden_units"] = max_hidden_units
                self.logger.info(f"Applied max_hidden_units: {max_hidden_units}")

        return applied
