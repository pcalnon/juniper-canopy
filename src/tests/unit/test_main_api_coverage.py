#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_main_api_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       2.0.0
# Date:          2025-12-13
# Last Modified: 2026-02-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for main.py API endpoints focusing on backend-mode branches
#                to improve coverage from 67% target.
#                Updated for BackendProtocol pattern (Phase 5).
#####################################################################
"""
Unit tests for main.py API endpoints with focus on:
- schedule_broadcast function edge cases
- Backend protocol mode branches (demo vs service)
- Protocol method return value handling (None → 503)
- Training control endpoints via protocol

These tests directly call the endpoint async functions to avoid lifespan
initialization issues with demo mode.  All tests save/restore `main.backend`
instead of the removed `main.demo_mode_instance` / `main.demo_mode_active`.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    async def test_topology_returns_topology(self):
        """Backend returning topology dict should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_network_topology.return_value = {
            "input_units": 3,
            "hidden_units": 2,
            "output_units": 1,
            "nodes": [],
            "connections": [],
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_topology()

            mock_backend.get_network_topology.assert_called_once()
            assert result == mock_backend.get_network_topology.return_value
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_topology_none_returns_503(self):
        """Backend returning None for topology should yield 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_network_topology.return_value = None

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_topology()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_topology_demo_mode_returns_topology(self):
        """Demo backend returning topology dict should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.get_network_topology.return_value = {
            "input_units": 2,
            "hidden_units": 0,
            "output_units": 1,
            "nodes": [],
            "connections": [],
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_topology()

            mock_backend.get_network_topology.assert_called_once()
            assert result["input_units"] == 2
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/dataset endpoint - direct async function calls
# =============================================================================
class TestDatasetEndpointDirect:
    """Test /api/dataset endpoint by calling async function directly."""

    @pytest.mark.asyncio
    async def test_dataset_returns_data(self):
        """Backend returning dataset dict should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_dataset.return_value = {
            "inputs": [[1.0, 2.0], [3.0, 4.0]],
            "targets": [0, 1],
            "num_samples": 2,
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_dataset()

            mock_backend.get_dataset.assert_called_once()
            assert result["num_samples"] == 2
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_dataset_none_returns_503(self):
        """Backend returning None for dataset should yield 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_dataset.return_value = None

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_dataset()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_dataset_demo_mode_returns_data(self):
        """Demo backend returning dataset should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.get_dataset.return_value = {
            "inputs": [[0.0, 1.0]],
            "targets": [1],
            "num_samples": 1,
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_dataset()

            assert result["num_samples"] == 1
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/decision_boundary endpoint - direct async function calls
# =============================================================================
class TestDecisionBoundaryEndpointDirect:
    """Test /api/decision_boundary endpoint by calling async function directly."""

    @pytest.mark.asyncio
    async def test_decision_boundary_returns_data(self):
        """Backend returning boundary data should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.get_decision_boundary.return_value = {
            "grid_x": [0.0, 1.0],
            "grid_y": [0.0, 1.0],
            "predictions": [[0.1, 0.9], [0.8, 0.2]],
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_decision_boundary()

            mock_backend.get_decision_boundary.assert_called_once_with(100)
            assert "predictions" in result
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_decision_boundary_none_returns_503(self):
        """Backend returning None for decision boundary should yield 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_decision_boundary.return_value = None

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_decision_boundary()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.backend = original_backend


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

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.start_training.return_value = {"current_epoch": 0, "is_running": True}

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_start(reset=False)

            mock_backend.start_training.assert_called_once_with(reset=False)
            assert result["status"] == "started"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_start_service_mode_returns_started(self):
        """Service mode start should return started status."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.start_training.return_value = {"is_training": True}

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_start(reset=False)

            mock_backend.start_training.assert_called_once_with(reset=False)
            assert result["status"] == "started"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_start_with_reset(self):
        """Start with reset=True should forward reset flag."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.start_training.return_value = {"current_epoch": 0, "is_running": True}

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_start(reset=True)

            mock_backend.start_training.assert_called_once_with(reset=True)
            assert result["status"] == "started"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/pause ----
    @pytest.mark.asyncio
    async def test_train_pause_returns_paused(self):
        """Pause should call backend.pause_training and return paused."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_pause()

            mock_backend.pause_training.assert_called_once()
            assert result["status"] == "paused"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_pause_service_mode_returns_paused(self):
        """Service mode pause should return paused status."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_pause()

            mock_backend.pause_training.assert_called_once()
            assert result["status"] == "paused"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/resume ----
    @pytest.mark.asyncio
    async def test_train_resume_returns_running(self):
        """Resume should call backend.resume_training and return running."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_resume()

            mock_backend.resume_training.assert_called_once()
            assert result["status"] == "running"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_resume_service_mode_returns_running(self):
        """Service mode resume should return running status."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_resume()

            mock_backend.resume_training.assert_called_once()
            assert result["status"] == "running"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/stop ----
    @pytest.mark.asyncio
    async def test_train_stop_returns_stopped(self):
        """Stop should call backend.stop_training and return stopped."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_stop()

            mock_backend.stop_training.assert_called_once()
            assert result["status"] == "stopped"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_stop_service_mode_returns_stopped(self):
        """Service mode stop should return stopped status."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_stop()

            mock_backend.stop_training.assert_called_once()
            assert result["status"] == "stopped"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    # ---- /api/train/reset ----
    @pytest.mark.asyncio
    async def test_train_reset_returns_reset_state(self):
        """Reset should call backend.reset_training and return reset status."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.reset_training.return_value = {"current_epoch": 0, "is_running": False}

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_reset()

            mock_backend.reset_training.assert_called_once()
            assert result["status"] == "reset"
            assert result["current_epoch"] == 0
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop

    @pytest.mark.asyncio
    async def test_train_reset_service_mode_returns_reset(self):
        """Service mode reset should return reset status."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.reset_training.return_value = {"is_training": False}

        original_backend = main.backend
        original_loop = main.loop_holder["loop"]

        try:
            main.backend = mock_backend
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            main.loop_holder["loop"] = mock_loop

            result = await main.api_train_reset()

            mock_backend.reset_training.assert_called_once()
            assert result["status"] == "reset"
        finally:
            main.backend = original_backend
            main.loop_holder["loop"] = original_loop


# =============================================================================
# Test /api/metrics/history endpoint - direct async function calls
# =============================================================================
class TestMetricsHistoryEndpointDirect:
    """Test /api/metrics/history by calling async function directly."""

    @pytest.mark.asyncio
    async def test_metrics_history_returns_history(self):
        """Backend returning history list should be wrapped in dict."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_metrics_history.return_value = [
            {"epoch": 1, "loss": 0.5},
            {"epoch": 2, "loss": 0.3},
        ]

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_metrics_history()

            mock_backend.get_metrics_history.assert_called_once_with(100)
            assert "history" in result
            assert len(result["history"]) == 2
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_metrics_history_empty_returns_empty_list(self):
        """Backend returning empty list should yield empty history."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_metrics_history.return_value = []

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_metrics_history()

            assert result == {"history": []}
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_metrics_history_demo_mode(self):
        """Demo backend should also return history via protocol."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.get_metrics_history.return_value = [{"epoch": 1, "loss": 0.4}]

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_metrics_history()

            assert len(result["history"]) == 1
        finally:
            main.backend = original_backend


# =============================================================================
# N1 event-loop guard: the poll routes exercised by the un-gated dashboard
# polls must run their synchronous backend calls via asyncio.to_thread so a
# slow cascor cannot stall canopy's event loop (training-runtime defects plan
# §8 row 2).
# =============================================================================
class TestPollRoutesUseToThread:
    """Pin the asyncio.to_thread wiring on /api/metrics/history, /api/topology,
    and /api/topology/raw (the routes the N1 un-gated polls hit)."""

    @pytest.mark.asyncio
    async def test_metrics_history_runs_backend_call_in_thread(self):
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        try:
            main.backend = mock_backend
            with patch("main.offload", new=AsyncMock(return_value=[{"epoch": 1}])) as mock_offload:
                result = await main.get_metrics_history(limit=50)

            mock_offload.assert_awaited_once()
            call = mock_offload.await_args
            assert call.args[0] == mock_backend.get_metrics_history
            assert call.args[1] == 50
            assert result == {"history": [{"epoch": 1}]}
            mock_backend.get_metrics_history.assert_not_called()  # only via to_thread
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_metrics_history_limit_zero_maps_to_10k_in_thread(self):
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        try:
            main.backend = mock_backend
            with patch("main.offload", new=AsyncMock(return_value=[])) as mock_offload:
                result = await main.get_metrics_history(limit=0)

            call = mock_offload.await_args
            assert call.args[0] == mock_backend.get_metrics_history
            assert call.args[1] == 10000
            assert result == {"history": []}
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_topology_runs_backend_call_in_thread(self):
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        try:
            main.backend = mock_backend
            with patch("main.offload", new=AsyncMock(return_value={"nodes": [], "connections": []})) as mock_offload:
                result = await main.get_topology()

            mock_offload.assert_awaited_once()
            assert mock_offload.await_args.args[0] == mock_backend.get_network_topology
            assert result == {"nodes": [], "connections": []}
            mock_backend.get_network_topology.assert_not_called()
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_raw_topology_runs_backend_call_in_thread(self):
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        original_backend = main.backend
        try:
            main.backend = mock_backend
            with patch("main.offload", new=AsyncMock(return_value={"weights": []})) as mock_offload:
                result = await main.get_raw_topology()

            mock_offload.assert_awaited_once()
            assert mock_offload.await_args.args[0] == mock_backend.get_raw_topology
            assert result == {"weights": []}
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/metrics endpoint - direct async function calls
# =============================================================================
class TestMetricsEndpointDirect:
    """Test /api/metrics by calling async function directly."""

    @pytest.mark.asyncio
    async def test_metrics_returns_dict(self):
        """Backend returning metrics dict should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_metrics.return_value = {"epoch": 5, "loss": 0.2}

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_metrics()

            mock_backend.get_metrics.assert_called_once()
            assert result["epoch"] == 5
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_metrics_empty_dict(self):
        """Backend returning empty dict should yield empty metrics."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_metrics.return_value = {}

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_metrics()

            assert result == {}
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_metrics_demo_mode(self):
        """Demo backend should return metrics via protocol."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.get_metrics.return_value = {"epoch": 10, "loss": 0.1, "accuracy": 0.95}

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_metrics()

            assert result["epoch"] == 10
            assert result["accuracy"] == 0.95
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/status endpoint - direct async function calls
# =============================================================================
class TestStatusEndpointDirect:
    """Test /api/status by calling async function directly."""

    @pytest.mark.asyncio
    async def test_status_returns_status(self):
        """Backend returning status dict should be returned directly."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_status.return_value = {
            "is_training": True,
            "network_connected": True,
            "current_epoch": 50,
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_status()

            mock_backend.get_status.assert_called_once()
            assert result["is_training"] is True
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_status_inactive(self):
        """Backend returning inactive status should be returned as-is."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_status.return_value = {
            "is_training": False,
            "network_connected": False,
        }

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_status()

            assert result["is_training"] is False
            assert result["network_connected"] is False
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/network/stats endpoint - direct async function calls
# =============================================================================
class TestNetworkStatsEndpointDirect:
    """Test /api/network/stats by calling async function directly."""

    @pytest.mark.asyncio
    async def test_network_stats_service_mode_returns_stats(self):
        """Service mode should call _adapter.get_network_data and return stats."""
        import numpy as np

        import main

        mock_adapter = MagicMock()
        mock_adapter.get_network_data.return_value = {
            "input_weights": np.array([[0.1, 0.2]]),
            "hidden_weights": None,
            "output_weights": np.array([[0.3]]),
            "hidden_biases": None,
            "output_biases": np.array([0.1]),
            "threshold_function": "tanh",
            "optimizer": "adam",
        }

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend._adapter = mock_adapter

        original_backend = main.backend
        try:
            main.backend = mock_backend

            await main.get_network_stats()

            mock_adapter.get_network_data.assert_called_once()
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_network_stats_demo_mode_returns_stats(self):
        """Demo mode should call _demo.get_network and return stats."""
        import numpy as np

        import main

        mock_network = MagicMock()
        mock_network.input_weights = np.array([[0.1, 0.2]])
        mock_network.hidden_units = []
        mock_network.output_weights = np.array([[0.3]])
        mock_network.output_bias = np.array([0.1])

        mock_demo = MagicMock()
        mock_demo.get_network.return_value = mock_network
        mock_demo.get_current_state.return_value = {
            "activation_fn": "tanh",
            "optimizer": "sgd",
        }

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend._demo = mock_demo

        original_backend = main.backend
        try:
            main.backend = mock_backend

            await main.get_network_stats()

            mock_demo.get_network.assert_called_once()
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_network_stats_unknown_backend_type_returns_503(self):
        """Backend with neither _demo nor _adapter should return 503."""
        from fastapi.responses import JSONResponse

        import main

        mock_backend = MagicMock(spec=[])
        mock_backend.backend_type = "unknown"

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_network_stats()

            assert isinstance(result, JSONResponse)
            assert result.status_code == 503
        finally:
            main.backend = original_backend


# =============================================================================
# Test /health endpoint - direct async function calls
# =============================================================================
class TestHealthEndpointDirect:
    """Test /health by calling async function directly."""

    @pytest.mark.asyncio
    async def test_health_service_mode_with_training_active(self):
        """Service mode with active training should report training_active=True."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.is_training_active.return_value = True

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.health_check()

            assert result["training_active"] is True
            assert result["demo_mode"] is False
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_health_service_mode_inactive(self):
        """Service mode with no training should report training_active=False."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.is_training_active.return_value = False

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.health_check()

            assert result["training_active"] is False
            assert result["demo_mode"] is False
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_health_demo_mode(self):
        """Demo backend should report demo_mode=True."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.is_training_active.return_value = True

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.health_check()

            assert result["training_active"] is True
            assert result["demo_mode"] is True
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/state endpoint - direct async function calls
# =============================================================================
class TestStateEndpointDirect:
    """Test /api/state by calling async function directly."""

    @pytest.mark.asyncio
    async def test_state_without_demo_mode_uses_global_training_state(self):
        """When backend_type is 'service', should use global training_state."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        # Ensure hasattr(backend, "_demo") is False for the service path
        del mock_backend._demo

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_state()

            assert isinstance(result, dict)
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_state_with_demo_mode_uses_demo_training_state(self):
        """When backend_type is 'demo', should use demo's training_state."""
        import main

        mock_training_state = MagicMock()
        mock_training_state.get_state.return_value = {"learning_rate": 0.05}

        mock_demo = MagicMock()
        mock_demo.training_state = mock_training_state

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend._demo = mock_demo

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.get_state()

            assert result["learning_rate"] == 0.05
            mock_training_state.get_state.assert_called_once()
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/train/status endpoint - direct async function calls
# =============================================================================
class TestTrainStatusEndpoint:
    """Test /api/train/status by calling async function directly."""

    @pytest.mark.asyncio
    async def test_train_status_includes_backend_type(self):
        """Train status should include backend type and status from protocol."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"
        mock_backend.get_status.return_value = {"is_training": True, "current_epoch": 42}

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.api_train_status()

            assert result["backend"] == "demo"
            assert result["is_training"] is True
            assert result["current_epoch"] == 42
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_train_status_service_mode(self):
        """Service mode train status should include 'service' backend type."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend.get_status.return_value = {"is_training": False}

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.api_train_status()

            assert result["backend"] == "service"
            assert result["is_training"] is False
        finally:
            main.backend = original_backend


# =============================================================================
# Test /api/set_params endpoint - direct async function calls
# =============================================================================
class TestSetParamsEndpoint:
    """Test /api/set_params by calling async function directly."""

    @pytest.mark.asyncio
    async def test_set_params_calls_backend_apply_params(self):
        """set_params should call backend.apply_params with the updates."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.api_set_params(main.SetParamsRequest(learning_rate=0.02))

            mock_backend.apply_params.assert_called_once_with(nn_learning_rate=0.02)
            assert result["status"] == "success"
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_set_params_no_params_returns_400(self):
        """Empty params dict should return 400 error."""
        from fastapi.responses import JSONResponse

        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "demo"

        original_backend = main.backend
        try:
            main.backend = mock_backend

            result = await main.api_set_params(main.SetParamsRequest())

            assert isinstance(result, JSONResponse)
            assert result.status_code == 400
        finally:
            main.backend = original_backend

    @pytest.mark.asyncio
    async def test_set_params_backend_rejection_returns_502_and_skips_state_updates(self):
        """Backend validation failure should return 502 without mutating state."""
        from fastapi.responses import JSONResponse

        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        mock_training_state = MagicMock()
        mock_training_state.get_state.return_value = {"status": "idle"}

        mock_ws_manager = MagicMock()
        mock_ws_manager.broadcast = AsyncMock()

        original_backend = main.backend
        original_training_state = main.training_state
        original_ws_manager = main.websocket_manager
        try:
            main.backend = mock_backend
            main.training_state = mock_training_state
            main.websocket_manager = mock_ws_manager

            with patch(
                "main.offload",
                new=AsyncMock(return_value={"ok": False, "error": "invalid threshold"}),
            ) as mock_offload:
                result = await main.api_set_params(main.SetParamsRequest(learning_rate=0.03, nn_patience=5))

            assert isinstance(result, JSONResponse)
            assert result.status_code == 502
            assert b"Backend rejected parameters: invalid threshold" in result.body
            mock_offload.assert_awaited_once()
            call = mock_offload.await_args
            assert call.args[0] == mock_backend.apply_params
            assert call.kwargs["nn_learning_rate"] == 0.03
            assert call.kwargs["nn_patience"] == 5
            mock_training_state.update_state.assert_not_called()
            mock_ws_manager.broadcast.assert_not_awaited()
        finally:
            main.backend = original_backend
            main.training_state = original_training_state
            main.websocket_manager = original_ws_manager

    @pytest.mark.asyncio
    async def test_set_params_success_broadcasts_params_updated_payload(self):
        """Successful updates should emit params_updated with applied_params."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        mock_training_state = MagicMock()
        mock_training_state.get_state.return_value = {"status": "running", "current_epoch": 12}

        mock_ws_manager = MagicMock()
        mock_ws_manager.broadcast = AsyncMock()

        original_backend = main.backend
        original_training_state = main.training_state
        original_ws_manager = main.websocket_manager
        try:
            main.backend = mock_backend
            main.training_state = mock_training_state
            main.websocket_manager = mock_ws_manager

            with patch("main.offload", new=AsyncMock(return_value={"ok": True})) as mock_offload:
                result = await main.api_set_params(
                    main.SetParamsRequest(
                        learning_rate=0.04,
                        patience=7,
                        cn_candidate_learning_rate=0.15,
                    )
                )

            assert result["status"] == "success"
            mock_offload.assert_awaited_once()
            call = mock_offload.await_args
            assert call.kwargs["nn_learning_rate"] == 0.04
            assert call.kwargs["nn_patience"] == 7
            assert call.kwargs["cn_candidate_learning_rate"] == 0.15

            mock_training_state.update_state.assert_called_once_with(
                learning_rate=0.04,
                patience=7,
                candidate_learning_rate=0.15,
            )
            mock_ws_manager.broadcast.assert_awaited_once()
            broadcast_msg = mock_ws_manager.broadcast.await_args.args[0]
            assert broadcast_msg["type"] == "params_updated"
            assert broadcast_msg["data"]["applied_params"]["nn_learning_rate"] == 0.04
            assert broadcast_msg["data"]["applied_params"]["nn_patience"] == 7
            assert broadcast_msg["data"]["applied_params"]["cn_candidate_learning_rate"] == 0.15
        finally:
            main.backend = original_backend
            main.training_state = original_training_state
            main.websocket_manager = original_ws_manager

    @pytest.mark.asyncio
    async def test_set_params_prefixed_keys_take_precedence_over_legacy_aliases(self):
        """When both legacy and prefixed keys are present, prefixed value wins."""
        import main

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"

        mock_training_state = MagicMock()
        mock_training_state.get_state.return_value = {"status": "idle"}

        mock_ws_manager = MagicMock()
        mock_ws_manager.broadcast = AsyncMock()

        original_backend = main.backend
        original_training_state = main.training_state
        original_ws_manager = main.websocket_manager
        try:
            main.backend = mock_backend
            main.training_state = mock_training_state
            main.websocket_manager = mock_ws_manager

            with patch("main.offload", new=AsyncMock(return_value={"ok": True})) as mock_offload:
                await main.api_set_params(main.SetParamsRequest(patience=5, nn_patience=9))

            call = mock_offload.await_args
            assert "patience" not in call.kwargs
            assert call.kwargs["nn_patience"] == 9
            mock_training_state.update_state.assert_called_once_with(patience=9)
        finally:
            main.backend = original_backend
            main.training_state = original_training_state
            main.websocket_manager = original_ws_manager
