#!/usr/bin/env python
"""
Direct handler tests for dashboard_manager.py to improve coverage from 68% to 90%+.

This file tests the handler methods directly (lines 630-1500) which include:
- Theme toggle handlers
- Status bar update handlers
- Network info handlers
- Training button handlers
- Parameter handlers
- Data store handlers
"""
import time
from unittest.mock import MagicMock, Mock, patch

import dash
import pytest

from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dashboard_manager():
    """Create dashboard manager instance for testing."""
    config = {
        "metrics_panel": {},
        "network_visualizer": {},
        "dataset_plotter": {},
        "decision_boundary": {},
    }
    return DashboardManager(config)


# =============================================================================
# Theme Toggle Handlers (Lines 632-658)
# =============================================================================
@pytest.mark.unit
class TestThemeToggleHandlers:
    """Test theme toggle callback handlers."""

    def test_toggle_dark_mode_handler_odd_clicks(self, dashboard_manager):
        """Test dark mode toggle returns (True, sun icon) for odd clicks."""
        result = dashboard_manager._toggle_dark_mode_handler(n_clicks=1)
        assert result[0] is True
        assert result[1] == "☀️"

    def test_toggle_dark_mode_handler_even_clicks(self, dashboard_manager):
        """Test dark mode toggle returns (False, moon icon) for even clicks."""
        result = dashboard_manager._toggle_dark_mode_handler(n_clicks=2)
        assert result[0] is False
        assert result[1] == "🌙"

    def test_toggle_dark_mode_handler_zero_clicks(self, dashboard_manager):
        """Test dark mode toggle returns (False, moon icon) for zero clicks."""
        result = dashboard_manager._toggle_dark_mode_handler(n_clicks=0)
        assert result[0] is False
        assert result[1] == "🌙"

    def test_toggle_dark_mode_handler_three_clicks(self, dashboard_manager):
        """Test dark mode toggle returns (True, sun icon) for 3 clicks."""
        result = dashboard_manager._toggle_dark_mode_handler(n_clicks=3)
        assert result[0] is True
        assert result[1] == "☀️"

    def test_update_theme_state_handler_dark(self, dashboard_manager):
        """Test theme state update for dark mode returns 'dark'."""
        result = dashboard_manager._update_theme_state_handler(is_dark=True)
        assert result == "dark"

    def test_update_theme_state_handler_light(self, dashboard_manager):
        """Test theme state update for light mode returns 'light'."""
        result = dashboard_manager._update_theme_state_handler(is_dark=False)
        assert result == "light"

    def test_update_theme_state_handler_none(self, dashboard_manager):
        """Test theme state update with None returns 'light'."""
        result = dashboard_manager._update_theme_state_handler(is_dark=None)
        assert result == "light"


# =============================================================================
# Network Info Handlers (Lines 681-1150)
# =============================================================================
@pytest.mark.unit
class TestNetworkInfoHandlers:
    """Test network info panel handlers."""

    def test_toggle_network_info_handler_odd(self, dashboard_manager):
        """Test network info collapse toggle for odd clicks."""
        result = dashboard_manager._toggle_network_info_handler(n=1)
        assert result is True

    def test_toggle_network_info_handler_even(self, dashboard_manager):
        """Test network info collapse toggle for even clicks."""
        result = dashboard_manager._toggle_network_info_handler(n=2)
        assert result is False

    def test_toggle_network_info_handler_none(self, dashboard_manager):
        """Test network info collapse toggle for None."""
        result = dashboard_manager._toggle_network_info_handler(n=None)
        assert result is True

    def test_toggle_network_info_details_handler_odd(self, dashboard_manager):
        """Test network info details collapse toggle for odd clicks."""
        result = dashboard_manager._toggle_network_info_details_handler(n=1)
        assert result is True

    def test_toggle_network_info_details_handler_even(self, dashboard_manager):
        """Test network info details collapse toggle for even clicks."""
        result = dashboard_manager._toggle_network_info_details_handler(n=2)
        assert result is False

    def test_toggle_network_info_details_handler_none(self, dashboard_manager):
        """Test network info details collapse toggle for None."""
        result = dashboard_manager._toggle_network_info_details_handler(n=None)
        assert result is False

    @patch("requests.get")
    def test_update_network_info_handler_success(self, mock_get, dashboard_manager):
        """Test network info update with successful API response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "input_size": 2,
            "hidden_units": 3,
            "output_size": 1,
            "current_epoch": 50,
            "current_phase": "Output Training",
            "network_connected": True,
            "monitoring_active": True,
        }
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_handler(n=1)

        assert result is not None
        assert hasattr(result, "children")

    @patch("requests.get")
    def test_update_network_info_handler_failure(self, mock_get, dashboard_manager):
        """Test network info update with API failure."""
        mock_get.side_effect = Exception("Connection error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_handler(n=1)

        assert result is not None
        assert "Unable to fetch" in str(result)

    @patch("requests.get")
    def test_update_network_info_details_handler_success(self, mock_get, dashboard_manager):
        """Test network info details update with success."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "threshold_function": "sigmoid",
            "optimizer": "sgd",
            "total_nodes": 10,
        }
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_details_handler(n=1)

        assert result is not None

    @patch("requests.get")
    def test_update_network_info_details_handler_failure(self, mock_get, dashboard_manager):
        """Test network info details update with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_details_handler(n=1)

        assert result is not None
        assert "Unable to fetch" in str(result)


# =============================================================================
# Status Bar Handlers (Lines 940-1070)
# =============================================================================
@pytest.mark.unit
class TestStatusBarHandlers:
    """Test status bar update handlers."""

    @patch("requests.get")
    def test_update_unified_status_bar_handler_success(self, mock_get, dashboard_manager):
        """Test unified status bar update with success."""
        mock_health = Mock()
        mock_health.status_code = 200

        mock_status = Mock()
        mock_status.status_code = 200
        mock_status.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 3,
        }

        mock_get.side_effect = [mock_health, mock_status]

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)

        assert len(result) == 9
        assert result[3] == "Running"
        assert result[5] == "Output Training"

    @patch("requests.get")
    def test_update_unified_status_bar_handler_paused(self, mock_get, dashboard_manager):
        """Test unified status bar with paused state."""
        mock_health = Mock()
        mock_health.status_code = 200

        mock_status = Mock()
        mock_status.status_code = 200
        mock_status.json.return_value = {
            "is_running": True,
            "is_paused": True,
            "phase": "candidate",
            "current_epoch": 50,
            "hidden_units": 5,
        }

        mock_get.side_effect = [mock_health, mock_status]

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)

        assert result[3] == "Paused"
        assert result[5] == "Candidate Pool"

    @patch("requests.get")
    def test_update_unified_status_bar_handler_stopped(self, mock_get, dashboard_manager):
        """Test unified status bar with stopped state."""
        mock_health = Mock()
        mock_health.status_code = 200

        mock_status = Mock()
        mock_status.status_code = 200
        mock_status.json.return_value = {
            "is_running": False,
            "is_paused": False,
            "phase": "idle",
            "current_epoch": 0,
            "hidden_units": 0,
        }

        mock_get.side_effect = [mock_health, mock_status]

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)

        assert result[3] == "Stopped"
        assert result[5] == "Idle"

    @patch("requests.get")
    def test_update_unified_status_bar_handler_backend_error(self, mock_get, dashboard_manager):
        """Test unified status bar with backend error."""
        mock_health = Mock()
        mock_health.status_code = 500

        mock_get.side_effect = [mock_health]

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)

        assert len(result) == 9
        assert result[3] == "Error"

    @patch("requests.get")
    def test_update_unified_status_bar_handler_exception(self, mock_get, dashboard_manager):
        """Test unified status bar with exception."""
        mock_get.side_effect = Exception("Connection failed")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)

        assert result[1] == "Connection Error"
        assert result[3] == "Error"

    @patch("requests.get")
    def test_build_unified_status_bar_content_latency_green(self, mock_get, dashboard_manager):
        """Test status bar content with low latency (green)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 2,
        }

        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50)

        assert result[0]["color"] == "#28a745"  # Green

    @patch("requests.get")
    def test_build_unified_status_bar_content_latency_orange(self, mock_get, dashboard_manager):
        """Test status bar content with medium latency (orange)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 2,
        }

        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=250)

        assert result[0]["color"] == "#ffc107"  # Orange

    @patch("requests.get")
    def test_build_unified_status_bar_content_latency_red(self, mock_get, dashboard_manager):
        """Test status bar content with high latency (red)."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 2,
        }

        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=600)

        assert result[0]["color"] == "#dc3545"  # Red

    def test_build_unified_status_bar_content_inference_phase(self, dashboard_manager):
        """Test status bar content with inference phase."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "phase": "inference",
            "current_epoch": 100,
            "hidden_units": 8,
        }

        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50)

        assert result[5] == "Inference"


# =============================================================================
# Data Store Handlers (Lines 1170-1256)
# =============================================================================
@pytest.mark.unit
class TestDataStoreHandlers:
    """Test data store update handlers."""

    @patch("requests.get")
    def test_update_metrics_store_handler_success_with_history(self, mock_get, dashboard_manager):
        """Test metrics store update with history key."""
        mock_response = Mock()
        mock_response.json.return_value = {"history": [{"epoch": 1, "loss": 0.5}, {"epoch": 2, "loss": 0.4}]}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)

        assert len(result) == 2
        assert result[0]["epoch"] == 1

    @patch("requests.get")
    def test_update_metrics_store_handler_success_with_data(self, mock_get, dashboard_manager):
        """Test metrics store update with data key."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": [{"epoch": 1, "loss": 0.5}]}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)

        assert len(result) == 1

    @patch("requests.get")
    def test_update_metrics_store_handler_success_with_list(self, mock_get, dashboard_manager):
        """Test metrics store update with direct list response."""
        mock_response = Mock()
        mock_response.json.return_value = [{"epoch": 1}]
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)

        assert result == [{"epoch": 1}]

    @patch("requests.get")
    def test_update_metrics_store_handler_empty_dict(self, mock_get, dashboard_manager):
        """Test metrics store update with empty dict."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)

        assert result == []

    @patch("requests.get")
    def test_update_metrics_store_handler_failure(self, mock_get, dashboard_manager):
        """Test metrics store update with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)

        assert result == []

    @patch("requests.get")
    def test_update_topology_store_handler_active_tab(self, mock_get, dashboard_manager):
        """Test topology store update when topology tab is active."""
        mock_response = Mock()
        mock_response.json.return_value = {"nodes": [], "connections": []}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_topology_store_handler(n=1, active_tab="topology")

        assert result == {"nodes": [], "connections": []}

    def test_update_topology_store_handler_inactive_tab(self, dashboard_manager):
        """Test topology store update when different tab is active."""
        result = dashboard_manager._update_topology_store_handler(n=1, active_tab="metrics")

        assert result == dash.no_update

    @patch("requests.get")
    def test_update_topology_store_handler_failure(self, mock_get, dashboard_manager):
        """Test topology store update with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_topology_store_handler(n=1, active_tab="topology")

        assert result == {}

    @patch("requests.get")
    def test_update_dataset_store_handler_active_tab(self, mock_get, dashboard_manager):
        """Test dataset store update when dataset tab is active."""
        mock_response = Mock()
        mock_response.json.return_value = {"inputs": [[1, 2]], "targets": [0]}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_dataset_store_handler(n=1, active_tab="dataset")

        assert result == {"inputs": [[1, 2]], "targets": [0]}

    def test_update_dataset_store_handler_inactive_tab(self, dashboard_manager):
        """Test dataset store update when different tab is active."""
        result = dashboard_manager._update_dataset_store_handler(n=1, active_tab="metrics")

        assert result == dash.no_update

    @patch("requests.get")
    def test_update_dataset_store_handler_failure(self, mock_get, dashboard_manager):
        """Test dataset store update with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_dataset_store_handler(n=1, active_tab="dataset")

        assert result is None

    @patch("requests.get")
    def test_update_boundary_store_handler_active_tab(self, mock_get, dashboard_manager):
        """Test boundary store update when boundaries tab is active."""
        mock_response = Mock()
        mock_response.json.return_value = {"grid": [], "predictions": []}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_store_handler(n=1, active_tab="boundaries")

        assert result == {"grid": [], "predictions": []}

    def test_update_boundary_store_handler_inactive_tab(self, dashboard_manager):
        """Test boundary store update when different tab is active."""
        result = dashboard_manager._update_boundary_store_handler(n=1, active_tab="metrics")

        assert result == dash.no_update

    @patch("requests.get")
    def test_update_boundary_store_handler_failure(self, mock_get, dashboard_manager):
        """Test boundary store update with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_store_handler(n=1, active_tab="boundaries")

        assert result is None

    @patch("requests.get")
    def test_update_boundary_store_handler_passes_resolution(self, mock_get, dashboard_manager):
        """Test boundary store handler appends resolution query param to API URL."""
        mock_response = Mock()
        mock_response.json.return_value = {"xx": [], "yy": [], "Z": []}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            dashboard_manager._update_boundary_store_handler(n=1, active_tab="boundaries", resolution=75)

        call_url = mock_get.call_args[0][0]
        assert "resolution=75" in call_url

    @patch("requests.get")
    def test_update_boundary_store_handler_no_resolution(self, mock_get, dashboard_manager):
        """Test boundary store handler omits resolution param when None."""
        mock_response = Mock()
        mock_response.json.return_value = {"xx": [], "yy": [], "Z": []}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            dashboard_manager._update_boundary_store_handler(n=1, active_tab="boundaries")

        call_url = mock_get.call_args[0][0]
        assert "resolution" not in call_url

    @patch("requests.get")
    def test_update_boundary_dataset_store_handler_active_tab(self, mock_get, dashboard_manager):
        """Test boundary dataset store update when boundaries tab is active."""
        mock_response = Mock()
        mock_response.json.return_value = {"inputs": [], "targets": []}
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_dataset_store_handler(n=1, active_tab="boundaries")

        assert result == {"inputs": [], "targets": []}

    def test_update_boundary_dataset_store_handler_inactive_tab(self, dashboard_manager):
        """Test boundary dataset store update when different tab is active."""
        result = dashboard_manager._update_boundary_dataset_store_handler(n=1, active_tab="topology")

        assert result == dash.no_update

    @patch("requests.get")
    def test_update_boundary_dataset_store_handler_failure(self, mock_get, dashboard_manager):
        """Test boundary dataset store update with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_dataset_store_handler(n=1, active_tab="boundaries")

        assert result is None


# =============================================================================
# Training Button Handlers (Lines 1258-1373)
# =============================================================================
@pytest.mark.unit
class TestTrainingButtonHandlers:
    """Test training control button handlers."""

    @patch("requests.post")
    def test_handle_training_buttons_handler_start(self, mock_post, dashboard_manager):
        """Test start button handler."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
        }

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._handle_training_buttons_handler(
                start_clicks=1,
                button_states=button_states,
                trigger="start-button",
            )

        assert result[0]["success"] is True
        assert result[1]["start"]["loading"] is True

    @patch("requests.post")
    def test_handle_training_buttons_handler_pause(self, mock_post, dashboard_manager):
        """Test pause button handler."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
        }

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._handle_training_buttons_handler(
                pause_clicks=1,
                button_states=button_states,
                trigger="pause-button",
            )

        assert result[0]["success"] is True

    @patch("requests.post")
    def test_handle_training_buttons_handler_stop(self, mock_post, dashboard_manager):
        """Test stop button handler."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        button_states = {"stop": {"disabled": False, "loading": False, "timestamp": 0}}

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._handle_training_buttons_handler(
                stop_clicks=1,
                button_states=button_states,
                trigger="stop-button",
            )

        assert result[0]["success"] is True

    @patch("requests.post")
    def test_handle_training_buttons_handler_resume(self, mock_post, dashboard_manager):
        """Test resume button handler."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        button_states = {"resume": {"disabled": False, "loading": False, "timestamp": 0}}

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._handle_training_buttons_handler(
                resume_clicks=1,
                button_states=button_states,
                trigger="resume-button",
            )

        assert result[0]["success"] is True

    @patch("requests.post")
    def test_handle_training_buttons_handler_reset(self, mock_post, dashboard_manager):
        """Test reset button handler."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        button_states = {"reset": {"disabled": False, "loading": False, "timestamp": 0}}

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._handle_training_buttons_handler(
                reset_clicks=1,
                button_states=button_states,
                trigger="reset-button",
            )

        assert result[0]["success"] is True

    @patch("requests.post")
    def test_handle_training_buttons_handler_failure(self, mock_post, dashboard_manager):
        """Test button handler with API failure."""
        mock_post.side_effect = Exception("Connection error")

        button_states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._handle_training_buttons_handler(
                start_clicks=1,
                button_states=button_states,
                trigger="start-button",
            )

        assert result[0]["success"] is False
        assert result[1]["start"]["loading"] is False

    def test_handle_training_buttons_handler_debounce(self, dashboard_manager):
        """Test button handler debouncing."""
        button_states = {"start": {"disabled": False, "loading": False, "timestamp": 0}}
        current_time = time.time()
        last_click = {"button": "start-button", "timestamp": current_time - 0.2}

        result = dashboard_manager._handle_training_buttons_handler(
            start_clicks=1,
            button_states=button_states,
            trigger="start-button",
            last_click=last_click,
        )

        assert result == (dash.no_update, dash.no_update)

    def test_handle_training_buttons_handler_unknown_button(self, dashboard_manager):
        """Test button handler with unknown button."""
        button_states = {}

        result = dashboard_manager._handle_training_buttons_handler(
            button_states=button_states,
            trigger="unknown-button",
        )

        assert result == (dash.no_update, dash.no_update)

    def test_update_last_click_handler_with_action(self, dashboard_manager):
        """Test last click update with action."""
        action = {"last": "start-button", "ts": 12345.0}

        result = dashboard_manager._update_last_click_handler(action=action)

        assert result["button"] == "start-button"
        assert result["timestamp"] == 12345.0

    def test_update_last_click_handler_without_action(self, dashboard_manager):
        """Test last click update without action."""
        result = dashboard_manager._update_last_click_handler(action=None)

        assert result == dash.no_update

    def test_update_last_click_handler_empty_action(self, dashboard_manager):
        """Test last click update with empty action."""
        result = dashboard_manager._update_last_click_handler(action={})

        assert result == dash.no_update


# =============================================================================
# Button Appearance Handlers (Lines 1319-1346)
# =============================================================================
@pytest.mark.unit
class TestButtonAppearanceHandlers:
    """Test button appearance update handlers."""

    def test_update_button_appearance_handler_normal(self, dashboard_manager):
        """Test button appearance with normal state."""
        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        result = dashboard_manager._update_button_appearance_handler(button_states=button_states)

        assert len(result) == 10  # 5 buttons x 2 (disabled, text)
        assert result[0] is False  # start disabled
        assert "▶ Start Training" in result[1]

    def test_update_button_appearance_handler_loading(self, dashboard_manager):
        """Test button appearance with loading state."""
        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        result = dashboard_manager._update_button_appearance_handler(button_states=button_states)

        assert result[0] is True  # start disabled
        assert "⏳" in result[1]  # loading indicator

    def test_update_button_appearance_handler_empty_states(self, dashboard_manager):
        """Test button appearance with empty states."""
        result = dashboard_manager._update_button_appearance_handler(button_states={})

        assert len(result) == 10
        # All should have default values
        assert result[0] is False


# =============================================================================
# Button Timeout Handler (Lines 1348-1373)
# =============================================================================
@pytest.mark.unit
class TestButtonTimeoutHandlers:
    """Test button timeout and acknowledgment handlers."""

    def test_handle_button_timeout_no_states(self, dashboard_manager):
        """Test timeout handler with no button states."""
        result = dashboard_manager._handle_button_timeout_and_acks_handler(button_states=None)

        assert result == dash.no_update

    def test_handle_button_timeout_not_loading(self, dashboard_manager):
        """Test timeout handler when buttons are not loading."""
        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
        }

        result = dashboard_manager._handle_button_timeout_and_acks_handler(
            button_states=button_states,
            n_intervals=1,
        )

        assert result == dash.no_update

    def test_handle_button_timeout_reset_after_timeout(self, dashboard_manager):
        """Test timeout handler resets button after 2s."""
        old_time = time.time() - 3.0  # 3 seconds ago
        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": old_time},
        }

        result = dashboard_manager._handle_button_timeout_and_acks_handler(
            button_states=button_states,
            n_intervals=1,
        )

        assert result["start"]["loading"] is False
        assert result["start"]["disabled"] is False

    def test_handle_button_timeout_no_reset_before_timeout(self, dashboard_manager):
        """Test timeout handler doesn't reset before 2s - returns unchanged states."""
        recent_time = time.time() - 0.5  # 0.5 seconds ago
        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": recent_time},
        }

        result = dashboard_manager._handle_button_timeout_and_acks_handler(
            button_states=button_states,
            n_intervals=1,
        )

        # Should return no_update since no changes needed (not timed out yet)
        assert result == dash.no_update


# =============================================================================
# Parameter Handlers (Lines 1375-1457)
# =============================================================================
@pytest.mark.unit
class TestParameterHandlers:
    """Test parameter input and sync handlers."""

    @patch("requests.get")
    def test_sync_backend_params_handler_success(self, mock_get, dashboard_manager):
        """Test backend params sync with success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "learning_rate": 0.02,
            "max_hidden_units": 15,
            "max_epochs": 300,
            "convergence_enabled": True,
            "convergence_threshold": 0.001,
        }
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._sync_backend_params_handler(n=1)

        assert result["learning_rate"] == 0.02
        assert result["max_hidden_units"] == 15
        assert result["max_epochs"] == 300
        assert result["convergence_enabled"] is True
        assert result["convergence_threshold"] == 0.001

    @patch("requests.get")
    def test_sync_backend_params_handler_failure(self, mock_get, dashboard_manager):
        """Test backend params sync with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._sync_backend_params_handler(n=1)

        assert result == dash.no_update

    @patch("requests.get")
    def test_sync_backend_params_handler_bad_status(self, mock_get, dashboard_manager):
        """Test backend params sync with bad status code."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._sync_backend_params_handler(n=1)

        assert result == dash.no_update

    def test_handle_parameter_changes_handler_learning_rate(self, dashboard_manager):
        """Test parameter change handler for learning rate."""
        result = dashboard_manager._handle_parameter_changes_handler(
            learning_rate=0.05,
            trigger="learning-rate-input",
        )

        assert result == dash.no_update

    def test_handle_parameter_changes_handler_hidden_units(self, dashboard_manager):
        """Test parameter change handler for hidden units."""
        result = dashboard_manager._handle_parameter_changes_handler(
            max_hidden_units=20,
            trigger="max-hidden-units-input",
        )

        assert result == dash.no_update

    def test_track_param_changes_handler_no_applied(self, dashboard_manager):
        """Test param changes tracking with no applied values."""
        result = dashboard_manager._track_param_changes_handler(lr=0.01, hu=10, epochs=200, conv_enabled=["enabled"], conv_threshold=0.001, applied=None)

        assert result == (True, "")

    def test_track_param_changes_handler_no_changes(self, dashboard_manager):
        """Test param changes tracking with no changes."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200, "convergence_enabled": True, "convergence_threshold": 0.001}

        result = dashboard_manager._track_param_changes_handler(lr=0.01, hu=10, epochs=200, conv_enabled=["enabled"], conv_threshold=0.001, applied=applied)

        assert result[0] is True  # disabled
        assert result[1] == ""

    def test_track_param_changes_handler_with_changes(self, dashboard_manager):
        """Test param changes tracking with changes."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200, "convergence_enabled": True, "convergence_threshold": 0.001}

        result = dashboard_manager._track_param_changes_handler(lr=0.05, hu=10, epochs=200, conv_enabled=["enabled"], conv_threshold=0.001, applied=applied)

        assert result[0] is False  # enabled
        assert "Unsaved" in result[1]

    @patch("requests.post")
    def test_apply_parameters_handler_success(self, mock_post, dashboard_manager):
        """Test apply parameters handler with success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._apply_parameters_handler(n_clicks=1, lr=0.02, hu=15, epochs=300, conv_enabled=["enabled"], conv_threshold=0.001)

        assert result[0]["learning_rate"] == 0.02
        assert "applied" in result[1].lower()

    @patch("requests.post")
    def test_apply_parameters_handler_failure(self, mock_post, dashboard_manager):
        """Test apply parameters handler with failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._apply_parameters_handler(n_clicks=1, lr=0.02, hu=15, epochs=300, conv_enabled=["enabled"], conv_threshold=0.001)

        assert result[0] == dash.no_update
        assert "Failed" in result[1]

    @patch("requests.post")
    def test_apply_parameters_handler_exception(self, mock_post, dashboard_manager):
        """Test apply parameters handler with exception."""
        mock_post.side_effect = Exception("Connection error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._apply_parameters_handler(n_clicks=1, lr=0.02, hu=15, epochs=300, conv_enabled=["enabled"], conv_threshold=0.001)

        assert result[0] == dash.no_update
        assert "Error" in result[1]

    def test_apply_parameters_handler_no_clicks(self, dashboard_manager):
        """Test apply parameters handler with no clicks."""
        result = dashboard_manager._apply_parameters_handler(n_clicks=None, lr=0.02, hu=15, epochs=300, conv_enabled=["enabled"], conv_threshold=0.001)

        assert result == (dash.no_update, dash.no_update)

    def test_apply_parameters_handler_with_none_values(self, dashboard_manager):
        """Test apply parameters handler with None values uses defaults."""
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
                result = dashboard_manager._apply_parameters_handler(n_clicks=1, lr=None, hu=None, epochs=None, conv_enabled=None, conv_threshold=None)

            assert result[0]["learning_rate"] == 0.01  # default
            assert result[0]["max_hidden_units"] == 10  # default
            assert result[0]["max_epochs"] == 200  # default
            assert result[0]["convergence_enabled"] is False  # None -> empty list -> False
            assert result[0]["convergence_threshold"] == 0.001  # default

    @patch("requests.get")
    def test_init_applied_params_handler_success(self, mock_get, dashboard_manager):
        """Test init applied params with success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "learning_rate": 0.01,
            "max_hidden_units": 10,
            "max_epochs": 200,
            "convergence_enabled": True,
            "convergence_threshold": 0.001,
        }
        mock_get.return_value = mock_response

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._init_applied_params_handler(n=1, current=None)

        assert result["learning_rate"] == 0.01
        assert result["convergence_enabled"] is True
        assert result["convergence_threshold"] == 0.001

    def test_init_applied_params_handler_already_set(self, dashboard_manager):
        """Test init applied params when already set."""
        current = {"learning_rate": 0.02}

        result = dashboard_manager._init_applied_params_handler(n=1, current=current)

        assert result == dash.no_update

    @patch("requests.get")
    def test_init_applied_params_handler_failure(self, mock_get, dashboard_manager):
        """Test init applied params with failure."""
        mock_get.side_effect = Exception("API error")

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._init_applied_params_handler(n=1, current=None)

        assert result == dash.no_update


# =============================================================================
# Input Value Sync Handler (Lines 1071-1079)
# =============================================================================
@pytest.mark.unit
class TestInputValueSyncHandlers:
    """Test input value synchronization handlers."""

    def test_sync_input_values_from_backend_handler_with_state(self, dashboard_manager):
        """Test sync input values with backend state."""
        backend_state = {
            "learning_rate": 0.02,
            "max_hidden_units": 15,
            "max_epochs": 300,
            "convergence_enabled": True,
            "convergence_threshold": 0.001,
        }

        result = dashboard_manager._sync_input_values_from_backend_handler(backend_state=backend_state)

        assert result == (0.02, 15, 300, ["enabled"], 0.001)

    def test_sync_input_values_from_backend_handler_without_state(self, dashboard_manager):
        """Test sync input values without backend state."""
        result = dashboard_manager._sync_input_values_from_backend_handler(backend_state=None)

        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_sync_input_values_from_backend_handler_empty_state(self, dashboard_manager):
        """Test sync input values with empty dict returns no_update (empty dict is falsy)."""
        result = dashboard_manager._sync_input_values_from_backend_handler(backend_state={})

        # Empty dict is falsy, so returns no_update
        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_sync_input_values_from_backend_handler_partial_state(self, dashboard_manager):
        """Test sync input values with partial state."""
        backend_state = {"learning_rate": 0.05}

        result = dashboard_manager._sync_input_values_from_backend_handler(backend_state=backend_state)

        assert result[0] == 0.05  # provided
        assert result[1] == 10  # default
        assert result[2] == 200  # default
        assert result[3] == ["enabled"]  # default (convergence_enabled=True -> ["enabled"])
        assert result[4] == 0.001  # default
