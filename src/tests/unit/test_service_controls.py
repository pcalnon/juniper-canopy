"""Tests for service mode training controls (pause/resume/reset)."""

import pytest
from juniper_cascor_client.testing import FakeCascorClient


class TestServiceModeControls:
    def test_pause_training_delegates_to_cascor(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)
        result = backend.pause_training()
        assert result["ok"] is True
        assert fake._state == "paused"

    def test_resume_training_delegates_to_cascor(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        fake.set_state("paused")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)
        result = backend.resume_training()
        assert result["ok"] is True
        assert fake._state == "training"

    def test_reset_training_delegates_to_cascor(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)
        result = backend.reset_training()
        assert result["ok"] is True
        assert fake._state == "idle"

    def test_pause_returns_error_when_not_training(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)
        result = backend.pause_training()
        assert result["ok"] is False

    def test_apply_params_maps_nn_keys(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)
        result = backend.apply_params(nn_learning_rate=0.005)
        assert result["ok"] is True
        # learning_rate should be updated in fake
        assert fake._network_config.get("learning_rate") == 0.005

    def test_apply_params_skips_unknown_keys(self):
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        fake = FakeCascorClient(scenario="two_spiral_training")
        adapter = CascorServiceAdapter(client=fake)
        backend = ServiceBackend(adapter)
        # nn_spiral_rotations has no cascor equivalent — should not raise
        result = backend.apply_params(nn_spiral_rotations=3)
        assert result["ok"] is True
