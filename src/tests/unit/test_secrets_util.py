"""Tests for Docker secrets utility: get_secret() and resolve_secret()."""

import pytest

from secrets_util import get_secret, resolve_secret


class TestGetSecret:
    """Tests for the get_secret() function."""

    @pytest.mark.unit
    def test_returns_none_when_neither_set(self, monkeypatch):
        """get_secret returns None when no env var and no file var are set."""
        monkeypatch.delenv("MY_SECRET", raising=False)
        monkeypatch.delenv("MY_SECRET_FILE", raising=False)

        assert get_secret("MY_SECRET") is None

    @pytest.mark.unit
    def test_reads_from_env_var(self, monkeypatch):
        """get_secret returns the value from the plain env var."""
        monkeypatch.setenv("MY_SECRET", "env-value")
        monkeypatch.delenv("MY_SECRET_FILE", raising=False)

        assert get_secret("MY_SECRET") == "env-value"

    @pytest.mark.unit
    def test_reads_from_file(self, monkeypatch, tmp_path):
        """get_secret reads the secret from a file when _FILE var is set."""
        secret_file = tmp_path / "my_secret"
        secret_file.write_text("file-value\n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == "file-value"

    @pytest.mark.unit
    def test_file_takes_precedence_over_env_var(self, monkeypatch, tmp_path):
        """File-based secret takes precedence when both are set."""
        secret_file = tmp_path / "my_secret"
        secret_file.write_text("file-value\n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.setenv("MY_SECRET", "env-value")

        assert get_secret("MY_SECRET") == "file-value"

    @pytest.mark.unit
    def test_default_file_env_var_naming(self, monkeypatch, tmp_path):
        """Default file env var is constructed as <env_var>_FILE."""
        secret_file = tmp_path / "canopy_api_key"
        secret_file.write_text("secret-from-file\n")

        monkeypatch.setenv("CANOPY_API_KEY_FILE", str(secret_file))
        monkeypatch.delenv("CANOPY_API_KEY", raising=False)

        # Should automatically check CANOPY_API_KEY_FILE
        assert get_secret("CANOPY_API_KEY") == "secret-from-file"

    @pytest.mark.unit
    def test_custom_file_env_var(self, monkeypatch, tmp_path):
        """Caller can specify a custom file env var name."""
        secret_file = tmp_path / "custom_secret"
        secret_file.write_text("custom-file-value\n")

        monkeypatch.setenv("CUSTOM_PATH", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)
        monkeypatch.delenv("MY_SECRET_FILE", raising=False)

        assert get_secret("MY_SECRET", file_env_var="CUSTOM_PATH") == "custom-file-value"

    @pytest.mark.unit
    def test_file_not_found_falls_back_to_env_var(self, monkeypatch):
        """When _FILE points to a non-existent file, falls back to env var."""
        monkeypatch.setenv("MY_SECRET_FILE", "/nonexistent/path/secret.txt")
        monkeypatch.setenv("MY_SECRET", "fallback-value")

        assert get_secret("MY_SECRET") == "fallback-value"

    @pytest.mark.unit
    def test_file_not_found_no_env_var_returns_none(self, monkeypatch):
        """When _FILE points to a non-existent file and no env var, returns None."""
        monkeypatch.setenv("MY_SECRET_FILE", "/nonexistent/path/secret.txt")
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") is None

    @pytest.mark.unit
    def test_strips_whitespace_from_file(self, monkeypatch, tmp_path):
        """Secret read from file is stripped of leading/trailing whitespace."""
        secret_file = tmp_path / "my_secret"
        secret_file.write_text("  secret-with-spaces  \n\n")

        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert get_secret("MY_SECRET") == "secret-with-spaces"


class TestResolveSecret:
    """``resolve_secret`` names the variable that supplied the value (APD-ECO-008 follow-up).

    ``security.get_api_key_auth`` words its blank-key WARNING by that name, so the name
    must follow ``get_secret``'s precedence exactly: the file wins only while the
    ``_FILE`` variable names an existing file.
    """

    @pytest.mark.unit
    def test_file_source_is_named_and_its_value_stripped(self, monkeypatch, tmp_path):
        secret_file = tmp_path / "my_secret"
        secret_file.write_text("  file-value \n")
        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.setenv("MY_SECRET", "env-value")

        assert resolve_secret("MY_SECRET") == ("file-value", "MY_SECRET_FILE")

    @pytest.mark.unit
    def test_a_blank_file_still_wins_over_the_env_var(self, monkeypatch, tmp_path):
        """The case a single blank-key message got wrong: the env var is not read at all."""
        secret_file = tmp_path / "my_secret"
        secret_file.write_text(" \t\n")
        monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        monkeypatch.setenv("MY_SECRET", "real-env-value")

        assert resolve_secret("MY_SECRET") == ("", "MY_SECRET_FILE")

    @pytest.mark.unit
    @pytest.mark.parametrize("value", ["env-value", "  padded  ", "", "   "])
    def test_env_source_is_named_and_its_value_returned_raw(self, monkeypatch, value):
        monkeypatch.delenv("MY_SECRET_FILE", raising=False)
        monkeypatch.setenv("MY_SECRET", value)

        assert resolve_secret("MY_SECRET") == (value, "MY_SECRET")

    @pytest.mark.unit
    def test_a_file_var_naming_no_file_leaves_the_env_var_the_source(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MY_SECRET_FILE", str(tmp_path / "absent"))
        monkeypatch.setenv("MY_SECRET", "   ")

        assert resolve_secret("MY_SECRET") == ("   ", "MY_SECRET")

    @pytest.mark.unit
    def test_neither_set_names_no_source(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MY_SECRET_FILE", str(tmp_path / "absent"))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert resolve_secret("MY_SECRET") == (None, None)

    @pytest.mark.unit
    def test_custom_file_env_var_is_the_name_reported(self, monkeypatch, tmp_path):
        secret_file = tmp_path / "custom_secret"
        secret_file.write_text("custom-file-value\n")
        monkeypatch.setenv("CUSTOM_PATH", str(secret_file))
        monkeypatch.delenv("MY_SECRET", raising=False)

        assert resolve_secret("MY_SECRET", file_env_var="CUSTOM_PATH") == ("custom-file-value", "CUSTOM_PATH")

    @pytest.mark.unit
    @pytest.mark.parametrize("file_content, env_value", [("file-value\n", "env-value"), (" \n", "env-value"), (None, "env-value"), (None, ""), (None, None)])
    def test_get_secret_returns_exactly_the_resolved_value(self, monkeypatch, tmp_path, file_content, env_value):
        if file_content is None:
            monkeypatch.delenv("MY_SECRET_FILE", raising=False)
        else:
            secret_file = tmp_path / "my_secret"
            secret_file.write_text(file_content)
            monkeypatch.setenv("MY_SECRET_FILE", str(secret_file))
        if env_value is None:
            monkeypatch.delenv("MY_SECRET", raising=False)
        else:
            monkeypatch.setenv("MY_SECRET", env_value)

        assert get_secret("MY_SECRET") == resolve_secret("MY_SECRET")[0]
