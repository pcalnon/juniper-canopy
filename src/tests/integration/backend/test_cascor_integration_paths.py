"""
Unit Tests for CascorIntegration Path Resolution

Tests path resolution, backend path validation, and import error handling.
"""

# import os
import sys

# from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.cascor_integration import CascorIntegration


@pytest.mark.unit
class TestCascorIntegrationPaths:
    """Test suite for CascorIntegration path resolution."""

    def test_resolve_backend_path_with_explicit_path(self, tmp_path):
        """Test _resolve_backend_path with explicit path argument."""
        # Create a fake backend directory
        backend_dir = tmp_path / "cascor_backend"
        backend_dir.mkdir(exist_ok=True)
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                result = integration._resolve_backend_path(str(backend_dir))
                # trunk-ignore(bandit/B101)
                assert result == backend_dir.resolve()
                # trunk-ignore(bandit/B101)
                assert result.exists()

    def test_resolve_backend_path_with_env_variable(self, tmp_path, monkeypatch):
        """Test _resolve_backend_path with environment variable."""
        backend_dir = tmp_path / "cascor_from_env"
        backend_dir.mkdir(exist_ok=True)
        monkeypatch.setenv("CASCOR_BACKEND_PATH", str(backend_dir))
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                result = self._get_backend_path()
                # trunk-ignore(bandit/B101)
                assert result == backend_dir.resolve()

    def test_resolve_backend_path_with_tilde_expansion(self, tmp_path, monkeypatch):
        """Test _resolve_backend_path with tilde expansion."""
        backend_dir = tmp_path / "cascor_home"
        backend_dir.mkdir(exist_ok=True)

        # Mock expanduser to return our tmp_path
        with patch("os.path.expanduser", return_value=str(backend_dir)):
            with patch.object(CascorIntegration, "_add_backend_to_path"):
                with patch.object(CascorIntegration, "_import_backend_modules"):
                    result = self._get_backend_path("~/cascor_home")
                    # trunk-ignore(bandit/B101)
                    assert result.exists()

    def test_resolve_backend_path_with_env_var_expansion(self, tmp_path, monkeypatch):
        """Test _resolve_backend_path with environment variable expansion."""
        backend_dir = tmp_path / "cascor_from_var"
        backend_dir.mkdir(exist_ok=True)
        monkeypatch.setenv("CUSTOM_PATH", str(backend_dir))
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                result = self._get_backend_path("$CUSTOM_PATH")
                # trunk-ignore(bandit/B101)
                assert result == backend_dir.resolve()

    def test_resolve_backend_path_missing_raises_error(self):
        """Test _resolve_backend_path raises FileNotFoundError for missing path."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()

                with pytest.raises(FileNotFoundError) as exc_info:
                    integration._resolve_backend_path("/nonexistent/path/to/cascor")

                # trunk-ignore(bandit/B101)
                assert "CasCor backend not found" in str(exc_info.value)
                # trunk-ignore(bandit/B101)
                assert "/nonexistent/path/to/cascor" in str(exc_info.value)

    def test_resolve_backend_path_from_config(self, tmp_path):
        """Test _resolve_backend_path falls back to config file."""
        backend_dir = tmp_path / "cascor_from_config"
        backend_dir.mkdir(exist_ok=True)
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                self._resolve_backend_path(backend_dir)

    def _resolve_backend_path(self, backend_dir):
        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()
        integration.config_mgr = MagicMock()
        integration.config_mgr.config = {"backend": {"cascor_integration": {"backend_path": str(backend_dir)}}}
        result = integration._resolve_backend_path(None)
        # trunk-ignore(bandit/B101)
        assert result == backend_dir.resolve()

    def _get_backend_path(self, backend_path=None):
        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()
        integration.config_mgr = MagicMock()
        integration.config_mgr.config = {"backend": {"cascor_integration": {"backend_path": None}}}
        return integration._resolve_backend_path(backend_path)

    def _extracted_from_test_import_backend_modules_missing_raises_error_8(self, backend_dir):
        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()
        integration.backend_path = backend_dir.resolve()
        return integration

    def test_resolve_backend_path_config_fallback_to_default(self, tmp_path):
        """Test _resolve_backend_path uses default when config has no path and env var not set."""
        with patch.object(CascorIntegration, "_add_backend_to_path"):
            with patch.object(CascorIntegration, "_import_backend_modules"):
                integration = CascorIntegration.__new__(CascorIntegration)
                integration.logger = MagicMock()
                integration.config_mgr = MagicMock()
                integration.config_mgr.config = {"backend": {"cascor_integration": {"backend_path": None}}}

                with pytest.raises(FileNotFoundError) as exc_info:
                    integration._resolve_backend_path(None)

                # trunk-ignore(bandit/B101)
                assert "CasCor backend not found" in str(exc_info.value)

    def test_add_backend_to_path_success(self, tmp_path):
        """Test _add_backend_to_path adds src directory to sys.path."""
        backend_dir = tmp_path / "cascor"
        backend_src = backend_dir / "src"
        backend_src.mkdir(parents=True, exist_ok=True)
        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = self._extracted_from_test_import_backend_modules_missing_raises_error_8(backend_dir)
            original_path = sys.path.copy()
            try:
                integration._add_backend_to_path()
                # trunk-ignore(bandit/B101)
                assert str(backend_src) in sys.path
            finally:
                # Restore original sys.path
                sys.path = original_path

    def test_add_backend_to_path_missing_src_raises_error(self, tmp_path):
        """Test _add_backend_to_path raises error when src/ directory missing."""
        backend_dir = tmp_path / "cascor_no_src"
        backend_dir.mkdir(exist_ok=True)
        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = self._extracted_from_test_import_backend_modules_missing_raises_error_8(backend_dir)
            with pytest.raises(FileNotFoundError) as exc_info:
                integration._add_backend_to_path()

            # trunk-ignore(bandit/B101)
            assert "src directory not found" in str(exc_info.value)
            # trunk-ignore(bandit/B101)
            assert str(backend_dir / "src") in str(exc_info.value)

    def test_add_backend_to_path_idempotent(self, tmp_path):
        """Test _add_backend_to_path doesn't add duplicate entries."""
        backend_dir = tmp_path / "cascor"
        backend_src = backend_dir / "src"
        backend_src.mkdir(parents=True, exist_ok=True)
        with patch.object(CascorIntegration, "_import_backend_modules"):
            integration = self._extracted_from_test_import_backend_modules_missing_raises_error_8(backend_dir)
            original_path = sys.path.copy()
            try:
                self._check_add_backend_to_path(integration, backend_src)
            finally:
                sys.path = original_path

    def _check_add_backend_to_path(self, integration: CascorIntegration = None, backend_src: sys.path = None):
        integration._add_backend_to_path()
        path_count_1 = sys.path.count(str(backend_src))

        integration._add_backend_to_path()
        path_count_2 = sys.path.count(str(backend_src))

        # trunk-ignore(bandit/B101)
        assert path_count_1 == path_count_2
        # trunk-ignore(bandit/B101)
        assert path_count_1 == 1

    def test_import_backend_modules_missing_raises_error(self, tmp_path):
        """Test _import_backend_modules raises ImportError when modules missing."""
        backend_dir = tmp_path / "cascor"
        backend_src = backend_dir / "src"
        backend_src.mkdir(parents=True, exist_ok=True)
        integration = self._extracted_from_test_import_backend_modules_missing_raises_error_8(backend_dir)
        with pytest.raises(ImportError) as exc_info:
            integration._import_backend_modules()

        # trunk-ignore(bandit/B101)
        assert "Failed to import CasCor backend modules" in str(exc_info.value)

    def test_import_backend_modules_success(self, tmp_path):
        """Test _import_backend_modules successfully imports mocked modules."""
        # Mock the imports
        mock_network_class = MagicMock(name="CascadeCorrelationNetwork")
        mock_config_class = MagicMock(name="CascadeCorrelationConfig")
        mock_results_class = MagicMock(name="TrainingResults")

        with patch.dict(
            "sys.modules",
            {
                "cascade_correlation": MagicMock(),
                "cascade_correlation.cascade_correlation": MagicMock(
                    CascadeCorrelationNetwork=mock_network_class, TrainingResults=mock_results_class
                ),
                "cascade_correlation.cascade_correlation_config": MagicMock(),
                "cascade_correlation.cascade_correlation_config.cascade_correlation_config": MagicMock(
                    CascadeCorrelationConfig=mock_config_class
                ),
            },
        ):
            self._checking_cascor_network_creation_with_results(
                mock_network_class=mock_network_class,
                mock_config_class=mock_config_class,
                mock_results_class=mock_results_class,
            )

    def _checking_cascor_network_creation_with_results(
        self,
        mock_network_class: MagicMock = None,
        mock_config_class: MagicMock = None,
        mock_results_class: MagicMock = None,
    ):
        integration = self._check_magic_mocks_against_cascor_network_and_config(
            mock_network_class=mock_network_class, mock_config_class=mock_config_class
        )
        # trunk-ignore(bandit/B101)
        assert integration.TrainingResults == mock_results_class

    def test_import_backend_modules_without_training_results(self):
        """Test _import_backend_modules handles missing TrainingResults gracefully."""
        mock_network_class = MagicMock(name="CascadeCorrelationNetwork")
        mock_config_class = MagicMock(name="CascadeCorrelationConfig")

        # Mock module without TrainingResults
        mock_cc_module = MagicMock()
        mock_cc_module.CascadeCorrelationNetwork = mock_network_class
        del mock_cc_module.TrainingResults  # Remove TrainingResults

        with patch.dict(
            "sys.modules",
            {
                "cascade_correlation": MagicMock(),
                "cascade_correlation.cascade_correlation": mock_cc_module,
                "cascade_correlation.cascade_correlation_config": MagicMock(),
                "cascade_correlation.cascade_correlation_config.cascade_correlation_config": MagicMock(
                    CascadeCorrelationConfig=mock_config_class
                ),
            },
        ):
            self._checking_cascor_network_creation_no_results(mock_network_class, mock_config_class)

    def _checking_cascor_network_creation_no_results(
        self, mock_network_class: MagicMock = None, mock_config_class: MagicMock = None
    ):
        integration = self._check_magic_mocks_against_cascor_network_and_config(
            mock_network_class=mock_network_class, mock_config_class=mock_config_class
        )
        # trunk-ignore(bandit/B101)
        assert integration.TrainingResults is None

    def _check_magic_mocks_against_cascor_network_and_config(
        self, mock_network_class: MagicMock = None, mock_config_class: MagicMock = None
    ):
        result = CascorIntegration.__new__(CascorIntegration)
        result.logger = MagicMock()
        result._import_backend_modules()
        # trunk-ignore(bandit/B101)
        assert result.CascadeCorrelationNetwork == mock_network_class
        # trunk-ignore(bandit/B101)
        assert result.CascadeCorrelationConfig == mock_config_class
        return result
