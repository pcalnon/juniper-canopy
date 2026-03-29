"""Tests for CascorStateSync."""

from unittest.mock import MagicMock

import pytest


def _make_fake_client(scenario: str):
    """Import FakeCascorClient lazily so non-fake tests can still run."""
    testing = pytest.importorskip("juniper_cascor_client.testing", reason="juniper-cascor-client testing helpers not installed")
    return testing.FakeCascorClient(scenario=scenario)


class TestCascorStateSync:
    def test_sync_idle_state(self):
        from backend.state_sync import CascorStateSync

        fake = _make_fake_client(scenario="idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        synced = CascorStateSync(fake).sync()
        assert synced.is_training is False
        assert synced.status == "Stopped"

    def test_sync_training_state(self):
        from backend.state_sync import CascorStateSync

        fake = _make_fake_client(scenario="two_spiral_training")
        synced = CascorStateSync(fake).sync()
        assert synced.is_training is True
        assert synced.status == "Started"
        assert synced.current_epoch >= 0

    def test_sync_paused_state(self):
        from backend.state_sync import CascorStateSync

        fake = _make_fake_client(scenario="two_spiral_training")
        fake.set_state("paused")
        synced = CascorStateSync(fake).sync()
        assert synced.status == "Paused"

    def test_sync_includes_metrics_history(self):
        from backend.state_sync import CascorStateSync

        fake = _make_fake_client(scenario="two_spiral_training")
        fake.advance_epoch(10)
        synced = CascorStateSync(fake).sync(metrics_limit=100)
        assert len(synced.metrics_history) > 0

    def test_sync_tolerates_topology_failure(self):
        from unittest.mock import patch

        from backend.state_sync import CascorStateSync

        fake = _make_fake_client(scenario="idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        with patch.object(fake, "get_topology", side_effect=Exception("network error")):
            synced = CascorStateSync(fake).sync()
        assert synced.topology is None  # No exception raised

    def test_sync_respects_metrics_limit(self):
        from backend.state_sync import CascorStateSync

        fake = _make_fake_client(scenario="two_spiral_training")
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


class TestCascorStateSyncNormalizationBranches:
    def _make_client(self):
        client = MagicMock()
        client.get_training_status.return_value = {"is_training": False, "data": {"training_active": False}}
        client.get_training_params.return_value = {"data": {"params": {}}}
        client.get_topology.return_value = {"data": {"input_size": 2, "output_size": 1, "hidden_units": []}}
        client.get_metrics_history.return_value = {"data": []}
        return client

    def test_sync_prefers_top_level_is_training_flag(self):
        from backend.state_sync import CascorStateSync

        client = self._make_client()
        client.get_training_status.return_value = {
            "is_training": False,
            "data": {
                "training_active": True,
                "state_machine": {"status": "TRAINING", "phase": "OUTPUT"},
                "monitor": {"current_epoch": 12},
                "training_state": {"max_epochs": 300},
            },
        }

        synced = CascorStateSync(client).sync()

        assert synced.is_training is False
        assert synced.status == "Started"
        assert synced.current_epoch == 12
        assert synced.max_epochs == 300

    def test_sync_maps_flat_param_payload_when_nested_params_missing(self):
        from backend.state_sync import CascorStateSync

        client = self._make_client()
        client.get_training_params.return_value = {
            "data": {
                "learning_rate": 0.04,
                "max_hidden_units": 8,
                "epochs_max": 222,
                "status": "started",
                "meta": {"source": "test"},
                "timestamp": "2026-03-29T00:00:00Z",
                "dataset": "two_spiral",
            }
        }

        synced = CascorStateSync(client).sync()

        assert synced.params["nn_learning_rate"] == 0.04
        assert synced.params["nn_max_hidden_units"] == 8
        assert synced.params["nn_max_total_epochs"] == 222
        assert "status" not in synced.params
        assert "meta" not in synced.params
        assert "timestamp" not in synced.params
        assert "dataset" not in synced.params

    def test_sync_normalizes_top_level_metrics_history_list(self):
        from backend.state_sync import CascorStateSync

        client = self._make_client()
        client.get_metrics_history.return_value = [
            {"epoch": 1, "loss": 0.0, "accuracy": 0.0, "hidden_units": 0},
            {"epoch": 2, "validation_loss": 0.55, "validation_accuracy": 0.88, "hidden_units": 1},
        ]

        synced = CascorStateSync(client).sync()

        assert len(synced.metrics_history) == 2
        assert synced.metrics_history[0]["metrics"]["loss"] == 0.0
        assert synced.metrics_history[0]["metrics"]["accuracy"] == 0.0
        assert synced.metrics_history[0]["network_topology"]["hidden_units"] == 0
        assert synced.metrics_history[1]["metrics"]["val_loss"] == 0.55
        assert synced.metrics_history[1]["metrics"]["val_accuracy"] == 0.88
