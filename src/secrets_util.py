#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Docker secrets utility for file-based secret resolution
#
# Author:        Paul Calnon
# Version:       0.3.0
# File Name:     secrets_util.py
#
# Created Date:  2026-04-01
# Last Modified: 2026-09-24
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
#    A <ENV_VAR>_FILE that is set but names no existing file falls through to step 2
#    exactly as if it were unset; resolve_secret_detail() reports that it happened.
#
#####################################################################################################################################################################################################
import os
from pathlib import Path
from typing import NamedTuple


class SecretResolution(NamedTuple):
    """What :func:`resolve_secret_detail` found.

    ``source`` and ``missing_file_var`` are variable NAMES and safe to log. ``value`` is the
    secret and never is.
    """

    value: str | None
    source: str | None
    missing_file_var: str | None


def resolve_secret_detail(env_var: str, file_env_var: str | None = None) -> SecretResolution:
    """Read a secret value; report which variable supplied it and whether a ``_FILE`` variable was ignored.

    The one implementation of the resolution order in this file's header notes.
    :func:`resolve_secret` and :func:`get_secret` delegate here, so a caller that must say
    WHERE a value came from, or why the file it pointed at was not used, cannot drift from
    them.

    Args:
        env_var: Name of the environment variable holding the secret value
            directly (e.g. ``"CANOPY_API_KEY"``).
        file_env_var: Name of the environment variable pointing to the secret
            file.  Defaults to ``f"{env_var}_FILE"`` when not provided.

    Returns:
        ``SecretResolution(value, source, missing_file_var)``. ``value`` and ``source`` are
        exactly :func:`resolve_secret`'s pair. ``missing_file_var`` is ``file_env_var`` when
        that variable is set (non-empty) but does not name an existing file -- the case the
        resolution order otherwise treats silently as unset -- and ``None`` otherwise. It is
        the variable's NAME, never its value: an operator who confuses the two variables puts
        the secret itself in the ``_FILE`` variable, so its value is not safe to log either.
    """
    if file_env_var is None:
        file_env_var = f"{env_var}_FILE"

    missing_file_var = None
    file_path = os.environ.get(file_env_var)
    if file_path:
        path = Path(file_path)
        if path.is_file():
            return SecretResolution(path.read_text().strip(), file_env_var, None)
        missing_file_var = file_env_var

    value = os.environ.get(env_var)
    return SecretResolution(value, env_var if value is not None else None, missing_file_var)


def resolve_secret(env_var: str, file_env_var: str | None = None) -> tuple[str | None, str | None]:
    """Read a secret value and report which variable supplied it.

    Delegates to :func:`resolve_secret_detail`, the one implementation of the resolution
    order in this file's header notes, so a caller that must say WHERE a value came from
    cannot drift from :func:`get_secret`, which delegates here.

    Args:
        env_var: Name of the environment variable holding the secret value
            directly (e.g. ``"CANOPY_API_KEY"``).
        file_env_var: Name of the environment variable pointing to the secret
            file.  Defaults to ``f"{env_var}_FILE"`` when not provided.

    Returns:
        ``(value, source)``. ``source`` is the NAME of the variable whose
        setting supplied ``value`` -- ``file_env_var`` when it names an existing
        file (whose contents win, whitespace-stripped, and may be empty), else
        ``env_var`` when that is set (returned raw, not stripped) -- and
        ``(None, None)`` when neither applies.  The name is safe to log; the
        value never is.
    """
    value, source, _ = resolve_secret_detail(env_var, file_env_var)
    return value, source


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
        The secret string (whitespace-stripped when read from the file; the
        environment variable is returned as set) or ``None`` when neither the
        file nor the environment variable is set.
    """
    return resolve_secret(env_var, file_env_var)[0]
