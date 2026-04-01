#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Docker secrets utility for file-based secret resolution
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     secrets_util.py
#
# Created Date:  2026-04-01
# Last Modified: 2026-04-01
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Utility for reading secrets from Docker secret files mounted at
#    /run/secrets/ (via _FILE environment variables) with fallback to
#    plain environment variables.  This enables transparent support for
#    Docker Swarm / Compose secrets without changing application code
#    beyond a single call-site swap from os.environ.get() to get_secret().
#
#####################################################################################################################################################################################################
# Notes:
#
#    Resolution order (first match wins):
#      1. Read value from the file pointed to by <ENV_VAR>_FILE
#      2. Read value from ENV_VAR directly
#      3. Return None
#
#####################################################################################################################################################################################################
import os
from pathlib import Path


def get_secret(env_var: str, file_env_var: str | None = None) -> str | None:
    """Read a secret value, preferring file-based Docker secrets over env vars.

    Docker Compose / Swarm mounts secret files and exposes their paths via
    ``<ENV_VAR>_FILE`` environment variables.  This helper checks for the
    file first and falls back to a plain environment variable.

    Args:
        env_var: Name of the environment variable holding the secret value
            directly (e.g. ``"CANOPY_API_KEY"``).
        file_env_var: Name of the environment variable pointing to the secret
            file.  Defaults to ``f"{env_var}_FILE"`` when not provided.

    Returns:
        The secret string (whitespace-stripped) or ``None`` when neither the
        file nor the environment variable is set.
    """
    if file_env_var is None:
        file_env_var = f"{env_var}_FILE"

    file_path = os.environ.get(file_env_var)
    if file_path:
        path = Path(file_path)
        if path.is_file():
            return path.read_text().strip()

    return os.environ.get(env_var)
