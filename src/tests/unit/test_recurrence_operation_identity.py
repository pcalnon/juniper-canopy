#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_operation_identity.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# Last Modified: 2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   W1.5 canopy half, adapter level: the train request is
#                named (X-Request-ID), the service's operation identity
#                is read, a timed-out train is attributed by the status
#                (the four races), and a busy 409 names its holder.
#####################################################################
"""Adapter tests for W1.5's canopy half (F-C4, F-CON1, F-CON2).

Plan: juniper-ml ``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md``, the
W1.5 row and Details. The service half is juniper-recurrence#192 (``d20a581b``), whose wire shapes
``tests/fixtures/recurrence_service_fake.py`` mirrors. Every test drives the real ``RecurrenceServiceAdapter`` over an
``httpx.MockTransport``.

* ``TestTheFourRaces`` -- the plan's named races: timeout-then-success, timeout-then-failure, timeout-then-unreachable,
  and 409-from-another-caller.
* ``TestNeverSucceededBlindly`` -- a timed-out fit is ``succeeded`` only when the status names canopy's request AND that
  operation produced the model the service holds. ``trained`` alone, ``restored``, and a service without operation
  identity are each ``unknown``.
* ``TestTheBusy409`` -- the holder named, the old string detail of the published 0.5.0 still tolerated.
"""

import copy
import json
import pickle
import re

import httpx
import pytest

from backend.recurrence_service_adapter import (
    OUTCOME_FAILED,
    OUTCOME_RUNNING,
    OUTCOME_SUCCEEDED,
    OUTCOME_UNKNOWN,
    REQUEST_ID_HEADER,
    RecurrenceBusyHolder,
    RecurrenceServiceAdapter,
    RecurrenceServiceError,
    RecurrenceServiceTimeoutError,
    RecurrenceTrainInProgressError,
    new_request_id,
)
from frontend.dashboard_manager import DashboardManager
from outbound_errors import outbound_error_text
from tests.fixtures.recurrence_service_fake import (
    BUSY_409_0_5_0,
    BUSY_SINCE,
    DATASET_ID,
    EARLIER_OPERATION_ID,
    FINAL_METRICS,
    MINE,
    OPERATION_ID,
    OTHER_CALLER,
    OTHER_OPERATION_ID,
    TRAIN_OK,
    UNREACHABLE,
    FakeRecurrenceService,
    busy_409,
    status_body,
    status_body_0_5_0,
    status_failed,
    status_running,
    status_trained,
)

_NON_FINITE = "invalid dataset: X_train has non-finite values (NaN/Inf)"
_BUSY_REMEDY = "retry when it ends (a fit cannot be cancelled), or give canopy a service of its own"


def _timed_out_train(service):
    """Run a train against ``service`` whose reply times out; return ``(adapter, request_id)`` for the follow-up."""
    adapter = service.adapter()
    request_id = new_request_id()
    with pytest.raises(RecurrenceServiceTimeoutError) as caught:
        adapter.train(generator="equities_seq", request_id=request_id)
    assert caught.value.reply_pending is True, "a ReadTimeout means the request reached the service"
    assert service.request_ids == [request_id]
    return adapter, request_id


@pytest.mark.unit
class TestTheRequestIsNamed:
    """``POST /v1/train`` carries canopy's ``X-Request-ID``; the reply's ``operation_id`` is read."""

    def test_the_request_id_goes_out_as_x_request_id(self):
        service = FakeRecurrenceService()
        service.adapter().train(generator="equities_seq", request_id="juniper-canopy-abc")
        assert REQUEST_ID_HEADER == "X-Request-ID"
        assert service.requests[0].headers["X-Request-ID"] == "juniper-canopy-abc"

    def test_without_a_request_id_no_header_is_sent(self):
        service = FakeRecurrenceService()
        service.adapter().train(generator="equities_seq")
        assert "X-Request-ID" not in service.requests[0].headers

    def test_only_the_train_request_carries_it(self):
        service = FakeRecurrenceService(statuses=[status_trained()])
        adapter = service.adapter()
        adapter.train(generator="equities_seq", request_id="juniper-canopy-abc")
        adapter.training_status()
        assert "X-Request-ID" not in service.requests[1].headers

    def test_canopys_request_ids_name_canopy_and_never_repeat(self):
        ids = {new_request_id() for _ in range(200)}
        assert len(ids) == 200
        assert all(re.fullmatch(r"juniper-canopy-[0-9a-f]{32}", request_id) for request_id in ids)

    def test_the_fits_operation_id_is_read_from_the_reply(self):
        result = FakeRecurrenceService().adapter().train(generator="equities_seq")
        assert result.operation_id == OPERATION_ID
        assert result.final_metrics == FINAL_METRICS

    def test_a_reply_without_one_has_none(self):
        """juniper-recurrence 0.5.0 -- the contract floor -- mints no operation id."""
        reply = {key: value for key, value in TRAIN_OK.items() if key != "operation_id"}
        result = FakeRecurrenceService(train=httpx.Response(200, json=reply)).adapter().train(generator="equities_seq")
        assert result.operation_id is None


@pytest.mark.unit
class TestTheStatusSaysWhoseOperation:
    """``GET /v1/training/status``: juniper-recurrence#192's identity fields parse; 0.5.0's absence of them is told apart."""

    def test_every_identity_field_parses(self):
        body = status_running(requested_by=OTHER_CALLER)
        status = FakeRecurrenceService(statuses=[body]).adapter().training_status()
        assert (status.state, status.operation_id, status.operation, status.busy_since) == ("training", OPERATION_ID, "train", BUSY_SINCE)
        assert (status.dataset_id, status.requested_by, status.model_operation_id) == (DATASET_ID, OTHER_CALLER, EARLIER_OPERATION_ID)
        assert status.reports_operations is True
        assert status.model_present is False, "a fit in flight is not a model"

    def test_a_failed_status_carries_its_failure(self):
        status = FakeRecurrenceService(statuses=[status_failed(_NON_FINITE, 422)]).adapter().training_status()
        assert status.state == "failed"
        assert (status.failure.detail, status.failure.status_code) == (_NON_FINITE, 422)

    def test_an_idle_service_still_reports_operations(self):
        """#192 sends ``operation_id: null`` while idle: the key's presence, not its value, says the service has identity."""
        body = status_body("idle", requested_by=None, operation=None, operation_id=None, dataset_id=None)
        status = FakeRecurrenceService(statuses=[body]).adapter().training_status()
        assert status.reports_operations is True
        assert status.operation_id is None

    def test_a_0_5_0_status_reports_no_operations(self):
        status = FakeRecurrenceService(statuses=[status_body_0_5_0("trained")]).adapter().training_status()
        assert status.state == "trained" and status.model_present is True
        assert status.reports_operations is False
        assert (status.operation_id, status.requested_by, status.model_operation_id, status.failure) == (None, None, None, None)

    def test_requested_by_is_kept_exactly_as_sent(self):
        """It is compared with the id canopy sent, character for character, so nothing may normalise it."""
        status = FakeRecurrenceService(statuses=[status_running(requested_by=" padded ")]).adapter().training_status()
        assert status.requested_by == " padded "


@pytest.mark.unit
class TestTheFourRaces:
    """W1.5's four races, at the adapter: a timed-out train, then what ``train_outcome`` makes of the status."""

    def test_race_timeout_then_success(self):
        service = FakeRecurrenceService(train="timeout", statuses=[status_trained()])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_SUCCEEDED
        assert outcome.reason == f"succeeded (upstream): the service finished canopy's fit after the request timed out (operation {OPERATION_ID})"
        result = outcome.result
        assert result.operation_id == OPERATION_ID
        assert result.final_metrics == FINAL_METRICS
        assert result.stopped_reason == "converged"
        assert result.n_epochs == 1, "read from the last epoch_end event, which counts from 0"
        assert result.dataset == {"dataset_id": DATASET_ID}
        assert service.paths() == ["POST /v1/train", "GET /v1/training/status"]

    def test_race_timeout_then_failure(self):
        service = FakeRecurrenceService(train="timeout", statuses=[status_failed(_NON_FINITE, 422)])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_FAILED
        assert outcome.reason == f"recurrence service error 422 on POST /v1/train, reported by GET /v1/training/status after the request timed out: {_NON_FINITE}"
        assert (outcome.failure.detail, outcome.failure.status_code) == (_NON_FINITE, 422)
        assert outcome.result is None

    def test_race_timeout_then_unreachable(self):
        service = FakeRecurrenceService(train="timeout", statuses=[UNREACHABLE])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_UNKNOWN
        assert outcome.reason == "unknown (upstream unreachable): canopy could not reach GET /v1/training/status after its POST /v1/train timed out, so it cannot tell whether the fit finished"
        assert outcome.result is None and outcome.status is None
        assert type(outcome.error).__name__ == "RecurrenceServiceUnavailableError"

    def test_race_409_from_another_caller(self):
        service = FakeRecurrenceService(train=httpx.Response(409, json=busy_409()))
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            service.adapter().train(generator="equities_seq", request_id=new_request_id())
        error = caught.value
        assert error.status_code == 409
        assert error.holder == RecurrenceBusyHolder(message="a training run is already in progress", operation_id=OTHER_OPERATION_ID, operation="train", busy_since=BUSY_SINCE, requested_by=OTHER_CALLER, dataset_id=DATASET_ID)
        holder = f"a training run is already in progress (train operation {OTHER_OPERATION_ID} since {BUSY_SINCE}, requested by {OTHER_CALLER}, dataset {DATASET_ID})"
        assert str(error) == f"recurrence training already in progress (POST /v1/train) — {_BUSY_REMEDY}: {holder}"

    @pytest.mark.parametrize(
        "events, n_epochs",
        [
            ([], 0),
            ([{"type": "epoch_end", "seq": 1, "payload": {"epoch": True}}], 0),
            ([{"type": "epoch_end", "seq": 1, "payload": {"epoch": "4"}}], 0),
            ([{"type": "epoch_end", "seq": 1, "payload": {"epoch": -1}}], 0),
            ([{"type": "epoch_end", "seq": 1, "payload": None}, {"type": "training_end", "seq": 2, "payload": {"epoch": 9}}], 0),
            ([{"type": "epoch_end", "seq": 1, "payload": {"epoch": 0}}, {"type": "epoch_end", "seq": 2, "payload": {"epoch": 41}}], 42),
        ],
        ids=["no-events", "bool-epoch", "string-epoch", "negative-epoch", "no-epoch-end-payload", "the-last-epoch-end-counts"],
    )
    def test_a_recovered_fit_counts_epochs_only_from_its_epoch_end_events(self, events, n_epochs):
        """The status carries no epoch count: it is read from the events, and never guessed (0, as for a reply without it)."""
        service = FakeRecurrenceService(train="timeout", statuses=[status_trained(events=events)])
        adapter, request_id = _timed_out_train(service)
        assert adapter.train_outcome(request_id).result.n_epochs == n_epochs

    def test_timeout_then_still_running(self):
        service = FakeRecurrenceService(train="timeout", statuses=[status_running()])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_RUNNING
        assert outcome.reason == f"running (upstream): the service is still fitting canopy's request (operation {OPERATION_ID} since {BUSY_SINCE}); a fit cannot be cancelled"
        assert outcome.result is None

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_a_5xx_failure_keeps_its_detail_off_the_reason(self, status_code):
        """Exactly ``_parse``'s rule: a 5xx detail can relay the service's own upstream text, which can quote a key."""
        relayed = "data fetch failed: Request failed: Invalid leading whitespace ... in header value: ' LEAKME-w15'"
        service = FakeRecurrenceService(train="timeout", statuses=[status_failed(relayed, status_code)])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_FAILED
        assert outcome.reason == f"recurrence service error {status_code} on POST /v1/train, reported by GET /v1/training/status after the request timed out"
        assert "LEAKME" not in outcome.reason

    def test_a_long_4xx_failure_detail_is_flattened_and_bounded_as_parse_does(self):
        service = FakeRecurrenceService(train="timeout", statuses=[status_failed("x\n" * 400, 422)])
        adapter, request_id = _timed_out_train(service)
        reason = adapter.train_outcome(request_id).reason
        detail = reason.split("after the request timed out: ", 1)[1]
        assert len(detail) == 300 and detail.endswith("…") and "\n" not in detail

    def test_a_connect_timeout_never_reached_the_service(self):
        service = FakeRecurrenceService(train="connect-timeout")
        with pytest.raises(RecurrenceServiceTimeoutError) as caught:
            service.adapter().train(generator="equities_seq", request_id=new_request_id())
        assert caught.value.reply_pending is False

    def test_reply_pending_survives_pickle_and_copy(self):
        error = RecurrenceServiceTimeoutError("timed out", reply_pending=True)
        for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error)):
            assert type(clone) is RecurrenceServiceTimeoutError
            assert (str(clone), clone.status_code, clone.reply_pending) == ("timed out", None, True)


@pytest.mark.unit
class TestNeverSucceededBlindly:
    """Only canopy's own operation, having produced the model the service holds, is a success (W1.5 Details)."""

    @pytest.mark.parametrize(
        "status, label",
        [
            # Another caller's fit finished: ``trained`` and a model present -- not canopy's.
            (status_trained(requested_by=OTHER_CALLER, operation_id=OTHER_OPERATION_ID, model_operation_id=OTHER_OPERATION_ID), "another operation since"),
            # A snapshot restore since: a model present (``restored`` counts, W1.6) -- never a fit at all.
            (status_body("restored", requested_by=None, operation="restore", operation_id=OTHER_OPERATION_ID, model_operation_id=OTHER_OPERATION_ID, dataset_id=None, restored_from="snap-0001"), "another operation since"),
            # A restore carrying canopy's own id is still no fit: the operation must be a train.
            (status_body("restored", operation="restore", operation_id=OTHER_OPERATION_ID, model_operation_id=OTHER_OPERATION_ID, restored_from="snap-0001"), "another operation since"),
            # Another caller's fit is running now: canopy's ended at some point before it, unseen.
            (status_running(requested_by=OTHER_CALLER, operation_id=OTHER_OPERATION_ID), "another operation since"),
            # The service restarted: no operation on record, its model and canopy's fit gone.
            (status_body("idle", requested_by=None, operation=None, operation_id=None, dataset_id=None), "no operation on record"),
            # canopy's operation, ``trained``, but the model is someone else's: not attributable.
            (status_trained(model_operation_id=OTHER_OPERATION_ID), "outcome not attributable"),
            # canopy's operation, ``trained``, with no model named at all.
            (status_trained(model_operation_id=None), "outcome not attributable"),
            # juniper-recurrence 0.5.0: ``trained`` with a model, and nothing saying whose.
            (status_body_0_5_0("trained"), "no operation identity"),
        ],
        ids=["another-callers-fit", "a-restore", "a-restore-with-canopys-id", "another-fit-running", "service-restarted", "model-from-another-operation", "no-model-named", "0.5.0-service"],
    )
    def test_anything_less_is_unknown(self, status, label):
        service = FakeRecurrenceService(train="timeout", statuses=[status])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_UNKNOWN
        assert outcome.result is None
        assert outcome.reason.startswith(f"unknown ({label}): ")
        assert outcome.reason.endswith("canopy cannot tell whether its fit finished")

    def test_another_callers_operation_is_named(self):
        service = FakeRecurrenceService(train="timeout", statuses=[status_trained(requested_by=OTHER_CALLER, operation_id=OTHER_OPERATION_ID, model_operation_id=OTHER_OPERATION_ID)])
        adapter, request_id = _timed_out_train(service)
        reason = adapter.train_outcome(request_id).reason
        assert reason == f"unknown (another operation since): the status describes train operation {OTHER_OPERATION_ID} (trained, requested by {OTHER_CALLER}), not canopy's request {request_id}; canopy cannot tell whether its fit finished"

    def test_trained_alone_never_settles_it(self):
        """The bug the plan names: reading ``state == "trained"`` and calling it canopy's success."""
        service = FakeRecurrenceService(train="timeout", statuses=[status_trained(requested_by=OTHER_CALLER)])
        adapter, request_id = _timed_out_train(service)
        status = adapter.training_status()
        assert status.state == "trained" and status.model_present, "the status alone looks like success"
        assert adapter.train_outcome(request_id).state == OUTCOME_UNKNOWN

    @pytest.mark.parametrize(
        "answer, rendered",
        [
            (httpx.Response(429, json={"detail": "Rate limit exceeded"}, headers={"Retry-After": "12"}), "recurrence service error 429 on GET /v1/training/status — retry after 12 s: Rate limit exceeded"),
            (httpx.Response(500, json={"detail": "internal LEAKME-500"}), "recurrence service error 500 on GET /v1/training/status"),
            (httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"}), "recurrence service returned a non-JSON body on GET /v1/training/status"),
        ],
        ids=["429", "500", "non-json"],
    )
    def test_an_unreadable_status_is_unknown_with_the_services_answer(self, answer, rendered):
        service = FakeRecurrenceService(train="timeout", statuses=[answer])
        adapter, request_id = _timed_out_train(service)

        outcome = adapter.train_outcome(request_id)

        assert outcome.state == OUTCOME_UNKNOWN
        assert outcome.reason == f"unknown (upstream status unreadable): {rendered}"
        assert isinstance(outcome.error, RecurrenceServiceError)

    def test_a_status_poll_that_times_out_is_unreachable(self):
        def handler(request):
            if request.url.path == "/v1/train":
                raise httpx.ReadTimeout("timed out", request=request)
            raise httpx.ReadTimeout("timed out again", request=request)

        adapter = RecurrenceServiceAdapter("http://recurrence.test:8210", transport=httpx.MockTransport(handler))
        outcome = adapter.train_outcome(new_request_id())
        assert outcome.state == OUTCOME_UNKNOWN
        assert outcome.reason.startswith("unknown (upstream unreachable): ")
        assert isinstance(outcome.error, RecurrenceServiceTimeoutError)

    def test_the_unreachable_reason_never_carries_transport_text(self):
        """The reason reaches ``completion_reason``; httpx's text can quote a header value (#683)."""

        def handler(request):
            if request.url.path == "/v1/train":
                raise httpx.ReadTimeout("timed out", request=request)
            raise httpx.ConnectError("Illegal header value b' LEAKME-w15'", request=request)

        adapter = RecurrenceServiceAdapter("http://recurrence.test:8210", transport=httpx.MockTransport(handler))
        outcome = adapter.train_outcome(new_request_id())
        assert "LEAKME" not in outcome.reason
        assert "LEAKME" in str(outcome.error), "the full text stays on the exception, for the log"


@pytest.mark.unit
class TestTheBusy409:
    """A busy 409 names its holder (F-CON1); juniper-recurrence 0.5.0's string detail is still read as before."""

    def test_the_old_string_detail_is_tolerated_unchanged(self):
        """The published 0.5.0 sends a string. The message is exactly the pre-W1.5 one, and there is no holder."""
        raw = json.dumps(BUSY_409_0_5_0)
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, content=raw.encode(), headers={"content-type": "application/json"}), "POST", "/v1/train")
        assert str(caught.value) == "recurrence training already in progress (POST /v1/train): a training run is already in progress"
        assert caught.value.holder is None
        assert caught.value.body == raw

    def test_a_restore_holder_is_named_as_one(self):
        body = busy_409(message="a snapshot restore is in progress", operation="restore", requested_by=None, dataset_id=None)
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, json=body), "POST", "/v1/train")
        assert str(caught.value).endswith(f": a snapshot restore is in progress (restore operation {OTHER_OPERATION_ID} since {BUSY_SINCE})")

    def test_a_holder_the_service_could_not_name_still_reads(self):
        """The service nulls the holder's fields when its lock was taken outside the API."""
        body = {"detail": {"message": "a training run is already in progress", "operation_id": None, "operation": None, "busy_since": None, "requested_by": None, "dataset_id": None}}
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, json=body), "POST", "/v1/train")
        assert str(caught.value) == f"recurrence training already in progress (POST /v1/train) — {_BUSY_REMEDY}: a training run is already in progress"
        assert caught.value.holder == RecurrenceBusyHolder(message="a training run is already in progress")

    @pytest.mark.parametrize(
        "holder, described",
        [
            (RecurrenceBusyHolder(message="busy", busy_since=BUSY_SINCE), f"busy (since {BUSY_SINCE})"),
            (RecurrenceBusyHolder(message="busy", operation_id=OTHER_OPERATION_ID), f"busy (an operation {OTHER_OPERATION_ID})"),
            (RecurrenceBusyHolder(message="busy", operation="restore"), "busy (restore operation)"),
            (RecurrenceBusyHolder(message="", requested_by=OTHER_CALLER), f"the service is busy (requested by {OTHER_CALLER})"),
        ],
        ids=["start-time-only", "id-only", "kind-only", "no-message"],
    )
    def test_a_partly_known_holder_names_what_is_known(self, holder, described):
        assert holder.describe() == described

    def test_another_409_object_is_not_a_holder(self):
        """``/v1/predict``'s ``expect_operation_id`` mismatch is a 409 object too, but it names no holder."""
        body = {"detail": {"message": "expected operation x, model is y", "expected_operation_id": "x", "model_operation_id": "y"}}
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, json=body), "POST", "/v1/predict")
        assert caught.value.holder is None
        assert str(caught.value).startswith("recurrence training already in progress (POST /v1/predict): {")

    def test_another_callers_fields_are_flattened_and_bounded(self):
        """``requested_by`` is whatever ``X-Request-ID`` another caller chose to send."""
        body = busy_409(requested_by="line one\nline two " + "r" * 500, dataset_id="d" * 500)
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, json=body), "POST", "/v1/train")
        message = str(caught.value)
        assert "\n" not in message
        requested_by = message.split("requested by ", 1)[1].split(", dataset ", 1)[0]
        assert requested_by.startswith("line one line two r") and len(requested_by) == 64 and requested_by.endswith("…")
        assert caught.value.holder.requested_by.startswith("line one\nline two"), "the holder keeps the value as sent"

    def test_the_whole_holder_is_bounded_like_any_detail(self):
        body = busy_409(message="m" * 1000)
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, json=body), "POST", "/v1/train")
        rendered = str(caught.value).split(f"{_BUSY_REMEDY}: ", 1)[1]
        assert len(rendered) == 300 and rendered.endswith("…")

    def test_the_longest_409_fits_the_status_bar_hover_uncut(self):
        """The status bar's hover holds 480 characters (``_FAILURE_REASON_TOOLTIP_MAX_CHARS``): the 409 must fit whole."""
        body = busy_409(message="m" * 5000, requested_by="r" * 5000, dataset_id="d" * 5000)
        with pytest.raises(RecurrenceTrainInProgressError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(409, json=body), "POST", "/v1/train")
        reason = outbound_error_text(caught.value)
        assert reason == str(caught.value), "a 409 is the service's answer: it passes whole"
        assert len(reason) > DashboardManager._COMPLETION_REASON_MAX_CHARS, "the label must cut this reason"
        assert DashboardManager._failure_reason_tooltip(reason) == reason, "the hover must not"

    def test_the_holder_survives_pickle_and_copy(self):
        holder = RecurrenceBusyHolder(message="busy", operation_id=OTHER_OPERATION_ID, operation="train", busy_since=BUSY_SINCE, requested_by=OTHER_CALLER, dataset_id=DATASET_ID)
        error = RecurrenceTrainInProgressError("busy", status_code=409, body="{}", holder=holder)
        for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error)):
            assert type(clone) is RecurrenceTrainInProgressError
            assert (str(clone), clone.status_code, clone.body, clone.holder) == ("busy", 409, "{}", holder)


@pytest.mark.unit
class TestOutcomeReasonsFitTheHover:
    """An outcome's reason becomes ``completion_reason``; the longest ones must still fit the status bar's hover whole."""

    def test_the_longest_another_operation_reason_fits(self):
        status = status_trained(requested_by="r" * 5000, operation="o" * 5000, operation_id="i" * 5000, model_operation_id="i" * 5000)
        status["state"] = "s" * 5000
        service = FakeRecurrenceService(train="timeout", statuses=[status])
        adapter, request_id = _timed_out_train(service)
        reason = adapter.train_outcome(request_id).reason
        assert reason.startswith("unknown (another operation since): ")
        assert DashboardManager._failure_reason_tooltip(reason) == reason

    def test_the_longest_failure_reason_fits(self):
        service = FakeRecurrenceService(train="timeout", statuses=[status_failed("d" * 5000, 422)])
        adapter, request_id = _timed_out_train(service)
        reason = adapter.train_outcome(request_id).reason
        assert DashboardManager._failure_reason_tooltip(reason) == reason

    def test_mine_is_the_fakes_stand_in_and_never_a_real_id(self):
        """Guard on the fixture itself: ``MINE`` is replaced by the id sent, so a test can never match it by accident."""
        assert not re.fullmatch(r"juniper-canopy-[0-9a-f]{32}", MINE)
