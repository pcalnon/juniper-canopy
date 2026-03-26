"""Integration test: non-destructive attach to a running cascor instance.

Validates that ServiceBackend.initialize() performs non-destructive attach,
syncs state from cascor, and does NOT create/reset networks.
"""

import pytest

pytest.importorskip("juniper_cascor_client", reason="juniper-cascor-client not installed")

from unittest.mock import AsyncMock, patch

from juniper_cascor_client.testing import FakeCascorClient

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend
from backend.state_sync import SyncedState


@pytest.fixture
def training_client():
    """FakeCascorClient simulating a running cascor with existing network + training state."""
    client = FakeCascorClient(scenario="two_spiral_training")
    client.advance_epoch(25)
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
@pytest.mark.asyncio
async def test_initialize_calls_attach_and_syncs_state(adapter, training_client):
    """initialize() should call attach_to_existing() and sync cascor state."""
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock):
        sb = ServiceBackend(adapter)
        result = await sb.initialize()
        assert result is True
        assert adapter._attached_to_existing is True
        synced = sb.get_synced_state()
        assert synced is not None
        assert isinstance(synced, SyncedState)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_does_not_create_or_reset_network(adapter, training_client):
    """initialize() must not call create_network or reset on the cascor client."""
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock), patch.object(training_client, "create_network", wraps=training_client.create_network) as mock_create, patch.object(training_client, "reset_training", wraps=training_client.reset_training) as mock_reset:
        sb = ServiceBackend(adapter)
        await sb.initialize()
        mock_create.assert_not_called()
        mock_reset.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_synced_state_has_training_params(adapter):
    """State sync should populate params from the running cascor instance."""
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock):
        sb = ServiceBackend(adapter)
        await sb.initialize()
        synced = sb.get_synced_state()
        assert synced is not None
        assert isinstance(synced.params, dict)
        assert len(synced.params) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_synced_state_has_epoch_and_status(adapter):
    """State sync should capture the current epoch and training status."""
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock):
        sb = ServiceBackend(adapter)
        await sb.initialize()
        synced = sb.get_synced_state()
        assert synced is not None
        assert synced.is_training is True
        assert synced.status == "Started"
        assert synced.current_epoch >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_synced_state_has_topology(adapter):
    """State sync should fetch topology during sync."""
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock):
        sb = ServiceBackend(adapter)
        await sb.initialize()
        synced = sb.get_synced_state()
        assert synced is not None
        assert synced.topology is not None
        assert isinstance(synced.topology, dict)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_idle_does_not_sync(adapter):
    """When no network exists, initialize() should skip state sync."""
    idle_client = FakeCascorClient(scenario="idle")
    idle_adapter = CascorServiceAdapter(client=idle_client)
    with patch.object(idle_adapter, "start_metrics_relay", new_callable=AsyncMock):
        sb = ServiceBackend(idle_adapter)
        result = await sb.initialize()
        assert result is True
        assert sb.get_synced_state() is None
    idle_client.close()
