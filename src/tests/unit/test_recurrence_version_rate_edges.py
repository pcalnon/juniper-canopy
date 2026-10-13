#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_version_rate_edges.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-05
# Last Modified: 2026-10-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Edges the W1.6 / W1.7 suites do not reach: a failed
#                health read must not become a version, a Retry-After
#                unit is only for an all-digit wait, and a status token
#                counts as a model only when it is exact.
#####################################################################
"""Edges around recurrence version lookup, 429 waits, and model-present.

``TestServiceVersion`` falls through to ``/openapi.json`` only when ``GET /v1/health`` is HTTP 200
and its ``version`` is not a version. A health call that fails — refused, rate-limited, 5xx,
non-JSON, timed out, unreachable — is an error, even when ``/openapi.json`` would have answered
``0.5.0``. ``TestW16AuthRestoredRateLimit`` pins integer and HTTP-date ``Retry-After`` values; a
zero wait and a fractional or signed token are the cases ``str.isdigit`` decides. ``model_present``
is pinned on states the parser has already stored; a cased or padded token, and an idle status that
still carries ``restored_from``, have to come through ``training_status``.
"""

import logging

import httpx
import pytest

from backend.recurrence_service_adapter import (
    RecurrenceServiceAdapter,
    RecurrenceServiceAuthError,
    RecurrenceServiceError,
    RecurrenceServiceRateLimited,
    RecurrenceServiceTimeoutError,
    RecurrenceServiceUnavailableError,
)
from model_registry import (
    RECURRENCE_PROVIDER,
    SERVICE_VERSION_UNAVAILABLE,
    get_model_spec,
    refresh_model_versions,
)

_BASE = "http://recurrence.test:8210"
_OPENAPI_VERSION = "0.5.0"
_OPENAPI = {"openapi": "3.1.0", "info": {"title": "Juniper Recurrence", "version": _OPENAPI_VERSION}, "paths": {}}

# kind -> the typed error ``service_version`` must raise. Exact type, not a subclass: a 500 that
# became an auth error, or a 401 that became the base, is a different failure.
_HEALTH_FAILURES = {
    "401": RecurrenceServiceAuthError,
    "429": RecurrenceServiceRateLimited,
    "500": RecurrenceServiceError,
    "non-json": RecurrenceServiceError,
    "non-object": RecurrenceServiceError,
    "timeout": RecurrenceServiceTimeoutError,
    "connect": RecurrenceServiceUnavailableError,
}


def _health_fails_openapi_would_answer(kind, sink):
    """Fail ``GET /v1/health`` as ``kind``; ``GET /openapi.json`` would report the contract-floor version."""

    def handler(request: httpx.Request) -> httpx.Response:
        sink.append(request)
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=_OPENAPI)
        if kind == "timeout":
            raise httpx.ReadTimeout("read timed out", request=request)
        if kind == "connect":
            raise httpx.ConnectError("connection refused", request=request)
        if kind == "401":
            return httpx.Response(401, json={"detail": "Invalid API key."})
        if kind == "429":
            return httpx.Response(429, headers={"Retry-After": "12"}, json={"detail": "Rate limit exceeded"})
        if kind == "500":
            return httpx.Response(500, json={"detail": "internal"})
        if kind == "non-json":
            return httpx.Response(200, content=b"ok", headers={"content-type": "text/plain"})
        if kind == "non-object":
            return httpx.Response(200, json=[_OPENAPI_VERSION])
        raise AssertionError(f"unknown health failure {kind}")

    return handler


def _adapter(handler):
    return RecurrenceServiceAdapter(_BASE, "k", transport=httpx.MockTransport(handler))


@pytest.mark.unit
class TestAFailedHealthReadIsNotAVersion:
    """W1.7 / F-C8: the openapi fallback runs only after health answered and named no version."""

    @pytest.mark.parametrize("kind", list(_HEALTH_FAILURES))
    def test_a_failed_health_read_does_not_fall_through_to_openapi(self, kind):
        sink = []
        adapter = _adapter(_health_fails_openapi_would_answer(kind, sink))
        with pytest.raises(_HEALTH_FAILURES[kind]) as caught:
            adapter.service_version()
        error = caught.value
        assert type(error) is _HEALTH_FAILURES[kind]
        assert [request.url.path for request in sink] == ["/v1/health"]
        assert sink[0].headers["X-API-Key"] == "k"
        assert _OPENAPI_VERSION not in str(error)
        assert "reported no version" not in str(error)
        if kind == "429":
            assert error.retry_after == "12"
            assert "retry after 12 s" in str(error)


@pytest.mark.unit
class TestRetryAfterUnit:
    """W1.6 / F-C7: the ``s`` is for a delta-seconds token. Anything else is carried as sent."""

    @pytest.mark.parametrize(
        "header, shown",
        [
            ("0", "0 s"),
            (" 0 ", "0 s"),
            ("30.0", "30.0"),
            ("+30", "+30"),
            ("-1", "-1"),
            ("30s", "30s"),
            ("3 0", "3 0"),
        ],
    )
    def test_only_an_all_digit_wait_is_labelled_in_seconds(self, header, shown):
        response = httpx.Response(429, headers={"Retry-After": header})
        with pytest.raises(RecurrenceServiceRateLimited) as caught:
            RecurrenceServiceAdapter._parse(response, "POST", "/v1/train")
        assert caught.value.retry_after == " ".join(header.split())
        assert str(caught.value) == f"recurrence service error 429 on POST /v1/train — retry after {shown}"


@pytest.mark.unit
class TestRefreshLabelsServiceErrors:
    """W1.7 / F-C8: refresh never raises for a version, including when the service refuses the key or the rate."""

    @pytest.mark.parametrize(
        "kind, error_name",
        [("401", "RecurrenceServiceAuthError"), ("429", "RecurrenceServiceRateLimited")],
    )
    def test_an_answered_refusal_is_the_unavailable_label(self, kind, error_name, caplog):
        source = _adapter(_health_fails_openapi_would_answer(kind, [])).service_version
        with caplog.at_level(logging.WARNING, logger="juniper_canopy.model_registry"):
            refreshed = refresh_model_versions({RECURRENCE_PROVIDER: source})
        assert get_model_spec("recurrence", models=refreshed).version == SERVICE_VERSION_UNAVAILABLE
        assert get_model_spec("recurrence").version == ""
        assert any(error_name in record.getMessage() for record in caplog.records)


@pytest.mark.unit
class TestModelPresentIsAnExactToken:
    """W1.6 / F-C6: ``trained`` and ``restored`` count. A lookalike, or a snapshot id on idle, does not."""

    @pytest.mark.parametrize("state", ["TRAINED", "Restored", "trained ", " restored"])
    def test_a_cased_or_padded_state_is_not_a_model(self, state):
        status = _adapter(lambda request: httpx.Response(200, json={"state": state, "restored_from": "snap-1"})).training_status()
        assert status.state == state
        assert status.model_present is False

    def test_a_snapshot_id_and_metrics_do_not_make_idle_a_model(self):
        payload = {
            "state": "idle",
            "restored_from": "snap-20261004-0001",
            "final_metrics": {"r2": 1.0},
            "stopped_reason": "fit_complete",
        }
        status = _adapter(lambda request: httpx.Response(200, json=payload)).training_status()
        assert status.state == "idle"
        assert status.restored_from == "snap-20261004-0001"
        assert status.final_metrics == {"r2": 1.0}
        assert status.model_present is False
