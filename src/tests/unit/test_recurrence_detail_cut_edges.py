#!/usr/bin/env python
"""Edges of the W0.5 422-detail path that the W0.5 suites do not reach.

``TestServiceDetailInTheMessage`` pins a string detail, a short validation list, a uniform
``"x" * 1000`` cut, and a 5xx that must not relay a key. ``TestFailedRecurrenceFitReason``
pins a tooltip for one mid-length reason and a ``"z" * 2000`` title. Neither forces:

* a falsy ``detail`` or a falsy ``msg`` (``0``, ``False``, ``""``), which a truthiness check
  drops or dumps via ``str(item)`` -- and ``str(item)`` includes the echoed ``input``;
* an empty or whitespace-only validation list, which must not grow a suffix;
* collapse-then-bound, so a raw body longer than 300 characters whose collapsed form fits
  is kept whole;
* a joined validation list cut on a space, so ``rstrip`` before the ellipsis is load-bearing
  and a later item's ``input`` cannot ride along in the truncated message;
* the status-bar bounds at exactly the label bound (120) and the tooltip bound (480) and one
  past each, the label cut that lands on a space, and a reason that is long only before
  whitespace collapse.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import httpx
import pytest
from dash import html

from backend.recurrence_service_adapter import (
    RecurrenceServiceAdapter,
    RecurrenceServiceAuthError,
    RecurrenceServiceError,
    RecurrenceTrainInProgressError,
)
from frontend.dashboard_manager import DashboardManager

_PREFIX_422 = "recurrence service error 422 on POST /v1/train"
# W1.6 / F-C5: the 401 / 403 remedy names the two variables an operator can set.
_AUTH_REMEDY = "set JUNIPER_CANOPY_RECURRENCE_API_KEY or JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE to a key the service accepts"
_ELLIPSIS = "…"


def _parse(status_code, payload):
    """The exception ``_parse`` raises for ``payload`` as the response body."""
    with pytest.raises(RecurrenceServiceError) as caught:
        RecurrenceServiceAdapter._parse(httpx.Response(status_code, json=payload), "POST", "/v1/train")
    return caught.value


def _detail_of(error):
    """The rendered detail after the adapter's own ``": "`` separator, or ``None`` when there is none."""
    message = str(error)
    head, sep, tail = message.partition(": ")
    if sep and head in {
        _PREFIX_422,
        "recurrence training already in progress (POST /v1/train)",
        f"recurrence service rejected the request (401 on POST /v1/train) — {_AUTH_REMEDY}",
        f"recurrence service rejected the request (403 on POST /v1/train) — {_AUTH_REMEDY}",
    }:
        return tail
    return None


@pytest.mark.unit
class TestFalsyDetailsAreStillTheServiceAnswer:
    """``0`` and ``False`` are answers. A ``if not detail`` check would drop them."""

    @pytest.mark.parametrize("detail", [0, False], ids=["zero", "false"])
    def test_a_falsy_scalar_detail_is_appended(self, detail):
        error = _parse(422, {"detail": detail})
        assert str(error) == f"{_PREFIX_422}: {detail}"
        assert error.status_code == 422

    @pytest.mark.parametrize(
        "item, rendered, secret",
        [
            ({"loc": ["body", "n"], "msg": 0, "input": "SECRET-ZERO"}, "body.n -> 0", "SECRET-ZERO"),
            ({"loc": ["body", "flag"], "msg": False, "input": "SECRET-FALSE"}, "body.flag -> False", "SECRET-FALSE"),
            ({"loc": ["body", "n"], "msg": "", "input": "SECRET-EMPTY"}, "body.n ->", "SECRET-EMPTY"),
        ],
        ids=["msg-zero", "msg-false", "msg-empty"],
    )
    def test_a_falsy_msg_renders_loc_and_msg_and_not_the_echoed_input(self, item, rendered, secret):
        """Truthiness would treat these as "no msg" and fall through to ``str(item)``, which includes ``input``."""
        error = _parse(422, {"detail": [item]})
        assert str(error) == f"{_PREFIX_422}: {rendered}"
        assert secret not in str(error)
        assert secret in error.body


@pytest.mark.unit
class TestAnEmptyDetailDoesNotGrowASuffix:
    """An empty validation list is not the same path as a missing ``detail`` key: it is a list that joins to nothing."""

    @pytest.mark.parametrize(
        "status_code, error_type, message",
        [
            (401, RecurrenceServiceAuthError, f"recurrence service rejected the request (401 on POST /v1/train) — {_AUTH_REMEDY}"),
            (403, RecurrenceServiceAuthError, f"recurrence service rejected the request (403 on POST /v1/train) — {_AUTH_REMEDY}"),
            (409, RecurrenceTrainInProgressError, "recurrence training already in progress (POST /v1/train)"),
            (422, RecurrenceServiceError, _PREFIX_422),
        ],
        ids=["401", "403", "409", "422"],
    )
    def test_an_empty_validation_list_leaves_every_template_unsuffixed(self, status_code, error_type, message):
        error = _parse(status_code, {"detail": []})
        assert type(error) is error_type
        assert str(error) == message
        assert json.loads(error.body) == {"detail": []}

    @pytest.mark.parametrize(
        "detail",
        [
            ["   "],
            [" \n\t "],
            [{"loc": [], "msg": " \r\n ", "input": "SECRET-BLANK"}],
        ],
        ids=["blank-string", "blank-string-with-newline", "blank-msg"],
    )
    def test_a_whitespace_only_item_leaves_the_message_unsuffixed(self, detail):
        """One blank item collapses to nothing. Its ``input``, when it has one, stays in ``body`` only."""
        error = _parse(422, {"detail": detail})
        assert str(error) == _PREFIX_422
        assert "SECRET-BLANK" not in str(error)
        if isinstance(detail[0], dict):
            assert "SECRET-BLANK" in error.body


@pytest.mark.unit
class TestTheBoundAppliesToTheCollapsedDetail:
    """Whitespace is collapsed first. A raw body past the cap whose collapsed form fits is not cut."""

    def test_a_raw_detail_past_the_cap_is_kept_whole_when_it_collapses_under_the_cap(self):
        raw = "e\n\n" * 120
        assert len(raw) > 300
        collapsed = " ".join(raw.split())
        assert len(collapsed) <= 300
        error = _parse(422, {"detail": raw})
        assert str(error) == f"{_PREFIX_422}: {collapsed}"
        assert _ELLIPSIS not in str(error)
        assert "\n" not in str(error)
        assert collapsed.count("e") == 120

    def test_a_long_validation_list_is_cut_on_the_joined_line_and_drops_later_inputs(self):
        """Twenty field errors. The cut lands on the space after ``field13``, so ``rstrip`` shortens the line.

        Item ``i`` renders as ``body.fieldNN -> nope`` (20 chars) joined by ``"; "``. The 299-character slice ends on
        the space that follows ``body.field13``; ``rstrip`` removes it. ``field14`` and every ``input`` fall past the
        cut or were never rendered. ``body`` keeps the raw JSON, secrets included.
        """
        items = [{"loc": ["body", f"field{i:02d}"], "msg": "nope", "input": f"SECRET-{i:02d}"} for i in range(20)]
        error = _parse(422, {"detail": items})
        detail = _detail_of(error)
        assert detail is not None
        assert detail.startswith("body.field00 -> nope; ")
        assert "body.field12 -> nope" in detail
        assert detail.endswith(f"body.field13{_ELLIPSIS}")
        assert not detail.endswith(f" {_ELLIPSIS}")
        assert len(detail) == 299
        assert "field14" not in detail
        assert "SECRET-" not in detail
        assert "nope" in detail  # the errors that fit are still loc -> msg, not str(item)
        body = json.loads(error.body)
        assert body["detail"][19]["input"] == "SECRET-19"
        assert "SECRET-13" in error.body


@pytest.mark.unit
class TestStatusBarBoundsAreIndependent:
    """The label bound is 120 and the tooltip bound is 480 (W1.6). Each exact edge decides whether a Span is used."""

    @pytest.fixture
    def dashboard_manager(self):
        config = {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
        return DashboardManager(config)

    @staticmethod
    def _failed(reason, **overrides):
        data = {
            "is_running": False,
            "is_paused": False,
            "completed": False,
            "failed": True,
            "phase": "idle",
            "current_epoch": 1,
            "hidden_units": 0,
            "max_hidden_units": 10,
            "completion_reason": reason,
        }
        data.update(overrides)
        response = Mock()
        response.json.return_value = data
        return response

    def _display(self, dashboard_manager, reason, **overrides):
        return dashboard_manager._build_unified_status_bar_content(self._failed(reason, **overrides), latency_ms=50)

    def test_a_reason_of_exactly_the_label_bound_stays_a_string(self, dashboard_manager):
        reason = "c" * DashboardManager._COMPLETION_REASON_MAX_CHARS
        result = self._display(dashboard_manager, reason)
        assert result[3] == f"Failed — {reason}"
        assert _ELLIPSIS not in result[3]

    def test_one_past_the_label_bound_puts_the_dropped_character_on_the_tooltip(self, dashboard_manager):
        reason = "c" * (DashboardManager._COMPLETION_REASON_MAX_CHARS - 1) + "YZ"
        assert len(reason) == DashboardManager._COMPLETION_REASON_MAX_CHARS + 1
        result = self._display(dashboard_manager, reason)
        display = result[3]
        assert isinstance(display, html.Span)
        assert display.title == reason
        assert not str(display.title).endswith(_ELLIPSIS)
        assert display.children == "Failed — " + "c" * (DashboardManager._COMPLETION_REASON_MAX_CHARS - 1) + _ELLIPSIS
        assert "Z" not in display.children
        assert "Z" in display.title
        assert isinstance(result[1], str)

    def test_a_reason_of_exactly_the_tooltip_bound_is_not_cut_there(self, dashboard_manager):
        reason = "d" * DashboardManager._FAILURE_REASON_TOOLTIP_MAX_CHARS
        display = self._display(dashboard_manager, reason)[3]
        assert isinstance(display, html.Span)
        assert display.title == reason
        assert not str(display.title).endswith(_ELLIPSIS)
        assert display.children == "Failed — " + "d" * (DashboardManager._COMPLETION_REASON_MAX_CHARS - 1) + _ELLIPSIS

    def test_one_past_the_tooltip_bound_cuts_the_tooltip_and_leaves_the_label_at_its_own_bound(self, dashboard_manager):
        reason = "d" * DashboardManager._FAILURE_REASON_TOOLTIP_MAX_CHARS + "Q"
        display = self._display(dashboard_manager, reason)[3]
        assert isinstance(display, html.Span)
        assert len(display.title) == DashboardManager._FAILURE_REASON_TOOLTIP_MAX_CHARS
        assert display.title.endswith(_ELLIPSIS)
        assert "Q" not in display.title
        assert display.children == "Failed — " + "d" * (DashboardManager._COMPLETION_REASON_MAX_CHARS - 1) + _ELLIPSIS
        assert display.title != display.children

    def test_a_label_cut_that_lands_on_a_space_does_not_keep_the_space(self, dashboard_manager):
        """``rstrip`` before the ellipsis. The tooltip, under the larger bound, still holds the tail."""
        reason = "w" * 118 + " " + "TAIL"
        display = self._display(dashboard_manager, reason)[3]
        assert isinstance(display, html.Span)
        assert display.children == "Failed — " + "w" * 118 + _ELLIPSIS
        assert not display.children.endswith(f" {_ELLIPSIS}")
        assert display.title == reason
        assert "TAIL" in display.title
        assert "TAIL" not in display.children

    def test_whitespace_that_only_exceeds_the_label_bound_before_collapse_gets_no_tooltip(self, dashboard_manager):
        reason = "ab\n\n" * 40
        assert len(reason) > DashboardManager._COMPLETION_REASON_MAX_CHARS
        collapsed = " ".join(reason.split())
        assert len(collapsed) <= DashboardManager._COMPLETION_REASON_MAX_CHARS
        display = self._display(dashboard_manager, reason)[3]
        assert display == f"Failed — {collapsed}"
        assert "\n" not in display

    def test_a_short_reason_with_partial_data_stays_a_string(self, dashboard_manager):
        display = self._display(dashboard_manager, "short reason", dataset_shortfall={"requested": 10, "delivered": 7})[3]
        assert display == "Failed — short reason · partial data"

    @pytest.mark.parametrize(
        "reason",
        ["", " \n\t ", None, 0, ["SECRET-STATUS"], {"input": "SECRET-STATUS"}],
        ids=["empty", "whitespace", "none", "zero", "list", "dict"],
    )
    def test_a_reason_with_no_visible_text_stays_bare_failed(self, dashboard_manager, reason):
        result = self._display(dashboard_manager, reason)
        assert result[3] == "Failed"
        assert "SECRET-STATUS" not in str(result[3])
        assert "SECRET-STATUS" not in result[1]
