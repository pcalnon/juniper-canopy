#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_demo_backend.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-02-26
# Last Modified: 2026-02-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for DemoBackend — BackendProtocol adapter wrapping DemoMode
#####################################################################
"""
Unit tests for DemoBackend — all BackendProtocol methods return expected types.

Task 5.7 of the Microservices Architecture Development Roadmap.
Also covers Task 5.6 (runtime_checkable protocol conformance).
"""
import pytest

from backend.demo_backend import DemoBackend
from backend.protocol import BackendProtocol
from demo_mode import get_demo_mode


@pytest.fixture
def demo_backend():
    """Create a DemoBackend wrapping a real DemoMode instance."""
    demo = get_demo_mode(update_interval=1.0)
    backend = DemoBackend(demo)
    yield backend
    # Ensure demo is stopped after test
    demo.stop()


class TestProtocolConformance:
    """Task 5.6: runtime_checkable protocol conformance."""

    def test_demo_backend_is_instance_of_backend_protocol(self, demo_backend):
        """DemoBackend should satisfy BackendProtocol via isinstance()."""
        assert isinstance(demo_backend, BackendProtocol)

    def test_backend_type_is_demo(self, demo_backend):
        """backend_type property should return 'demo'."""
        assert demo_backend.backend_type == "demo"


class TestTrainingControl:
    """Test training control methods."""

    def test_start_training_returns_dict(self, demo_backend):
        """start_training() should return a dict."""
        result = demo_backend.start_training(reset=True)
        assert isinstance(result, dict)

    def test_stop_training_returns_dict(self, demo_backend):
        """stop_training() should return a dict."""
        demo_backend.start_training(reset=True)
        result = demo_backend.stop_training()
        assert isinstance(result, dict)

    def test_pause_training_returns_dict(self, demo_backend):
        """pause_training() should return a dict."""
        demo_backend.start_training(reset=True)
        result = demo_backend.pause_training()
        assert isinstance(result, dict)

    def test_resume_training_returns_dict(self, demo_backend):
        """resume_training() should return a dict."""
        demo_backend.start_training(reset=True)
        demo_backend.pause_training()
        result = demo_backend.resume_training()
        assert isinstance(result, dict)

    def test_reset_training_returns_dict(self, demo_backend):
        """reset_training() should return a dict."""
        result = demo_backend.reset_training()
        assert isinstance(result, dict)

    def test_is_training_active_returns_bool(self, demo_backend):
        """is_training_active() should return a bool."""
        result = demo_backend.is_training_active()
        assert isinstance(result, bool)

    def test_is_training_active_after_start(self, demo_backend):
        """is_training_active() should be True after start."""
        demo_backend.start_training(reset=True)
        assert demo_backend.is_training_active() is True

    def test_is_training_active_after_stop(self, demo_backend):
        """is_training_active() should be False after stop."""
        demo_backend.start_training(reset=True)
        demo_backend.stop_training()
        assert demo_backend.is_training_active() is False


class TestStatusAndMetrics:
    """Test status and metrics methods."""

    def test_get_status_returns_dict(self, demo_backend):
        """get_status() should return a dict."""
        result = demo_backend.get_status()
        assert isinstance(result, dict)

    def test_get_status_has_required_fields(self, demo_backend):
        """get_status() should include FSM and network fields."""
        demo_backend.start_training(reset=True)
        status = demo_backend.get_status()
        assert "is_training" in status
        assert "is_running" in status
        assert "is_paused" in status
        assert "fsm_status" in status
        assert "phase" in status
        assert "network_connected" in status
        assert "input_size" in status
        assert "output_size" in status

    def test_get_status_reflects_training_state(self, demo_backend):
        """get_status() should reflect whether training is active."""
        demo_backend.start_training(reset=True)
        status = demo_backend.get_status()
        assert status["is_training"] is True
        assert status["is_running"] is True

        demo_backend.stop_training()
        status = demo_backend.get_status()
        assert status["is_training"] is False

    def test_get_metrics_returns_dict(self, demo_backend):
        """get_metrics() should return a dict."""
        result = demo_backend.get_metrics()
        assert isinstance(result, dict)

    def test_get_metrics_history_returns_list(self, demo_backend):
        """get_metrics_history() should return a list."""
        result = demo_backend.get_metrics_history(count=10)
        assert isinstance(result, list)

    def test_get_metrics_history_respects_count(self, demo_backend):
        """get_metrics_history() should respect the count parameter."""
        result = demo_backend.get_metrics_history(count=5)
        assert len(result) <= 5


class TestNetworkAndData:
    """Test network and data methods."""

    def test_has_network_returns_bool(self, demo_backend):
        """has_network() should return a bool."""
        result = demo_backend.has_network()
        assert isinstance(result, bool)

    def test_has_network_is_true_for_demo(self, demo_backend):
        """DemoMode creates a MockCascorNetwork, so has_network() should be True."""
        assert demo_backend.has_network() is True

    def test_get_network_topology_returns_dict(self, demo_backend):
        """get_network_topology() should return a dict for demo mode."""
        result = demo_backend.get_network_topology()
        assert isinstance(result, dict)

    def test_get_network_topology_has_required_keys(self, demo_backend):
        """Topology should have nodes, connections, input_size, output_size."""
        topo = demo_backend.get_network_topology()
        assert "nodes" in topo
        assert "connections" in topo
        assert "input_size" in topo
        assert "output_size" in topo
        assert "hidden_units" in topo
        assert isinstance(topo["nodes"], list)
        assert isinstance(topo["connections"], list)

    def test_get_network_topology_nodes_have_required_fields(self, demo_backend):
        """Each node should have id, type, layer."""
        topo = demo_backend.get_network_topology()
        for node in topo["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "layer" in node

    def test_get_network_topology_connections_have_required_fields(self, demo_backend):
        """Each connection should have from, to, weight."""
        topo = demo_backend.get_network_topology()
        for conn in topo["connections"]:
            assert "from" in conn
            assert "to" in conn
            assert "weight" in conn

    def test_get_network_stats_returns_dict(self, demo_backend):
        """get_network_stats() should return a dict."""
        result = demo_backend.get_network_stats()
        assert isinstance(result, dict)

    def test_get_network_stats_has_expected_keys(self, demo_backend):
        """Network stats should include hidden_units, input_size, output_size."""
        stats = demo_backend.get_network_stats()
        assert "hidden_units" in stats
        assert "input_size" in stats
        assert "output_size" in stats

    def test_get_dataset_returns_dict(self, demo_backend):
        """get_dataset() should return a dict for demo mode."""
        result = demo_backend.get_dataset()
        assert isinstance(result, dict)

    def test_get_dataset_has_required_keys(self, demo_backend):
        """Dataset should have num_samples, inputs, targets."""
        dataset = demo_backend.get_dataset()
        assert "num_samples" in dataset
        assert "inputs" in dataset
        assert "targets" in dataset
        assert isinstance(dataset["inputs"], list)
        assert isinstance(dataset["targets"], list)

    def test_get_decision_boundary_returns_dict(self, demo_backend):
        """get_decision_boundary() should return a dict for demo mode."""
        result = demo_backend.get_decision_boundary(resolution=10)
        assert isinstance(result, dict)

    def test_get_decision_boundary_has_required_keys(self, demo_backend):
        """Decision boundary should have x, y, z, resolution, bounds."""
        boundary = demo_backend.get_decision_boundary(resolution=10)
        assert "x" in boundary
        assert "y" in boundary
        assert "z" in boundary
        assert "resolution" in boundary
        assert "x_min" in boundary
        assert "x_max" in boundary
        assert "y_min" in boundary
        assert "y_max" in boundary

    def test_get_decision_boundary_resolution_matches(self, demo_backend):
        """Decision boundary resolution should match the requested value."""
        boundary = demo_backend.get_decision_boundary(resolution=15)
        assert boundary["resolution"] == 15
        assert len(boundary["x"]) == 15
        assert len(boundary["y"]) == 15


class TestParameters:
    """Test parameter methods."""

    def test_apply_params_returns_dict(self, demo_backend):
        """apply_params() should return a dict."""
        result = demo_backend.apply_params(learning_rate=0.05)
        assert isinstance(result, dict)


class TestLifecycle:
    """Test async lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_returns_true(self, demo_backend):
        """initialize() should return True for demo mode."""
        result = await demo_backend.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_completes(self, demo_backend):
        """shutdown() should complete without error."""
        await demo_backend.initialize()
        await demo_backend.shutdown()
        assert demo_backend.is_training_active() is False
