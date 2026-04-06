#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_service_backend.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-02-26
# Last Modified: 2026-02-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for ServiceBackend — BackendProtocol adapter wrapping CascorServiceAdapter
#####################################################################
"""
Unit tests for ServiceBackend — all BackendProtocol methods return expected types.

Uses a mocked CascorServiceAdapter to avoid network dependencies.
Task 5.8 of the Microservices Architecture Development Roadmap.
Also covers Task 5.6 (runtime_checkable protocol conformance).
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from backend.protocol import BackendProtocol

try:
    from backend.service_backend import ServiceBackend

    _HAS_SERVICE_BACKEND = True
except ImportError:
    _HAS_SERVICE_BACKEND = False

pytestmark = pytest.mark.skipif(not _HAS_SERVICE_BACKEND, reason="juniper-cascor-client not installed")


@pytest.fixture
def mock_adapter():
    """Create a mock CascorServiceAdapter with realistic return values."""
    adapter = MagicMock()

    # Network property
    type(adapter).network = PropertyMock(return_value=MagicMock(__bool__=lambda s: True))

    # Training control
    adapter.is_training_in_progress.return_value = False
    adapter.start_training_background.return_value = True
    adapter.request_training_stop.return_value = True

    # Status and metrics
    adapter.get_training_status.return_value = {
        "is_training": False,
        "current_epoch": 0,
        "phase": "idle",
    }
    adapter.training_monitor.get_current_metrics.return_value = {
        "current_epoch": 0,
        "current_loss": 0.5,
        "current_accuracy": 0.75,
    }
    adapter.training_monitor.get_recent_metrics.return_value = [
        {"epoch": 1, "metrics": {"loss": 0.5}},
    ]

    # Network and data
    adapter.extract_network_topology.return_value = {
        "nodes": [{"id": "input_0", "type": "input", "layer": 0}],
        "connections": [],
    }
    adapter.get_network_data.return_value = {"hidden_units": 0, "total_weights": 4}
    adapter.get_dataset_info.return_value = {
        "inputs": [[0.0, 0.0]],
        "targets": [[0]],
        "num_samples": 1,
    }

    # Async lifecycle
    adapter.connect = AsyncMock(return_value=True)
    adapter.start_metrics_relay = AsyncMock()
    adapter.stop_metrics_relay = AsyncMock()
    adapter.shutdown = MagicMock()

    adapter._service_url = "http://localhost:8200"

    return adapter


@pytest.fixture
def service_backend(mock_adapter):
    """Create a ServiceBackend wrapping a mock adapter."""
    return ServiceBackend(mock_adapter)


class TestProtocolConformance:
    """Task 5.6: runtime_checkable protocol conformance."""

    def test_service_backend_is_instance_of_backend_protocol(self, service_backend):
        """ServiceBackend should satisfy BackendProtocol via isinstance()."""
        assert isinstance(service_backend, BackendProtocol)

    def test_backend_type_is_service(self, service_backend):
        """backend_type property should return 'service'."""
        assert service_backend.backend_type == "service"


class TestTrainingControl:
    """Test training control methods."""

    def test_start_training_returns_dict(self, service_backend):
        """start_training() should return a dict."""
        result = service_backend.start_training(reset=True)
        assert isinstance(result, dict)

    def test_start_training_success(self, service_backend, mock_adapter):
        """start_training() should delegate to adapter and return ok=True."""
        result = service_backend.start_training(reset=True)
        assert result["ok"] is True
        assert result["is_training"] is True
        mock_adapter.start_training_background.assert_called_once()

    def test_start_training_no_network(self, service_backend, mock_adapter):
        """start_training() should fail when no network exists."""
        type(mock_adapter).network = PropertyMock(return_value=None)
        result = service_backend.start_training()
        assert result["ok"] is False
        assert "No network" in result["error"]

    def test_start_training_already_in_progress(self, service_backend, mock_adapter):
        """start_training() should fail when training already running."""
        mock_adapter.is_training_in_progress.return_value = True
        result = service_backend.start_training()
        assert result["ok"] is False
        assert "already in progress" in result["error"]

    def test_stop_training_returns_dict(self, service_backend):
        """stop_training() should return a dict."""
        result = service_backend.stop_training()
        assert isinstance(result, dict)

    def test_stop_training_delegates_to_adapter(self, service_backend, mock_adapter):
        """stop_training() should call adapter.request_training_stop()."""
        result = service_backend.stop_training()
        assert result["ok"] is True
        mock_adapter.request_training_stop.assert_called_once()

    def test_pause_training_delegates_to_adapter(self, service_backend, mock_adapter):
        """pause_training() should delegate to adapter."""
        mock_adapter.pause_training.return_value = {"ok": True, "data": {}}
        result = service_backend.pause_training()
        assert result["ok"] is True
        mock_adapter.pause_training.assert_called_once()

    def test_resume_training_delegates_to_adapter(self, service_backend, mock_adapter):
        """resume_training() should delegate to adapter."""
        mock_adapter.resume_training.return_value = {"ok": True, "data": {}}
        result = service_backend.resume_training()
        assert result["ok"] is True
        mock_adapter.resume_training.assert_called_once()

    def test_reset_training_delegates_to_adapter(self, service_backend, mock_adapter):
        """reset_training() should delegate to adapter."""
        mock_adapter.reset_training.return_value = {"ok": True, "data": {}}
        result = service_backend.reset_training()
        assert result["ok"] is True
        mock_adapter.reset_training.assert_called_once()

    def test_is_training_active_returns_bool(self, service_backend):
        """is_training_active() should return a bool."""
        result = service_backend.is_training_active()
        assert isinstance(result, bool)

    def test_is_training_active_delegates_to_adapter(self, service_backend, mock_adapter):
        """is_training_active() should delegate to adapter."""
        mock_adapter.is_training_in_progress.return_value = True
        assert service_backend.is_training_active() is True
        mock_adapter.is_training_in_progress.return_value = False
        assert service_backend.is_training_active() is False


class TestStatusAndMetrics:
    """Test status and metrics methods."""

    def test_get_status_returns_dict(self, service_backend):
        """get_status() should return a dict."""
        result = service_backend.get_status()
        assert isinstance(result, dict)

    def test_get_status_delegates_to_adapter(self, service_backend, mock_adapter):
        """get_status() should delegate to adapter.get_training_status()."""
        service_backend.get_status()
        mock_adapter.get_training_status.assert_called_once()

    def test_get_metrics_returns_dict(self, service_backend):
        """get_metrics() should return a dict."""
        result = service_backend.get_metrics()
        assert isinstance(result, dict)

    def test_get_metrics_delegates_to_training_monitor(self, service_backend, mock_adapter):
        """get_metrics() should delegate to adapter.training_monitor."""
        service_backend.get_metrics()
        mock_adapter.training_monitor.get_current_metrics.assert_called_once()

    def test_get_metrics_history_returns_list(self, service_backend):
        """get_metrics_history() should return a list."""
        result = service_backend.get_metrics_history(count=10)
        assert isinstance(result, list)

    def test_get_metrics_history_passes_count(self, service_backend, mock_adapter):
        """get_metrics_history() should pass count to adapter."""
        service_backend.get_metrics_history(count=42)
        mock_adapter.training_monitor.get_recent_metrics.assert_called_once_with(42)


class TestNetworkAndData:
    """Test network and data methods."""

    def test_has_network_returns_bool(self, service_backend):
        """has_network() should return a bool."""
        result = service_backend.has_network()
        assert isinstance(result, bool)

    def test_has_network_with_network(self, service_backend):
        """has_network() should be True when adapter has a network."""
        assert service_backend.has_network() is True

    def test_has_network_without_network(self, service_backend, mock_adapter):
        """has_network() should be False when no network."""
        type(mock_adapter).network = PropertyMock(return_value=None)
        assert service_backend.has_network() is False

    def test_get_network_topology_returns_dict_or_none(self, service_backend):
        """get_network_topology() should return a dict or None."""
        result = service_backend.get_network_topology()
        assert isinstance(result, (dict, type(None)))

    def test_get_network_topology_delegates_to_adapter(self, service_backend, mock_adapter):
        """get_network_topology() should delegate to adapter."""
        service_backend.get_network_topology()
        mock_adapter.extract_network_topology.assert_called_once()

    def test_get_network_stats_returns_dict(self, service_backend):
        """get_network_stats() should return a dict."""
        result = service_backend.get_network_stats()
        assert isinstance(result, dict)

    def test_get_dataset_returns_dict_or_none(self, service_backend):
        """get_dataset() should return a dict or None."""
        result = service_backend.get_dataset()
        assert isinstance(result, (dict, type(None)))

    def test_get_dataset_passes_through_inputs_targets(self, service_backend, mock_adapter):
        """get_dataset() includes inputs/targets when present in raw response."""
        mock_adapter.get_dataset_info.return_value = {
            "loaded": True,
            "train_samples": 100,
            "test_samples": 25,
            "input_features": 2,
            "output_features": 1,
            "inputs": [[0.1, 0.2], [0.3, 0.4]],
            "targets": [0, 1],
        }
        result = service_backend.get_dataset()
        assert "inputs" in result
        assert "targets" in result
        assert result["inputs"] == [[0.1, 0.2], [0.3, 0.4]]
        assert result["targets"] == [0, 1]
        assert result["num_samples"] == 125
        mock_adapter.get_dataset_data.assert_not_called()

    def test_get_dataset_passthrough_for_non_metadata_shape(self, service_backend, mock_adapter):
        """Raw dataset payload without metadata keys is returned unchanged."""
        raw = {
            "inputs": [[0.1, 0.2], [0.3, 0.4]],
            "targets": [0, 1],
            "split_indices": {"train": [0], "test": [1]},
        }
        mock_adapter.get_dataset_info.return_value = raw

        result = service_backend.get_dataset()

        assert result == raw
        mock_adapter.get_dataset_data.assert_not_called()

    def test_get_dataset_metadata_only_no_inputs_key(self, service_backend, mock_adapter):
        """get_dataset() omits inputs/targets when not in raw response and data endpoint unavailable."""
        mock_adapter.get_dataset_info.return_value = {
            "loaded": True,
            "train_samples": 800,
            "test_samples": 200,
            "input_features": 2,
            "output_features": 1,
        }
        mock_adapter.get_dataset_data.return_value = None
        result = service_backend.get_dataset()
        assert "inputs" not in result
        assert "targets" not in result
        assert result["num_samples"] == 1000

    def test_get_dataset_returns_none_when_info_missing(self, service_backend, mock_adapter):
        """get_dataset() returns None when adapter has no dataset info."""
        mock_adapter.get_dataset_info.return_value = None

        result = service_backend.get_dataset()

        assert result is None
        mock_adapter.get_dataset_data.assert_not_called()

    def test_get_dataset_fetches_inputs_targets_from_dataset_data(self, service_backend, mock_adapter):
        """get_dataset() fetches arrays from get_dataset_data() when metadata-only response is returned."""
        mock_adapter.get_dataset_info.return_value = {
            "loaded": True,
            "train_samples": 80,
            "test_samples": 20,
            "input_features": 2,
            "output_features": 2,
        }
        mock_adapter.get_dataset_data.return_value = {
            "inputs": [[0.1, 0.2], [0.3, 0.4]],
            "targets": [1, 0],
        }

        result = service_backend.get_dataset()

        assert result["num_samples"] == 100
        assert result["num_features"] == 2
        assert result["num_classes"] == 2
        assert result["inputs"] == [[0.1, 0.2], [0.3, 0.4]]
        assert result["targets"] == [1, 0]
        mock_adapter.get_dataset_data.assert_called_once()

    def test_get_decision_boundary_delegates_to_adapter(self, service_backend, mock_adapter):
        """get_decision_boundary() should delegate to adapter."""
        mock_adapter.get_decision_boundary.return_value = {
            "xx": [[1, 2], [1, 2]],
            "yy": [[1, 1], [2, 2]],
            "Z": [[0.1, 0.9], [0.8, 0.2]],
            "x_min": -1.5,
            "x_max": 1.5,
            "y_min": -1.5,
            "y_max": 1.5,
            "resolution": 2,
        }
        result = service_backend.get_decision_boundary(resolution=50)
        assert result is not None
        assert "xx" in result
        mock_adapter.get_decision_boundary.assert_called_once_with(50)


class TestParameters:
    """Test parameter methods."""

    def test_apply_params_delegates_to_adapter(self, service_backend, mock_adapter):
        """apply_params() should delegate to adapter."""
        mock_adapter.apply_params.return_value = {"ok": True, "data": {"learning_rate": 0.05}}
        result = service_backend.apply_params(learning_rate=0.05)
        assert result["ok"] is True
        mock_adapter.apply_params.assert_called_once_with(learning_rate=0.05)


class TestLifecycle:
    """Test async lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_connects_and_starts_relay(self, service_backend, mock_adapter):
        """initialize() should connect and start metrics relay."""
        result = await service_backend.initialize()
        assert result is True
        mock_adapter.connect.assert_awaited_once()
        mock_adapter.start_metrics_relay.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_returns_false_on_connection_failure(self, service_backend, mock_adapter):
        """initialize() should return False if connect fails."""
        mock_adapter.connect = AsyncMock(return_value=False)
        result = await service_backend.initialize()
        assert result is False
        mock_adapter.start_metrics_relay.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_shutdown_stops_relay_and_adapter(self, service_backend, mock_adapter):
        """shutdown() should stop relay and shutdown adapter."""
        await service_backend.shutdown()
        mock_adapter.stop_metrics_relay.assert_awaited_once()
        mock_adapter.shutdown.assert_called_once()
