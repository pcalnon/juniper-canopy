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
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/
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
import math
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from backend.training_state_machine import Command, TrainingPhase, TrainingStateMachine  # TrainingStatus,
from canopy_constants import BackendConstants, TrainingConstants
from settings import get_settings

# import copy


class MockCascorNetwork:
    """
    Mock CasCor network that simulates training behavior.

    Implements the Cascade Correlation algorithm (Fahlman & Lebiere, 1990)
    using PyTorch autograd and Adam optimizer, matching the real
    CascadeCorrelationNetwork in juniper-cascor.
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
        self.hidden_units: List[Dict[str, Any]] = []
        self.learning_rate = 0.01

        # Training history (use deque with maxlen to prevent unbounded growth)
        self.history: Dict[str, deque] = {
            "train_loss": deque(maxlen=TrainingConstants.METRICS_HISTORY_MAXLEN),
            "train_accuracy": deque(maxlen=TrainingConstants.METRICS_HISTORY_MAXLEN),
            "val_loss": deque(maxlen=TrainingConstants.METRICS_HISTORY_MAXLEN),
            "val_accuracy": deque(maxlen=TrainingConstants.METRICS_HISTORY_MAXLEN),
        }

        # Output layer: nn.Linear + Adam optimizer (matching CasCor)
        self.output_layer = torch.nn.Linear(input_size, output_size)
        torch.nn.init.normal_(self.output_layer.weight, std=0.1)
        torch.nn.init.normal_(self.output_layer.bias, std=0.1)
        self.output_optimizer = torch.optim.Adam(self.output_layer.parameters(), lr=self.learning_rate)
        self.loss_fn = torch.nn.MSELoss()

        # Legacy attribute for network stats endpoint compatibility
        self.input_weights = torch.randn(input_size, output_size) * 0.1

        # Input normalization parameters (set when dataset is loaded)
        self._input_min: Optional[torch.Tensor] = None
        self._input_max: Optional[torch.Tensor] = None

        # Training state
        self.current_epoch = 0
        self.current_iteration = 0
        self.is_training = False

        # Dataset storage
        self.train_x = None
        self.train_y = None

    @property
    def output_weights(self):
        """Backward-compatible access to output layer weights."""
        return self.output_layer.weight.data

    @output_weights.setter
    def output_weights(self, value):
        """Backward-compatible setter — rebuilds output_layer from raw tensor."""
        out_features, in_features = value.shape
        self.output_size = out_features  # Keep output_size synchronized with actual layer shape
        self.output_layer = torch.nn.Linear(in_features, out_features)
        self.output_layer.weight.data = value
        self.output_optimizer = torch.optim.Adam(self.output_layer.parameters(), lr=self.learning_rate)

    @property
    def output_bias(self):
        """Backward-compatible access to output layer bias."""
        return self.output_layer.bias.data

    @output_bias.setter
    def output_bias(self, value):
        """Backward-compatible setter for output layer bias."""
        self.output_layer.bias.data = value

    def normalize_inputs(self, x: torch.Tensor) -> torch.Tensor:
        """Normalize inputs to [-1, 1] using stored min/max parameters.

        Args:
            x: Input tensor of shape (batch_size, input_size)

        Returns:
            Normalized tensor in [-1, 1] range
        """
        if self._input_min is not None and self._input_max is not None:
            return 2.0 * (x - self._input_min) / (self._input_max - self._input_min + 1e-8) - 1.0
        return x

    def _cascade_features(self, x: torch.Tensor) -> torch.Tensor:
        """Build the full feature vector by cascading through hidden units.

        Each hidden unit receives [original inputs + all previous hidden outputs].
        Returns [original inputs, hidden_0 output, hidden_1 output, ...].

        Args:
            x: Input tensor of shape (batch_size, input_size)

        Returns:
            Features tensor of shape (batch_size, input_size + num_hidden)
        """
        hidden_outputs: List[torch.Tensor] = []
        for unit in self.hidden_units:
            if hidden_outputs:
                unit_input = torch.cat([x] + hidden_outputs, dim=1)
            else:
                unit_input = x
            h = unit["activation_fn"](torch.sum(unit_input * unit["weights"], dim=1) + unit["bias"])
            hidden_outputs.append(h.unsqueeze(1))

        if hidden_outputs:
            return torch.cat([x] + hidden_outputs, dim=1)
        return x

    def add_hidden_unit(self, candidate_steps=None, pool_size=None):
        """Add a new cascade hidden unit with trained weights.

        .. deprecated::
            Not called in the production training loop (_training_loop).
            Retained as a convenience method for unit tests. The production
            path uses train_candidate_pool() + install_candidate() separately.

        Trains a pool of candidate units via Pearson correlation maximization
        (matching the real CasCor candidate training phase), selects the best,
        and installs it. After installation, output layer is expanded and
        retrained for OUTPUT_RETRAIN_STEPS full-batch steps. Returns the best
        correlation, or None if no candidate met the quality threshold.

        Args:
            candidate_steps: Override for per-candidate training steps (default: CANDIDATE_TRAINING_STEPS).
            pool_size: Override for candidate pool size (default: CANDIDATE_POOL_SIZE).
        """
        hidden_id = len(self.hidden_units)
        input_dim = self.input_size + hidden_id

        best_unit = None
        best_correlation = -1.0

        # This method is retained only as a convenience for unit tests (not used in
        # the production training loop). Use modest defaults that finish quickly.
        if candidate_steps is None:
            candidate_steps = 50
        if pool_size is None:
            pool_size = 8

        # Train a pool of candidates and select the best (matching CasCor pool)
        for _ in range(pool_size):
            # Xavier-scale init: std = 1/sqrt(input_dim) to keep pre-activation
            # variance constant as cascade depth grows (prevents tanh saturation)
            init_std = 1.0 / math.sqrt(input_dim)
            unit = {
                "id": hidden_id,
                "weights": torch.randn(input_dim) * init_std,
                "bias": torch.randn(1) * init_std,
                "activation_fn": torch.tanh,
            }

            # Train candidate weights to maximize correlation with residual error
            if self.train_x is not None and self.train_y is not None:
                correlation = self._train_candidate(unit, steps=candidate_steps, lr=0.01)
                if correlation > best_correlation:
                    best_correlation = correlation
                    best_unit = unit
            else:
                best_unit = unit
                break

        if best_unit is None:
            return None

        # Correlation threshold guard — don't install noise-level candidates
        # (matches production CasCor's correlation_threshold check).
        # Only applies when training data is available (candidates were actually trained).
        if self.train_x is not None and best_correlation < TrainingConstants.MIN_CANDIDATE_CORRELATION:
            return None

        # Delegate to install_candidate (preserves optimizer momentum)
        self.install_candidate(best_unit)

        # Retrain output with full-batch for OUTPUT_RETRAIN_STEPS steps
        for _ in range(TrainingConstants.OUTPUT_RETRAIN_STEPS):
            self.train_output_step()

        return best_correlation

    def train_candidate_pool(self, min_correlation: float = None, stop_check=None, progress_callback=None, pool_size: int = None, candidate_steps: int = None):
        """Train a pool of candidate units and return the best if it meets quality threshold.

        This method does NOT modify shared network state (hidden_units, output_layer)
        and is safe to call without holding the DemoMode lock.

        Args:
            min_correlation: Minimum correlation threshold. If None, uses
                TrainingConstants.MIN_CANDIDATE_CORRELATION.
            stop_check: Optional callable returning True if training should abort.
                Used to propagate stop signals from the training thread.
            progress_callback: Optional callable(candidate_index, pool_size, best_correlation)
                called after each candidate finishes training. Used for dashboard updates.
            pool_size: Override for candidate pool size (default: CANDIDATE_POOL_SIZE).
            candidate_steps: Override for per-candidate training steps (default: CANDIDATE_TRAINING_STEPS).

        Returns:
            Tuple of (unit_dict, best_correlation) if a quality candidate was found,
            or None if no candidate met the threshold or stop was requested.
        """
        if min_correlation is None:
            min_correlation = TrainingConstants.MIN_CANDIDATE_CORRELATION

        hidden_id = len(self.hidden_units)
        input_dim = self.input_size + hidden_id

        best_unit = None
        best_correlation = -1.0

        if pool_size is None:
            pool_size = TrainingConstants.CANDIDATE_POOL_SIZE
        if candidate_steps is None:
            candidate_steps = TrainingConstants.CANDIDATE_TRAINING_STEPS
        for i in range(pool_size):
            if stop_check and stop_check():
                return None

            init_std = 1.0 / math.sqrt(input_dim)
            unit = {
                "id": hidden_id,
                "weights": torch.randn(input_dim) * init_std,
                "bias": torch.randn(1) * init_std,
                "activation_fn": torch.tanh,
            }

            if self.train_x is not None and self.train_y is not None:
                correlation = self._train_candidate(unit, steps=candidate_steps, lr=0.01)
                if correlation > best_correlation:
                    best_correlation = correlation
                    best_unit = unit
            else:
                best_unit = unit
                break

            if progress_callback:
                progress_callback(i, pool_size, best_correlation)

        if best_unit is None:
            return None

        if self.train_x is not None and best_correlation < min_correlation:
            return None

        return (best_unit, best_correlation)

    def install_candidate(self, unit: dict):
        """Install a trained candidate unit into the network.

        Appends the unit to hidden_units, expands the output layer, and creates
        an optimizer that preserves momentum for existing weights. This method
        modifies shared network state and should be called under lock protection.

        Args:
            unit: Trained candidate unit dict with 'weights', 'bias', 'activation_fn'.
        """
        # Save old optimizer state before replacing the layer — needed to
        # transfer momentum into the new optimizer and avoid Adam bias
        # correction overshoot (~1000x amplification on first step).
        old_weight = self.output_layer.weight
        old_bias = self.output_layer.bias
        old_weight_state = self.output_optimizer.state.get(old_weight, {})
        old_bias_state = self.output_optimizer.state.get(old_bias, {})

        self.hidden_units.append(unit)

        old_layer = self.output_layer
        new_dim = self.input_size + len(self.hidden_units)
        self.output_layer = torch.nn.Linear(new_dim, self.output_size)
        with torch.no_grad():
            self.output_layer.weight[:, : old_layer.in_features] = old_layer.weight
            self.output_layer.bias[:] = old_layer.bias
            self.output_layer.weight[:, old_layer.in_features :] = torch.randn(self.output_size, new_dim - old_layer.in_features) * TrainingConstants.OUTPUT_WEIGHT_INIT_STD

        self.output_optimizer = torch.optim.Adam(self.output_layer.parameters(), lr=self.learning_rate)

        # Transfer old momentum/variance for preserved weight columns so the
        # optimizer continues smoothly instead of overshooting.  New column
        # (for the just-installed hidden unit) starts with zero moments.
        if old_weight_state:
            old_dim = old_layer.in_features
            new_weight = self.output_layer.weight
            weight_state = {
                "step": old_weight_state["step"].clone(),
                "exp_avg": torch.zeros_like(new_weight),
                "exp_avg_sq": torch.zeros_like(new_weight),
            }
            weight_state["exp_avg"][:, :old_dim] = old_weight_state["exp_avg"]
            weight_state["exp_avg_sq"][:, :old_dim] = old_weight_state["exp_avg_sq"]
            self.output_optimizer.state[new_weight] = weight_state

        if old_bias_state:
            self.output_optimizer.state[self.output_layer.bias] = {
                "step": old_bias_state["step"].clone(),
                "exp_avg": old_bias_state["exp_avg"].clone(),
                "exp_avg_sq": old_bias_state["exp_avg_sq"].clone(),
            }

    def compute_metrics(self):
        """Compute current loss and accuracy from real network predictions.

        Returns:
            Tuple of (loss, accuracy). Returns (1.0, 0.5) if no training data.
        """
        if self.train_x is None or self.train_y is None:
            return 1.0, 0.5

        with torch.no_grad():
            self.output_layer.eval()
            predictions = self.forward(self.train_x)
            self.output_layer.train()
            mse = float(((predictions - self.train_y) ** 2).mean())
            accuracy = float(((predictions > 0.5).float() == self.train_y).float().mean())
        return mse, accuracy

    def _train_candidate(self, unit: dict, steps: int = 600, lr: float = 0.01):
        """Train a candidate hidden unit to maximize Pearson correlation with residual.

        Uses PyTorch autograd and Adam optimizer for gradient computation,
        matching the real CasCor implementation. Correlation is normalized
        by the product of standard deviations (Pearson correlation coefficient).
        Includes gradient clipping and early stopping with best-weight tracking.

        Args:
            unit: The candidate unit dict with 'weights', 'bias', 'activation_fn'.
            steps: Maximum number of optimization steps.
            lr: Learning rate for candidate Adam optimizer.

        Returns:
            Best absolute Pearson correlation value (float).
        """
        x = self.train_x
        y = self.train_y

        # Current network prediction (before this unit is added)
        with torch.no_grad():
            current_pred = self.forward(x)
        residual = (y - current_pred).detach()

        # Build the input this candidate unit will receive
        with torch.no_grad():
            candidate_input = self._cascade_features(x)

        # Wrap candidate weights as Parameters for autograd + Adam
        weights = torch.nn.Parameter(unit["weights"].clone())
        bias = torch.nn.Parameter(unit["bias"].clone())
        optimizer = torch.optim.Adam([weights, bias], lr=lr)

        best_correlation = 0.0
        patience_counter = 0
        best_weights = unit["weights"].clone()
        best_bias = unit["bias"].clone()

        for _ in range(steps):
            optimizer.zero_grad()

            # Forward through candidate unit
            z = candidate_input @ weights + bias
            v = torch.tanh(z)

            # Pearson correlation (normalized by std product)
            v_centered = v - v.mean()
            e_centered = residual - residual.mean(dim=0)
            cov = (v_centered.unsqueeze(1) * e_centered).sum(dim=0)
            std_v = torch.sqrt((v_centered**2).sum() + 1e-8)
            std_e = torch.sqrt((e_centered**2).sum(dim=0) + 1e-8)
            correlation = (cov / (std_v * std_e)).abs().sum()

            # Maximize correlation (minimize negative)
            (-correlation).backward()
            optimizer.step()

            # Early stopping with best-weight tracking
            abs_corr = float(correlation.detach())
            if abs_corr > best_correlation:
                best_correlation = abs_corr
                patience_counter = 0
                best_weights = weights.detach().clone()
                best_bias = bias.detach().clone()
            else:
                patience_counter += 1
                if patience_counter >= TrainingConstants.CANDIDATE_PATIENCE:
                    break

        # Store best weights (not final — may have overshot)
        unit["weights"] = best_weights
        unit["bias"] = best_bias

        return best_correlation

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass using cascade-correlation architecture.

        Each hidden unit receives [original inputs + all previous hidden outputs].
        Output layer maps [inputs + all hidden outputs] through nn.Linear.

        Args:
            x: Input tensor of shape (batch_size, input_size)

        Returns:
            Output predictions of shape (batch_size, output_size)
        """
        features = self._cascade_features(x)
        output: torch.Tensor = self.output_layer(features)
        return output

    def train_output_step(self, batch_size: Optional[int] = None):
        """Perform one gradient step on the output layer using Adam optimizer.

        Uses nn.Linear + MSELoss + Adam optimizer, matching the real CasCor
        algorithm. Defaults to full-batch training. Hidden unit weights remain
        frozen (not wrapped as Parameters).

        Args:
            batch_size: Number of samples per batch. None = full batch (default).
        """
        if self.train_x is None or self.train_y is None:
            return

        # Select batch
        n_samples = self.train_x.shape[0]
        if batch_size is not None and n_samples > batch_size:
            indices = torch.randperm(n_samples)[:batch_size]
            batch_x = self.train_x[indices]
            batch_y = self.train_y[indices]
        else:
            batch_x = self.train_x
            batch_y = self.train_y

        # Build features (no grad for frozen hidden units)
        with torch.no_grad():
            features = self._cascade_features(batch_x)

        # Forward through output layer with autograd
        self.output_optimizer.zero_grad()
        predictions = self.output_layer(features)
        loss = self.loss_fn(predictions, batch_y)
        loss.backward()
        self.output_optimizer.step()


class DemoMode:
    """
    Demo mode manager for Juniper Canopy.

    Simulates realistic training behavior without actual neural network:
    - Generates synthetic datasets (spiral, XOR, etc.)
    - Simulates training with realistic loss curves
    - Periodically adds cascade units
    - Broadcasts updates via WebSocket
    """

    def __init__(self, update_interval: float = None):
        """
        Initialize demo mode with config-driven simulation parameters.

        Args:
            update_interval: Time between simulated epochs (seconds)
        """
        self.logger = logging.getLogger(__name__)

        # Load settings for demo configuration
        _settings = get_settings()
        training_defaults = _settings.get_training_defaults()

        self.update_interval = update_interval if update_interval is not None else _settings.demo_update_interval

        # Create mock network
        self.network = MockCascorNetwork(input_size=2, output_size=1)

        # Generate demo dataset — fall back to local generation if JuniperData
        # is unreachable (e.g., Docker standalone, CI smoke test).
        try:
            self.dataset = self._generate_spiral_dataset(n_samples=200)
        except Exception as exc:
            self.logger.warning("JuniperData dataset generation failed (%s), falling back to local generation", exc)
            self.dataset = self._generate_spiral_dataset_local(n_samples=200)
        self.network.train_x = self.dataset["inputs_tensor"]
        self.network.train_y = self.dataset["targets_tensor"]

        # Training simulation state
        self.current_epoch = 0
        self.current_loss = 1.0
        self.current_accuracy = 0.5
        self.is_running = False
        self.thread: Optional[threading.Thread] = None

        # Thread safety
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._pause = threading.Event()

        self.max_epochs = int(training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS))
        self.max_hidden_units = int(training_defaults.get("hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS))
        # DEPRECATED: cascade_every, convergence_enabled, convergence_threshold, and
        # _cascade_cooldown_remaining are vestigial from the pre-Phase-6C epoch-based
        # cascade trigger (_should_add_cascade_unit). The production _training_loop uses
        # candidate correlation threshold instead. Retained for test compatibility.
        self.cascade_every = _settings.demo_cascade_every
        self.convergence_enabled = TrainingConstants.DEFAULT_CONVERGENCE_ENABLED
        self.convergence_threshold = TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD
        self._cascade_cooldown_remaining = 0

        # Spiral dataset parameter
        self.spiral_rotations = TrainingConstants.DEFAULT_SPIRAL_ROTATIONS

        # Cascade event markers for loss chart (epoch, unit_index, correlation)
        self.cascade_events: List[Dict[str, Any]] = []

        # Cascade growth counter — incremented in _training_loop after each
        # candidate install. Mirrored to TrainingState.grow_iteration. Also reset
        # in _reset_state_and_history(); declared here so get_current_state()
        # is safe before start() is called.
        self.current_iteration: int = 0

        # Phase 3 progress fields (mirror cascor TrainingState semantics so the
        # canopy progress UI displays non-zero values during demo training).
        # See juniper-ml/notes/code-review/CANOPY_CASCOR_INTERFACE_ROADMAP_2026-04-08.md §5.
        self._best_correlation_state: float = 0.0
        self._candidates_trained_count: int = 0
        self._candidates_total_count: int = 0
        self._phase_detail: str = ""
        self._phase_started_at: str = ""

        # Metrics buffer for realistic curves
        self.metrics_history: deque = deque(maxlen=TrainingConstants.METRICS_HISTORY_MAXLEN)

        self.logger.info(
            "DemoMode configuration: max_epochs=%s, max_hidden_units=%s, cascade_every=%s, update_interval=%ss",
            self.max_epochs,
            self.max_hidden_units,
            self.cascade_every,
            self.update_interval,
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

    # CONC-08 (Phase 3C): `self.is_running` is touched from at least three
    # contexts — the API control endpoints (start/stop/pause/resume/reset),
    # the demo training thread itself (which clears it on completion or stop),
    # and the regenerate_dataset path. Pre-fix sites were inconsistently
    # locked: writes inside the training thread used `with self._lock:` while
    # the API-side checks (`if self.is_running ...`) and the
    # `was_running := self.is_running` walrus read it without the lock,
    # leaving classic check-then-act races. The `running` property and
    # `_set_running` helper below give every caller a single locked path so
    # the field is read and written under `self._lock` consistently. The
    # underlying `self.is_running` attribute is kept (rather than promoted to
    # a property) so existing test code that introspects it as a plain field
    # keeps working; the helpers are for the production code paths that
    # actually run in the racing contexts.
    @property
    def running(self) -> bool:
        """Thread-safe read of `is_running`."""
        with self._lock:
            return self.is_running

    def _set_running(self, value: bool) -> None:
        """Thread-safe write of `is_running`."""
        with self._lock:
            self.is_running = value

    def _initialize_training_state(self):
        """Initialize TrainingState with demo values."""
        if self.training_state:
            ds_name = self.dataset.get("dataset_name", "Spiral2D") if hasattr(self, "dataset") and self.dataset else "Spiral2D"
            ds_version = self.dataset.get("dataset_version", 0) if hasattr(self, "dataset") and self.dataset else 0
            self.training_state.update_state(
                status="Stopped",
                phase="Idle",
                learning_rate=0.01,
                max_hidden_units=self.max_hidden_units,
                max_epochs=self.max_epochs,
                current_epoch=0,
                current_step=0,
                network_name="MockCascorNetwork",
                dataset_name=ds_name,
                dataset_version=ds_version,
                threshold_function="tanh",
                optimizer_name="Adam",
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

        ds_name = self.dataset.get("dataset_name", "Spiral2D") if hasattr(self, "dataset") and self.dataset else "Spiral2D"
        ds_version = self.dataset.get("dataset_version", 0) if hasattr(self, "dataset") and self.dataset else 0
        self.training_state.update_state(
            status=status,
            phase=phase,
            learning_rate=self.network.learning_rate,
            max_hidden_units=self.max_hidden_units,
            max_epochs=self.max_epochs,
            current_epoch=self.current_epoch,
            current_step=self.current_epoch,
            network_name="MockCascorNetwork",
            dataset_name=ds_name,
            dataset_version=ds_version,
            threshold_function="tanh",
            optimizer_name="Adam",
            candidate_pool_status=pool_status,
            candidate_pool_phase=pool_phase,
            candidate_pool_size=pool_size,
            top_candidate_id=top_cand_id,
            top_candidate_score=top_cand_score,
            second_candidate_id=second_cand_id,
            second_candidate_score=second_cand_score,
            pool_metrics=pool_metrics,
            # Phase 3 progress fields — mirror cascor TrainingState semantics.
            grow_iteration=self.current_iteration,
            grow_max=self.max_hidden_units,
            best_correlation=self._best_correlation_state,
            candidates_trained=self._candidates_trained_count,
            candidates_total=self._candidates_total_count,
            phase_detail=self._phase_detail,
            phase_started_at=self._phase_started_at,
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
            self.logger.warning("State broadcast failed: %s: %s", type(e).__name__, e)

    def _generate_spiral_dataset(self, n_samples: int = 200, algorithm: Optional[str] = None, n_rotations: Optional[float] = None) -> Dict[str, Any]:
        """
        Generate two-class spiral dataset from JuniperData service.

        JuniperData service is REQUIRED. The JUNIPER_DATA_URL environment variable
        must be set. No local fallback is provided.

        Args:
            n_samples: Number of total samples (split across classes)
            algorithm: Optional algorithm parameter for backward compatibility
            n_rotations: Number of spiral rotations (defaults to self.spiral_rotations)

        Returns:
            Dataset dictionary with keys: inputs, targets, inputs_tensor, targets_tensor,
            num_samples, num_features, num_classes

        Raises:
            JuniperDataConfigurationError: If JUNIPER_DATA_URL is not set
        """
        from juniper_data_client.exceptions import JuniperDataConfigurationError

        juniper_data_url = get_settings().juniper_data_url

        if not juniper_data_url:
            raise JuniperDataConfigurationError("JUNIPER_DATA_URL environment variable is required. " "All datasets must be fetched from the JuniperData service. " "Set JUNIPER_DATA_URL=http://localhost:8100 to connect to a local instance.")

        if n_rotations is None:
            n_rotations = getattr(self, "spiral_rotations", TrainingConstants.DEFAULT_SPIRAL_ROTATIONS)

        self.logger.info("Fetching dataset from JuniperData at %s (n_rotations=%s)", juniper_data_url, n_rotations)
        return self._generate_spiral_dataset_from_juniper_data(n_samples, juniper_data_url, algorithm=algorithm, n_rotations=n_rotations)

    @staticmethod
    def _validate_npz_arrays(npz_data: Dict[str, Any]) -> None:
        """Validate NPZ dataset arrays for dtype, shape, and consistency.

        Args:
            npz_data: Dictionary of numpy arrays from NPZ artifact.

        Raises:
            ValueError: If validation fails (wrong dtype, shape, or mismatched counts).
        """
        inputs = npz_data.get("X_full")
        targets = npz_data.get("y_full")

        if inputs is None or targets is None:
            raise ValueError("JuniperData artifact missing required keys: X_full, y_full")

        if not isinstance(inputs, np.ndarray) or not isinstance(targets, np.ndarray):
            raise ValueError(f"Expected numpy arrays, got X_full={type(inputs).__name__}, y_full={type(targets).__name__}")

        if inputs.dtype != np.float32:
            raise ValueError(f"X_full dtype must be float32, got {inputs.dtype}")

        if inputs.ndim != 2:
            raise ValueError(f"X_full must be 2D (samples, features), got shape {inputs.shape}")

        if inputs.shape[0] != targets.shape[0]:
            raise ValueError(f"Sample count mismatch: X_full has {inputs.shape[0]} samples, y_full has {targets.shape[0]}")

    @staticmethod
    def _user_friendly_data_error(exc: Exception) -> str:
        """Map JuniperData client exceptions to user-friendly messages.

        Args:
            exc: The caught exception.

        Returns:
            A human-readable error message.
        """
        from juniper_data_client.exceptions import (
            JuniperDataClientError,
            JuniperDataConfigurationError,
            JuniperDataConnectionError,
            JuniperDataNotFoundError,
            JuniperDataTimeoutError,
            JuniperDataValidationError,
        )

        error_map = {
            JuniperDataConnectionError: "Cannot connect to JuniperData service. Verify JUNIPER_DATA_URL and that the service is running.",
            JuniperDataTimeoutError: "JuniperData request timed out. The service may be overloaded or unreachable.",
            JuniperDataNotFoundError: "Requested dataset or artifact not found on JuniperData service.",
            JuniperDataValidationError: "JuniperData rejected the request due to invalid parameters.",
            JuniperDataConfigurationError: "JuniperData client is misconfigured. Check JUNIPER_DATA_URL.",
        }

        for exc_type, message in error_map.items():
            if isinstance(exc, exc_type):
                return message

        if isinstance(exc, JuniperDataClientError):
            return f"JuniperData service error: {exc}"

        return f"Unexpected error communicating with JuniperData: {exc}"

    def _generate_spiral_dataset_from_juniper_data(
        self,
        n_samples: int,
        juniper_data_url: str,
        algorithm: Optional[str] = None,
        n_rotations: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate spiral dataset using JuniperData service.

        Includes structured logging for API interactions, exception-to-user-message
        mapping, and NPZ dtype/shape validation.

        Args:
            n_samples: Number of total samples (split across classes)
            juniper_data_url: URL of the JuniperData service
            algorithm: Optional algorithm parameter for backward compatibility
            n_rotations: Number of spiral rotations

        Returns:
            Dataset dictionary

        Raises:
            JuniperDataClientError: If the JuniperData request fails
            ValueError: If NPZ validation fails
        """
        from juniper_data_client import JuniperDataClient
        from juniper_data_client.exceptions import JuniperDataClientError

        from observability import build_data_client_request_hook

        # METRICS-MON R4.3 / seed-13: pass the Prometheus-emitting hook
        # so every outbound HTTP call from this client instance bumps
        # ``juniper_canopy_data_client_requests_total`` +
        # ``juniper_canopy_data_client_request_duration_ms``. The hook
        # is built fresh per client construction so test-side resets of
        # ``_canopy_metrics`` see a usable closure on the next call.
        client = JuniperDataClient(
            base_url=juniper_data_url,
            on_request=build_data_client_request_hook(),
        )

        params: Dict[str, Any] = {
            "n_points_per_spiral": n_samples // 2,
            "n_spirals": 2,
            "noise": 0.1,
            "seed": 42,
        }
        if n_rotations is not None:
            params["n_rotations"] = float(n_rotations)
        if algorithm is not None:
            params["algorithm"] = algorithm

        try:
            t0 = time.monotonic()
            response = client.create_dataset(
                generator="spiral",
                params=params,
                persist=True,
            )
            create_ms = (time.monotonic() - t0) * 1000
            self.logger.info("JuniperData create_dataset completed", extra={"latency_ms": f"{create_ms:.1f}", "url": juniper_data_url})
        except JuniperDataClientError as exc:
            msg = self._user_friendly_data_error(exc)
            self.logger.error("JuniperData create_dataset failed: %s (raw: %s)", msg, exc, extra={"url": juniper_data_url})
            raise

        dataset_id = response.get("dataset_id")
        if not dataset_id:
            raise ValueError("JuniperData response missing dataset_id")

        try:
            t0 = time.monotonic()
            npz_data = client.download_artifact_npz(dataset_id)
            download_ms = (time.monotonic() - t0) * 1000
            self.logger.info("JuniperData download_artifact_npz completed", extra={"latency_ms": f"{download_ms:.1f}", "dataset_id": dataset_id})
        except JuniperDataClientError as exc:
            msg = self._user_friendly_data_error(exc)
            self.logger.error("JuniperData download_artifact_npz failed: %s (raw: %s)", msg, exc, extra={"dataset_id": dataset_id})
            raise

        self._validate_npz_arrays(npz_data)

        inputs = npz_data["X_full"]
        targets_one_hot = npz_data["y_full"]

        targets = np.argmax(targets_one_hot, axis=1).astype(np.float32)

        # Normalize inputs to [-1, 1] (prevents activation saturation with large-range data)
        inputs_tensor = torch.from_numpy(inputs).float()
        input_min = inputs_tensor.min(dim=0).values
        input_max = inputs_tensor.max(dim=0).values
        inputs_tensor = 2.0 * (inputs_tensor - input_min) / (input_max - input_min + 1e-8) - 1.0

        # Store normalization params on network for decision boundary use
        if hasattr(self, "network") and self.network is not None:
            self.network._input_min = input_min
            self.network._input_max = input_max

        self.logger.info("Generated spiral dataset via JuniperData: %s samples (normalized to [-1, 1])", len(inputs))

        # Extract versioning metadata from response (if present)
        meta = response.get("meta", {})
        result = {
            "inputs": inputs,
            "targets": targets,
            "inputs_tensor": inputs_tensor,
            "targets_tensor": torch.from_numpy(targets).float().unsqueeze(1),
            "num_samples": len(inputs),
            "num_features": inputs.shape[1] if len(inputs.shape) > 1 else 2,
            "num_classes": 2,
        }
        if "dataset_name" in meta:
            result["dataset_name"] = meta["dataset_name"]
        if "dataset_version" in meta:
            result["dataset_version"] = meta["dataset_version"]

        return result

    def _generate_spiral_dataset_local(self, n_samples: int = 200) -> Dict[str, Any]:
        """
        Generate two-class spiral dataset locally.

        .. deprecated::
            This method is deprecated and will be removed in a future release.
            Dataset generation is now handled by the JuniperData service.

        Args:
            n_samples: Number of samples per class

        Returns:
            Dataset dictionary
        """
        import warnings

        warnings.warn(
            "DemoMode._generate_spiral_dataset_local() is deprecated and will be removed in a future release. " "Dataset generation is now handled by the JuniperData service.",
            DeprecationWarning,
            stacklevel=2,
        )

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
        Perform one training epoch — real gradient step with real metrics.

        Trains the output layer weights via ``train_output_step()`` (full-batch)
        and then computes the actual loss and accuracy from the network's
        predictions on the training data.

        Returns:
            Tuple of (loss, accuracy)
        """
        # Perform an actual weight update (full-batch, inline)
        with self._lock:
            self.network.train_output_step()

        # Compute real metrics from network predictions
        with self._lock, torch.no_grad():
            if self.network.train_x is not None and self.network.train_y is not None:
                self.network.output_layer.eval()
                predictions = self.network.forward(self.network.train_x)
                self.network.output_layer.train()
                # MSE loss (matching CasCor algorithm)
                mse = ((predictions - self.network.train_y) ** 2).mean()
                self.current_loss = float(mse)
                # Classification accuracy (threshold at 0.5 for {0,1} targets)
                pred_classes = (predictions > 0.5).float()
                self.current_accuracy = float((pred_classes == self.network.train_y).float().mean())
            else:
                # Fallback if no training data
                self.current_loss = 1.0
                self.current_accuracy = 0.5

        return self.current_loss, self.current_accuracy

    def _simulate_candidate_pool(self):
        """Simulate candidate pool training with synthetic data."""
        if not self.candidate_pool:
            return

        # Activate pool (match actual training pool size)
        pool_size = TrainingConstants.CANDIDATE_POOL_SIZE
        self.candidate_pool.update_pool(
            status="Active",
            phase="Training",
            size=pool_size,
            iterations=len(self.network.hidden_units),
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

    # DEPRECATED: _should_add_cascade_unit is not called by the production
    # _training_loop (which uses candidate correlation threshold). Retained
    # for test compatibility only.
    def _should_add_cascade_unit(self) -> bool:
        """
        Determine if a cascade unit should be added using convergence-based criteria.

        .. deprecated::
            Not called in the production training loop (_training_loop).
            The two-phase loop (Phase 6C) replaced epoch-based cascade triggers
            with continuous candidate pool training. cascade_every is also unused.
            Retained for test coverage compatibility.

        When convergence detection is enabled, adds a hidden unit when the loss
        improvement over the last 10 epochs falls below ``self.convergence_threshold``.
        The fixed schedule (``self.cascade_every``) always acts as a fallback.

        Returns:
            True if should add unit
        """
        # Thread-safe check of max_hidden_units and convergence params
        with self._lock:
            max_units = self.max_hidden_units
            current_units = len(self.network.hidden_units)
            conv_enabled = self.convergence_enabled
            conv_threshold = self.convergence_threshold

            # Post-cascade cooldown: block ALL triggers during cooldown
            if self._cascade_cooldown_remaining > 0:
                self._cascade_cooldown_remaining -= 1
                return False

        if current_units >= max_units:
            return False

        # Convergence-based: check if loss has stopped improving
        if conv_enabled and len(self.network.history["train_loss"]) >= 10:
            recent = list(self.network.history["train_loss"])[-10:]
            improvement = recent[0] - recent[-1]
            if improvement < conv_threshold:
                return True

        # Fallback: fixed schedule as maximum interval
        return self.current_epoch > 0 and self.current_epoch % self.cascade_every == 0

    def _training_loop(self):
        """CasCor two-phase training loop.

        Phase 1: Train output layer on initial network (no hidden units).
        Phase 2: Cascade growth — repeatedly train candidate pool, install best,
                 retrain output layer. Each phase emits periodic metrics for
                 dashboard visualization.

        Lock granularity: candidate training requires NO lock (operates on
        candidate-local state). Installation is a brief locked operation.
        Retrain steps run without lock, with periodic locked metric emissions.
        This ensures get_current_state() returns within ~10ms at any point.
        """
        self.logger.info("Demo training simulation started")

        # Phase 1: Initial output training
        self.state_machine.set_phase(TrainingPhase.OUTPUT)
        self._phase_detail = "training_output"
        self._phase_started_at = datetime.now().isoformat()
        # Initialize last_emit far enough in the past that the first step triggers an emission
        last_emit = time.monotonic() - self.update_interval
        for step in range(TrainingConstants.OUTPUT_RETRAIN_STEPS):
            if self._stop.is_set():
                break

            # Check pause
            while self._pause.is_set() and not self._stop.is_set():
                self._stop.wait(0.1)
            if self._stop.is_set():
                break

            self.network.train_output_step()

            # Step-based metric emission for retrain visibility (time-based fallback)
            now = time.monotonic()
            is_step_emit = (step + 1) % TrainingConstants.OUTPUT_RETRAIN_EMIT_EVERY == 0
            is_final = step == TrainingConstants.OUTPUT_RETRAIN_STEPS - 1
            is_time_emit = now - last_emit >= self.update_interval
            if is_step_emit or is_final or is_time_emit:
                self._emit_training_metrics()
                last_emit = now
                with self._lock:
                    if self.current_epoch >= self.max_epochs:
                        break

        if self._stop.is_set():
            self._set_running(False)  # CONC-08
            self.logger.info("Demo training stopped during initial output training")
            return

        # Check if max_epochs was reached during Phase 1
        phase1_done = False
        with self._lock:
            if self.current_epoch >= self.max_epochs:
                self.logger.info("Training complete: reached max_epochs=%s during initial training", self.max_epochs)
                self.state_machine.mark_completed()
                self.is_running = False
                phase1_done = True
        if phase1_done:
            self._update_training_status()
            return

        # Phase 2: Cascade growth
        while not self._stop.is_set():
            # Check stopping criteria
            with self._lock:
                if len(self.network.hidden_units) >= self.max_hidden_units:
                    self.logger.info("Max hidden units reached (%s)", self.max_hidden_units)
                    break
                if self.current_epoch >= self.max_epochs:
                    self.logger.info("Max epochs reached (%s)", self.max_epochs)
                    break

            # Check pause
            while self._pause.is_set() and not self._stop.is_set():
                self._stop.wait(0.1)
            if self._stop.is_set():
                break

            # Step 2a: Train candidate pool (NO LOCK — candidate-local state only)
            self.state_machine.set_phase(TrainingPhase.CANDIDATE)
            self._phase_detail = "training_candidates"
            self._phase_started_at = datetime.now().isoformat()
            self._candidates_total_count = TrainingConstants.CANDIDATE_POOL_SIZE
            self._candidates_trained_count = 0
            if self.candidate_pool:
                self.candidate_pool.update_pool(
                    status="Active",
                    phase="Training",
                    size=TrainingConstants.CANDIDATE_POOL_SIZE,
                    iterations=0,
                    progress=0.0,
                    target=0.85,
                )

            min_corr = getattr(self, "cn_correlation_threshold", TrainingConstants.MIN_CANDIDATE_CORRELATION)
            last_candidate_emit = [time.monotonic()]  # mutable for closure

            def _candidate_progress(idx, pool_size, best_corr, _emit_tracker=last_candidate_emit):
                """Emit periodic metrics during candidate training for dashboard updates."""
                # Respect pause — wait if paused, don't emit
                while self._pause.is_set() and not self._stop.is_set():
                    self._stop.wait(0.1)
                # Update Phase 3 progress fields visible to the dashboard.
                self._candidates_trained_count = max(0, int(idx) + 1)
                self._candidates_total_count = max(self._candidates_total_count, int(pool_size))
                self._best_correlation_state = float(best_corr)
                now = time.monotonic()
                if now - _emit_tracker[0] >= self.update_interval:
                    self._emit_training_metrics()
                    _emit_tracker[0] = now

            result = self.network.train_candidate_pool(
                min_correlation=min_corr,
                stop_check=self._stop.is_set,
                progress_callback=_candidate_progress,
            )

            if self.candidate_pool:
                self.candidate_pool.update_pool(status="Inactive")
                self.candidate_pool.clear()

            if result is None:
                self.logger.info("No candidate met correlation threshold — stopping cascade growth")
                break

            best_unit, best_correlation = result
            self._best_correlation_state = float(best_correlation)

            # Step 2b: Install candidate (BRIEF LOCK — modifies shared network state)
            with self._lock:
                self.network.install_candidate(best_unit)
                self.current_iteration += 1
                hidden_count = len(self.network.hidden_units)
                unit_index = hidden_count - 1
                epoch_snapshot = self.current_epoch

                # Record cascade event for chart markers
                self.cascade_events.append(
                    {
                        "epoch": epoch_snapshot,
                        "unit_index": unit_index,
                        "correlation": best_correlation,
                    }
                )

            self.logger.info("Installed cascade unit #%s (correlation=%.4f)", unit_index, best_correlation)
            self._broadcast_cascade_add(unit_index, hidden_count, epoch_snapshot)

            # Emit metrics at cascade boundary (unconditional — ensures at least 1 per cycle)
            self._emit_training_metrics()

            # Step 2c: Retrain output layer (NO LOCK per step — only lock for metric emission)
            self.state_machine.set_phase(TrainingPhase.OUTPUT)
            self._phase_detail = "retraining_output"
            self._phase_started_at = datetime.now().isoformat()
            last_retrain_emit = time.monotonic()
            for step in range(TrainingConstants.OUTPUT_RETRAIN_STEPS):
                if self._stop.is_set():
                    break

                # Check pause
                while self._pause.is_set() and not self._stop.is_set():
                    self._stop.wait(0.1)
                if self._stop.is_set():
                    break

                self.network.train_output_step()

                # Step-based metric emission for retrain visibility (time-based fallback)
                now = time.monotonic()
                is_step_emit = (step + 1) % TrainingConstants.OUTPUT_RETRAIN_EMIT_EVERY == 0
                is_final = step == TrainingConstants.OUTPUT_RETRAIN_STEPS - 1
                is_time_emit = now - last_retrain_emit >= self.update_interval
                if is_step_emit or is_final or is_time_emit:
                    self._emit_training_metrics()
                    last_retrain_emit = now
                    with self._lock:
                        if self.current_epoch >= self.max_epochs:
                            break

            # Brief yield between cascade cycles for stop/pause responsiveness
            if self._stop.wait(0.01):
                break

        # Mark completion
        self.state_machine.mark_completed()
        self._update_training_status()
        self._set_running(False)  # CONC-08
        self.logger.info("Demo training simulation completed")

    def _emit_training_metrics(self):
        """Compute real metrics from network state and emit to dashboard.

        Increments the epoch counter, updates history, and broadcasts via WebSocket.
        Acquires the lock briefly for shared state updates only.
        """
        loss, accuracy = self.network.compute_metrics()

        val_loss = loss * 1.1 + np.random.randn() * 0.01
        val_accuracy = accuracy * 0.95 + np.random.randn() * 0.01

        with self._lock:
            self.current_epoch += 1
            self.current_loss = loss
            self.current_accuracy = accuracy
            self.network.current_epoch = self.current_epoch

            self.network.history["train_loss"].append(loss)
            self.network.history["train_accuracy"].append(accuracy)
            self.network.history["val_loss"].append(val_loss)
            self.network.history["val_accuracy"].append(val_accuracy)

            phase_name = self.state_machine.get_phase().name.lower()
            metrics = {
                "epoch": self.current_epoch,
                "iteration": self.current_iteration,
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

        self._broadcast_metrics(metrics)
        self._update_training_status()

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
            self.logger.warning("WebSocket broadcast failed: %s: %s", type(e).__name__, e)

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
            self.logger.warning("WebSocket cascade broadcast failed: %s: %s", type(e).__name__, e)

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

        if self.running and not reset:  # CONC-08
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
        self.current_iteration = 0
        self.current_loss = 1.0
        self.current_accuracy = 0.5
        self.metrics_history.clear()

        # Reset network history
        for key in self.network.history:
            self.network.history[key].clear()
        self.network.hidden_units.clear()
        self.network.current_epoch = 0

        # Reinitialize nn.Linear + fresh optimizer (prevents dimension mismatch
        # after clearing hidden_units and ensures clean optimizer state)
        self.network.output_layer = torch.nn.Linear(self.network.input_size, self.network.output_size)
        torch.nn.init.normal_(self.network.output_layer.weight, std=TrainingConstants.OUTPUT_WEIGHT_INIT_STD)
        torch.nn.init.normal_(self.network.output_layer.bias, std=TrainingConstants.OUTPUT_WEIGHT_INIT_STD)
        self.network.output_optimizer = torch.optim.Adam(self.network.output_layer.parameters(), lr=self.network.learning_rate)

        # Restore convergence parameters, cooldown, and spiral rotations to defaults
        # (DEPRECATED — convergence fields retained for test compatibility only)
        self.convergence_enabled = TrainingConstants.DEFAULT_CONVERGENCE_ENABLED
        self.convergence_threshold = TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD
        self._cascade_cooldown_remaining = 0
        self.cascade_events = []

        # Reset Phase 3 progress fields
        self._best_correlation_state = 0.0
        self._candidates_trained_count = 0
        self._candidates_total_count = 0
        self._phase_detail = ""
        self._phase_started_at = ""
        # Note: spiral_rotations is NOT reset here — it persists across training resets
        # so the user's chosen complexity is preserved. Only explicitly changed via apply_params.

    def stop(self):
        """Stop demo training simulation."""
        # Handle FSM transition
        if not self.state_machine.handle_command(Command.STOP):
            self.logger.error("FSM: Invalid STOP command in current state")
            return

        if not self.running:  # CONC-08
            # Update state even if not running
            # self._update_training_state()
            self._update_training_status()
            return

        # Signal stop
        self._stop.set()

        # Wait for thread to finish
        if self.thread:
            self.thread.join(timeout=BackendConstants.DEMO_THREAD_JOIN_TIMEOUT)
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
        if self.state_machine.get_phase() == TrainingPhase.CANDIDATE and self.state_machine.get_candidate_state() is None:
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

        if not self.running:  # CONC-08
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
                self.logger.info("Restoring candidate state: %s", candidate_state)

        if not self.running:  # CONC-08
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

        if was_running := self.running:  # CONC-08
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
            self.thread.join(timeout=BackendConstants.DEMO_THREAD_JOIN_TIMEOUT)
        self._perform_reset()

    def _perform_reset(self):
        # BUG-CN-01 (Phase 3D): keep `is_running`, `_stop`, and `_pause`
        # transitions atomic by holding `self._lock` across all three. The
        # pre-fix version released the lock between `is_running = False` and
        # the event clears, so the training loop could observe `is_running ==
        # False` while `_stop` was still set — leaving the next start() call
        # racing against a stale stop signal that gets cleared a moment later.
        # Holding the lock keeps the state machine and the threading.Event
        # primitives in sync from the perspective of every reader.
        with self._lock:
            self.is_running = False
            self._stop.clear()
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
            self.logger.warning("WebSocket status broadcast failed: %s: %s", type(e).__name__, e)

    def get_network(self) -> MockCascorNetwork:
        """
        Get mock network instance.

        Returns:
            MockCascorNetwork instance
        """
        return self.network

    def regenerate_dataset(self, n_samples: int = 200, n_spirals: int = 2, noise: float = 0.1, n_rotations: Optional[float] = None) -> Dict[str, Any]:
        """Regenerate the dataset with new parameters and reset the network.

        Args:
            n_samples: Total number of samples.
            n_spirals: Number of spiral arms (passed as context but JuniperData uses n_points_per_spiral).
            noise: Gaussian noise standard deviation.
            n_rotations: Number of spiral rotations.

        Returns:
            New dataset dictionary.
        """
        if self.running:  # CONC-08
            self.stop()

        try:
            self.dataset = self._generate_spiral_dataset(n_samples=n_samples, n_rotations=n_rotations)
        except Exception as exc:
            self.logger.warning("JuniperData dataset generation failed (%s), falling back to local generation", exc)
            self.dataset = self._generate_spiral_dataset_local(n_samples=n_samples)
        # CONC-07/BUG-CN-11: train_x/train_y and the current_* counters are read by
        # the training thread under self._lock; mutating them outside the lock allowed
        # readers to observe a partial state (e.g. new train_x with stale train_y, or
        # a stale epoch counter alongside the freshly assigned dataset). Apply all
        # reset state changes atomically inside the lock. Dataset generation stays
        # outside the lock so the (potentially slow) JuniperData round-trip does not
        # block training-thread state reads.
        with self._lock:
            self.network.train_x = self.dataset["inputs_tensor"]
            self.network.train_y = self.dataset["targets_tensor"]
            self.current_epoch = 0
            self.current_loss = 1.0
            self.current_accuracy = 0.5
            self.metrics_history.clear()
        self.logger.info("Dataset regenerated: n_samples=%s, n_rotations=%s", n_samples, n_rotations)
        return self.dataset

    def import_dataset(self, inputs: Any, targets: Any, source_label: str = "imported") -> Dict[str, Any]:
        """CAN-016b: install a pre-parsed dataset (file upload, URL fetch, etc).

        Caller is responsible for parsing the source format (CSV, JSON, …) into
        2-D numpy float32 inputs and 1-D numpy int targets. We don't wrap that
        in here because callers (REST endpoints, tests) often want to surface
        parse errors to the user before mutation kicks in.

        Mirrors ``regenerate_dataset``'s lock discipline — dataset construction
        outside the lock, atomic commit of ``train_x`` / ``train_y`` /
        counters / metrics_history.clear() inside the lock so the training
        thread never observes a half-replaced dataset (CONC-07/BUG-CN-11).

        Args:
            inputs: 2-D numpy.ndarray of shape (n_samples, n_features), float32 preferred.
            targets: 1-D numpy.ndarray of shape (n_samples,), int dtype.
            source_label: short tag for logging / dataset.metadata; e.g. "upload:foo.csv".

        Returns:
            Dataset dict matching the shape produced by ``_generate_spiral_dataset``.

        Raises:
            ValueError: shape mismatch, empty arrays, or dtype that can't be coerced.
        """
        import numpy as np
        import torch

        inputs_arr = np.asarray(inputs)
        targets_arr = np.asarray(targets)
        if inputs_arr.ndim != 2 or inputs_arr.shape[0] == 0:
            raise ValueError(f"inputs must be 2-D with at least 1 row; got shape {inputs_arr.shape}")
        if targets_arr.ndim != 1 or targets_arr.shape[0] != inputs_arr.shape[0]:
            raise ValueError(f"targets must be 1-D with length matching inputs; got shape {targets_arr.shape} vs inputs {inputs_arr.shape}")

        inputs_f32 = inputs_arr.astype(np.float32, copy=False)
        try:
            targets_i = targets_arr.astype(np.int64, copy=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"targets could not be coerced to integer labels: {exc}") from exc

        if self.running:  # CONC-08: stop training before swapping the dataset.
            self.stop()

        inputs_tensor = torch.from_numpy(inputs_f32)
        targets_tensor = torch.from_numpy(targets_i)
        new_dataset = {
            "inputs": inputs_f32.tolist(),
            "targets": targets_i.tolist(),
            "inputs_tensor": inputs_tensor,
            "targets_tensor": targets_tensor,
            "n_samples": int(inputs_f32.shape[0]),
            "n_features": int(inputs_f32.shape[1]),
            "n_classes": int(targets_i.max()) + 1 if targets_i.size > 0 else 0,
            "source": source_label,
        }

        with self._lock:
            self.dataset = new_dataset
            self.network.train_x = inputs_tensor
            self.network.train_y = targets_tensor
            self.current_epoch = 0
            self.current_loss = 1.0
            self.current_accuracy = 0.5
            self.metrics_history.clear()

        self.logger.info(
            "Dataset imported (%s): n_samples=%d, n_features=%d, n_classes=%d",
            source_label,
            new_dataset["n_samples"],
            new_dataset["n_features"],
            new_dataset["n_classes"],
        )
        return new_dataset

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
            state = {
                "is_running": self.is_running,
                "is_paused": self._pause.is_set(),
                "current_epoch": self.current_epoch,
                "current_loss": self.current_loss,
                "current_accuracy": self.current_accuracy,
                "hidden_units": len(self.network.hidden_units),
                "metrics_count": len(self.metrics_history),
                "activation_fn": "tanh",
                "optimizer": "Adam",
                "convergence_enabled": self.convergence_enabled,
                "convergence_threshold": self.convergence_threshold,
                "spiral_rotations": self.spiral_rotations,
                "cascade_events": list(self.cascade_events),
                # Phase 3 progress fields — kept in sync with self.training_state
                # by _update_candidate_pool_state() so consumers reading either
                # source see the same values.
                "grow_iteration": self.current_iteration,
                "grow_max": self.max_hidden_units,
                "best_correlation": self._best_correlation_state,
                "candidates_trained": self._candidates_trained_count,
                "candidates_total": self._candidates_total_count,
                "phase_detail": self._phase_detail,
                "phase_started_at": self._phase_started_at,
            }
            # Include dataset versioning metadata when available
            if hasattr(self, "dataset") and self.dataset:
                if "dataset_name" in self.dataset:
                    state["dataset_name"] = self.dataset["dataset_name"]
                if "dataset_version" in self.dataset:
                    state["dataset_version"] = self.dataset["dataset_version"]
            return state

    def apply_params(
        self,
        learning_rate: Optional[float] = None,
        max_hidden_units: Optional[int] = None,
        max_epochs: Optional[int] = None,
        convergence_enabled: Optional[bool] = None,
        convergence_threshold: Optional[float] = None,
        spiral_rotations: Optional[float] = None,
        **kwargs,
    ):
        """
        Apply parameter changes to demo mode.

        Args:
            learning_rate: New learning rate value (backward compat)
            max_hidden_units: New max hidden units constraint (backward compat)
            max_epochs: New maximum epochs limit (backward compat)
            convergence_enabled: Enable/disable convergence-based cascade addition (backward compat)
            convergence_threshold: Loss improvement threshold for convergence detection (backward compat)
            spiral_rotations: Number of spiral rotations for dataset generation (backward compat)
            **kwargs: Additional nn_* and cn_* prefixed parameters
        """
        # Map prefixed keys to legacy positional args for backward compat
        if learning_rate is None and "nn_learning_rate" in kwargs:
            learning_rate = kwargs.pop("nn_learning_rate")
        if max_hidden_units is None and "nn_max_hidden_units" in kwargs:
            max_hidden_units = kwargs.pop("nn_max_hidden_units")
        if max_epochs is None and "nn_max_total_epochs" in kwargs:
            max_epochs = kwargs.pop("nn_max_total_epochs")
        if convergence_threshold is None and "nn_growth_convergence_threshold" in kwargs:
            convergence_threshold = kwargs.pop("nn_growth_convergence_threshold")
        if spiral_rotations is None and "nn_spiral_rotations" in kwargs:
            spiral_rotations = kwargs.pop("nn_spiral_rotations")

        with self._lock:
            if learning_rate is not None:
                self.network.learning_rate = learning_rate
                # Update Adam optimizer's learning rate to take effect immediately
                for param_group in self.network.output_optimizer.param_groups:
                    param_group["lr"] = learning_rate
                self.logger.info("Demo mode: learning_rate set to %s", learning_rate)

            if max_hidden_units is not None:
                self.max_hidden_units = max_hidden_units
                self.logger.info("Demo mode: max_hidden_units set to %s", max_hidden_units)

            if max_epochs is not None:
                self.max_epochs = int(max_epochs)
                self.logger.info("Demo mode: max_epochs set to %s", max_epochs)

            if convergence_enabled is not None:
                self.convergence_enabled = bool(convergence_enabled)
                self.logger.info("Demo mode: convergence_enabled set to %s", self.convergence_enabled)

            if convergence_threshold is not None:
                self.convergence_threshold = max(
                    TrainingConstants.MIN_CONVERGENCE_THRESHOLD,
                    min(float(convergence_threshold), TrainingConstants.MAX_CONVERGENCE_THRESHOLD),
                )
                self.logger.info("Demo mode: convergence_threshold set to %s", self.convergence_threshold)

            if spiral_rotations is not None:
                new_rotations = max(
                    TrainingConstants.MIN_SPIRAL_ROTATIONS,
                    min(float(spiral_rotations), TrainingConstants.MAX_SPIRAL_ROTATIONS),
                )
                if new_rotations != self.spiral_rotations:
                    self.spiral_rotations = new_rotations
                    self.logger.info("Demo mode: spiral_rotations set to %s — regenerating dataset", self.spiral_rotations)
                    # Regenerate dataset with new rotation count and reset training
                    try:
                        self.dataset = self._generate_spiral_dataset(n_samples=200, n_rotations=self.spiral_rotations)
                    except Exception as exc:
                        self.logger.warning("JuniperData dataset regeneration failed (%s), falling back to local generation", exc)
                        self.dataset = self._generate_spiral_dataset_local(n_samples=200)
                    self.network.train_x = self.dataset["inputs_tensor"]
                    self.network.train_y = self.dataset["targets_tensor"]
                    self._reset_state_and_history()

            # ── Store nn_* prefixed parameters ──
            nn_param_map = {
                "nn_max_iterations": int,
                "nn_max_total_epochs": int,
                "nn_learning_rate": float,
                "nn_max_hidden_units": int,
                "nn_multi_node_layers": bool,
                "nn_growth_trigger": str,
                "nn_growth_preset_epochs": int,
                "nn_growth_convergence_threshold": float,
                "nn_patience": int,
                "nn_spiral_rotations": float,
                "nn_spiral_number": int,
                "nn_dataset_elements": int,
                "nn_dataset_noise": float,
            }

            # ── Store cn_* prefixed parameters ──
            cn_param_map = {
                "cn_pool_size": int,
                "cn_correlation_threshold": float,
                "cn_selected_candidates": int,
                "cn_patience": int,
                "cn_training_complete": str,
                "cn_training_iterations": int,
                "cn_training_convergence_threshold": float,
                "cn_multi_candidate": bool,
                "cn_candidate_selection": str,
                "cn_top_candidates": int,
                "cn_random_candidates": int,
            }

            for param_name, cast_fn in {**nn_param_map, **cn_param_map}.items():
                if param_name in kwargs and kwargs[param_name] is not None:
                    value = cast_fn(kwargs[param_name])
                    setattr(self, param_name, value)
                    self.logger.info("Demo mode: %s set to %s", param_name, value)

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


def get_demo_mode(update_interval: float = None) -> DemoMode:
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
        # Run for the configured demo main loop sleep period
        time.sleep(BackendConstants.DEMO_MAIN_LOOP_SLEEP)
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
