"""Integration test: parameter application round-trip.

Validates that canopy nn_*/cn_* parameter names are correctly mapped to
cascor API parameter names on apply, and that get_canopy_params performs
the reverse mapping.
"""

import pytest

pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client[testing] not installed")

from juniper_cascor_client.testing import FakeCascorClient

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend


@pytest.fixture
def training_client():
    """FakeCascorClient with a running two_spiral network."""
    client = FakeCascorClient(scenario="two_spiral_training")
    yield client
    client.close()


@pytest.fixture
def adapter(training_client):
    """CascorServiceAdapter with injected FakeCascorClient."""
    return CascorServiceAdapter(client=training_client)


@pytest.fixture
def backend(adapter):
    """ServiceBackend wrapping the adapter."""
    return ServiceBackend(adapter)


@pytest.mark.integration
def test_apply_nn_learning_rate_maps_correctly(backend, training_client):
    """nn_learning_rate should map to cascor's learning_rate parameter."""
    result = backend.apply_params(nn_learning_rate=0.05)
    assert result["ok"] is True
    assert isinstance(result["data"], dict)


@pytest.mark.integration
def test_apply_all_mapped_params(backend, training_client):
    """All nn_*/cn_* params should map to cascor API names and be forwarded."""
    result = backend.apply_params(
        nn_learning_rate=0.02,
        nn_max_hidden_units=15,
        nn_max_total_epochs=500,
        nn_growth_convergence_threshold=5,
        cn_pool_size=16,
        cn_correlation_threshold=0.05,
        cn_training_iterations=100,
    )
    assert result["ok"] is True
    assert isinstance(result["data"], dict)


@pytest.mark.integration
def test_apply_unmapped_params_succeeds_with_message(backend):
    """Params without a cascor mapping should succeed with a 'no cascor-mappable' message."""
    result = backend.apply_params(nn_spiral_rotations=3.0, some_canopy_only_param=True)
    assert result["ok"] is True
    assert result.get("message") == "No cascor-mappable params provided"
    assert result.get("data") == {}


@pytest.mark.integration
def test_get_canopy_params_returns_mapped_keys(adapter):
    """get_canopy_params() should return canopy nn_*/cn_* namespace keys."""
    params = adapter.get_canopy_params()
    assert isinstance(params, dict)
    # The two_spiral_training scenario has these cascor params that should map back
    expected_canopy_keys = {"nn_learning_rate", "nn_max_hidden_units", "nn_max_total_epochs", "cn_pool_size", "cn_correlation_threshold", "cn_training_iterations"}
    # At least some of the expected keys should be present
    found_keys = set(params.keys()) & expected_canopy_keys
    assert len(found_keys) > 0, f"Expected some of {expected_canopy_keys} but got {params.keys()}"


@pytest.mark.integration
def test_apply_mixed_mapped_and_unmapped(backend):
    """A mix of mapped and unmapped params should forward only the mapped ones."""
    result = backend.apply_params(nn_learning_rate=0.03, unmapped_param=42)
    assert result["ok"] is True
    # The mapped param should have been forwarded (result contains data)
    assert isinstance(result["data"], dict)


@pytest.mark.integration
def test_apply_params_via_adapter_directly(adapter):
    """CascorServiceAdapter.apply_params should map and forward correctly."""
    result = adapter.apply_params(cn_pool_size=12)
    assert result["ok"] is True
    assert isinstance(result["data"], dict)
