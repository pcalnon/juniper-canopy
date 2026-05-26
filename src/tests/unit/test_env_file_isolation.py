"""Regression: a developer's local .env must not pollute the test session.

Background. ``src/settings.py`` configures pydantic-settings with
``env_file=".env"``, so every ``Settings()`` constructor call reads
``./.env`` (the gitignored, developer-local copy of ``.env.example``).
pydantic-settings layers .env *under* ``os.environ``, which means
``monkeypatch.delenv("JUNIPER_CANOPY_AUDIT_LOG_PATH")`` (and similar
``CFG-NN`` test patterns) removes the OS-level value but leaves the
.env value in effect.

CI never reproduces this — runner checkouts have no ``.env`` — so the
failure mode is strictly local. The fix is an autouse session-scoped
fixture in ``src/tests/conftest.py``
(``_disable_settings_env_file_for_tests``) that sets
``Settings.model_config["env_file"] = None`` for the session. This
regression test pins that behavior so a future refactor that drops
or breaks the fixture fails loudly here, not via the mysterious
``settings.audit_log_path == '/var/log/...'`` (or whatever the dev
happens to have in their .env) failure.

Sibling pin landed first in juniper-cascor PR #309 (2026-05-26); see
``src/tests/unit/test_env_file_isolation.py`` there for the cascor
version of this same pattern.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Mirror conftest.py's sys.path bootstrapping so this test can import
# ``settings`` whether it's run via ``pytest src/tests/...`` or
# ``cd src && pytest tests/...``.
_SRC = Path(__file__).resolve().parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from settings import Settings  # noqa: E402

pytestmark = pytest.mark.unit


class TestSettingsEnvFileIsolation:
    """Pin the conftest autouse fixture that disables .env loading in tests."""

    def test_settings_env_file_is_none_during_test_session(self):
        """The session-scoped autouse fixture must set env_file to None.

        Direct read of ``Settings.model_config["env_file"]`` after pytest
        has loaded conftest.py. If this assertion fails, the
        ``_disable_settings_env_file_for_tests`` fixture has been
        dropped, renamed, or its scope/autouse semantics broken.
        """
        assert Settings.model_config.get("env_file") is None, "Settings.model_config['env_file'] should be None for the test session. " "Check src/tests/conftest.py::_disable_settings_env_file_for_tests."

    def test_local_dot_env_in_cwd_does_not_leak_into_settings(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Behavioral check: a .env in CWD must not override class defaults.

        Synthesizes a temp directory with a polluting ``.env`` that
        sets ``JUNIPER_CANOPY_AUDIT_LOG_PATH``, chdirs into it, clears
        the same env var from ``os.environ``, and verifies that
        ``Settings()`` returns the class default rather than the value
        written to the file. This exercises the actual anti-regression
        contract — even if the fixture's mechanism changes (e.g. from
        ``env_file=None`` to a chdir+stub approach), as long as
        ``.env`` does not leak in, this test passes.

        ``audit_log_path`` is the canonical CFG-09 field that triggered
        the cross-repo investigation; pinning it here means the
        ``test_cfg_09_audit_log_default.py`` regression test stays
        deterministic regardless of developer environment.
        """
        leaked_value = "/etc/leaked/by/dot-env/audit.log"
        env_file = tmp_path / ".env"
        env_file.write_text(
            f"JUNIPER_CANOPY_AUDIT_LOG_PATH={leaked_value}\n",
            encoding="utf-8",
        )

        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("JUNIPER_CANOPY_AUDIT_LOG_PATH", raising=False)

        # Sanity: confirm the file we just wrote is visible from CWD.
        assert (Path.cwd() / ".env").exists(), "Test setup failed: .env not written to tmp_path"

        # Sanity: confirm the env var is actually unset.
        assert "JUNIPER_CANOPY_AUDIT_LOG_PATH" not in os.environ

        settings = Settings()

        assert settings.audit_log_path != leaked_value, f"Settings.audit_log_path leaked from the .env in CWD (got {settings.audit_log_path!r}). " "The autouse fixture in conftest.py is no longer preventing pydantic-settings from " "reading the developer's local .env."
