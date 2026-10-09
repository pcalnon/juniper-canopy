#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_backend_upstream.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-10-08
# Last Modified: 2026-10-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   W1.5 canopy half, backend level: a fit whose reply
#                times out is followed on the service's status, never
#                recorded as failed or succeeded blindly; what the
#                operator reads for each of the four races.
#####################################################################
"""Backend tests for W1.5's canopy half (F-C4): the four races as the operator sees them.

Plan: juniper-ml ``notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md``, W1.5.
Before this, a fit whose ``POST /v1/train`` outlived the adapter's 300 s read timeout was recorded ``failed`` with the
reason ``RecurrenceServiceTimeoutError`` -- while the service, which cannot cancel a fit, went on fitting, often to
success, and answered canopy's next Start with a 409 from a lock canopy believed free.

Each test drives a real ``RecurrenceBackend`` over the real ``RecurrenceServiceAdapter`` and the fake service of
``tests/fixtures/recurrence_service_fake.py`` (juniper-recurrence#192's wire shapes), and reads the result where the
operator reads it: ``get_status()`` -- which ``/api/status`` serves for recurrence -- and the status bar.
"""

import asyncio
import logging
import threading
import time
from unittest.mock import Mock

import httpx
import pytest
from dash import html

from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceServiceTimeoutError
from frontend.dashboard_manager import DashboardManager
from tests.fixtures.recurrence_service_fake import (
    BUSY_409_0_5_0,
    BUSY_SINCE,
    FINAL_METRICS,
    OPERATION_ID,
    OTHER_CALLER,
    OTHER_OPERATION_ID,
    UNREACHABLE,
    FakeRecurrenceService,
    busy_409,
    status_body_0_5_0,
    status_failed,
    status_running,
    status_trained,
)

_BACKEND_LOGGER = "juniper_canopy.backend.recurrence_backend"
_NON_FINITE = "invalid dataset: X_train has non-finite values (NaN/Inf)"
_BUSY_REMEDY = "retry when it ends (a fit cannot be cancelled), or give canopy a service of its own"
_FIT_THREAD_NAME = "recurrence-fit"
_JOIN_SECONDS = 5.0


@pytest.fixture(autouse=True)
def _join_recurrence_fit_threads():
    """Join every fit thread after each test, so a late log record cannot land in the next test's ``caplog``.

    The same guard as ``test_recurrence_backend.py``'s: a fit settles its state under the lock and logs after it.
    """
    yield
    deadline = time.monotonic() + _JOIN_SECONDS
    for thread in threading.enumerate():
        if thread.name == _FIT_THREAD_NAME:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))


@pytest.fixture
def dashboard_manager():
    """Minimal DashboardManager for direct status-bar calls."""
    return DashboardManager({"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}})


def _backend(service, *, reconcile_timeout=5.0):
    """A real backend over the real adapter, polling the fake every 10 ms."""
    return RecurrenceBackend(service.adapter(), reconcile_interval=0.01, reconcile_timeout=reconcile_timeout)


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _fit(backend):
    """Start a fit and wait until it has settled one way or another."""
    assert backend.start_training(generator="equities_seq")["ok"] is True
    assert _wait_until(lambda: not backend.is_training_active()), "the fit never settled"
    return backend.get_status()


def _status_bar(dashboard_manager, status):
    """The status bar's (text, tooltip, style) for ``status``, as ``/api/status`` would serve it."""
    response = Mock()
    response.json.return_value = status
    result = dashboard_manager._build_unified_status_bar_content(response, latency_ms=50)
    display = result[3]
    if isinstance(display, html.Span):
        return display.children, display.title, result[4]
    return display, None, result[4]


@pytest.mark.unit
class TestTheFourRacesReachTheOperator:
    """W1.5's four races, end to end: what ``get_status()`` and the status bar say."""

    def test_race_timeout_then_success(self, dashboard_manager):
        service = FakeRecurrenceService(train="timeout", statuses=[status_running(), status_running(), status_trained()])
        backend = _backend(service)

        status = _fit(backend)

        assert (status["completed"], status["failed"], status["fsm_status"], status["phase"]) == (True, False, "trained", "complete")
        assert "outcome_unknown" not in status
        assert status["operation_id"] == OPERATION_ID
        assert status["completion_reason"] == "converged"
        assert status["current_epoch"] == 1
        assert backend.get_metrics()["r2"] == pytest.approx(FINAL_METRICS["r2"])
        assert backend.has_network() is True
        # One train, then status reads until the service said "trained, by canopy's request".
        assert service.paths() == ["POST /v1/train"] + ["GET /v1/training/status"] * 3
        text, _, _ = _status_bar(dashboard_manager, status)
        assert text == "Completed — converged"

    def test_race_timeout_then_failure(self, dashboard_manager):
        service = FakeRecurrenceService(train="timeout", statuses=[status_running(), status_failed(_NON_FINITE, 422)])
        backend = _backend(service)

        status = _fit(backend)

        reason = f"recurrence service error 422 on POST /v1/train, reported by GET /v1/training/status after the request timed out: {_NON_FINITE}"
        assert (status["failed"], status["completed"], status["fsm_status"]) == (True, False, "failed")
        assert status["completion_reason"] == reason
        assert "outcome_unknown" not in status
        assert backend.has_network() is False
        text, tooltip, style = _status_bar(dashboard_manager, status)
        assert text.startswith("Failed — recurrence service error 422 on POST /v1/train, reported by")
        assert tooltip == reason, "the detail is at the end of the reason, which the label cuts"
        assert style["color"] == "#dc3545"

    def test_race_timeout_then_unreachable(self, dashboard_manager):
        service = FakeRecurrenceService(train="timeout", statuses=[UNREACHABLE])
        backend = _backend(service)

        status = _fit(backend)

        assert status["outcome_unknown"] is True
        assert (status["failed"], status["completed"], status["fsm_status"], status["phase"]) == (False, False, "unknown", "unknown")
        assert status["completion_reason"] == "unknown (upstream unreachable): canopy could not reach GET /v1/training/status after its POST /v1/train timed out, so it cannot tell whether the fit finished"
        assert backend.has_network() is False and backend.get_metrics() == {}
        text, tooltip, style = _status_bar(dashboard_manager, status)
        assert text.startswith("Unknown — unknown (upstream unreachable): ")
        assert tooltip == status["completion_reason"]
        assert style["color"] == "#fd7e14"

    def test_race_409_from_another_caller(self, dashboard_manager):
        service = FakeRecurrenceService(train=httpx.Response(409, json=busy_409()))
        backend = _backend(service)

        status = _fit(backend)

        reason = status["completion_reason"]
        assert status["failed"] is True
        assert reason.startswith(f"recurrence training already in progress (POST /v1/train) — {_BUSY_REMEDY}: ")
        for named in (OTHER_OPERATION_ID, BUSY_SINCE, OTHER_CALLER, "train operation"):
            assert named in reason
        assert service.paths() == ["POST /v1/train"], "a refused fit never ran, so there is nothing to follow"
        text, tooltip, _ = _status_bar(dashboard_manager, status)
        assert text.startswith("Failed — recurrence training already in progress (POST /v1/train) — retry when it ends")
        assert tooltip == reason, "the holder rides whole on the hover"


@pytest.mark.unit
class TestFollowingAFitUpstream:
    """The state while canopy follows a fit, and every way the following ends."""

    def test_while_followed_the_fit_is_running_upstream(self):
        backend = _backend(FakeRecurrenceService(train="timeout", statuses=[status_running()]), reconcile_timeout=60.0)
        assert backend.start_training(generator="equities_seq")["ok"] is True
        assert _wait_until(lambda: backend.get_status()["phase"] == "fitting (upstream)")

        status = backend.get_status()
        assert (status["is_training"], status["is_running"], status["fsm_status"]) == (True, True, "training")
        # The service would refuse a second fit with a 409; canopy refuses it first, and a reset with it.
        second = backend.start_training(generator="equities_seq")
        assert second["ok"] is False and "already in progress" in second["error"]
        assert backend.reset_training()["ok"] is False
        assert backend.is_training_active() is True, "a model swap reads this, and is refused too"

        asyncio.run(backend.shutdown())
        assert _wait_until(lambda: not backend.is_training_active())
        status = backend.get_status()
        assert status["outcome_unknown"] is True
        assert status["completion_reason"].startswith("unknown (no longer followed): canopy's recurrence backend shut down before the service reported how its request juniper-canopy-")

    def test_the_window_closing_is_unknown_never_success(self):
        backend = _backend(FakeRecurrenceService(train="timeout", statuses=[status_running()]), reconcile_timeout=0.05)

        status = _fit(backend)

        assert status["outcome_unknown"] is True and status["completed"] is False
        assert status["completion_reason"].startswith("unknown (still running upstream): the service was still fitting canopy's request juniper-canopy-")
        assert "after 0.05 s" in status["completion_reason"]

    def test_a_single_unreadable_read_is_not_a_verdict(self):
        """One network blip during a long fit: the next read finds canopy's fit finished."""
        service = FakeRecurrenceService(train="timeout", statuses=[UNREACHABLE, status_trained()])
        status = _fit(_backend(service))
        assert status["completed"] is True and "outcome_unknown" not in status
        assert service.paths() == ["POST /v1/train"] + ["GET /v1/training/status"] * 2

    def test_three_unreadable_reads_in_a_row_settle_it_unknown(self):
        service = FakeRecurrenceService(train="timeout", statuses=[UNREACHABLE])
        status = _fit(_backend(service))
        assert status["outcome_unknown"] is True
        assert status["completion_reason"].startswith("unknown (upstream unreachable): ")
        assert service.paths() == ["POST /v1/train"] + ["GET /v1/training/status"] * 3

    def test_a_read_that_answers_resets_the_count(self):
        """Two failed reads, an answer, two more failed reads: never three in a row, so the fit is still followed."""
        statuses = [UNREACHABLE, UNREACHABLE, status_running(), UNREACHABLE, UNREACHABLE, status_trained()]
        service = FakeRecurrenceService(train="timeout", statuses=statuses)
        status = _fit(_backend(service))
        assert status["completed"] is True
        assert service.paths() == ["POST /v1/train"] + ["GET /v1/training/status"] * 6

    def test_the_window_closing_after_a_failed_read_says_the_read_failed(self):
        """Not "still running upstream": the last read could not say whether it was."""
        status = _fit(_backend(FakeRecurrenceService(train="timeout", statuses=[UNREACHABLE]), reconcile_timeout=0.0))
        assert status["outcome_unknown"] is True
        assert status["completion_reason"].startswith("unknown (upstream unreachable): ")

    def test_another_callers_model_after_a_timeout_is_not_canopys(self):
        """``trained`` with a model present -- but the status names another caller's request. Never ``succeeded``."""
        service = FakeRecurrenceService(train="timeout", statuses=[status_trained(requested_by=OTHER_CALLER, operation_id=OTHER_OPERATION_ID, model_operation_id=OTHER_OPERATION_ID)])
        status = _fit(_backend(service))
        assert status["outcome_unknown"] is True and status["completed"] is False
        assert status["completion_reason"].startswith("unknown (another operation since): ")
        assert "operation_id" not in status

    def test_a_0_5_0_service_after_a_timeout_is_unknown(self):
        status = _fit(_backend(FakeRecurrenceService(train="timeout", statuses=[status_body_0_5_0("trained")])))
        assert status["outcome_unknown"] is True and status["completed"] is False
        assert status["completion_reason"].startswith("unknown (no operation identity): ")

    def test_a_connect_timeout_fails_without_following(self):
        """The request never reached the service, so there is no fit to follow: failed, as before W1.5."""
        service = FakeRecurrenceService(train="connect-timeout")
        status = _fit(_backend(service))
        assert status["failed"] is True
        assert status["completion_reason"] == "RecurrenceServiceTimeoutError", "transport text stays off the field (#683)"
        assert service.paths() == ["POST /v1/train"]

    def test_a_follow_up_that_crashes_is_unknown_not_stuck(self, caplog):
        class _BrokenFollowUp:
            def train(self, **kwargs):
                raise RecurrenceServiceTimeoutError("recurrence service timed out on POST /v1/train: timed out", reply_pending=True)

            def train_outcome(self, request_id):
                raise RuntimeError("unexpected")

        backend = RecurrenceBackend(_BrokenFollowUp(), reconcile_interval=0.01)
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            status = _fit(backend)
        assert status["outcome_unknown"] is True
        assert status["completion_reason"].startswith("unknown (follow-up failed): ")
        assert any(record.levelno == logging.ERROR and "crashed" in record.getMessage() for record in caplog.records)

    def test_reset_after_an_unknown_outcome_returns_to_idle(self):
        backend = _backend(FakeRecurrenceService(train="timeout", statuses=[UNREACHABLE]))
        assert _fit(backend)["outcome_unknown"] is True
        assert backend.reset_training()["ok"] is True
        status = backend.get_status()
        assert status["fsm_status"] == "idle" and "outcome_unknown" not in status and "completion_reason" not in status

    def test_the_timeout_and_the_outcome_are_logged(self, caplog):
        backend = _backend(FakeRecurrenceService(train="timeout", statuses=[status_failed(_NON_FINITE, 422)]))
        with caplog.at_level(logging.WARNING, logger=_BACKEND_LOGGER):
            _fit(backend)
            assert _wait_until(lambda: len([r for r in caplog.records if r.name == _BACKEND_LOGGER]) >= 2)
        messages = [record.getMessage() for record in caplog.records if record.name == _BACKEND_LOGGER]
        assert messages[0].startswith("recurrence fit: no reply to POST /v1/train within its read timeout (request juniper-canopy-")
        assert messages[1].startswith("recurrence fit failed after its reply timed out: recurrence service error 422 on POST /v1/train")


@pytest.mark.unit
class TestEveryFitIsNamed:
    """Each fit sends its own ``X-Request-ID``, and a fit that answers in time records its ``operation_id``."""

    def test_each_fit_sends_its_own_request_id(self):
        service = FakeRecurrenceService()
        backend = _backend(service)
        _fit(backend)
        _fit(backend)
        first, second = service.request_ids
        assert first.startswith("juniper-canopy-") and second.startswith("juniper-canopy-") and first != second

    def test_a_fit_that_answers_in_time_records_its_operation_id(self):
        service = FakeRecurrenceService()
        status = _fit(_backend(service))
        assert status["completed"] is True
        assert status["operation_id"] == OPERATION_ID
        assert service.paths() == ["POST /v1/train"], "a reply that arrived needs no status read"

    def test_the_old_string_409_still_fails_with_its_old_wording(self):
        """juniper-recurrence 0.5.0, the published floor: a string detail, read exactly as before W1.5."""
        status = _fit(_backend(FakeRecurrenceService(train=httpx.Response(409, json=BUSY_409_0_5_0))))
        assert status["failed"] is True
        assert status["completion_reason"] == "recurrence training already in progress (POST /v1/train): a training run is already in progress"
