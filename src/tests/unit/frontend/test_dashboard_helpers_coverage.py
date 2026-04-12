#!/usr/bin/env python
"""
Unit tests for DashboardManager helper methods.

Target coverage improvement for:
- _get_training_defaults_with_env
- _api_url
- _toggle_dark_mode_handler
- _update_theme_state_handler
- _update_unified_status_bar_handler
- _handle_training_buttons_handler (via CallbackContextAdapter)
"""

import os
from unittest.mock import Mock, patch

import dash
from werkzeug.test import EnvironBuilder

# import pytest


class TestGetTrainingDefaultsWithEnv:
    """Tests for _get_training_defaults_with_env method."""

    def test_base_config_present(self, reset_singletons):
        """Test when base config provides all defaults."""
        from frontend.dashboard_manager import DashboardManager

        # Clear any CASCOR env vars
        env_clean = {k: v for k, v in os.environ.items() if not k.startswith("CASCOR_TRAINING_")}
        with patch.dict(os.environ, env_clean, clear=True):
            manager = DashboardManager({})
            defaults = manager.training_defaults

            assert "learning_rate" in defaults
            assert "hidden_units" in defaults
            assert "epochs" in defaults
            assert isinstance(defaults["learning_rate"], (int, float))
            assert isinstance(defaults["hidden_units"], (int, float))
            assert isinstance(defaults["epochs"], (int, float))

    def test_env_var_override_learning_rate(self, reset_singletons):
        """Test CASCOR_TRAINING_LEARNING_RATE override."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_LEARNING_RATE": "0.123"}):
            manager = DashboardManager({})
            assert manager.training_defaults["learning_rate"] == 0.123

    def test_env_var_override_hidden_units(self, reset_singletons):
        """Test CASCOR_TRAINING_HIDDEN_UNITS override."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_HIDDEN_UNITS": "42"}):
            manager = DashboardManager({})
            assert manager.training_defaults["hidden_units"] == 42

    def test_env_var_override_epochs(self, reset_singletons):
        """Test CASCOR_TRAINING_EPOCHS override."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "999"}):
            manager = DashboardManager({})
            assert manager.training_defaults["epochs"] == 999

    def test_all_env_var_overrides(self, reset_singletons):
        """Test all three env var overrides together."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(
            os.environ,
            {
                "CASCOR_TRAINING_LEARNING_RATE": "0.05",
                "CASCOR_TRAINING_HIDDEN_UNITS": "25",
                "CASCOR_TRAINING_EPOCHS": "500",
            },
        ):
            manager = DashboardManager({})
            assert manager.training_defaults["learning_rate"] == 0.05
            assert manager.training_defaults["hidden_units"] == 25
            assert manager.training_defaults["epochs"] == 500

    def test_invalid_learning_rate_fallback(self, reset_singletons):
        """Test invalid CASCOR_TRAINING_LEARNING_RATE falls back to default."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_LEARNING_RATE": "not_a_float"}):
            manager = DashboardManager({})
            # Should have a valid float, not the invalid string
            assert isinstance(manager.training_defaults["learning_rate"], float)
            assert manager.training_defaults["learning_rate"] > 0

    def test_invalid_hidden_units_fallback(self, reset_singletons):
        """Test invalid CASCOR_TRAINING_HIDDEN_UNITS falls back to default."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_HIDDEN_UNITS": "abc"}):
            manager = DashboardManager({})
            assert isinstance(manager.training_defaults["hidden_units"], (int, float))
            assert manager.training_defaults["hidden_units"] > 0

    def test_invalid_epochs_fallback(self, reset_singletons):
        """Test invalid CASCOR_TRAINING_EPOCHS falls back to default."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "3.14"}):
            # float string is invalid for int conversion
            manager = DashboardManager({})
            assert isinstance(manager.training_defaults["epochs"], (int, float))
            assert manager.training_defaults["epochs"] > 0

    def test_partial_env_var_overrides(self, reset_singletons):
        """Test only some env vars set, others use defaults."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(
            os.environ,
            {"CASCOR_TRAINING_LEARNING_RATE": "0.02"},
            clear=False,
        ):
            # Clear other CASCOR vars
            os.environ.pop("CASCOR_TRAINING_HIDDEN_UNITS", None)
            os.environ.pop("CASCOR_TRAINING_EPOCHS", None)

            manager = DashboardManager({})
            assert manager.training_defaults["learning_rate"] == 0.02
            assert "hidden_units" in manager.training_defaults
            assert "epochs" in manager.training_defaults


class TestApiUrl:
    """Tests for _api_url helper method."""

    def test_api_url_with_leading_slash(self, reset_singletons):
        """Test _api_url with leading slash in path."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        url = manager._api_url("/api/health")
        assert "api/health" in url
        assert url.startswith("http://127.0.0.1:")

    def test_api_url_without_leading_slash(self, reset_singletons):
        """Test _api_url without leading slash in path."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        url = manager._api_url("api/metrics")
        assert "api/metrics" in url

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            url = manager._api_url("api/metrics")
            assert "api/metrics" in url

    def test_api_url_https_scheme(self, reset_singletons):
        """Test _api_url uses settings-based URL (always http to local server)."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        url = manager._api_url("/api/status")
        assert url.startswith("http://127.0.0.1:")
        assert "/api/status" in url

    def test_api_url_http_scheme(self, reset_singletons):
        """Test _api_url constructs correct URL from settings."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        url = manager._api_url("/api/train/start")
        assert url.startswith("http://")
        assert "/api/train/start" in url

    def test_api_url_preserves_host(self, reset_singletons):
        """Test _api_url uses configured server port."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        url = manager._api_url("/api/topology")
        assert "127.0.0.1" in url
        assert "/api/topology" in url

    def test_api_url_different_paths(self, reset_singletons):
        """Test _api_url with various API paths."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        paths = [
            "/api/health",
            "/api/metrics/history",
            "/api/train/start",
            "/api/set_params",
            "/api/decision_boundary",
        ]

        for path in paths:
            url = manager._api_url(path)
            assert path.lstrip("/") in url


class TestThemeHandlers:
    """Tests for dark mode / theme handling methods."""

    def test_toggle_dark_mode_from_light_to_dark(self, reset_singletons):
        """Test toggling from light mode (False) to dark mode (True)."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # current_dark_mode=False -> toggled to True (dark mode)
        is_dark, icon = manager._toggle_dark_mode_handler(current_dark_mode=False)
        assert is_dark is True
        assert icon == "☀️"  # Sun icon shows when in dark mode (to switch to light)

    def test_toggle_dark_mode_from_dark_to_light(self, reset_singletons):
        """Test toggling from dark mode (True) to light mode (False)."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # current_dark_mode=True -> toggled to False (light mode)
        is_dark, icon = manager._toggle_dark_mode_handler(current_dark_mode=True)
        assert is_dark is False
        assert icon == "🌙"  # Moon icon shows when in light mode (to switch to dark)

    def test_toggle_dark_mode_repeated_toggles(self, reset_singletons):
        """Test repeated toggles alternate between dark and light."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # Simulate toggling back and forth
        current = False
        for i in range(1, 5):
            is_dark, icon = manager._toggle_dark_mode_handler(current_dark_mode=current)
            expected_dark = not current
            assert is_dark == expected_dark, f"Toggle {i}: expected dark={expected_dark}, got {is_dark}"
            current = is_dark

    def test_toggle_dark_mode_none_becomes_dark(self, reset_singletons):
        """Test None current_dark_mode results in dark mode (not None = True)."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # current_dark_mode=None -> not None = True (dark mode)
        is_dark, icon = manager._toggle_dark_mode_handler(current_dark_mode=None)
        assert is_dark is True
        assert icon == "☀️"

    def test_update_theme_state_dark(self, reset_singletons):
        """Test theme state returns 'dark' when is_dark is True."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._update_theme_state_handler(is_dark=True)
        assert result == "dark"

    def test_update_theme_state_light(self, reset_singletons):
        """Test theme state returns 'light' when is_dark is False."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._update_theme_state_handler(is_dark=False)
        assert result == "light"

    def test_update_theme_state_none(self, reset_singletons):
        """Test theme state returns 'light' when is_dark is None."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._update_theme_state_handler(is_dark=None)
        assert result == "light"


class TestUnifiedStatusBarHandler:
    """Tests for _update_unified_status_bar_handler method."""

    @patch("requests.get")
    def test_healthy_response(self, mock_get, reset_singletons):
        """Test unified status bar update with healthy API response."""
        from frontend.dashboard_manager import DashboardManager

        # Create mock response for status endpoint (single request)
        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 3,
            "is_running": True,
            "is_paused": False,
        }

        mock_get.return_value = mock_status_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        # Returns tuple of 9 elements for unified status bar
        assert len(result) == 9
        (
            indicator_style,
            connection_status,
            latency_text,
            status,
            status_style,
            phase,
            phase_style,
            epoch,
            hidden_units,
        ) = result
        assert "color" in indicator_style
        assert status == "Running"
        assert phase == "Output Training"
        assert "ms" in latency_text
        assert epoch == "10"
        assert hidden_units == "3"

    @patch("requests.get")
    def test_error_response(self, mock_get, reset_singletons):
        """Test unified status bar update with error response."""
        import requests

        from frontend.dashboard_manager import DashboardManager

        mock_get.side_effect = requests.RequestException("Connection refused")

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        # Returns 9 elements with error indicators
        assert len(result) == 9
        indicator_style = result[0]
        status = result[3]
        status_style = result[4]
        assert indicator_style["color"] == "#dc3545"  # Red for error
        assert status == "Error"
        assert status_style["color"] == "#dc3545"

    @patch("requests.get")
    def test_timeout_response(self, mock_get, reset_singletons):
        """Test unified status bar update with timeout."""
        import requests

        from frontend.dashboard_manager import DashboardManager

        mock_get.side_effect = requests.Timeout("Request timed out")

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        indicator_style = result[0]
        assert indicator_style["color"] == "#dc3545"  # Red for error

    @patch("requests.get")
    def test_backend_unavailable(self, mock_get, reset_singletons):
        """Test unified status bar when backend returns non-200."""
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 503

        mock_get.return_value = mock_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        connection_status = result[1]
        assert "Unavailable" in connection_status


class TestTrainingButtonHandlers:
    """Tests for training control button handlers."""

    @patch("requests.post")
    def test_start_button_click(self, mock_post, reset_singletons):
        """Test start button click using CallbackContextAdapter."""
        from frontend.callback_context import CallbackContextAdapter
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = DashboardManager({})

        # Set test trigger
        ctx = CallbackContextAdapter()
        ctx.set_test_trigger("start-button")

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        try:
            with manager.app.server.request_context(env):
                result = manager._handle_training_buttons_handler(
                    start_clicks=1,
                    pause_clicks=0,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click=None,
                    button_states=button_states,
                    trigger="start-button",
                )

            assert result != (dash.no_update, dash.no_update)
            action, new_states = result
            assert action["last"] == "start-button"
            assert action["success"] is True
        finally:
            ctx.clear_test_trigger()

    @patch("requests.post")
    def test_pause_button_click(self, mock_post, reset_singletons):
        """Test pause button click."""
        from frontend.callback_context import CallbackContextAdapter
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = DashboardManager({})
        ctx = CallbackContextAdapter()
        ctx.set_test_trigger("pause-button")

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        try:
            with manager.app.server.request_context(env):
                result = manager._handle_training_buttons_handler(
                    start_clicks=0,
                    pause_clicks=1,
                    stop_clicks=0,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click=None,
                    button_states=button_states,
                    trigger="pause-button",
                )

            action, _ = result
            assert action["last"] == "pause-button"
        finally:
            ctx.clear_test_trigger()

    def test_no_trigger_returns_no_update(self, reset_singletons):
        """Test handler with no trigger returns no_update."""
        from frontend.callback_context import CallbackContextAdapter
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})
        ctx = CallbackContextAdapter()
        ctx.set_test_trigger(None)

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        try:
            result = manager._handle_training_buttons_handler(
                start_clicks=0,
                pause_clicks=0,
                stop_clicks=0,
                resume_clicks=0,
                reset_clicks=0,
                last_click=None,
                button_states=button_states,
                trigger=None,
            )

            assert result == (dash.no_update, dash.no_update)
        finally:
            ctx.clear_test_trigger()

    @patch("requests.post")
    def test_button_debouncing(self, mock_post, reset_singletons):
        """Test rapid clicks are debounced."""
        import time

        from frontend.callback_context import CallbackContextAdapter
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        manager = DashboardManager({})
        ctx = CallbackContextAdapter()
        ctx.set_test_trigger("start-button")

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        # Simulate recent click (within debounce window)
        recent_click = {"button": "start-button", "timestamp": time.time() - 0.1}

        try:
            result = manager._handle_training_buttons_handler(
                start_clicks=2,
                pause_clicks=0,
                stop_clicks=0,
                resume_clicks=0,
                reset_clicks=0,
                last_click=recent_click,
                button_states=button_states,
                trigger="start-button",
            )

            # Should be debounced - no_update
            assert result == (dash.no_update, dash.no_update)
        finally:
            ctx.clear_test_trigger()

    @patch("requests.post")
    def test_button_error_handling(self, mock_post, reset_singletons):
        """Test button handler gracefully handles API errors."""
        import requests

        from frontend.callback_context import CallbackContextAdapter
        from frontend.dashboard_manager import DashboardManager

        mock_post.side_effect = requests.RequestException("API unavailable")

        manager = DashboardManager({})
        ctx = CallbackContextAdapter()
        ctx.set_test_trigger("stop-button")

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        try:
            with manager.app.server.request_context(env):
                result = manager._handle_training_buttons_handler(
                    start_clicks=0,
                    pause_clicks=0,
                    stop_clicks=1,
                    resume_clicks=0,
                    reset_clicks=0,
                    last_click=None,
                    button_states=button_states,
                    trigger="stop-button",
                )

            action, new_states = result
            assert action["success"] is False
            # Button should be re-enabled on error
            assert new_states["stop"]["loading"] is False
        finally:
            ctx.clear_test_trigger()


class TestTopStatusPhaseHandler:
    """Tests for top status/phase display via unified handler."""

    @patch("requests.get")
    def test_running_status_display(self, mock_get, reset_singletons):
        """Test running status displays correctly in unified bar."""
        from frontend.dashboard_manager import DashboardManager

        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "phase": "output",
            "current_epoch": 5,
            "hidden_units": 2,
        }
        mock_get.return_value = mock_status_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        # Unified handler returns 9 elements
        status = result[3]
        status_style = result[4]
        phase = result[5]
        assert status == "Running"
        assert status_style["color"] == "#28a745"  # Green
        assert phase == "Output Training"

    @patch("requests.get")
    def test_paused_status_display(self, mock_get, reset_singletons):
        """Test paused status displays with orange color in unified bar."""
        from frontend.dashboard_manager import DashboardManager

        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "is_running": False,
            "is_paused": True,
            "phase": "candidate",
            "current_epoch": 10,
            "hidden_units": 3,
        }
        mock_get.return_value = mock_status_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        status = result[3]
        status_style = result[4]
        phase = result[5]
        assert status == "Paused"
        assert status_style["color"] == "#ffc107"  # Orange
        assert phase == "Candidate Pool"

    @patch("requests.get")
    def test_error_status_display(self, mock_get, reset_singletons):
        """Test error case displays error styling in unified bar."""
        import requests

        from frontend.dashboard_manager import DashboardManager

        mock_get.side_effect = requests.RequestException("Failed")

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        status = result[3]
        status_style = result[4]
        assert status == "Error"
        assert status_style["color"] == "#dc3545"  # Red

    @patch("requests.get")
    def test_stopped_status_display(self, mock_get, reset_singletons):
        """Test stopped status displays with gray color in unified bar."""
        from frontend.dashboard_manager import DashboardManager

        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "is_running": False,
            "is_paused": False,
            "phase": "idle",
            "current_epoch": 0,
            "hidden_units": 0,
        }
        mock_get.return_value = mock_status_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_unified_status_bar_handler(n_intervals=1)

        status = result[3]
        status_style = result[4]
        phase = result[5]
        assert status == "Stopped"
        assert status_style["color"] == "#6c757d"  # Gray
        assert phase == "Idle"


class TestButtonAppearanceHandler:
    """Tests for button appearance update handler."""

    def test_button_appearance_normal_state(self, reset_singletons):
        """Test button appearance in normal state."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        result = manager._update_button_appearance_handler(button_states=button_states)

        # Returns 10 values: (start_disabled, start_text, pause_disabled, pause_text, ...)
        assert len(result) == 10
        start_disabled, start_text = result[0], result[1]
        assert start_disabled is False
        assert "▶" in start_text

    def test_button_appearance_loading_state(self, reset_singletons):
        """Test button appearance in loading state."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": 100},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }

        result = manager._update_button_appearance_handler(button_states=button_states)

        start_disabled, start_text = result[0], result[1]
        assert start_disabled is True
        assert "⏳" in start_text  # Loading indicator


class TestParameterTrackingHandler:
    """Tests for parameter change tracking handler."""

    def test_track_param_changes_no_changes(self, reset_singletons):
        """Test tracking when params match applied."""
        import dash

        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {
            "nn_max_iterations": 1000,
            "nn_max_total_epochs": 1000000,
            "nn_learning_rate": 0.01,
            "nn_max_hidden_units": 1000,
            "nn_multi_node_layers": False,
            "nn_growth_trigger": "convergence",
            "nn_growth_preset_epochs": 50,
            "nn_growth_convergence_threshold": 0.001,
            "nn_patience": 50,
            "nn_spiral_rotations": 1.5,
            "nn_spiral_number": 2,
            "nn_dataset_elements": 1000,
            "nn_dataset_noise": 0.25,
            "cn_pool_size": 100,
            "cn_correlation_threshold": 0.001,
            "cn_selected_candidates": 1,
            "cn_training_complete": "preset_epochs",
            "cn_training_iterations": 500,
            "cn_training_convergence_threshold": 0.0001,
            "cn_patience": 30,
            "cn_multi_candidate": False,
            "cn_candidate_selection": None,
            "cn_top_candidates": 1,
            "cn_random_candidates": 1,
        }
        disabled, status = manager._track_param_changes_handler(1000, 1000000, 0.01, 1000, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1, applied)

        assert disabled is True  # Button disabled when no changes
        assert status is dash.no_update

    def test_track_param_changes_with_changes(self, reset_singletons):
        """Test tracking when params differ from applied."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {
            "nn_max_iterations": 1000,
            "nn_max_total_epochs": 1000000,
            "nn_learning_rate": 0.01,
            "nn_max_hidden_units": 1000,
            "nn_multi_node_layers": False,
            "nn_growth_trigger": "convergence",
            "nn_growth_preset_epochs": 50,
            "nn_growth_convergence_threshold": 0.001,
            "nn_patience": 50,
            "nn_spiral_rotations": 1.5,
            "nn_spiral_number": 2,
            "nn_dataset_elements": 1000,
            "nn_dataset_noise": 0.25,
            "cn_pool_size": 100,
            "cn_correlation_threshold": 0.001,
            "cn_selected_candidates": 1,
            "cn_training_complete": "preset_epochs",
            "cn_training_iterations": 500,
            "cn_training_convergence_threshold": 0.0001,
            "cn_patience": 30,
            "cn_multi_candidate": False,
            "cn_candidate_selection": None,
            "cn_top_candidates": 1,
            "cn_random_candidates": 1,
        }
        disabled, status = manager._track_param_changes_handler(1000, 1000000, 0.05, 1000, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1, applied)

        assert disabled is False  # Button enabled when changes exist
        assert "Unsaved" in status

    def test_track_param_changes_no_applied(self, reset_singletons):
        """Test tracking when no applied params exist."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        disabled, status = manager._track_param_changes_handler(1000, 1000000, 0.01, 1000, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1, None)

        assert disabled is True
        assert status == ""


class TestApplyParametersHandler:
    """Tests for apply parameters handler."""

    @patch("requests.post")
    def test_apply_parameters_success(self, mock_post, reset_singletons):
        """Test successful parameter application."""
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            params, status = manager._apply_parameters_handler(1, 1000, 1000000, 0.02, 15, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1)

        assert params["nn_learning_rate"] == 0.02
        assert params["nn_max_hidden_units"] == 15
        assert "Parameters applied" in status

    @patch("requests.post")
    def test_apply_parameters_failure(self, mock_post, reset_singletons):
        """Test parameter application failure."""
        import requests

        from frontend.dashboard_manager import DashboardManager

        mock_post.side_effect = requests.RequestException("API error")

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            params, status = manager._apply_parameters_handler(1, 1000, 1000000, 0.02, 15, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1)

        assert params == dash.no_update
        assert "Error:" in status or "Failed" in status

    def test_apply_parameters_no_clicks(self, reset_singletons):
        """Test apply with no clicks returns no_update."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._apply_parameters_handler(None, 1000, 1000000, 0.01, 1000, [], "convergence", 50, 0.001, 50, 1.5, 2, 1000, 0.25, 100, 0.001, 1, "preset_epochs", 500, 0.0001, 30, [], None, 1, 1)
        assert result == (dash.no_update, dash.no_update)
