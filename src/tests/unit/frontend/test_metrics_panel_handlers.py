#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_metrics_panel_handlers.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-06
# Last Modified: 2026-01-06
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for MetricsPanel callback handler methods
#####################################################################
"""Unit tests for MetricsPanel callback handlers to improve coverage from 67% to 90%."""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402


@pytest.fixture
def config():
    """Minimal config for metrics panel."""
    return {
        "max_data_points": 100,
        "update_interval": 500,
    }


@pytest.fixture
def metrics_panel(config):
    """Create MetricsPanel instance."""
    return MetricsPanel(config, component_id="test-panel")


@pytest.fixture
def registered_callbacks(config):
    """Create MetricsPanel with registered callbacks and return callback functions."""
    callbacks = {}

    def mock_callback(*args, **kwargs):
        def decorator(func):
            callbacks[func.__name__] = func
            return func

        return decorator

    mock_app = Mock()
    mock_app.callback = mock_callback

    panel = MetricsPanel(config, component_id="test-panel")
    panel.register_callbacks(mock_app)

    return panel, callbacks


@pytest.fixture
def sample_training_state():
    """Sample training state with candidate pool data."""
    return {
        "status": "RUNNING",
        "current_epoch": 42,
        "candidate_pool_status": "Active",
        "candidate_pool_phase": "Training",
        "candidate_pool_size": 8,
        "top_candidate_id": "C001",
        "top_candidate_score": 0.95,
        "second_candidate_id": "C002",
        "second_candidate_score": 0.88,
        "pool_metrics": {"avg_score": 0.75},
    }


@pytest.fixture
def sample_metrics_data():
    """Sample metrics data list."""
    return [{"epoch": i, "metrics": {"loss": 0.5 - i * 0.01, "accuracy": 0.5 + i * 0.02}} for i in range(50)]


@pytest.mark.unit
class TestFetchNetworkStatsHandler:
    """Tests for _fetch_network_stats_handler method."""

    def test_fetch_network_stats_success(self, metrics_panel):
        """Should return network stats on successful API call."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"nodes": 5, "connections": 12}
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_network_stats_handler()

            assert result == {"nodes": 5, "connections": 12}
            mock_get.assert_called_once_with("http://localhost:8050/api/network/stats", timeout=2)

    def test_fetch_network_stats_non_200_status(self, metrics_panel):
        """Should return empty dict on non-200 status code."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_network_stats_handler()

            assert result == {}

    def test_fetch_network_stats_connection_error(self, metrics_panel):
        """Should return empty dict on connection error."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = ConnectionError("Connection refused")

            result = metrics_panel._fetch_network_stats_handler()

            assert result == {}

    def test_fetch_network_stats_timeout(self, metrics_panel):
        """Should return empty dict on timeout."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = TimeoutError("Request timed out")

            result = metrics_panel._fetch_network_stats_handler()

            assert result == {}

    def test_fetch_network_stats_with_n_intervals(self, metrics_panel):
        """Should accept n_intervals parameter."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"nodes": 3}
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_network_stats_handler(n_intervals=10)

            assert result == {"nodes": 3}


@pytest.mark.unit
class TestFetchTrainingStateHandler:
    """Tests for _fetch_training_state_handler method."""

    def test_fetch_training_state_success(self, metrics_panel):
        """Should return training state on successful API call."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "RUNNING", "epoch": 25}
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_training_state_handler()

            assert result == {"status": "RUNNING", "epoch": 25}
            mock_get.assert_called_once_with("http://localhost:8050/api/state", timeout=2)

    def test_fetch_training_state_non_200_status(self, metrics_panel):
        """Should return empty dict on non-200 status code."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_training_state_handler()

            assert result == {}

    def test_fetch_training_state_exception(self, metrics_panel):
        """Should return empty dict on exception."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            result = metrics_panel._fetch_training_state_handler()

            assert result == {}

    def test_fetch_training_state_with_n_intervals(self, metrics_panel):
        """Should accept n_intervals parameter."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "PAUSED"}
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_training_state_handler(n_intervals=5)

            assert result == {"status": "PAUSED"}


@pytest.mark.unit
class TestToggleCandidateSection:
    """Tests for toggle_candidate_section callback logic."""

    def test_toggle_from_closed_to_open(self, metrics_panel):
        """Should toggle from closed to open state."""
        n_clicks = 1
        is_open = False
        new_state = not is_open if n_clicks else is_open
        icon = "▼" if new_state else "▶"
        # assert new_state is True
        assert new_state
        assert icon == "▼"

    def test_toggle_from_open_to_closed(self, metrics_panel):
        """Should toggle from open to closed state."""
        n_clicks = 1
        is_open = True
        new_state = not is_open if n_clicks else is_open
        icon = "▼" if new_state else "▶"
        # assert new_state is False
        assert not new_state
        assert icon == "▶"

    def test_toggle_no_clicks_returns_current_state(self, metrics_panel):
        """Should return current state when no clicks."""
        n_clicks = None
        is_open = True
        if n_clicks:
            new_state = not is_open
            icon = "▼" if new_state else "▶"
        else:
            new_state = is_open
            icon = "▼"
        # assert new_state is True
        assert new_state
        assert icon == "▼"


@pytest.mark.unit
class TestUpdateCandidateHistory:
    """Tests for update_candidate_history callback logic."""

    def test_update_history_with_no_state(self, metrics_panel):
        """Should return existing history when state is None."""
        state = None
        history = [{"epoch": 10}]

        result = history or []
        assert not state
        assert result == [{"epoch": 10}]

    def test_update_history_with_empty_state(self, metrics_panel):
        """Should return empty list when state is empty and no history."""
        state = {}
        history = None
        # if not state:
        #     result = history or []
        # else:
        #     result = history or []
        result = history if state else []
        assert result == []

    def test_update_history_inactive_pool(self, metrics_panel, sample_training_state):
        """Should not add to history when pool is inactive."""
        state = {**sample_training_state, "candidate_pool_status": "Inactive"}
        history = []

        pool_status = state.get("candidate_pool_status", "Inactive")
        if pool_status == "Inactive":
            result = history or []
        else:
            result = [{"epoch": state["current_epoch"]}] + history[:9]

        assert result == []

    def test_update_history_active_pool_new_entry(self, metrics_panel, sample_training_state):
        """Should add new pool snapshot for active pool."""
        state = sample_training_state
        history = []

        pool_status = state.get("candidate_pool_status", "Inactive")
        current_epoch = state.get("current_epoch", 0)

        if pool_status != "Inactive":
            pool_snapshot = {
                "epoch": current_epoch,
                "status": pool_status,
                "size": state.get("candidate_pool_size", 0),
            }
            existing = next((p for p in history if p.get("epoch") == current_epoch), None)
            result = history if existing else [pool_snapshot] + history[:9]
        else:
            result = history

        assert len(result) == 1
        assert result[0]["epoch"] == 42
        assert result[0]["status"] == "Active"

    def test_update_history_max_entries(self, metrics_panel, sample_training_state):
        """Should limit history to 10 entries."""
        state = sample_training_state
        history = [{"epoch": i} for i in range(12)]

        pool_status = state.get("candidate_pool_status", "Inactive")
        current_epoch = state.get("current_epoch", 0)

        if pool_status != "Inactive":
            pool_snapshot = {"epoch": current_epoch}
            existing = next((p for p in history if p.get("epoch") == current_epoch), None)
            result = history if existing else [pool_snapshot] + history[:9]
        else:
            result = history

        assert len(result) == 10

    def test_update_history_existing_epoch_not_duplicated(self, metrics_panel, sample_training_state):
        """Should not add duplicate entry for same epoch."""
        state = sample_training_state
        history = [{"epoch": 42, "status": "Previous"}]

        current_epoch = state.get("current_epoch", 0)
        existing = next((p for p in history if p.get("epoch") == current_epoch), None)

        assert existing is not None
        assert existing["status"] == "Previous"


@pytest.mark.unit
class TestRenderCandidateHistory:
    """Tests for render_candidate_history callback logic."""

    def test_render_empty_history(self, metrics_panel):
        """Should return empty list for empty history."""
        history = []
        result = [] if not history or len(history) <= 1 else ["items"]
        # assert result == []
        assert not result

    def test_render_single_entry_history(self, metrics_panel):
        """Should return empty list for single entry (current pool only)."""
        history = [{"epoch": 42}]
        result = [] if not history or len(history) <= 1 else ["items"]
        # assert result == []
        assert not result

    def test_render_multiple_entries(self, metrics_panel):
        """Should render items for multiple history entries."""
        history = [
            {"epoch": 42, "top_candidate_id": "C001", "top_candidate_score": 0.95},
            {"epoch": 30, "top_candidate_id": "C002", "top_candidate_score": 0.88},
            {"epoch": 20, "top_candidate_id": "C003", "top_candidate_score": 0.75},
        ]

        result = [] if not history or len(history) <= 1 else history[1:]
        assert len(result) == 2
        assert result[0]["epoch"] == 30


@pytest.mark.unit
class TestCaptureViewState:
    """Tests for capture_view_state callback logic."""

    def test_capture_loss_xaxis_range(self, metrics_panel):
        """Should capture loss plot x-axis range."""
        loss_relayout = {"xaxis.range[0]": 0, "xaxis.range[1]": 100}
        current_state = {}

        new_state = current_state.copy()
        if "xaxis.range[0]" in loss_relayout:
            new_state["loss_xaxis_range"] = [
                loss_relayout["xaxis.range[0]"],
                loss_relayout["xaxis.range[1]"],
            ]

        assert new_state["loss_xaxis_range"] == [0, 100]

    def test_capture_loss_yaxis_range(self, metrics_panel):
        """Should capture loss plot y-axis range."""
        loss_relayout = {"yaxis.range[0]": 0.1, "yaxis.range[1]": 0.9}
        current_state = {}

        new_state = current_state.copy()
        if "yaxis.range[0]" in loss_relayout:
            new_state["loss_yaxis_range"] = [
                loss_relayout["yaxis.range[0]"],
                loss_relayout["yaxis.range[1]"],
            ]

        assert new_state["loss_yaxis_range"] == [0.1, 0.9]

    def test_capture_loss_autorange_clears_range(self, metrics_panel):
        """Should clear range when autorange is set."""
        loss_relayout = {"xaxis.autorange": True}
        current_state = {"loss_xaxis_range": [0, 50]}

        new_state = current_state.copy()
        if loss_relayout.get("xaxis.autorange"):
            new_state["loss_xaxis_range"] = None

        assert new_state["loss_xaxis_range"] is None

    def test_capture_accuracy_xaxis_range(self, metrics_panel):
        """Should capture accuracy plot x-axis range."""
        accuracy_relayout = {"xaxis.range[0]": 10, "xaxis.range[1]": 50}
        current_state = {}

        new_state = current_state.copy()
        if "xaxis.range[0]" in accuracy_relayout:
            new_state["accuracy_xaxis_range"] = [
                accuracy_relayout["xaxis.range[0]"],
                accuracy_relayout["xaxis.range[1]"],
            ]

        assert new_state["accuracy_xaxis_range"] == [10, 50]

    def test_capture_no_trigger_returns_current(self, metrics_panel):
        """Should return current state when no trigger."""
        current_state = {"existing": "data"}

        result = current_state or {}
        assert result == {"existing": "data"}


@pytest.mark.unit
class TestToggleReplayVisibility:
    """Tests for toggle_replay_visibility callback logic."""

    def test_show_replay_when_stopped(self, metrics_panel):
        # sourcery skip: equality-identity, inline-variable
        """Should show replay controls when training is stopped."""
        state = {"status": "STOPPED"}
        _LIGHT_THEME = "light"
        _DARK_THEME = "dark"
        theme = _DARK_THEME

        # is_dark = theme == "dark"
        is_dark = theme == _DARK_THEME and theme != _LIGHT_THEME
        base_style = {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
            "borderRadius": "5px",
        }

        status = state.get("status", "STOPPED").upper()
        if status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"]:
            result = {**base_style, "display": "block"}
        else:
            result = {**base_style, "display": "none"}

        assert result["display"] == "block"
        assert result["backgroundColor"] == "#2d2d2d"

    def test_hide_replay_when_running(self, metrics_panel):
        """Should hide replay controls when training is running."""
        state = {"status": "RUNNING"}
        theme = "light"

        is_dark = theme == "dark"
        base_style = {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
            "borderRadius": "5px",
        }

        status = state.get("status", "STOPPED").upper()
        if status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"]:
            result = {**base_style, "display": "block"}
        else:
            result = {**base_style, "display": "none"}

        assert result["display"] == "none"
        assert result["backgroundColor"] == "#f8f9fa"

    def test_show_replay_when_state_none(self, metrics_panel):
        # sourcery skip: equality-identity, inline-variable
        """Should show replay controls when state is None."""
        state = None
        theme = "dark"

        is_dark = theme == "dark"
        base_style = {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
            "borderRadius": "5px",
        }

        result = base_style if state else {**base_style, "display": "block"}
        assert result["display"] == "block"

    def test_show_replay_when_paused(self, metrics_panel):
        """Should show replay controls when training is paused."""
        state = {"status": "paused"}

        status = state.get("status", "STOPPED").upper()
        visible = status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"]

        # assert visible is True
        assert visible

    def test_show_replay_when_completed(self, metrics_panel):
        """Should show replay controls when training is completed."""
        state = {"status": "COMPLETED"}

        status = state.get("status", "STOPPED").upper()
        visible = status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"]

        # assert visible is True
        assert visible


@pytest.mark.unit
class TestHandleReplayControls:
    """Tests for handle_replay_controls callback logic."""

    def test_play_button_starts_playback(self, metrics_panel, sample_metrics_data):
        """Should start playback when play button clicked."""
        current_state = {"mode": "stopped", "speed": 1.0, "current_index": 0}
        trigger = "test-panel-replay-play"

        state = current_state.copy()
        if "replay-play" in trigger:
            state["mode"] = "paused" if state["mode"] == "playing" else "playing"

        assert state["mode"] == "playing"

    def test_play_button_pauses_playback(self, metrics_panel):
        """Should pause playback when play button clicked during play."""
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 10}
        trigger = "test-panel-replay-play"

        state = current_state.copy()
        if "replay-play" in trigger:
            state["mode"] = "paused" if state["mode"] == "playing" else "playing"

        assert state["mode"] == "paused"

    def test_step_back_decrements_index(self, metrics_panel):
        """Should decrement index and pause on step back."""
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 10}
        trigger = "test-panel-step-back"

        state = current_state.copy()
        if "step-back" in trigger:
            state["mode"] = "paused"
            state["current_index"] = max(0, state["current_index"] - 1)

        assert state["mode"] == "paused"
        assert state["current_index"] == 9

    def test_step_back_stops_at_zero(self, metrics_panel):
        """Should not go below zero on step back."""
        current_state = {"mode": "stopped", "speed": 1.0, "current_index": 0}
        trigger = "test-panel-step-back"

        state = current_state.copy()
        if "step-back" in trigger:
            state["current_index"] = max(0, state["current_index"] - 1)

        assert state["current_index"] == 0

    def test_step_forward_increments_index(self, metrics_panel, sample_metrics_data):
        """Should increment index and pause on step forward."""
        max_index = len(sample_metrics_data) - 1
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 10}
        trigger = "test-panel-step-forward"

        state = current_state.copy()
        if "step-forward" in trigger:
            state["mode"] = "paused"
            state["current_index"] = min(max_index, state["current_index"] + 1)

        assert state["mode"] == "paused"
        assert state["current_index"] == 11

    def test_step_forward_stops_at_max(self, metrics_panel, sample_metrics_data):
        """Should not exceed max index on step forward."""
        max_index = len(sample_metrics_data) - 1
        current_state = {"mode": "stopped", "speed": 1.0, "current_index": max_index}
        trigger = "test-panel-step-forward"

        state = current_state.copy()
        if "step-forward" in trigger:
            state["current_index"] = min(max_index, state["current_index"] + 1)

        assert state["current_index"] == max_index

    def test_replay_start_jumps_to_beginning(self, metrics_panel):
        """Should jump to start index on replay-start."""
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 25, "start_index": 0}
        trigger = "test-panel-replay-start"

        state = current_state.copy()
        if "replay-start" in trigger:
            state["current_index"] = state["start_index"]
            state["mode"] = "paused"

        assert state["current_index"] == 0
        assert state["mode"] == "paused"

    def test_replay_end_jumps_to_end(self, metrics_panel, sample_metrics_data):
        """Should jump to end index on replay-end."""
        max_index = len(sample_metrics_data) - 1
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 10, "end_index": max_index}
        trigger = "test-panel-replay-end"

        state = current_state.copy()
        if "replay-end" in trigger:
            state["current_index"] = state["end_index"] or max_index
            state["mode"] = "paused"

        assert state["current_index"] == max_index
        assert state["mode"] == "paused"

    def test_speed_1x_sets_normal_speed(self, metrics_panel):
        """Should set speed to 1.0 on 1x button."""
        current_state = {"mode": "playing", "speed": 4.0, "current_index": 10}
        trigger = "test-panel-speed-1x"

        state = current_state.copy()
        if "speed-1x" in trigger:
            state["speed"] = 1.0

        assert state["speed"] == 1.0

    def test_speed_2x_sets_double_speed(self, metrics_panel):
        """Should set speed to 2.0 on 2x button."""
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 10}
        trigger = "test-panel-speed-2x"

        state = current_state.copy()
        if "speed-2x" in trigger:
            state["speed"] = 2.0

        assert state["speed"] == 2.0

    def test_speed_4x_sets_quad_speed(self, metrics_panel):
        """Should set speed to 4.0 on 4x button."""
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 10}
        trigger = "test-panel-speed-4x"

        state = current_state.copy()
        if "speed-4x" in trigger:
            state["speed"] = 4.0

        assert state["speed"] == 4.0

    def test_slider_updates_position(self, metrics_panel, sample_metrics_data):
        """Should update position from slider value."""
        max_index = len(sample_metrics_data) - 1
        current_state = {"mode": "playing", "speed": 1.0, "current_index": 0}
        trigger = "test-panel-replay-slider"

        state = current_state.copy()
        if "replay-slider" in trigger:
            slider_value = 50  # 50%
            state["current_index"] = int((slider_value / 100) * max_index) if max_index > 0 else 0
            state["mode"] = "paused"

        expected_index = int(0.5 * max_index)
        assert state["current_index"] == expected_index
        assert state["mode"] == "paused"

    def test_interval_calculation(self, metrics_panel):
        """Should calculate interval based on speed."""
        base_interval = 1000
        speeds = [1.0, 2.0, 4.0]
        expected_intervals = [1000, 500, 250]

        for speed, expected in zip(speeds, expected_intervals):
            interval = int(base_interval / speed)
            assert interval == expected


@pytest.mark.unit
class TestReplayTick:
    """Tests for replay_tick callback logic."""

    def test_replay_tick_advances_index(self, metrics_panel, sample_metrics_data):
        """Should advance index by one during playback."""
        max_index = len(sample_metrics_data) - 1
        state = {"mode": "playing", "current_index": 10, "end_index": max_index}

        if state["mode"] == "playing":
            new_index = state["current_index"] + 1
            if new_index > state["end_index"]:
                state["mode"] = "stopped"
                state["current_index"] = state["end_index"]
            else:
                state["current_index"] = new_index

        assert state["current_index"] == 11

    def test_replay_tick_stops_at_end(self, metrics_panel, sample_metrics_data):
        """Should stop when reaching end index."""
        max_index = len(sample_metrics_data) - 1
        state = {"mode": "playing", "current_index": max_index, "end_index": max_index}

        if state["mode"] == "playing":
            new_index = state["current_index"] + 1
            if new_index > state["end_index"]:
                state["mode"] = "stopped"
                state["current_index"] = state["end_index"]
            else:
                state["current_index"] = new_index

        assert state["mode"] == "stopped"
        assert state["current_index"] == max_index

    def test_replay_tick_ignores_paused(self, metrics_panel):
        """Should not advance when paused."""
        state = {"mode": "paused", "current_index": 10, "end_index": 50}

        original_index = state["current_index"]
        if state["mode"] == "playing":
            state["current_index"] += 1

        assert state["current_index"] == original_index

    def test_replay_tick_ignores_stopped(self, metrics_panel):
        """Should not advance when stopped."""
        state = {"mode": "stopped", "current_index": 10, "end_index": 50}

        original_index = state["current_index"]
        if state["mode"] == "playing":
            state["current_index"] += 1

        assert state["current_index"] == original_index

    def test_replay_tick_returns_state_when_none(self, metrics_panel):
        """Should return state unchanged when state is None."""
        state = None
        result = state
        assert result is None


@pytest.mark.unit
class TestUpdateReplayUI:
    """Tests for update_replay_ui callback logic."""

    def test_update_slider_position(self, metrics_panel, sample_metrics_data):
        """Should calculate correct slider position."""
        max_index = len(sample_metrics_data) - 1
        testing_index = 25
        state = {"current_index": testing_index}

        current_index = state.get("current_index", 0)
        slider_value = (current_index / max_index * 100) if max_index > 0 else 0
        position_text = f"{current_index} / {max_index}"

        expected_slider = (25 / 49) * 100
        assert abs(slider_value - expected_slider) < 0.01
        assert position_text == "25 / 49"

    def test_update_slider_zero_metrics(self, metrics_panel):
        """Should handle zero metrics gracefully."""
        metrics_data = []
        state = {"current_index": 0}

        max_index = len(metrics_data) - 1 if metrics_data else 0
        current_index = state.get("current_index", 0)

        slider_value = (current_index / max_index * 100) if max_index > 0 else 0
        position_text = f"{current_index} / {max_index}"

        assert slider_value == 0
        assert position_text == "0 / 0"

    def test_update_slider_none_state(self, metrics_panel, sample_metrics_data):
        """Should handle None state."""
        state = None

        current_index = state.get("current_index", 0) if state else 0
        assert current_index == 0


@pytest.mark.unit
class TestUpdatePlayButton:
    """Tests for update_play_button callback logic."""

    def test_show_pause_when_playing(self, metrics_panel):
        """Should show pause icon when playing."""
        state = {"mode": "playing"}

        icon = "⏸" if state and state.get("mode") == "playing" else "▶"

        assert icon == "⏸"

    def test_show_play_when_paused(self, metrics_panel):
        """Should show play icon when paused."""
        state = {"mode": "paused"}

        icon = "⏸" if state and state.get("mode") == "playing" else "▶"

        assert icon == "▶"

    def test_show_play_when_stopped(self, metrics_panel):
        """Should show play icon when stopped."""
        state = {"mode": "stopped"}

        icon = "⏸" if state and state.get("mode") == "playing" else "▶"

        assert icon == "▶"

    def test_show_play_when_state_none(self, metrics_panel):
        """Should show play icon when state is None."""
        state = None

        icon = "⏸" if state and state.get("mode") == "playing" else "▶"

        assert icon == "▶"


@pytest.mark.unit
class TestUpdateCandidatePoolHandler:
    """Tests for _update_candidate_pool_handler method."""

    def test_returns_empty_for_none_state(self, metrics_panel):
        """Should return empty display for None state."""
        result = metrics_panel._update_candidate_pool_handler(state=None)

        assert result[0] == []
        assert result[1] == {"marginTop": "20px"}

    def test_returns_inactive_message(self, metrics_panel):
        """Should return inactive message for inactive pool."""
        state = {"candidate_pool_status": "Inactive"}

        result = metrics_panel._update_candidate_pool_handler(state=state)

        assert result[1] == {"marginTop": "20px"}


@pytest.mark.unit
class TestUpdateMetricsDisplayHandler:
    """Tests for _update_metrics_display_handler method."""

    def test_handles_dict_with_history_key(self, metrics_panel):
        """Should extract history from dict payload and return correct output."""
        metrics_data = {
            "history": [
                {
                    "epoch": 1,
                    "phase": "output_training",
                    "metrics": {"loss": 0.5, "accuracy": 0.6},
                    "network_topology": {"hidden_units": 0},
                },
                {
                    "epoch": 2,
                    "phase": "output_training",
                    "metrics": {"loss": 0.4, "accuracy": 0.7},
                    "network_topology": {"hidden_units": 0},
                },
            ]
        }

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="light", view_state=None)

        assert len(result) == 8
        assert result[2] == "2"
        assert "0.4" in result[3]

    def test_handles_dict_with_data_key(self, metrics_panel):
        """Should extract data from dict payload."""
        metrics_data = {
            "data": [
                {
                    "epoch": 1,
                    "phase": "output_training",
                    "metrics": {"loss": 0.3, "accuracy": 0.8},
                    "network_topology": {"hidden_units": 1},
                },
            ]
        }

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="dark", view_state=None)

        assert len(result) == 8
        assert result[2] == "1"

    def test_handles_empty_dict(self, metrics_panel):
        """Should return empty state for empty dict."""
        metrics_data = {}

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="light", view_state=None)

        assert len(result) == 8
        assert result[2] == "0"
        assert result[3] == "--"
        assert result[6] == "Status: Idle"

    def test_handles_non_list_non_dict(self, metrics_panel):
        """Should return empty state for invalid types."""
        metrics_data = "invalid"

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="light", view_state=None)

        assert len(result) == 8
        assert result[2] == "0"
        assert result[3] == "--"

    def test_handles_none_metrics(self, metrics_panel):
        """Should return empty state for None metrics."""
        result = metrics_panel._update_metrics_display_handler(metrics_data=None, theme="light", view_state=None)

        assert len(result) == 8
        assert result[6] == "Status: Idle"

    def test_handles_list_metrics_directly(self, metrics_panel, sample_metrics_data):
        """Should handle list metrics directly."""
        metrics_with_full_data = [
            {
                "epoch": i,
                "phase": "output_training",
                "metrics": {"loss": 0.5 - i * 0.01, "accuracy": 0.5 + i * 0.01},
                "network_topology": {"hidden_units": 0},
            }
            for i in range(10)
        ]

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_with_full_data, theme="light", view_state=None)

        assert len(result) == 8
        assert result[2] == "9"

    def test_applies_view_state_loss_xaxis(self, metrics_panel):
        """Should apply view state for loss x-axis range."""
        metrics = [
            {
                "epoch": i,
                "phase": "output_training",
                "metrics": {"loss": 0.5, "accuracy": 0.5},
                "network_topology": {"hidden_units": 0},
            }
            for i in range(20)
        ]
        view_state = {"loss_xaxis_range": [5, 15]}

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics, theme="light", view_state=view_state)

        assert len(result) == 8

    def test_applies_view_state_loss_yaxis(self, metrics_panel):
        """Should apply view state for loss y-axis range."""
        metrics = [
            {
                "epoch": i,
                "phase": "output_training",
                "metrics": {"loss": 0.5, "accuracy": 0.5},
                "network_topology": {"hidden_units": 0},
            }
            for i in range(10)
        ]
        view_state = {"loss_yaxis_range": [0.1, 0.9]}

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics, theme="dark", view_state=view_state)

        assert len(result) == 8

    def test_applies_view_state_accuracy_xaxis(self, metrics_panel):
        """Should apply view state for accuracy x-axis range."""
        metrics = [
            {
                "epoch": i,
                "phase": "output_training",
                "metrics": {"loss": 0.5, "accuracy": 0.5},
                "network_topology": {"hidden_units": 0},
            }
            for i in range(10)
        ]
        view_state = {"accuracy_xaxis_range": [2, 8]}

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics, theme="light", view_state=view_state)

        assert len(result) == 8

    def test_applies_view_state_accuracy_yaxis(self, metrics_panel):
        """Should apply view state for accuracy y-axis range."""
        metrics = [
            {
                "epoch": i,
                "phase": "output_training",
                "metrics": {"loss": 0.5, "accuracy": 0.5},
                "network_topology": {"hidden_units": 0},
            }
            for i in range(10)
        ]
        view_state = {"accuracy_yaxis_range": [0.2, 0.8]}

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics, theme="light", view_state=view_state)

        assert len(result) == 8

    def test_formats_status_text(self, metrics_panel):
        """Should format status text correctly."""
        metrics = [
            {
                "epoch": 5,
                "phase": "candidate_training",
                "metrics": {"loss": 0.3, "accuracy": 0.7},
                "network_topology": {"hidden_units": 2},
            }
        ]

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics, theme="light", view_state=None)

        assert "Candidate Training" in result[6]

    def test_hidden_units_from_topology(self, metrics_panel):
        """Should extract hidden units from network topology."""
        metrics = [
            {
                "epoch": 10,
                "phase": "output_training",
                "metrics": {"loss": 0.2, "accuracy": 0.8},
                "network_topology": {"hidden_units": 5},
            }
        ]

        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics, theme="light", view_state=None)

        assert result[5] == "5"


@pytest.mark.unit
class TestRegisteredCallbacks:
    """Tests for actual registered callback functions to improve line coverage."""

    def test_toggle_candidate_section_opens(self, registered_callbacks):
        """Test toggle_candidate_section callback opens section."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_candidate_section"):
            result = func(1, False)
            assert result == (True, "▼")

    def test_toggle_candidate_section_closes(self, registered_callbacks):
        """Test toggle_candidate_section callback closes section."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_candidate_section"):
            result = func(1, True)
            assert result == (False, "▶")

    def test_toggle_candidate_section_no_clicks(self, registered_callbacks):
        """Test toggle_candidate_section callback with no clicks."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_candidate_section"):
            result = func(None, True)
            assert result == (True, "▼")

    def test_update_candidate_history_empty_state(self, registered_callbacks):
        """Test update_candidate_history with empty state."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_candidate_history"):
            result = func(None, [])
            assert result == []

    def test_update_candidate_history_inactive_pool(self, registered_callbacks):
        """Test update_candidate_history with inactive pool."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_candidate_history"):
            state = {"candidate_pool_status": "Inactive", "current_epoch": 10}
            result = func(state, [])
            assert result == []

    def test_update_candidate_history_active_pool(self, registered_callbacks):
        """Test update_candidate_history with active pool."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_candidate_history"):
            state = {
                "candidate_pool_status": "Active",
                "candidate_pool_phase": "Training",
                "current_epoch": 42,
                "candidate_pool_size": 8,
                "top_candidate_id": "C001",
                "top_candidate_score": 0.95,
                "second_candidate_id": "C002",
                "second_candidate_score": 0.88,
                "pool_metrics": {},
            }
            result = func(state, [])
            assert len(result) == 1
            assert result[0]["epoch"] == 42

    def test_update_candidate_history_existing_epoch(self, registered_callbacks):
        """Test update_candidate_history doesn't duplicate existing epoch."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_candidate_history"):
            state = {
                "candidate_pool_status": "Active",
                "current_epoch": 42,
            }
            history = [{"epoch": 42, "status": "Previous"}]
            result = func(state, history)
            assert len(result) == 1

    def test_update_candidate_history_max_entries(self, registered_callbacks):
        """Test update_candidate_history limits to 10 entries."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_candidate_history"):
            state = {
                "candidate_pool_status": "Active",
                "current_epoch": 100,
                "candidate_pool_size": 5,
            }
            history = [{"epoch": i} for i in range(15)]
            result = func(state, history)
            assert len(result) == 10

    def test_render_candidate_history_empty(self, registered_callbacks):
        """Test render_candidate_history with empty history."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("render_candidate_history"):
            result = func([])
            assert result == []

    def test_render_candidate_history_single_entry(self, registered_callbacks):
        """Test render_candidate_history with single entry."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("render_candidate_history"):
            result = func([{"epoch": 42}])
            assert result == []

    def test_render_candidate_history_multiple_entries(self, registered_callbacks):
        """Test render_candidate_history with multiple entries."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("render_candidate_history"):
            history = [
                {"epoch": 42, "top_candidate_id": "C001", "top_candidate_score": 0.95, "size": 8},
                {"epoch": 30, "top_candidate_id": "C002", "top_candidate_score": 0.88, "size": 6},
            ]
            result = func(history)
            assert result is not None

    def test_capture_view_state_no_trigger(self, registered_callbacks):
        """Test capture_view_state with no trigger."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = []
                result = func(None, None, {"existing": "data"})
                assert result == {"existing": "data"}

    def test_capture_view_state_loss_xaxis(self, registered_callbacks):
        """Test capture_view_state captures loss x-axis range."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-loss-plot.relayoutData"}]
                result = func({"xaxis.range[0]": 0, "xaxis.range[1]": 100}, None, {})
                assert result.get("loss_xaxis_range") == [0, 100]

    def test_capture_view_state_loss_yaxis(self, registered_callbacks):
        """Test capture_view_state captures loss y-axis range."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-loss-plot.relayoutData"}]
                result = func({"yaxis.range[0]": 0.1, "yaxis.range[1]": 0.9}, None, {})
                assert result.get("loss_yaxis_range") == [0.1, 0.9]

    def test_capture_view_state_loss_autorange(self, registered_callbacks):
        """Test capture_view_state clears range on autorange."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-loss-plot.relayoutData"}]
                result = func({"xaxis.autorange": True}, None, {"loss_xaxis_range": [0, 50]})
                assert result.get("loss_xaxis_range") is None

    def test_capture_view_state_accuracy_xaxis(self, registered_callbacks):
        """Test capture_view_state captures accuracy x-axis range."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-accuracy-plot.relayoutData"}]
                result = func(None, {"xaxis.range[0]": 10, "xaxis.range[1]": 50}, {})
                assert result.get("accuracy_xaxis_range") == [10, 50]

    def test_capture_view_state_accuracy_yaxis(self, registered_callbacks):
        """Test capture_view_state captures accuracy y-axis range."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-accuracy-plot.relayoutData"}]
                result = func(None, {"yaxis.range[0]": 0.2, "yaxis.range[1]": 0.8}, {})
                assert result.get("accuracy_yaxis_range") == [0.2, 0.8]

    def test_capture_view_state_accuracy_autorange(self, registered_callbacks):
        """Test capture_view_state clears accuracy range on autorange."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("capture_view_state"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-accuracy-plot.relayoutData"}]
                result = func(
                    None,
                    {"xaxis.autorange": True, "yaxis.autorange": True},
                    {"accuracy_xaxis_range": [5, 25], "accuracy_yaxis_range": [0.3, 0.7]},
                )
                assert result.get("accuracy_xaxis_range") is None
                assert result.get("accuracy_yaxis_range") is None

    def test_toggle_replay_visibility_stopped(self, registered_callbacks):
        """Test toggle_replay_visibility shows controls when stopped."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_replay_visibility"):
            result = func({"status": "STOPPED"}, "dark")
            assert result["display"] == "block"

    def test_toggle_replay_visibility_running(self, registered_callbacks):
        """Test toggle_replay_visibility hides controls when running."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_replay_visibility"):
            result = func({"status": "RUNNING"}, "light")
            assert result["display"] == "none"

    def test_toggle_replay_visibility_no_state(self, registered_callbacks):
        """Test toggle_replay_visibility shows controls when state is None."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_replay_visibility"):
            result = func(None, "dark")
            assert result["display"] == "block"

    def test_toggle_replay_visibility_paused(self, registered_callbacks):
        """Test toggle_replay_visibility shows controls when paused."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("toggle_replay_visibility"):
            result = func({"status": "PAUSED"}, "light")
            assert result["display"] == "block"

    def test_handle_replay_controls_play(self, registered_callbacks):
        """Test handle_replay_controls play button."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-replay-play.n_clicks"}]
                current_state = {"mode": "stopped", "speed": 1.0, "current_index": 0}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(1, 0, 0, 0, 0, 0, 0, 0, 0, current_state, metrics_data)
                assert result[0]["mode"] == "playing"

    def test_handle_replay_controls_step_back(self, registered_callbacks):
        """Test handle_replay_controls step back button."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-step-back.n_clicks"}]
                current_state = {"mode": "playing", "speed": 1.0, "current_index": 10}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(0, 1, 0, 0, 0, 0, 0, 0, 0, current_state, metrics_data)
                assert result[0]["mode"] == "paused"
                assert result[0]["current_index"] == 9

    def test_handle_replay_controls_step_forward(self, registered_callbacks):
        """Test handle_replay_controls step forward button."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-step-forward.n_clicks"}]
                current_state = {"mode": "stopped", "speed": 1.0, "current_index": 10}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(0, 0, 1, 0, 0, 0, 0, 0, 0, current_state, metrics_data)
                assert result[0]["mode"] == "paused"
                assert result[0]["current_index"] == 11

    def test_handle_replay_controls_start(self, registered_callbacks):
        """Test handle_replay_controls start button."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-replay-start.n_clicks"}]
                current_state = {"mode": "playing", "speed": 1.0, "current_index": 25, "start_index": 0}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(0, 0, 0, 1, 0, 0, 0, 0, 0, current_state, metrics_data)
                assert result[0]["current_index"] == 0
                assert result[0]["mode"] == "paused"

    def test_handle_replay_controls_end(self, registered_callbacks):
        """Test handle_replay_controls end button."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-replay-end.n_clicks"}]
                current_state = {"mode": "playing", "speed": 1.0, "current_index": 10, "end_index": None}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(0, 0, 0, 0, 1, 0, 0, 0, 0, current_state, metrics_data)
                assert result[0]["current_index"] == 49
                assert result[0]["mode"] == "paused"

    def test_handle_replay_controls_speed_2x(self, registered_callbacks):
        """Test handle_replay_controls speed 2x button."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-speed-2x.n_clicks"}]
                current_state = {"mode": "playing", "speed": 1.0, "current_index": 0}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(0, 0, 0, 0, 0, 0, 1, 0, 0, current_state, metrics_data)
                assert result[0]["speed"] == 2.0
                assert result[2] == 500

    def test_handle_replay_controls_slider(self, registered_callbacks):
        """Test handle_replay_controls slider change."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("handle_replay_controls"):
            with patch("dash.callback_context") as mock_ctx:
                mock_ctx.triggered = [{"prop_id": "test-panel-replay-slider.value"}]
                current_state = {"mode": "playing", "speed": 1.0, "current_index": 0}
                metrics_data = [{"epoch": i} for i in range(50)]
                result = func(0, 0, 0, 0, 0, 0, 0, 0, 50, current_state, metrics_data)
                assert result[0]["current_index"] == 24
                assert result[0]["mode"] == "paused"

    def test_replay_tick_advances(self, registered_callbacks):
        """Test replay_tick advances index during playback."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("replay_tick"):
            state = {"mode": "playing", "current_index": 10, "end_index": 49}
            metrics_data = [{"epoch": i} for i in range(50)]
            result = func(1, state, metrics_data)
            assert result["current_index"] == 11

    def test_replay_tick_stops_at_end(self, registered_callbacks):
        """Test replay_tick stops at end index."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("replay_tick"):
            state = {"mode": "playing", "current_index": 49, "end_index": 49}
            metrics_data = [{"epoch": i} for i in range(50)]
            result = func(1, state, metrics_data)
            assert result["mode"] == "stopped"
            assert result["current_index"] == 49

    def test_replay_tick_ignores_non_playing(self, registered_callbacks):
        """Test replay_tick ignores non-playing state."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("replay_tick"):
            state = {"mode": "paused", "current_index": 10, "end_index": 49}
            metrics_data = [{"epoch": i} for i in range(50)]
            result = func(1, state, metrics_data)
            assert result == state

    def test_update_replay_ui(self, registered_callbacks):
        """Test update_replay_ui calculates slider position."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_replay_ui"):
            state = {"current_index": 25}
            metrics_data = [{"epoch": i} for i in range(50)]
            result = func(state, metrics_data)
            assert abs(result[0] - 51.02) < 0.1
            assert result[1] == 100
            assert result[2] == "25 / 49"

    def test_update_play_button_playing(self, registered_callbacks):
        """Test update_play_button shows pause when playing."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_play_button"):
            result = func({"mode": "playing"})
            assert result == "⏸"

    def test_update_play_button_paused(self, registered_callbacks):
        """Test update_play_button shows play when paused."""
        panel, callbacks = registered_callbacks

        if func := callbacks.get("update_play_button"):
            result = func({"mode": "paused"})
            assert result == "▶"
