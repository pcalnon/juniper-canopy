"""Integration test: ServiceBackend + CascorServiceAdapter + FakeCascorClient.

Exercises the full protocol chain without a real CasCor service by injecting
FakeCascorClient into CascorServiceAdapter via the new `client` parameter.
"""

import pytest

pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")

from juniper_cascor_client.testing import FakeCascorClient

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.protocol import BackendProtocol
from backend.service_backend import ServiceBackend


@pytest.fixture
def fake_client():
    """FakeCascorClient configured for two_spiral_training scenario."""
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


# --- Protocol compliance ---


@pytest.mark.integration
def test_service_backend_satisfies_protocol(backend):
    """ServiceBackend must satisfy BackendProtocol."""
    assert isinstance(backend, BackendProtocol)


@pytest.mark.integration
def test_backend_type_is_service(backend):
    """ServiceBackend.backend_type should be 'service'."""
    assert backend.backend_type == "service"


# --- Network ---


@pytest.mark.integration
def test_has_network(backend):
    """two_spiral_training scenario starts with a network."""
    assert backend.has_network() is True


@pytest.mark.integration
def test_get_network_topology(backend):
    """Topology should be available for the training scenario."""
    topology = backend.get_network_topology()
    assert topology is not None
    assert isinstance(topology, dict)


@pytest.mark.integration
def test_get_network_stats(backend):
    """Network stats should return a dict."""
    stats = backend.get_network_stats()
    assert isinstance(stats, dict)


# --- Status & metrics ---


@pytest.mark.integration
def test_get_status(backend):
    """Status should return a dict with training info."""
    status = backend.get_status()
    assert isinstance(status, dict)


@pytest.mark.integration
def test_get_metrics(backend):
    """Metrics should return a dict."""
    metrics = backend.get_metrics()
    assert isinstance(metrics, dict)


@pytest.mark.integration
def test_get_metrics_history(backend):
    """Metrics history should return a list."""
    history = backend.get_metrics_history(count=10)
    assert isinstance(history, list)


# --- Training control ---


@pytest.mark.integration
def test_is_training_active(backend):
    """two_spiral_training starts in training state."""
    assert backend.is_training_active() is True


@pytest.mark.integration
def test_stop_training(backend):
    """Stop training should succeed."""
    result = backend.stop_training()
    assert isinstance(result, dict)
    assert result.get("ok") is True


@pytest.mark.integration
def test_start_training_when_already_running(backend):
    """Starting training when already running should report an error."""
    result = backend.start_training()
    assert result.get("ok") is False


# --- Dataset ---


@pytest.mark.integration
def test_get_dataset(backend):
    """Dataset info should be available for training scenario."""
    dataset = backend.get_dataset()
    assert dataset is not None
    assert isinstance(dataset, dict)


# --- Decision boundary ---


@pytest.mark.integration
def test_get_decision_boundary_returns_none(backend):
    """Decision boundary is not available over REST."""
    result = backend.get_decision_boundary()
    assert result is None


# --- Lifecycle ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_connects(adapter, mocker):
    """Initialize should return True when FakeCascorClient is healthy."""
    # Mock start_metrics_relay to avoid WebSocket/logger dependencies
    mocker.patch.object(adapter, "start_metrics_relay", return_value=None)
    sb = ServiceBackend(adapter)
    result = await sb.initialize()
    assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_shutdown_does_not_raise(adapter, mocker):
    """Shutdown should complete without errors."""
    mocker.patch.object(adapter, "start_metrics_relay", return_value=None)
    mocker.patch.object(adapter, "stop_metrics_relay", return_value=None)
    sb = ServiceBackend(adapter)
    await sb.initialize()
    await sb.shutdown()


# --- Idle scenario ---


@pytest.mark.integration
def test_idle_scenario_has_no_network():
    """Idle scenario should report no network."""
    fake = FakeCascorClient(scenario="idle")
    adapter = CascorServiceAdapter(client=fake)
    sb = ServiceBackend(adapter)
    assert sb.has_network() is False
    fake.close()


@pytest.mark.integration
def test_idle_scenario_start_training_fails():
    """Starting training without a network should fail."""
    fake = FakeCascorClient(scenario="idle")
    adapter = CascorServiceAdapter(client=fake)
    sb = ServiceBackend(adapter)
    result = sb.start_training()
    assert result.get("ok") is False
    fake.close()


# --- Converged scenario ---


@pytest.mark.integration
def test_converged_scenario_not_training():
    """xor_converged scenario should not be actively training."""
    fake = FakeCascorClient(scenario="xor_converged")
    adapter = CascorServiceAdapter(client=fake)
    sb = ServiceBackend(adapter)
    assert sb.is_training_active() is False
    fake.close()


@pytest.mark.integration
def test_converged_scenario_has_network():
    """xor_converged scenario should have a network."""
    fake = FakeCascorClient(scenario="xor_converged")
    adapter = CascorServiceAdapter(client=fake)
    sb = ServiceBackend(adapter)
    assert sb.has_network() is True
    fake.close()


# --- Apply params (not supported in service mode) ---


@pytest.mark.integration
def test_apply_params_not_supported(backend):
    """apply_params should report not supported."""
    result = backend.apply_params(learning_rate=0.001)
    assert result.get("ok") is False
