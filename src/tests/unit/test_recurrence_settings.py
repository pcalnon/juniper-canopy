#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_settings.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-22
# Last Modified: 2026-06-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for the recurrence_service_url / recurrence_api_key
#                settings added by the model-selection A1 enabler (A1-i, D3) —
#                prefixed/shared precedence and _FILE secret indirection.
#####################################################################
"""Unit tests for the ``recurrence_service_url`` and ``recurrence_api_key`` settings.

Mirrors the resolution contract of the existing juniper-data outbound key:
the prefixed ``JUNIPER_CANOPY_*`` var wins over the shared cross-service var, and the
API key honors ``<NAME>_FILE`` indirection (Docker / k8s secret mounts). Construction is
hermetic — ``Settings(_env_file=None)`` so a stray ``.env`` cannot leak in — and an
autouse fixture clears the relevant env vars before each test.
"""

import pytest

from settings import Settings

_RECURRENCE_ENV_VARS = (
    "JUNIPER_CANOPY_RECURRENCE_SERVICE_URL",
    "RECURRENCE_SERVICE_URL",
    "JUNIPER_CANOPY_RECURRENCE_API_KEY",
    "JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE",
    "JUNIPER_RECURRENCE_API_KEY",
    "JUNIPER_RECURRENCE_API_KEY_FILE",
)


@pytest.fixture(autouse=True)
def _clean_recurrence_env(monkeypatch):
    """Strip any host-provided recurrence env vars so each test starts from a clean slate."""
    for var in _RECURRENCE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


def _settings() -> Settings:
    """Hermetic Settings: no ``.env`` file, only the (monkeypatched) process env."""
    return Settings(_env_file=None)


@pytest.mark.unit
class TestRecurrenceServiceUrl:
    """``recurrence_service_url`` precedence: prefixed → shared → None."""

    def test_default_is_none(self):
        assert _settings().recurrence_service_url is None

    def test_prefixed_var(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CANOPY_RECURRENCE_SERVICE_URL", "http://recurrence:8210")
        assert _settings().recurrence_service_url == "http://recurrence:8210"

    def test_shared_fallback(self, monkeypatch):
        monkeypatch.setenv("RECURRENCE_SERVICE_URL", "http://shared-recurrence:8210")
        assert _settings().recurrence_service_url == "http://shared-recurrence:8210"

    def test_prefixed_wins_over_shared(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CANOPY_RECURRENCE_SERVICE_URL", "http://prefixed:8210")
        monkeypatch.setenv("RECURRENCE_SERVICE_URL", "http://shared:8210")
        assert _settings().recurrence_service_url == "http://prefixed:8210"


@pytest.mark.unit
class TestRecurrenceApiKey:
    """``recurrence_api_key`` precedence: prefixed → shared → None, with _FILE support."""

    def test_default_is_none(self):
        assert _settings().recurrence_api_key is None

    def test_prefixed_direct(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CANOPY_RECURRENCE_API_KEY", "canopy-key")
        assert _settings().recurrence_api_key == "canopy-key"

    def test_shared_direct(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_RECURRENCE_API_KEY", "shared-key")
        assert _settings().recurrence_api_key == "shared-key"

    def test_prefixed_wins_over_shared(self, monkeypatch):
        monkeypatch.setenv("JUNIPER_CANOPY_RECURRENCE_API_KEY", "canopy-key")
        monkeypatch.setenv("JUNIPER_RECURRENCE_API_KEY", "shared-key")
        assert _settings().recurrence_api_key == "canopy-key"

    def test_prefixed_file_indirection(self, monkeypatch, tmp_path):
        secret = tmp_path / "recurrence_api_key"
        secret.write_text("file-key\n")  # trailing newline must be stripped
        monkeypatch.setenv("JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE", str(secret))
        assert _settings().recurrence_api_key == "file-key"

    def test_shared_file_indirection(self, monkeypatch, tmp_path):
        secret = tmp_path / "shared_recurrence_api_key"
        secret.write_text("shared-file-key\n")
        monkeypatch.setenv("JUNIPER_RECURRENCE_API_KEY_FILE", str(secret))
        assert _settings().recurrence_api_key == "shared-file-key"

    def test_prefixed_file_wins_over_shared_direct(self, monkeypatch, tmp_path):
        secret = tmp_path / "recurrence_api_key"
        secret.write_text("file-key")
        monkeypatch.setenv("JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE", str(secret))
        monkeypatch.setenv("JUNIPER_RECURRENCE_API_KEY", "shared-key")
        assert _settings().recurrence_api_key == "file-key"
