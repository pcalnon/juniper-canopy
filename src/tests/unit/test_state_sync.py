"""Tests for CascorStateSync."""

import pytest
from juniper_cascor_client.testing import FakeCascorClient


class TestCascorStateSync:
    def test_sync_idle_state(self):
        from backend.state_sync import CascorStateSync

        fake = FakeCascorClient(scenario="idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        synced = CascorStateSync(fake).sync()
        assert synced.is_training is False
        assert synced.status == "Stopped"

    def test_sync_training_state(self):
        from backend.state_sync import CascorStateSync

        fake = FakeCascorClient(scenario="two_spiral_training")
        synced = CascorStateSync(fake).sync()
        assert synced.is_training is True
        assert synced.status == "Started"
        assert synced.current_epoch >= 0

    def test_sync_paused_state(self):
        from backend.state_sync import CascorStateSync

        fake = FakeCascorClient(scenario="two_spiral_training")
        fake.set_state("paused")
        synced = CascorStateSync(fake).sync()
        assert synced.status == "Paused"

    def test_sync_includes_metrics_history(self):
        from backend.state_sync import CascorStateSync

        fake = FakeCascorClient(scenario="two_spiral_training")
        fake.advance_epoch(10)
        synced = CascorStateSync(fake).sync(metrics_limit=100)
        assert len(synced.metrics_history) > 0

    def test_sync_tolerates_topology_failure(self):
        from unittest.mock import patch

        from backend.state_sync import CascorStateSync

        fake = FakeCascorClient(scenario="idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        with patch.object(fake, "get_topology", side_effect=Exception("network error")):
            synced = CascorStateSync(fake).sync()
        assert synced.topology is None  # No exception raised

    def test_sync_respects_metrics_limit(self):
        from backend.state_sync import CascorStateSync

        fake = FakeCascorClient(scenario="two_spiral_training")
        fake.advance_epoch(200)
        synced = CascorStateSync(fake).sync(metrics_limit=50)
        assert len(synced.metrics_history) <= 50

    def test_normalize_status_mapping(self):
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("idle") == "Stopped"
        assert CascorStateSync._normalize_status("training") == "Started"
        assert CascorStateSync._normalize_status("paused") == "Paused"
        assert CascorStateSync._normalize_status("complete") == "Completed"
        assert CascorStateSync._normalize_status("unknown") == "Stopped"
