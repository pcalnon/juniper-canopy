"""Tests for non-destructive attach to existing cascor network."""

import pytest
from juniper_cascor_client.exceptions import JuniperCascorNotFoundError

FakeCascorClient = pytest.importorskip("juniper_cascor_client.testing", reason="requires juniper-cascor-client[testing]").FakeCascorClient


class TestAttachToExisting:
    """Tests for non-destructive attachment to existing CasCor training sessions."""

    def test_attach_returns_true_when_network_exists(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        assert adapter.attach_to_existing() is True
        assert adapter._attached_to_existing is True

    def test_attach_returns_false_when_no_network(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        fake = FakeCascorClient(scenario="idle")  # No network loaded
        adapter = CascorServiceAdapter(client=fake)
        assert adapter.attach_to_existing() is False
        assert adapter._attached_to_existing is False

    def test_attach_does_not_raise_on_connection_error(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        fake = FakeCascorClient(scenario="error_prone")
        adapter = CascorServiceAdapter(client=fake)
        # Should return False gracefully, not raise
        result = adapter.attach_to_existing()
        assert isinstance(result, bool)

    def test_attach_does_not_create_network(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        fake = FakeCascorClient(scenario="idle")
        original_state = fake._network_loaded
        adapter = CascorServiceAdapter(client=fake)
        adapter.attach_to_existing()
        assert fake._network_loaded == original_state  # Unchanged
