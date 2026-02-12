#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_cascor_lifecycle.py
# File Path:     src/tests/integration/
#
# Created Date:  2026-02-11
# Last Modified: 2026-02-11
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Integration tests for CasCor backend lifecycle:
#     create → configure → train → monitor → stop.
#
#     Uses MagicMock to bypass real CasCor module imports while
#     exercising the CascorIntegration orchestration logic.
#
#####################################################################################################################################################################################################
# Notes:
#     CascorIntegration.__init__ performs dynamic imports of the real
#     CasCor backend, so we use __new__ + manual attribute init with
#     patched internal helpers to create testable instances without
#     a real backend installation.
#
#####################################################################################################################################################################################################
# References:
#     src/backend/cascor_integration.py
#     CasCor backend lifecycle: create_network → install_monitoring_hooks
#       → start_monitoring_thread → stop_monitoring → shutdown
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#     LC-1 through LC-8 initial implementation
#
#####################################################################################################################################################################################################

import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from backend.cascor_integration import CascorIntegration
from backend.data_adapter import DataAdapter
from backend.training_monitor import TrainingMonitor


@pytest.fixture
def mock_cascor_integration():
    """Create a CascorIntegration instance with mocked backend dependencies.

    Bypasses __init__ which would try to resolve a real CasCor backend path
    and import backend modules.  Initializes the minimal attribute set that
    the public API relies on.
    """
    with (
        patch.object(CascorIntegration, "_resolve_backend_path"),
        patch.object(CascorIntegration, "_add_backend_to_path"),
        patch.object(CascorIntegration, "_import_backend_modules"),
    ):
        integration = CascorIntegration.__new__(CascorIntegration)
        integration.logger = MagicMock()
        integration.config_mgr = MagicMock()
        integration.network = None
        integration.cascade_correlation_instance = None
        integration.monitoring_active = False
        integration.monitoring_thread = None
        integration.monitoring_interval = 1.0
        integration._original_methods = {}
        integration.topology_lock = threading.Lock()
        integration.metrics_lock = threading.Lock()
        integration._shutdown_called = False
        integration._training_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="TestFit")
        integration._training_lock = threading.Lock()
        integration._training_future = None
        integration._training_stop_requested = False
        integration.data_adapter = MagicMock(spec=DataAdapter)
        integration.training_monitor = MagicMock(spec=TrainingMonitor)
        integration.backend_path = MagicMock()

        yield integration

        if integration._training_executor is not None:
            integration._training_executor.shutdown(wait=False)


@pytest.mark.integration
class TestCascorLifecycle:
    """Integration tests for the CasCor backend lifecycle."""

    def test_create_network_sets_network_attribute(self, mock_cascor_integration):
        """LC-1: After create_network(), the network attribute is not None."""
        integration = mock_cascor_integration

        mock_config_cls = MagicMock()
        mock_network_cls = MagicMock()
        mock_network_instance = MagicMock()
        mock_network_instance.input_size = 2
        mock_network_instance.output_size = 1
        mock_network_cls.return_value = mock_network_instance

        integration.CascadeCorrelationConfig = mock_config_cls
        integration.CascadeCorrelationNetwork = mock_network_cls

        result = integration.create_network({"input_size": 2, "output_size": 1})

        assert integration.network is not None
        assert integration.network is mock_network_instance
        assert result is mock_network_instance
        mock_network_cls.assert_called_once()

    def test_install_hooks_wraps_methods(self, mock_cascor_integration):
        """LC-2: install_monitoring_hooks() wraps fit/train methods."""
        integration = mock_cascor_integration

        mock_network = MagicMock()
        mock_network.fit = MagicMock(name="original_fit")
        mock_network.train_output_layer = MagicMock(name="original_train_output")
        mock_network.train_candidates = MagicMock(name="original_train_candidates")
        integration.network = mock_network

        result = integration.install_monitoring_hooks()

        assert result is True
        assert integration.monitoring_active is True
        assert "fit" in integration._original_methods
        assert "train_output_layer" in integration._original_methods
        assert "train_candidates" in integration._original_methods
        assert integration.network.fit is not integration._original_methods["fit"]

    def test_monitoring_thread_starts(self, mock_cascor_integration):
        """LC-3: start_monitoring_thread() creates and starts a daemon thread."""
        integration = mock_cascor_integration
        integration.network = MagicMock()

        started = threading.Event()

        def blocking_loop(interval):
            started.set()
            while integration.monitoring_active:
                threading.Event().wait(timeout=0.05)

        with patch.object(integration, "_monitoring_loop", side_effect=blocking_loop):
            integration.start_monitoring_thread(interval=0.1)
            started.wait(timeout=2.0)

            assert integration.monitoring_thread is not None
            assert integration.monitoring_thread.is_alive()
            assert integration.monitoring_active is True
            assert integration.monitoring_thread.daemon is True

            integration.monitoring_active = False
            integration.monitoring_thread.join(timeout=2.0)

    def test_monitoring_thread_stops(self, mock_cascor_integration):
        """LC-4: stop_monitoring() stops the monitoring thread cleanly."""
        integration = mock_cascor_integration
        integration.network = MagicMock()

        stop_event = threading.Event()

        def fake_loop(interval):
            while integration.monitoring_active:
                if stop_event.wait(timeout=0.05):
                    break

        with patch.object(integration, "_monitoring_loop", side_effect=fake_loop):
            integration.start_monitoring_thread(interval=0.1)
            assert integration.monitoring_thread.is_alive()

            stop_event.set()
            integration.stop_monitoring()

            assert integration.monitoring_active is False
            assert integration.monitoring_thread is None

    def test_shutdown_cleans_up_resources(self, mock_cascor_integration):
        """LC-5: shutdown() stops monitoring and cleans up the executor."""
        integration = mock_cascor_integration
        integration.network = MagicMock()
        integration.monitoring_active = True

        executor = integration._training_executor

        with (
            patch.object(integration, "stop_monitoring") as mock_stop,
            patch.object(integration, "restore_original_methods") as mock_restore,
            patch.object(integration, "request_training_stop") as mock_req_stop,
        ):
            integration.shutdown()

            mock_req_stop.assert_called_once()
            mock_stop.assert_called_once()
            mock_restore.assert_called_once()
            assert integration._shutdown_called is True
            assert integration._training_executor is None

        executor.shutdown(wait=False)

    def test_get_training_status_with_no_network(self, mock_cascor_integration):
        """LC-6: get_training_status() returns network_connected=False when network is None."""
        integration = mock_cascor_integration
        integration.network = None
        integration.training_monitor.get_current_state.return_value = {
            "is_training": False,
            "current_epoch": 0,
        }

        status = integration.get_training_status()

        assert status["network_connected"] is False
        assert status["input_size"] == 0
        assert status["output_size"] == 0
        assert status["hidden_units"] == 0

    def test_get_training_status_with_network(self, mock_cascor_integration):
        """LC-7: get_training_status() returns network_connected=True when network exists."""
        integration = mock_cascor_integration

        mock_network = MagicMock()
        mock_network.input_size = 2
        mock_network.output_size = 1
        mock_network.hidden_units = [MagicMock(), MagicMock(), MagicMock()]
        integration.network = mock_network
        integration.training_monitor.get_current_state.return_value = {
            "is_training": True,
            "current_epoch": 42,
        }

        status = integration.get_training_status()

        assert status["network_connected"] is True
        assert status["input_size"] == 2
        assert status["output_size"] == 1
        assert status["hidden_units"] == 3
        assert status["monitoring_active"] is False

    def test_get_dataset_info_delegates_to_juniper_data(self, mock_cascor_integration):
        """LC-8: get_dataset_info() calls JuniperData when no local data."""
        integration = mock_cascor_integration
        integration.network = MagicMock(spec=[])

        expected = {
            "inputs": [[0.1, 0.2]],
            "targets": [0],
            "num_samples": 1,
            "num_features": 2,
            "num_classes": 1,
        }

        with patch.object(
            integration,
            "_generate_missing_dataset_info",
            return_value=expected,
        ) as mock_gen:
            result = integration.get_dataset_info()

            mock_gen.assert_called_once()
            assert result == expected
