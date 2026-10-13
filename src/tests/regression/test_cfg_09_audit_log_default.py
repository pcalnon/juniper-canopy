#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# File Name:     test_cfg_09_audit_log_default.py
# Author:        Paul Calnon
# Version:       1.0.0
# Date:          2026-05-24
# Last Modified: 2026-05-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Regression tests for v7 roadmap CFG-09: audit_log_path
#                must default to a CWD-relative user-space path, not the
#                root-only /var/log/canopy/audit.log that crashed non-root
#                deployments at startup (audit_log.py:51 mkdir or :53
#                TimedRotatingFileHandler open).
#####################################################################

"""Regression tests for CFG-09 (v7 roadmap §13896).

Before this change ``Settings.audit_log_path`` defaulted to
``"/var/log/canopy/audit.log"`` (and the matching parameter default in
``configure_audit_logger()`` mirrored it). On a fresh non-root install
the mkdir at ``audit_log.py:51`` or the TimedRotatingFileHandler open
at lines 53-58 raised ``PermissionError``, crashing canopy at startup.

These tests pin three properties that together close the failure
class:

1. ``Settings().audit_log_path`` resolves to the new ``"logs/audit.log"``
   CWD-relative default (positive contract).
2. Neither ``Settings`` nor ``configure_audit_logger()`` carries the
   old ``/var/log/canopy/audit.log`` string anywhere (scope guard
   against silent re-introduction).
3. The ``JUNIPER_CANOPY_AUDIT_LOG_PATH`` env var still overrides the
   default end-to-end (production-deployment escape hatch must keep
   working). This is the documented production override path; CFG-09
   must not break it.
"""

import inspect
import sys
from pathlib import Path

import pytest

# ``src`` is the canopy import root; mirror the import path used by the
# sibling regression tests so the file is portable across worktrees.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from audit_log import configure_audit_logger  # noqa: E402
from settings import Settings  # noqa: E402

pytestmark = pytest.mark.regression


_NEW_DEFAULT = "logs/audit.log"
_OLD_ROOT_ONLY_DEFAULT = "/var/log/canopy/audit.log"


class TestCfg09AuditLogDefault:
    """Pin the post-CFG-09 default value at the Settings + audit_log layer."""

    def test_settings_default_is_relative_user_space_path(self, monkeypatch):
        """``Settings().audit_log_path`` must default to ``"logs/audit.log"``.

        The host environment may have ``JUNIPER_CANOPY_AUDIT_LOG_PATH``
        exported (e.g. a developer running tests inside an activated
        Juniper shell). Clear it explicitly so the test sees the
        baked-in default rather than the operator override.
        """
        monkeypatch.delenv("JUNIPER_CANOPY_AUDIT_LOG_PATH", raising=False)
        settings = Settings()
        assert settings.audit_log_path == _NEW_DEFAULT, f"Settings.audit_log_path default must be {_NEW_DEFAULT!r}, got {settings.audit_log_path!r} — CFG-09 regression."

    def test_configure_audit_logger_parameter_default_matches(self):
        """``configure_audit_logger()`` parameter default must match Settings.

        The two defaults are deliberately duplicated (one for the
        pydantic field, one for the function signature) so callers that
        invoke ``configure_audit_logger()`` directly without passing
        ``settings.audit_log_path`` still get a user-space path. Keeping
        them in lockstep is the CFG-09 invariant.
        """
        sig = inspect.signature(configure_audit_logger)
        actual = sig.parameters["log_path"].default
        assert actual == _NEW_DEFAULT, f"configure_audit_logger(log_path) default must be {_NEW_DEFAULT!r}, got {actual!r} — CFG-09 regression."


class TestCfg09NoRootOnlyDefaultRemains:
    """Scope guard: the old root-only default string must not reappear."""

    def test_settings_source_has_no_var_log_default(self):
        """``settings.py`` source must not contain the old root-only default literal."""
        src = (Path(__file__).resolve().parents[2] / "settings.py").read_text()
        # Allow the comment block that documents the migration to mention
        # the old path (educates future readers). Block any *non-comment*
        # line that re-introduces the literal as a default value.
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert _OLD_ROOT_ONLY_DEFAULT not in line, f"settings.py reintroduced {_OLD_ROOT_ONLY_DEFAULT!r} on a non-comment line (CFG-09 regression): {line!r}"

    def test_audit_log_source_has_no_var_log_default(self):
        """``audit_log.py`` source must not contain the old root-only default literal."""
        src = (Path(__file__).resolve().parents[2] / "audit_log.py").read_text()
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            assert _OLD_ROOT_ONLY_DEFAULT not in line, f"audit_log.py reintroduced {_OLD_ROOT_ONLY_DEFAULT!r} on a non-comment line (CFG-09 regression): {line!r}"


class TestCfg09EnvVarOverrideStillWorks:
    """Production override path must keep working post-CFG-09."""

    def test_env_var_override_resolves(self, monkeypatch):
        """``JUNIPER_CANOPY_AUDIT_LOG_PATH`` env var must override the default.

        Production deployments rely on this to point audit logs at a
        deployment-specific location (e.g. ``/srv/canopy/audit.log``,
        a Docker volume mount, etc.). The CFG-09 fix is a default-value
        change only; the env-var escape hatch must keep working.
        """
        monkeypatch.setenv("JUNIPER_CANOPY_AUDIT_LOG_PATH", "/custom/canopy/audit.log")
        settings = Settings()
        assert settings.audit_log_path == "/custom/canopy/audit.log", "JUNIPER_CANOPY_AUDIT_LOG_PATH env var override no longer resolves into Settings — production deployments would lose their override path."
