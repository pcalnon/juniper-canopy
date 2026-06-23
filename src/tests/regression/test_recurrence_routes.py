#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_routes.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-23
# Last Modified: 2026-06-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1-iii-a route-correctness + dataset-ref plumbing regression
#                tests: a recurrence (one-shot) backend must not be mis-bucketed
#                by main.py's backend_type branches, and the training trigger
#                must forward a dataset ref + hyperparameters for recurrence.
#####################################################################
"""Regression tests for the A1-iii-a recurrence route fixes (juniper-canopy #368).

Exercises `main.py` with the global `backend` swapped to a `RecurrenceBackend` (backed by a
fake adapter — no network). Guards: no fabricated demo snapshots / workers for recurrence;
topology + decision-boundary 503 cleanly; and `/api/train/start` (+ the `_recurrence_start_kwargs`
helper shared with `/ws/control`) forwards the dataset ref + `d/theta/ridge` for recurrence while
leaving the cascor/demo call path unchanged.
"""

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import main
from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceTrainResult


class _FakeAdapter:
    """Stand-in for RecurrenceServiceAdapter that records train() calls (no network)."""

    def __init__(self):
        self.service_url = "http://rec.test:8210"
        self.calls = []

    def train(self, **kwargs):
        self.calls.append(kwargs)
        return RecurrenceTrainResult(
            final_metrics={"r2": 0.9, "mse": 0.02, "loss": 0.02},
            n_epochs=1,
            stopped_reason="fit_complete",
            dataset={"name": "equities_seq", "n_windows": 10, "n_features": 3, "output_dim": 1},
        )


def _wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


@pytest.fixture(scope="module")
def client():
    """One app + lifespan for the module (lifespan seeds the default demo backend)."""
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def recurrence_backend(monkeypatch):
    """Swap the module-global backend to a RecurrenceBackend for one test (auto-restored)."""
    rb = RecurrenceBackend(_FakeAdapter())
    monkeypatch.setattr(main, "backend", rb)
    return rb


# --------------------------------------------------------------------------- helper unit


@pytest.mark.regression
@pytest.mark.unit
class TestRecurrenceStartKwargs:
    """The dataset-ref/hyperparam extractor shared by the REST + WS start paths."""

    def test_empty_payload_returns_empty(self):
        assert main._recurrence_start_kwargs(None) == {}
        assert main._recurrence_start_kwargs({}) == {}

    def test_extracts_dataset_ref_and_hyperparams(self):
        kwargs = main._recurrence_start_kwargs({"dataset": {"generator": "equities_seq", "params": {"n": 5}, "split": "full"}, "d": 8, "theta": 1.5, "ridge": 0.1})
        assert kwargs == {"generator": "equities_seq", "params": {"n": 5}, "split": "full", "d": 8, "theta": 1.5, "ridge": 0.1}

    def test_omits_absent_keys(self):
        kwargs = main._recurrence_start_kwargs({"dataset": {"name": "ds-1"}})
        assert kwargs == {"name": "ds-1"}
        assert "d" not in kwargs and "generator" not in kwargs


# --------------------------------------------------------------------------- route fixes


@pytest.mark.regression
@pytest.mark.unit
class TestRecurrenceRouteCorrectness:
    """A recurrence backend must not fall into demo/cascor-only route branches."""

    def test_snapshots_no_fabricated_demo_mock(self, client, recurrence_backend):
        resp = client.get("/api/v1/snapshots")
        assert resp.status_code == 200
        # The bug: `!= "service"` made recurrence serve simulated demo snapshots.
        assert resp.json().get("message") != "Demo mode: showing simulated snapshots"

    def test_train_status_exposes_one_shot_execution(self, client, recurrence_backend):
        # A1-iii-b1: /api/train/status carries the execution paradigm that drives UI suppression.
        resp = client.get("/api/train/status")
        assert resp.status_code == 200
        assert resp.json()["execution"] == "one_shot"

    def test_workers_stats_empty_for_recurrence(self, client, recurrence_backend):
        resp = client.get("/api/v1/workers/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0  # not the synthetic 2-worker demo fixture
        assert data["average_health_score"] == 0

    def test_workers_list_empty_for_recurrence(self, client, recurrence_backend):
        resp = client.get("/api/v1/workers/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["workers"] == [] and data["count"] == 0

    def test_topology_503_for_recurrence(self, client, recurrence_backend):
        # LMU has no growing topology → get_network_topology() is None → clean 503, not a crash.
        assert client.get("/api/topology").status_code == 503

    def test_decision_boundary_503_for_recurrence(self, client, recurrence_backend):
        # Regression is not a 2-D classification boundary → None → clean 503.
        assert client.get("/api/decision_boundary").status_code == 503


# --------------------------------------------------------------------------- dataset-ref plumbing


@pytest.mark.regression
@pytest.mark.unit
class TestTrainStartDatasetRef:
    """`/api/train/start` forwards a dataset ref for recurrence; unchanged for others."""

    def test_forwards_dataset_ref_and_hyperparams(self, client, recurrence_backend):
        resp = client.post(
            "/api/train/start",
            json={"dataset": {"generator": "equities_seq", "split": "train"}, "d": 8, "theta": 1.5},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # start_training backgrounds the fit; wait for the worker thread to call the adapter.
        assert _wait_until(lambda: not recurrence_backend.is_training_active())
        call = recurrence_backend._adapter.calls[0]
        assert call["generator"] == "equities_seq"
        assert call["split"] == "train"
        assert call["d"] == 8 and call["theta"] == 1.5

    def test_no_body_still_works_for_recurrence(self, client, recurrence_backend):
        # Backward-compat: a bare start (no body) must fail closed in the BACKEND
        # ("no dataset reference"), not at the route — the route accepts the empty body.
        resp = client.post("/api/train/start")
        assert resp.status_code == 200
        assert resp.json()["ok"] is False  # backend rejects: no dataset ref

    def test_body_ignored_for_non_recurrence(self, client, monkeypatch):
        # cascor/demo must keep the bare reset-only call — extra kwargs would break them.
        fake = MagicMock()
        fake.backend_type = "service"
        fake.start_training.return_value = {"ok": True}
        monkeypatch.setattr(main, "backend", fake)
        resp = client.post("/api/train/start?reset=true", json={"dataset": {"generator": "g"}, "d": 8})
        assert resp.status_code == 200
        fake.start_training.assert_called_once_with(reset=True)
