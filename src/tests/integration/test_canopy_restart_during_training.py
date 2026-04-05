"""Integration test: canopy can start/stop without affecting cascor.

Validates that canopy shutdown does not stop or reset training on cascor,
and that a new canopy instance can re-attach and restore state.
"""

import pytest

pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client[testing] not installed")

from unittest.mock import AsyncMock, patch

from juniper_cascor_client.testing import FakeCascorClient

from backend.cascor_service_adapter import CascorServiceAdapter
from backend.service_backend import ServiceBackend


@pytest.fixture
def training_client():
    """FakeCascorClient simulating a running cascor with training in progress."""
    client = FakeCascorClient(scenario="two_spiral_training")
    client.advance_epoch(10)
    yield client
    client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initialize_establishes_connection(training_client):
    """ServiceBackend.initialize() should connect and report success."""
    adapter = CascorServiceAdapter(client=training_client)
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock):
        sb = ServiceBackend(adapter)
        result = await sb.initialize()
        assert result is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_shutdown_does_not_stop_cascor_training(training_client):
    """shutdown() should call adapter.shutdown() but NOT stop/reset training on cascor."""
    adapter = CascorServiceAdapter(client=training_client)
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock), patch.object(adapter, "stop_metrics_relay", new_callable=AsyncMock), patch.object(training_client, "stop_training", wraps=training_client.stop_training) as mock_stop, patch.object(training_client, "reset_training", wraps=training_client.reset_training) as mock_reset:
        sb = ServiceBackend(adapter)
        await sb.initialize()
        await sb.shutdown()
        mock_stop.assert_not_called()
        mock_reset.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_shutdown_does_not_send_stop_command(training_client):
    """shutdown() should close the HTTP session but never send stop/reset commands.

    We verify by wrapping stop_training/reset_training on the client and confirming
    they are never called. The client.close() call is expected (session teardown),
    but that is a local resource cleanup, not a cascor-side training command.
    """
    adapter = CascorServiceAdapter(client=training_client)
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock), patch.object(adapter, "stop_metrics_relay", new_callable=AsyncMock), patch.object(training_client, "stop_training", wraps=training_client.stop_training) as mock_stop, patch.object(training_client, "reset_training", wraps=training_client.reset_training) as mock_reset:
        sb = ServiceBackend(adapter)
        await sb.initialize()
        await sb.shutdown()
        mock_stop.assert_not_called()
        mock_reset.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_canopy_reconnects_and_restores_state():
    """A fresh ServiceBackend should re-attach and restore state from a still-running cascor.

    Simulates two separate canopy sessions connecting to the same cascor service.
    Uses separate FakeCascorClient instances to model independent HTTP sessions
    against the same running cascor.
    """
    # First canopy session
    client1 = FakeCascorClient(scenario="two_spiral_training")
    client1.advance_epoch(10)
    adapter1 = CascorServiceAdapter(client=client1)
    with patch.object(adapter1, "start_metrics_relay", new_callable=AsyncMock), patch.object(adapter1, "stop_metrics_relay", new_callable=AsyncMock):
        sb1 = ServiceBackend(adapter1)
        await sb1.initialize()
        await sb1.shutdown()

    # Second canopy session (fresh client simulating same cascor service, still training)
    client2 = FakeCascorClient(scenario="two_spiral_training")
    client2.advance_epoch(15)
    adapter2 = CascorServiceAdapter(client=client2)
    with patch.object(adapter2, "start_metrics_relay", new_callable=AsyncMock):
        sb2 = ServiceBackend(adapter2)
        result = await sb2.initialize()
        assert result is True
        assert adapter2._attached_to_existing is True
        synced = sb2.get_synced_state()
        assert synced is not None
        assert synced.is_training is True
        assert synced.status == "Started"
    client2.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_shutdown_calls_adapter_shutdown(training_client):
    """shutdown() should invoke adapter.shutdown() to close the HTTP session."""
    adapter = CascorServiceAdapter(client=training_client)
    with patch.object(adapter, "start_metrics_relay", new_callable=AsyncMock), patch.object(adapter, "stop_metrics_relay", new_callable=AsyncMock), patch.object(adapter, "shutdown", wraps=adapter.shutdown) as mock_shutdown:
        sb = ServiceBackend(adapter)
        await sb.initialize()
        await sb.shutdown()
        mock_shutdown.assert_called_once()
