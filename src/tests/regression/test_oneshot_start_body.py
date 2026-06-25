#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_oneshot_start_body.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-24
# Last Modified: 2026-06-24
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1-iv-3c regression tests: the one-shot (recurrence) Start
#                button forwards a dataset-ref body so the LMU fit is trainable
#                from the dashboard, with juniper-data params sourced from the
#                registry's seeded default_params (single source of truth).
#####################################################################
"""Regression tests for the A1-iv-3c one-shot Start dataset-ref body (juniper-canopy #368).

iv-3c is the last A1a sub-slice: it makes the recurrence (one-shot / LMU) model trainable from
the dashboard. The Start button must forward a dataset-ref body ``{"dataset": {generator,
params}}`` so ``RecurrenceBackend.start_training`` has a generator to fit (else it bails with
"no dataset reference"). The body is resolved in ONE place
(``DashboardManager._resolve_oneshot_start_body_handler``) from the model-class flag + the
gated dataset dropdown, and its juniper-data params come from the registry's seeded
``DatasetTypeSpec.default_params``. BOTH training-button transports forward it; a live
(cascor/demo) model sends no body so its bare start POST is unchanged.

Coverage:
  * the resolution handler — one_shot vs live, generator+params vs generator-only, copy semantics;
  * the server-side REST handler — attaches ``json`` only for a one-shot Start, never otherwise;
  * end-to-end — the resolved body round-trips through ``/api/train/start`` to ``adapter.train``.

The Phase D clientside-JS half of the dual transport is asserted (string contract) in
``tests/unit/test_phase_d_button_clientside.py``.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import frontend.dashboard_manager as dm_module
import main
from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceTrainResult
from frontend.dashboard_manager import DashboardManager
from model_registry import dataset_default_params

_EQUITIES_PARAMS = {"max_symbols": 5, "regression_target": "return"}


# --------------------------------------------------------------------------- resolution handler


@pytest.mark.regression
@pytest.mark.unit
class TestResolveOneshotStartBody:
    """The single resolution point both transports read (``oneshot-start-params-store``)."""

    def test_one_shot_equities_builds_generator_plus_registry_params(self):
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        assert body == {"dataset": {"generator": "equities_seq", "params": _EQUITIES_PARAMS}}

    def test_live_model_returns_none(self):
        # cascor / demo are "live" — their start POST stays bare (route sees body=None).
        assert DashboardManager._resolve_oneshot_start_body_handler("live", "spirals") is None
        assert DashboardManager._resolve_oneshot_start_body_handler(None, "equities_seq") is None

    def test_one_shot_without_generator_returns_none(self):
        # No dataset selected yet → no body (the backend would otherwise reject the fit).
        assert DashboardManager._resolve_oneshot_start_body_handler("one_shot", None) is None
        assert DashboardManager._resolve_oneshot_start_body_handler("one_shot", "") is None

    def test_one_shot_generator_without_default_params_omits_params_key(self):
        # A generator with no seeded params yields a generator-only ref (no empty "params" key).
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "spirals")
        assert body == {"dataset": {"generator": "spirals"}}
        assert "params" not in body["dataset"]

    def test_resolved_params_are_decoupled_from_registry(self):
        # Mutating the produced body must never bleed into the registry seed (copy semantics).
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        body["dataset"]["params"]["max_symbols"] = 999
        assert dataset_default_params("equities_seq")["max_symbols"] == 5


# --------------------------------------------------------------------------- server-side transport


def _make_dashboard() -> DashboardManager:
    """A demo-mode DashboardManager (conftest forces JUNIPER_CANOPY_DEMO_MODE=1).

    Constructing it also validates the new resolution callback + store register cleanly
    (no allow_duplicate conflict) — a free up-front guard.
    """
    return DashboardManager({})


def _drive_button(dm, monkeypatch, trigger, *, oneshot_start_body=None):
    """Invoke the server-side handler for ``trigger`` and return the patched ``requests.post`` mock."""
    fake_ctx = MagicMock()
    fake_ctx.get_triggered_id.return_value = trigger
    monkeypatch.setattr(dm_module, "get_callback_context", lambda: fake_ctx, raising=True)

    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    post_mock = MagicMock(return_value=fake_response)
    monkeypatch.setattr(dm_module.requests, "post", post_mock, raising=True)

    states = {cmd: {"disabled": False, "loading": False, "timestamp": 0} for cmd in ("start", "pause", "stop", "resume", "reset")}
    dm._handle_training_buttons_handler(
        start_clicks=1,
        pause_clicks=1,
        stop_clicks=1,
        resume_clicks=1,
        reset_clicks=1,
        last_click={"button": None, "timestamp": 0},
        button_states=states,
        oneshot_start_body=oneshot_start_body,
    )
    return post_mock


@pytest.mark.regression
@pytest.mark.unit
class TestServerSideHandlerForwardsBody:
    """``_handle_training_buttons_handler`` (the default, non-Phase-D transport)."""

    def test_start_forwards_json_body_for_one_shot(self, monkeypatch):
        dm = _make_dashboard()
        body = {"dataset": {"generator": "equities_seq", "params": _EQUITIES_PARAMS}}
        post_mock = _drive_button(dm, monkeypatch, "start-button", oneshot_start_body=body)
        post_mock.assert_called_once()
        assert post_mock.call_args.kwargs.get("json") == body
        assert "/api/train/start" in post_mock.call_args[0][0]

    def test_start_sends_no_body_when_none(self, monkeypatch):
        # Live (cascor/demo) Start: store resolved to None → bare POST, exactly as before iv-3c.
        dm = _make_dashboard()
        post_mock = _drive_button(dm, monkeypatch, "start-button", oneshot_start_body=None)
        post_mock.assert_called_once()
        assert "json" not in post_mock.call_args.kwargs

    def test_non_start_command_never_sends_body(self, monkeypatch):
        # Even with a body resolved, only the start command carries it (reset/stop/... stay bare).
        dm = _make_dashboard()
        body = {"dataset": {"generator": "equities_seq", "params": _EQUITIES_PARAMS}}
        post_mock = _drive_button(dm, monkeypatch, "reset-button", oneshot_start_body=body)
        post_mock.assert_called_once()
        assert "json" not in post_mock.call_args.kwargs
        assert "/api/train/reset" in post_mock.call_args[0][0]


# --------------------------------------------------------------------------- end-to-end tie-through


class _FakeAdapter:
    """Records ``train()`` calls so the end-to-end test can assert the forwarded dataset ref."""

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


@pytest.mark.regression
class TestOneshotBodyReachesAdapterEndToEnd:
    """The body the dashboard resolves must round-trip to the recurrence adapter's ``train``."""

    def test_resolved_body_round_trips_to_adapter(self, client, recurrence_backend):
        # The exact body the sidebar produces for a one-shot equities fit...
        body = DashboardManager._resolve_oneshot_start_body_handler("one_shot", "equities_seq")
        resp = client.post("/api/train/start", json=body)
        assert resp.status_code == 200
        # ...is fetched + fit by the recurrence service via the dataset ref (backgrounded thread).
        assert _wait_until(lambda: bool(recurrence_backend._adapter.calls))
        call = recurrence_backend._adapter.calls[0]
        assert call["generator"] == "equities_seq"
        assert call["params"] == _EQUITIES_PARAMS
        # split defaults at the adapter; never an accuracy-style synthetic param.
        assert "n_samples" not in call.get("params", {}) and "noise" not in call.get("params", {})
