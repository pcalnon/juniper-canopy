#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_service_adapter.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-22
# Last Modified: 2026-10-05
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for RecurrenceServiceAdapter (A1-i, D3) — the
#                synchronous httpx REST client for the juniper-recurrence
#                model service. Mocked end-to-end via httpx.MockTransport;
#                no network, no live service.
#####################################################################
"""Unit tests for ``backend.recurrence_service_adapter`` (A1-i of the model-selection
A1 enabler). Exercises request shaping, the outbound ``X-API-Key`` header, the generous
train timeout, JSON parsing, and the typed error mapping (409 / 401 / 403 / 429 / other-HTTP /
timeout / unreachable / non-JSON) — all against an injected ``httpx.MockTransport``.

``TestServiceDetailInTheMessage`` pins W0.5 / F-C1: on a 4xx the service's ``{"detail": …}``
-- the only place it says *why* it refused -- rides on the exception message, bounded, while
``body`` keeps the raw response text. A 5xx detail never does: there the service relays its
own upstream's exception text, which can quote a key.

``TestW16AuthRestoredRateLimit`` pins W1.6 (F-C5, F-C6, F-C7): a 401 names the key variables, a
``restored`` status reads as model-present, and a 429 carries its ``Retry-After``.
``TestServiceVersion`` pins W1.7 (F-C8): the version is read from the service, never assumed.
"""

import copy
import json
import pickle
import re
from pathlib import Path

import httpx
import pytest

from backend.recurrence_service_adapter import (
    MODEL_PRESENT_STATES,
    RECURRENCE_SERVICE_CONTRACT_FLOOR,
    RecurrenceServiceAdapter,
    RecurrenceServiceAuthError,
    RecurrenceServiceError,
    RecurrenceServiceRateLimited,
    RecurrenceServiceTimeoutError,
    RecurrenceServiceUnavailableError,
    RecurrenceStatus,
    RecurrenceTrainInProgressError,
    RecurrenceTrainResult,
)
from outbound_errors import outbound_error_text

_BASE = "http://recurrence.test:8210"

# W1.6 / F-C5: the 401 / 403 remedy names the variables an operator sets, not the setting's Python name.
_AUTH_REMEDY = "set JUNIPER_CANOPY_RECURRENCE_API_KEY or JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE to a key the service accepts"

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


def _raw_responder(status_code, content, content_type="application/json"):
    """A MockTransport handler returning ``content`` byte-for-byte, so ``body`` can be pinned exactly."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=content.encode("utf-8"), headers={"content-type": content_type})

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

    def test_train_tolerates_a_response_key_it_does_not_know(self):
        """The service is gaining ``metrics_scope: "in_sample"`` on this response (W0.7); an unknown key must not break parsing."""
        adapter = _adapter(_responder({**_TRAIN_OK, "metrics_scope": "in_sample"}))
        result = adapter.train(generator="equities_seq")
        assert result.final_metrics["r2"] == pytest.approx(0.97)
        assert result.stopped_reason == "fit_complete"

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


_NON_FINITE = "invalid dataset: X_train has non-finite values (NaN/Inf)"


def _train_error(handler):
    """The exception ``train`` raises against ``handler``."""
    with pytest.raises(RecurrenceServiceError) as caught:
        _adapter(handler).train(generator="equities_seq")
    return caught.value


@pytest.mark.unit
class TestServiceDetailInTheMessage:
    """W0.5 / F-C1: the service's ``detail`` reaches the exception message; ``body`` is untouched."""

    def test_a_422_string_detail_is_appended(self):
        raw = json.dumps({"detail": _NON_FINITE})
        error = _train_error(_raw_responder(422, raw))
        assert str(error) == f"recurrence service error 422 on POST /v1/train: {_NON_FINITE}"
        assert error.status_code == 422
        assert error.body == raw  # the raw response text, exactly as before

    def test_a_validation_error_list_renders_loc_and_msg_pairs(self):
        """FastAPI's 422 shape. ``input`` echoes the request back verbatim and is never rendered."""
        detail = [
            {"type": "missing", "loc": ["body", "dataset", "generator"], "msg": "Field required", "input": {"split": "train"}},
            {"type": "int_parsing", "loc": ["body", "d"], "msg": "Input should be a valid integer, unable to parse string as an integer", "input": "ECHO-7c1d"},
        ]
        error = _train_error(_responder({"detail": detail}, status_code=422))
        assert str(error) == "recurrence service error 422 on POST /v1/train: body.dataset.generator -> Field required; body.d -> Input should be a valid integer, unable to parse string as an integer"
        assert "ECHO-7c1d" not in str(error)

    @pytest.mark.parametrize(
        "item, rendered",
        [
            ({"loc": ["body", "dataset", "params", "symbols", 0], "msg": "Input should be a valid string"}, "body.dataset.params.symbols.0 -> Input should be a valid string"),
            ({"loc": "query", "msg": "bad"}, "query -> bad"),
            ({"loc": [], "msg": "no location"}, "no location"),
            ({"msg": "no loc key"}, "no loc key"),
            ({"type": "custom", "loc": ["body"]}, "{'type': 'custom', 'loc': ['body']}"),
            ("a bare string item", "a bare string item"),
        ],
        ids=["int-in-loc", "string-loc", "empty-loc", "missing-loc", "missing-msg", "non-mapping"],
    )
    def test_each_validation_item_shape(self, item, rendered):
        error = _train_error(_responder({"detail": [item]}, status_code=422))
        assert str(error) == f"recurrence service error 422 on POST /v1/train: {rendered}"

    @pytest.mark.parametrize(
        "detail, rendered",
        [({"reason": "bad"}, "{'reason': 'bad'}"), (42, "42"), (True, "True")],
        ids=["object", "number", "boolean"],
    )
    def test_any_other_detail_is_stringified(self, detail, rendered):
        error = _train_error(_responder({"detail": detail}, status_code=422))
        assert str(error) == f"recurrence service error 422 on POST /v1/train: {rendered}"

    def test_whitespace_in_the_detail_is_collapsed(self):
        error = _train_error(_responder({"detail": "line one\n\tline two   three\r\n"}, status_code=422))
        assert str(error) == "recurrence service error 422 on POST /v1/train: line one line two three"

    def test_a_long_detail_is_bounded_with_an_ellipsis(self):
        prefix = "recurrence service error 422 on POST /v1/train: "
        error = _train_error(_responder({"detail": "x" * 1000}, status_code=422))
        message = str(error)
        assert message.startswith(prefix)
        rendered = message[len(prefix) :]
        assert len(rendered) == 300
        assert rendered.endswith("…"), "a cut detail must show that it was cut"

    def test_a_detail_at_the_bound_is_not_cut(self):
        error = _train_error(_responder({"detail": "y" * 300}, status_code=422))
        assert str(error).endswith(": " + "y" * 300)

    @pytest.mark.parametrize(
        "status_code, content, content_type",
        [
            (400, "<html><body>400 Bad Request</body></html>", "text/html"),
            (404, "Not Found", "text/plain"),
            (422, json.dumps({"error": "no detail key"}), "application/json"),
            (422, json.dumps({"detail": None}), "application/json"),
            (422, json.dumps({"detail": ""}), "application/json"),
            (422, json.dumps({"detail": " \n\t "}), "application/json"),
            (422, json.dumps(["detail", "a list body"]), "application/json"),
            (429, "", "application/json"),
        ],
        ids=["html", "plain-text", "json-without-detail", "null-detail", "empty-detail", "blank-detail", "json-list-body", "empty-body"],
    )
    def test_a_body_without_a_usable_detail_leaves_the_message_unchanged(self, status_code, content, content_type):
        """All 4xx -- the codes that WOULD carry a detail -- so each case exercises the 'no usable detail' path."""
        error = _train_error(_raw_responder(status_code, content, content_type))
        assert str(error) == f"recurrence service error {status_code} on POST /v1/train"
        assert error.body == content

    @pytest.mark.parametrize(
        "status_code, error_type, message",
        [
            (401, RecurrenceServiceAuthError, f"recurrence service rejected the request (401 on POST /v1/train) — {_AUTH_REMEDY}"),
            (409, RecurrenceTrainInProgressError, "recurrence training already in progress (POST /v1/train)"),
            (422, RecurrenceServiceError, "recurrence service error 422 on POST /v1/train"),
        ],
        ids=["401", "409", "422"],
    )
    def test_a_body_the_decoder_cannot_handle_never_changes_the_error(self, status_code, error_type, message):
        """Deep nesting makes the JSON decoder raise ``RecursionError``, which is not a ``ValueError``.

        Reading the detail is decoration: whatever the body holds, the typed error and its message must stand.
        """
        error = _train_error(_raw_responder(status_code, "[" * 100_000 + "]" * 100_000))
        assert type(error) is error_type
        assert str(error) == message
        assert error.status_code == status_code

    def test_409_keeps_its_wording_and_appends_the_detail(self):
        raw = json.dumps({"detail": "a training run is already in progress"})
        error = _train_error(_raw_responder(409, raw))
        assert isinstance(error, RecurrenceTrainInProgressError)
        assert str(error) == "recurrence training already in progress (POST /v1/train): a training run is already in progress"
        assert error.status_code == 409
        assert error.body == raw

    def test_409_without_a_detail_is_unchanged(self):
        error = _train_error(_raw_responder(409, "", "text/plain"))
        assert str(error) == "recurrence training already in progress (POST /v1/train)"

    @pytest.mark.parametrize("code", [401, 403])
    def test_auth_errors_keep_the_remedy_and_append_the_detail(self, code):
        raw = json.dumps({"detail": "Invalid or missing API key"})
        error = _train_error(_raw_responder(code, raw))
        assert isinstance(error, RecurrenceServiceAuthError)
        assert str(error) == f"recurrence service rejected the request ({code} on POST /v1/train) — {_AUTH_REMEDY}: Invalid or missing API key"
        assert error.body == raw

    def test_the_status_route_carries_the_detail_too(self):
        """``_parse`` is shared, so ``GET /v1/training/status`` gets the same treatment."""
        with pytest.raises(RecurrenceServiceError) as caught:
            _adapter(_responder({"detail": "Rate limit exceeded"}, status_code=429)).training_status()
        assert str(caught.value) == "recurrence service error 429 on GET /v1/training/status: Rate limit exceeded"

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_a_5xx_detail_is_never_appended(self, status_code):
        """A 5xx detail relays the service's OWN upstream's exception text, which can quote a key.

        juniper-recurrence's ``map_data_error`` answers a juniper-data client failure with
        ``502 f"data fetch failed: {exc}"``, and juniper-data-client 0.5.0 words a refused header exactly as below. The
        message -- what reaches ``completion_reason`` and the log -- keeps only canopy's own words; ``body`` keeps the
        raw text, as it always has.
        """
        relayed = "data fetch failed: Request failed: Invalid leading whitespace, reserved character(s), or return character(s) in header value: ' LEAKME-5xx'"
        raw = json.dumps({"detail": relayed})
        error = _train_error(_raw_responder(status_code, raw))
        assert str(error) == f"recurrence service error {status_code} on POST /v1/train"
        assert "LEAKME" not in str(error)
        assert error.body == raw

    def test_a_success_body_is_still_returned_as_is(self):
        """A 2xx is never searched for a ``detail``: only an error status renders one."""
        status = _adapter(_responder({"state": "idle", "detail": "not an error"})).training_status()
        assert status.state == "idle"


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


# What juniper-service-core's rate limiter sends with a 429 (``security.py``: the detail, and ``Retry-After`` among its headers).
_RATE_LIMITED_DETAIL = "Rate limit exceeded. Try again in 30 seconds."


def _rate_limited(retry_after=None, payload=None):
    """A MockTransport handler answering 429, with ``Retry-After: <retry_after>`` when given and ``payload`` as the JSON body."""

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {} if retry_after is None else {"Retry-After": retry_after}
        if payload is None:
            return httpx.Response(429, headers=headers)
        return httpx.Response(429, json=payload, headers=headers)

    return handler


@pytest.mark.unit
class TestW16AuthRestoredRateLimit:
    """W1.6: a 401 names the key variables (F-C5); ``restored`` reads as model-present (F-C6); a 429 carries ``Retry-After`` (F-C7).

    The first three tests are the plan's three adapter tests; the rest pin the edges around each.
    """

    def test_a_401_remedy_names_both_key_variables(self):
        """F-C5: the remedy said ``check recurrence_api_key`` -- the setting's Python name, which no operator can set."""
        error = _train_error(_responder({"detail": "Invalid API key."}, status_code=401))
        assert type(error) is RecurrenceServiceAuthError
        named = set(re.findall(r"\bJUNIPER_[A-Z_]+\b", str(error)))
        assert named == {"JUNIPER_CANOPY_RECURRENCE_API_KEY", "JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE"}
        assert "recurrence_api_key" not in str(error)
        assert str(error) == f"recurrence service rejected the request (401 on POST /v1/train) — {_AUTH_REMEDY}: Invalid API key."

    def test_a_restored_status_parses_and_reads_as_model_present(self):
        """F-C6: the service's third state -- a model loaded from a snapshot -- is a model, exactly as ``trained`` is."""
        payload = {"state": "restored", "final_metrics": None, "stopped_reason": None, "events": [], "restored_from": "snap-20261004-0001"}
        status = _adapter(_responder(payload)).training_status()
        assert status.state == "restored"
        assert status.restored_from == "snap-20261004-0001"
        assert status.model_present is True
        assert status.final_metrics is None and status.stopped_reason is None and status.events == []

    def test_a_429_with_retry_after_raises_rate_limited_carrying_the_wait(self):
        """F-C7: the reply juniper-service-core's limiter sends -- the header and its detail -- reaches the message."""
        error = _train_error(_rate_limited("30", {"detail": _RATE_LIMITED_DETAIL}))
        assert type(error) is RecurrenceServiceRateLimited
        assert isinstance(error, RecurrenceServiceError)
        assert error.status_code == 429
        assert error.retry_after == "30"
        assert "retry after 30 s" in str(error)
        assert str(error) == f"recurrence service error 429 on POST /v1/train — retry after 30 s: {_RATE_LIMITED_DETAIL}"

    def test_a_403_names_both_key_variables_too(self):
        error = _train_error(_raw_responder(403, "", "text/plain"))
        assert type(error) is RecurrenceServiceAuthError
        assert str(error) == f"recurrence service rejected the request (403 on POST /v1/train) — {_AUTH_REMEDY}"

    @pytest.mark.parametrize("state, present", [("idle", False), ("trained", True), ("restored", True), ("fitting", False), ("", False)])
    def test_model_present_is_trained_or_restored_and_nothing_else(self, state, present):
        assert RecurrenceStatus(state=state, final_metrics=None, stopped_reason=None).model_present is present

    def test_the_model_present_states_are_exactly_trained_and_restored(self):
        assert MODEL_PRESENT_STATES == frozenset({"trained", "restored"})

    def test_a_status_from_a_service_predating_restored_has_no_restored_from(self):
        """juniper-recurrence 0.5.0 -- the contract floor -- sends no ``restored_from`` key at all."""
        payload = {"state": "trained", "final_metrics": {"r2": 0.9}, "stopped_reason": "converged", "events": []}
        status = _adapter(_responder(payload)).training_status()
        assert status.restored_from is None
        assert status.model_present is True

    def test_the_wait_alone_reaches_the_message_when_the_reply_has_no_detail(self):
        """The ``30`` comes from the header here: there is no detail to carry it."""
        error = _train_error(_rate_limited("30"))
        assert type(error) is RecurrenceServiceRateLimited
        assert str(error) == "recurrence service error 429 on POST /v1/train — retry after 30 s"

    def test_a_429_without_retry_after_is_rate_limited_with_the_generic_wording(self):
        error = _train_error(_rate_limited(None, {"detail": "Rate limit exceeded"}))
        assert type(error) is RecurrenceServiceRateLimited
        assert error.retry_after is None
        assert str(error) == "recurrence service error 429 on POST /v1/train: Rate limit exceeded"

    def test_an_http_date_retry_after_is_carried_as_sent(self):
        """RFC 9110 allows an HTTP-date; a proxy in front of the service may send one. It is not seconds, so no ``s``."""
        when = "Wed, 21 Oct 2015 07:28:00 GMT"
        error = _train_error(_rate_limited(when))
        assert error.retry_after == when
        assert str(error) == f"recurrence service error 429 on POST /v1/train — retry after {when}"

    @pytest.mark.parametrize("value", ["", "   ", "\t"])
    def test_a_blank_retry_after_counts_as_absent(self, value):
        error = _train_error(_rate_limited(value))
        assert error.retry_after is None
        assert str(error) == "recurrence service error 429 on POST /v1/train"

    def test_a_long_retry_after_is_flattened_and_bounded(self):
        error = _train_error(_rate_limited("in  a\twhile " + "x" * 500))
        assert error.retry_after.startswith("in a while x")
        assert len(error.retry_after) == 64
        assert error.retry_after.endswith("…"), "a cut value must show that it was cut"

    def test_the_status_route_is_rate_limited_too(self):
        """``_parse`` is shared, so ``GET /v1/training/status`` raises the same type with the same wait."""
        with pytest.raises(RecurrenceServiceRateLimited) as caught:
            _adapter(_rate_limited("7", {"detail": "Rate limit exceeded. Try again in 7 seconds."})).training_status()
        assert str(caught.value) == "recurrence service error 429 on GET /v1/training/status — retry after 7 s: Rate limit exceeded. Try again in 7 seconds."

    def test_rate_limited_round_trips_through_pickle_and_copy(self):
        """The base rebuilds from ``self.args``; the fourth value must survive the same way."""
        error = RecurrenceServiceRateLimited("limited", status_code=429, body="{}", retry_after="30")
        for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error)):
            assert type(clone) is RecurrenceServiceRateLimited
            assert (str(clone), clone.status_code, clone.body, clone.retry_after) == ("limited", 429, "{}", "30")

    def test_the_base_error_still_round_trips_with_its_three_values(self):
        """The base now forwards any values a subclass appends (``*extra``); a plain error keeps exactly three."""
        error = RecurrenceServiceError("refused", status_code=422, body="{}")
        assert error.args == ("refused", 422, "{}")
        for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error)):
            assert type(clone) is RecurrenceServiceError
            assert (str(clone), clone.status_code, clone.body, clone.args) == ("refused", 422, "{}", ("refused", 422, "{}"))

    def test_outbound_error_text_passes_the_wait_through(self):
        """The backend writes ``outbound_error_text(exc)`` into ``completion_reason``. A 429 is the service's answer, so it passes whole."""
        error = _train_error(_rate_limited("30", {"detail": _RATE_LIMITED_DETAIL}))
        assert outbound_error_text(error) == str(error)


_OPENAPI = {"openapi": "3.1.0", "info": {"title": "Juniper Recurrence", "version": "0.5.0"}, "paths": {}}


def _routed(routes, sink=None):
    """A MockTransport handler answering by path: ``routes`` maps a path to ``(status_code, json_payload)``; 404 otherwise."""

    def handler(request: httpx.Request) -> httpx.Response:
        if sink is not None:
            sink.append(request)
        status_code, payload = routes.get(request.url.path, (404, {"detail": "Not Found"}))
        return httpx.Response(status_code, json=payload)

    return handler


@pytest.mark.unit
class TestServiceVersion:
    """W1.7 / F-C8: the version is read from the service -- ``/v1/health``'s ``version``, else ``/openapi.json``'s ``info.version``."""

    def test_a_version_in_the_health_body_is_the_answer(self):
        sink = []
        adapter = _adapter(_routed({"/v1/health": (200, {"status": "ok", "version": "0.6.0"})}, sink=sink))
        assert adapter.service_version() == "0.6.0"
        assert [request.url.path for request in sink] == ["/v1/health"], "a health version needs no second call"

    def test_without_one_the_openapi_info_version_is_read(self):
        """juniper-recurrence 0.5.0's health body is ``{"status": "ok"}``, measured against the app in process."""
        sink = []
        adapter = _adapter(_routed({"/v1/health": (200, {"status": "ok"}), "/openapi.json": (200, _OPENAPI)}, sink=sink), api_key="k")
        assert adapter.service_version() == "0.5.0"
        assert [(request.method, request.url.path) for request in sink] == [("GET", "/v1/health"), ("GET", "/openapi.json")]
        assert sink[1].headers["X-API-Key"] == "k", "/openapi.json is authenticated under juniper-service-core 0.7.0"

    @pytest.mark.parametrize("health_version", ["", "   ", None, 6], ids=["empty", "blank", "null", "number"])
    def test_a_health_version_that_is_not_one_falls_through_to_openapi(self, health_version):
        adapter = _adapter(_routed({"/v1/health": (200, {"status": "ok", "version": health_version}), "/openapi.json": (200, _OPENAPI)}))
        assert adapter.service_version() == "0.5.0"

    def test_surrounding_whitespace_is_stripped(self):
        adapter = _adapter(_routed({"/v1/health": (200, {"status": "ok", "version": " 0.6.0\n"})}))
        assert adapter.service_version() == "0.6.0"

    @pytest.mark.parametrize(
        "openapi",
        [{}, {"info": "0.5.0"}, {"info": {}}, {"info": {"version": ""}}, {"info": {"version": 5}}],
        ids=["no-info", "info-not-an-object", "no-version", "blank-version", "number-version"],
    )
    def test_no_version_on_either_surface_raises(self, openapi):
        adapter = _adapter(_routed({"/v1/health": (200, {"status": "ok"}), "/openapi.json": (200, openapi)}))
        with pytest.raises(RecurrenceServiceError) as caught:
            adapter.service_version()
        assert type(caught.value) is RecurrenceServiceError
        assert caught.value.status_code is None
        assert str(caught.value) == "recurrence service reported no version on GET /v1/health or GET /openapi.json"

    def test_a_refused_key_on_openapi_is_an_auth_error(self):
        adapter = _adapter(_routed({"/v1/health": (200, {"status": "ok"}), "/openapi.json": (401, {"detail": "Invalid API key."})}))
        with pytest.raises(RecurrenceServiceAuthError) as caught:
            adapter.service_version()
        assert str(caught.value) == f"recurrence service rejected the request (401 on GET /openapi.json) — {_AUTH_REMEDY}: Invalid API key."

    def test_a_timeout_maps(self):
        def handler(request):
            raise httpx.ReadTimeout("read timed out", request=request)

        with pytest.raises(RecurrenceServiceTimeoutError):
            _adapter(handler).service_version()

    def test_the_contract_floor_is_0_5_0_and_the_docs_name_it(self):
        """The floor lives in two places -- the constant and the API reference -- so they are pinned together."""
        assert RECURRENCE_SERVICE_CONTRACT_FLOOR == "0.5.0"
        reference = (Path(__file__).resolve().parents[3] / "docs" / "api" / "API_REFERENCE.md").read_text(encoding="utf-8")
        assert f"juniper-recurrence {RECURRENCE_SERVICE_CONTRACT_FLOOR}" in reference
