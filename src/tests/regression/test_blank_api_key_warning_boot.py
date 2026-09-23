#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_blank_api_key_warning_boot.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-09-23
# Last Modified: 2026-09-23
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     APD-ECO-008 follow-up. A SET-but-blank CANOPY_API_KEY disables API-key auth, and the boot posture check words that
#     exactly like an unset key ("running OPEN"), so the blank case carries its own WARNING. The first version logged it
#     where the key is read: ``get_api_key_auth()``, which first runs at import (``api_key_auth = get_api_key_auth()`` in
#     main.py), before the lifespan's ``configure_logging``. There it reached only Python's last-resort handler -- no
#     level, no JSON, no Sentry, never logs/system.log -- and the test that covered it used ``caplog``, which hides that.
#     These tests run canopy's REAL lifespan and capture on the system logger that ``configure_logging`` has configured
#     by then, and they record whether configuration had already happened when the record arrived.
#
#####################################################################################################################################################################################################
"""Regression tests: the set-but-blank CANOPY_API_KEY WARNING is emitted by the lifespan, once, after logging is configured."""

import logging

import pytest
from fastapi.testclient import TestClient

# Written out rather than imported from security.py: an expectation imported from the
# module under test moves with any mutant that rewrites the advice there, and passes.
# src/tests/unit/test_security.py pins the same two texts at the unit level.
ENV_WARNING = "CANOPY_API_KEY is set but blank (empty or whitespace-only), so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured. Set a real key, or unset CANOPY_API_KEY for an intentional open profile."
FILE_WARNING = "The file named by CANOPY_API_KEY_FILE is blank (empty or whitespace-only), so API-key authentication is DISABLED: every route, including the state-changing /api/* routes and the /api/train/* control surface, serves without a key, exactly as with no key configured. While CANOPY_API_KEY_FILE names an existing file it takes precedence and CANOPY_API_KEY is not read. Write a real key into that file, or unset CANOPY_API_KEY_FILE to use CANOPY_API_KEY instead."

# Common to both texts and to nothing the posture check logs, so a mutant that rewords
# or repeats the WARNING is still COUNTED here, and fails on the count or the text.
BLANK_MARKER = "blank (empty or whitespace-only)"


class _Capture(logging.Handler):
    """Records every record with whether ``configure_logging`` had run when it arrived."""

    def __init__(self, state: dict) -> None:
        super().__init__(level=logging.DEBUG)
        self._state = state
        self.seen: list[tuple[logging.LogRecord, bool]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.seen.append((record, self._state["configured"]))


@pytest.fixture
def boot(monkeypatch):
    """Run canopy's real lifespan N times; return the blank-key records the system logger received."""
    import main
    from frontend import internal_api

    state = {"configured": False, "configure_calls": 0}
    real_configure_logging = main.configure_logging

    def configure_logging_spy(*args, **kwargs):
        real_configure_logging(*args, **kwargs)
        state["configured"] = True
        state["configure_calls"] += 1

    monkeypatch.setattr(main, "configure_logging", configure_logging_spy)
    # The stdlib logger behind ``main.system_logger``: its handlers write logs/system.log,
    # and it propagates to the root handler ``configure_logging`` installs.
    system = main.system_logger.logger
    capture = _Capture(state)
    system.addHandler(capture)

    def run(startups: int) -> list[tuple[logging.LogRecord, bool]]:
        for _ in range(startups):
            with TestClient(main.app):
                pass
        return [(record, configured) for record, configured in capture.seen if BLANK_MARKER in record.getMessage()]

    try:
        yield run, state
    finally:
        system.removeHandler(capture)
        # internal_api caches the key per process; never let a blank one outlive this test.
        internal_api._canopy_api_key.cache_clear()


def _read_key_as_main_does_at_import(monkeypatch, tmp_path, source: str) -> None:
    """Configure the key's source, then rebuild the auth singleton the way main.py's import does."""
    import security

    monkeypatch.delenv("CANOPY_API_KEY_FILE", raising=False)
    monkeypatch.delenv("CANOPY_API_KEY", raising=False)
    if source == "env-blank":
        monkeypatch.setenv("CANOPY_API_KEY", " \t ")
    elif source == "file-blank":
        secret_file = tmp_path / "canopy_api_key"
        secret_file.write_text("  \n", encoding="utf-8")
        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        # The case the first WARNING got wrong: the env var holds a real key the file overrides.
        monkeypatch.setenv("CANOPY_API_KEY", "real-key-the-file-overrides")
    elif source == "env-real":
        monkeypatch.setenv("CANOPY_API_KEY", "real-key")
    security.reset_security_state()
    security.get_api_key_auth()


@pytest.mark.parametrize("source, expected", [("env-blank", ENV_WARNING), ("file-blank", FILE_WARNING)], ids=["env", "file"])
def test_blank_key_warns_once_through_the_configured_logger(boot, monkeypatch, tmp_path, source, expected):
    run, state = boot
    _read_key_as_main_does_at_import(monkeypatch, tmp_path, source)

    blank = run(startups=2)

    assert state["configure_calls"] == 2, "both startups must have run the real lifespan"
    assert len(blank) == 1, f"exactly one blank-key record across two startups, got {[r.getMessage() for r, _ in blank]}"
    record, configured = blank[0]
    assert configured is True, "the WARNING must be emitted after configure_logging, not where the key is read"
    assert record.levelno == logging.WARNING
    assert record.getMessage() == expected


@pytest.mark.parametrize("source", ["unset", "env-real"])
def test_unset_or_real_key_emits_no_blank_key_warning(boot, monkeypatch, tmp_path, source):
    run, state = boot
    _read_key_as_main_does_at_import(monkeypatch, tmp_path, source)

    assert run(startups=1) == []
    assert state["configure_calls"] == 1


def test_lifespan_reports_right_after_the_posture_check():
    """Source-order pin, the companion of test_auth_posture_boot_check.py's: the report
    follows ``enforce_auth_posture`` and precedes the bind guard and backend creation."""
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "main.py").read_text(encoding="utf-8")
    posture = src.index("enforce_auth_posture(\n")
    report = src.index("report_blank_api_key(system_logger)")
    assert posture < report < src.index("enforce_loopback_bind_guard(\n") < src.index("create_backend(")
