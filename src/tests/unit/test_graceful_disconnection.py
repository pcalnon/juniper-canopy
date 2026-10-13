"""Tests for graceful canopy disconnection (cascor continues running)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FakeCascorClient = pytest.importorskip("juniper_cascor_client.testing", reason="requires juniper-cascor-client[testing]").FakeCascorClient


class TestGracefulDisconnection:
    """Tests for graceful WebSocket disconnection handling."""

    @pytest.mark.asyncio
    async def test_shutdown_does_not_call_stop_training(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)

        # Spy on stop_training
        original_stop = fake.stop_training
        stop_called = []

        def spy_stop():
            stop_called.append(True)
            return original_stop()

        fake.stop_training = spy_stop

        await backend.shutdown()
        assert not stop_called, "stop_training() must NOT be called on canopy shutdown"

    @pytest.mark.asyncio
    async def test_shutdown_does_not_call_delete_network(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)

        delete_called = []
        original_delete = fake.delete_network

        def spy_delete():
            delete_called.append(True)
            return original_delete()

        fake.delete_network = spy_delete

        await backend.shutdown()
        assert not delete_called, "delete_network() must NOT be called on canopy shutdown"

    def test_cascor_state_unchanged_after_adapter_shutdown(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        adapter.shutdown()
        # cascor should still show as training; FakeCascorClient (cascor-client
        # 0.5.0, Phase 4D) reports the canonical uppercase STATE_TRAINING.
        assert fake._state == "STARTED"
