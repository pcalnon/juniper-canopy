#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       0.2.0
# File Name:     exceptions.py
# File Path:     ${HOME}/Development/python/JuniperCanopy/juniper_canopy/src/juniper_data_client/
#
# Date Created:  2026-02-07
# Last Modified: 2026-02-07
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Custom exceptions for the JuniperData client library.
#    Mirrors the exception hierarchy from the shared juniper-data-client package (DATA-012).
#
#####################################################################################################################################################################################################

"""Custom exceptions for the JuniperData client library."""


class JuniperDataClientError(Exception):
    """Base exception for all JuniperData client errors."""

    pass


class JuniperDataConnectionError(JuniperDataClientError):
    """Raised when connection to JuniperData service fails."""

    pass


class JuniperDataTimeoutError(JuniperDataClientError):
    """Raised when a request to JuniperData times out."""

    pass


class JuniperDataNotFoundError(JuniperDataClientError):
    """Raised when a requested resource is not found (404)."""

    pass


class JuniperDataValidationError(JuniperDataClientError):
    """Raised when request parameters fail validation (400/422)."""

    pass


class JuniperDataConfigurationError(JuniperDataClientError):
    """Raised when JuniperData configuration is missing or invalid."""

    pass
