#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Docker secrets utility for file-based secret resolution
#
# Author:        Paul Calnon
# Version:       0.4.0
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
#    A key canopy SENDS (juniper-cascor, juniper-data, recurrence) is read through
#    get_outbound_secret(), which refuses a value no HTTP client can carry and records
#    the variable's NAME for report_refused_outbound_keys(). bind_outbound_key() then
#    stops the client libraries from reading the same variables again on their own.
#
#####################################################################################################################################################################################################
import os
from pathlib import Path
from threading import Lock
from typing import Any, NamedTuple, TypeVar


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


# ── Outbound API keys (#683 validation, item 1) ────────────────────────────────────────────────────────────────────────
#
# canopy sends three keys as ``X-API-Key``: juniper-cascor's (``backend.create_backend``), and juniper-data's and the
# recurrence service's (``settings.Settings``' validators). Every HTTP client canopy uses REFUSES a header value it
# cannot carry, and QUOTES the value in the exception it raises (requests 2.34.2, httpx 0.28.1 / h11 0.16.0 and
# websockets 17.1, measured by ``util/ad-hoc/2026-09-24_683_validation_leak_probes.py lib``):
#
#   * requests (juniper-cascor-client, juniper-data-client): leading whitespace, or a line break anywhere ->
#     ``InvalidHeader: ... in header value: ' <key>'``;
#   * httpx / h11 (the recurrence adapter, the generators proxy): leading or trailing whitespace, a vertical tab or a
#     line break -> ``LocalProtocolError: Illegal header value b' <key>'``, and anything non-ASCII -> ``UnicodeEncodeError``;
#   * websockets 17.1 (the cascor WebSocket streams): a line break or another control character except tab, or a
#     character above U+00FF -> ``InvalidHeaderValue: invalid X-API-Key header: <key>``. (websockets 16.0 SENDS it
#     instead, line breaks included.)
#
# canopy logged that text at ERROR -- on every status-refresher tick -- Sentry received it, and canopy returned it in
# API bodies that an anonymous caller could read with auth enabled. So each key is checked where it is read, against
# the union of those rules: every character printable ASCII other than space, 0x21-0x7E. That rule also refuses a space
# or tab INSIDE a key, which every client would carry. A refused value is treated exactly like an EMPTY one -- the
# resolution moves on to the next key canopy falls back to, or to none -- and its variable's NAME, never the value or
# the path a ``_FILE`` variable holds, is recorded for :func:`report_refused_outbound_keys`. Nothing is logged where the
# key is read: ``settings.Settings`` is first built at import (``main.settings``), before ``configure_logging`` has run,
# so a record logged there would reach only Python's last-resort handler (the #660 lesson ``security.py`` records).

# Printable ASCII other than space.
_SENDABLE_KEY_CHARS = range(0x21, 0x7F)

# The WARNING for a refused key, one wording per source, as ``security.py``'s blank-key WARNING has.
_REFUSED_KEY_EFFECT = "HTTP clients refuse such a header value, and the error they raise quotes it."
_REFUSED_KEY_ENV_WARNING = "{var} holds a key canopy does not send: it has leading or trailing whitespace, or a character outside printable ASCII (0x21-0x7E) such as a line break, a space or a non-ASCII character. " + _REFUSED_KEY_EFFECT + " Canopy treats {var} as empty instead, so no client is handed the key: a request it would have authenticated carries the next key canopy falls back to, or none. Remove the whitespace, line break or non-ASCII character from {var}."
_REFUSED_KEY_FILE_WARNING = (
    "The file named by {var} holds a key canopy does not send: with its leading and trailing whitespace stripped, the key still holds a character outside printable ASCII (0x21-0x7E) such as a line break, a space or a non-ASCII character. " + _REFUSED_KEY_EFFECT + " Canopy treats the key as empty instead, so no client is handed it: a request it would have authenticated carries the next key canopy falls back to, or none. Write the key into that file on one line, with no space or non-ASCII character in it."
)

# Variable NAME -> (the value was the content of the file that variable names, reported yet). Guarded by the lock.
_refused_outbound_keys: dict[str, tuple[bool, bool]] = {}
_refused_outbound_keys_lock = Lock()

_ClientT = TypeVar("_ClientT")


def is_sendable_key(value: str) -> bool:
    """True when ``value`` is non-empty and every character is printable ASCII other than space (0x21-0x7E).

    The one rule for a key canopy sends (this section's notes). It subsumes ``value != value.strip()``: a value made of
    0x21-0x7E alone holds no whitespace anywhere.
    """
    return bool(value) and all(ord(char) in _SENDABLE_KEY_CHARS for char in value)


def screen_outbound_key(value: str | None, source: str, *, from_file: bool = False) -> str | None:
    """Return ``value`` when canopy may send it as ``X-API-Key``; otherwise record ``source`` and return ``None``.

    ``None`` and ``""`` come back unchanged: an unset or empty key is the absence of a key, not a finding. ``source`` is
    the NAME of the variable that supplied ``value`` -- recorded, never the value -- and ``from_file`` says the value is
    the content of the file that variable names, which picks the WARNING's wording.
    """
    if not value or is_sendable_key(value):
        return value
    with _refused_outbound_keys_lock:
        if source not in _refused_outbound_keys:
            _refused_outbound_keys[source] = (from_file, False)
    return None


def get_outbound_secret(env_var: str, file_env_var: str | None = None) -> str | None:
    """:func:`get_secret` for a key canopy SENDS: a value no HTTP client can carry comes back as ``None``.

    The refusal is recorded by variable NAME for :func:`report_refused_outbound_keys` (:func:`screen_outbound_key`).
    Callers test the result's truthiness, so a refused value takes exactly the path an empty one always took.
    """
    if file_env_var is None:
        file_env_var = f"{env_var}_FILE"
    value, source, _ = resolve_secret_detail(env_var, file_env_var)
    return screen_outbound_key(value, source or env_var, from_file=source == file_env_var)


def report_refused_outbound_keys(log: Any) -> int:
    """Log, through ``log``, one WARNING per outbound-key variable whose value was refused, each at most once per process.

    ``main.lifespan`` calls this with the system logger once ``configure_logging`` has run. It reads only what
    :func:`screen_outbound_key` recorded -- variable names, never a key or a path.

    Returns:
        How many WARNINGs this call logged.
    """
    with _refused_outbound_keys_lock:
        pending = [(name, from_file) for name, (from_file, reported) in _refused_outbound_keys.items() if not reported]
        for name, from_file in pending:
            _refused_outbound_keys[name] = (from_file, True)
    for name, from_file in pending:
        log.warning((_REFUSED_KEY_FILE_WARNING if from_file else _REFUSED_KEY_ENV_WARNING).format(var=name))
    return len(pending)


def reset_outbound_key_findings() -> None:
    """Forget every recorded refusal. Useful for testing."""
    with _refused_outbound_keys_lock:
        _refused_outbound_keys.clear()


def bind_outbound_key(client: _ClientT, api_key: str | None) -> _ClientT:
    """Leave ``client`` sending ``api_key`` -- canopy's resolution -- and never a key it read from the environment itself.

    juniper-cascor-client's ``JuniperCascorClient``, ``CascorTrainingStream`` and ``CascorControlStream`` fall back to
    ``os.environ["JUNIPER_CASCOR_API_KEY"]``, and juniper-data-client's ``JuniperDataClient`` to
    ``JUNIPER_DATA_API_KEY_FILE`` / ``JUNIPER_DATA_API_KEY``, whenever the key they are handed is falsy
    (``api_key or os.environ.get(...)``). That is a second read of variables canopy has already resolved, and it skips
    :func:`get_outbound_secret`: the raw value canopy refused came straight back through it, and so did an env var that a
    key file shadows in canopy's own order. When canopy resolved no key, this undoes whatever the client found on its
    own -- its ``api_key`` attribute, which the WebSocket streams read at connect time, and the ``X-API-Key`` header the
    REST clients set on their ``requests`` session. A key canopy did resolve is left exactly as the client set it.

    Returns:
        ``client``, so a construction can be wrapped in place.
    """
    if api_key:
        return client
    if getattr(client, "api_key", None) is not None:
        client.api_key = None
    session = getattr(client, "session", None)
    if session is not None:
        session.headers.pop("X-API-Key", None)
    return client
