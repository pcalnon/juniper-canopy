#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     cascor_integration.py
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This file contains the code to integrate the Cascade Correlation Neural Network prototype
#       with the Juniper prototype Frontend for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#
# CasCor Integration Module
#
# Provides integration layer between CasCor neural network prototype
# and the frontend monitoring system.
#
# This module handles:
# - Dynamic import of CasCor backend modules
# - Network instantiation and configuration
# - Method wrapping for monitoring hooks
# - Real-time metrics extraction
# - Network topology extraction
# - Background monitoring thread for epoch-level updates
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
import contextlib
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple, Union

import numpy as np
import torch

from config_manager import ConfigManager

# from .data_adapter import DataAdapter, NetworkTopology
from .data_adapter import DataAdapter
from .training_monitor import TrainingMonitor


class CascorIntegration:
    """
    Description:
        Integration layer for CasCor neural network monitoring.
    Provides:
    - Dynamic import of CasCor backend classes
    - Network instantiation with configuration
    - Method wrapping for monitoring hooks
    - Real-time metric extraction and streaming
    - Network topology visualization
    - Dataset management
    Usage:
        integration = CascorIntegration()
        network = integration.create_network(config={...})
        integration.install_monitoring_hooks()
        integration.start_monitoring_thread()
        history = network.fit(x_train, y_train)
    """

    # TODO:  Make sure calling code is passing in valid backend_path
    def __init__(self, backend_path: Optional[str] = None):
        """
        Description:
            Initialize CasCor integration.
        Args:
            backend_path: Path to CasCor backend directory (default: from config)
        Raises: None
        Notes:
            Resolves backend path, imports modules, and initializes adapters.
        Returns: None
        Example:
            integration = CascorIntegration(backend_path="../cascor")
        """
        # TODO: Fix call to logging
        self.logger = logging.getLogger(__name__)

        # Initialize ConfigManager
        self.config_mgr = ConfigManager()

        self.logger.debug(f"Before Resolution CasCor backend path: {backend_path}")
        self.backend_path = self._resolve_backend_path(backend_path)  # Resolve backend path
        self.logger.info(f"CasCor backend path: {self.backend_path}")
        self._add_backend_to_path()  # Add backend to Python path
        self._import_backend_modules()  # Import backend modules
        self.data_adapter = DataAdapter()  # Initialize adapters
        self.training_monitor = TrainingMonitor(self.data_adapter)
        self.network = None  # Network instance (set by create_network or connect_to_network)
        self.cascade_correlation_instance = None  # Alias for compatibility
        self.monitoring_active = False  # Monitoring state
        self.monitoring_thread = None
        # TODO: Make configurable via Constants or config
        self.monitoring_interval = 1.0  # seconds
        self._original_methods = {}  # Original methods (for restoration)
        self.topology_lock = threading.Lock()  # Thread safety for topology extraction
        # CANOPY-P1-003: Add metrics lock for thread-safe metrics extraction
        # Fixes race condition where _monitoring_loop reads network.history while training mutates it
        self.metrics_lock = threading.Lock()  # Thread safety for metrics extraction
        self._shutdown_called = False
        self.logger.info("CascorIntegration initialized successfully")

    def _resolve_backend_path(self, backend_path: Optional[str] = None) -> Path:
        """
        Description:
            Resolve backend path from config or environment variable (cross-platform).
        Args:
            backend_path: Explicit path (highest priority)
        Raises:
            FileNotFoundError: If backend path doesn't exist
        Notes:
            Checks in order:
            1. Provided backend_path argument
            2. CASCOR_BACKEND_PATH environment variable
            3. Configuration file (conf/app_config.yaml)
            4. Default '../cascor' relative to current file
            Supports:
            - Tilde expansion (~/)
            - Environment variables ($VAR, ${VAR})
            - Relative paths (../, ./)
            - Absolute paths
            - Cross-platform (Windows, macOS, Linux)
        Returns:
            Resolved Path object
        Example:
            path = self._resolve_backend_path()
        """
        self.logger.debug(f"Resolving CasCor backend path, initial: {backend_path}")

        # Configuration hierarchy:
        # 1. Provided backend_path argument (highest priority)
        # 2. Environment variable (CASCOR_BACKEND_PATH)
        # 3. YAML configuration (backend.cascor_integration.backend_path)
        # 4. Default '../cascor' (lowest priority)

        path_source = "default"

        if backend_path is None:
            self.logger.debug("No backend_path argument provided, checking environment variable")
            backend_path = os.getenv("CASCOR_BACKEND_PATH")
            if backend_path:
                path_source = "environment"
                self.logger.info(f"Backend path from environment variable: {backend_path}")
        else:
            path_source = "argument"
            self.logger.info(f"Backend path from argument: {backend_path}")

        if backend_path is None:  # Try config
            self.logger.debug("No backend_path in env, checking YAML config")
            backend_path = self.config_mgr.config.get("backend", {}).get("cascor_integration", {}).get("backend_path")
            if backend_path:
                path_source = "config"
                self.logger.info(f"Backend path from YAML config: {backend_path}")

        if backend_path is None:  # Use default
            backend_path = "../cascor"
            path_source = "default"
            self.logger.info(f"Backend path using default: {backend_path}")

        self.logger.debug(f"Final backend path before resolution: {backend_path} (source: {path_source})")

        # Expand environment variables and user home directory (cross-platform)
        backend_path_expanded = os.path.expandvars(backend_path)  # Expand $VAR and ${VAR}
        backend_path_expanded = os.path.expanduser(backend_path_expanded)  # Expand ~

        # Resolve to absolute path
        path = Path(backend_path_expanded).resolve()
        self.logger.debug(f"Resolved backend path: {path}")
        if not path.exists():
            self.logger.error(f"CasCor backend not found at: {path}")
            raise FileNotFoundError(
                f"CasCor backend not found at: {path}\n"
                f"Original path: {backend_path}\n"
                f"Expanded path: {backend_path_expanded}\n"
                f"Please set CASCOR_BACKEND_PATH environment variable or "
                f"update conf/app_config.yaml"
            )
        self.logger.info(f"CasCor backend found at: {path}")
        return path

    def _add_backend_to_path(self):
        """
        Description:
            Add backend src directory to Python path.
        Args: None
        Raises:
            FileNotFoundError: If backend path doesn't exist
        Notes:
            Ensures CasCor backend modules can be imported.
        Returns: None
        Example:
            integration._add_backend_to_path()
        """
        backend_src = self.backend_path / "src"
        if not backend_src.exists():
            raise FileNotFoundError(f"CasCor src directory not found: {backend_src}")
        if str(backend_src) not in sys.path:
            sys.path.insert(0, str(backend_src))
            self.logger.info(f"Added to Python path: {backend_src}")

    # Property aliases for test compatibility
    @property
    def original_fit(self) -> None:
        """
        Description:
            Alias for _original_methods['fit']
        Args: None
        Raises: None
        Notes:
            Provides access to the original fit method before it was wrapped for monitoring.
        Returns:
            Original fit method
        Example:
            original_method = integration.original_fit
        """
        return self._original_methods.get("fit")

    @property
    def original_train_output(self) -> None:
        """
        Description:
            Alias for _original_methods['train_output_layer']
        Args: None
        Raises: None
        Notes:
            Provides access to the original train_output_layer method before it was wrapped for monitoring.
        Returns:
            Original train_output_layer method
        Example:
            original_method = integration.original_train_output
        """
        return self._original_methods.get("train_output_layer")

    @property
    def original_train_candidates(self) -> Callable:
        """
        Description:
            Alias for _original_methods['train_candidates']
        Args: None
        Raises: None
        Notes:
            Provides access to the original train_candidates method before it was wrapped for monitoring.
        Returns:
            Original train_candidates method
        Example:
            original_method = integration.original_train_candidates
        """
        return self._original_methods.get("train_candidates")

    def _import_backend_modules(self) -> None:
        """
        Description:
            Import required modules from CasCor backend.
        Args: None
        Imports:
            - CascadeCorrelationNetwork: Main network class
            - CascadeCorrelationConfig: Configuration class
            - TrainingResults: Results data class (if available)
        Raises:
            ImportError: If backend modules cannot be imported
        Notes:
            - Ensure CasCor backend is properly installed.
            - Check backend path configuration.
        Returns: None
        Example:
            integration = CascorIntegration()
        """
        try:
            # Import main network class
            from cascade_correlation.cascade_correlation import CascadeCorrelationNetwork

            self.cascade_correlation_class = CascadeCorrelationNetwork  # Alias for tests
            self.CascadeCorrelationNetwork = CascadeCorrelationNetwork
            self.logger.info("Imported CascadeCorrelationNetwork")

            # Import configuration class
            from cascade_correlation.cascade_correlation_config.cascade_correlation_config import (
                CascadeCorrelationConfig,
            )

            self.CascadeCorrelationConfig = CascadeCorrelationConfig
            self.cascade_correlation_config_class = CascadeCorrelationConfig  # Alias for tests
            self.logger.info("Imported CascadeCorrelationConfig")

            # Try to import TrainingResults (may not exist)
            try:
                from cascade_correlation.cascade_correlation import TrainingResults

                self.TrainingResults = TrainingResults
                self.logger.info("Imported TrainingResults")
            except ImportError:
                self.TrainingResults = None
                self.logger.debug("TrainingResults not available")
        except ImportError as e:
            raise ImportError(
                f"Failed to import CasCor backend modules: {e}\n"
                f"Backend path: {self.backend_path}\n"
                f"Ensure CasCor prototype is properly installed"
            ) from e

    def create_network(self, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Description:
            Create new CascadeCorrelationNetwork instance. Applies configuration mapping.
        Args:
            config: Configuration dictionary for network:
                - input_size: int - Number of input features
                - output_size: int - Number of output features
                - learning_rate: float - Learning rate
                - output_epochs: int - Epochs for output training
                - candidate_epochs: int - Epochs for candidate training
                - max_hidden_units: int - Maximum hidden units
                - ... (see CascadeCorrelationConfig for full list)
        Raises: None
        Notes:
            Maps common parameter names to backend-specific names.
            Creates and returns a new CascadeCorrelationNetwork instance.
        Returns:
            Initialized CascadeCorrelationNetwork instance
        Example:
            network = integration.create_network(config={
                'input_size': 2,
                'output_size': 1,
                'learning_rate': 0.01,
                'output_epochs': 100
            })
        """
        if config is None:
            config = {}
        self.logger.info(f"Creating network with config: {config}")

        # Map common parameter names to backend-specific names
        config_mapped = config.copy()

        # Map max_epochs -> epochs_max (backend uses epochs_max)
        if "max_epochs" in config_mapped:
            config_mapped["epochs_max"] = config_mapped.pop("max_epochs")

        # Create backend config object
        backend_config = self.CascadeCorrelationConfig(**config_mapped)

        # Create network instance
        self.network = self.CascadeCorrelationNetwork(config=backend_config)
        self.cascade_correlation_instance = self.network  # Alias
        self.logger.info(
            f"Network created: input_size={self.network.input_size}, output_size={self.network.output_size}"
        )
        return self.network

    def connect_to_network(self, network: Any):
        """
        Description:
            Connect to existing CascadeCorrelationNetwork instance.
        Args:
            network: Existing network instance to monitor
        Raises: None
        Notes:
            Sets internal reference to provided network instance.
        Returns:
            bool: True if connection successful
        Example:
            network = CascadeCorrelationNetwork(...)
            integration.connect_to_network(network)
        """
        self.network = network
        self.cascade_correlation_instance = network  # Alias
        self.logger.info(
            f"Connected to network: input_size={self.network.input_size}, output_size={self.network.output_size}"
        )
        return True

    # Alias for backward compatibility
    connect_to_cascor_network = connect_to_network

    def install_monitoring_hooks(self):
        """
        Description:
            Install monitoring hooks on network training methods.
        Args: None
        Raises: None
        Notes:
            Wraps the following methods:
                - fit: Main training loop
                - train_output_layer: Output training phase
                - train_candidates: Candidate training phase
            The wrapped methods inject monitoring callbacks that:
                - Extract training metrics
                - Broadcast updates via WebSocket
                - Track training phases
        Returns:
            bool: True if hooks installed successfully, False otherwise
        Example:
            integration.install_monitoring_hooks()
            # Now training will be monitored automatically
            network.fit(x_train, y_train)
        """
        if self.network is None:
            self.logger.error("No network connected. Call create_network() or connect_to_network() first.")
            return False
        if self.monitoring_active:
            self.logger.warning("Monitoring hooks already installed")
            return True
        try:
            # Save original methods
            self._original_methods["fit"] = self.network.fit
            self._original_methods["train_output_layer"] = self.network.train_output_layer
            self._original_methods["train_candidates"] = self.network.train_candidates

            # Wrap fit method
            original_fit = self.network.fit

            def monitored_fit(*args, **kwargs):
                self._on_training_start()
                result = original_fit(*args, **kwargs)
                self._on_training_complete(result)
                return result

            self.network.fit = monitored_fit

            # Wrap train_output_layer
            original_train_output = self.network.train_output_layer

            def monitored_train_output(*args, **kwargs):
                self._on_output_phase_start()
                result = original_train_output(*args, **kwargs)
                self._on_output_phase_end(result)
                return result

            self.network.train_output_layer = monitored_train_output

            # Wrap train_candidates
            original_train_candidates = self.network.train_candidates

            def monitored_train_candidates(*args, **kwargs):
                self._on_candidate_phase_start()
                result = original_train_candidates(*args, **kwargs)
                self._on_candidate_phase_end(result)
                return result

            self.network.train_candidates = monitored_train_candidates
            self.monitoring_active = True
            self.logger.info("Monitoring hooks installed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to install monitoring hooks: {e}", exc_info=True)
            return False

    def _on_training_start(self):
        """
        Description:
            Called when training starts (fit method called).
        Args: None
        Raises: None
        Notes:
            Provides notification of training start.
            This method is idempotent and can be called multiple times without adverse effects.
        Returns: None
        Example:
            self._on_training_start()
        """
        self.logger.info("Training started")
        self.training_monitor.on_training_start()

        # Broadcast via WebSocket
        self._broadcast_message(
            {
                "type": "training_start",
                "timestamp": datetime.now().isoformat(),
                "input_size": self.network.input_size,
                "output_size": self.network.output_size,
            }
        )

    def _on_training_complete(self, history: Dict):
        """
        Description:
            Called when training completes (fit method returns).
        Args:
            history: Training history dictionary from fit()
        Raises: None
        Notes:
            Serialize history and broadcast via WebSocket.
            This method is idempotent and can be called multiple times without adverse effects.
        Returns: None
        Example:
            self._on_training_complete(history)
        """
        self.logger.info("Training completed")
        self.training_monitor.on_training_end()

        # Serialize history (convert torch tensors to floats)
        serialized_history = self._serialize_history(history)

        # Broadcast via WebSocket
        self._broadcast_message(
            {
                "type": "training_complete",
                "timestamp": datetime.now().isoformat(),
                "history": serialized_history,
                "hidden_units_added": len(self.network.hidden_units),
            }
        )

    def _on_output_phase_start(self):
        """
        Description:
            Called when output training phase starts.
        Args: None
        Raises: None
        Notes:
            Provides notification of output phase start.
            This method is idempotent and can be called multiple times without adverse effects.
        Returns: None
        Example:
            self._on_output_phase_start()
        """
        self.logger.debug("Output training phase started")
        self._broadcast_message({"type": "phase_start", "phase": "output", "timestamp": datetime.now().isoformat()})

    def _on_output_phase_end(self, loss: float):
        """
        Description:
            Called when output training phase ends.
        Args:
            loss: Final loss value from train_output_layer
        Raises: None
        Notes:
            Extract metrics and report to training monitor.
        Returns: None
        Example:
            self._on_output_phase_end(loss)
        """
        self.logger.debug(f"Output training phase ended: loss={loss:.6f}")

        # Extract current metrics from network state
        metrics = {
            "type": "phase_end",
            "phase": "output",
            "loss": loss,
            "accuracy": (
                self.network.history["train_accuracy"][-1] if self.network.history.get("train_accuracy") else 0.0
            ),
            "hidden_units": len(self.network.hidden_units),
            "epoch": len(self.network.history.get("train_loss", [])),
            "timestamp": datetime.now().isoformat(),
        }

        # Report to training monitor
        self.training_monitor.on_epoch_end(
            epoch=metrics["epoch"],
            loss=metrics["loss"],
            accuracy=metrics["accuracy"],
            learning_rate=self.network.learning_rate,
        )

        # Broadcast via WebSocket
        self._broadcast_message(metrics)

    def _on_candidate_phase_start(self):
        """
        Description:
            Called when candidate training phase starts.
        Args: None
        Raises: None
        Notes:
            This method is idempotent and can be called multiple times without adverse effects.
        Returns: None
        Example:
            self._on_candidate_phase_start()
        """
        self.logger.debug("Candidate training phase started")
        self._broadcast_message({"type": "phase_start", "phase": "candidate", "timestamp": datetime.now().isoformat()})

    def _on_candidate_phase_end(self, results: Tuple):
        """
        Description:
            Called when candidate training phase ends.
        Args:
            results: Tuple from train_candidates (statistics dict)
        Raises: None
        Notes:
            Extract statistics from results.
            Results can be tuple: (candidates_list, best_candidate_data, statistics) or a statistics dict.
        Returns: None
        Example:
            self._on_candidate_phase_end(results)
        """
        self.logger.debug("Candidate training phase ended")
        statistics = results if isinstance(results, dict) else {}
        self._broadcast_message(
            {
                "type": "phase_end",
                "phase": "candidate",
                "statistics": statistics,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _serialize_history(self, history: Dict) -> Dict:
        """
        Description:
            Convert history with torch tensors to JSON-serializable format.
        Args:
            history: History dictionary from network.fit()
        Raises: None
        Notes:
            This method is idempotent and can be called multiple times without adverse effects.
        Returns:
            Serialized history dictionary
        Example:
            serialized = self._serialize_history(history)
        """
        serialized = {}
        for key, value in history.items():
            if isinstance(value, list):
                serialized[key] = [float(v) if torch.is_tensor(v) else v for v in value]
            elif torch.is_tensor(value):
                serialized[key] = float(value)
            else:
                serialized[key] = value
        return serialized

    def _broadcast_message(self, message: Dict):
        """
        Description:
            Broadcast message via WebSocket.
        Args:
            message: Message dictionary to broadcast
        Raises: None
        Notes:
            Uses websocket_manager to broadcast synchronously.
        Returns: None
        Example:
            self._broadcast_message({'type': 'metrics_update', 'epoch': 5, 'train_loss': 0.2})
        """
        try:
            from communication.websocket_manager import websocket_manager

            websocket_manager.broadcast_sync(message)
        except Exception as e:
            self.logger.warning(f"Failed to broadcast message: {e}")

    def start_monitoring_thread(self, interval: float = 1.0):
        """
        Description:
            Start background thread to poll network state for epoch-level updates.
        Args:
            interval: Polling interval in seconds (default: 1.0)
        Raises: None
        Notes:
            This provides real-time metrics updates during long training phases
            where the backend doesn't expose epoch-level callbacks.
        Returns: None
        Example:
            integration.start_monitoring_thread(interval=0.5)  # Poll every 500ms
        """
        if self.monitoring_thread is not None and self.monitoring_thread.is_alive():
            self.logger.warning("Monitoring thread already running")
            return
        self.monitoring_interval = interval
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, args=(interval,), daemon=True, name="CascorMonitoringThread"
        )
        self.monitoring_thread.start()
        self.logger.info(f"Monitoring thread started (interval={interval}s)")

    def stop_monitoring(self):
        """
        Description:
            Stop background monitoring thread (idempotent).
        Args: None
        Raises: None
        Notes:
            This method is idempotent and can be called multiple times without adverse effects.
        Returns: None
        Example:
            integration.stop_monitoring()
        """
        if not self.monitoring_active:
            return
        self.monitoring_active = False
        if self.monitoring_thread is not None:
            self.monitoring_thread.join(timeout=5.0)
            if self.monitoring_thread.is_alive():
                self.logger.warning("Monitoring thread did not stop cleanly within timeout")
            else:
                self.logger.info("Monitoring thread stopped successfully")
            self.monitoring_thread = None

    def _monitoring_loop(self, interval: float):
        """
        Description:
            Background monitoring loop.
        Args:
            interval: Polling interval in seconds
        Raises: None
        Notes:
            Polls network state and broadcasts updates at regular intervals.
        Returns: None
        Example:
            integration.start_monitoring_thread(interval=0.5)  # Poll every 500ms
        """
        self.logger.debug("Monitoring loop started")
        while self.monitoring_active and self.network is not None:
            try:

                # Extract current metrics
                metrics = self._extract_current_metrics()
                if metrics and metrics.get("epoch", 0) > 0:

                    # Broadcast update
                    self._broadcast_message({"type": "metrics_update", **metrics})
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            time.sleep(interval)
        self.logger.debug("Monitoring loop ended")

    def _extract_current_metrics(self) -> Dict:
        """
        Description:
            Extract current metrics from network state (thread-safe).
        Args: None
        Raises: None
        Notes:
            CANOPY-P1-003: Uses metrics_lock for thread-safe access to network.history.
            Returns a dictionary with the current metrics.
            {
                'epoch': 5,
                'train_loss': 0.2,
                'train_accuracy': 0.95,
                'value_loss': 0.3,
                'value_accuracy': 0.9,
                'hidden_units': 128,
                'timestamp': '2023-10-01T12:00:00'
            }
        Returns:
            Dictionary with current metrics
        Example:
            metrics = integration._extract_current_metrics()
        """
        if self.network is None or not hasattr(self.network, "history"):
            return {}
        # CANOPY-P1-003: Use metrics_lock to prevent race condition with training thread
        # The network.history dictionary is mutated during training, so we need exclusive access
        with self.metrics_lock:
            try:
                history = self.network.history
                # Copy values while holding lock to prevent mutation during read
                train_loss_list = list(history.get("train_loss", []))
                train_accuracy_list = list(history.get("train_accuracy", []))
                value_loss_list = list(history.get("value_loss", []))
                value_accuracy_list = list(history.get("value_accuracy", []))
                hidden_units_count = len(self.network.hidden_units)
            except (RuntimeError, KeyError) as e:
                # Handle case where history is modified during read
                self.logger.debug(f"Concurrent modification detected in metrics extraction: {e}")
                return {}
        return {
            "epoch": len(train_loss_list),
            "train_loss": train_loss_list[-1] if train_loss_list else None,
            "train_accuracy": train_accuracy_list[-1] if train_accuracy_list else None,
            "value_loss": value_loss_list[-1] if value_loss_list else None,
            "value_accuracy": value_accuracy_list[-1] if value_accuracy_list else None,
            "hidden_units": hidden_units_count,
            "timestamp": datetime.now().isoformat(),
        }

    def get_network_topology(self) -> Optional[Dict]:
        # sourcery skip: class-extract-method
        """
        Description:
            Extract current network topology for visualization (thread-safe).
        Args: None
        Raise: None
        Notes:
            Returns a dictionary representing the network structure,
            including input size, output size, hidden units, weights, biases, and activation functions.
            Dictionary with network structure:
            {
                'input_size': int,
                'output_size': int,
                'hidden_units': [
                    {
                        'id': int,
                        'weights': list,  # Connection weights
                        'bias': float,
                        'activation': str
                    },
                    ...
                ],
                'output_weights': list,  # 2D array
                'output_bias': list
            }
        Returns:
            Optional[Dictionary] - Dictionary with network structure
        Example:
            topology = integration.get_network_topology()
            visualizer.update_topology(topology)
        """
        if self.network is None:
            self.logger.warning("No network connected")
            return None
        try:
            with self.topology_lock:
                with torch.no_grad():
                    topology = {
                        "input_size": self.network.input_size,
                        "output_size": self.network.output_size,
                        "hidden_units": [],
                        "output_weights": self.network.output_weights.detach().cpu().tolist(),
                        "output_bias": self.network.output_bias.detach().cpu().tolist(),
                    }

                    # Extract hidden units
                    for i, unit in enumerate(self.network.hidden_units):
                        topology["hidden_units"].append(
                            {
                                "id": i,
                                "weights": unit["weights"].detach().cpu().tolist(),
                                "bias": float(unit["bias"]),
                                "activation": unit.get("activation_fn", torch.sigmoid).__name__,
                            }
                        )
            self.logger.debug(
                f"Extracted topology: {topology['input_size']} inputs, "
                f"{len(topology['hidden_units'])} hidden, "
                f"{topology['output_size']} outputs"
            )
            return topology
        except Exception as e:
            self.logger.error(f"Failed to extract network topology: {e}", exc_info=True)
            import traceback

            traceback.print_exc()
            return None

    # Alias for compatibility with existing code
    extract_network_topology = get_network_topology

    def extract_cascor_topology(self) -> Optional[Dict]:
        """
        Description:
            Extract current network topology from CasCor instance.
        Args: None
        Raises: None
        Notes:
            Uses internal CasCor instance to extract weights, biases,
            cascade history, and current epoch.
        Returns:
            NetworkTopology object or None if extraction fails
        Example:
            topology = integration.extract_cascor_topology()
        """
        if self.cascade_correlation_instance is None:
            return None
        try:
            return self._cascor_topology_get_components()
        except Exception as e:
            self.logger.error(f"Failed to extract network topology: {e}")
            import traceback

            traceback.print_exc()
            return None

    def _cascor_topology_get_components(self) -> Optional[Dict]:
        """
        Description:
            Extract components of the CasCor topology.
        Args: None
        Raises: None
        Notes:
            Extracts weights, biases, cascade history, and current epoch
            from the CasCor instance and converts to NetworkTopology format.
        Returns:
            NetworkTopology dictionary or None if extraction fails
        Example:
            topology = integration._cascor_topology_get_components()
        """
        if self.cascade_correlation_instance is None:
            return None

        # Extract weight tensors
        input_weights = self.cascade_correlation_instance.input_weights
        hidden_weights = getattr(self.cascade_correlation_instance, "hidden_weights", None)
        output_weights = self.cascade_correlation_instance.output_weights
        hidden_biases = getattr(self.cascade_correlation_instance, "hidden_biases", None)
        output_biases = self.cascade_correlation_instance.output_biases

        # Get cascade history
        cascade_history = getattr(self.cascade_correlation_instance, "cascade_history", [])

        # Current epoch
        current_epoch = getattr(self.cascade_correlation_instance, "current_epoch", 0)
        return self.data_adapter.convert_network_topology(
            input_weights=input_weights,
            hidden_weights=hidden_weights,
            output_weights=output_weights,
            hidden_biases=hidden_biases,
            output_biases=output_biases,
            cascade_history=cascade_history,
            current_epoch=current_epoch,
        )

    def get_dataset_info(
        self, x: Optional[torch.Tensor] = None, y: Optional[torch.Tensor] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Description:
            Get information about dataset for visualization.
        Args:
            x: Feature tensor (default: extract from network)
            y: Label tensor (default: extract from network)
        Raises: None
        Notes:
            If x or y are not provided, attempts to extract from connected network.
            If no dataset is available, generates a mock spiral dataset for demo purposes.
            Dictionary with dataset information:
            {
                'features': list,  # 2D array
                'labels': list,    # 1D array
                'num_samples': int,
                'num_features': int,
                'num_classes': int,
                'class_distribution': dict
            }
        Returns:
            Optional[Dictionary] - Dataset information dictionary
        Example:
            dataset_info = integration.get_dataset_info(x_train, y_train)
            dataset_plotter.load_dataset(dataset_info)
        """
        # Try to get from parameters or network
        if x is None and hasattr(self.network, "train_x"):
            x = self.network.train_x
        if y is None and hasattr(self.network, "train_y"):
            y = self.network.train_y
        if x is None or y is None:
            return self._generate_missing_dataset_info()
        try:

            # Convert tensors to numpy
            if isinstance(x, torch.Tensor):
                x = x.cpu().numpy()
            if isinstance(y, torch.Tensor):
                y = y.cpu().numpy()
            return self.data_adapter.prepare_dataset_for_visualization(features=x, labels=y, dataset_name="training")
        except Exception as e:
            self.logger.error(f"Failed to get dataset info: {e}", exc_info=True)
            import traceback

            traceback.print_exc()
            return None

    def _generate_missing_dataset_info(self):
        """
        Description:
            Generate mock dataset information when no real dataset is available.
        Args: None
        Raises: None
        Notes:
            Generates a simple spiral dataset for demonstration purposes.
        Returns:
            Dictionary with mock dataset information
        Example:
            dataset_info = integration._generate_missing_dataset_info()
        """
        # Generate mock spiral dataset for demo
        self.logger.info("No dataset available, generating mock spiral dataset")
        import numpy as np

        n_samples = 100
        theta = np.linspace(0, 4 * np.pi, n_samples)

        # Generate two spiral classes
        x1 = theta * np.cos(theta) / 10
        y1 = theta * np.sin(theta) / 10
        x2 = -theta * np.cos(theta) / 10
        y2 = -theta * np.sin(theta) / 10
        features = np.vstack([np.column_stack([x1, y1]), np.column_stack([x2, y2])])
        labels = np.concatenate([np.zeros(n_samples), np.ones(n_samples)])
        return {
            "features": features.tolist(),
            "labels": labels.tolist(),
            "num_samples": 2 * n_samples,
            "num_features": 2,
            "num_classes": 2,
            "class_distribution": {0: n_samples, 1: n_samples},
            "dataset_name": "Mock Spiral Dataset",
            "mock_mode": True,
        }

    def get_prediction_function(self) -> Optional[Callable]:
        """
        Description:
            Get prediction function for decision boundary visualization.
        Args: None
        Raises: None
        Notes:
            Returns a callable that accepts input data (numpy array or torch tensor)
            and returns predictions from the connected network.
        Returns:
            Callable that takes input (numpy array or torch tensor) and returns predictions
        Example:
            predict_fn = integration.get_prediction_function()
            decision_boundary.set_prediction_function(predict_fn)
        """
        # Validate network connection
        if self.network is None:
            return None

        # Define prediction function
        def predict(x: Union[np.ndarray, torch.Tensor]) -> torch.Tensor:
            """
            Description:
                Predict using network. Accepts numpy arrays or torch tensors.
            Args:
                x: Input data (numpy array or torch tensor)
            Raises: None
            Notes:
                Converts numpy arrays to torch tensors if needed.
            Returns:
                Predictions as torch tensor
            Example:
                preds = predict_fn(input_data)
            """
            with torch.no_grad():
                if isinstance(x, np.ndarray):  # Convert numpy to torch if needed
                    x = torch.from_numpy(x).float()
                return self.network.forward(x)

        # Return the prediction function
        return predict

    def create_monitoring_callback(self, event_type: str, callback: Callable):
        """
        Description:
            Register callback for monitoring events.
        Args:
            event_type: Type of event to monitor
            callback: Callback function
        Raises: None
        Notes:
            Supported event types:
                - 'epoch_end': Called at end of each epoch
                - 'training_start': Called when training starts
                - 'training_end': Called when training ends
            Callback signature depends on event type.
        Returns: None
        Example:
            def on_epoch(epoch, loss, accuracy):
                print(f"Epoch {epoch}: loss={loss}, acc={accuracy}")
            integration.create_monitoring_callback('epoch_end', on_epoch)
        """
        self.training_monitor.register_callback(event_type, callback)

    def get_training_status(self) -> Dict[str, Any]:
        """
        Description:
            Get current training status.
        Args: None
        Raises: None
        Notes:
            Dictionary with status information:
            {
                'is_training': bool,
                'current_epoch': int,
                'current_loss': float,
                'current_accuracy': float,
                'network_connected': bool,
                'monitoring_active': bool,
                'input_size': int,
                'output_size': int,
                'hidden_units': int
            }
            - 'is_training': Indicates if training is currently active
            - 'current_epoch': The epoch number currently being trained
        Returns:
            Dictionary with training status information
        Example:
            status = integration.get_training_status()
            if status['is_training']:
                print(f"Training epoch {status['current_epoch']}")
        """
        status = self.training_monitor.get_current_state()

        # Add network-specific information
        if self.network:
            status["network_connected"] = True
            status["input_size"] = self.network.input_size
            status["output_size"] = self.network.output_size
            status["hidden_units"] = len(self.network.hidden_units)
        else:
            status["network_connected"] = False
            status["input_size"] = 0
            status["output_size"] = 0
            status["hidden_units"] = 0

        # Add monitoring status
        status["monitoring_active"] = self.monitoring_active
        return status

    def restore_original_methods(self):
        """
        Description:
            Restore original training methods (remove monitoring hooks).
        Args: None
        Raises: None
        Notes:
            Restores the original methods saved in _original_methods.
        Returns: None
        Example:
            integration.restore_original_methods()
        """
        if not self._original_methods or self.network is None:
            return
        for method_name, original_method in self._original_methods.items():
            setattr(self.network, method_name, original_method)
        self._original_methods.clear()
        self.logger.info("Original methods restored")

    def shutdown(self):
        """
        Description:
            Clean up integration resources (idempotent).
        Args: None
        Raises: None
        Notes:
        - Stops monitoring thread
        - Restores original methods
        - Ends training monitoring
        Returns: None
        Example:
            integration.shutdown()
        """
        if self._shutdown_called:
            self.logger.debug("Shutdown already called, skipping")
            return
        self._shutdown_called = True
        self.logger.info("Shutting down CasCor integration")
        self.stop_monitoring()  # Stop monitoring thread
        self.restore_original_methods()  # Restore original methods
        if hasattr(self, "training_monitor") and self.training_monitor:  # End training monitoring
            self.training_monitor.on_training_end()
        self.logger.info("CasCor integration shutdown complete")

    def __del__(self):
        """
        Description:
            Destructor: ensure cleanup on garbage collection.
        Args: None
        Raises: None
        Notes:
            Calls shutdown() to clean up resources.
        Returns: None
        Example:
            del integration
        """
        with contextlib.suppress(Exception):
            self.shutdown()
