#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Pin Settings.juniper_data_api_key resolution + _FILE indirection
#
# Author:        Paul Calnon
# Version:       0.5.0
# File Name:     test_juniper_data_api_key_resolution.py
# File Path:     ${HOME}/Development/python/Juniper/juniper-canopy/src/tests/unit/
#
# Date Created:  2026-05-29
# Last Modified: 2026-05-29
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Regression tests for ``Settings.juniper_data_api_key`` — the outbound
#    API key canopy sends as ``X-API-Key`` on every juniper-data call.
#    Resolution chain handled by ``_check_juniper_data_api_key`` via
#    ``secrets_util.get_secret`` (which understands ``<NAME>_FILE``
#    Docker-secret indirection).
#
#    Closes the gap memo'd as
#    ``project_juniper_canopy_data_api_key_gap``: canopy never sent an
#    outbound key, so once juniper-deploy#100 enabled juniper-data auth,
#    canopy → juniper-data calls (dataset enumeration, training-pair
#    fetch) silently 401'd while canopy's own ``/v1/health`` continued
#    to report ``juniper_data_available: true`` (data's ``/v1/health``
#    is auth-exempt).
#
#####################################################################################################################################################################################################
"""Unit tests for Settings.juniper_data_api_key resolution + _FILE indirection."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest

from settings import Settings

_ENV_VARS_TO_SCRUB = (
    "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY",
    "JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE",
    "JUNIPER_DATA_API_KEY",
    "JUNIPER_DATA_API_KEY_FILE",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    """Strip every env var the api-key validator considers, so the test starts
    from a known-empty state. The CI environment can inherit one of these."""
    for name in _ENV_VARS_TO_SCRUB:
        monkeypatch.delenv(name, raising=False)
    yield monkeypatch


@pytest.fixture
def secret_file(tmp_path: Path) -> Path:
    """Path to a freshly-written secret file containing one token."""
    path = tmp_path / "data_api_key.txt"
    path.write_text("CanopyDataKeyToken123\n", encoding="utf-8")
    return path


class TestPrefixedDirectEnv:
    """``JUNIPER_CANOPY_JUNIPER_DATA_API_KEY`` (prefixed direct env var)."""

    def test_prefixed_direct_returns_value(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY", "canopy-direct-key")
        assert Settings().juniper_data_api_key == "canopy-direct-key"


class TestPrefixedFileEnv:
    """``JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE`` — Docker-secrets shape."""

    def test_prefixed_file_reads_content(self, clean_env: pytest.MonkeyPatch, secret_file: Path) -> None:
        clean_env.setenv("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE", str(secret_file))
        assert Settings().juniper_data_api_key == "CanopyDataKeyToken123"

    def test_prefixed_file_wins_over_prefixed_direct(self, clean_env: pytest.MonkeyPatch, secret_file: Path) -> None:
        """Same precedence ``get_secret`` enforces — ``_FILE`` before direct."""
        clean_env.setenv("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY", "should-lose")
        clean_env.setenv("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE", str(secret_file))
        assert Settings().juniper_data_api_key == "CanopyDataKeyToken123"

    def test_prefixed_missing_file_falls_through(self, clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Missing file should not raise; the validator continues to the
        cross-service shared env var or default. Mirrors the cascor-worker
        ``_FILE`` fallthrough contract."""
        clean_env.setenv("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY_FILE", str(tmp_path / "nope.txt"))
        clean_env.setenv("JUNIPER_DATA_API_KEY", "shared-direct-fallback")
        assert Settings().juniper_data_api_key == "shared-direct-fallback"


class TestSharedCrossServiceEnv:
    """``JUNIPER_DATA_API_KEY[_FILE]`` — shared across cascor / canopy /
    data-client. Used when no canopy-prefixed override is set."""

    def test_shared_direct_returns_value(self, clean_env: pytest.MonkeyPatch) -> None:
        clean_env.setenv("JUNIPER_DATA_API_KEY", "shared-direct-key")
        assert Settings().juniper_data_api_key == "shared-direct-key"

    def test_shared_file_reads_content(self, clean_env: pytest.MonkeyPatch, secret_file: Path) -> None:
        clean_env.setenv("JUNIPER_DATA_API_KEY_FILE", str(secret_file))
        assert Settings().juniper_data_api_key == "CanopyDataKeyToken123"

    def test_prefixed_wins_over_shared(self, clean_env: pytest.MonkeyPatch) -> None:
        """Prefixed canonical takes precedence — operator can route a
        canopy-only key separately from cascor's."""
        clean_env.setenv("JUNIPER_CANOPY_JUNIPER_DATA_API_KEY", "prefixed-wins")
        clean_env.setenv("JUNIPER_DATA_API_KEY", "shared-loses")
        assert Settings().juniper_data_api_key == "prefixed-wins"


class TestDefault:
    """No env vars set — value is ``None`` (auth header omitted; matches
    pre-this-PR behaviour and remains backwards-compatible with stacks
    where juniper-data auth is disabled)."""

    def test_default_is_none(self, clean_env: pytest.MonkeyPatch) -> None:
        assert Settings().juniper_data_api_key is None
