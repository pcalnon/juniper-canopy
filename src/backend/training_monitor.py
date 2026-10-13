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
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from canopy_constants import BackendConstants

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
        "dataset_version",
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
        "phase_detail",
        "grow_iteration",
        "grow_max",
        "best_correlation",
        "candidates_trained",
        "candidates_total",
        "phase_started_at",
        "candidate_epoch",
        "candidate_total_epochs",
        "all_correlations",
    }

    def __init__(self):
        """Initialize TrainingState with default values."""
        self._lock = threading.Lock()
        self._state: Dict[str, Any] = {
            "status": "Stopped",
            "phase": "Idle",
            "learning_rate": 0.0,
            "max_hidden_units": 0,
            "max_epochs": 200,
            "current_epoch": 0,
            "current_step": 0,
            "network_name": "",
            "dataset_name": "",
            "dataset_version": 0,
            "threshold_function": "",
            "optimizer_name": "",
            "timestamp": time.time(),
            "candidate_pool_status": "Inactive",
            "candidate_pool_phase": "Idle",
            "candidate_pool_size": 0,
            "top_candidate_id": "",
            "top_candidate_score": 0.0,
            "second_candidate_id": "",
            "second_candidate_score": 0.0,
            "pool_metrics": {},
            "phase_detail": "",
            "grow_iteration": 0,
            "grow_max": 0,
            "best_correlation": 0.0,
            "candidates_trained": 0,
            "candidates_total": 0,
            "phase_started_at": "",
            "candidate_epoch": 0,
            "candidate_total_epochs": 0,
            "all_correlations": [],
        }
        # F-CANOPY-036: candidate-pool history, accumulated HERE rather than in the
        # browser. The dashboard used to append it client-side, from a callback whose
        # Input was a ~1 Hz store — so any pool state shorter-lived than the callback's
        # promotion delay was simply never recorded, and across five training runs
        # (~20 candidate phases) the panel rendered no card at all. Every write that
        # can change ``candidate_pool_status`` already funnels through
        # ``update_state`` under ``self._lock``, so recording it there observes each
        # transition synchronously with the write that caused it. The race is not
        # narrowed, it is removed: there is no window in which a state exists and is
        # unobserved.
        self._pool_history: list = []

    def get_state(self) -> Dict[str, Any]:
        """
        Get current state as dictionary.

        Returns:
            Dictionary containing all state fields
        """
        with self._lock:
            snapshot = dict(self._state)
            # Return a defensive copy of mutable containers
            snapshot["all_correlations"] = list(snapshot["all_correlations"])
            snapshot["pool_metrics"] = dict(snapshot.get("pool_metrics", {}))
            return snapshot

    def update_state(self, **kwargs) -> None:
        """
        Update state fields atomically.

        Accepts keyword arguments using public field names
        (e.g., status="Started", phase="Output", ...).
        Unknown fields are ignored. Passing None leaves the field unchanged.

        Args:
            **kwargs: State fields to update (status, phase, learning_rate, etc.)
        """
        updated = False

        with self._lock:
            for key, value in kwargs.items():
                if value is None or key not in self._STATE_FIELDS:
                    continue

                if key in self._state:
                    self._state[key] = value
                    updated = True

            if updated and "timestamp" not in kwargs:
                self._state["timestamp"] = time.time()

            if updated:
                # F-CANOPY-036: still under the lock, so the snapshot is taken from
                # the state the caller just wrote and cannot be overtaken by the next
                # writer.
                self._record_pool_snapshot_locked()

    def _record_pool_snapshot_locked(self) -> None:
        """Record one pool snapshot per epoch while a pool is active (F-CANOPY-036).

        CALLER MUST HOLD ``self._lock``. Preserves the client-side append's contract
        exactly — one entry per ``current_epoch``, newest first, keeping the FIRST
        observation for an epoch and capping the list — so the panel's rendering and
        its existing tests are unaffected by where the accumulation happens.
        """
        status = self._state.get("candidate_pool_status") or "Inactive"
        if status == "Inactive":
            return

        epoch = self._state.get("current_epoch", 0)
        if any(entry.get("epoch") == epoch for entry in self._pool_history):
            return

        self._pool_history.insert(
            0,
            {
                "epoch": epoch,
                "status": status,
                "phase": self._state.get("candidate_pool_phase", "Idle"),
                "size": self._state.get("candidate_pool_size", 0),
                "top_candidate_id": self._state.get("top_candidate_id", ""),
                "top_candidate_score": self._state.get("top_candidate_score", 0.0),
                "second_candidate_id": self._state.get("second_candidate_id", ""),
                "second_candidate_score": self._state.get("second_candidate_score", 0.0),
                "pool_metrics": dict(self._state.get("pool_metrics") or {}),
                "timestamp": time.time(),
            },
        )
        del self._pool_history[BackendConstants.MAX_POOL_HISTORY_ENTRIES :]

    def get_pool_history(self) -> list:
        """Accumulated candidate-pool history, newest first (F-CANOPY-036).

        Returns defensive copies so a caller cannot mutate the accumulator.
        """
        with self._lock:
            return [dict(entry) for entry in self._pool_history]

    def clear_pool_history(self) -> None:
        """Drop the accumulated pool history (a new run starts a new history)."""
        with self._lock:
            self._pool_history.clear()

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
        self.max_buffer_size = BackendConstants.MAX_METRICS_BUFFER_SIZE

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
        with self.lock:
            if event_type in self.callbacks:
                self.callbacks[event_type].append(callback)
                self.logger.debug(f"Registered callback for {event_type}")
            else:
                self.logger.warning(f"Unknown event type: {event_type}")

    def _trigger_callbacks(self, event_type: str, **kwargs):
        """
        Trigger all callbacks for an event type.

        Takes a snapshot of the callback list under lock to avoid races
        with concurrent register_callback() calls.

        Args:
            event_type: Type of event
            **kwargs: Event data
        """
        with self.lock:
            callbacks = list(self.callbacks.get(event_type, []))
        for callback in callbacks:
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
        # Snapshot state under lock, then create metrics outside lock
        with self.lock:
            hidden_units = self.current_hidden_units
            cascade_phase = self.current_phase

        metrics = self.data_adapter.extract_training_metrics(
            epoch=epoch,
            loss=loss,
            accuracy=accuracy,
            learning_rate=learning_rate,
            hidden_units=hidden_units,
            cascade_phase=cascade_phase,
            validation_loss=validation_loss,
            validation_accuracy=validation_accuracy,
        )

        with self.lock:
            self.metrics_buffer.append(metrics)
            if len(self.metrics_buffer) > self.max_buffer_size:
                self.metrics_buffer.pop(0)

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
            total_hidden = self.current_hidden_units

        cascade_event = {
            "timestamp": datetime.now().isoformat(),
            "hidden_unit_index": hidden_unit_index,
            "correlation": correlation,
            "total_hidden_units": total_hidden,
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
