"""
Tests for ServiceBackend.get_decision_boundary() — delegation to adapter.

Verifies that ServiceBackend delegates decision boundary requests to the
CascorServiceAdapter instead of returning None.
"""

from unittest.mock import MagicMock, PropertyMock

import pytest

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
    type(adapter).network = PropertyMock(return_value=MagicMock(__bool__=lambda s: True))
    adapter._service_url = "http://localhost:8200"
    return adapter


@pytest.fixture
def service_backend(mock_adapter):
    """Create a ServiceBackend wrapping a mock adapter."""
    return ServiceBackend(mock_adapter)


class TestDecisionBoundaryDelegation:
    """Test that ServiceBackend delegates to adapter for decision boundary."""

    def test_delegates_to_adapter(self, service_backend, mock_adapter):
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

    def test_passes_resolution_to_adapter(self, service_backend, mock_adapter):
        """Resolution parameter should be forwarded to adapter."""
        mock_adapter.get_decision_boundary.return_value = {"xx": [], "yy": [], "Z": []}

        service_backend.get_decision_boundary(resolution=100)
        mock_adapter.get_decision_boundary.assert_called_once_with(100)

    def test_returns_none_when_adapter_returns_none(self, service_backend, mock_adapter):
        """Should propagate None from adapter (e.g., no network)."""
        mock_adapter.get_decision_boundary.return_value = None

        result = service_backend.get_decision_boundary(resolution=50)
        assert result is None

    def test_default_resolution(self, service_backend, mock_adapter):
        """Default resolution should be 50."""
        mock_adapter.get_decision_boundary.return_value = None

        service_backend.get_decision_boundary()
        mock_adapter.get_decision_boundary.assert_called_once_with(50)

    def test_returns_dict_with_expected_keys(self, service_backend, mock_adapter):
        """Result should contain all expected keys."""
        expected = {
            "xx": [[1, 2], [1, 2]],
            "yy": [[1, 1], [2, 2]],
            "Z": [[0.1, 0.9], [0.8, 0.2]],
            "x_min": -1.5,
            "x_max": 1.5,
            "y_min": -1.5,
            "y_max": 1.5,
            "resolution": 2,
        }
        mock_adapter.get_decision_boundary.return_value = expected

        result = service_backend.get_decision_boundary(resolution=2)

        for key in ("xx", "yy", "Z", "x_min", "x_max", "y_min", "y_max", "resolution"):
            assert key in result, f"Missing key: {key}"
