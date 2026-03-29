"""Characterization tests for cascor response normalization.

These tests validate that canopy correctly handles both real cascor
ResponseEnvelope responses and FakeCascorClient responses. Initially
written as failing tests documenting bugs; they pass after Phase 2 fixes.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from tests.fixtures.cascor_response_fixtures import (
    fake_metrics_history,
    fake_training_status_active,
    fake_training_status_idle,
    real_dataset,
    real_metrics_current,
    real_metrics_history,
    real_training_params,
    real_training_status_active,
    real_training_status_epoch_zero,
    real_training_status_idle,
    real_topology,
)

# ---------------------------------------------------------------------------
# Helper: create a mock client that returns the given fixtures
# ---------------------------------------------------------------------------


def _make_mock_client(**method_returns):
    """Create a mock JuniperCascorClient with specified return values."""
    client = MagicMock()
    for method_name, return_value in method_returns.items():
        getattr(client, method_name).return_value = return_value
    return client


# ===========================================================================
# FIX-1: _ServiceTrainingMonitor.get_recent_metrics()
# ===========================================================================


class TestGetRecentMetrics:
    """FIX-1: get_recent_metrics must handle both real and fake envelope formats."""

    def test_real_envelope_returns_metrics_list(self):
        """Real cascor: data is a flat list, not data.history."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics_history=real_metrics_history())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_recent_metrics(count=10)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["train_loss"] == 0.95
        assert result[0]["epoch"] == 1

    def test_fake_envelope_returns_metrics_list(self):
        """FakeCascorClient: data.history is a list."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics_history=fake_metrics_history())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_recent_metrics(count=10)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["train_loss"] == 0.95

    def test_empty_data_returns_empty_list(self):
        """Edge case: empty data dict returns empty list."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics_history={"status": "success", "data": []})
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_recent_metrics(count=10)

        assert result == []

    def test_loss_zero_preserved(self):
        """FIX-13 edge: loss=0.0 must not be treated as missing."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics_history=real_metrics_history())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_recent_metrics(count=10)

        # Third entry in fixture has loss=0.0
        assert result[2]["train_loss"] == 0.0


# ===========================================================================
# FIX-2: _ServiceTrainingMonitor.is_training
# ===========================================================================


class TestIsTraining:
    """FIX-2: is_training must handle real cascor nested format."""

    def test_real_envelope_active(self):
        """Real cascor: training_active=True at data level."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_training_status=real_training_status_active())
        monitor = _ServiceTrainingMonitor(client)
        assert monitor.is_training is True

    def test_real_envelope_idle(self):
        """Real cascor: training_active=False."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_training_status=real_training_status_idle())
        monitor = _ServiceTrainingMonitor(client)
        assert monitor.is_training is False

    def test_fake_envelope_active(self):
        """FakeCascorClient: top-level is_training=True."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_training_status=fake_training_status_active())
        monitor = _ServiceTrainingMonitor(client)
        assert monitor.is_training is True

    def test_false_not_fallthrough(self):
        """FIX-2 edge: is_training=False must not fall through to nested check."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        # FakeCascorClient with is_training=False explicitly set
        client = _make_mock_client(get_training_status=fake_training_status_idle())
        monitor = _ServiceTrainingMonitor(client)
        assert monitor.is_training is False


# ===========================================================================
# FIX-3: _ServiceTrainingMonitor.get_current_metrics()
# ===========================================================================


class TestGetCurrentMetrics:
    """FIX-3: get_current_metrics must unwrap envelope."""

    def test_real_envelope_unwraps(self):
        """Real cascor: must return inner dict, not full envelope."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics=real_metrics_current())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_current_metrics()

        assert "train_loss" in result
        assert result["train_loss"] == 0.45
        # Must NOT contain envelope keys
        assert "status" not in result
        assert "meta" not in result

    def test_real_envelope_emits_legacy_metrics_shape(self):
        """Current metrics include legacy nested metrics keys used by dashboard."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics=real_metrics_current())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_current_metrics()

        assert result["metrics"]["loss"] == 0.45
        assert result["metrics"]["accuracy"] == 0.72


# ===========================================================================
# FIX-4: ServiceBackend.get_status()
# ===========================================================================


class TestGetStatus:
    """FIX-4: get_status must normalize cascor nested structure to flat dict."""

    def _make_service_backend(self, training_status_fixture):
        """Create a ServiceBackend with a mocked adapter returning the given status."""
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        adapter = MagicMock(spec=CascorServiceAdapter)
        # get_training_status on the adapter returns unwrapped data
        # (since _unwrap_response is called inside the adapter method)
        data = training_status_fixture.get("data", training_status_fixture)
        adapter.get_training_status.return_value = data
        backend = ServiceBackend(adapter)
        return backend

    def test_normalizes_cascor_nested(self):
        """Real cascor nested structure -> flat dashboard dict."""
        backend = self._make_service_backend(real_training_status_active())
        status = backend.get_status()

        assert status["is_running"] is True
        assert status["is_training"] is True
        assert status["phase"] == "output"
        assert status["current_epoch"] == 42
        assert status["hidden_units"] == 3

    def test_epoch_zero_preserved(self):
        """FIX-4 edge: epoch=0 must not be treated as missing."""
        backend = self._make_service_backend(real_training_status_epoch_zero())
        status = backend.get_status()

        assert status["current_epoch"] == 0
        assert status["is_training"] is True

    def test_hidden_units_zero_preserved(self):
        """FIX-4 edge: hidden_units=0 must not be treated as missing."""
        backend = self._make_service_backend(real_training_status_epoch_zero())
        status = backend.get_status()

        assert status["hidden_units"] == 0

    def test_uppercase_started(self):
        """FIX-4 case: STARTED -> is_running=True."""
        backend = self._make_service_backend(real_training_status_active())
        status = backend.get_status()

        assert status["is_running"] is True
        assert status["is_paused"] is False
        assert status["completed"] is False

    def test_passthrough_flat(self):
        """Demo-compatible flat dict passes through unchanged."""
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        adapter = MagicMock(spec=CascorServiceAdapter)
        flat_status = {
            "is_training": True,
            "is_running": True,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 2,
        }
        adapter.get_training_status.return_value = flat_status
        backend = ServiceBackend(adapter)
        status = backend.get_status()

        # Flat format should pass through
        assert status["is_running"] is True
        assert status["current_epoch"] == 10

    def test_partial_nested(self):
        """FIX-4: handles partial nested structure (e.g., missing monitor)."""
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        adapter = MagicMock(spec=CascorServiceAdapter)
        partial = {
            "training_active": True,
            "state_machine": {"status": "STARTED", "phase": "OUTPUT"},
            # monitor missing
            "training_state": {"max_epochs": 100},
        }
        adapter.get_training_status.return_value = partial
        backend = ServiceBackend(adapter)
        status = backend.get_status()

        assert status["is_running"] is True
        assert status["current_epoch"] == 0  # default when monitor missing
        assert status["hidden_units"] == 0


# ===========================================================================
# FIX-8: CascorServiceAdapter.is_training_in_progress()
# ===========================================================================


class TestIsTrainingInProgress:
    """FIX-8: is_training_in_progress has same envelope bug as is_training."""

    def test_real_envelope(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        client = _make_mock_client(get_training_status=real_training_status_active())
        adapter = CascorServiceAdapter(client=client)
        assert adapter.is_training_in_progress() is True

    def test_real_envelope_idle(self):
        from backend.cascor_service_adapter import CascorServiceAdapter

        client = _make_mock_client(get_training_status=real_training_status_idle())
        adapter = CascorServiceAdapter(client=client)
        assert adapter.is_training_in_progress() is False


# ===========================================================================
# FIX-13: Metric field name normalization
# ===========================================================================


class TestMetricFieldNormalization:
    """FIX-13: loss -> train_loss, accuracy -> train_accuracy, etc."""

    def test_real_field_names_normalized(self):
        """Real cascor field names are mapped to canopy canonical names."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics_history=real_metrics_history())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_recent_metrics(count=10)

        entry = result[0]
        assert "train_loss" in entry
        assert "train_accuracy" in entry
        assert "val_loss" in entry
        assert "val_accuracy" in entry
        # Raw names should not be present
        assert "loss" not in entry
        assert "accuracy" not in entry
        # Legacy nested shape expected by metrics panel callbacks
        assert entry["metrics"]["loss"] == 0.95
        assert entry["metrics"]["accuracy"] == 0.35
        assert entry["network_topology"]["hidden_units"] == 0

    def test_fake_field_names_preserved(self):
        """FakeCascorClient already uses canopy names."""
        from backend.cascor_service_adapter import _ServiceTrainingMonitor

        client = _make_mock_client(get_metrics_history=fake_metrics_history())
        monitor = _ServiceTrainingMonitor(client)
        result = monitor.get_recent_metrics(count=10)

        entry = result[0]
        assert entry["train_loss"] == 0.95
        assert entry["train_accuracy"] == 0.35


# ===========================================================================
# FIX-9: extract_network_topology() cascor -> canopy conversion
# ===========================================================================


class TestExtractNetworkTopology:
    """Covers topology conversion paths with high dashboard blast radius."""

    def test_real_topology_converted_to_canopy_shape(self):
        """Real cascor topology should be converted into canopy node/edge schema."""
        from backend.cascor_service_adapter import CascorServiceAdapter

        client = _make_mock_client(get_topology=real_topology())
        adapter = CascorServiceAdapter(client=client)
        result = adapter.extract_network_topology()

        assert result is not None
        assert result["input_units"] == 2
        assert result["output_units"] == 3
        assert result["hidden_units"] == 2
        assert len(result["nodes"]) == 7  # 2 input + 2 hidden + 3 output
        assert any(c["from"] == "input_0" and c["to"] == "hidden_0" for c in result["connections"])
        assert any(c["from"] == "hidden_1" and c["to"] == "output_2" for c in result["connections"])

    def test_canopy_topology_passthrough_unchanged(self):
        """Topology already in canopy format should not be transformed."""
        from backend.cascor_service_adapter import CascorServiceAdapter

        canopy_topology = {
            "input_units": 2,
            "hidden_units": 1,
            "output_units": 2,
            "nodes": [{"id": "input_0"}, {"id": "hidden_0"}, {"id": "output_0"}, {"id": "output_1"}],
            "connections": [{"from": "input_0", "to": "hidden_0"}],
        }
        client = _make_mock_client(get_topology={"status": "success", "data": canopy_topology})
        adapter = CascorServiceAdapter(client=client)

        result = adapter.extract_network_topology()
        assert result == canopy_topology


# ===========================================================================
# FIX-10: ServiceBackend.get_dataset() real cascor shape normalization
# ===========================================================================


class TestDatasetNormalization:
    """Ensure dataset metadata is normalized to frontend contract."""

    def test_real_dataset_fields_mapped_for_dashboard(self):
        """input_features/output_features shape should map to num_* fields."""
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        adapter = MagicMock(spec=CascorServiceAdapter)
        adapter.get_dataset_info.return_value = real_dataset()["data"]
        backend = ServiceBackend(adapter)

        dataset = backend.get_dataset()
        assert dataset is not None
        assert dataset["num_samples"] == 1000
        assert dataset["num_features"] == 2
        assert dataset["num_classes"] == 3
        assert dataset["train_samples"] == 800
        assert dataset["test_samples"] == 200

    def test_missing_counts_default_to_zero(self):
        """Missing train/test counts should not raise and should default safely."""
        from backend.cascor_service_adapter import CascorServiceAdapter
        from backend.service_backend import ServiceBackend

        adapter = MagicMock(spec=CascorServiceAdapter)
        adapter.get_dataset_info.return_value = {"input_features": 4, "output_features": 2, "loaded": True}
        backend = ServiceBackend(adapter)

        dataset = backend.get_dataset()
        assert dataset is not None
        assert dataset["num_samples"] == 0
        assert dataset["train_samples"] == 0
        assert dataset["test_samples"] == 0
