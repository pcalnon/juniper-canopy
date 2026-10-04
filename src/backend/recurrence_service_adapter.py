#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Generic REST adapter for the juniper-recurrence (LMU) model service
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     recurrence_service_adapter.py
# File Path:     JuniperCanopy/juniper_canopy/src/backend/
#
# Date Created:  2026-06-22
# Last Modified: 2026-10-04
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     A1-i of the model-selection A1 enabler (design-of-record: juniper-ml
#     notes/JUNIPER_CANOPY_MODEL_SELECTION_A1_ENABLER_SCOPE_2026-06-18.md, decision D3).
#
#     Thin SYNCHRONOUS REST client for the juniper-recurrence model service. The
#     recurrence service exposes a one-shot fit: ``POST /v1/train`` BLOCKS until the LMU
#     is fitted (a juniper-data fetch + a single ridge/lstsq solve — there are no epochs
#     to stream), and ``GET /v1/training/status`` returns the terminal state (idle |
#     trained) instantly. There is no background job and no WebSocket, so — unlike the
#     cascor adapter — this adapter needs neither an async event loop nor a streaming
#     relay. A plain ``httpx.Client`` per call is the honest, simplest fit; the backend
#     wrapper (A1-ii) backgrounds the blocking ``train`` on a worker thread so the Dash
#     callback returns immediately, then polls a binary in-progress -> trained status.
#
#     This module is the wire only: it speaks the recurrence REST contract, sends the
#     outbound ``X-API-Key`` (the service runs ``SecurityMiddleware``; a missing key
#     401s — loud by design), applies a generous read-timeout to the blocking train, and
#     maps transport / HTTP failures onto a small typed exception hierarchy so the UI
#     one-shot path (D1-A) can surface 409 / timeout / unavailable distinctly. Routing
#     this adapter into ``create_backend`` and the ``BackendProtocol`` wrapper are A1-ii.
#
#####################################################################################################################################################################################################
# Notes:
#     - Regression-generic: recurrence metrics are the regression set (mse / rmse / mae /
#       r2 / loss) — never an ``accuracy`` key. Result objects carry the raw metric dict.
#     - Scope (A1-i, per the ratified slice cadence): ``train`` + ``training_status``
#       only. ``/v1/predict`` and ``/v1/crossval`` are deferred (enabler-doc OQ-2).
#     - A fresh ``httpx.Client`` is built per request (no pooled client held across the
#       adapter's lifetime) so the adapter has no teardown obligation — appropriate for an
#       occasional, blocking one-shot call rather than a hot path. Tests inject an
#       ``httpx.MockTransport`` via the ``transport`` argument (no network, no extra dep).
#
#####################################################################################################################################################################################################
# References:
#     - juniper-recurrence routers/training.py (POST /v1/train, GET /v1/training/status)
#       and schemas.py (TrainRequest / TrainResponse / StatusResponse / DatasetRef).
#     - Outbound X-API-Key pattern mirrors Settings.juniper_data_api_key (settings.py).
#     - Tracks canopy issue #368 (model selection); enabler scope §3.3 / §4 (D3).
#
#####################################################################################################################################################################################################
# TODO :
#     - A1-ii: route ``recurrence``-provider models here via ``create_backend`` + a
#       ``BackendProtocol`` wrapper that backgrounds the blocking train.
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
"""Synchronous REST adapter for the juniper-recurrence model service (A1-i, D3).

Speaks the recurrence one-shot-fit contract over ``httpx`` (no WebSocket): a blocking
``POST /v1/train`` and the instant ``GET /v1/training/status``. See the module header for
the design rationale (why synchronous, why per-request client) and the enabler design-of-
record for the full A1 program.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional, cast

import httpx

logger = logging.getLogger("juniper_canopy.backend.recurrence")

__all__ = [
    "RecurrenceServiceAdapter",
    "RecurrenceTrainResult",
    "RecurrenceStatus",
    "RecurrenceServiceError",
    "RecurrenceTrainInProgressError",
    "RecurrenceServiceAuthError",
    "RecurrenceServiceTimeoutError",
    "RecurrenceServiceUnavailableError",
]

# ``POST /v1/train`` blocks through a juniper-data fetch + an lstsq solve, so the read
# phase must be generous; the connect phase stays short to fail fast on an unreachable
# service. Both are overridable per-instance. ``GET /v1/training/status`` is an in-memory
# read (instant) so it uses a short timeout.
_DEFAULT_TRAIN_READ_TIMEOUT = 300.0
_DEFAULT_CONNECT_TIMEOUT = 10.0
_DEFAULT_STATUS_TIMEOUT = 10.0

# The most a service-supplied ``detail`` may add to an error message (W0.5 / F-C1). The message reaches canopy's log,
# ``completion_reason`` on ``/api/status`` and the status bar, so a long pydantic error list or an echoed payload must
# not grow it without limit.
_DETAIL_MAX_CHARS = 300


class RecurrenceServiceError(RuntimeError):
    """Base error for any failed juniper-recurrence service interaction.

    ``status_code`` / ``body`` carry the HTTP detail when the failure is a non-2xx
    response (they are ``None`` for transport-level failures — timeout / unreachable).
    All three values are passed positionally to ``super().__init__`` so the exception
    round-trips through ``pickle`` / ``copy.copy`` (rebuilt from ``self.args``); ``__str__``
    keeps the human message clean (just the first arg, not the whole tuple).
    """

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None) -> None:
        super().__init__(message, status_code, body)

    @property
    def status_code(self) -> Optional[int]:
        return cast(Optional[int], self.args[1])

    @property
    def body(self) -> Optional[str]:
        return cast(Optional[str], self.args[2])

    def __str__(self) -> str:
        return str(self.args[0])


class RecurrenceTrainInProgressError(RecurrenceServiceError):
    """A ``/v1/train`` run is already in progress (HTTP 409 — the service's train_lock)."""


class RecurrenceServiceAuthError(RecurrenceServiceError):
    """The service rejected the request for auth reasons (HTTP 401 / 403).

    Almost always a missing or wrong outbound ``X-API-Key`` — see ``recurrence_api_key``.
    """


class RecurrenceServiceTimeoutError(RecurrenceServiceError):
    """The request exceeded its timeout (the blocking fit ran too long, or a network stall)."""


class RecurrenceServiceUnavailableError(RecurrenceServiceError):
    """The service could not be reached (connection refused / DNS / network error)."""


@dataclass(frozen=True)
class RecurrenceTrainResult:
    """Parsed ``POST /v1/train`` response.

    ``final_metrics`` is the regression metric set (mse / rmse / mae / r2 / loss); LMU is
    a one-shot fit so ``n_epochs`` is nominal (typically 1) and ``stopped_reason`` may be
    ``None``. ``dataset`` is the service's ``DatasetDescriptor`` as a raw dict.
    """

    final_metrics: dict[str, float]
    n_epochs: int
    stopped_reason: Optional[str]
    dataset: dict[str, Any]


@dataclass(frozen=True)
class RecurrenceStatus:
    """Parsed ``GET /v1/training/status`` response (terminal state, never per-epoch).

    ``state`` is ``"idle"`` (no run yet) or ``"trained"``. ``final_metrics`` /
    ``stopped_reason`` describe the last completed run (``None`` when idle). ``events`` is
    the ordered training-event buffer recorded during the (already-finished) run.
    """

    state: str
    final_metrics: Optional[dict[str, float]]
    stopped_reason: Optional[str]
    events: list[dict[str, Any]] = field(default_factory=list)


def _validation_error_text(item: Any) -> str:
    """One FastAPI / pydantic validation error as ``loc -> msg`` (``body.dataset.generator -> Field required``).

    Only ``loc`` and ``msg`` are rendered. ``input`` -- the offending value, echoed back verbatim -- is deliberately left
    out: what an operator needs is *which field* and *which rule*, and an echo of the request has no place in a status
    line. An item without a ``msg`` falls back to ``str()``.
    """
    if isinstance(item, Mapping) and item.get("msg") is not None:
        loc = item.get("loc")
        if isinstance(loc, (list, tuple)) and loc:
            return f"{'.'.join(str(part) for part in loc)} -> {item['msg']}"
        if isinstance(loc, str) and loc:
            return f"{loc} -> {item['msg']}"
        return str(item["msg"])
    return str(item)


def _service_detail(response: httpx.Response) -> Optional[str]:
    """Render the service's ``{"detail": ...}`` error body as one bounded line (W0.5 / F-C1), else ``None``.

    The recurrence service answers a refused request the FastAPI way: an ``HTTPException`` gives ``{"detail": "<text>"}``
    (its dataset validator says ``invalid dataset: X_train has non-finite values (NaN/Inf)``), and a request that fails
    validation gives ``{"detail": [{"loc": [...], "msg": "...", ...}, ...]}``. That text is *why* the request was
    refused, and canopy used to keep it only as ``body=`` on the exception, which nothing read.

    A string is used as is; a list becomes ``loc -> msg`` pairs joined by ``; ``; anything else is ``str()``-ed.
    Whitespace is collapsed and the result is bounded to ``_DETAIL_MAX_CHARS``, ending in an ellipsis when cut.
    ``None`` -- leave the message as it was -- for a body that is not JSON, not an object, or has no usable ``detail``.

    It never raises. The detail only decorates the message, so nothing a reply holds may change which typed error
    ``_parse`` raises -- including a body nested deeply enough that the JSON decoder raises ``RecursionError``, which is
    not a ``ValueError``.
    """
    try:
        return _render_detail(response.json())
    except Exception:  # noqa: BLE001 -- a describer must not raise: the typed error stands whatever the body holds
        return None


def _render_detail(payload: Any) -> Optional[str]:
    """The ``detail`` of a decoded error body as one bounded line, or ``None`` when there is none to show."""
    if not isinstance(payload, dict):
        return None
    detail = payload.get("detail")
    if detail is None:
        return None
    if isinstance(detail, str):
        text = detail
    elif isinstance(detail, list):
        text = "; ".join(_validation_error_text(item) for item in detail)
    else:
        text = str(detail)
    collapsed = " ".join(text.split())
    if not collapsed:
        return None
    if len(collapsed) > _DETAIL_MAX_CHARS:
        return collapsed[: _DETAIL_MAX_CHARS - 1].rstrip() + "…"
    return collapsed


class RecurrenceServiceAdapter:
    """Thin synchronous REST client for the juniper-recurrence model service.

    Args:
        service_url: Base URL of the recurrence service (e.g.
            ``http://juniper-recurrence:8210``). Required; a trailing slash is stripped.
        api_key: Outbound key sent as ``X-API-Key`` on every request. ``None`` omits the
            header — appropriate only against an unsecured service; a secured service
            then 401s (raised as :class:`RecurrenceServiceAuthError`).
        train_read_timeout: Read-phase timeout (seconds) for the blocking ``/v1/train``.
        connect_timeout: Connect-phase timeout (seconds) for every request.
        status_timeout: Total timeout (seconds) for the instant ``/v1/training/status``.
        transport: Optional ``httpx`` transport — tests inject an ``httpx.MockTransport``;
            production leaves it ``None`` (httpx builds its default transport).
    """

    def __init__(
        self,
        service_url: str,
        api_key: Optional[str] = None,
        *,
        train_read_timeout: float = _DEFAULT_TRAIN_READ_TIMEOUT,
        connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
        status_timeout: float = _DEFAULT_STATUS_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not service_url:
            raise ValueError("RecurrenceServiceAdapter requires a non-empty service_url")
        self._base_url = service_url.rstrip("/")
        self._api_key = api_key or None
        self._train_timeout = httpx.Timeout(train_read_timeout, connect=connect_timeout)
        self._status_timeout = httpx.Timeout(status_timeout, connect=connect_timeout)
        self._transport = transport
        logger.debug("RecurrenceServiceAdapter initialised for %s (api_key=%s)", self._base_url, bool(self._api_key))

    @property
    def service_url(self) -> str:
        """The normalised base URL (trailing slash stripped)."""
        return self._base_url

    # ------------------------------------------------------------------ public API

    def train(
        self,
        *,
        dataset_id: Optional[str] = None,
        name: Optional[str] = None,
        generator: Optional[str] = None,
        params: Optional[Mapping[str, Any]] = None,
        split: str = "train",
        d: Optional[int] = None,
        theta: Optional[float] = None,
        ridge: Optional[float] = None,
    ) -> RecurrenceTrainResult:
        """Synchronously fit the LMU on a dataset split via ``POST /v1/train``.

        The dataset is referenced (not piped) — the recurrence service fetches the arrays
        from juniper-data itself. Resolution precedence mirrors the service's
        ``DatasetRef``: ``dataset_id`` -> ``name`` -> ``generator`` + ``params``; at least
        one MUST be supplied (validated client-side before the HTTP call). Unset
        hyperparameters fall back to the service defaults.

        Raises:
            ValueError: no dataset reference supplied.
            RecurrenceTrainInProgressError: a run is already in progress (409).
            RecurrenceServiceAuthError: rejected for auth (401 / 403).
            RecurrenceServiceTimeoutError: the blocking fit exceeded the read timeout.
            RecurrenceServiceUnavailableError: the service was unreachable.
            RecurrenceServiceError: any other non-2xx response.
        """
        if not (dataset_id or name or generator):
            raise ValueError("dataset ref requires one of: dataset_id, name, generator")

        dataset_ref: dict[str, Any] = {"split": split}
        if dataset_id is not None:
            dataset_ref["dataset_id"] = dataset_id
        if name is not None:
            dataset_ref["name"] = name
        if generator is not None:
            dataset_ref["generator"] = generator
        if params is not None:
            dataset_ref["params"] = dict(params)

        body: dict[str, Any] = {"dataset": dataset_ref}
        if d is not None:
            body["d"] = d
        if theta is not None:
            body["theta"] = theta
        if ridge is not None:
            body["ridge"] = ridge

        data = self._call("POST", "/v1/train", self._train_timeout, json_body=body)
        return RecurrenceTrainResult(
            final_metrics=dict(data.get("final_metrics") or {}),
            n_epochs=int(data.get("n_epochs", 0)),
            stopped_reason=data.get("stopped_reason"),
            dataset=dict(data.get("dataset") or {}),
        )

    def training_status(self) -> RecurrenceStatus:
        """Return the last training status via ``GET /v1/training/status`` (instant).

        This is terminal state (idle | trained) plus the recorded event buffer — there is
        nothing to poll *during* a fit (the fit blocks ``/v1/train``). The backend wrapper
        (A1-ii) uses this to flip a binary in-progress -> trained after the backgrounded
        train completes.
        """
        data = self._call("GET", "/v1/training/status", self._status_timeout)
        return RecurrenceStatus(
            state=str(data.get("state", "idle")),
            final_metrics=data.get("final_metrics"),
            stopped_reason=data.get("stopped_reason"),
            events=list(data.get("events") or []),
        )

    # ------------------------------------------------------------------ HTTP plumbing

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    def _call(self, method: str, path: str, timeout: httpx.Timeout, *, json_body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Issue one request and map transport / HTTP failures onto the typed hierarchy.

        Named ``_call`` (deliberately NOT ``_request`` / ``_get`` / ``_post``): the static
        guard ``tests/unit/backend/test_cascor_service_adapter_v1_prefix_regression.py``
        flags any ``_request``-family call under ``src/backend/`` that passes a
        ``/v1/``-prefixed path — a convention specific to ``JuniperCascorClient`` (whose
        ``api_url`` already embeds ``/v1``, so cascor paths must omit it). This adapter is
        raw ``httpx`` against a plain ``base_url``, and the recurrence routes genuinely are
        ``/v1/...`` (the service's own tests POST ``/v1/train``), so the prefix is correct
        here and the helper must sit outside that guarded name-set.
        """
        try:
            with httpx.Client(base_url=self._base_url, headers=self._headers(), timeout=timeout, transport=self._transport) as client:
                response = client.request(method, path, json=json_body)
        except httpx.TimeoutException as exc:
            raise RecurrenceServiceTimeoutError(f"recurrence service timed out on {method} {path}: {exc}") from exc
        except httpx.RequestError as exc:
            raise RecurrenceServiceUnavailableError(f"recurrence service unreachable on {method} {path}: {exc}") from exc
        return self._parse(response, method, path)

    @staticmethod
    def _parse(response: httpx.Response, method: str, path: str) -> dict[str, Any]:
        """Raise the appropriate typed error for a non-2xx response, else return the JSON body.

        A 4xx error message ends with the service's own ``detail`` (``…: <detail>``) when the body carries one (W0.5 /
        F-C1): it is the only place the service says *why* it refused the request, and the message is what reaches the
        log, ``completion_reason`` and the status bar. ``body`` still holds the raw response text, unchanged.

        A 5xx detail is NOT appended, deliberately. A 4xx is the service's judgement of THIS request (validation,
        conflict, auth, not-found); a 5xx says the service itself failed, and on this service its detail relays its own
        upstream's exception text: ``map_data_error`` (juniper-recurrence ``routers/_common.py``) answers a juniper-data
        client failure with ``502 f"data fetch failed: {exc}"``, and juniper-data-client 0.5.0 words a refused header
        as ``Request failed: … in header value: ' <key>'``. A padded juniper-data key on the service would therefore
        reach ``completion_reason`` -- which an anonymous caller can read -- verbatim. That is transport text one hop
        removed, which is what ``outbound_errors`` keeps from callers (#683).
        """
        code = response.status_code
        detail = _service_detail(response) if httpx.codes.is_client_error(code) else None
        suffix = f": {detail}" if detail else ""
        if code == httpx.codes.CONFLICT:  # 409
            raise RecurrenceTrainInProgressError(f"recurrence training already in progress ({method} {path}){suffix}", status_code=code, body=response.text)
        if code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):  # 401 / 403
            raise RecurrenceServiceAuthError(f"recurrence service rejected the request ({code} on {method} {path}) — check recurrence_api_key{suffix}", status_code=code, body=response.text)
        if code >= httpx.codes.BAD_REQUEST:  # any other 4xx / 5xx
            raise RecurrenceServiceError(f"recurrence service error {code} on {method} {path}{suffix}", status_code=code, body=response.text)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RecurrenceServiceError(f"recurrence service returned a non-JSON body on {method} {path}", status_code=code, body=response.text) from exc
        if not isinstance(payload, dict):
            raise RecurrenceServiceError(f"recurrence service returned a non-object JSON body on {method} {path}", status_code=code, body=response.text)
        return payload
