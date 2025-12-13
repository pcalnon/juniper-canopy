#!/usr/bin/env python
"""
Unit tests for DashboardManager helper methods.

Target coverage improvement for:
- _get_training_defaults_with_env
- _api_url
- _toggle_dark_mode_handler
- _update_theme_state_handler
- _update_status_bar_handler
- _handle_training_buttons_handler (via CallbackContextAdapter)
"""
import os
from unittest.mock import Mock, patch

import dash
import pytest
from werkzeug.test import EnvironBuilder


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
            assert isinstance(defaults["learning_rate"], float)
            assert isinstance(defaults["hidden_units"], int)
            assert isinstance(defaults["epochs"], int)

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
            assert isinstance(manager.training_defaults["hidden_units"], int)
            assert manager.training_defaults["hidden_units"] > 0

    def test_invalid_epochs_fallback(self, reset_singletons):
        """Test invalid CASCOR_TRAINING_EPOCHS falls back to default."""
        from frontend.dashboard_manager import DashboardManager

        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "3.14"}):
            # float string is invalid for int conversion
            manager = DashboardManager({})
            assert isinstance(manager.training_defaults["epochs"], int)
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

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            url = manager._api_url("/api/health")
            assert "api/health" in url
            assert url.startswith("http://")

    def test_api_url_without_leading_slash(self, reset_singletons):
        """Test _api_url without leading slash in path."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

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
        """Test _api_url preserves HTTPS scheme."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="https://secure.example.com:443/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            url = manager._api_url("/api/status")
            assert url.startswith("https://")

    def test_api_url_http_scheme(self, reset_singletons):
        """Test _api_url uses HTTP scheme correctly."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            url = manager._api_url("/api/train/start")
            assert url.startswith("http://")
            assert "localhost" in url

    def test_api_url_preserves_host(self, reset_singletons):
        """Test _api_url preserves the request host."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://myhost.local:9000/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            url = manager._api_url("/api/topology")
            assert "myhost.local:9000" in url

    def test_api_url_different_paths(self, reset_singletons):
        """Test _api_url with various API paths."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        paths = [
            "/api/health",
            "/api/metrics/history",
            "/api/train/start",
            "/api/set_params",
            "/api/decision_boundary",
        ]

        with manager.app.server.request_context(env):
            for path in paths:
                url = manager._api_url(path)
                assert path.lstrip("/") in url


class TestThemeHandlers:
    """Tests for dark mode / theme handling methods."""

    def test_toggle_dark_mode_first_click_light_to_dark(self, reset_singletons):
        """Test first click toggles from light to dark."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # First click (n_clicks=1) -> odd -> dark mode
        is_dark, icon = manager._toggle_dark_mode_handler(n_clicks=1)
        assert is_dark is True
        assert icon == "☀️"  # Sun icon shows when in dark mode (to switch to light)

    def test_toggle_dark_mode_second_click_dark_to_light(self, reset_singletons):
        """Test second click toggles from dark back to light."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # Second click (n_clicks=2) -> even -> light mode
        is_dark, icon = manager._toggle_dark_mode_handler(n_clicks=2)
        assert is_dark is False
        assert icon == "🌙"  # Moon icon shows when in light mode (to switch to dark)

    def test_toggle_dark_mode_repeated_clicks(self, reset_singletons):
        """Test repeated clicks toggle back and forth."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # Simulate multiple clicks
        for i in range(1, 5):
            is_dark, icon = manager._toggle_dark_mode_handler(n_clicks=i)
            expected_dark = i % 2 == 1  # Odd clicks = dark, even clicks = light
            assert is_dark == expected_dark, f"Click {i}: expected dark={expected_dark}, got {is_dark}"

    def test_toggle_dark_mode_zero_clicks(self, reset_singletons):
        """Test zero clicks results in light mode."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # n_clicks=0 -> even -> light mode
        is_dark, icon = manager._toggle_dark_mode_handler(n_clicks=0)
        assert is_dark is False
        assert icon == "🌙"

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


class TestStatusBarUpdateHandler:
    """Tests for _update_status_bar_handler method."""

    @patch("requests.get")
    def test_healthy_response(self, mock_get, reset_singletons):
        """Test status bar update with healthy API response."""
        from frontend.dashboard_manager import DashboardManager

        # Create mock responses for both health and status endpoints
        mock_health_response = Mock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {"status": "healthy"}

        mock_status_response = Mock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "phase": "output",
            "current_epoch": 10,
            "hidden_units": 3,
            "is_running": True,
            "is_paused": False,
        }

        mock_get.side_effect = [mock_health_response, mock_status_response]

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_status_bar_handler(n_intervals=1)

        # Returns tuple: (style_dict, status_text, latency_text)
        assert len(result) == 3
        style, status_text, latency_text = result
        assert "color" in style
        assert "Running" in status_text
        assert "ms" in latency_text

    @patch("requests.get")
    def test_error_response(self, mock_get, reset_singletons):
        """Test status bar update with error response."""
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
            result = manager._update_status_bar_handler(n_intervals=1)

        # Should return error indicators
        assert len(result) == 3
        style, status_text, latency_text = result
        assert style["color"] == "#dc3545"  # Red for error
        assert "Error" in status_text

    @patch("requests.get")
    def test_timeout_response(self, mock_get, reset_singletons):
        """Test status bar update with timeout."""
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
            result = manager._update_status_bar_handler(n_intervals=1)

        style, status_text, _ = result
        assert style["color"] == "#dc3545"  # Red for error

    @patch("requests.get")
    def test_backend_unavailable(self, mock_get, reset_singletons):
        """Test status bar when backend returns non-200."""
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
            result = manager._update_status_bar_handler(n_intervals=1)

        style, status_text, _ = result
        assert "Unavailable" in status_text


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


class TestNetworkInfoToggleHandlers:
    """Tests for network info collapse toggle handlers."""

    def test_toggle_network_info_first_click(self, reset_singletons):
        """Test first click on network info header."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        # n=1 means first click, should collapse (return True -> n%2==1)
        result = manager._toggle_network_info_handler(n=1)
        assert result is True

    def test_toggle_network_info_second_click(self, reset_singletons):
        """Test second click expands again."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._toggle_network_info_handler(n=2)
        assert result is False

    def test_toggle_network_info_no_clicks(self, reset_singletons):
        """Test default state with no clicks."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._toggle_network_info_handler(n=None)
        assert result is True  # Default expanded

    def test_toggle_network_info_details_first_click(self, reset_singletons):
        """Test first click on details section."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._toggle_network_info_details_handler(n=1)
        assert result is True  # Opens details

    def test_toggle_network_info_details_no_clicks(self, reset_singletons):
        """Test default state for details (collapsed)."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._toggle_network_info_details_handler(n=None)
        assert result is False  # Default collapsed


class TestTopStatusPhaseHandler:
    """Tests for top status/phase display handler."""

    @patch("requests.get")
    def test_running_status_display(self, mock_get, reset_singletons):
        """Test running status displays correctly."""
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "STARTED", "phase": "OUTPUT"}
        mock_get.return_value = mock_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_top_status_phase_handler(n_intervals=1)

        # Returns tuple: (status, status_style, phase, phase_style)
        status, status_style, phase, phase_style = result
        assert status == "Running"
        assert status_style["color"] == "#28a745"  # Green
        assert phase == "Output Training"

    @patch("requests.get")
    def test_paused_status_display(self, mock_get, reset_singletons):
        """Test paused status displays with orange color."""
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "PAUSED", "phase": "CANDIDATE"}
        mock_get.return_value = mock_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_top_status_phase_handler(n_intervals=1)

        status, status_style, phase, phase_style = result
        assert status == "Paused"
        assert status_style["color"] == "#ffc107"  # Orange
        assert phase == "Candidate Pool"

    @patch("requests.get")
    def test_error_status_display(self, mock_get, reset_singletons):
        """Test error case displays error styling."""
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
            result = manager._update_top_status_phase_handler(n_intervals=1)

        status, status_style, phase, phase_style = result
        assert status == "Error"
        assert status_style["color"] == "#dc3545"  # Red

    @patch("requests.get")
    def test_stopped_status_display(self, mock_get, reset_singletons):
        """Test stopped status displays with gray color."""
        from frontend.dashboard_manager import DashboardManager

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "STOPPED", "phase": "IDLE"}
        mock_get.return_value = mock_response

        manager = DashboardManager({})

        builder = EnvironBuilder(
            method="GET",
            base_url="http://localhost:8050/dashboard/",
            path="/dashboard/",
        )
        env = builder.get_environ()

        with manager.app.server.request_context(env):
            result = manager._update_top_status_phase_handler(n_intervals=1)

        status, status_style, phase, phase_style = result
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
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {"learning_rate": 0.01, "hidden_units": 10, "epochs": 200}
        disabled, status = manager._track_param_changes_handler(lr=0.01, hu=10, epochs=200, applied=applied)

        assert disabled is True  # Button disabled when no changes
        assert status == ""

    def test_track_param_changes_with_changes(self, reset_singletons):
        """Test tracking when params differ from applied."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        applied = {"learning_rate": 0.01, "hidden_units": 10, "epochs": 200}
        disabled, status = manager._track_param_changes_handler(lr=0.02, hu=10, epochs=200, applied=applied)

        assert disabled is False  # Button enabled when changes exist
        assert "Unsaved" in status

    def test_track_param_changes_no_applied(self, reset_singletons):
        """Test tracking when no applied params exist."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        disabled, status = manager._track_param_changes_handler(lr=0.01, hu=10, epochs=200, applied=None)

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
            params, status = manager._apply_parameters_handler(n_clicks=1, lr=0.02, hu=15, epochs=300)

        assert params["learning_rate"] == 0.02
        assert params["hidden_units"] == 15
        assert params["epochs"] == 300
        assert "✓" in status

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
            params, status = manager._apply_parameters_handler(n_clicks=1, lr=0.02, hu=15, epochs=300)

        assert params == dash.no_update
        assert "❌" in status

    def test_apply_parameters_no_clicks(self, reset_singletons):
        """Test apply with no clicks returns no_update."""
        from frontend.dashboard_manager import DashboardManager

        manager = DashboardManager({})

        result = manager._apply_parameters_handler(n_clicks=None, lr=0.01, hu=10, epochs=200)
        assert result == (dash.no_update, dash.no_update)
