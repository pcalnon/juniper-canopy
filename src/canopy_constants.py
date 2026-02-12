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

    # Epoch limits
    MIN_TRAINING_EPOCHS: Final[int] = 10
    MAX_TRAINING_EPOCHS: Final[int] = 1000
    DEFAULT_TRAINING_EPOCHS: Final[int] = 300

    # Learning rate defaults
    DEFAULT_LEARNING_RATE: Final[float] = 0.01
    MIN_LEARNING_RATE: Final[float] = 0.0001
    MAX_LEARNING_RATE: Final[float] = 1.0

    # Hidden units defaults
    DEFAULT_MAX_HIDDEN_UNITS: Final[int] = 20
    MIN_HIDDEN_UNITS: Final[int] = 0
    MAX_HIDDEN_UNITS: Final[int] = 20


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
