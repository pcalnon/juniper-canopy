#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     recurrence_service_fake.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# Last Modified: 2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A fake juniper-recurrence service behind an
#                httpx.MockTransport, shaped after the operation-
#                identity contract of juniper-recurrence#192 (W1.5).
#####################################################################
"""A fake juniper-recurrence service for canopy's adapter, backend and route tests -- no network.

The wire shapes follow juniper-recurrence ``main`` at ``d20a581b`` (juniper-recurrence#192, W1.5 of juniper-ml's
``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md``):

* ``POST /v1/train`` takes an optional ``X-Request-ID``, which the service records verbatim as the operation's
  ``requested_by``. Its 200 ``TrainResponse`` carries the fit's ``operation_id`` (uuid4 hex). A busy 409's ``detail`` is
  an object naming the holder (``BusyDetail``).
* ``GET /v1/training/status`` (``StatusResponse``) reports ``state`` -- ``idle`` | ``training`` | ``restoring`` |
  ``trained`` | ``restored`` | ``failed`` -- with ``operation_id``, ``operation``, ``busy_since``, ``dataset_id``,
  ``requested_by``, ``model_operation_id`` and ``failure``, every key present (``null`` when unset).
* juniper-recurrence 0.5.0, the published contract floor, sends none of the identity fields, answers a busy 409 with a
  bare string, and reports ``idle`` / ``trained`` only: :func:`status_body_0_5_0` and :data:`BUSY_409_0_5_0`.

:class:`FakeRecurrenceService` records the ``X-Request-ID`` each train request sent, and a status body whose
``requested_by`` is :data:`MINE` answers with the id actually sent -- so a test can say "the status describes canopy's
own request" without knowing the id the code under test minted.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Optional, Union

import httpx

from backend.recurrence_service_adapter import RecurrenceServiceAdapter

BASE_URL = "http://recurrence.test:8210"

# Stand-ins for the uuid4-hex ids the service mints (32 lowercase hex characters).
OPERATION_ID = "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
OTHER_OPERATION_ID = "aaaabbbbccccddddeeeeffff00001111"
EARLIER_OPERATION_ID = "1234567890abcdef1234567890abcdef"
BUSY_SINCE = "2026-10-08T17:44:00.123Z"
DATASET_ID = "equities_seq-5d0c1f"

# A status body's ``requested_by`` that stands for "the X-Request-ID canopy's train request sent".
MINE = "<the X-Request-ID canopy sent>"
# Another caller's ``X-Request-ID``: a CLI experiment suite sharing the service (F-CON1).
OTHER_CALLER = "cli-suite-e-h-cell-7"

# What ``GET /v1/training/status`` raises instead of answering, as an item of ``statuses``.
UNREACHABLE = "<unreachable>"

FINAL_METRICS = {"r2": 0.0081, "mse": 0.000214, "rmse": 0.01463, "mae": 0.0101, "loss": 0.000214}

TRAIN_OK = {
    "final_metrics": FINAL_METRICS,
    "metrics_scope": "in_sample",
    "n_epochs": 1,
    "stopped_reason": "converged",
    "dataset": {"dataset_id": DATASET_ID, "name": None, "split": "train", "n_windows": 1346, "lookback": 64, "n_features": 15, "output_dim": 1, "has_target_dt": True, "has_seq_lengths": False},
    "operation_id": OPERATION_ID,
}

# The events a closed-form fit records (juniper-recurrence-model ``LMURegressor.fit``): ``epoch`` counts from 0.
FIT_EVENTS = [
    {"type": "training_start", "seq": 0, "payload": {"n_samples": 1346}},
    {"type": "epoch_end", "seq": 1, "payload": {"epoch": 0, "metrics": FINAL_METRICS}},
    {"type": "training_end", "seq": 2, "payload": {"metrics": FINAL_METRICS}},
]

# juniper-recurrence 0.5.0's busy 409: a bare string detail.
BUSY_409_0_5_0 = {"detail": "a training run is already in progress"}


def status_body(
    state: str,
    *,
    requested_by: Optional[str] = MINE,
    operation: Optional[str] = "train",
    operation_id: Optional[str] = OPERATION_ID,
    model_operation_id: Optional[str] = None,
    busy_since: Optional[str] = None,
    dataset_id: Optional[str] = DATASET_ID,
    failure: Optional[dict[str, Any]] = None,
    final_metrics: Optional[dict[str, float]] = None,
    stopped_reason: Optional[str] = None,
    events: Iterable[dict[str, Any]] = (),
    restored_from: Optional[str] = None,
) -> dict[str, Any]:
    """A juniper-recurrence#192 ``StatusResponse`` body: every key present, ``None`` where unset, as the service sends it."""
    return {
        "state": state,
        "final_metrics": final_metrics,
        "stopped_reason": stopped_reason,
        "events": list(events),
        "restored_from": restored_from,
        "operation_id": operation_id,
        "operation": operation,
        "busy_since": busy_since,
        "dataset_id": dataset_id,
        "requested_by": requested_by,
        "model_operation_id": model_operation_id,
        "failure": failure,
    }


def status_running(**overrides: Any) -> dict[str, Any]:
    """canopy's fit still holding the lock (``training``), an earlier model still loaded."""
    return status_body("training", **{"busy_since": BUSY_SINCE, "model_operation_id": EARLIER_OPERATION_ID, **overrides})


def status_trained(**overrides: Any) -> dict[str, Any]:
    """canopy's fit finished: its metrics and events, and the model it produced (``model_operation_id == operation_id``)."""
    return status_body("trained", **{"model_operation_id": OPERATION_ID, "final_metrics": FINAL_METRICS, "stopped_reason": "converged", "events": FIT_EVENTS, **overrides})


def status_failed(detail: str, status_code: int, **overrides: Any) -> dict[str, Any]:
    """canopy's fit failed: the detail and status its request returned; an earlier model still loaded."""
    return status_body("failed", **{"failure": {"detail": detail, "status_code": status_code}, "model_operation_id": EARLIER_OPERATION_ID, **overrides})


def status_body_0_5_0(state: str = "trained") -> dict[str, Any]:
    """juniper-recurrence 0.5.0's ``StatusResponse``: ``idle`` / ``trained`` and no operation identity at all."""
    if state == "idle":
        return {"state": "idle", "final_metrics": None, "stopped_reason": None, "events": []}
    return {"state": state, "final_metrics": FINAL_METRICS, "stopped_reason": "converged", "events": FIT_EVENTS}


def busy_409(**overrides: Any) -> dict[str, Any]:
    """juniper-recurrence#192's busy 409 body (``BusyResponse``): the holder is another caller's fit."""
    detail = {"message": "a training run is already in progress", "operation_id": OTHER_OPERATION_ID, "operation": "train", "busy_since": BUSY_SINCE, "requested_by": OTHER_CALLER, "dataset_id": DATASET_ID}
    detail.update(overrides)
    return {"detail": detail}


TrainBehaviour = Union[str, httpx.Response, Callable[[httpx.Request], httpx.Response]]


class FakeRecurrenceService:
    """juniper-recurrence's train, status and version routes behind an ``httpx.MockTransport``.

    Args:
        train: what ``POST /v1/train`` does after recording the ``X-Request-ID`` it was sent -- ``"timeout"``
            (``httpx.ReadTimeout``: the request arrived, its reply did not), ``"connect-timeout"``
            (``httpx.ConnectTimeout``: it never arrived), an ``httpx.Response``, or a callable ``request -> Response``.
        statuses: the ``GET /v1/training/status`` bodies, answered in turn; the last one repeats. A body whose
            ``requested_by`` is :data:`MINE` is answered with the id the latest train request sent. :data:`UNREACHABLE`
            raises ``httpx.ConnectError`` instead; an ``httpx.Response`` is answered as is.
        version: ``info.version`` of ``GET /openapi.json``. ``GET /v1/health`` answers ``{"status": "ok"}``, as 0.5.0 does,
            so the version is read the way canopy reads it from the published service.
    """

    def __init__(self, *, train: TrainBehaviour = "ok", statuses: Iterable[Any] = (), version: str = "0.5.0") -> None:
        self._train = train
        self._statuses = list(statuses)
        self._version = version
        self.requests: list[httpx.Request] = []
        self.request_ids: list[Optional[str]] = []

    # ------------------------------------------------------------------ the transport

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def adapter(self, api_key: Optional[str] = None) -> RecurrenceServiceAdapter:
        """A real :class:`RecurrenceServiceAdapter` whose every request this fake answers."""
        return RecurrenceServiceAdapter(BASE_URL, api_key, transport=self.transport)

    def paths(self) -> list[str]:
        return [f"{request.method} {request.url.path}" for request in self.requests]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/v1/train":
            self.request_ids.append(request.headers.get("X-Request-ID"))
            return self._answer_train(request)
        if request.method == "GET" and path == "/v1/training/status":
            return self._answer_status(request)
        if request.method == "GET" and path == "/v1/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.method == "GET" and path == "/openapi.json":
            return httpx.Response(200, json={"openapi": "3.1.0", "info": {"title": "Juniper Recurrence", "version": self._version}, "paths": {}})
        return httpx.Response(404, json={"detail": "Not Found"})

    # ------------------------------------------------------------------ routes

    def _answer_train(self, request: httpx.Request) -> httpx.Response:
        behaviour = self._train
        if behaviour == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if behaviour == "connect-timeout":
            raise httpx.ConnectTimeout("timed out", request=request)
        if behaviour == "ok":
            return httpx.Response(200, json=TRAIN_OK)
        if isinstance(behaviour, httpx.Response):
            return behaviour
        if callable(behaviour):
            return behaviour(request)
        raise AssertionError(f"unknown train behaviour {behaviour!r}")

    def _answer_status(self, request: httpx.Request) -> httpx.Response:
        if not self._statuses:
            raise AssertionError("the fake was asked for a status it was not given")
        item = self._statuses.pop(0) if len(self._statuses) > 1 else self._statuses[0]
        if item == UNREACHABLE:
            raise httpx.ConnectError("connection refused", request=request)
        if isinstance(item, httpx.Response):
            return item
        body = dict(item)
        if body.get("requested_by") == MINE:
            body["requested_by"] = self.request_ids[-1] if self.request_ids else None
        return httpx.Response(200, json=body)
