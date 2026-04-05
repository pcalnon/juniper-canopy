"""
Regression tests for CascorServiceAdapter parameter mapping.

These tests intentionally avoid real juniper-cascor-client behavior so they run
in CI environments where the package may be stubbed.
"""

from unittest.mock import MagicMock

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter


@pytest.fixture
def mock_client():
    """Mock client with only the methods needed for mapping tests."""
    client = MagicMock()
    client.update_params.return_value = {"ok": True}
    return client


@pytest.mark.unit
def test_apply_params_maps_candidate_specific_keys(mock_client):
    """cn_* candidate keys should translate to candidate_* cascor names."""
    adapter = CascorServiceAdapter(client=mock_client)

    result = adapter.apply_params(
        cn_patience=25,
        cn_training_convergence_threshold=0.0001,
        cn_training_iterations=300,
    )

    assert result["ok"] is True
    mock_client.update_params.assert_called_once_with(
        {
            "candidate_patience": 25,
            "candidate_convergence_threshold": 0.0001,
            "candidate_epochs": 300,
        }
    )


@pytest.mark.unit
def test_get_canopy_params_maps_candidate_specific_keys(mock_client):
    """candidate_* cascor response keys should map back to canopy cn_* keys."""
    mock_client.get_training_params.return_value = {
        "data": {
            "params": {
                "candidate_patience": 12,
                "candidate_convergence_threshold": 0.0005,
                "candidate_epochs": 150,
            }
        }
    }
    adapter = CascorServiceAdapter(client=mock_client)

    result = adapter.get_canopy_params()

    assert result["cn_patience"] == 12
    assert result["cn_training_convergence_threshold"] == 0.0005
    assert result["cn_training_iterations"] == 150
