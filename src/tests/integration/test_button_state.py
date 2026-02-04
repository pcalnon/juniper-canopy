#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_button_state.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Integration tests for button state management.
#    Tests the full flow: click → disable → send command → receive ack → re-enable
#
#####################################################################################################################################################################################################
import time
from unittest.mock import patch


class TestButtonStateIntegration:
    """Integration tests for button state management."""

    def test_button_click_disables_button(self):
        """Test: Click Start → verify button disabled."""
        from unittest.mock import MagicMock, patch

        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            mock_request = MagicMock()
            mock_request.scheme = "http"
            mock_request.host = "localhost:8050"

            with patch("frontend.dashboard_manager.request", mock_request):
                _, button_states = dashboard._handle_training_buttons_handler(
                    start_clicks=1,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click={"button": None, "timestamp": 0},
                    button_states={
                        "start": {"disabled": False, "loading": False},
                        "pause": {"disabled": False, "loading": False},
                        "stop": {"disabled": False, "loading": False},
                        "resume": {"disabled": False, "loading": False},
                        "reset": {"disabled": False, "loading": False},
                    },
                    trigger="start-button",
                )

            # Verify button is disabled after click
            assert button_states["start"]["disabled"] is True, "Button should be disabled after click"
            assert button_states["start"]["loading"] is True, "Button should show loading state"

    def test_dashboard_has_button_state_stores(self):
        """Test: Dashboard has button state management stores."""
        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        # Verify button state stores exist in layout
        layout_str = str(dashboard.app.layout)
        assert "button-states" in layout_str, "button-states store should exist"
        assert "last-button-click" in layout_str, "last-button-click store should exist"

    def test_button_click_sends_single_command(self):
        """Test: Click Start → verify single command sent."""
        from unittest.mock import MagicMock

        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            mock_request = MagicMock()
            mock_request.scheme = "http"
            mock_request.host = "localhost:8050"

            with patch("frontend.dashboard_manager.request", mock_request):
                action, button_states = dashboard._handle_training_buttons_handler(
                    start_clicks=1,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click={"button": None, "timestamp": 0},
                    button_states={
                        "start": {"disabled": False, "loading": False},
                        "pause": {"disabled": False, "loading": False},
                        "stop": {"disabled": False, "loading": False},
                        "resume": {"disabled": False, "loading": False},
                        "reset": {"disabled": False, "loading": False},
                    },
                    trigger="start-button",
                )

                # Verify single API call
                assert mock_post.call_count == 1

                # Verify correct endpoint
                call_args = mock_post.call_args
                assert "/api/train/start" in str(call_args)

    def test_button_re_enables_after_acknowledgment(self):
        """Test: Click → disable → ack received → button re-enabled."""
        from unittest.mock import MagicMock

        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            mock_request = MagicMock()
            mock_request.scheme = "http"
            mock_request.host = "localhost:8050"

            with patch("frontend.dashboard_manager.request", mock_request):
                action, button_states = dashboard._handle_training_buttons_handler(
                    start_clicks=1,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click={"button": None, "timestamp": 0},
                    button_states={
                        "start": {"disabled": False, "loading": False, "timestamp": 0},
                        "pause": {"disabled": False, "loading": False, "timestamp": 0},
                        "stop": {"disabled": False, "loading": False, "timestamp": 0},
                        "resume": {"disabled": False, "loading": False, "timestamp": 0},
                        "reset": {"disabled": False, "loading": False, "timestamp": 0},
                    },
                    trigger="start-button",
                )

            # Verify disabled
            assert button_states["start"]["disabled"] is True
            assert button_states["start"]["loading"] is True
            assert button_states["start"]["timestamp"] > 0

            # Simulate button was pressed 2.5 seconds ago (exceeds 2s timeout)
            button_states_with_old_timestamp = button_states.copy()
            button_states_with_old_timestamp["start"] = {
                "disabled": True,
                "loading": True,
                "timestamp": time.time() - 2.5,
            }

            new_states = dashboard._handle_button_timeout_and_acks_handler(
                action=None,
                n_intervals=1,
                button_states=button_states_with_old_timestamp,
            )

            # Verify re-enabled after timeout
            assert new_states["start"]["disabled"] is False
            assert new_states["start"]["loading"] is False
            assert new_states["start"]["timestamp"] == 0

    def test_rapid_clicks_only_send_one_command(self):
        """Test: Rapid clicks → verify only one command sent."""
        from unittest.mock import MagicMock

        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            mock_request = MagicMock()
            mock_request.scheme = "http"
            mock_request.host = "localhost:8050"

            with patch("frontend.dashboard_manager.request", mock_request):
                current_time = time.time()
                action1, states1 = dashboard._handle_training_buttons_handler(
                    start_clicks=1,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click={"button": None, "timestamp": 0},
                    button_states={
                        "start": {"disabled": False, "loading": False},
                        "pause": {"disabled": False, "loading": False},
                        "stop": {"disabled": False, "loading": False},
                        "resume": {"disabled": False, "loading": False},
                        "reset": {"disabled": False, "loading": False},
                    },
                    trigger="start-button",
                )

                # Second click within debounce window (< 500ms)
                dashboard._handle_training_buttons_handler(
                    start_clicks=2,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click={"button": "start-button", "timestamp": current_time},
                    button_states=states1,
                    trigger="start-button",
                )

                # Only one API call should have been made
                assert mock_post.call_count == 1

    def test_loading_indicator_visible(self):
        """Test: Button shows loading indicator when clicked."""
        from unittest.mock import MagicMock

        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            mock_request = MagicMock()
            mock_request.scheme = "http"
            mock_request.host = "localhost:8050"

            with patch("frontend.dashboard_manager.request", mock_request):
                action, button_states = dashboard._handle_training_buttons_handler(
                    start_clicks=1,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click={"button": None, "timestamp": 0},
                    button_states={
                        "start": {"disabled": False, "loading": False},
                        "pause": {"disabled": False, "loading": False},
                        "stop": {"disabled": False, "loading": False},
                        "resume": {"disabled": False, "loading": False},
                        "reset": {"disabled": False, "loading": False},
                    },
                    trigger="start-button",
                )

            result = dashboard._update_button_appearance_handler(button_states=button_states)

            start_disabled, start_text = result[0], result[1]

            assert "⏳" in start_text or "..." in start_text, f"Button should show loading indicator, got: {start_text}"
            assert start_disabled is True, "Button should be disabled"

    def test_error_handling_re_enables_button(self):
        """Test: API error → button re-enabled immediately."""
        from frontend.dashboard_manager import DashboardManager

        config = {
            "metrics_panel": {},
            "network_visualizer": {},
            "dataset_plotter": {},
            "decision_boundary": {},
        }

        dashboard = DashboardManager(config)

        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.side_effect = Exception("API Error")

            action, button_states = dashboard._handle_training_buttons_handler(
                start_clicks=1,
                pause_clicks=0,
                stop_clicks=0,
                resume_clicks=0,
                reset_clicks=0,
                last_click={"button": None, "timestamp": 0},
                button_states={
                    "start": {"disabled": False, "loading": False},
                    "pause": {"disabled": False, "loading": False},
                    "stop": {"disabled": False, "loading": False},
                    "resume": {"disabled": False, "loading": False},
                    "reset": {"disabled": False, "loading": False},
                },
                trigger="start-button",
            )

            # Button should be re-enabled on error
            assert button_states["start"]["disabled"] is False
            assert button_states["start"]["loading"] is False
            assert action["success"] is False
