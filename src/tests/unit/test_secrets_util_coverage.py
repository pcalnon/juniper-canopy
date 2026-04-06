"""Extended coverage tests for secrets_util.py.

Covers empty files, directories instead of files, unicode content,
symlinks, and multi-line secret files (SOPS-related edge cases).
"""

import os

import pytest

from secrets_util import get_secret


@pytest.mark.unit
class TestGetSecretEdgeCases:
    """Edge case tests for get_secret()."""

    def test_empty_file_returns_empty_string(self, monkeypatch, tmp_path):
        """Empty secret file returns empty string (after strip)."""
        secret_file = tmp_path / "empty_secret"
        secret_file.write_text("")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == ""

    def test_whitespace_only_file_returns_empty_string(self, monkeypatch, tmp_path):
        """File with only whitespace returns empty string after strip."""
        secret_file = tmp_path / "ws_secret"
        secret_file.write_text("   \n\n  \t  \n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == ""

    def test_directory_path_is_not_read(self, monkeypatch, tmp_path):
        """When _FILE points to a directory, falls back to env var."""
        monkeypatch.setenv("MY_SECRET_FILE", str(tmp_path))
        monkeypatch.setenv("MY_SECRET", "env-fallback")

        assert get_secret("MY_SECRET") == "env-fallback"

    def test_directory_path_no_env_returns_none(self, monkeypatch, tmp_path):
        """When _FILE points to a directory and no env var, returns None."""
        monkeypatch.setenv("MY_SECRET_FILE", str(tmp_path))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") is None

    def test_unicode_content_in_file(self, monkeypatch, tmp_path):
        """Secret files with unicode content are read correctly."""
        secret_file = tmp_path / "unicode_secret"
        secret_file.write_text("sécret-kéy-🔐\n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == "sécret-kéy-🔐"

    def test_multiline_file_returns_full_stripped_content(self, monkeypatch, tmp_path):
        """Multi-line secret file returns full content (only leading/trailing whitespace stripped)."""
        secret_file = tmp_path / "multiline_secret"
        secret_file.write_text("  line1\nline2\nline3  \n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        result = get_secret("MY_SECRET")
        assert result == "line1\nline2\nline3"

    def test_symlink_to_secret_file(self, monkeypatch, tmp_path):
        """Symlinked secret file is readable."""
        real_file = tmp_path / "real_secret"
        real_file.write_text("symlinked-value\n")
        link = tmp_path / "link_secret"
        link.symlink_to(real_file)

        monkeypatch.setenv("MY_SECRET_FILE", str(link))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == "symlinked-value"

    def test_file_env_var_set_to_empty_string(self, monkeypatch):
        """Empty _FILE env var is falsy, falls back to env var."""
        monkeypatch.setenv("MY_SECRET_FILE", "")
        monkeypatch.setenv("MY_SECRET", "env-value")

        assert get_secret("MY_SECRET") == "env-value"

    def test_env_var_preserves_whitespace(self, monkeypatch):
        """Plain env var value is NOT stripped (only file content is stripped)."""
        monkeypatch.delenv("MY_SECRET_FILE", raising=False)
        monkeypatch.setenv("MY_SECRET", "  padded  ")

        # os.environ.get returns the raw value
        assert get_secret("MY_SECRET") == "  padded  "

    def test_broken_symlink_falls_back(self, monkeypatch, tmp_path):
        """Broken symlink falls back to env var."""
        broken_link = tmp_path / "broken_link"
        broken_link.symlink_to(tmp_path / "nonexistent")

        monkeypatch.setenv("MY_SECRET_FILE", str(broken_link))
        monkeypatch.setenv("MY_SECRET", "fallback")

        assert get_secret("MY_SECRET") == "fallback"

    def test_docker_run_secrets_path(self, monkeypatch, tmp_path):
        """Typical Docker /run/secrets/ path works."""
        secret_file = tmp_path / "run" / "secrets" / "api_key"
        secret_file.parent.mkdir(parents=True)
        secret_file.write_text("docker-secret-value\n")

        monkeypatch.setenv("API_KEY_FILE", str(secret_file))
        monkeypatch.delenv("API_KEY", raising=False)

        assert get_secret("API_KEY") == "docker-secret-value"

    def test_long_secret_value(self, monkeypatch, tmp_path):
        """Very long secret values are handled correctly."""
        long_value = "a" * 10000
        secret_file = tmp_path / "long_secret"
        secret_file.write_text(long_value + "\n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == long_value
