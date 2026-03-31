"""Tests for CascorStateSync."""

from unittest.mock import MagicMock

import pytest

from tests.fixtures.cascor_response_fixtures import (
    real_metrics_history,
    real_topology,
    real_training_params,
    real_training_status_active,
)


def _fake_client_or_skip(scenario: str):
    """Return FakeCascorClient when testing utilities are available.

    The runtime package may be installed without the optional ``testing``
    module in some CI/automation environments.
    """
    testing_module = pytest.importorskip("juniper_cascor_client.testing", reason="juniper_cascor_client.testing is unavailable in this environment")
    return testing_module.FakeCascorClient(scenario=scenario)


class TestCascorStateSync:
    def test_sync_idle_state(self):
        from backend.state_sync import CascorStateSync

        fake = _fake_client_or_skip("idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        synced = CascorStateSync(fake).sync()
        assert synced.is_training is False
        assert synced.status == "Stopped"

    def test_sync_training_state(self):
        from backend.state_sync import CascorStateSync

        fake = _fake_client_or_skip("two_spiral_training")
        synced = CascorStateSync(fake).sync()
        assert synced.is_training is True
        assert synced.status == "Started"
        assert synced.current_epoch >= 0

    def test_sync_paused_state(self):
        from backend.state_sync import CascorStateSync

        fake = _fake_client_or_skip("two_spiral_training")
        fake.set_state("paused")
        synced = CascorStateSync(fake).sync()
        assert synced.status == "Paused"

    def test_sync_includes_metrics_history(self):
        from backend.state_sync import CascorStateSync

        fake = _fake_client_or_skip("two_spiral_training")
        fake.advance_epoch(10)
        synced = CascorStateSync(fake).sync(metrics_limit=100)
        assert len(synced.metrics_history) > 0

    def test_sync_tolerates_topology_failure(self):
        from unittest.mock import patch

        from backend.state_sync import CascorStateSync

        fake = _fake_client_or_skip("idle")
        fake.create_network(input_size=2, output_size=2, learning_rate=0.01)
        with patch.object(fake, "get_topology", side_effect=Exception("network error")):
            synced = CascorStateSync(fake).sync()
        assert synced.topology is None  # No exception raised

    def test_sync_respects_metrics_limit(self):
        from backend.state_sync import CascorStateSync

        fake = _fake_client_or_skip("two_spiral_training")
        fake.advance_epoch(200)
        synced = CascorStateSync(fake).sync(metrics_limit=50)
        assert len(synced.metrics_history) <= 50

    def test_normalize_status_mapping(self):
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("idle") == "Stopped"
        assert CascorStateSync._normalize_status("training") == "Started"
        assert CascorStateSync._normalize_status("paused") == "Paused"
        assert CascorStateSync._normalize_status("complete") == "Completed"
        assert CascorStateSync._normalize_status("started") == "Started"
        assert CascorStateSync._normalize_status("running") == "Started"
        assert CascorStateSync._normalize_status("completed") == "Completed"
        assert CascorStateSync._normalize_status("stopped") == "Stopped"
        assert CascorStateSync._normalize_status("unknown") == "Stopped"

    def test_sync_real_envelope_nested_status_fields(self):
        """Real cascor nested status payload should map into SyncedState."""
        from backend.state_sync import CascorStateSync

        class MockClient:
            def get_training_status(self):
                return real_training_status_active()

            def get_training_params(self):
                return real_training_params()

            def get_topology(self):
                return real_topology()

            def get_metrics_history(self, count=500):
                return real_metrics_history()

        synced = CascorStateSync(MockClient()).sync()
        assert synced.is_training is True
        assert synced.status == "Started"
        assert synced.phase == "output"
        assert synced.current_epoch == 42
        assert synced.max_epochs == 1000
        assert isinstance(synced.topology, dict)
        assert len(synced.metrics_history) == 3

    def test_sync_real_params_filter_non_param_fields(self):
        """Flat real-server param payload should exclude metadata fields."""
        from backend.state_sync import CascorStateSync

        class MockClient:
            def get_training_status(self):
                return {"status": "success", "data": {"training_active": False}}

            def get_training_params(self):
                return {
                    "status": "success",
                    "data": {
                        "learning_rate": 0.01,
                        "epochs_max": 100,
                        "status": "success",
                        "meta": {"source": "test"},
                        "timestamp": 123.4,
                        "dataset": "spiral",
                    },
                }

            def get_topology(self):
                return {}

            def get_metrics_history(self, count=500):
                return {"data": []}

        synced = CascorStateSync(MockClient()).sync()
        assert synced.params["nn_learning_rate"] == 0.01
        assert synced.params["nn_max_total_epochs"] == 100
        assert "status" not in synced.params
        assert "meta" not in synced.params
        assert "timestamp" not in synced.params
        assert "dataset" not in synced.params
