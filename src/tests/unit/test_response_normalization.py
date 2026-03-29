#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_response_normalization.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-03-26
# Last Modified: 2026-03-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Phase 0 characterization tests — document current bugs with real cascor responses
#####################################################################
"""
Phase 0 characterization tests for response normalization.

These tests exercise _ServiceTrainingMonitor and ServiceBackend methods with real
cascor ResponseEnvelope-formatted responses. They document what the code SHOULD do
after fixes — they will fail now and pass after Phase 2 fixes.

Uses unittest.mock.MagicMock to create mock clients returning fixture responses.
"""
from unittest.mock import MagicMock, PropertyMock

import pytest

try:
    from backend.cascor_service_adapter import CascorServiceAdapter, _ServiceTrainingMonitor
    from backend.service_backend import ServiceBackend

    _HAS_SERVICE_BACKEND = True
except ImportError:
    _HAS_SERVICE_BACKEND = False

pytestmark = pytest.mark.skipif(not _HAS_SERVICE_BACKEND, reason="juniper-cascor-client not installed")

from tests.fixtures.cascor_response_fixtures import (
    real_metrics_current,
    real_metrics_history,
    real_topology,
    real_training_status_active,
    real_training_status_idle,
    real_topology,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_monitor(client_mock):
    """Create a _ServiceTrainingMonitor wrapping a mock client."""
    return _ServiceTrainingMonitor(client_mock)


def _make_service_backend(adapter_mock):
    """Create a ServiceBackend wrapping a mock adapter."""
    return ServiceBackend(adapter_mock)


def _make_adapter_mock(**overrides):
    """Create a mock CascorServiceAdapter with sensible defaults.

    Keyword arguments override specific adapter method return values.
    """
    adapter = MagicMock(spec=CascorServiceAdapter)
    type(adapter).network = PropertyMock(return_value=MagicMock(__bool__=lambda s: True))
    adapter.is_training_in_progress.return_value = False
    adapter.training_monitor = MagicMock()
    adapter._service_url = "http://localhost:8200"
    for key, value in overrides.items():
        setattr(adapter, key, value) if not callable(value) else None
        if callable(value):
            getattr(adapter, key).return_value = value()
    return adapter


# ==================================================================
# FIX-1: get_recent_metrics envelope handling
# ==================================================================


@pytest.mark.unit
class TestFix1RecentMetrics:
    """FIX-1: _ServiceTrainingMonitor.get_recent_metrics must unwrap real cascor envelopes."""

    def test_get_recent_metrics_with_real_envelope(self):
        """Real cascor returns envelope with data as a flat list of metrics.

        After FIX-A (P5-RC-01): output is now nested dashboard format.
        """
        client = MagicMock()
        client.get_metrics_history.return_value = real_metrics_history()
        monitor = _make_monitor(client)

        result = monitor.get_recent_metrics(count=100)

        assert isinstance(result, list)
        assert len(result) > 0
        # After normalization + dashboard transform, entries use nested format
        assert "metrics" in result[0]
        assert "network_topology" in result[0]
        assert "loss" in result[0]["metrics"]
        assert "accuracy" in result[0]["metrics"]
        assert "hidden_units" in result[0]["network_topology"]

    def test_get_recent_metrics_with_fake_envelope(self):
        """Backward compat: old-style response with nested history key."""
        client = MagicMock()
        client.get_metrics_history.return_value = {"status": "ok", "data": {"history": [{"train_loss": 0.5}]}}
        monitor = _make_monitor(client)

        result = monitor.get_recent_metrics(count=100)

        assert isinstance(result, list)
        assert len(result) == 1
        # After FIX-A: output is nested dashboard format
        assert result[0]["metrics"]["loss"] == 0.5

    def test_get_recent_metrics_empty_data(self):
        """Empty data list should return empty list."""
        client = MagicMock()
        client.get_metrics_history.return_value = {"status": "success", "data": [], "meta": {}}
        monitor = _make_monitor(client)

        result = monitor.get_recent_metrics(count=100)

        assert result == []


# ==================================================================
# FIX-2: is_training envelope handling
# ==================================================================


@pytest.mark.unit
class TestFix2IsTraining:
    """FIX-2: _ServiceTrainingMonitor.is_training must handle real cascor envelopes."""

    def test_is_training_with_real_envelope(self):
        """Real cascor wraps training_active in a nested data structure."""
        client = MagicMock()
        client.get_training_status.return_value = real_training_status_active()
        monitor = _make_monitor(client)

        assert monitor.is_training is True

    def test_is_training_false_not_fallthrough(self):
        """Top-level is_training=False should take precedence (is not None guard)."""
        client = MagicMock()
        client.get_training_status.return_value = {
            "status": "ok",
            "is_training": False,
            "data": {"training_active": True},
        }
        monitor = _make_monitor(client)

        assert monitor.is_training is False


# ==================================================================
# FIX-3: get_current_metrics envelope handling
# ==================================================================


@pytest.mark.unit
class TestFix3CurrentMetrics:
    """FIX-3: _ServiceTrainingMonitor.get_current_metrics must unwrap envelope."""

    def test_get_current_metrics_unwraps(self):
        """Real cascor wraps current metrics in envelope — result uses nested dashboard format."""
        client = MagicMock()
        client.get_metrics.return_value = real_metrics_current()
        monitor = _make_monitor(client)

        result = monitor.get_current_metrics()

        assert "epoch" in result
        assert result["epoch"] == 42
        # After FIX-A (P5-RC-01, P5-RC-09): output is nested dashboard format
        assert "metrics" in result
        assert "network_topology" in result


# ==================================================================
# FIX-4: get_status normalization of cascor nested structure
# ==================================================================


@pytest.mark.unit
class TestFix4GetStatus:
    """FIX-4: ServiceBackend.get_status must normalize cascor's nested structure."""

    def test_get_status_normalizes_cascor(self):
        """Unwrapped data from real_training_status_active should normalize to flat keys."""
        unwrapped = real_training_status_active()["data"]
        adapter = _make_adapter_mock()
        adapter.get_training_status.return_value = unwrapped
        backend = _make_service_backend(adapter)

        result = backend.get_status()

        assert "is_running" in result
        assert "phase" in result
        assert "current_epoch" in result
        assert result["is_running"] is True
        assert result["current_epoch"] == 42

    def test_get_status_epoch_zero_preserved(self):
        """Epoch 0 should be preserved, not missing or None."""
        unwrapped = real_training_status_idle()["data"]
        adapter = _make_adapter_mock()
        adapter.get_training_status.return_value = unwrapped
        backend = _make_service_backend(adapter)

        result = backend.get_status()

        assert result["current_epoch"] == 0

    def test_get_status_hidden_units_zero_preserved(self):
        """Hidden units 0 should be preserved, not missing or None."""
        unwrapped = real_training_status_idle()["data"]
        adapter = _make_adapter_mock()
        adapter.get_training_status.return_value = unwrapped
        backend = _make_service_backend(adapter)

        result = backend.get_status()

        assert result.get("hidden_units", None) == 0

    def test_get_status_uppercase_started(self):
        """Cascor sends STARTED (uppercase) — should map to is_running=True."""
        unwrapped = real_training_status_active()["data"]
        assert unwrapped["state_machine"]["status"] == "STARTED"
        adapter = _make_adapter_mock()
        adapter.get_training_status.return_value = unwrapped
        backend = _make_service_backend(adapter)

        result = backend.get_status()

        assert result["is_running"] is True

    def test_get_status_passthrough_flat(self):
        """A flat dict (already normalized) should pass through unchanged."""
        flat = {"is_running": True, "phase": "output"}
        adapter = _make_adapter_mock()
        adapter.get_training_status.return_value = flat
        backend = _make_service_backend(adapter)

        result = backend.get_status()

        assert result["is_running"] is True
        assert result["phase"] == "output"

    def test_get_status_partial_nested(self):
        """Data with state_machine but no monitor should not crash."""
        partial = {
            "state_machine": {"status": "STARTED", "phase": "OUTPUT"},
            "training_active": True,
        }
        adapter = _make_adapter_mock()
        adapter.get_training_status.return_value = partial
        backend = _make_service_backend(adapter)

        result = backend.get_status()

        assert result.get("current_epoch", 0) == 0


# ==================================================================
# FIX-8: is_training_in_progress with real envelope
# ==================================================================


@pytest.mark.unit
class TestFix8IsTrainingInProgress:
    """FIX-8: CascorServiceAdapter.is_training_in_progress must handle real envelopes."""

    def test_is_training_in_progress_real(self):
        """Real cascor envelope should be unwrapped to detect active training."""
        client = MagicMock()
        client.get_training_status.return_value = real_training_status_active()
        adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
        adapter._client = client

        result = adapter.is_training_in_progress()

        assert result is True


# ==================================================================
# FIX-13: zero-value metric preservation
# ==================================================================


@pytest.mark.unit
class TestFix13ZeroMetricPreservation:
    """FIX-13: Metrics with value 0.0 must not be normalized to None."""

    def test_metrics_loss_zero_preserved(self):
        """A metric dict with loss=0.0 should produce train_loss=0.0 in flat, and preserve through dashboard transform."""
        metric = {"loss": 0.0, "accuracy": 0.0}
        normalized = CascorServiceAdapter._normalize_metric(metric)

        assert normalized["train_loss"] == 0.0
        assert normalized["train_accuracy"] == 0.0

        # Also verify through dashboard transform
        dashboard = CascorServiceAdapter._to_dashboard_metric(normalized)
        assert dashboard["metrics"]["loss"] == 0.0
        assert dashboard["metrics"]["accuracy"] == 0.0


# ==================================================================
# P5-RC-01 / P5-RC-09: Dashboard format contract tests
# ==================================================================


@pytest.mark.unit
class TestDashboardMetricsContract:
    """Verify service metrics output matches dashboard's nested access contract."""

    def test_to_dashboard_metric_produces_nested_format(self):
        """_to_dashboard_metric must produce the nested format the dashboard reads."""
        flat = {
            "epoch": 5,
            "train_loss": 0.45,
            "train_accuracy": 0.82,
            "val_loss": 0.60,
            "val_accuracy": 0.65,
            "hidden_units": 3,
            "phase": "output",
            "timestamp": "2026-03-28T12:00:00",
        }
        result = CascorServiceAdapter._to_dashboard_metric(flat)

        # Dashboard reads: m.get("metrics", {}).get("loss", 0)
        assert result["metrics"]["loss"] == 0.45
        assert result["metrics"]["accuracy"] == 0.82
        assert result["metrics"]["val_loss"] == 0.60
        assert result["metrics"]["val_accuracy"] == 0.65
        # Dashboard reads: m.get("network_topology", {}).get("hidden_units", 0)
        assert result["network_topology"]["hidden_units"] == 3
        # Top-level keys preserved
        assert result["epoch"] == 5
        assert result["phase"] == "output"
        assert result["timestamp"] == "2026-03-28T12:00:00"

    def test_metrics_history_uses_nested_format(self):
        """get_recent_metrics output must use nested keys, not flat keys."""
        client = MagicMock()
        client.get_metrics_history.return_value = real_metrics_history()
        monitor = _make_monitor(client)

        result = monitor.get_recent_metrics(count=100)

        for entry in result:
            # Must have nested "metrics" dict
            assert "metrics" in entry, f"Entry missing 'metrics' key: {entry.keys()}"
            assert isinstance(entry["metrics"], dict)
            # Must have nested "network_topology" dict
            assert "network_topology" in entry, f"Entry missing 'network_topology' key: {entry.keys()}"
            assert isinstance(entry["network_topology"], dict)
            # Must NOT have flat service keys
            assert "train_loss" not in entry, "Flat key 'train_loss' should not be at top level"
            assert "train_accuracy" not in entry, "Flat key 'train_accuracy' should not be at top level"

    def test_current_metrics_uses_nested_format(self):
        """get_current_metrics output must use nested keys, not flat keys."""
        client = MagicMock()
        client.get_metrics.return_value = real_metrics_current()
        monitor = _make_monitor(client)

        result = monitor.get_current_metrics()

        assert "metrics" in result
        assert "network_topology" in result
        assert "train_loss" not in result
        assert "train_accuracy" not in result

    def test_field_name_mapping_strips_train_prefix(self):
        """train_loss -> metrics.loss (strip train_ prefix), val_loss stays."""
        flat = {"train_loss": 0.5, "train_accuracy": 0.8, "val_loss": 0.6, "val_accuracy": 0.7}
        result = CascorServiceAdapter._to_dashboard_metric(flat)

        assert result["metrics"]["loss"] == 0.5
        assert result["metrics"]["accuracy"] == 0.8
        assert result["metrics"]["val_loss"] == 0.6
        assert result["metrics"]["val_accuracy"] == 0.7


# ==================================================================
# P5-RC-02: Topology transformation tests
# ==================================================================


@pytest.mark.unit
class TestTopologyTransformation:
    """Verify topology transformation from weight-oriented to graph-oriented format."""

    def test_transform_topology_basic(self):
        """Weight-oriented topology must be transformed to graph-oriented."""
        raw = real_topology()["data"]
        result = CascorServiceAdapter._transform_topology(raw)

        assert "input_units" in result
        assert "output_units" in result
        assert isinstance(result["hidden_units"], int)
        assert "nodes" in result
        assert "connections" in result
        assert result["input_units"] == 2
        assert result["output_units"] == 1
        assert result["hidden_units"] == 2

    def test_transform_topology_graph_format_passthrough(self):
        """Already graph-oriented topology must pass through unchanged."""
        graph = {
            "input_units": 2,
            "output_units": 1,
            "hidden_units": 3,
            "nodes": [{"id": "input_0", "type": "input"}],
            "connections": [{"from": "input_0", "to": "hidden_0", "weight": 0.5}],
        }
        result = CascorServiceAdapter._transform_topology(graph)
        assert result is graph  # Same object, not a copy

    def test_transform_topology_creates_correct_nodes(self):
        """Transformation must create input, hidden, and output nodes."""
        raw = real_topology()["data"]
        result = CascorServiceAdapter._transform_topology(raw)

        node_types = {n["type"] for n in result["nodes"]}
        assert "input" in node_types
        assert "hidden" in node_types
        assert "output" in node_types
        assert len([n for n in result["nodes"] if n["type"] == "input"]) == 2
        assert len([n for n in result["nodes"] if n["type"] == "hidden"]) == 2
        assert len([n for n in result["nodes"] if n["type"] == "output"]) == 1

    def test_transform_topology_cascade_connections(self):
        """Hidden unit 1 must connect to inputs AND to hidden unit 0 (cascade)."""
        raw = real_topology()["data"]
        result = CascorServiceAdapter._transform_topology(raw)

        # Hidden_1 should have connections from input_0, input_1, AND hidden_0
        h1_connections = [c for c in result["connections"] if c["to"] == "hidden_1"]
        h1_sources = {c["from"] for c in h1_connections}
        assert "input_0" in h1_sources
        assert "input_1" in h1_sources
        assert "hidden_0" in h1_sources  # Cascade connection

    def test_transform_topology_empty_network(self):
        """Network with no hidden units must still produce valid structure."""
        raw = {"input_size": 2, "output_size": 1, "hidden_units": [], "output_weights": [[0.5, 0.3]], "output_bias": [0.1]}
        result = CascorServiceAdapter._transform_topology(raw)

        assert result["input_units"] == 2
        assert result["output_units"] == 1
        assert result["hidden_units"] == 0
        assert len([n for n in result["nodes"] if n["type"] == "input"]) == 2
        assert len([n for n in result["nodes"] if n["type"] == "output"]) == 1

    def test_extract_network_topology_applies_transform(self):
        """extract_network_topology must apply _transform_topology."""
        client = MagicMock()
        client.get_topology.return_value = real_topology()
        adapter = CascorServiceAdapter.__new__(CascorServiceAdapter)
        adapter._client = client

        result = adapter.extract_network_topology()

        assert result is not None
        assert "input_units" in result
        assert isinstance(result["hidden_units"], int)
        assert "connections" in result


# ==================================================================
# P5-RC-03: Status normalization hardening tests
# ==================================================================


@pytest.mark.unit
class TestStatusNormalizationHardening:
    """Verify _normalize_status handles all case variants."""

    def test_normalize_status_lowercase(self):
        """Standard lowercase inputs normalize correctly."""
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("started") == "Started"
        assert CascorStateSync._normalize_status("paused") == "Paused"
        assert CascorStateSync._normalize_status("completed") == "Completed"
        assert CascorStateSync._normalize_status("stopped") == "Stopped"
        assert CascorStateSync._normalize_status("failed") == "Failed"
        assert CascorStateSync._normalize_status("idle") == "Stopped"
        assert CascorStateSync._normalize_status("training") == "Started"
        assert CascorStateSync._normalize_status("running") == "Started"

    def test_normalize_status_uppercase(self):
        """Uppercase enum names (from TrainingStatus.name) must normalize correctly."""
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("STARTED") == "Started"
        assert CascorStateSync._normalize_status("PAUSED") == "Paused"
        assert CascorStateSync._normalize_status("COMPLETED") == "Completed"
        assert CascorStateSync._normalize_status("STOPPED") == "Stopped"
        assert CascorStateSync._normalize_status("FAILED") == "Failed"

    def test_normalize_status_title_case(self):
        """Title-case (current CasCor broadcast format) must normalize correctly."""
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("Started") == "Started"
        assert CascorStateSync._normalize_status("Paused") == "Paused"
        assert CascorStateSync._normalize_status("Completed") == "Completed"
        assert CascorStateSync._normalize_status("Stopped") == "Stopped"
        assert CascorStateSync._normalize_status("Failed") == "Failed"

    def test_normalize_status_unknown_defaults_to_stopped(self):
        """Unknown status strings default to 'Stopped'."""
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("unknown_status") == "Stopped"
        assert CascorStateSync._normalize_status("") == "Stopped"

    def test_normalize_status_whitespace_handling(self):
        """Leading/trailing whitespace must be stripped."""
        from backend.state_sync import CascorStateSync

        assert CascorStateSync._normalize_status("  started  ") == "Started"
        assert CascorStateSync._normalize_status(" PAUSED ") == "Paused"
