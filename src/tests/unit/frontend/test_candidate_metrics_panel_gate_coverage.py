#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.candidate_metrics_panel``.

Drives the panel's callback closures (via a stub app that records the raw
callback functions) plus the display-builder branches the baseline suite
misses: the ``_fetch_training_state`` HTTP path, the empty-epochs branch of
``_create_candidate_loss_figure``, and the second-candidate rows of
``_render_pool_history``.
"""

from unittest.mock import MagicMock, patch

import dash
import plotly.graph_objects as go
import pytest
from dash import html

from frontend.components.candidate_metrics_panel import CandidateMetricsPanel


class _StubApp:
    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    return CandidateMetricsPanel({}, component_id="cmp-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


class TestApiUrl:
    def test_api_url_concatenates_base_and_path(self, panel):
        url = panel._api_url("/api/state")
        assert url.endswith("/api/state")
        assert url.startswith("http")


class TestFetchTrainingStateCallback:
    def test_non_candidate_tab_returns_no_update(self, callbacks):
        result = callbacks["fetch_training_state"](3, "metrics")
        assert result is dash.no_update

    def test_candidate_tab_fetches_state_on_200(self, panel, callbacks):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"candidate_pool_status": "Active"}
        with patch("requests.get", return_value=resp):
            result = callbacks["fetch_training_state"](1, "candidates")
        assert result == {"candidate_pool_status": "Active"}

    def test_fetch_swallows_exception_and_returns_empty(self, panel, callbacks):
        with patch("requests.get", side_effect=RuntimeError("boom")):
            result = callbacks["fetch_training_state"](1, "candidates")
        assert result == {}

    def test_fetch_non_200_returns_empty(self, panel):
        resp = MagicMock(status_code=503)
        with patch("requests.get", return_value=resp):
            assert panel._fetch_training_state() == {}


class TestStatusDisplayCallback:
    def test_empty_state_defaults(self, callbacks):
        badge, style, phase, size = callbacks["update_status_display"](None)
        assert badge == "Inactive"
        assert phase == "Idle"
        assert size == "0"
        assert isinstance(style, dict)

    def test_populated_state(self, callbacks):
        state = {"candidate_pool_status": "Active", "candidate_pool_phase": "candidate_training", "candidate_pool_size": 6}
        badge, style, phase, size = callbacks["update_status_display"](state)
        assert badge == "Active"
        assert phase == "candidate_training"
        assert size == "6"


class TestEpochProgressCallback:
    def test_empty_state_hidden(self, callbacks):
        style, value, label = callbacks["update_epoch_progress"](None)
        assert style == {"display": "none"}
        assert value == 0
        assert label == ""

    def test_active_progress_computes_percent(self, callbacks):
        style, value, label = callbacks["update_epoch_progress"]({"candidate_epoch": 5, "candidate_total_epochs": 10})
        assert style == {"display": "block"}
        assert value == 50
        assert label == "5/10"

    def test_state_without_epoch_hidden(self, callbacks):
        style, value, label = callbacks["update_epoch_progress"]({"candidate_pool_status": "Active"})
        assert style == {"display": "none"}
        assert value == 0


class TestPoolInfoCallback:
    def test_empty_state_placeholder(self, callbacks):
        result = callbacks["update_pool_info"](None)
        assert isinstance(result, html.Div)
        assert "No active candidate pool" in str(result)

    def test_inactive_pool_placeholder(self, callbacks):
        result = callbacks["update_pool_info"]({"candidate_pool_status": "Inactive"})
        assert "No active candidate pool" in str(result)

    def test_active_pool_builds_display(self, callbacks):
        state = {
            "candidate_pool_status": "Active",
            "top_candidate_id": "cand_1",
            "top_candidate_score": 0.9,
            "pool_metrics": {"avg_loss": 0.1},
        }
        result = callbacks["update_pool_info"](state)
        assert isinstance(result, html.Div)
        assert "Top 2 Candidates" in str(result)


class TestLossPlotCallback:
    def test_returns_figure(self, callbacks):
        state = {"epochs": [1, 2, 3], "losses": [0.5, 0.4, 0.3], "phases": ["candidate", "candidate", "candidate"]}
        fig = callbacks["update_loss_plot"](state, "dark")
        assert isinstance(fig, go.Figure)

    def test_none_theme_defaults_light(self, callbacks):
        fig = callbacks["update_loss_plot"](None, None)
        assert isinstance(fig, go.Figure)


class TestTogglePoolDetailsCallback:
    def test_click_toggles_open(self, callbacks):
        is_open, icon = callbacks["toggle_pool_details"](1, True)
        assert is_open is False
        assert icon == "▶"

    def test_click_toggles_closed_to_open(self, callbacks):
        is_open, icon = callbacks["toggle_pool_details"](1, False)
        assert is_open is True
        assert icon == "▼"

    def test_no_click_keeps_state(self, callbacks):
        is_open, icon = callbacks["toggle_pool_details"](0, True)
        assert is_open is True
        assert icon == "▼"


class TestPoolHistoryCallback:
    def test_empty_state_returns_existing_history(self, callbacks):
        assert callbacks["update_pool_history"](None, [{"epoch": 1}]) == [{"epoch": 1}]

    def test_inactive_pool_keeps_history(self, callbacks):
        result = callbacks["update_pool_history"]({"candidate_pool_status": "Inactive", "current_epoch": 3}, [])
        assert result == []

    def test_active_pool_appends_snapshot(self, callbacks):
        state = {
            "candidate_pool_status": "Active",
            "current_epoch": 7,
            "candidate_pool_phase": "candidate_training",
            "top_candidate_id": "c1",
        }
        result = callbacks["update_pool_history"](state, [])
        assert len(result) == 1
        assert result[0]["epoch"] == 7

    def test_active_pool_existing_epoch_not_duplicated(self, callbacks):
        state = {"candidate_pool_status": "Active", "current_epoch": 7}
        history = [{"epoch": 7, "status": "Active"}]
        result = callbacks["update_pool_history"](state, history)
        assert result == history


class TestRenderPoolHistoryCallback:
    def test_callback_delegates_to_helper(self, callbacks):
        result = callbacks["render_pool_history"]([])
        assert len(result) == 1  # placeholder message


class TestToggleHistoryCallback:
    def test_toggles(self, callbacks):
        is_open, icon = callbacks["toggle_history"](1, False)
        assert is_open is True
        assert icon == "▼"
        is_open2, icon2 = callbacks["toggle_history"](1, True)
        assert is_open2 is False
        assert icon2 == "▶"


class TestLossFigureEmptyEpochs:
    def test_empty_epochs_returns_empty_plot(self, panel):
        # state is truthy but epochs/losses/phases are empty -> empty plot branch.
        fig = panel._create_candidate_loss_figure({"epochs": [], "losses": [], "phases": []})
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0


class TestRenderPoolHistorySecondCandidate:
    def test_second_candidate_rows_rendered(self, panel):
        history = [
            {
                "epoch": 12,
                "status": "Active",
                "phase": "Training",
                "size": 8,
                "top_candidate_id": "c1",
                "top_candidate_score": 0.9,
                "second_candidate_id": "c2",
                "second_candidate_score": 0.7,
                "pool_metrics": {"avg_loss": 0.2, "avg_accuracy": 0.8},
            }
        ]
        result = panel._render_pool_history(history)
        assert len(result) == 1
        assert "2nd Candidate" in str(result)
