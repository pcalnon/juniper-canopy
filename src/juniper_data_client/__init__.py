#!/usr/bin/env python
"""
Project:       Juniper
Sub-Project:   JuniperCanopy
File Name:     __init__.py
Author:        Paul Calnon
Version:       0.1.1

Date Created:  2026-01-31
Last Modified: 2026-01-31

License:       MIT License
Copyright:     Copyright (c) 2024-2026 Paul Calnon

Description:
    Package initialization for juniper_data_client module.
    Provides REST API client for JuniperData service integration.
"""

from .client import JuniperDataClient

__all__ = ["JuniperDataClient"]
