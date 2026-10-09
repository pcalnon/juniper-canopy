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
# Last Modified: 2026-10-08
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
#     to stream), and ``GET /v1/training/status`` returns the current or last operation's
#     state instantly: idle | training | trained | restored | failed since juniper-recurrence#192
#     (W1.5), idle | trained on the 0.5.0 contract floor. There is no background job and no WebSocket, so — unlike the
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
#       ``service_version`` (W1.7) reads the version the service reports.
#     - Operation identity (W1.5 / F-C4, F-CON1, F-CON2; juniper-recurrence#192): ``train``
#       sends canopy's ``X-Request-ID`` and reads the ``operation_id`` the service mints;
#       ``train_outcome`` reads ``GET /v1/training/status`` after a train request timed out
#       and says whose operation the status describes; a busy 409 names its holder. canopy
#       calls neither ``/v1/predict`` nor ``POST /v1/model/snapshots``, so it has nowhere to
#       send ``expect_operation_id`` yet; ``RecurrenceTrainResult.operation_id`` is the id to send.
#     - Contract floor: ``RECURRENCE_SERVICE_CONTRACT_FLOOR`` (W1.7 / F-C8). canopy speaks
#       the service's REST contract here over raw httpx and imports no recurrence client
#       package, so no pin in pyproject.toml can carry a floor; the constant and
#       docs/api/API_REFERENCE.md § Recurrence Service Contract carry it instead.
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
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Optional, cast

import httpx

from outbound_errors import outbound_error_text

logger = logging.getLogger("juniper_canopy.backend.recurrence")

__all__ = [
    "MODEL_PRESENT_STATES",
    "OUTCOME_FAILED",
    "OUTCOME_RUNNING",
    "OUTCOME_SUCCEEDED",
    "OUTCOME_UNKNOWN",
    "RECURRENCE_SERVICE_CONTRACT_FLOOR",
    "REQUEST_ID_HEADER",
    "RecurrenceBusyHolder",
    "RecurrenceOperationFailure",
    "RecurrenceServiceAdapter",
    "RecurrenceTrainOutcome",
    "RecurrenceTrainResult",
    "RecurrenceStatus",
    "RecurrenceServiceError",
    "RecurrenceTrainInProgressError",
    "RecurrenceServiceAuthError",
    "RecurrenceServiceRateLimited",
    "RecurrenceServiceTimeoutError",
    "RecurrenceServiceUnavailableError",
    "new_request_id",
]

# The juniper-recurrence release this adapter is written and verified against: its documented contract floor (W1.7 /
# F-C8). canopy reaches the service through this module over raw httpx and imports no juniper-recurrence-client, so a
# package pin in pyproject.toml would constrain nothing canopy runs; this constant and docs/api/API_REFERENCE.md
# § Recurrence Service Contract carry the floor instead. 0.5.0 serves every route and reply shape this module parses
# except the ``restored`` status state, which is newer (on juniper-recurrence main, unreleased as of 2026-10-05, where
# ``__version__`` still reads 0.5.0): it is parsed when present, and a 0.5.0 release simply never sends it.
RECURRENCE_SERVICE_CONTRACT_FLOOR = "0.5.0"

# The ``GET /v1/training/status`` states in which the service holds a model it can predict with (W1.6 / F-C6).
# ``restored`` is a model loaded from a snapshot -- present and predictable, but never fitted by the service process, so
# it reports no ``final_metrics`` / ``stopped_reason`` / ``events``. Anything asking "is there a model?" reads
# :attr:`RecurrenceStatus.model_present`, never ``state == "trained"``.
MODEL_PRESENT_STATES: frozenset[str] = frozenset({"trained", "restored"})

# The variables that set the key canopy sends as ``X-API-Key`` (``Settings.recurrence_api_key``; the ``_FILE`` form is
# read first). A 401 / 403 names them (W1.6 / F-C5): the setting's Python name is not something an operator can set.
_AUTH_REMEDY = "set JUNIPER_CANOPY_RECURRENCE_API_KEY or JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE to a key the service accepts"

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

# The most a 429's ``Retry-After`` value may add to the message (W1.6 / F-C7). juniper-service-core sends delta-seconds;
# an HTTP-date, which RFC 9110 also allows, is 29 characters. Bounded for the reason the detail is.
_RETRY_AFTER_MAX_CHARS = 64

# W1.5 (F-C4 / F-CON2): the header that names canopy's ``POST /v1/train`` request. juniper-recurrence records it verbatim
# as the operation's ``requested_by`` (juniper-recurrence#192), so a caller whose request timed out -- and so never
# received the ``operation_id`` its reply carried -- can still find its own operation in ``GET /v1/training/status``.
# A service that predates #192 ignores the header.
REQUEST_ID_HEADER = "X-Request-ID"

# canopy's request ids name canopy, so whoever reads one -- in the service's status, in a busy 409 another caller gets,
# in the service's log -- can tell whose request it was without asking: ``juniper-canopy-<uuid4 hex>``.
_REQUEST_ID_PREFIX = "juniper-canopy-"

# ``RecurrenceTrainOutcome.state``: what ``GET /v1/training/status`` says became of a train request whose reply never
# arrived (W1.5). The operator-facing ``reason`` of each starts with the plan's label for it -- ``running (upstream)``,
# ``unknown (upstream unreachable)`` and so on -- and ``failed`` reads as the failed request's own error would have.
OUTCOME_RUNNING = "running"
OUTCOME_SUCCEEDED = "succeeded"
OUTCOME_FAILED = "failed"
OUTCOME_UNKNOWN = "unknown"

# What a refused ``POST /v1/train`` can do about a busy service (W1.5 / F-CON1). The service runs one operation at a time
# under one lock, and nothing -- not canopy, not the caller that started it -- can cancel a fit, so the choices are to
# wait it out or to stop sharing the service (juniper-recurrence's README, § One caller per service).
_BUSY_REMEDY = "retry when it ends (a fit cannot be cancelled), or give canopy a service of its own"

# The most one service-supplied field (another caller's ``requested_by``, a ``dataset_id``, a state name ...) may add
# to a message or a reason. ``requested_by`` is whatever ``X-Request-ID`` another caller chose to send; the status and
# the 409 relay it verbatim. A uuid4 hex ``operation_id`` is 32 characters.
_FIELD_MAX_CHARS = 64

# Where in ``GET /v1/training/status``'s ``state`` an operation holds the service's lock right now (W1.5).
_IN_FLIGHT_STATES: frozenset[str] = frozenset({"training", "restoring"})


@dataclass(frozen=True)
class RecurrenceBusyHolder:
    """The operation holding the service when a ``POST /v1/train`` was refused: the busy 409's object ``detail`` (W1.5).

    juniper-recurrence#192 names the holder (F-CON1 was a 409 that said nothing about who held the lock): its
    ``operation_id``, its kind (``operation``: ``train`` or ``restore``), ``busy_since`` (ISO-8601 UTC), the
    ``requested_by`` its request carried as ``X-Request-ID``, and its ``dataset_id`` as far as that has resolved.
    ``message`` is the service's refusal (``a training run is already in progress``, or ``a snapshot restore is in
    progress``). Every other field may be ``None``: the service nulls them when its lock was taken outside the API,
    which only its tests do. Values are kept as sent; :meth:`describe` flattens and bounds them for a message.
    """

    message: str
    operation_id: Optional[str] = None
    operation: Optional[str] = None
    busy_since: Optional[str] = None
    requested_by: Optional[str] = None
    dataset_id: Optional[str] = None

    def describe(self) -> str:
        """The holder on one line: ``<message> (<operation> operation <id> since <time>, requested by <id>, dataset <id>)``.

        Absent fields are left out, and the parentheses with them when nothing is known beyond the message. Each field
        is flattened and bounded (``_FIELD_MAX_CHARS``) and the whole is bounded as any service ``detail`` is
        (``_DETAIL_MAX_CHARS``), so the line fits wherever a 4xx detail fits.
        """
        facts = []
        since = f"since {_bounded_line(self.busy_since, _FIELD_MAX_CHARS)}" if self.busy_since else ""
        if self.operation_id or self.operation:
            kind = _bounded_line(self.operation, _FIELD_MAX_CHARS) if self.operation else "an"
            identity = f" {_bounded_line(self.operation_id, _FIELD_MAX_CHARS)}" if self.operation_id else ""
            facts.append(f"{kind} operation{identity}{f' {since}' if since else ''}")
        elif since:
            facts.append(since)
        if self.requested_by:
            facts.append(f"requested by {_bounded_line(self.requested_by, _FIELD_MAX_CHARS)}")
        if self.dataset_id:
            facts.append(f"dataset {_bounded_line(self.dataset_id, _FIELD_MAX_CHARS)}")
        message = _bounded_line(self.message, _DETAIL_MAX_CHARS) or "the service is busy"
        return _bounded_line(f"{message} ({', '.join(facts)})" if facts else message, _DETAIL_MAX_CHARS)


class RecurrenceServiceError(RuntimeError):
    """Base error for any failed juniper-recurrence service interaction.

    ``status_code`` / ``body`` carry the HTTP detail when the failure is a non-2xx
    response (they are ``None`` for transport-level failures — timeout / unreachable).
    All three values -- and any a subclass appends after them (``extra``; see
    :class:`RecurrenceServiceRateLimited`) -- are passed positionally to ``super().__init__``
    so the exception round-trips through ``pickle`` / ``copy.copy`` (rebuilt from
    ``self.args``); ``__str__`` keeps the human message clean (just the first arg, not the
    whole tuple).
    """

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None, *extra: Any) -> None:
        super().__init__(message, status_code, body, *extra)

    @property
    def status_code(self) -> Optional[int]:
        return cast(Optional[int], self.args[1])

    @property
    def body(self) -> Optional[str]:
        return cast(Optional[str], self.args[2])

    def __str__(self) -> str:
        return str(self.args[0])


class RecurrenceTrainInProgressError(RecurrenceServiceError):
    """A ``/v1/train`` run is already in progress (HTTP 409 — the service's train_lock).

    Since juniper-recurrence#192 (W1.5) the busy 409's ``detail`` is an object naming the operation that holds the
    lock. :attr:`holder` carries it parsed, and the message names the holder and what to do about it (F-CON1). The
    published 0.5.0 still sends the bare string ``a training run is already in progress``: that is appended as any
    4xx ``detail`` is, and :attr:`holder` is ``None``, as it is for any 409 whose detail is not that object.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None, holder: Optional[RecurrenceBusyHolder] = None) -> None:
        # A fourth positional value, so the exception still rebuilds from ``self.args`` (pickle / copy) as the base's does.
        super().__init__(message, status_code, body, holder)

    @property
    def holder(self) -> Optional[RecurrenceBusyHolder]:
        """The operation holding the service, from the 409's object ``detail``; ``None`` for a string detail."""
        return cast(Optional[RecurrenceBusyHolder], self.args[3])


class RecurrenceServiceAuthError(RecurrenceServiceError):
    """The service rejected the request for auth reasons (HTTP 401 / 403).

    Almost always a missing or wrong outbound ``X-API-Key``, which ``JUNIPER_CANOPY_RECURRENCE_API_KEY`` or
    ``JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE`` sets (``Settings.recurrence_api_key``); the message names both.
    """


class RecurrenceServiceRateLimited(RecurrenceServiceError):
    """The service refused the request under its rate limit (HTTP 429).

    juniper-recurrence's ``SecurityMiddleware`` rate-limits per key or client (enabled, 60 requests a minute, by
    default) and answers a refusal with a ``Retry-After`` header: the seconds until its window resets. When the reply
    has the header, the message carries the wait (``… — retry after 30 s``), so it reaches the log,
    ``completion_reason`` and the status bar; :attr:`retry_after` holds the value as sent, or ``None``. canopy's
    dashboard polls canopy, not the service, and canopy calls the service rarely, so a 429 usually means another
    client shares the service's key or address.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None, retry_after: Optional[str] = None) -> None:
        # A fourth positional value, so the exception still rebuilds from ``self.args`` (pickle / copy) as the base's does.
        super().__init__(message, status_code, body, retry_after)

    @property
    def retry_after(self) -> Optional[str]:
        """The reply's ``Retry-After`` value (one line, bounded), or ``None`` when it sent none."""
        return cast(Optional[str], self.args[3])


class RecurrenceServiceTimeoutError(RecurrenceServiceError):
    """The request exceeded its timeout (the blocking fit ran too long, or a network stall).

    :attr:`reply_pending` says whether the request reached the service (W1.5 / F-C4). It is ``True`` after httpx's
    ``ReadTimeout``: the request was sent whole and its reply did not arrive in time, so the service may still be
    working on it -- and a ``POST /v1/train`` fit is not cancelled by canopy giving up. It is ``False`` after a
    connect, write or pool timeout, when the request never got that far.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None, reply_pending: bool = False) -> None:
        # A fourth positional value, so the exception still rebuilds from ``self.args`` (pickle / copy) as the base's does.
        super().__init__(message, status_code, body, reply_pending)

    @property
    def reply_pending(self) -> bool:
        """``True`` when the request reached the service and only its reply timed out (``httpx.ReadTimeout``)."""
        return bool(self.args[3])


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
    # W1.5 / F-CON2: the id the service minted for this fit when it took its lock -- what ``GET /v1/training/status``
    # reports as ``model_operation_id`` while this model is loaded, and what ``expect_operation_id`` takes on
    # ``/v1/predict`` and ``POST /v1/model/snapshots``. ``None`` from a service predating #192 (juniper-recurrence 0.5.0).
    operation_id: Optional[str] = None


@dataclass(frozen=True)
class RecurrenceOperationFailure:
    """Why the service's most recent operation failed: ``StatusResponse.failure`` under ``state == "failed"`` (W1.5).

    ``detail`` is the error detail the failing request returned -- for an unexpected exception, its type and message --
    and ``status_code`` the HTTP status it returned (500 for that exception). Both are as the service sent them. A 5xx
    ``detail`` is never rendered onto an operator surface, for the reason :meth:`RecurrenceServiceAdapter._parse` gives.
    """

    detail: str
    status_code: Optional[int] = None


@dataclass(frozen=True)
class RecurrenceStatus:
    """Parsed ``GET /v1/training/status`` response (one operation's state, never per-epoch).

    ``state`` is ``"idle"`` (no operation yet), ``"training"`` / ``"restoring"`` (an operation holds the service's lock
    now; W1.5), ``"trained"`` (fitted by the service process), ``"restored"`` (loaded from the snapshot
    ``restored_from`` names; W1.6 / F-C6) or ``"failed"`` (the last operation took the lock and did not complete;
    ``failure`` says why; W1.5). ``final_metrics`` / ``stopped_reason`` describe the last completed fit and are ``None``
    otherwise -- including when restored, because no fit produced that model. ``events`` is the ordered training-event
    buffer of that fit. ``restored_from`` is ``None`` unless the state is ``restored``.

    Operation identity (W1.5 / F-CON2; juniper-recurrence#192): ``operation_id`` is the operation the state describes
    and ``operation`` its kind (``train`` / ``restore``); ``busy_since`` is set while it holds the lock; ``requested_by``
    is the ``X-Request-ID`` its request carried; ``dataset_id`` its dataset; ``model_operation_id`` the operation that
    produced the in-memory model -- the model ``/v1/predict`` would score, which is not always the operation the state
    describes. ``reports_operations`` is ``False`` from a service that sends none of these fields (the 0.5.0 contract
    floor, and every service before #192): such a status cannot say whose operation it describes, and every identity
    field is then ``None``.
    """

    state: str
    final_metrics: Optional[dict[str, float]]
    stopped_reason: Optional[str]
    events: list[dict[str, Any]] = field(default_factory=list)
    restored_from: Optional[str] = None
    operation_id: Optional[str] = None
    operation: Optional[str] = None
    busy_since: Optional[str] = None
    dataset_id: Optional[str] = None
    requested_by: Optional[str] = None
    model_operation_id: Optional[str] = None
    failure: Optional[RecurrenceOperationFailure] = None
    reports_operations: bool = False

    @property
    def model_present(self) -> bool:
        """True when the service holds a model it can predict with: ``trained`` or ``restored`` (:data:`MODEL_PRESENT_STATES`).

        A restored model is as present as a trained one. It is not evidence that a fit canopy asked for landed: the
        service reports ``restored`` for a model it never fitted.
        """
        return self.state in MODEL_PRESENT_STATES


@dataclass(frozen=True)
class RecurrenceTrainOutcome:
    """What became of a ``POST /v1/train`` whose reply never arrived, as ``GET /v1/training/status`` tells it (W1.5).

    ``state`` is :data:`OUTCOME_RUNNING` (the service is still fitting canopy's request), :data:`OUTCOME_SUCCEEDED`
    (the fit finished and the model the service holds is the one that request produced; ``result`` is set),
    :data:`OUTCOME_FAILED` (that request failed; ``failure`` is set) or :data:`OUTCOME_UNKNOWN` (canopy cannot tell).

    ``reason`` is one line for the operator, led by the outcome's label -- ``running (upstream)``, ``succeeded
    (upstream)``, ``unknown (upstream unreachable)`` and the other ``unknown (...)`` labels -- or, for a failure, worded
    as the failed request's own error would have been. It is built from canopy's words and the service's answer only,
    never from transport text, so it may go wherever ``outbound_error_text`` output goes. ``status`` is the status that
    was read; when none could be, it is ``None`` and ``error`` holds the exception, whose full text is for the log.
    """

    state: str
    reason: str
    result: Optional[RecurrenceTrainResult] = None
    failure: Optional[RecurrenceOperationFailure] = None
    status: Optional[RecurrenceStatus] = None
    error: Optional[RecurrenceServiceError] = None


def new_request_id() -> str:
    """A fresh ``X-Request-ID`` naming one canopy request: ``juniper-canopy-<uuid4 hex>`` (W1.5)."""
    return f"{_REQUEST_ID_PREFIX}{uuid.uuid4().hex}"


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


def _retry_after(response: httpx.Response) -> Optional[str]:
    """The reply's ``Retry-After`` value as one bounded line (W1.6 / F-C7), or ``None`` when absent or blank.

    Carried as sent rather than parsed: juniper-service-core sends delta-seconds, but a proxy in front of the service
    may send an HTTP-date, and either is what the operator needs to read. Whitespace is collapsed and the value is
    bounded to ``_RETRY_AFTER_MAX_CHARS``, ending in an ellipsis when cut.
    """
    collapsed = " ".join(response.headers.get("retry-after", "").split())
    if not collapsed:
        return None
    if len(collapsed) > _RETRY_AFTER_MAX_CHARS:
        return collapsed[: _RETRY_AFTER_MAX_CHARS - 1].rstrip() + "…"
    return collapsed


def _version_text(value: Any) -> Optional[str]:
    """``value`` stripped when it is a non-blank string -- a version a surface reported -- else ``None``."""
    if isinstance(value, str) and value.strip():
        return value.strip()
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


def _bounded_line(text: Any, max_chars: int) -> str:
    """``text`` on one line -- whitespace runs collapsed -- cut to ``max_chars`` with an ellipsis; ``""`` for ``None``."""
    if text is None:
        return ""
    collapsed = " ".join(str(text).split())
    if len(collapsed) > max_chars:
        return collapsed[: max_chars - 1].rstrip() + "…"
    return collapsed


def _wire_text(value: Any) -> Optional[str]:
    """A string field of a reply exactly as sent, or ``None`` when it is absent, blank or not a string.

    Not stripped: ``requested_by`` must compare equal to the ``X-Request-ID`` canopy sent, character for character.
    """
    if isinstance(value, str) and value.strip():
        return value
    return None


def _operation_failure(value: Any) -> Optional[RecurrenceOperationFailure]:
    """``StatusResponse.failure`` parsed, or ``None`` when the reply carries none (or carries something else)."""
    if not isinstance(value, Mapping):
        return None
    detail = value.get("detail")
    code = value.get("status_code")
    return RecurrenceOperationFailure(detail="" if detail is None else str(detail), status_code=code if isinstance(code, int) and not isinstance(code, bool) else None)


def _busy_holder(response: httpx.Response) -> Optional[RecurrenceBusyHolder]:
    """The busy 409's object ``detail`` (juniper-recurrence#192) as a :class:`RecurrenceBusyHolder`, else ``None``.

    Recognised by shape: an object with a ``busy_since`` key, which every ``BusyDetail`` carries (null when unknown)
    and no other 409 detail does. The bare string juniper-recurrence 0.5.0 sends is not a holder, nor is the
    ``expect_operation_id`` mismatch of ``/v1/predict``, which names ``expected_operation_id`` instead. Never raises,
    for the reason :func:`_service_detail` gives.
    """
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 -- a describer must not raise: the typed error stands whatever the body holds
        return None
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if not isinstance(detail, dict) or "busy_since" not in detail:
        return None
    message = detail.get("message")
    return RecurrenceBusyHolder(
        message=message if isinstance(message, str) else "",
        operation_id=_wire_text(detail.get("operation_id")),
        operation=_wire_text(detail.get("operation")),
        busy_since=_wire_text(detail.get("busy_since")),
        requested_by=_wire_text(detail.get("requested_by")),
        dataset_id=_wire_text(detail.get("dataset_id")),
    )


def _result_from_status(status: RecurrenceStatus) -> RecurrenceTrainResult:
    """The fit's result as ``GET /v1/training/status`` reports it, for a fit whose ``POST /v1/train`` reply never came (W1.5).

    The status carries the ``final_metrics`` and ``stopped_reason`` the reply would have carried, and the resolved
    ``dataset_id``. It carries no epoch count and no dataset descriptor, so ``n_epochs`` is read from the fit's last
    ``epoch_end`` event -- juniper-recurrence-model numbers its ``epoch`` from 0 -- and is 0 without one, as for a
    reply without the key; ``dataset`` holds the id alone.
    """
    n_epochs = 0
    for event in status.events:
        payload = event.get("payload") if isinstance(event, Mapping) else None
        if isinstance(payload, Mapping) and event.get("type") == "epoch_end":
            epoch = payload.get("epoch")
            if isinstance(epoch, int) and not isinstance(epoch, bool) and epoch >= 0:
                n_epochs = epoch + 1
    return RecurrenceTrainResult(
        final_metrics=dict(status.final_metrics or {}),
        n_epochs=n_epochs,
        stopped_reason=status.stopped_reason,
        dataset={"dataset_id": status.dataset_id} if status.dataset_id else {},
        operation_id=status.operation_id,
    )


def _failure_reason(failure: Optional[RecurrenceOperationFailure]) -> str:
    """A failed fit's reason, worded as its own ``POST /v1/train`` error would have been, and saying how it was learned.

    The status code, method and path, then -- on a 4xx only -- the service's ``detail``, flattened and bounded exactly as
    :meth:`RecurrenceServiceAdapter._parse` renders it. A 5xx ``detail`` is left off for the reason ``_parse`` gives.
    """
    code = failure.status_code if failure is not None else None
    head = f"recurrence service error {code} on POST /v1/train" if code is not None else "recurrence fit failed on POST /v1/train"
    head = f"{head}, reported by GET /v1/training/status after the request timed out"
    detail = _render_detail({"detail": failure.detail}) if failure is not None and code is not None and httpx.codes.is_client_error(code) else None
    return f"{head}: {detail}" if detail else head


def _classify_train_outcome(status: RecurrenceStatus, request_id: str) -> RecurrenceTrainOutcome:
    """Read ``status`` against the train request canopy named ``request_id``; see :meth:`RecurrenceServiceAdapter.train_outcome`."""
    if not status.reports_operations:
        reason = "unknown (no operation identity): the service does not say which request its status describes (juniper-recurrence 0.5.0 and older), so canopy cannot tell whether its fit finished"
        return RecurrenceTrainOutcome(OUTCOME_UNKNOWN, reason, status=status)
    operation_id = _bounded_line(status.operation_id, _FIELD_MAX_CHARS)
    state = _bounded_line(status.state, _FIELD_MAX_CHARS)
    if status.requested_by != request_id or status.operation not in (None, "train"):
        if status.operation_id is None:
            reason = "unknown (no operation on record): the service reports no operation since it started, so it restarted after canopy's request or never received it; canopy cannot tell whether its fit finished"
        else:
            kind = _bounded_line(status.operation, _FIELD_MAX_CHARS) or "an"
            by = f", requested by {_bounded_line(status.requested_by, _FIELD_MAX_CHARS)}" if status.requested_by else ""
            reason = f"unknown (another operation since): the status describes {kind} operation {operation_id} ({state}{by}), not canopy's request {_bounded_line(request_id, _FIELD_MAX_CHARS)}; canopy cannot tell whether its fit finished"
        return RecurrenceTrainOutcome(OUTCOME_UNKNOWN, reason, status=status)
    if status.state in _IN_FLIGHT_STATES:
        since = f" since {_bounded_line(status.busy_since, _FIELD_MAX_CHARS)}" if status.busy_since else ""
        return RecurrenceTrainOutcome(OUTCOME_RUNNING, f"running (upstream): the service is still fitting canopy's request (operation {operation_id}{since}); a fit cannot be cancelled", status=status)
    if status.state == "failed":
        return RecurrenceTrainOutcome(OUTCOME_FAILED, _failure_reason(status.failure), failure=status.failure, status=status)
    # The one way to succeed: the operation canopy's request started is the one that produced the model the service now
    # holds. ``model_present`` alone also holds for a restored model and for another caller's fit; ``trained`` alone
    # also holds for another caller's fit; neither says whose model it is.
    if status.model_present and status.operation_id is not None and status.model_operation_id == status.operation_id:
        reason = f"succeeded (upstream): the service finished canopy's fit after the request timed out (operation {operation_id})"
        return RecurrenceTrainOutcome(OUTCOME_SUCCEEDED, reason, result=_result_from_status(status), status=status)
    held = f"holds a model from operation {_bounded_line(status.model_operation_id, _FIELD_MAX_CHARS)}" if status.model_operation_id else "holds no model"
    reason = f"unknown (outcome not attributable): the service reports canopy's operation {operation_id} as {state} and {held}; canopy cannot tell whether its fit finished"
    return RecurrenceTrainOutcome(OUTCOME_UNKNOWN, reason, status=status)


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
        request_id: Optional[str] = None,
    ) -> RecurrenceTrainResult:
        """Synchronously fit the LMU on a dataset split via ``POST /v1/train``.

        The dataset is referenced (not piped) — the recurrence service fetches the arrays
        from juniper-data itself. Resolution precedence mirrors the service's
        ``DatasetRef``: ``dataset_id`` -> ``name`` -> ``generator`` + ``params``; at least
        one MUST be supplied (validated client-side before the HTTP call). Unset
        hyperparameters fall back to the service defaults.

        ``request_id`` (W1.5) goes out as ``X-Request-ID``, which the service records as the
        operation's ``requested_by``: if the reply never arrives, :meth:`train_outcome` can
        still find the fit by it. :func:`new_request_id` mints one. The result's
        ``operation_id`` is the id the service minted for the fit.

        Raises:
            ValueError: no dataset reference supplied.
            RecurrenceTrainInProgressError: another operation holds the service (409); its
                ``holder`` names it when the service says.
            RecurrenceServiceAuthError: rejected for auth (401 / 403).
            RecurrenceServiceTimeoutError: the blocking fit exceeded the read timeout. With
                ``reply_pending`` the fit may still be running: ask :meth:`train_outcome`.
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

        headers = {REQUEST_ID_HEADER: request_id} if request_id else None
        data = self._call("POST", "/v1/train", self._train_timeout, json_body=body, headers=headers)
        return RecurrenceTrainResult(
            final_metrics=dict(data.get("final_metrics") or {}),
            n_epochs=int(data.get("n_epochs", 0)),
            stopped_reason=data.get("stopped_reason"),
            dataset=dict(data.get("dataset") or {}),
            operation_id=_wire_text(data.get("operation_id")),
        )

    def training_status(self) -> RecurrenceStatus:
        """Return the current or last operation's status via ``GET /v1/training/status`` (instant).

        The state (idle | training | restoring | trained | restored | failed), the recorded event
        buffer, and -- since juniper-recurrence#192 (W1.5) -- which operation the state describes,
        whose request it was, and which operation produced the model the service holds. A service
        that predates #192 reports ``idle`` / ``trained`` only and no identity, which parses as
        ``reports_operations=False``. Whether the service holds a model is
        :attr:`RecurrenceStatus.model_present`, which counts a restored model exactly as a trained
        one (W1.6 / F-C6).
        """
        data = self._call("GET", "/v1/training/status", self._status_timeout)
        return RecurrenceStatus(
            state=str(data.get("state", "idle")),
            final_metrics=data.get("final_metrics"),
            stopped_reason=data.get("stopped_reason"),
            events=list(data.get("events") or []),
            restored_from=data.get("restored_from"),
            operation_id=_wire_text(data.get("operation_id")),
            operation=_wire_text(data.get("operation")),
            busy_since=_wire_text(data.get("busy_since")),
            dataset_id=_wire_text(data.get("dataset_id")),
            requested_by=_wire_text(data.get("requested_by")),
            model_operation_id=_wire_text(data.get("model_operation_id")),
            failure=_operation_failure(data.get("failure")),
            # Key presence, not value: #192 sends ``operation_id`` on every status (null while idle), 0.5.0 never does.
            reports_operations="operation_id" in data,
        )

    def train_outcome(self, request_id: str) -> RecurrenceTrainOutcome:
        """What became of the ``POST /v1/train`` that sent ``X-Request-ID: <request_id>`` and timed out (W1.5 / F-C4).

        One ``GET /v1/training/status``, read against the request id. The service does not cancel a fit when canopy
        stops waiting for it, so how the fit ended is the service's to say, and canopy must not guess: recording
        ``failed`` on the timeout -- canopy's old behaviour -- was wrong whenever the fit went on to succeed, and left
        the next Start to meet a 409 from a lock canopy believed free.

        The status speaks for canopy's fit only when it names canopy's request as its ``requested_by``. That fit
        **succeeded** only when it produced the model the service holds (``model_operation_id == operation_id``):
        ``trained`` alone may be another caller's fit, and ``restored`` is never a fit at all, though both count as a
        model being present (:attr:`RecurrenceStatus.model_present`). Anything less is :data:`OUTCOME_UNKNOWN`, never
        :data:`OUTCOME_SUCCEEDED` -- including every status from a service that reports no operation identity.

        Never raises: an unreachable or unreadable status is an unknown outcome carrying the exception as ``error``.
        """
        try:
            status = self.training_status()
        except (RecurrenceServiceTimeoutError, RecurrenceServiceUnavailableError) as exc:
            # canopy's own words: a transport failure's text can quote a header value (#683), and this reason is shown.
            reason = "unknown (upstream unreachable): canopy could not reach GET /v1/training/status after its POST /v1/train timed out, so it cannot tell whether the fit finished"
            return RecurrenceTrainOutcome(OUTCOME_UNKNOWN, reason, error=exc)
        except RecurrenceServiceError as exc:
            return RecurrenceTrainOutcome(OUTCOME_UNKNOWN, f"unknown (upstream status unreadable): {outbound_error_text(exc)}", error=exc)
        return _classify_train_outcome(status, request_id)

    def service_version(self) -> str:
        """The version the recurrence service reports about itself (W1.7 / F-C8), read over the wire.

        ``GET /v1/health`` first: a non-blank ``version`` in its body is the answer. juniper-recurrence 0.5.0's has none
        -- juniper-service-core's health router answers ``{"status": "ok"}`` -- so the fallback is ``GET /openapi.json``,
        whose ``info.version`` FastAPI fills from the ``version=__version__`` the service passes to ``create_app``. That
        route is exempt from auth under juniper-service-core 0.5.0 and authenticated under 0.7.0; this sends the same
        ``X-API-Key`` as every call, so it reads both. ``GET /`` is no help: the service mounts no root route.

        Raises:
            RecurrenceServiceAuthError / RecurrenceServiceTimeoutError / RecurrenceServiceUnavailableError /
            RecurrenceServiceError: as for any call, and ``RecurrenceServiceError`` when neither surface names a
            version. A caller that wants a label rather than an error uses ``model_registry.refresh_model_versions``.
        """
        version = _version_text(self._call("GET", "/v1/health", self._status_timeout).get("version"))
        if version is not None:
            return version
        info = self._call("GET", "/openapi.json", self._status_timeout).get("info")
        version = _version_text(info.get("version") if isinstance(info, dict) else None)
        if version is not None:
            return version
        raise RecurrenceServiceError("recurrence service reported no version on GET /v1/health or GET /openapi.json")

    # ------------------------------------------------------------------ HTTP plumbing

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    def _call(self, method: str, path: str, timeout: httpx.Timeout, *, json_body: Optional[dict[str, Any]] = None, headers: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
        """Issue one request and map transport / HTTP failures onto the typed hierarchy.

        Named ``_call`` (deliberately NOT ``_request`` / ``_get`` / ``_post``): the static
        guard ``tests/unit/backend/test_cascor_service_adapter_v1_prefix_regression.py``
        flags any ``_request``-family call under ``src/backend/`` that passes a
        ``/v1/``-prefixed path — a convention specific to ``JuniperCascorClient`` (whose
        ``api_url`` already embeds ``/v1``, so cascor paths must omit it). This adapter is
        raw ``httpx`` against a plain ``base_url``, and the recurrence routes genuinely are
        ``/v1/...`` (the service's own tests POST ``/v1/train``), so the prefix is correct
        here and the helper must sit outside that guarded name-set.

        ``headers`` are added to the adapter's own for this request only (``X-Request-ID`` on a train, W1.5).
        """
        try:
            with httpx.Client(base_url=self._base_url, headers=self._headers(), timeout=timeout, transport=self._transport) as client:
                response = client.request(method, path, json=json_body, headers=headers)
        except httpx.TimeoutException as exc:
            # A ReadTimeout is the one timeout after which the request has reached the service (W1.5 / F-C4).
            raise RecurrenceServiceTimeoutError(f"recurrence service timed out on {method} {path}: {exc}", reply_pending=isinstance(exc, httpx.ReadTimeout)) from exc
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

        A 401 / 403 names the variables that set the key (W1.6 / F-C5). A 429 raises
        :class:`RecurrenceServiceRateLimited`, whose message carries the reply's ``Retry-After`` before the detail
        (W1.6 / F-C7); without the header its message is the generic 4xx wording, unchanged.

        A busy 409 whose ``detail`` is the object juniper-recurrence#192 sends names the operation holding the service
        (W1.5 / F-CON1): the message carries what to do (``_BUSY_REMEDY``) before the holder, as a 429 carries its wait,
        and the error's ``holder`` has it parsed. A string detail -- the published 0.5.0's -- is appended unchanged.
        """
        code = response.status_code
        detail = _service_detail(response) if httpx.codes.is_client_error(code) else None
        suffix = f": {detail}" if detail else ""
        if code == httpx.codes.CONFLICT:  # 409
            holder = _busy_holder(response)
            if holder is not None:
                raise RecurrenceTrainInProgressError(f"recurrence training already in progress ({method} {path}) — {_BUSY_REMEDY}: {holder.describe()}", status_code=code, body=response.text, holder=holder)
            raise RecurrenceTrainInProgressError(f"recurrence training already in progress ({method} {path}){suffix}", status_code=code, body=response.text)
        if code in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN):  # 401 / 403
            raise RecurrenceServiceAuthError(f"recurrence service rejected the request ({code} on {method} {path}) — {_AUTH_REMEDY}{suffix}", status_code=code, body=response.text)
        if code == httpx.codes.TOO_MANY_REQUESTS:  # 429
            retry_after = _retry_after(response)
            wait = "" if retry_after is None else f" — retry after {retry_after}{' s' if retry_after.isdigit() else ''}"
            raise RecurrenceServiceRateLimited(f"recurrence service error {code} on {method} {path}{wait}{suffix}", status_code=code, body=response.text, retry_after=retry_after)
        if code >= httpx.codes.BAD_REQUEST:  # any other 4xx / 5xx
            raise RecurrenceServiceError(f"recurrence service error {code} on {method} {path}{suffix}", status_code=code, body=response.text)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RecurrenceServiceError(f"recurrence service returned a non-JSON body on {method} {path}", status_code=code, body=response.text) from exc
        if not isinstance(payload, dict):
            raise RecurrenceServiceError(f"recurrence service returned a non-object JSON body on {method} {path}", status_code=code, body=response.text)
        return payload
