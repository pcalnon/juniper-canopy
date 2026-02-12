#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.2.1
# File Name:     __init__.py
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/juniper_data_client/
#
# Date Created:  2026-01-31
# Last Modified: 2026-02-12
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Package initialization for juniper_data_client module.
#    Re-exports from the shared juniper-data-client package (DATA-012).
#    Falls back to local implementation if shared package is not installed.
#
#####################################################################################################################################################################################################

"""JuniperData Client - Python client library for the JuniperData REST API.

This package provides a robust client for interacting with the JuniperData
dataset generation service, used by both JuniperCascor and JuniperCanopy.

Features:
    - Dataset creation and artifact download (NPZ format)
    - Health check and readiness polling
    - Automatic retry with exponential backoff
    - Connection pooling and session management
    - Custom exception hierarchy
    - Context manager support
    - Full type hints
"""

try:
    from juniper_data_client import (
        JuniperDataClient,
        JuniperDataClientError,
        JuniperDataConfigurationError,
        JuniperDataConnectionError,
        JuniperDataNotFoundError,
        JuniperDataTimeoutError,
        JuniperDataValidationError,
        __version__,
    )

    _USING_SHARED_PACKAGE = True
except ImportError:
    from .client import JuniperDataClient
    from .exceptions import (
        JuniperDataClientError,
        JuniperDataConfigurationError,
        JuniperDataConnectionError,
        JuniperDataNotFoundError,
        JuniperDataTimeoutError,
        JuniperDataValidationError,
    )

    _USING_SHARED_PACKAGE = False
    __version__ = "0.2.1-local"

__all__ = [
    "JuniperDataClient",
    "JuniperDataClientError",
    "JuniperDataConfigurationError",
    "JuniperDataConnectionError",
    "JuniperDataNotFoundError",
    "JuniperDataTimeoutError",
    "JuniperDataValidationError",
    "__version__",
    "_USING_SHARED_PACKAGE",
]
