"""Regression coverage for CasCor service adapter network mutations.

These tests intentionally exercise the adapter through the lightweight
``juniper_cascor_client`` stub installed by ``tests/conftest.py`` when the
real package is absent. The older adapter test module skips in that scenario,
so these checks keep the CAN-015h transport contract covered in minimal CI
environments.
"""

from unittest.mock import MagicMock

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter


@pytest.fixture
def mock_client():
    """Return a fake CasCor client with private HTTP verbs available."""
    return MagicMock()


@pytest.fixture
def adapter(mock_client):
    """Return an adapter wired to the fake client."""
    return CascorServiceAdapter(service_url="http://localhost:8200", client=mock_client)


@pytest.mark.unit
@pytest.mark.parametrize(
    "method_name",
    [
        "patch_weights",
        "add_hidden_unit",
        "remove_hidden_unit",
    ],
)
def test_network_mutation_methods_are_part_of_adapter_contract(adapter, method_name):
    """Expose all CAN-015h mutation methods for future route/UI callers."""
    assert callable(getattr(adapter, method_name))


@pytest.mark.unit
def test_patch_weights_preserves_non_default_dtype_and_hidden_unit_index(adapter, mock_client):
    """Forward dtype and hidden-unit index exactly to CasCor validation."""
    mock_client._patch.return_value = {"operation": "patch_weights"}

    adapter.patch_weights(
        target="hidden_unit",
        field="weights",
        values=[[0.1, 0.2, 0.3]],
        hidden_unit_index=2,
        dtype="float64",
    )

    mock_client._patch.assert_called_once_with(
        "/v1/network/weights",
        json={
            "target": "hidden_unit",
            "field": "weights",
            "values": [[0.1, 0.2, 0.3]],
            "dtype": "float64",
            "hidden_unit_index": 2,
        },
    )


@pytest.mark.unit
def test_patch_weights_does_not_synthesize_hidden_unit_index(adapter, mock_client):
    """Leave missing hidden-unit indexes for the CasCor route to reject."""
    mock_client._patch.return_value = {"operation": "patch_weights"}

    adapter.patch_weights(
        target="hidden_unit",
        field="bias",
        values=[0.5],
    )

    mock_client._patch.assert_called_once()
    body = mock_client._patch.call_args.kwargs["json"]
    assert body == {
        "target": "hidden_unit",
        "field": "bias",
        "values": [0.5],
        "dtype": "float32",
    }
    assert "hidden_unit_index" not in body

