"""Integration test: ServiceBackend decision boundary with FakeCascorClient.

Exercises the full decision boundary pipeline in service mode:
ServiceBackend → CascorServiceAdapter → FakeCascorClient (in-memory).

Verifies that the transformed response matches the data contract expected
by the DecisionBoundary frontend component.
"""

import numpy as np
import pytest

pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")

from juniper_cascor_client.testing import FakeCascorClient

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend


@pytest.fixture
def fake_client():
    """FakeCascorClient with a loaded network (two_spiral_training scenario)."""
    client = FakeCascorClient(scenario="two_spiral_training")
    yield client
    client.close()


@pytest.fixture
def adapter(fake_client):
    """CascorServiceAdapter with injected FakeCascorClient."""
    return CascorServiceAdapter(client=fake_client)


@pytest.fixture
def backend(adapter):
    """ServiceBackend wrapping the adapter."""
    return ServiceBackend(adapter)


class TestDecisionBoundaryServiceMode:
    """Integration tests for decision boundary in service mode."""

    @pytest.mark.integration
    def test_returns_data_not_none(self, backend):
        """Service mode should return decision boundary data (not None)."""
        result = backend.get_decision_boundary(resolution=10)
        assert result is not None

    @pytest.mark.integration
    def test_response_has_required_keys(self, backend):
        """Response must contain all keys expected by the frontend."""
        result = backend.get_decision_boundary(resolution=10)

        for key in ("xx", "yy", "Z", "x_min", "x_max", "y_min", "y_max", "resolution"):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.integration
    def test_xx_is_2d_meshgrid(self, backend):
        """xx must be a 2D array (meshgrid format)."""
        result = backend.get_decision_boundary(resolution=10)
        xx = np.array(result["xx"])
        assert xx.ndim == 2
        assert xx.shape == (10, 10)

    @pytest.mark.integration
    def test_yy_is_2d_meshgrid(self, backend):
        """yy must be a 2D array (meshgrid format)."""
        result = backend.get_decision_boundary(resolution=10)
        yy = np.array(result["yy"])
        assert yy.ndim == 2
        assert yy.shape == (10, 10)

    @pytest.mark.integration
    def test_Z_shape_matches_grid(self, backend):
        """Z shape must match (resolution, resolution)."""
        result = backend.get_decision_boundary(resolution=10)
        Z = np.array(result["Z"])
        assert Z.ndim == 2
        assert Z.shape == (10, 10)

    @pytest.mark.integration
    def test_predictions_are_numeric(self, backend):
        """All Z values must be numeric (not NaN)."""
        result = backend.get_decision_boundary(resolution=10)
        Z = np.array(result["Z"])
        assert not np.any(np.isnan(Z))

    @pytest.mark.integration
    def test_frontend_contour_access_pattern(self, backend):
        """Transformed data must work with frontend's contour access pattern.

        Frontend accesses: x=xx[0], y=yy[:, 0], z=Z
        """
        result = backend.get_decision_boundary(resolution=10)
        xx = np.array(result["xx"])
        yy = np.array(result["yy"])
        Z = np.array(result["Z"])

        # These access patterns must not raise
        x_axis = xx[0]
        y_axis = yy[:, 0]

        assert len(x_axis) == 10
        assert len(y_axis) == 10
        assert Z.shape == (len(y_axis), len(x_axis))

    @pytest.mark.integration
    def test_different_resolutions(self, backend):
        """Boundary data should work at various resolutions."""
        for res in [5, 25, 50]:
            result = backend.get_decision_boundary(resolution=res)
            assert result is not None
            xx = np.array(result["xx"])
            assert xx.shape == (res, res)


class TestDecisionBoundaryServiceModeNoNetwork:
    """Test decision boundary when no network is loaded."""

    @pytest.mark.integration
    def test_returns_none_when_no_network(self):
        """Idle scenario (no network) should return None."""
        fake = FakeCascorClient(scenario="idle")
        adapter = CascorServiceAdapter(client=fake)
        sb = ServiceBackend(adapter)
        result = sb.get_decision_boundary(resolution=10)
        assert result is None
        fake.close()


class TestDecisionBoundaryConvergedNetwork:
    """Test decision boundary with a converged network."""

    @pytest.mark.integration
    def test_converged_network_returns_data(self):
        """Converged network should return valid boundary data."""
        fake = FakeCascorClient(scenario="xor_converged")
        adapter = CascorServiceAdapter(client=fake)
        sb = ServiceBackend(adapter)
        result = sb.get_decision_boundary(resolution=10)
        assert result is not None
        assert "xx" in result
        assert "Z" in result
        fake.close()
