#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     canopy_constants.py
# Author:        Paul Calnon
# Version:       0.1.1
#
# Date:          2025-10-22
# Last Modified: 2025-12-13
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Centralized constants for juniper_canopy application
#
#####################################################################################################################################################################################################
# Notes:
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
from typing import Final


class TrainingConstants:
    """Training-related constants.

    Defines default values, minimum and maximum constraints for training
    parameters including epochs, learning rates, and hidden units.
    """

    # ── Neural Network: Epoch limits ──
    MIN_TRAINING_EPOCHS: Final[int] = 10
    MAX_TRAINING_EPOCHS: Final[int] = 10000000
    DEFAULT_TRAINING_EPOCHS: Final[int] = 1000000

    # ── Neural Network: Maximum growth iterations (hidden unit additions) ──
    DEFAULT_MAX_GROWTH_ITERATIONS: Final[int] = 1000
    MIN_MAX_GROWTH_ITERATIONS: Final[int] = 1
    MAX_MAX_GROWTH_ITERATIONS: Final[int] = 100000

    # ── Neural Network: Learning rate ──
    DEFAULT_LEARNING_RATE: Final[float] = 0.01
    MIN_LEARNING_RATE: Final[float] = 0.0001
    MAX_LEARNING_RATE: Final[float] = 1.0

    # ── Neural Network: Hidden units ──
    DEFAULT_MAX_HIDDEN_UNITS: Final[int] = 1000
    MIN_HIDDEN_UNITS: Final[int] = 0
    MAX_HIDDEN_UNITS: Final[int] = 10000

    # ── Neural Network: Multi-node layers ──
    DEFAULT_MULTI_NODE_LAYERS: Final[bool] = False

    # ── Neural Network: Growth trigger ──
    DEFAULT_GROWTH_TRIGGER: Final[str] = "convergence"
    DEFAULT_PRESET_EPOCHS: Final[int] = 50
    MIN_PRESET_EPOCHS: Final[int] = 1
    MAX_PRESET_EPOCHS: Final[int] = 10000

    # ── Neural Network: Convergence detection (used by growth trigger) ──
    DEFAULT_CONVERGENCE_ENABLED: Final[bool] = True
    DEFAULT_CONVERGENCE_THRESHOLD: Final[float] = 0.001
    MIN_CONVERGENCE_THRESHOLD: Final[float] = 0.0001
    MAX_CONVERGENCE_THRESHOLD: Final[float] = 0.1

    # ── Neural Network: Patience ──
    DEFAULT_PATIENCE: Final[int] = 50
    MIN_PATIENCE: Final[int] = 1
    MAX_PATIENCE: Final[int] = 500

    # ── Neural Network: Spiral dataset ──
    DEFAULT_SPIRAL_ROTATIONS: Final[float] = 1.5
    MIN_SPIRAL_ROTATIONS: Final[float] = 0.5
    MAX_SPIRAL_ROTATIONS: Final[float] = 5.0
    DEFAULT_SPIRAL_NUMBER: Final[int] = 2
    MIN_SPIRAL_NUMBER: Final[int] = 1
    MAX_SPIRAL_NUMBER: Final[int] = 10
    DEFAULT_DATASET_ELEMENTS: Final[int] = 1000
    MIN_DATASET_ELEMENTS: Final[int] = 50
    MAX_DATASET_ELEMENTS: Final[int] = 50000
    DEFAULT_DATASET_NOISE: Final[float] = 0.25
    MIN_DATASET_NOISE: Final[float] = 0.0
    MAX_DATASET_NOISE: Final[float] = 1.0

    # ── Candidate Nodes: Pool size ──
    DEFAULT_CANDIDATE_POOL_SIZE: Final[int] = 100
    MIN_CANDIDATE_POOL_SIZE: Final[int] = 1
    MAX_CANDIDATE_POOL_SIZE: Final[int] = 500

    # ── Candidate Nodes: Correlation threshold ──
    DEFAULT_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.001
    MIN_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.00001
    MAX_CANDIDATE_CORRELATION_THRESHOLD: Final[float] = 0.1

    # ── Candidate Nodes: Selected candidates ──
    DEFAULT_SELECTED_CANDIDATES: Final[int] = 1
    MIN_SELECTED_CANDIDATES: Final[int] = 1
    MAX_SELECTED_CANDIDATES: Final[int] = 50

    # ── Candidate Nodes: Patience ──
    DEFAULT_CN_PATIENCE: Final[int] = 30
    MIN_CN_PATIENCE: Final[int] = 1
    MAX_CN_PATIENCE: Final[int] = 500

    # ── Candidate Nodes: Pool training complete ──
    DEFAULT_CN_TRAINING_COMPLETE: Final[str] = "preset_epochs"
    DEFAULT_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 500
    MIN_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 10
    MAX_CANDIDATE_TRAINING_ITERATIONS: Final[int] = 5000
    DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.0001
    MIN_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.000001
    MAX_CANDIDATE_CONVERGENCE_THRESHOLD: Final[float] = 0.01

    # ── Candidate Nodes: Multi candidate selection ──
    DEFAULT_MULTI_CANDIDATE_ENABLED: Final[bool] = False
    DEFAULT_TOP_CANDIDATES_COUNT: Final[int] = 1
    MIN_TOP_CANDIDATES_COUNT: Final[int] = 1
    MAX_TOP_CANDIDATES_COUNT: Final[int] = 20
    DEFAULT_RANDOM_CANDIDATES_COUNT: Final[int] = 1
    MIN_RANDOM_CANDIDATES_COUNT: Final[int] = 1
    MAX_RANDOM_CANDIDATES_COUNT: Final[int] = 20

    # ── Cascade correlation internal constants (Phase 6 — matches CasCor reference) ──
    CASCADE_COOLDOWN_EPOCHS: Final[int] = 50  # DEPRECATED: only used by _should_add_cascade_unit (not production loop)
    CANDIDATE_POOL_SIZE: Final[int] = 32  # internal CasCor constant, distinct from UI DEFAULT_CANDIDATE_POOL_SIZE
    CANDIDATE_TRAINING_STEPS: Final[int] = 600
    CANDIDATE_PATIENCE: Final[int] = 30
    OUTPUT_RETRAIN_STEPS: Final[int] = 1000
    OUTPUT_RETRAIN_EMIT_EVERY: Final[int] = 50
    OUTPUT_WEIGHT_INIT_STD: Final[float] = 0.1
    MIN_CANDIDATE_CORRELATION: Final[float] = 0.01
    METRICS_HISTORY_MAXLEN: Final[int] = 10000


class DashboardConstants:
    """Dashboard UI constants.

    Defines update intervals, timeouts, and data limits for the dashboard
    components and API interactions.
    """

    # Update intervals (milliseconds)
    FAST_UPDATE_INTERVAL_MS: Final[int] = 1000  # 1 second
    SLOW_UPDATE_INTERVAL_MS: Final[int] = 5000  # 5 seconds

    # API timeouts (seconds)
    API_TIMEOUT_SECONDS: Final[int] = 2

    # Data limits
    MAX_METRICS_HISTORY: Final[int] = 100
    MAX_DATA_POINTS: Final[int] = 10000

    DEFAULT_METRICS_HISTORY: Final[int] = 50
    DEFAULT_DATA_POINTS: Final[int] = 1000
    DEFAULT_SLIDING_WINDOW_SIZE: Final[int] = 500

    # Display Constants
    DEFAULT_SCALE: Final[float] = 10.0
    DEFAULT_ZOOM: Final[int] = 1
    DEFAULT_ZOOM_INCREMENT: Final[int] = 1
    DEFAULT_ZOOM_DECREMENT: Final[int] = 1
    DEFAULT_ZOOM_MIN: Final[int] = 1
    DEFAULT_ZOOM_MAX: Final[int] = 10


class ServerConstants:
    """Server configuration constants.

    Defines default server configuration including host, port, and
    WebSocket endpoint paths.
    """

    DEFAULT_HOST: Final[str] = "127.0.0.1"
    DEFAULT_PORT: Final[int] = 8050

    # WebSocket paths
    WS_TRAINING_PATH: Final[str] = "/ws/training"
    WS_CONTROL_PATH: Final[str] = "/ws/control"


class WebSocketConstants:
    """WebSocket configuration constants.

    Defines WebSocket connection limits, heartbeat intervals, and
    reconnection parameters.
    """

    MAX_CONNECTIONS: Final[int] = 50
    HEARTBEAT_INTERVAL_SEC: Final[int] = 30
    RECONNECT_ATTEMPTS: Final[int] = 5
    RECONNECT_DELAY_SEC: Final[int] = 2


class JuniperDataConstants:
    """JuniperData service integration constants.

    Defines default values for connecting to and interacting with the
    JuniperData dataset generation service.
    """

    DEFAULT_URL: Final[str] = "http://localhost:8100"
    DEFAULT_TIMEOUT_S: Final[int] = 30
    DEFAULT_RETRY_ATTEMPTS: Final[int] = 3
    DEFAULT_RETRY_BACKOFF_BASE_S: Final[float] = 0.5
    DEFAULT_DATASET_SAMPLES: Final[int] = 200
    DEFAULT_DATASET_NOISE: Final[float] = 0.1
    DEFAULT_DATASET_SEED: Final[int] = 42
    DEFAULT_GENERATOR: Final[str] = "spiral"
    API_VERSION: Final[str] = "v1"


# Convenience imports at module level for commonly used constants
MIN_TRAINING_EPOCHS = TrainingConstants.MIN_TRAINING_EPOCHS
MAX_TRAINING_EPOCHS = TrainingConstants.MAX_TRAINING_EPOCHS
DEFAULT_TRAINING_EPOCHS = TrainingConstants.DEFAULT_TRAINING_EPOCHS
