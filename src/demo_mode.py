#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.1.1
# File Name:     demo_mode.py
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/
#
# Date Created:  2025-10-22
# Last Modified: 2025-12-13
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     This file provides demo mode functionality for the Juniper Canopy, generating
#     mock training data and network states to enable frontend development and testing
#     without requiring an active CasCor training session.
#
#####################################################################################################################################################################################################
# Notes:
#     Demo Mode Module
#         Generates realistic mock data for all frontend components:
#             - Training metrics with realistic loss/accuracy curves
#             - Network topology evolution (cascade unit additions)
#             - Decision boundaries from synthetic classifiers
#             - Spiral dataset for visualization
#         Training Control Methods (verified in v1.1.0):
#             - start()  - Begin training simulation
#             - pause()  - Pause training without losing state
#             - resume() - Resume from paused state
#             - stop()   - Stop training completely
#             - reset()  - Reset to initial state
#         Usage:
#             from demo_mode import DemoMode
#             demo = DemoMode()
#             demo.start()  # Begins continuous demo simulation
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#     Force pre-commit checks to run
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from backend.training_state_machine import Command, TrainingPhase, TrainingStateMachine  # TrainingStatus,
from canopy_constants import TrainingConstants
from config_manager import ConfigManager

# import copy


class MockCascorNetwork:
    """
    Mock CasCor network that simulates training behavior.

    Provides same interface as real CascadeCorrelationNetwork but with
    synthetic data generation instead of actual neural network computations.
    """

    def __init__(self, input_size: int = 2, output_size: int = 1):
        """
        Initialize mock network.

        Args:
            input_size: Number of input features
            output_size: Number of output units
        """
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_units = []
        self.learning_rate = 0.01

        # Training history (use deque with maxlen to prevent unbounded growth)
        self.history = {
            "train_loss": deque(maxlen=1000),
            "train_accuracy": deque(maxlen=1000),
            "val_loss": deque(maxlen=1000),
            "val_accuracy": deque(maxlen=1000),
        }

        # Network weights (initialized small random)
        self.input_weights = torch.randn(input_size, output_size) * 0.1
        self.output_weights = torch.randn(output_size, input_size) * 0.1
        self.output_bias = torch.randn(output_size) * 0.1

        # Training state
        self.current_epoch = 0
        self.is_training = False

        # Dataset storage
        self.train_x = None
        self.train_y = None

    def add_hidden_unit(self):
        """Add a new cascade hidden unit."""
        hidden_id = len(self.hidden_units)

        # Create hidden unit with random weights
        unit = {
            "id": hidden_id,
            "weights": torch.randn(self.input_size + hidden_id) * 0.1,
            "bias": torch.randn(1) * 0.1,
            "activation_fn": torch.sigmoid,
        }

        self.hidden_units.append(unit)

        # Update output weights to accommodate new hidden unit
        # Need to expand output_weights matrix by one column for new hidden unit
        old_num_cols = self.output_weights.shape[1]
        new_output_weights = torch.randn(self.output_size, self.input_size + len(self.hidden_units)) * 0.1
        # Copy all existing weights (inputs + previous hidden units)
        new_output_weights[:, :old_num_cols] = self.output_weights
        self.output_weights = new_output_weights

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass (simplified simulation).

        Args:
            x: Input tensor

        Returns:
            Output predictions
        """
        # Simple linear transformation (mock prediction)
        if len(self.hidden_units) == 0:
            output = torch.matmul(x, self.input_weights) + self.output_bias
        else:
            # Include hidden unit contributions (simplified)
            output = torch.matmul(x, self.input_weights[: x.shape[1], :]) + self.output_bias

        return torch.sigmoid(output)


class DemoMode:
    """
    Demo mode manager for Juniper Canopy.

    Simulates realistic training behavior without actual neural network:
    - Generates synthetic datasets (spiral, XOR, etc.)
    - Simulates training with realistic loss curves
    - Periodically adds cascade units
    - Broadcasts updates via WebSocket
    """

    def __init__(self, update_interval: float = 1.0):
        """
        Initialize demo mode with config-driven simulation parameters.

        Args:
            update_interval: Time between simulated epochs (seconds)
        """
        self.logger = logging.getLogger(__name__)

        # Initialize ConfigManager for demo configuration
        config_mgr = ConfigManager()
        training_defaults = config_mgr.get_training_defaults()
        demo_config = config_mgr.config.get("development", {}).get("demo_mode", {})

        if interval_env := os.getenv("CASCOR_DEMO_UPDATE_INTERVAL"):
            try:
                self.update_interval = float(interval_env)
                self.logger.info(f"Demo update interval from env: {self.update_interval}s")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_DEMO_UPDATE_INTERVAL: {interval_env}")
                self.update_interval = demo_config.get("simulation_interval_sec", update_interval)
        else:
            self.update_interval = demo_config.get("simulation_interval_sec", update_interval)

        # Create mock network
        self.network = MockCascorNetwork(input_size=2, output_size=1)

        # Generate demo dataset
        self.dataset = self._generate_spiral_dataset(n_samples=200)
        self.network.train_x = self.dataset["inputs_tensor"]
        self.network.train_y = self.dataset["targets_tensor"]

        # Training simulation state
        self.current_epoch = 0
        self.current_loss = 1.0
        self.current_accuracy = 0.5
        self.target_loss = 0.1
        self.is_running = False
        self.thread = None

        # Thread safety
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pause = threading.Event()

        if epochs_env := os.getenv("CASCOR_TRAINING_EPOCHS"):
            try:
                self.max_epochs = int(epochs_env)
                self.logger.info(f"Max epochs from env: {self.max_epochs}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_TRAINING_EPOCHS: {epochs_env}")
                self.max_epochs = training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)
        else:
            self.max_epochs = training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)

        if hidden_units_env := os.getenv("CASCOR_TRAINING_HIDDEN_UNITS"):
            try:
                self.max_hidden_units = int(hidden_units_env)
                self.logger.info(f"Max hidden units from env: {self.max_hidden_units}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_TRAINING_HIDDEN_UNITS: {hidden_units_env}")
                self.max_hidden_units = training_defaults.get(
                    "hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS
                )
        else:
            self.max_hidden_units = training_defaults.get("hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS)

        if cascade_every_env := os.getenv("CASCOR_DEMO_CASCADE_EVERY"):
            try:
                self.cascade_every = int(cascade_every_env)
                self.logger.info(f"Cascade frequency from env: {self.cascade_every}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_DEMO_CASCADE_EVERY: {cascade_every_env}")
                self.cascade_every = demo_config.get("cascade_every", 30)
        else:
            self.cascade_every = demo_config.get("cascade_every", 30)

        # Metrics buffer for realistic curves
        self.metrics_history = deque(maxlen=1000)

        self.logger.info(
            f"DemoMode configuration: "
            f"max_epochs={self.max_epochs}, "
            f"max_hidden_units={self.max_hidden_units}, "
            f"cascade_every={self.cascade_every}, "
            f"update_interval={self.update_interval}s"
        )

        # TrainingState instance
        try:
            from backend.training_monitor import CandidatePool, TrainingState

            self.training_state = TrainingState()
            self.candidate_pool = CandidatePool()
            self._initialize_training_state()
        except ImportError:
            self.training_state = None
            self.candidate_pool = None
            self.logger.warning("TrainingState not available")

        # Training state machine
        self.state_machine = TrainingStateMachine()
        self.logger.info("Training state machine initialized")

        self.logger.info("DemoMode initialized with spiral dataset")

    def _initialize_training_state(self):
        """Initialize TrainingState with demo values."""
        if self.training_state:
            self.training_state.update_state(
                status="Stopped",
                phase="Idle",
                learning_rate=0.01,
                max_hidden_units=self.max_hidden_units,
                max_epochs=self.max_epochs,
                current_epoch=0,
                current_step=0,
                network_name="MockCascorNetwork",
                dataset_name="Spiral2D",
                threshold_function="tanh",
                optimizer_name="SGD",
            )

    # def _update_training_state(self):
    def _update_training_status(self):
        """Update TrainingState based on current demo state and FSM."""
        if not self.training_state:
            return

        with self._lock:
            self._update_candidate_pool_state()
        self._broadcast_state()

    def _update_candidate_pool_state(self):
        # Get status and phase from FSM
        fsm_state = self.state_machine.get_state_summary()
        status = fsm_state["status"]
        phase = fsm_state["phase"]

        # Get candidate pool data
        pool_status = "Inactive"
        pool_phase = "Idle"
        pool_size = 0
        top_cand_id = ""
        top_cand_score = 0.0
        second_cand_id = ""
        second_cand_score = 0.0
        pool_metrics = {}

        if self.candidate_pool and phase == "CANDIDATE":
            pool_state = self.candidate_pool.get_state()
            pool_status = pool_state["status"]
            pool_phase = pool_state["phase"]
            pool_size = pool_state["size"]

            top_candidates = self.candidate_pool.get_top_n_candidates(n=2)
            if len(top_candidates) > 0:
                top_cand_id = top_candidates[0].get("id", "")
                top_cand_score = top_candidates[0].get("correlation", 0.0)
            if len(top_candidates) > 1:
                second_cand_id = top_candidates[1].get("id", "")
                second_cand_score = top_candidates[1].get("correlation", 0.0)

            pool_metrics = self.candidate_pool.get_pool_metrics()

        self.training_state.update_state(
            status=status,
            phase=phase,
            learning_rate=self.network.learning_rate,
            max_hidden_units=self.max_hidden_units,
            max_epochs=self.max_epochs,
            current_epoch=self.current_epoch,
            current_step=self.current_epoch,
            network_name="MockCascorNetwork",
            dataset_name="Spiral2D",
            threshold_function="tanh",
            optimizer_name="SGD",
            candidate_pool_status=pool_status,
            candidate_pool_phase=pool_phase,
            candidate_pool_size=pool_size,
            top_candidate_id=top_cand_id,
            top_candidate_score=top_cand_score,
            second_candidate_id=second_cand_id,
            second_candidate_score=second_cand_score,
            pool_metrics=pool_metrics,
        )

    def _broadcast_state(self):
        """Broadcast TrainingState via WebSocket."""
        if not self.training_state:
            return

        try:
            from communication.websocket_manager import websocket_manager

            websocket_manager.broadcast_state_change(self.training_state.get_state())
        except ImportError:
            pass
        except Exception as e:
            self.logger.warning(f"State broadcast failed: {type(e).__name__}: {e}")

    def _generate_spiral_dataset(self, n_samples: int = 200, algorithm: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate two-class spiral dataset.

        Uses JuniperData service if JUNIPER_DATA_URL environment variable is set,
        otherwise falls back to local generation.

        Args:
            n_samples: Number of samples per class
            algorithm: Optional algorithm parameter for backward compatibility

        Returns:
            Dataset dictionary
        """
        juniper_data_url = os.environ.get("JUNIPER_DATA_URL")
        if juniper_data_url:
            dataset = self._generate_spiral_dataset_from_juniper_data(n_samples, juniper_data_url, algorithm=algorithm)
            if dataset is not None:
                return dataset
            self.logger.warning("JuniperData service unavailable, falling back to local generation")

        return self._generate_spiral_dataset_local(n_samples)

    def _generate_spiral_dataset_from_juniper_data(
        self,
        n_samples: int,
        juniper_data_url: str,
        algorithm: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate spiral dataset using JuniperData service.

        Args:
            n_samples: Number of samples per class
            juniper_data_url: URL of the JuniperData service
            algorithm: Optional algorithm parameter for backward compatibility

        Returns:
            Dataset dictionary or None if service unavailable
        """
        try:
            from juniper_data_client import JuniperDataClient

            client = JuniperDataClient(base_url=juniper_data_url)

            params = {
                "n_points_per_spiral": n_samples // 2,
                "n_spirals": 2,
                "noise": 0.1,
                "seed": 42,
            }
            if algorithm is not None:
                params["algorithm"] = algorithm

            response = client.create_dataset(
                generator="spiral",
                params=params,
                persist=False,
            )

            dataset_id = response.get("dataset_id")
            if not dataset_id:
                self.logger.warning("JuniperData response missing dataset_id")
                return None

            npz_data = client.download_artifact_npz(dataset_id)

            inputs = npz_data.get("X_full")
            targets_one_hot = npz_data.get("y_full")
            if inputs is None or targets_one_hot is None:
                self.logger.warning("JuniperData artifact missing X_full/y_full")
                return None

            targets = np.argmax(targets_one_hot, axis=1).astype(np.float32)

            self.logger.info(f"Generated spiral dataset via JuniperData: {len(inputs)} samples")

            return {
                "inputs": inputs,
                "targets": targets,
                "inputs_tensor": torch.from_numpy(inputs).float(),
                "targets_tensor": torch.from_numpy(targets).float().unsqueeze(1),
                "num_samples": len(inputs),
                "num_features": inputs.shape[1] if len(inputs.shape) > 1 else 2,
                "num_classes": 2,
            }

        except ImportError:
            self.logger.warning("juniper_data_client not available")
            return None
        except Exception as e:
            self.logger.warning(f"JuniperData request failed: {type(e).__name__}: {e}")
            return None

    def _generate_spiral_dataset_local(self, n_samples: int = 200) -> Dict[str, Any]:
        """
        Generate two-class spiral dataset locally.

        Args:
            n_samples: Number of samples per class

        Returns:
            Dataset dictionary
        """
        np.random.seed(42)

        n_per_class = n_samples // 2
        theta = np.linspace(0, 4 * np.pi, n_per_class)

        r0 = theta / (4 * np.pi)
        x0 = r0 * np.cos(theta) + np.random.randn(n_per_class) * 0.1
        y0 = r0 * np.sin(theta) + np.random.randn(n_per_class) * 0.1

        r1 = theta / (4 * np.pi)
        x1 = -r1 * np.cos(theta) + np.random.randn(n_per_class) * 0.1
        y1 = -r1 * np.sin(theta) + np.random.randn(n_per_class) * 0.1

        inputs = np.vstack([np.column_stack([x0, y0]), np.column_stack([x1, y1])])
        targets = np.concatenate([np.zeros(n_per_class), np.ones(n_per_class)])

        indices = np.random.permutation(len(inputs))
        inputs = inputs[indices]
        targets = targets[indices]

        return {
            "inputs": inputs,
            "targets": targets,
            "inputs_tensor": torch.from_numpy(inputs).float(),
            "targets_tensor": torch.from_numpy(targets).float().unsqueeze(1),
            "num_samples": len(inputs),
            "num_features": 2,
            "num_classes": 2,
        }

    def _simulate_training_step(self) -> Tuple[float, float]:
        """
        Simulate one training epoch.

        Returns:
            Tuple of (loss, accuracy)
        """
        # Exponential decay towards target with noise
        decay_rate = 0.05
        noise_level = 0.02

        # Loss decreases exponentially with random fluctuations
        self.current_loss = self.target_loss + (self.current_loss - self.target_loss) * (1 - decay_rate)
        self.current_loss += np.random.randn() * noise_level
        self.current_loss = max(self.target_loss, self.current_loss)

        # Accuracy increases (inverse of loss trend)
        self.current_accuracy = 1.0 - (self.current_loss / 2.0)  # Rough approximation
        self.current_accuracy = min(0.98, max(0.5, self.current_accuracy))
        self.current_accuracy += np.random.randn() * 0.01  # Small noise

        return self.current_loss, self.current_accuracy

    def _simulate_candidate_pool(self):
        """Simulate candidate pool training with synthetic data."""
        if not self.candidate_pool:
            return

        # Activate pool
        pool_size = 8
        self.candidate_pool.update_pool(
            status="Active",
            phase="Training",
            size=pool_size,
            iterations=self.current_epoch * 10,
            progress=min(1.0, (self.current_epoch % 5) / 5.0),
            target=0.85,
        )

        # Generate synthetic candidates
        for i in range(pool_size):
            correlation = np.random.uniform(0.4, 0.9)
            loss = np.random.uniform(0.1, 0.5)
            accuracy = np.random.uniform(0.6, 0.95)
            precision = np.random.uniform(0.6, 0.9)
            recall = np.random.uniform(0.6, 0.9)
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            self.candidate_pool.add_candidate(
                candidate_id=f"cand_{i}",
                name=f"Candidate_{i}",
                correlation=correlation,
                loss=loss,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
            )

    def _should_add_cascade_unit(self) -> bool:
        """
        Determine if a cascade unit should be added.

        Returns:
            True if should add unit
        """
        # Thread-safe check of max_hidden_units
        with self._lock:
            max_units = self.max_hidden_units
            current_units = len(self.network.hidden_units)

        if current_units >= max_units:
            return False

        # Add unit every cascade_every epochs
        return self.current_epoch > 0 and self.current_epoch % self.cascade_every == 0

    def _training_loop(self):
        """Background training simulation loop."""
        self.logger.info("Demo training simulation started")

        while not self._stop.is_set():
            # Thread-safe check of max_epochs (read each iteration for dynamic updates)
            with self._lock:
                should_continue = self.current_epoch < self.max_epochs

            if not should_continue:
                self.logger.info(f"Training complete: reached max_epochs={self.max_epochs}")
                self.state_machine.mark_completed()
                self._update_training_status()
                break

            # Check if paused
            while self._pause.is_set() and not self._stop.is_set() and not self._stop.wait(0.1):
                pass

            # Check if stopped during pause
            if self._stop.is_set():
                break

            # Determine training phase
            is_candidate_phase = self.current_epoch > 0 and self.current_epoch % 5 == 0
            if is_candidate_phase:
                self.state_machine.set_phase(TrainingPhase.CANDIDATE)
                self._simulate_candidate_pool()
            else:
                self.state_machine.set_phase(TrainingPhase.OUTPUT)
                if self.candidate_pool:
                    self.candidate_pool.update_pool(status="Inactive")
                    self.candidate_pool.clear()

            # Simulate epoch
            loss, accuracy = self._simulate_training_step()

            # Generate validation metrics (slightly worse than training)
            val_loss = loss * 1.1 + np.random.randn() * 0.01
            val_accuracy = accuracy * 0.95 + np.random.randn() * 0.01

            # Thread-safe update of state
            with self._lock:
                self.current_epoch += 1
                self.network.current_epoch = self.current_epoch

                # Update history with standardized key names
                self.network.history["train_loss"].append(loss)
                self.network.history["train_accuracy"].append(accuracy)
                self.network.history["val_loss"].append(val_loss)
                self.network.history["val_accuracy"].append(val_accuracy)

                # Store metrics
                phase_name = self.state_machine.get_phase().name.lower()
                metrics = {
                    "epoch": self.current_epoch,
                    "metrics": {
                        "loss": float(loss),
                        "accuracy": float(accuracy),
                        "val_loss": float(val_loss),
                        "val_accuracy": float(val_accuracy),
                    },
                    "network_topology": {
                        "input_units": self.network.input_size,
                        "hidden_units": len(self.network.hidden_units),
                        "output_units": self.network.output_size,
                    },
                    "phase": phase_name,
                    "timestamp": datetime.now().isoformat(),
                }
                self.metrics_history.append(metrics)

            # Broadcast via WebSocket (outside lock to avoid blocking)
            self._broadcast_metrics(metrics)

            # Update and broadcast TrainingState
            # self._update_training_state()
            self._update_training_status()

            # Check if should add cascade unit
            if self._should_add_cascade_unit():
                # Add hidden unit and capture state snapshot (minimal lock time)
                with self._lock:
                    self.network.add_hidden_unit()
                    hidden_count = len(self.network.hidden_units)
                    unit_index = hidden_count - 1
                    current_epoch_snapshot = self.current_epoch

                    # Reset loss target to simulate retraining
                    self.current_loss = min(1.0, self.current_loss * 1.5)
                    self.target_loss *= 0.8

                # Broadcast outside lock to avoid blocking training thread
                self._broadcast_cascade_add(unit_index, hidden_count, current_epoch_snapshot)

            # Wait with ability to stop promptly
            if self._stop.wait(self.update_interval):
                break

        self.is_running = False
        self.logger.info("Demo training simulation completed")

    def _broadcast_metrics(self, metrics: Dict[str, Any]):
        """
        Broadcast metrics via WebSocket.

        Args:
            metrics: Metrics dictionary
        """
        try:
            from communication.websocket_manager import create_metrics_message, websocket_manager

            websocket_manager.broadcast_from_thread(create_metrics_message(metrics))
        except ImportError:
            # Module not available - expected during initialization
            pass
        except Exception as e:
            self.logger.warning(f"WebSocket broadcast failed: {type(e).__name__}: {e}")

    def _broadcast_cascade_add(self, unit_index: int, hidden_count: int, epoch: int):
        """
        Broadcast cascade unit addition event.

        Args:
            unit_index: Index of added unit
            hidden_count: Total number of hidden units after addition
            epoch: Current epoch when unit was added
        """
        try:
            from communication.websocket_manager import create_event_message, websocket_manager

            details = {"unit_index": unit_index, "total_hidden_units": hidden_count, "epoch": epoch}
            websocket_manager.broadcast_from_thread(create_event_message("cascade_add", details))
        except ImportError:
            # Module not available - expected during initialization
            pass
        except Exception as e:
            self.logger.warning(f"WebSocket cascade broadcast failed: {type(e).__name__}: {e}")

    def start(self, reset: bool = True) -> Dict[str, Any]:
        """
        Start demo training simulation.

        Args:
            reset: If True, reset all histories and state to fresh start

        Returns:
            Initial state snapshot after reset
        """
        # Handle FSM transition
        if reset and not self.state_machine.handle_command(Command.RESET):
            self.logger.error("FSM: Failed to reset before start")
            return self.get_current_state()

        # Use START command (acts as RESUME if paused)
        if not self.state_machine.handle_command(Command.START):
            self.logger.error("FSM: Invalid START command in current state")
            return self.get_current_state()

        if self.is_running and not reset:
            self.logger.warning("Demo mode already running")
            return self.get_current_state()

        with self._lock:
            if reset:
                self._reset_state_and_history()
            self.is_running = True
            self._stop.clear()

            # Capture state snapshot BEFORE starting thread
            state_snapshot = {
                "is_running": self.is_running,
                "is_paused": self._pause.is_set(),
                "current_epoch": self.current_epoch,
                "current_loss": self.current_loss,
                "current_accuracy": self.current_accuracy,
                "hidden_units": len(self.network.hidden_units),
                "metrics_count": len(self.metrics_history),
            }

        # Start background thread AFTER releasing lock and capturing state
        if not self.thread or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._training_loop, daemon=True)
            self.thread.start()

        # Update FSM phase
        self.state_machine.set_phase(TrainingPhase.OUTPUT)

        # Update TrainingState
        # self._update_training_state()
        self._update_training_status()

        self.logger.info("Demo mode started" + (" (reset)" if reset else " (continued)"))
        return state_snapshot

    def _reset_state_and_history(self):
        # Reset all state for fresh run
        self.current_epoch = 0
        self.current_loss = 1.0
        self.current_accuracy = 0.5
        self.target_loss = 0.1
        self.metrics_history.clear()

        # Reset network history
        for key in self.network.history:
            self.network.history[key].clear()
        self.network.hidden_units.clear()
        self.network.current_epoch = 0

    def stop(self):
        """Stop demo training simulation."""
        # Handle FSM transition
        if not self.state_machine.handle_command(Command.STOP):
            self.logger.error("FSM: Invalid STOP command in current state")
            return

        if not self.is_running:
            # Update state even if not running
            # self._update_training_state()
            self._update_training_status()
            return

        # Signal stop
        self._stop.set()

        # Wait for thread to finish
        if self.thread:
            self.thread.join(timeout=5.0)
            if self.thread.is_alive():
                self.logger.warning("Demo thread did not stop cleanly")
        self._perform_reset()

        # Update TrainingState
        # self._update_training_state()
        self._update_training_status()

        self.logger.info("Demo mode stopped")

    def pause(self):
        """Pause demo training simulation."""
        # Save candidate state if in candidate phase (only if not already saved)
        if (
            self.state_machine.get_phase() == TrainingPhase.CANDIDATE
            and self.state_machine.get_candidate_state() is None
        ):
            candidate_state = {
                "epoch": self.current_epoch,
                "loss": self.current_loss,
                "accuracy": self.current_accuracy,
            }
            self.state_machine.save_candidate_state(candidate_state)

        # Handle FSM transition
        if not self.state_machine.handle_command(Command.PAUSE):
            self.logger.error("FSM: Invalid PAUSE command in current state")
            return

        if not self.is_running:
            self.logger.warning("Demo mode not running, cannot pause")
            return

        with self._lock:
            if self._pause.is_set():
                self.logger.warning("Demo mode already paused")
                return
            self._pause.set()

        self._update_training_state("paused", "Demo mode paused")

    def resume(self):
        """Resume demo training simulation."""
        # Handle FSM transition
        if not self.state_machine.handle_command(Command.RESUME):
            self.logger.error("FSM: Invalid RESUME command in current state")
            return

        # Restore candidate state if it was saved
        if self.state_machine.get_phase() == TrainingPhase.CANDIDATE:
            if candidate_state := self.state_machine.get_candidate_state():
                self.logger.info(f"Restoring candidate state: {candidate_state}")

        if not self.is_running:
            self.logger.warning("Demo mode not running, cannot resume")
            return

        with self._lock:
            if not self._pause.is_set():
                self.logger.warning("Demo mode not paused, cannot resume")
                return
            self._pause.clear()

        self._update_training_state("running", "Demo mode resumed")

    def _update_training_state(
        self,
        status_label: Optional[str] = None,
        log_message: Optional[str] = None,
    ) -> None:
        """
        Update training state and optionally broadcast status and log a message.

        Args:
            status_label: Optional status string to broadcast via WebSocket
            log_message: Optional message to log
        """
        self._update_training_status()

        if status_label is not None:
            self._broadcast_status(status_label)

        if log_message:
            self.logger.info(log_message)

    def reset(self) -> Dict[str, Any]:
        """
        Reset demo mode state and restart.

        Returns:
            State snapshot after reset
        """
        # Handle FSM transition
        if not self.state_machine.handle_command(Command.RESET):
            self.logger.error("FSM: Failed to reset")
            return self.get_current_state()

        if was_running := self.is_running:
            self._reset_while_running(was_running)
        with self._lock:
            self._reset_state_and_history()

            # Capture state snapshot BEFORE restarting
            state_snapshot = {
                "is_running": False,  # Stopped for reset
                "is_paused": self._pause.is_set(),
                "current_epoch": self.current_epoch,
                "current_loss": self.current_loss,
                "current_accuracy": self.current_accuracy,
                "hidden_units": len(self.network.hidden_units),
                "metrics_count": len(self.metrics_history),
            }

        # Don't auto-restart after reset - let caller decide
        self._update_training_state()
        self.logger.info("Demo mode reset")
        return state_snapshot

    def _reset_while_running(self, was_running):
        self.logger.info("Resetting demo mode while running")
        self.was_running = was_running
        # Stop without FSM command (RESET already handled it)
        self._stop.set()
        if self.thread:
            self.thread.join(timeout=5.0)
        self._perform_reset()

    def _perform_reset(self):
        with self._lock:
            self.is_running = False
        self._stop = threading.Event()
        self._pause.clear()

    def _broadcast_status(self, status: str):
        """
        Broadcast status change via WebSocket.

        Args:
            status: Status string ('running', 'paused', 'stopped', 'reset')
        """
        try:
            from communication.websocket_manager import create_event_message, websocket_manager

            state = self.get_current_state()
            details = {"status": status, **state}

            websocket_manager.broadcast_from_thread(create_event_message("status_change", details))
        except ImportError:
            pass
        except Exception as e:
            self.logger.warning(f"WebSocket status broadcast failed: {type(e).__name__}: {e}")

    def get_network(self) -> MockCascorNetwork:
        """
        Get mock network instance.

        Returns:
            MockCascorNetwork instance
        """
        return self.network

    def get_dataset(self) -> Dict[str, Any]:
        """
        Get demo dataset.

        Returns:
            Dataset dictionary
        """
        return self.dataset

    def get_metrics_history(self) -> List[Dict[str, Any]]:
        """
        Get metrics history (thread-safe).

        Returns:
            List of metrics dictionaries
        """
        with self._lock:
            return list(self.metrics_history)

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get current demo state (thread-safe).

        Returns:
            State dictionary
        """
        with self._lock:
            return {
                "is_running": self.is_running,
                "is_paused": self._pause.is_set(),
                "current_epoch": self.current_epoch,
                "current_loss": self.current_loss,
                "current_accuracy": self.current_accuracy,
                "hidden_units": len(self.network.hidden_units),
                "metrics_count": len(self.metrics_history),
                "activation_fn": "tanh",
                "optimizer": "SGD",
            }

    def apply_params(
        self,
        learning_rate: Optional[float] = None,
        max_hidden_units: Optional[int] = None,
        max_epochs: Optional[int] = None,
    ):
        """
        Apply parameter changes to demo mode.

        Args:
            learning_rate: New learning rate value
            max_hidden_units: New max hidden units constraint
            max_epochs: New maximum epochs limit
        """
        with self._lock:
            if learning_rate is not None:
                self.network.learning_rate = learning_rate
                self.logger.info(f"Demo mode: learning_rate set to {learning_rate}")

            if max_hidden_units is not None:
                self.max_hidden_units = max_hidden_units
                self.logger.info(f"Demo mode: max_hidden_units set to {max_hidden_units}")

            if max_epochs is not None:
                self.max_epochs = int(max_epochs)
                self.logger.info(f"Demo mode: max_epochs set to {max_epochs}")

        # Update TrainingState with new parameter values
        if self.training_state:
            updates = {}
            if learning_rate is not None:
                updates["learning_rate"] = learning_rate
            if max_hidden_units is not None:
                updates["max_hidden_units"] = max_hidden_units
            if max_epochs is not None:
                updates["max_epochs"] = max_epochs
            if updates:
                self.training_state.update_state(**updates)

        # Update TrainingState if available
        self._update_training_state()


# Global demo mode instance (singleton)
_demo_instance: Optional[DemoMode] = None


def get_demo_mode(update_interval: float = 1.0) -> DemoMode:
    """
    Get or create global demo mode instance.

    Args:
        update_interval: Time between simulated epochs

    Returns:
        DemoMode instance
    """
    global _demo_instance

    if _demo_instance is None:
        _demo_instance = DemoMode(update_interval=update_interval)

    return _demo_instance


if __name__ == "__main__":
    # Test demo mode standalone
    logging.basicConfig(level=logging.INFO)

    demo = get_demo_mode(update_interval=0.5)
    demo.start()

    try:
        # Run for 30 seconds
        time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        demo.stop()

        # Print summary
        state = demo.get_current_state()
        print("\nDemo Summary:")
        print(f"  Epochs: {state['current_epoch']}")
        print(f"  Final Loss: {state['current_loss']:.4f}")
        print(f"  Final Accuracy: {state['current_accuracy']:.4f}")
        print(f"  Hidden Units: {state['hidden_units']}")
