#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_service_adapter.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-22
# Last Modified: 2026-06-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for RecurrenceServiceAdapter (A1-i, D3) — the
#                synchronous httpx REST client for the juniper-recurrence
#                model service. Mocked end-to-end via httpx.MockTransport;
#                no network, no live service.
#####################################################################
"""Unit tests for ``backend.recurrence_service_adapter`` (A1-i of the model-selection
A1 enabler). Exercises request shaping, the outbound ``X-API-Key`` header, the generous
train timeout, JSON parsing, and the typed error mapping (409 / 401 / 403 / other-HTTP /
timeout / unreachable / non-JSON) — all against an injected ``httpx.MockTransport``.
"""

import json

import httpx
import pytest

from backend.recurrence_service_adapter import (
    RecurrenceServiceAdapter,
    RecurrenceServiceAuthError,
    RecurrenceServiceError,
    RecurrenceServiceTimeoutError,
    RecurrenceServiceUnavailableError,
    RecurrenceStatus,
    RecurrenceTrainInProgressError,
    RecurrenceTrainResult,
)

_BASE = "http://recurrence.test:8210"

# A representative successful ``POST /v1/train`` body (regression metrics — never accuracy).
_TRAIN_OK = {
    "final_metrics": {"r2": 0.97, "mse": 0.012, "rmse": 0.11, "mae": 0.08, "loss": 0.012},
    "n_epochs": 1,
    "stopped_reason": "fit_complete",
    "dataset": {
        "dataset_id": "ds-123",
        "name": "equities_seq",
        "split": "train",
        "n_windows": 256,
        "lookback": 32,
        "n_features": 5,
        "output_dim": 1,
        "has_target_dt": True,
        "has_seq_lengths": True,
    },
}


def _adapter(handler, *, api_key=None, **kwargs):
    """Build an adapter wired to a MockTransport running ``handler``."""
    return RecurrenceServiceAdapter(_BASE, api_key, transport=httpx.MockTransport(handler), **kwargs)


def _responder(payload, status_code=200, sink=None):
    """A MockTransport handler returning ``payload`` as JSON; records requests into ``sink``."""

    def handler(request: httpx.Request) -> httpx.Response:
        if sink is not None:
            sink.append(request)
        return httpx.Response(status_code, json=payload)

    return handler


@pytest.mark.unit
class TestConstruction:
    """Constructor normalisation and validation."""

    def test_empty_service_url_raises(self):
        with pytest.raises(ValueError):
            RecurrenceServiceAdapter("")

    def test_trailing_slash_stripped(self):
        adapter = RecurrenceServiceAdapter("http://recurrence.test:8210/")
        assert adapter.service_url == "http://recurrence.test:8210"

    def test_empty_api_key_sends_no_header(self):
        """An empty-string api_key is treated as None (no X-API-Key header)."""
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink), api_key="")
        adapter.train(generator="equities_seq")
        assert "X-API-Key" not in sink[0].headers


@pytest.mark.unit
class TestTrain:
    """``POST /v1/train`` — request shaping, parsing, and success path."""

    def test_train_success_parses_result(self):
        adapter = _adapter(_responder(_TRAIN_OK))
        result = adapter.train(generator="equities_seq")
        assert isinstance(result, RecurrenceTrainResult)
        assert result.final_metrics["r2"] == pytest.approx(0.97)
        assert "accuracy" not in result.final_metrics  # regression-generic
        assert result.n_epochs == 1
        assert result.stopped_reason == "fit_complete"
        assert result.dataset["name"] == "equities_seq"

    def test_train_request_method_and_path(self):
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink))
        adapter.train(generator="equities_seq")
        assert sink[0].method == "POST"
        assert sink[0].url.path == "/v1/train"

    def test_train_dataset_ref_and_split(self):
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink))
        adapter.train(name="equities_seq", params={"n": 256}, split="full")
        body = json.loads(sink[0].content)
        assert body["dataset"]["name"] == "equities_seq"
        assert body["dataset"]["params"] == {"n": 256}
        assert body["dataset"]["split"] == "full"

    def test_train_omits_unset_hyperparams(self):
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink))
        adapter.train(generator="equities_seq")
        body = json.loads(sink[0].content)
        assert "d" not in body and "theta" not in body and "ridge" not in body

    def test_train_includes_hyperparams_when_given(self):
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink))
        adapter.train(generator="equities_seq", d=8, theta=1.5, ridge=0.1)
        body = json.loads(sink[0].content)
        assert body["d"] == 8 and body["theta"] == 1.5 and body["ridge"] == 0.1

    def test_train_sends_api_key_header(self):
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink), api_key="secret-key")
        adapter.train(generator="equities_seq")
        assert sink[0].headers["X-API-Key"] == "secret-key"

    def test_train_omits_api_key_header_when_none(self):
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink))
        adapter.train(generator="equities_seq")
        assert "X-API-Key" not in sink[0].headers

    def test_train_requires_dataset_ref(self):
        """No dataset reference → local ValueError, before any HTTP call."""
        sink = []
        adapter = _adapter(_responder(_TRAIN_OK, sink=sink))
        with pytest.raises(ValueError):
            adapter.train()
        assert sink == []  # never hit the wire


@pytest.mark.unit
class TestTrainErrorMapping:
    """``POST /v1/train`` — typed error mapping for every failure class."""

    def test_409_maps_to_in_progress(self):
        adapter = _adapter(_responder({"detail": "in progress"}, status_code=409))
        with pytest.raises(RecurrenceTrainInProgressError) as exc:
            adapter.train(generator="equities_seq")
        assert exc.value.status_code == 409

    @pytest.mark.parametrize("code", [401, 403])
    def test_auth_errors_map(self, code):
        adapter = _adapter(_responder({"detail": "nope"}, status_code=code))
        with pytest.raises(RecurrenceServiceAuthError) as exc:
            adapter.train(generator="equities_seq")
        assert exc.value.status_code == code

    @pytest.mark.parametrize("code", [400, 422, 500, 503])
    def test_other_http_errors_map_to_base(self, code):
        adapter = _adapter(_responder({"detail": "boom"}, status_code=code))
        with pytest.raises(RecurrenceServiceError) as exc:
            adapter.train(generator="equities_seq")
        # base error, not one of the more specific subclasses
        assert not isinstance(exc.value, (RecurrenceTrainInProgressError, RecurrenceServiceAuthError))
        assert exc.value.status_code == code

    def test_timeout_maps(self):
        def handler(request):
            raise httpx.ReadTimeout("read timed out", request=request)

        adapter = _adapter(handler)
        with pytest.raises(RecurrenceServiceTimeoutError):
            adapter.train(generator="equities_seq")

    def test_connect_error_maps_to_unavailable(self):
        def handler(request):
            raise httpx.ConnectError("connection refused", request=request)

        adapter = _adapter(handler)
        with pytest.raises(RecurrenceServiceUnavailableError):
            adapter.train(generator="equities_seq")

    def test_non_json_body_maps_to_error(self):
        def handler(request):
            return httpx.Response(200, content=b"<html>not json</html>")

        adapter = _adapter(handler)
        with pytest.raises(RecurrenceServiceError):
            adapter.train(generator="equities_seq")


@pytest.mark.unit
class TestTrainingStatus:
    """``GET /v1/training/status`` — terminal state + event buffer."""

    def test_status_idle(self):
        adapter = _adapter(_responder({"state": "idle", "events": []}))
        status = adapter.training_status()
        assert isinstance(status, RecurrenceStatus)
        assert status.state == "idle"
        assert status.final_metrics is None
        assert status.events == []

    def test_status_trained(self):
        payload = {
            "state": "trained",
            "final_metrics": {"r2": 0.95, "loss": 0.02},
            "stopped_reason": "fit_complete",
            "events": [{"type": "fit_start", "seq": 0, "payload": {}}, {"type": "fit_end", "seq": 1, "payload": {"r2": 0.95}}],
        }
        adapter = _adapter(_responder(payload))
        status = adapter.training_status()
        assert status.state == "trained"
        assert status.final_metrics == {"r2": 0.95, "loss": 0.02}
        assert len(status.events) == 2

    def test_status_request_method_path_and_api_key(self):
        sink = []
        adapter = _adapter(_responder({"state": "idle"}, sink=sink), api_key="k")
        adapter.training_status()
        assert sink[0].method == "GET"
        assert sink[0].url.path == "/v1/training/status"
        assert sink[0].headers["X-API-Key"] == "k"
