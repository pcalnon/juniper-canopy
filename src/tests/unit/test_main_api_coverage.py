#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_main_api_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-12-13
# Last Modified: 2025-12-13
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for main.py API endpoints focusing on backend-mode branches
#                to improve coverage from 67% target.
#####################################################################
"""
Unit tests for main.py API endpoints with focus on:
- schedule_broadcast function edge cases
- CasCor backend mode branches
- No-backend (503) error paths
- Training control endpoints in all modes

These tests directly call the endpoint async functions to avoid lifespan
initialization issues with demo mode.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is in path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


# =============================================================================
# Test schedule_broadcast function
# =============================================================================
class TestScheduleBroadcast:
    """Test schedule_broadcast helper function edge cases."""

    def test_schedule_broadcast_loop_is_none_logs_warning(self):
        """When loop_holder['loop'] is None, should log warning."""
        import main

        original_loop = main.loop_holder["loop"]
        try:
            main.loop_holder["loop"] = None

            async def mock_coro():
                pass

            with patch.object(main.system_logger, "warning") as mock_warning:
                main.schedule_broadcast(mock_coro())
                mock_warning.assert_called_once_with("Event loop not available for broadcasting")
        finally:
            main.loop_holder["loop"] = original_loop

    def test_schedule_broadcast_loop_is_closed_logs_warning(self):
        """When loop_holder['loop'] is closed, should log warning."""
        import main

        original_loop = main.loop_holder["loop"]
        try:
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = True
            main.loop_holder["loop"] = mock_loop

            async def mock_coro():
                pass

            with patch.object(main.system_logger, "warning") as mock_warning:
                main.schedule_broadcast(mock_coro())
                mock_warning.assert_called_once_with("Event loop not available for broadcasting")
        finally:
            main.loop_holder["loop"] = original_loop

    def test_schedule_broadcast_loop_open_calls_run_coroutine_threadsafe(self):
        """When loop is open, should call run_coroutine_threadsafe."""
        import main

        original_loop = main.loop_holder["loop"]
        try:
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            async def mock_coro():
                pass

            coro = mock_coro()
            with patch("main.asyncio.run_coroutine_threadsafe") as mock_run:
                main.schedule_broadcast(coro)
                mock_run.assert_called_once_with(coro, mock_loop)
        finally:
            main.loop_holder["loop"] = original_loop

    def test_schedule_broadcast_exception_logs_error(self):
        """When run_coroutine_threadsafe raises, should log error."""
        import main

        original_loop = main.loop_holder["loop"]
        try:
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            async def mock_coro():
                pass

            with (
                patch("main.asyncio.run_coroutine_threadsafe", side_effect=RuntimeError("test error")),
                patch.object(main.system_logger, "error") as mock_error,
            ):
                main.schedule_broadcast(mock_coro())
                mock_error.assert_called_once()
                assert "Failed to schedule broadcast" in str(mock_error.call_args)
        finally:
            main.loop_holder["loop"] = original_loop


# =============================================================================
# Test /api/topology endpoint - direct async function calls
# =============================================================================
class TestTopologyEndpointDirect:
    """Test /api/topology endpoint by calling async function directly."""

    @pytest.mark.asyncio
    async def test_topology_cascor_mode_returns_topology(self):
        """CasCor mode should call extract_network_topology."""
        import main

        mock_topology = MagicMock()
        mock_topology.to_dict.return_value = {
            "input_units": 3,
            "hidden_units": 2,
            "output_units": 1,
            "nodes": [],
            "connections": [],
        }

        mock_cascor = MagicMock()
        mock_cascor.extract_network_topology.return_value = mock_topology

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_topology()

            mock_cascor.extract_network_topology.assert_called_once()
            assert result == mock_topology.to_dict.return_value
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_topology_cascor_mode_no_topology_returns_503(self):
        """CasCor mode with no topology should return 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_cascor = MagicMock()
        mock_cascor.extract_network_topology.return_value = None

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_topology()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_topology_no_backend_returns_503(self):
        """No backend available should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_topology()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /api/dataset endpoint - direct async function calls
# =============================================================================
class TestDatasetEndpointDirect:
    """Test /api/dataset endpoint by calling async function directly."""

    @pytest.mark.asyncio
    async def test_dataset_cascor_mode_returns_data(self):
        """CasCor mode should return dataset from get_dataset_info."""
        import main

        mock_cascor = MagicMock()
        mock_cascor.get_dataset_info.return_value = {
            "inputs": [[1.0, 2.0], [3.0, 4.0]],
            "targets": [0, 1],
            "num_samples": 2,
        }

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_dataset()

            mock_cascor.get_dataset_info.assert_called_once()
            assert result["num_samples"] == 2
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_dataset_cascor_mode_no_data_returns_503(self):
        """CasCor mode with no dataset should return 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_cascor = MagicMock()
        mock_cascor.get_dataset_info.return_value = None

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_dataset()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_dataset_no_backend_returns_503(self):
        """No backend available should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_dataset()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /api/decision_boundary endpoint - direct async function calls
# =============================================================================
class TestDecisionBoundaryEndpointDirect:
    """Test /api/decision_boundary endpoint by calling async function directly."""

    @pytest.mark.asyncio
    async def test_decision_boundary_cascor_mode_with_predict_fn(self):
        """CasCor mode with predict function should log info then return 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_predict_fn = MagicMock()
        mock_cascor = MagicMock()
        mock_cascor.get_prediction_function.return_value = mock_predict_fn

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_decision_boundary()

            mock_cascor.get_prediction_function.assert_called_once()
            # Currently returns 503 as cascor path doesn't compute boundary
            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_decision_boundary_no_backend_returns_503(self):
        """No backend available should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_decision_boundary()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test Training Control Endpoints - direct async function calls
# =============================================================================
class TestTrainingControlEndpointsDirect:
    """Test POST training control endpoints by calling async functions directly."""

    # ---- /api/train/start ----
    @pytest.mark.asyncio
    async def test_train_start_demo_mode_returns_started(self):
        """Demo mode start should return started status."""
        import main

        mock_demo = MagicMock()
        mock_demo.start.return_value = {"current_epoch": 0, "is_running": True}

        original_demo_instance = main.demo_mode_instance
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = mock_demo
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_start(reset=False)

            mock_demo.start.assert_called_once_with(reset=False)
            assert result["status"] == "started"
        finally:
            main.demo_mode_instance = original_demo_instance
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_start_cascor_mode_returns_unimplemented(self):
        """CasCor mode start should return unimplemented status."""
        import main

        mock_cascor = MagicMock()

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_start(reset=False)

            assert result["status"] == "unimplemented"
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_start_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_start(reset=False)

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/pause ----
    @pytest.mark.asyncio
    async def test_train_pause_demo_mode_returns_paused(self):
        """Demo mode pause should return paused status."""
        import main

        mock_demo = MagicMock()

        original_demo_instance = main.demo_mode_instance
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = mock_demo
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_pause()

            mock_demo.pause.assert_called_once()
            assert result["status"] == "paused"
        finally:
            main.demo_mode_instance = original_demo_instance
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_pause_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_pause()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/resume ----
    @pytest.mark.asyncio
    async def test_train_resume_demo_mode_returns_running(self):
        """Demo mode resume should return running status."""
        import main

        mock_demo = MagicMock()

        original_demo_instance = main.demo_mode_instance
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = mock_demo
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_resume()

            mock_demo.resume.assert_called_once()
            assert result["status"] == "running"
        finally:
            main.demo_mode_instance = original_demo_instance
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_resume_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_resume()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/stop ----
    @pytest.mark.asyncio
    async def test_train_stop_demo_mode_returns_stopped(self):
        """Demo mode stop should return stopped status."""
        import main

        mock_demo = MagicMock()

        original_demo_instance = main.demo_mode_instance
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = mock_demo
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_stop()

            mock_demo.stop.assert_called_once()
            assert result["status"] == "stopped"
        finally:
            main.demo_mode_instance = original_demo_instance
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_stop_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_stop()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/reset ----
    @pytest.mark.asyncio
    async def test_train_reset_demo_mode_returns_reset_state(self):
        """Demo mode reset should return reset status with state."""
        import main

        mock_demo = MagicMock()
        mock_demo.reset.return_value = {"current_epoch": 0, "is_running": False}

        original_demo_instance = main.demo_mode_instance
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = mock_demo
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_reset()

            mock_demo.reset.assert_called_once()
            assert result["status"] == "reset"
        finally:
            main.demo_mode_instance = original_demo_instance
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_reset_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration
        original_loop = main.loop_holder["loop"]

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_reset()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor
            main.loop_holder["loop"] = original_loop


# =============================================================================
# Test /api/metrics/history endpoint - direct async function calls
# =============================================================================
class TestMetricsHistoryEndpointDirect:
    """Test /api/metrics/history by calling async function directly."""

    @pytest.mark.asyncio
    async def test_metrics_history_cascor_mode_returns_history(self):
        """CasCor mode should return history from training_monitor."""
        import main

        mock_metric1 = MagicMock()
        mock_metric1.to_dict.return_value = {"epoch": 1, "loss": 0.5}
        mock_metric2 = MagicMock()
        mock_metric2.to_dict.return_value = {"epoch": 2, "loss": 0.3}

        mock_training_monitor = MagicMock()
        mock_training_monitor.get_recent_metrics.return_value = [mock_metric1, mock_metric2]

        mock_cascor = MagicMock()
        mock_cascor.training_monitor = mock_training_monitor

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_metrics_history()

            assert "history" in result
            assert len(result["history"]) == 2
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_metrics_history_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_metrics_history()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /api/metrics endpoint - direct async function calls
# =============================================================================
class TestMetricsEndpointDirect:
    """Test /api/metrics by calling async function directly."""

    @pytest.mark.asyncio
    async def test_metrics_cascor_mode_with_to_dict(self):
        """CasCor mode metrics with to_dict method."""
        import main

        mock_metrics = MagicMock()
        mock_metrics.to_dict.return_value = {"epoch": 5, "loss": 0.2}

        mock_training_monitor = MagicMock()
        mock_training_monitor.get_current_metrics.return_value = mock_metrics

        mock_cascor = MagicMock()
        mock_cascor.training_monitor = mock_training_monitor

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_metrics()

            assert result["epoch"] == 5
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_metrics_cascor_mode_without_to_dict(self):
        """CasCor mode metrics without to_dict (returns dict directly)."""
        import main

        # Use a plain dict without to_dict method
        mock_metrics = {"epoch": 10, "loss": 0.1}

        mock_training_monitor = MagicMock()
        mock_training_monitor.get_current_metrics.return_value = mock_metrics

        mock_cascor = MagicMock()
        mock_cascor.training_monitor = mock_training_monitor

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_metrics()

            assert result["epoch"] == 10
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_metrics_no_backend_returns_empty(self):
        """No backend should return empty dict."""
        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_metrics()

            assert result == {}
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /api/status endpoint - direct async function calls
# =============================================================================
class TestStatusEndpointDirect:
    """Test /api/status by calling async function directly."""

    @pytest.mark.asyncio
    async def test_status_cascor_mode_returns_training_status(self):
        """CasCor mode should call get_training_status."""
        import main

        mock_cascor = MagicMock()
        mock_cascor.get_training_status.return_value = {
            "is_training": True,
            "network_connected": True,
            "current_epoch": 50,
        }

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.get_status()

            mock_cascor.get_training_status.assert_called_once()
            assert result["is_training"] is True
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_status_no_backend_returns_inactive(self):
        """No backend should return is_training=False."""
        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_status()

            assert result["is_training"] is False
            assert result["network_connected"] is False
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /api/network/stats endpoint - direct async function calls
# =============================================================================
class TestNetworkStatsEndpointDirect:
    """Test /api/network/stats by calling async function directly."""

    @pytest.mark.asyncio
    async def test_network_stats_cascor_mode_returns_stats(self):
        """CasCor mode should call get_network_data."""
        import numpy as np

        import main

        mock_cascor = MagicMock()
        mock_cascor.get_network_data.return_value = {
            "input_weights": np.array([[0.1, 0.2]]),
            "hidden_weights": None,
            "output_weights": np.array([[0.3]]),
            "hidden_biases": None,
            "output_biases": np.array([0.1]),
            "threshold_function": "tanh",
            "optimizer": "adam",
        }

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            await main.get_network_stats()

            mock_cascor.get_network_data.assert_called_once()
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_network_stats_no_backend_returns_503(self):
        """No backend should return 503."""
        from fastapi.responses import JSONResponse

        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.get_network_stats()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /health endpoint - direct async function calls
# =============================================================================
class TestHealthEndpointDirect:
    """Test /health by calling async function directly."""

    @pytest.mark.asyncio
    async def test_health_cascor_mode_with_training_monitor(self):
        """CasCor mode with training_monitor should check is_training."""
        import main

        mock_training_monitor = MagicMock()
        mock_training_monitor.is_training = True

        mock_cascor = MagicMock()
        mock_cascor.training_monitor = mock_training_monitor

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = mock_cascor

            result = await main.health_check()

            assert result["training_active"] is True
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor

    @pytest.mark.asyncio
    async def test_health_no_backend_returns_inactive(self):
        """No backend should return training_active=False."""
        import main

        original_demo_instance = main.demo_mode_instance
        original_cascor = main.cascor_integration

        try:
            main.demo_mode_instance = None
            main.cascor_integration = None

            result = await main.health_check()

            assert result["training_active"] is False
        finally:
            main.demo_mode_instance = original_demo_instance
            main.cascor_integration = original_cascor


# =============================================================================
# Test /api/state endpoint - direct async function calls
# =============================================================================
class TestStateEndpointDirect:
    """Test /api/state by calling async function directly."""

    @pytest.mark.asyncio
    async def test_state_without_demo_mode_uses_global_training_state(self):
        """When demo_mode_instance is None, should use global training_state."""
        import main

        original_demo_instance = main.demo_mode_instance

        try:
            main.demo_mode_instance = None

            result = await main.get_state()

            assert isinstance(result, dict)
        finally:
            main.demo_mode_instance = original_demo_instance

    @pytest.mark.asyncio
    async def test_state_with_demo_mode_uses_demo_training_state(self):
        """When demo_mode_instance is active, should use its training_state."""
        import main

        mock_training_state = MagicMock()
        mock_training_state.get_state.return_value = {"learning_rate": 0.05}

        mock_demo = MagicMock()
        mock_demo.training_state = mock_training_state

        original_demo_instance = main.demo_mode_instance

        try:
            main.demo_mode_instance = mock_demo

            result = await main.get_state()

            assert result["learning_rate"] == 0.05
            mock_training_state.get_state.assert_called_once()
        finally:
            main.demo_mode_instance = original_demo_instance
