#!/usr/bin/env python
"""Unit tests for the canopy status-bar ``completion_reason`` consumer (Issue #3 follow-up).

cascor #320 surfaces a ``grow_network`` ``completion_reason`` on ``/api/status``;
``service_backend`` carries it through and ``_build_unified_status_bar_content``
appends it to a *completed* run's status ("Completed — converged" vs
"Completed — stalled (0 new units)"). These pin the label mapping and the
augmentation (only when completed, only when the reason is present/known).

``TestFailedRecurrenceFitReason`` and ``TestA422ReachesTheStatusBar`` pin W0.5 / F-C1: a
failed recurrence fit's reason -- the service's 422 ``detail`` included -- reaches the bar,
and a reason too long for the bar's label rides whole on a hover tooltip. W1.6 lengthened two
of those reasons (a 401's key variables, a 429's ``Retry-After``); the tooltip bound holds both.
"""

import time
from unittest.mock import Mock

import httpx
import pytest
from dash import html

from backend.recurrence_backend import RecurrenceBackend
from backend.recurrence_service_adapter import RecurrenceServiceAdapter, RecurrenceServiceError, RecurrenceServiceRateLimited
from frontend.dashboard_manager import DashboardManager
from outbound_errors import outbound_error_text


@pytest.fixture
def dashboard_manager():
    """Minimal DashboardManager for direct handler calls."""
    config = {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
    return DashboardManager(config)


def _status_response(**overrides):
    """A minimal completed-run /api/status payload, with overrides applied."""
    data = {
        "is_running": False,
        "is_paused": False,
        "completed": True,
        "failed": False,
        "phase": "idle",
        "current_epoch": 12,
        "hidden_units": 3,
        "max_hidden_units": 10,
    }
    data.update(overrides)
    resp = Mock()
    resp.json.return_value = data
    return resp


@pytest.mark.unit
class TestCompletionReasonLabel:
    """The static reason → operator-label mapping."""

    @pytest.mark.parametrize(
        "reason,label",
        [
            ("residual_collapsed", "converged"),
            ("below_threshold", "converged"),
            ("no_candidate", "stalled (0 new units)"),
            ("early_stopped", "early stopped"),
            ("max_iterations", "max iterations"),
        ],
    )
    def test_known_reasons(self, reason, label):
        assert DashboardManager._completion_reason_label(reason) == label

    @pytest.mark.parametrize("reason", [None, "", "something_new", "unknown"])
    def test_unknown_or_missing_returns_none(self, reason):
        assert DashboardManager._completion_reason_label(reason) is None


@pytest.mark.unit
class TestStatusBarCompletionReason:
    """_build_unified_status_bar_content appends the reason on a completed run only."""

    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("residual_collapsed", "Completed — converged"),
            ("below_threshold", "Completed — converged"),
            ("no_candidate", "Completed — stalled (0 new units)"),
            ("early_stopped", "Completed — early stopped"),
            ("max_iterations", "Completed — max iterations"),
        ],
    )
    def test_completed_appends_reason(self, dashboard_manager, reason, expected):
        result = dashboard_manager._build_unified_status_bar_content(_status_response(completion_reason=reason), latency_ms=50)
        assert result[3] == expected

    def test_completed_without_reason_stays_bare(self, dashboard_manager):
        """No completion_reason (e.g. cascor predates the field) → plain "Completed"."""
        result = dashboard_manager._build_unified_status_bar_content(_status_response(), latency_ms=50)
        assert result[3] == "Completed"

    def test_unknown_reason_stays_bare(self, dashboard_manager):
        """An unrecognized reason is not surfaced (forward-compatible)."""
        result = dashboard_manager._build_unified_status_bar_content(_status_response(completion_reason="brand_new_reason"), latency_ms=50)
        assert result[3] == "Completed"

    def test_non_completed_ignores_reason(self, dashboard_manager):
        """A stale completion_reason must not decorate a non-completed status."""
        result = dashboard_manager._build_unified_status_bar_content(
            _status_response(completed=False, is_running=True, completion_reason="no_candidate"),
            latency_ms=50,
        )
        assert result[3] == "Running"


_NON_FINITE = "invalid dataset: X_train has non-finite values (NaN/Inf)"
_NON_FINITE_REASON = f"recurrence service error 422 on POST /v1/train: {_NON_FINITE}"
# A FastAPI validation-error list as the adapter renders it: longer than the 120-char label, and
# the error the label's cut drops -- the last one -- is the one that names ``ridge``.
_VALIDATION_ERRORS = [
    "body.dataset.params.symbols.0 -> Input should be a valid string",
    "body.dataset.params.start_date -> Input should be a valid date or datetime, invalid character in year",
    "body.ridge -> Input should be greater than or equal to 0",
]
_LONG_REASON = "recurrence service error 422 on POST /v1/train: " + "; ".join(_VALIDATION_ERRORS)


def _failed(reason, **overrides):
    return _status_response(completed=False, failed=True, completion_reason=reason, **overrides)


@pytest.mark.unit
class TestFailedRecurrenceFitReason:
    """W0.5 / F-C1: the reason renders; a reason the label cuts rides whole on a tooltip."""

    def test_a_422_detail_renders_in_the_label(self, dashboard_manager):
        result = dashboard_manager._build_unified_status_bar_content(_failed(_NON_FINITE_REASON), latency_ms=50)
        assert result[3] == f"Failed — {_NON_FINITE_REASON}"
        assert "non-finite" in result[3]

    def test_a_reason_the_label_holds_gets_no_tooltip(self, dashboard_manager):
        """A tooltip that repeats the label adds nothing, so element 3 stays the plain string."""
        assert len(_NON_FINITE_REASON) <= DashboardManager._COMPLETION_REASON_MAX_CHARS
        result = dashboard_manager._build_unified_status_bar_content(_failed(_NON_FINITE_REASON), latency_ms=50)
        assert isinstance(result[3], str)

    def test_a_reason_the_label_cuts_rides_whole_on_a_tooltip(self, dashboard_manager):
        assert len(_LONG_REASON) > DashboardManager._COMPLETION_REASON_MAX_CHARS
        display = dashboard_manager._build_unified_status_bar_content(_failed(_LONG_REASON), latency_ms=50)[3]
        assert isinstance(display, html.Span)
        label = DashboardManager._failure_reason_label(_LONG_REASON)
        assert display.children == f"Failed — {label}"
        assert len(label) == DashboardManager._COMPLETION_REASON_MAX_CHARS and label.endswith("…")
        assert "ridge" not in display.children, "the label's cut drops the tail -- which is why the tooltip exists"
        assert display.title == _LONG_REASON
        assert "body.ridge -> Input should be greater than or equal to 0" in display.title

    def test_the_tooltip_is_flattened(self, dashboard_manager):
        """A multi-line reason reaches the tooltip on one line, exactly as the label flattens it."""
        display = dashboard_manager._build_unified_status_bar_content(_failed(_LONG_REASON.replace("; ", ";\n  ")), latency_ms=50)[3]
        assert display.title == _LONG_REASON

    def test_the_tooltip_is_bounded(self, dashboard_manager):
        display = dashboard_manager._build_unified_status_bar_content(_failed("z" * 2000), latency_ms=50)[3]
        assert len(display.title) == DashboardManager._FAILURE_REASON_TOOLTIP_MAX_CHARS
        assert display.title.endswith("…")

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 409, 422, 429])
    def test_the_tooltip_holds_every_reason_the_adapter_can_build_uncut(self, code):
        """The tooltip bound is sized from the adapter's: its longest wording plus a detail at its 300-char bound.

        Built by the real ``_parse`` and ``outbound_error_text`` -- the path a reason really takes -- so a longer
        adapter wording or a larger detail bound fails here instead of being cut in front of an operator. Only 4xx
        codes carry a detail (a 5xx detail is never appended), so these are every branch that can build a long reason.
        """
        with pytest.raises(RecurrenceServiceError) as caught:
            RecurrenceServiceAdapter._parse(httpx.Response(code, json={"detail": "d" * 5000}), "POST", "/v1/train")
        reason = outbound_error_text(caught.value)
        assert len(reason) > DashboardManager._COMPLETION_REASON_MAX_CHARS, "the label must cut this reason"
        assert DashboardManager._failure_reason_tooltip(reason) == reason, "the tooltip must not"

    @pytest.mark.parametrize("retry_after", ["9" * 64, "9" * 5000, "Wed, 21 Oct 2015 07:28:00 GMT"], ids=["longest-seconds", "cut", "http-date"])
    def test_the_tooltip_holds_a_rate_limited_reason_with_its_wait_uncut(self, retry_after):
        """W1.6 / F-C7: a 429 carries its ``Retry-After`` wait before the detail, so the bound must hold that too.

        The test above sends no header, so its 429 builds the plain wording. Here the header is at its bound (64
        digits, which also earn the ``s``), past it (cut to the bound), and an HTTP-date.
        """
        response = httpx.Response(429, json={"detail": "d" * 5000}, headers={"Retry-After": retry_after})
        with pytest.raises(RecurrenceServiceRateLimited) as caught:
            RecurrenceServiceAdapter._parse(response, "POST", "/v1/train")
        reason = outbound_error_text(caught.value)
        assert "— retry after " in reason
        assert len(reason) > DashboardManager._COMPLETION_REASON_MAX_CHARS, "the label must cut this reason"
        assert DashboardManager._failure_reason_tooltip(reason) == reason, "the tooltip must not"

    def test_the_hidden_connection_status_stays_text(self, dashboard_manager):
        result = dashboard_manager._build_unified_status_bar_content(_failed(_LONG_REASON), latency_ms=50)
        assert isinstance(result[1], str)
        assert result[1].startswith("Status: Failed — recurrence service error 422 on POST /v1/train: ")

    def test_the_partial_data_mark_stays_on_the_label(self, dashboard_manager):
        display = dashboard_manager._build_unified_status_bar_content(_failed(_LONG_REASON, dataset_shortfall={"requested": 10, "delivered": 7}), latency_ms=50)[3]
        assert display.children.endswith("· partial data")
        assert display.title == _LONG_REASON

    @pytest.mark.parametrize(
        "overrides, expected",
        [
            ({"completed": True, "failed": False, "completion_reason": "x" * 500}, "Completed"),
            ({"completed": False, "failed": False, "is_running": True, "completion_reason": "x" * 500}, "Running"),
            ({"completed": False, "failed": True, "completion_reason": None}, "Failed"),
        ],
        ids=["completed-with-free-text", "running-with-stale-reason", "failed-without-reason"],
    )
    def test_no_other_state_gets_a_tooltip(self, dashboard_manager, overrides, expected):
        assert dashboard_manager._build_unified_status_bar_content(_status_response(**overrides), latency_ms=50)[3] == expected


@pytest.mark.unit
class TestA422ReachesTheStatusBar:
    """F-C1 end to end inside canopy: the service's 422 body -> adapter -> backend -> ``/api/status`` -> the bar.

    Each hop dropped the detail in a different way before W0.5, so the chain is driven whole: a real adapter over a
    ``MockTransport``, the real ``RecurrenceBackend``, the real route (recurrence has no status cache, so the route
    serves ``get_status()`` as is), and the real status-bar builder.
    """

    def test_the_service_detail_is_rendered(self, client, monkeypatch, dashboard_manager):
        import main

        def refuse(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"detail": _NON_FINITE})

        backend = RecurrenceBackend(RecurrenceServiceAdapter("http://rec.test:8210", transport=httpx.MockTransport(refuse)))
        monkeypatch.setattr(main, "backend", backend)
        backend.start_training(generator="equities_seq")
        deadline = time.monotonic() + 5.0
        while backend.is_training_active() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert not backend.is_training_active()

        response = client.get("/api/status")
        assert response.status_code == 200
        assert response.json()["completion_reason"] == _NON_FINITE_REASON
        rendered = dashboard_manager._build_unified_status_bar_content(response, latency_ms=50)[3]
        assert rendered == f"Failed — {_NON_FINITE_REASON}"
        assert "non-finite" in rendered
