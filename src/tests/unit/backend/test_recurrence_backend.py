#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_backend.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-22
# Last Modified: 2026-06-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for RecurrenceBackend (A1-ii) — the BackendProtocol
#                wrapper that backgrounds the recurrence one-shot fit. Uses a
#                controllable fake adapter (no network, no live service).
#####################################################################
"""Unit tests for ``backend.recurrence_backend.RecurrenceBackend`` (A1-ii).

Verifies the one-shot execution paradigm: ``start_training`` backgrounds the blocking
``adapter.train`` and the backend reports a binary idle/training/trained/failed status;
dataset ref + hyperparameters are forwarded; the cascade-only surface is stubbed; and the
unsupported controls (stop/pause/resume) fail closed.
"""

import threading
import time

import pytest

from backend.protocol import BackendProtocol
from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceServiceError, RecurrenceTrainResult


def _make_result():
    return RecurrenceTrainResult(
        final_metrics={"r2": 0.96, "mse": 0.02, "rmse": 0.14, "mae": 0.1, "loss": 0.02},
        n_epochs=1,
        stopped_reason="fit_complete",
        dataset={"name": "equities_seq", "dataset_id": "ds-1", "n_windows": 200, "lookback": 32, "n_features": 5, "output_dim": 1},
    )


class _FakeAdapter:
    """Stand-in for RecurrenceServiceAdapter with a controllable ``train``."""

    def __init__(self, *, result=None, error=None, gate=None):
        self.service_url = "http://rec.test:8210"
        self._result = result if result is not None else _make_result()
        self._error = error
        self._gate = gate  # if set, train() blocks on this Event (simulates a long fit)
        self.calls = []

    def train(self, **kwargs):
        self.calls.append(kwargs)
        if self._gate is not None:
            self._gate.wait(timeout=5.0)
        if self._error is not None:
            raise self._error
        return self._result


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


@pytest.mark.unit
class TestIdentityAndConformance:
    def test_backend_type(self):
        assert RecurrenceBackend(_FakeAdapter()).backend_type == "recurrence"

    def test_protocol_conformance(self):
        assert isinstance(RecurrenceBackend(_FakeAdapter()), BackendProtocol)


@pytest.mark.unit
class TestStartTraining:
    def test_backgrounds_and_completes(self):
        backend = RecurrenceBackend(_FakeAdapter())
        result = backend.start_training(generator="equities_seq")
        assert result["ok"] is True
        assert _wait_until(lambda: not backend.is_training_active())
        status = backend.get_status()
        assert status["completed"] is True
        assert status["fsm_status"] == "trained"
        assert backend.has_network() is True

    def test_in_progress_status_while_fitting(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        try:
            backend.start_training(generator="equities_seq")
            assert _wait_until(backend.is_training_active)
            status = backend.get_status()
            assert status["is_training"] is True
            assert status["fsm_status"] == "training"
            assert status["phase"] == "fitting"
        finally:
            gate.set()  # release the fit so the daemon thread can finish
        assert _wait_until(lambda: not backend.is_training_active())

    def test_requires_dataset_ref(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        result = backend.start_training()  # no ref
        assert result["ok"] is False
        assert backend.is_training_active() is False
        assert adapter.calls == []  # never reached the adapter

    def test_forwards_dataset_ref_and_hyperparams(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        backend.start_training(name="equities_seq", params={"n": 128}, split="full", d=8, theta=1.5, ridge=0.1)
        assert _wait_until(lambda: not backend.is_training_active())
        call = adapter.calls[0]
        assert call["name"] == "equities_seq"
        assert call["params"] == {"n": 128}
        assert call["split"] == "full"
        assert call["d"] == 8 and call["theta"] == 1.5 and call["ridge"] == 0.1

    def test_double_start_rejected(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        try:
            first = backend.start_training(generator="equities_seq")
            assert first["ok"] is True
            assert _wait_until(backend.is_training_active)
            second = backend.start_training(generator="equities_seq")
            assert second["ok"] is False
            assert "in progress" in second["error"]
        finally:
            gate.set()
        assert _wait_until(lambda: not backend.is_training_active())


@pytest.mark.unit
class TestFailureHandling:
    def test_failed_fit_sets_failed_state(self):
        adapter = _FakeAdapter(error=RecurrenceServiceError("boom", status_code=500))
        backend = RecurrenceBackend(adapter)
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        status = backend.get_status()
        assert status["failed"] is True
        assert status["fsm_status"] == "failed"
        assert "boom" in status["completion_reason"]
        assert backend.has_network() is False


@pytest.mark.unit
class TestUnsupportedControls:
    def test_stop_pause_resume_fail_closed(self):
        backend = RecurrenceBackend(_FakeAdapter())
        assert backend.stop_training()["ok"] is False
        assert backend.pause_training()["ok"] is False
        assert backend.resume_training()["ok"] is False

    def test_reset_after_trained_returns_to_idle(self):
        backend = RecurrenceBackend(_FakeAdapter())
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        assert backend.has_network() is True
        result = backend.reset_training()
        assert result["ok"] is True
        assert backend.has_network() is False
        assert backend.get_status()["fsm_status"] == "idle"

    def test_reset_during_fit_rejected(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        try:
            backend.start_training(generator="equities_seq")
            assert _wait_until(backend.is_training_active)
            assert backend.reset_training()["ok"] is False
        finally:
            gate.set()
        assert _wait_until(lambda: not backend.is_training_active())


@pytest.mark.unit
class TestMetricsAndDataAccessors:
    def _trained(self):
        backend = RecurrenceBackend(_FakeAdapter())
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        return backend

    def test_get_metrics_carries_regression_set(self):
        metrics = self._trained().get_metrics()
        assert metrics["r2"] == pytest.approx(0.96)
        assert "accuracy" not in metrics  # regression-generic
        assert metrics["loss"] == pytest.approx(0.02)
        assert metrics["epoch"] == 1

    def test_get_metrics_empty_before_fit(self):
        assert RecurrenceBackend(_FakeAdapter()).get_metrics() == {}

    def test_metrics_history_single_point(self):
        history = self._trained().get_metrics_history()
        assert len(history) == 1
        assert history[0]["r2"] == pytest.approx(0.96)

    def test_metrics_history_empty_before_fit(self):
        assert RecurrenceBackend(_FakeAdapter()).get_metrics_history() == []

    def test_cascade_surface_is_stubbed(self):
        backend = self._trained()
        assert backend.get_network_topology() is None
        assert backend.get_raw_topology() is None
        assert backend.get_decision_boundary() is None

    def test_get_dataset_maps_descriptor(self):
        dataset = self._trained().get_dataset()
        assert dataset["num_samples"] == 200
        assert dataset["num_features"] == 5
        assert dataset["dataset_name"] == "equities_seq"

    def test_get_dataset_none_before_fit(self):
        assert RecurrenceBackend(_FakeAdapter()).get_dataset() is None


@pytest.mark.unit
class TestApplyParams:
    def test_apply_params_staged_into_next_fit(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        applied = backend.apply_params(d=12, theta=2.0, ridge=0.5, junk="ignored")
        assert applied["ok"] is True
        assert applied["data"] == {"d": 12, "theta": 2.0, "ridge": 0.5}
        backend.start_training(generator="equities_seq")
        assert _wait_until(lambda: not backend.is_training_active())
        call = adapter.calls[0]
        assert call["d"] == 12 and call["theta"] == 2.0 and call["ridge"] == 0.5

    def test_start_training_kwargs_override_staged(self):
        adapter = _FakeAdapter()
        backend = RecurrenceBackend(adapter)
        backend.apply_params(d=12)
        backend.start_training(generator="equities_seq", d=8)  # explicit wins
        assert _wait_until(lambda: not backend.is_training_active())
        assert adapter.calls[0]["d"] == 8


@pytest.mark.unit
class TestLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_returns_true(self):
        assert await RecurrenceBackend(_FakeAdapter()).initialize() is True

    @pytest.mark.asyncio
    async def test_shutdown_joins_inflight_fit(self):
        gate = threading.Event()
        backend = RecurrenceBackend(_FakeAdapter(gate=gate))
        backend.start_training(generator="equities_seq")
        assert _wait_until(backend.is_training_active)
        gate.set()  # let the fit finish so shutdown's join returns promptly
        await backend.shutdown()
        assert backend.is_training_active() is False
