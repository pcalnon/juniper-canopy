#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Integration tests for real CasCor backend initialization path in main.py lifespan
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     test_cascor_real_backend_init.py
# File Path:     src/tests/integration/
#
# Created Date:  2026-02-11
# Last Modified: 2026-02-11
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Validates Fix 1 (RC-1, RC-2) from the regression analysis: the real backend
#     initialization path in the lifespan handler of main.py. When cascor_integration
#     is not None and demo_mode_active is False, the lifespan must call
#     create_network(), get_dataset_info(), install_monitoring_hooks(),
#     start_monitoring_thread(), and setup_monitoring_callbacks().
#
#     Tests run under CASCOR_DEMO_MODE=1 (forced by conftest.py) so the real backend
#     path is exercised by patching module-level globals in main.py.
#
#####################################################################################################################################################################################################
# Notes:
#     - conftest.py forces CASCOR_DEMO_MODE=1, so we mock main.demo_mode_active = False
#       and main.cascor_integration = <MagicMock> to simulate the real backend path.
#     - Uses FastAPI TestClient which triggers the lifespan context manager.
#
#####################################################################################################################################################################################################
# References:
#     - Fix 1 (RC-1, RC-2) regression analysis
#     - src/main.py lifespan() lines 154-199
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     - Initial implementation with 7 integration tests
#
#####################################################################################################################################################################################################

from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient


def _make_mock_integration():
    """Create a pre-configured MagicMock for CascorIntegration."""
    mock = MagicMock()
    mock.create_network.return_value = MagicMock()
    mock.install_monitoring_hooks.return_value = True
    mock.get_dataset_info.return_value = {"num_samples": 200, "num_classes": 2}
    mock.get_training_status.return_value = {"is_training": False}
    mock.start_monitoring_thread.return_value = None
    mock.create_monitoring_callback.return_value = None
    mock.shutdown.return_value = None
    return mock


@pytest.mark.integration
class TestRealBackendInit:
    """Integration tests for the real CasCor backend initialization in lifespan."""

    def test_real_backend_creates_network(self):
        """Verify create_network is called with config-driven defaults."""
        mock_integration = self._create_mock_integration()
        mock_integration.create_network.assert_called_once()
        network_config = mock_integration.create_network.call_args[0][0]
        assert "input_size" in network_config
        assert "output_size" in network_config
        assert "learning_rate" in network_config
        assert "max_hidden_units" in network_config
        assert "max_epochs" in network_config

    def test_real_backend_installs_monitoring_hooks(self):
        """Verify install_monitoring_hooks is called during initialization."""
        mock_integration = _make_mock_integration()

        with (
            patch("main.demo_mode_active", False),
            patch("main.backend", mock_integration),
            patch("main.setup_monitoring_callbacks"),
        ):
            from main import app

            with TestClient(app):
                pass

        mock_integration.install_monitoring_hooks.assert_called_once()

    def test_real_backend_starts_monitoring_thread(self):
        """Verify start_monitoring_thread is called with interval=1.0."""
        mock_integration = _make_mock_integration()

        with (
            patch("main.demo_mode_active", False),
            patch("main.backend", mock_integration),
            patch("main.setup_monitoring_callbacks"),
        ):
            from main import app

            with TestClient(app):
                pass

        mock_integration.start_monitoring_thread.assert_called_once_with(interval=1.0)

    def test_real_backend_setup_monitoring_callbacks(self):
        """Verify setup_monitoring_callbacks is invoked to register WebSocket broadcast callbacks."""
        mock_integration = self._create_mock_integration()
        assert mock_integration

    # TODO Rename this here and in `test_real_backend_creates_network` and `test_real_backend_setup_monitoring_callbacks`
    # def _extracted_from_test_real_backend_setup_monitoring_callbacks_3(self):
    def _create_mock_integration(self):
        result = _make_mock_integration()
        with patch("main.demo_mode_active", False), patch("main.backend", result), patch("main.setup_monitoring_callbacks") as mock_setup_cb:
            from main import app

            with TestClient(app):
                pass
        mock_setup_cb.assert_called_once()
        return result

    def test_real_backend_fetches_dataset(self):
        """Verify get_dataset_info is called during backend initialization."""
        mock_integration = _make_mock_integration()

        with (
            patch("main.demo_mode_active", False),
            patch("main.backend", mock_integration),
            patch("main.setup_monitoring_callbacks"),
        ):
            from main import app

            with TestClient(app):
                pass

        mock_integration.get_dataset_info.assert_called_once()

    def test_real_backend_handles_network_creation_failure(self):
        """Verify graceful degradation when create_network raises an exception."""
        mock_integration = _make_mock_integration()
        mock_integration.create_network.side_effect = RuntimeError("Network creation failed")

        with (
            patch("main.demo_mode_active", False),
            patch("main.backend", mock_integration),
            patch("main.setup_monitoring_callbacks"),
        ):
            from main import app

            with TestClient(app):
                pass

        mock_integration.create_network.assert_called_once()
        mock_integration.install_monitoring_hooks.assert_not_called()
        mock_integration.start_monitoring_thread.assert_not_called()

    def test_real_backend_handles_dataset_fetch_failure(self):
        """Verify graceful handling when get_dataset_info raises an exception."""
        mock_integration = _make_mock_integration()
        mock_integration.get_dataset_info.side_effect = ConnectionError("JuniperData unavailable")

        with (
            patch("main.demo_mode_active", False),
            patch("main.backend", mock_integration),
            patch("main.setup_monitoring_callbacks"),
        ):
            from main import app

            with TestClient(app):
                pass

        mock_integration.get_dataset_info.assert_called_once()
        mock_integration.install_monitoring_hooks.assert_called_once()
        mock_integration.start_monitoring_thread.assert_called_once()
