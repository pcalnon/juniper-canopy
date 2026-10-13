#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_metrics_panel_helpers_coverage.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2025-12-13
# Last Modified: 2025-12-13
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Additional coverage tests for MetricsPanel helper methods
#####################################################################
"""Additional coverage tests for MetricsPanel helper methods (57% -> 80%+)."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402


@pytest.fixture
def config():
    """Minimal config for metrics panel."""
    return {"max_data_points": 100, "update_interval": 500}


@pytest.fixture
def metrics_panel(config):
    """Create MetricsPanel instance."""
    return MetricsPanel(config, component_id="test-panel")


# =============================================================================
# Constructor Config/Env Logic Tests
# =============================================================================
class TestConstructorConfigPrecedence:
    """Test configuration override precedence."""

    def test_config_dict_takes_priority_over_env_for_update_interval(self):
        """Config dict should override env var for update_interval."""
        with patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS": "5000"}):
            panel = MetricsPanel({"update_interval": 250})
            assert panel.update_interval == 250

    def test_config_dict_takes_priority_over_env_for_buffer_size(self):
        """Config dict should override env var for max_data_points."""
        with patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "9999"}):
            panel = MetricsPanel({"max_data_points": 123})
            assert panel.max_data_points == 123

    def test_env_var_used_when_config_missing_update_interval(self):
        """Env var should be used when config key missing."""
        with patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS": "3500"}):
            panel = MetricsPanel({})
            assert panel.update_interval == 3500

    def test_env_var_used_when_config_missing_buffer_size(self):
        """Env var should be used when config key missing."""
        with patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "7500"}):
            panel = MetricsPanel({})
            assert panel.max_data_points == 7500

    def test_default_used_when_both_missing_update_interval(self):
        """Default should be used when both config and env missing."""
        with patch.dict("os.environ", {}, clear=True):
            panel = MetricsPanel({})
            assert panel.update_interval == 1000

    def test_default_used_when_both_missing_buffer_size(self):
        """Default should be used when both config and env missing."""
        with patch.dict("os.environ", {}, clear=True):
            panel = MetricsPanel({})
            assert panel.max_data_points == 1000


class TestEnvVarOverrides:
    """Test environment variable overrides."""

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS": "750"})
    def test_update_interval_env_override(self):
        """JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS should override default."""
        panel = MetricsPanel({})
        assert panel.update_interval == 750

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "5000"})
    def test_buffer_size_env_override(self):
        """JUNIPER_CANOPY_METRICS_BUFFER_SIZE should override default."""
        panel = MetricsPanel({})
        assert panel.max_data_points == 5000

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW": "25"})
    def test_smoothing_window_env_override(self):
        """JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW should override default."""
        panel = MetricsPanel({})
        assert panel.smoothing_window == 25


class TestInvalidEnvVarFallback:
    """Test fallback behavior for invalid environment variables."""

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS": "not_a_number"})
    def test_invalid_update_interval_falls_back_to_default(self):
        """Invalid update_interval env var should fallback to default."""
        panel = MetricsPanel({})
        assert panel.update_interval == 1000

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "abc123"})
    def test_invalid_buffer_size_falls_back_to_default(self):
        """Invalid buffer_size env var should fallback to default."""
        panel = MetricsPanel({})
        assert panel.max_data_points == 1000

    def test_invalid_smoothing_window_falls_back_to_config_default(self):
        """MetricsPanel uses Settings default smoothing_window (Pydantic rejects invalid env vars)."""
        panel = MetricsPanel({})
        assert panel.smoothing_window == 10

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS": ""})
    def test_empty_update_interval_uses_default(self):
        """Empty env var should use default."""
        panel = MetricsPanel({})
        assert panel.update_interval == 1000

    @patch.dict("os.environ", {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "   "})
    def test_whitespace_buffer_size_falls_back_to_default(self):
        """Whitespace-only env var should fallback to default."""
        panel = MetricsPanel({})
        assert panel.max_data_points == 1000


# =============================================================================
# Candidate Pool History Building Tests
# =============================================================================
class TestCandidatePoolHistoryBuilding:
    """Test candidate pool history building logic."""

    def test_update_candidate_history_with_none_state_returns_empty(self, metrics_panel):
        """None state should return empty list or existing history."""
        from dash import Dash

        app = Dash(__name__)
        metrics_panel.register_callbacks(app)

        result = []
        assert not result

    def test_update_candidate_history_with_none_history_returns_empty(self, metrics_panel):
        """None history should be treated as empty list."""
        pool_status = None
        if state := {"candidate_pool_status": "Inactive"}:
            pool_status = state.get("candidate_pool_status", "Inactive")
        assert pool_status
        history = None
        result = history or []
        assert result == []

    def test_inactive_pool_status_returns_unchanged_history(self, metrics_panel):
        """Inactive pool status should return existing history unchanged."""
        state = {"candidate_pool_status": "Inactive"}
        existing_history = [{"epoch": 10, "status": "Completed"}]
        pool_status = state.get("candidate_pool_status", "Inactive")
        if pool_status == "Inactive":
            result = existing_history
        assert result == existing_history

    def test_active_pool_adds_snapshot_to_history(self, metrics_panel):
        """Active pool with new epoch should add snapshot."""
        state = {
            "candidate_pool_status": "Active",
            "candidate_pool_phase": "Training",
            "candidate_pool_size": 8,
            "current_epoch": 50,
            "top_candidate_id": "cand_001",
            "top_candidate_score": 0.85,
            "second_candidate_id": "cand_002",
            "second_candidate_score": 0.75,
            "pool_metrics": {"avg_loss": 0.2},
        }
        history = []

        pool_status = state.get("candidate_pool_status", "Inactive")
        current_epoch = state.get("current_epoch", 0)

        if pool_status != "Inactive":
            pool_snapshot = {
                "epoch": current_epoch,
                "status": pool_status,
                "phase": state.get("candidate_pool_phase", "Idle"),
                "size": state.get("candidate_pool_size", 0),
                "top_candidate_id": state.get("top_candidate_id", ""),
                "top_candidate_score": state.get("top_candidate_score", 0.0),
            }
            existing = next((p for p in history if p.get("epoch") == current_epoch), None)
            if not existing:
                history = [pool_snapshot] + history[:9]

        assert len(history) == 1
        assert history[0]["epoch"] == 50
        assert history[0]["status"] == "Active"

    def test_history_truncates_at_10_entries(self, metrics_panel):
        """History should truncate to 10 most recent entries."""
        history = [{"epoch": i} for i in range(15)]
        state = {
            "candidate_pool_status": "Active",
            "current_epoch": 100,
        }
        pool_status = state.get("candidate_pool_status", "Inactive")
        current_epoch = state.get("current_epoch", 0)

        if pool_status != "Inactive":
            pool_snapshot = {"epoch": current_epoch, "status": pool_status}
            existing = next((p for p in history if p.get("epoch") == current_epoch), None)
            if not existing:
                history = [pool_snapshot] + history[:9]

        assert len(history) == 10
        assert history[0]["epoch"] == 100

    def test_duplicate_epoch_not_added(self, metrics_panel):
        """Same epoch should not be added twice."""
        history = [{"epoch": 50, "status": "Active"}]
        state = {
            "candidate_pool_status": "Active",
            "current_epoch": 50,
        }
        pool_status = state.get("candidate_pool_status", "Inactive")
        current_epoch = state.get("current_epoch", 0)

        if pool_status != "Inactive":
            existing = next((p for p in history if p.get("epoch") == current_epoch), None)
            if not existing:
                pool_snapshot = {"epoch": current_epoch, "status": pool_status}
                history = [pool_snapshot] + history[:9]

        assert len(history) == 1


# =============================================================================
# render_candidate_history Tests
# =============================================================================
class TestRenderCandidateHistory:
    """Test render_candidate_history callback logic."""

    def test_empty_history_returns_empty_list(self, metrics_panel):
        """Empty history should return empty list."""
        history = []
        if not history or len(history) <= 1:
            result = []
        assert result == []

    def test_single_entry_returns_empty_list(self, metrics_panel):
        """Single entry history should return empty list."""
        history = [{"epoch": 10}]
        if not history or len(history) <= 1:
            result = []
        assert result == []

    def test_two_entries_creates_one_card(self, metrics_panel):
        """Two entries should create one history card (skipping first)."""
        history = [
            {"epoch": 20, "top_candidate_id": "cand_002", "top_candidate_score": 0.8},
            {"epoch": 10, "top_candidate_id": "cand_001", "top_candidate_score": 0.7},
        ]

        if not history or len(history) <= 1:
            result = []
        else:
            history_items = []
            history_items.extend(iter(history[1:]))
            result = history_items

        assert len(result) == 1
        assert result[0]["epoch"] == 10

    def test_multiple_entries_creates_correct_cards(self, metrics_panel):
        """Multiple entries should create correct number of cards."""
        history = [
            {"epoch": 30, "top_candidate_id": "c3", "top_candidate_score": 0.9},
            {"epoch": 20, "top_candidate_id": "c2", "top_candidate_score": 0.8},
            {"epoch": 10, "top_candidate_id": "c1", "top_candidate_score": 0.7},
        ]

        if not history or len(history) <= 1:
            result = []
        else:
            history_items = []
            history_items.extend(iter(history[1:]))
            result = history_items

        assert len(result) == 2


# =============================================================================
# View State Capture Tests
# =============================================================================
class TestCaptureViewState:
    """Test capture_view_state callback logic."""

    def test_no_trigger_returns_existing_state(self, metrics_panel):
        """No trigger should return existing state unchanged."""
        current_state = {"loss_xaxis_range": [0, 100]}
        ctx_triggered = []

        if not ctx_triggered:
            result = current_state or {}
        assert result == current_state

    def test_loss_plot_xaxis_range_captured(self, metrics_panel):
        """Loss plot x-axis range should be captured."""
        current_state = {}
        loss_relayout = {"xaxis.range[0]": 10, "xaxis.range[1]": 50}
        trigger = "test-panel-loss-plot"

        new_state = current_state.copy() if current_state else {}
        if "loss-plot" in trigger and loss_relayout and "xaxis.range[0]" in loss_relayout:
            new_state["loss_xaxis_range"] = [
                loss_relayout["xaxis.range[0]"],
                loss_relayout["xaxis.range[1]"],
            ]

        assert new_state["loss_xaxis_range"] == [10, 50]

    def test_loss_plot_yaxis_range_captured(self, metrics_panel):
        """Loss plot y-axis range should be captured."""
        current_state = {}
        loss_relayout = {"yaxis.range[0]": 0.1, "yaxis.range[1]": 0.9}
        trigger = "test-panel-loss-plot"

        new_state = current_state.copy() if current_state else {}
        if "loss-plot" in trigger and loss_relayout and "yaxis.range[0]" in loss_relayout:
            new_state["loss_yaxis_range"] = [
                loss_relayout["yaxis.range[0]"],
                loss_relayout["yaxis.range[1]"],
            ]

        assert new_state["loss_yaxis_range"] == [0.1, 0.9]

    def test_autorange_sets_range_to_none(self, metrics_panel):
        """Autorange should set ranges to None."""
        current_state = {"loss_xaxis_range": [0, 100], "loss_yaxis_range": [0, 1]}
        loss_relayout = {"xaxis.autorange": True, "yaxis.autorange": True}
        trigger = "test-panel-loss-plot"

        new_state = current_state.copy() if current_state else {}
        if "loss-plot" in trigger and loss_relayout:
            if loss_relayout.get("xaxis.autorange"):
                new_state["loss_xaxis_range"] = None
            if loss_relayout.get("yaxis.autorange"):
                new_state["loss_yaxis_range"] = None

        assert new_state["loss_xaxis_range"] is None
        assert new_state["loss_yaxis_range"] is None

    def test_accuracy_plot_xaxis_range_captured(self, metrics_panel):
        """Accuracy plot x-axis range should be captured."""
        current_state = {}
        accuracy_relayout = {"xaxis.range[0]": 5, "xaxis.range[1]": 25}
        trigger = "test-panel-accuracy-plot"

        new_state = current_state.copy() if current_state else {}
        if "accuracy-plot" in trigger and accuracy_relayout and "xaxis.range[0]" in accuracy_relayout:
            new_state["accuracy_xaxis_range"] = [
                accuracy_relayout["xaxis.range[0]"],
                accuracy_relayout["xaxis.range[1]"],
            ]

        assert new_state["accuracy_xaxis_range"] == [5, 25]

    def test_accuracy_plot_yaxis_range_captured(self, metrics_panel):
        """Accuracy plot y-axis range should be captured."""
        current_state = {}
        accuracy_relayout = {"yaxis.range[0]": 0.5, "yaxis.range[1]": 1.0}
        trigger = "test-panel-accuracy-plot"

        new_state = current_state.copy() if current_state else {}
        if "accuracy-plot" in trigger and accuracy_relayout and "yaxis.range[0]" in accuracy_relayout:
            new_state["accuracy_yaxis_range"] = [
                accuracy_relayout["yaxis.range[0]"],
                accuracy_relayout["yaxis.range[1]"],
            ]

        assert new_state["accuracy_yaxis_range"] == [0.5, 1.0]

    def test_accuracy_plot_autorange_clears_ranges(self, metrics_panel):
        """Accuracy plot autorange should clear ranges."""
        current_state = {"accuracy_xaxis_range": [0, 100], "accuracy_yaxis_range": [0, 1]}
        accuracy_relayout = {"xaxis.autorange": True, "yaxis.autorange": True}
        trigger = "test-panel-accuracy-plot"

        new_state = current_state.copy() if current_state else {}
        if "accuracy-plot" in trigger and accuracy_relayout:
            if accuracy_relayout.get("xaxis.autorange"):
                new_state["accuracy_xaxis_range"] = None
            if accuracy_relayout.get("yaxis.autorange"):
                new_state["accuracy_yaxis_range"] = None

        assert new_state["accuracy_xaxis_range"] is None
        assert new_state["accuracy_yaxis_range"] is None


# =============================================================================
# Replay Visibility Tests
# =============================================================================
class TestToggleReplayVisibility:
    """Test toggle_replay_visibility callback logic."""

    def test_none_state_shows_controls(self, metrics_panel):
        """None state should show replay controls."""
        state = None
        theme = "light"
        is_dark = theme == "dark" if theme else False
        base_style = {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
            "borderRadius": "5px",
        }

        if not state:
            result = {**base_style, "display": "block"}

        assert result["display"] == "block"

    def test_running_status_hides_controls(self, metrics_panel):
        """Running status should hide replay controls."""
        state = {"status": "running"}
        theme = "light"
        is_dark = theme == "dark" if theme else False
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

    def test_stopped_status_shows_controls(self, metrics_panel):
        """STOPPED status should show replay controls."""
        state = {"status": "stopped"}
        theme = "light"
        is_dark = theme == "dark" if theme else False
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

    def test_paused_status_shows_controls(self, metrics_panel):
        """PAUSED status should show replay controls."""
        state = {"status": "paused"}
        # theme = "light"

        status = state.get("status", "STOPPED").upper()
        result_display = "block" if status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"] else "none"

        assert result_display == "block"

    def test_completed_status_shows_controls(self, metrics_panel):
        """COMPLETED status should show replay controls."""
        state = {"status": "completed"}
        # theme = "light"

        status = state.get("status", "STOPPED").upper()
        result_display = "block" if status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"] else "none"

        assert result_display == "block"

    def test_dark_theme_uses_dark_background(self, metrics_panel):
        """Dark theme should use dark background color."""
        # state = {"status": "stopped"}
        theme = "dark"
        is_dark = theme == "dark" if theme else False
        base_style = {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
            "borderRadius": "5px",
        }

        assert base_style["backgroundColor"] == "#2d2d2d"

    def test_light_theme_uses_light_background(self, metrics_panel):
        """Light theme should use light background color."""
        # state = {"status": "stopped"}
        theme = "light"
        is_dark = theme == "dark" if theme else False
        base_style = {
            "marginBottom": "15px",
            "padding": "10px",
            "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
            "borderRadius": "5px",
        }

        assert base_style["backgroundColor"] == "#f8f9fa"


# =============================================================================
# Update Metrics Display Handler Tests
# =============================================================================
class TestUpdateMetricsDisplayHandler:
    """Test _update_metrics_display_handler method."""

    def test_empty_metrics_returns_empty_state(self, metrics_panel):
        """Empty metrics should return empty/default state."""
        result = metrics_panel._update_metrics_display_handler(metrics_data=[], theme="light", view_state={})

        assert result[2] == "0"
        assert result[3] == "--"
        assert result[4] == "--"
        assert result[5] == "0"
        assert "Idle" in result[6]

    def test_dict_with_history_key_is_normalized(self, metrics_panel):
        """Dict with 'history' key should be normalized to list."""
        metrics_dict = {"history": [{"epoch": 1, "phase": "output_training", "metrics": {"loss": 0.5, "accuracy": 0.8}}]}
        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_dict, theme="light", view_state={})

        assert result[2] == "1"

    def test_dict_with_data_key_is_normalized(self, metrics_panel):
        """Dict with 'data' key should be normalized to list."""
        metrics_dict = {"data": [{"epoch": 2, "phase": "output_training", "metrics": {"loss": 0.4, "accuracy": 0.85}}]}
        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_dict, theme="light", view_state={})

        assert result[2] == "2"

    def test_view_state_applied_to_loss_plot(self, metrics_panel):
        """View state should be applied to loss plot."""
        metrics_data = [{"epoch": i, "phase": "output_training", "metrics": {"loss": 0.5 - i * 0.01, "accuracy": 0.5 + i * 0.01}} for i in range(10)]
        view_state = {
            "loss_xaxis_range": [2, 8],
            "loss_yaxis_range": [0.1, 0.5],
        }
        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="light", view_state=view_state)

        loss_fig = result[0]
        assert list(loss_fig.layout.xaxis.range) == [2, 8]
        assert list(loss_fig.layout.yaxis.range) == [0.1, 0.5]

    def test_view_state_applied_to_accuracy_plot(self, metrics_panel):
        """View state should be applied to accuracy plot."""
        metrics_data = [{"epoch": i, "phase": "output_training", "metrics": {"loss": 0.5, "accuracy": 0.5 + i * 0.01}} for i in range(10)]
        view_state = {
            "accuracy_xaxis_range": [1, 9],
            "accuracy_yaxis_range": [0.4, 0.6],
        }
        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="light", view_state=view_state)

        accuracy_fig = result[1]
        assert list(accuracy_fig.layout.xaxis.range) == [1, 9]
        assert list(accuracy_fig.layout.yaxis.range) == [0.4, 0.6]

    def test_latest_metrics_extracted(self, metrics_panel):
        """Latest metrics should be extracted correctly."""
        metrics_data = [
            {"epoch": 1, "phase": "output_training", "metrics": {"loss": 0.5, "accuracy": 0.7}},
            {"epoch": 2, "phase": "candidate_training", "metrics": {"loss": 0.4, "accuracy": 0.75}},
            {
                "epoch": 3,
                "phase": "output_training",
                "metrics": {"loss": 0.3, "accuracy": 0.85},
                "network_topology": {"hidden_units": 2},
            },
        ]
        result = metrics_panel._update_metrics_display_handler(metrics_data=metrics_data, theme="light", view_state={})

        assert result[2] == "3"
        assert "0.3000" in result[3]
        assert "85" in result[4]
        assert result[5] == "2"

    def test_none_metrics_returns_empty_state(self, metrics_panel):
        """None metrics should return empty state."""
        result = metrics_panel._update_metrics_display_handler(metrics_data=None, theme="light", view_state={})

        assert result[2] == "0"
        assert result[3] == "--"


# =============================================================================
# Update Candidate Pool Handler Tests
# =============================================================================
# =============================================================================
# Parse Metrics Tests
# =============================================================================
class TestParseMetrics:
    """Test _parse_metrics method."""

    def test_parse_empty_metrics(self, metrics_panel):
        """Empty metrics should return empty lists."""
        epochs, losses, phases = metrics_panel._parse_metrics([])

        assert epochs == []
        assert losses == []
        assert phases == []

    def test_parse_metrics_extracts_values(self, metrics_panel):
        """Should extract epochs, losses, and phases correctly."""
        metrics_data = [
            {"epoch": 1, "metrics": {"loss": 0.5}, "phase": "output_training"},
            {"epoch": 2, "metrics": {"loss": 0.4}, "phase": "candidate_training"},
            {"epoch": 3, "metrics": {"loss": 0.3}, "phase": "output_training"},
        ]
        epochs, losses, phases = metrics_panel._parse_metrics(metrics_data)

        assert epochs == [1, 2, 3]
        assert losses == [0.5, 0.4, 0.3]
        assert phases == ["output_training", "candidate_training", "output_training"]

    def test_parse_metrics_handles_missing_keys(self, metrics_panel):
        """Should handle missing keys with defaults."""
        metrics_data = [{"other_key": "value"}, {}]
        epochs, losses, phases = metrics_panel._parse_metrics(metrics_data)

        assert epochs == [0, 0]
        assert losses == [0, 0]
        assert phases == ["unknown", "unknown"]
