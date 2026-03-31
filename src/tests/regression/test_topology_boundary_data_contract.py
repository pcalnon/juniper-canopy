#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
#
# Author:        Paul Calnon
# Version:       1.0.0
# File Name:     test_topology_boundary_data_contract.py
# File Path:     src/tests/regression/
#
# Created Date:  2026-03-16
# Last Modified: 2026-03-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     Regression tests for data contract mismatches between DemoBackend and
#     frontend components. Ensures the topology and decision boundary API
#     responses use the key names and data shapes expected by the frontend.
#
#     Network topology regression: DemoBackend returned "input_size"/"output_size"
#     but NetworkVisualizer expected "input_units"/"output_units", causing the
#     topology graph to show "No network topology available" even during training.
#
#     Decision boundary regression: DemoBackend returned "x"/"y"/"z" (1D linspace)
#     but DecisionBoundary expected "xx"/"yy"/"Z" (2D meshgrid), causing the
#     boundary plot to show "No boundary data available" even during training.
#
#####################################################################################################################################################################################################
"""Regression tests for topology and decision boundary data contract between DemoBackend and frontend."""

import numpy as np
import pytest

from demo_mode import DemoMode

_HAS_CASCOR_CLIENT = True
try:
    from juniper_cascor_client.testing import FakeCascorClient
except ImportError:
    _HAS_CASCOR_CLIENT = False


@pytest.mark.regression
@pytest.mark.unit
class TestTopologyDataContract:
    """Regression tests: topology API response must match frontend expectations."""

    def test_topology_contains_input_units_key(self):
        """Topology dict must use 'input_units' (not 'input_size').

        The NetworkVisualizer checks topology_data.get("input_units", 0)
        to decide whether to render the graph. If the key is missing,
        the visualizer shows 'No network topology available'.
        """
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        topology = backend.get_network_topology()

        assert topology is not None, "DemoBackend.get_network_topology() returned None"
        assert "input_units" in topology, f"Topology missing 'input_units' key. " f"Available keys: {list(topology.keys())}. " f"NetworkVisualizer expects 'input_units', not 'input_size'."
        assert topology["input_units"] > 0, "input_units must be > 0 for a valid network"

    def test_topology_contains_output_units_key(self):
        """Topology dict must use 'output_units' (not 'output_size')."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        topology = backend.get_network_topology()

        assert topology is not None
        assert "output_units" in topology, f"Topology missing 'output_units' key. " f"Available keys: {list(topology.keys())}. " f"NetworkVisualizer expects 'output_units', not 'output_size'."
        assert topology["output_units"] > 0

    def test_topology_does_not_use_size_keys(self):
        """Topology dict must NOT contain 'input_size' or 'output_size'.

        These were the incorrect key names that caused the regression.
        """
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        topology = backend.get_network_topology()

        assert topology is not None
        assert "input_size" not in topology, "Topology contains 'input_size' — must use 'input_units' instead"
        assert "output_size" not in topology, "Topology contains 'output_size' — must use 'output_units' instead"

    def test_topology_has_required_keys(self):
        """Topology dict must contain all keys expected by NetworkVisualizer."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        topology = backend.get_network_topology()

        assert topology is not None
        required_keys = {"nodes", "connections", "input_units", "output_units", "hidden_units"}
        missing = required_keys - set(topology.keys())
        assert not missing, f"Topology missing required keys: {missing}"

    def test_topology_api_endpoint_returns_correct_keys(self):
        """The /api/topology endpoint must return input_units/output_units."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            response = client.get("/api/topology")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "input_units" in data, f"API response missing 'input_units'. Keys: {list(data.keys())}"
            assert "output_units" in data, f"API response missing 'output_units'. Keys: {list(data.keys())}"


@pytest.mark.regression
@pytest.mark.unit
class TestDecisionBoundaryDataContract:
    """Regression tests: boundary API response must match frontend expectations."""

    def test_boundary_uses_xx_key(self):
        """Boundary dict must use 'xx' (not 'x') for meshgrid x-coordinates.

        DecisionBoundary._create_boundary_plot() accesses boundary_data.get("xx").
        The 'xx' data must be a 2D meshgrid array, not a 1D linspace.
        """
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        boundary = backend.get_decision_boundary(resolution=10)

        assert boundary is not None, "DemoBackend.get_decision_boundary() returned None"
        assert "xx" in boundary, f"Boundary missing 'xx' key. " f"Available keys: {list(boundary.keys())}. " f"DecisionBoundary expects 'xx', not 'x'."

    def test_boundary_uses_yy_key(self):
        """Boundary dict must use 'yy' (not 'y') for meshgrid y-coordinates."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        boundary = backend.get_decision_boundary(resolution=10)

        assert boundary is not None
        assert "yy" in boundary, f"Boundary missing 'yy' key. " f"Available keys: {list(boundary.keys())}. " f"DecisionBoundary expects 'yy', not 'y'."

    def test_boundary_uses_uppercase_Z_key(self):
        """Boundary dict must use 'Z' (not 'z') for predictions.

        DecisionBoundary._create_boundary_plot() accesses boundary_data.get("Z").
        """
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        boundary = backend.get_decision_boundary(resolution=10)

        assert boundary is not None
        assert "Z" in boundary, f"Boundary missing 'Z' key. " f"Available keys: {list(boundary.keys())}. " f"DecisionBoundary expects uppercase 'Z', not lowercase 'z'."

    def test_boundary_does_not_use_old_keys(self):
        """Boundary dict must NOT contain old key names that caused the regression."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        boundary = backend.get_decision_boundary(resolution=10)

        assert boundary is not None
        assert "x" not in boundary, "Boundary contains 'x' — must use 'xx' instead"
        assert "y" not in boundary, "Boundary contains 'y' — must use 'yy' instead"
        assert "z" not in boundary, "Boundary contains lowercase 'z' — must use uppercase 'Z'"

    def test_boundary_xx_yy_are_2d(self):
        """Boundary 'xx' and 'yy' must be 2D arrays (meshgrid), not 1D (linspace).

        The frontend accesses xx[0] (first row) and yy[:, 0] (first column),
        which requires 2D arrays. 1D arrays would cause IndexError or wrong plots.
        """
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        boundary = backend.get_decision_boundary(resolution=10)

        assert boundary is not None
        xx = np.array(boundary["xx"])
        yy = np.array(boundary["yy"])

        assert xx.ndim == 2, f"'xx' must be 2D (meshgrid), got {xx.ndim}D with shape {xx.shape}"
        assert yy.ndim == 2, f"'yy' must be 2D (meshgrid), got {yy.ndim}D with shape {yy.shape}"

    def test_boundary_Z_shape_matches_grid(self):
        """Boundary 'Z' shape must match the meshgrid dimensions."""
        from backend.demo_backend import DemoBackend

        demo = DemoMode(update_interval=1.0)
        backend = DemoBackend(demo)
        resolution = 10
        boundary = backend.get_decision_boundary(resolution=resolution)

        assert boundary is not None
        Z = np.array(boundary["Z"])
        assert Z.shape == (resolution, resolution), f"Z shape {Z.shape} doesn't match expected ({resolution}, {resolution})"

    def test_boundary_api_endpoint_returns_correct_keys(self):
        """The /api/decision_boundary endpoint must return xx/yy/Z keys."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            response = client.get("/api/decision_boundary")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            assert "xx" in data, f"API response missing 'xx'. Keys: {list(data.keys())}"
            assert "yy" in data, f"API response missing 'yy'. Keys: {list(data.keys())}"
            assert "Z" in data, f"API response missing 'Z'. Keys: {list(data.keys())}"

    def test_boundary_api_endpoint_accepts_resolution_param(self):
        """The /api/decision_boundary endpoint must accept a resolution query param."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            response = client.get("/api/decision_boundary?resolution=15")
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            Z = np.array(data["Z"])
            assert Z.shape == (15, 15), f"Z shape {Z.shape} doesn't match resolution 15"

    def test_boundary_api_endpoint_clamps_resolution(self):
        """The /api/decision_boundary endpoint must clamp resolution to 5-200."""
        from fastapi.testclient import TestClient

        from main import app

        with TestClient(app) as client:
            # Resolution below minimum should be clamped to 5
            response = client.get("/api/decision_boundary?resolution=1")
            assert response.status_code == 200
            data = response.json()
            Z = np.array(data["Z"])
            assert Z.shape[0] == 5


@pytest.mark.regression
@pytest.mark.skipif(not _HAS_CASCOR_CLIENT, reason="juniper-cascor-client not installed")
class TestServiceBackendBoundaryDataContract:
    """Regression tests: service backend boundary response must match frontend expectations.

    These tests verify that the CascorServiceAdapter correctly transforms
    the CasCor service response format into the frontend's expected format.
    """

    @pytest.fixture
    def service_backend(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        sb = ServiceBackend(adapter)
        yield sb
        fake.close()

    def test_service_boundary_uses_xx_key(self, service_backend):
        """Service mode boundary must use 'xx' key (not 'x_grid')."""
        boundary = service_backend.get_decision_boundary(resolution=10)
        assert boundary is not None
        assert "xx" in boundary, f"Service boundary missing 'xx'. Keys: {list(boundary.keys())}"
        assert "x_grid" not in boundary, "Service boundary contains 'x_grid' — must use 'xx'"

    def test_service_boundary_uses_yy_key(self, service_backend):
        """Service mode boundary must use 'yy' key (not 'y_grid')."""
        boundary = service_backend.get_decision_boundary(resolution=10)
        assert boundary is not None
        assert "yy" in boundary, f"Service boundary missing 'yy'. Keys: {list(boundary.keys())}"
        assert "y_grid" not in boundary, "Service boundary contains 'y_grid' — must use 'yy'"

    def test_service_boundary_uses_uppercase_Z_key(self, service_backend):
        """Service mode boundary must use 'Z' key (not 'predictions')."""
        boundary = service_backend.get_decision_boundary(resolution=10)
        assert boundary is not None
        assert "Z" in boundary, f"Service boundary missing 'Z'. Keys: {list(boundary.keys())}"
        assert "predictions" not in boundary, "Service boundary contains 'predictions' — must use 'Z'"

    def test_service_boundary_xx_yy_are_2d(self, service_backend):
        """Service mode xx/yy must be 2D meshgrids (not 1D arrays)."""
        boundary = service_backend.get_decision_boundary(resolution=10)
        assert boundary is not None
        xx = np.array(boundary["xx"])
        yy = np.array(boundary["yy"])
        assert xx.ndim == 2, f"Service 'xx' must be 2D, got {xx.ndim}D"
        assert yy.ndim == 2, f"Service 'yy' must be 2D, got {yy.ndim}D"

    def test_service_boundary_Z_shape_matches_grid(self, service_backend):
        """Service mode Z shape must match (resolution, resolution)."""
        boundary = service_backend.get_decision_boundary(resolution=10)
        assert boundary is not None
        Z = np.array(boundary["Z"])
        assert Z.shape == (10, 10), f"Service Z shape {Z.shape} doesn't match (10, 10)"
