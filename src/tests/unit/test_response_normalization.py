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
    real_training_status_active,
    real_training_status_idle,
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
        """Real cascor returns envelope with data as a flat list of metrics."""
        client = MagicMock()
        client.get_metrics_history.return_value = real_metrics_history()
        monitor = _make_monitor(client)

        result = monitor.get_recent_metrics(count=100)

        assert isinstance(result, list)
        assert len(result) > 0
        # After normalization, entries should have canopy field names
        assert "train_loss" in result[0] or "loss" in result[0]

    def test_get_recent_metrics_with_fake_envelope(self):
        """Backward compat: old-style response with nested history key."""
        client = MagicMock()
        client.get_metrics_history.return_value = {"status": "ok", "data": {"history": [{"train_loss": 0.5}]}}
        monitor = _make_monitor(client)

        result = monitor.get_recent_metrics(count=100)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["train_loss"] == 0.5

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
        """Real cascor wraps current metrics in envelope — result should have epoch key directly."""
        client = MagicMock()
        client.get_metrics.return_value = real_metrics_current()
        monitor = _make_monitor(client)

        result = monitor.get_current_metrics()

        assert "epoch" in result
        assert result["epoch"] == 42


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
        """A metric dict with loss=0.0 should produce train_loss=0.0, not None."""
        metric = {"loss": 0.0, "accuracy": 0.0}
        normalized = CascorServiceAdapter._normalize_metric(metric)

        assert normalized["train_loss"] == 0.0
        assert normalized["train_accuracy"] == 0.0
