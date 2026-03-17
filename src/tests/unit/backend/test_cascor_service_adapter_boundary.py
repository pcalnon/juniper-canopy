"""
Tests for CascorServiceAdapter.get_decision_boundary() — data transformation.

Verifies that the adapter correctly transforms the CasCor service response
(2D meshgrid arrays ``grid_x``/``grid_y`` and 2D integer prediction grid)
into the frontend format (``xx``/``yy``/``Z``).
"""

from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")

from juniper_cascor_client.exceptions import JuniperCascorClientError, JuniperCascorConnectionError, JuniperCascorNotFoundError

from backend.cascor_service_adapter import CascorServiceAdapter, _ServiceTrainingMonitor


@pytest.fixture
def mock_client():
    """Create a mock JuniperCascorClient."""
    client = MagicMock()
    client.is_ready.return_value = True
    return client


@pytest.fixture
def adapter(mock_client):
    """Create a CascorServiceAdapter with a mocked client."""
    a = CascorServiceAdapter(service_url="http://localhost:8200")
    a._client = mock_client
    a.training_monitor = _ServiceTrainingMonitor(mock_client)
    return a


def _make_cascor_boundary_response(resolution=10):
    """Create a response matching the real CasCor API format.

    The real ``/v1/decision-boundary`` endpoint returns:
    - ``grid_x``, ``grid_y``: 2D meshgrid arrays (resolution x resolution)
    - ``predictions``: 2D array of integer class indices (resolution x resolution)
    """
    xx_1d = np.linspace(-1.5, 1.5, resolution)
    yy_1d = np.linspace(-1.5, 1.5, resolution)
    grid_x, grid_y = np.meshgrid(xx_1d, yy_1d)
    # Integer class predictions (0 or 1) — matches argmax output
    predictions = np.random.randint(0, 2, size=(resolution, resolution))
    return {
        "status": "success",
        "data": {
            "grid_x": grid_x.tolist(),
            "grid_y": grid_y.tolist(),
            "predictions": predictions.tolist(),
            "resolution": resolution,
            "x_range": [-1.5, 1.5],
            "y_range": [-1.5, 1.5],
        },
    }


class TestGetDecisionBoundary:
    """Test CascorServiceAdapter.get_decision_boundary() transformation."""

    def test_transforms_response_to_frontend_format(self, adapter, mock_client):
        """Verify real CasCor API format is transformed to frontend format."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        assert result is not None
        assert "xx" in result
        assert "yy" in result
        assert "Z" in result
        assert "x_min" in result
        assert "x_max" in result
        assert "y_min" in result
        assert "y_max" in result
        assert "resolution" in result

    def test_xx_is_2d_meshgrid(self, adapter, mock_client):
        """Verify xx is a 2D meshgrid array."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        xx = np.array(result["xx"])
        assert xx.ndim == 2
        assert xx.shape == (10, 10)

    def test_yy_is_2d_meshgrid(self, adapter, mock_client):
        """Verify yy is a 2D meshgrid array."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        yy = np.array(result["yy"])
        assert yy.ndim == 2
        assert yy.shape == (10, 10)

    def test_Z_shape_matches_resolution(self, adapter, mock_client):
        """Verify Z is a 2D array with shape (resolution, resolution)."""
        res = 15
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(res)
        result = adapter.get_decision_boundary(resolution=res)

        Z = np.array(result["Z"])
        assert Z.ndim == 2
        assert Z.shape == (res, res)

    def test_Z_contains_integer_class_indices(self, adapter, mock_client):
        """Verify Z contains integer class indices, not continuous values."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        Z = np.array(result["Z"])
        unique_vals = np.unique(Z)
        for val in unique_vals:
            assert val == int(val), f"Expected integer class index, got {val}"

    def test_meshgrid_rows_are_constant_x(self, adapter, mock_client):
        """Each row of xx should be identical (meshgrid property)."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        xx = np.array(result["xx"])
        for row in xx:
            np.testing.assert_array_equal(row, xx[0])

    def test_meshgrid_columns_are_constant_y(self, adapter, mock_client):
        """Each column of yy should be identical (meshgrid property)."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        yy = np.array(result["yy"])
        for col_idx in range(yy.shape[1]):
            np.testing.assert_array_equal(yy[:, col_idx], yy[:, 0])

    def test_bounds_extracted_from_x_range_y_range(self, adapter, mock_client):
        """Verify bounds are correctly extracted from x_range/y_range."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        assert result["x_min"] == -1.5
        assert result["x_max"] == 1.5
        assert result["y_min"] == -1.5
        assert result["y_max"] == 1.5

    def test_passes_resolution_to_client(self, adapter, mock_client):
        """Verify resolution parameter is forwarded to the client."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(75)
        adapter.get_decision_boundary(resolution=75)

        mock_client.get_decision_boundary.assert_called_once_with(75)

    def test_returns_none_on_client_error(self, adapter, mock_client):
        """Verify graceful handling of client connection errors."""
        mock_client.get_decision_boundary.side_effect = JuniperCascorConnectionError("no conn")
        result = adapter.get_decision_boundary(resolution=50)

        assert result is None

    def test_returns_none_on_not_found(self, adapter, mock_client):
        """Verify graceful handling when no network is loaded."""
        mock_client.get_decision_boundary.side_effect = JuniperCascorNotFoundError("No network")
        result = adapter.get_decision_boundary(resolution=50)

        assert result is None

    def test_returns_none_on_empty_data(self, adapter, mock_client):
        """Verify None returned when response data is empty."""
        mock_client.get_decision_boundary.return_value = {"status": "success", "data": {}}
        result = adapter.get_decision_boundary(resolution=50)

        assert result is None

    def test_returns_none_on_missing_data_key(self, adapter, mock_client):
        """Verify None returned when response has no data key."""
        mock_client.get_decision_boundary.return_value = {"status": "error"}
        result = adapter.get_decision_boundary(resolution=50)

        assert result is None

    def test_returns_none_on_malformed_data(self, adapter, mock_client):
        """Verify None returned when data is missing required fields."""
        mock_client.get_decision_boundary.return_value = {
            "status": "success",
            "data": {"grid_x": [[1, 2], [1, 2]]},  # missing grid_y, predictions
        }
        result = adapter.get_decision_boundary(resolution=50)

        assert result is None

    def test_resolution_in_response_matches_data(self, adapter, mock_client):
        """Verify resolution in response matches the data's resolution field."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(20)
        result = adapter.get_decision_boundary(resolution=20)

        assert result["resolution"] == 20

    def test_different_resolutions(self, adapter, mock_client):
        """Verify correct transformation at various resolutions."""
        for res in [5, 25, 50, 100]:
            mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(res)
            result = adapter.get_decision_boundary(resolution=res)

            assert result is not None
            xx = np.array(result["xx"])
            yy = np.array(result["yy"])
            Z = np.array(result["Z"])
            assert xx.shape == (res, res)
            assert yy.shape == (res, res)
            assert Z.shape == (res, res)

    def test_frontend_compatible_contour_access(self, adapter, mock_client):
        """Verify the transformed data works with the frontend's access pattern.

        The DecisionBoundary component accesses data as:
            x = xx[0]       (first row = x-axis values)
            y = yy[:, 0]    (first column = y-axis values)
        """
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(10)
        result = adapter.get_decision_boundary(resolution=10)

        xx = np.array(result["xx"])
        yy = np.array(result["yy"])

        # xx[0] should give the x-axis values
        x_axis = xx[0]
        assert len(x_axis) == 10
        assert x_axis[0] < x_axis[-1]  # increasing

        # yy[:, 0] should give the y-axis values
        y_axis = yy[:, 0]
        assert len(y_axis) == 10
        assert y_axis[0] < y_axis[-1]  # increasing


class TestRegressionKeyNames:
    """Regression tests to prevent key name mismatch from recurring.

    The real CasCor API uses grid_x/grid_y (not x_grid/y_grid).
    These tests ensure the adapter reads the correct keys.
    """

    def test_adapter_does_not_read_x_grid_key(self, adapter, mock_client):
        """Verify the adapter does NOT look for the old 'x_grid' key."""
        mock_client.get_decision_boundary.return_value = {
            "status": "success",
            "data": {
                "x_grid": np.linspace(-1, 1, 5).tolist(),  # old key — should be ignored
                "y_grid": np.linspace(-1, 1, 5).tolist(),  # old key — should be ignored
                "predictions": np.zeros(25).tolist(),
                "resolution": 5,
            },
        }
        # Should return None because grid_x/grid_y are missing
        result = adapter.get_decision_boundary(resolution=5)
        assert result is None

    def test_adapter_reads_grid_x_key(self, adapter, mock_client):
        """Verify the adapter reads the correct 'grid_x' key from the real API."""
        mock_client.get_decision_boundary.return_value = _make_cascor_boundary_response(5)
        result = adapter.get_decision_boundary(resolution=5)
        assert result is not None
        assert "xx" in result
