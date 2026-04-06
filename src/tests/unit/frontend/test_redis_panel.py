#!/usr/bin/env python
"""
Unit tests for Redis monitoring panel component (P3-6).

Tests cover:
- Layout contains expected components (status badge, health card, metrics card)
- _api_url() helper builds correct URLs
- Callback registration works correctly
- Status badge colors match status values (via layout inspection)
- Error handling for failed API calls
- Formatting helper functions
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

src_dir = Path(__file__).parents[3]
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))


@pytest.fixture
def config():
    """Minimal config for Redis panel."""
    return {
        "interval_ms": 5000,
        "api_timeout": 2,
        "api_base_url": "http://localhost:8050",
    }


@pytest.fixture
def redis_panel(config):
    """Create RedisPanel instance."""
    from frontend.components.redis_panel import RedisPanel

    return RedisPanel(config, component_id="test-redis-panel")


@pytest.mark.unit
class TestRedisPanelLayout:
    """Test Redis panel layout structure."""

    def test_layout_returns_div(self, redis_panel):
        """get_layout returns html.Div."""
        from dash import html

        layout = redis_panel.get_layout()
        assert isinstance(layout, html.Div)

    def test_layout_has_component_id(self, redis_panel):
        """Layout div has correct component id."""
        layout = redis_panel.get_layout()
        assert layout.id == "test-redis-panel"

    def test_layout_contains_status_badge(self, redis_panel):
        """Layout contains status badge component."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "status-badge" in layout_str

    def test_layout_contains_mode_badge(self, redis_panel):
        """Layout contains mode badge component."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "mode-badge" in layout_str

    def test_layout_contains_health_card(self, redis_panel):
        """Layout contains health metrics card."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Health" in layout_str

    def test_layout_contains_metrics_card(self, redis_panel):
        """Layout contains performance metrics card."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Metrics" in layout_str

    def test_layout_contains_version_field(self, redis_panel):
        """Layout contains version display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Version" in layout_str

    def test_layout_contains_uptime_field(self, redis_panel):
        """Layout contains uptime display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Uptime" in layout_str

    def test_layout_contains_clients_field(self, redis_panel):
        """Layout contains connected clients display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Connected Clients" in layout_str

    def test_layout_contains_latency_field(self, redis_panel):
        """Layout contains latency display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Latency" in layout_str

    def test_layout_contains_memory_field(self, redis_panel):
        """Layout contains memory usage display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Memory Usage" in layout_str

    def test_layout_contains_ops_sec_field(self, redis_panel):
        """Layout contains ops/sec display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Ops/sec" in layout_str

    def test_layout_contains_hit_rate_field(self, redis_panel):
        """Layout contains hit rate display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Hit Rate" in layout_str

    def test_layout_contains_keyspace_field(self, redis_panel):
        """Layout contains keyspace display field."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "Keyspace" in layout_str

    def test_layout_contains_interval_component(self, redis_panel):
        """Layout contains refresh interval component."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "refresh-interval" in layout_str

    def test_layout_contains_error_display(self, redis_panel):
        """Layout contains error display area."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert "error-display" in layout_str


@pytest.mark.unit
class TestApiUrlHelper:
    """Test _api_url() helper function."""

    def test_api_url_builds_correct_path(self, redis_panel):
        """_api_url builds correct full URL."""
        url = redis_panel._api_url("/api/v1/redis/status")
        assert url.endswith("/api/v1/redis/status")

    def test_api_url_uses_config_base_url(self, config):
        """_api_url uses api_base_url from config."""
        from frontend.components.redis_panel import RedisPanel

        config["api_base_url"] = "http://custom:9090"
        panel = RedisPanel(config, component_id="test")

        url = panel._api_url("/api/v1/redis/metrics")
        assert url == "http://custom:9090/api/v1/redis/metrics"

    def test_api_url_default_base_url(self):
        """_api_url uses settings-based URL when not configured."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({}, component_id="test")

        url = panel._api_url("/api/v1/redis/status")
        assert url.endswith("/api/v1/redis/status")
        assert "8050" in url


@pytest.mark.unit
class TestCallbackRegistration:
    """Test callback registration."""

    def test_register_callbacks_decorates_app(self, redis_panel):
        """register_callbacks calls app.callback decorator."""
        mock_app = MagicMock()
        redis_panel.register_callbacks(mock_app)

        mock_app.callback.assert_called_once()

    def test_register_callbacks_stores_function(self, redis_panel):
        """register_callbacks stores callback function reference."""
        mock_app = MagicMock()
        redis_panel.register_callbacks(mock_app)

        assert hasattr(redis_panel, "_cb_update_redis_panel")

    def test_callback_has_correct_output_count(self, redis_panel):
        """Callback decorator is called with 13 outputs."""
        mock_app = MagicMock()
        redis_panel.register_callbacks(mock_app)

        call_args = mock_app.callback.call_args
        outputs = call_args[0][0]
        assert len(outputs) == 13

    def test_callback_has_correct_input(self, redis_panel):
        """Callback decorator is called with interval input."""
        mock_app = MagicMock()
        redis_panel.register_callbacks(mock_app)

        call_args = mock_app.callback.call_args
        inputs = call_args[0][1]
        assert "refresh-interval" in str(inputs)


@pytest.mark.unit
class TestStatusColorMapping:
    """Test status to color mapping logic (conceptual validation)."""

    def test_status_colors_are_bootstrap_valid(self):
        """Verify expected status colors are valid Bootstrap colors."""
        valid_colors = {"success", "danger", "warning", "secondary", "info", "primary"}

        expected_mappings = {
            "UP": "success",
            "DOWN": "danger",
            "DISABLED": "warning",
            "UNAVAILABLE": "secondary",
        }

        for status, color in expected_mappings.items():
            assert color in valid_colors, f"Color {color} for {status} not in Bootstrap colors"

    def test_mode_colors_are_bootstrap_valid(self):
        """Verify expected mode colors are valid Bootstrap colors."""
        valid_colors = {"success", "danger", "warning", "secondary", "info", "primary"}

        expected_mappings = {
            "DEMO": "info",
            "LIVE": "primary",
            "DISABLED": "secondary",
        }

        for mode, color in expected_mappings.items():
            assert color in valid_colors, f"Color {color} for {mode} not in Bootstrap colors"


@pytest.mark.unit
class TestFormattingHelpers:
    """Test formatting helper functions."""

    def test_format_uptime_seconds(self, redis_panel):
        """Format seconds correctly."""
        assert redis_panel._format_uptime(45) == "45s"

    def test_format_uptime_minutes(self, redis_panel):
        """Format minutes correctly."""
        assert redis_panel._format_uptime(125) == "2m 5s"

    def test_format_uptime_hours(self, redis_panel):
        """Format hours correctly."""
        result = redis_panel._format_uptime(3725)
        assert "1h" in result
        assert "2m" in result

    def test_format_uptime_days(self, redis_panel):
        """Format days correctly."""
        result = redis_panel._format_uptime(90000)
        assert "1d" in result

    def test_format_uptime_none(self, redis_panel):
        """Handle None uptime value."""
        assert redis_panel._format_uptime(None) == "--"

    def test_format_uptime_invalid(self, redis_panel):
        """Handle invalid uptime value."""
        assert redis_panel._format_uptime("invalid") == "--"

    def test_format_latency(self, redis_panel):
        """Format latency correctly."""
        assert redis_panel._format_latency(1.234) == "1.23"

    def test_format_latency_none(self, redis_panel):
        """Handle None latency value."""
        assert redis_panel._format_latency(None) == "--"

    def test_format_memory_bytes(self, redis_panel):
        """Format bytes correctly."""
        assert "B" in redis_panel._format_memory(512)

    def test_format_memory_kilobytes(self, redis_panel):
        """Format kilobytes correctly."""
        assert "KB" in redis_panel._format_memory(2048)

    def test_format_memory_megabytes(self, redis_panel):
        """Format megabytes correctly."""
        assert "MB" in redis_panel._format_memory(2 * 1024 * 1024)

    def test_format_memory_gigabytes(self, redis_panel):
        """Format gigabytes correctly."""
        assert "GB" in redis_panel._format_memory(2 * 1024 * 1024 * 1024)

    def test_format_memory_none(self, redis_panel):
        """Handle None memory value."""
        assert redis_panel._format_memory(None) == "--"

    def test_format_hit_rate(self, redis_panel):
        """Format hit rate correctly (input is already a percentage)."""
        assert redis_panel._format_hit_rate(85.0) == "85.0%"

    def test_format_hit_rate_none(self, redis_panel):
        """Handle None hit rate value."""
        assert redis_panel._format_hit_rate(None) == "--"

    def test_format_keyspace_dict(self, redis_panel):
        """Format keyspace dict correctly."""
        result = redis_panel._format_keyspace({"db0": {"keys": 100}})
        assert "100 keys" in result

    def test_format_keyspace_int(self, redis_panel):
        """Format keyspace int correctly."""
        result = redis_panel._format_keyspace(50)
        assert "50 keys" in result

    def test_format_keyspace_none(self, redis_panel):
        """Handle None keyspace value."""
        assert redis_panel._format_keyspace(None) == "--"

    def test_format_keyspace_multiple_dbs(self, redis_panel):
        """Format keyspace with multiple databases."""
        result = redis_panel._format_keyspace(
            {
                "db0": {"keys": 100},
                "db1": {"keys": 50},
            }
        )
        assert "150 keys" in result

    def test_format_uptime_zero(self, redis_panel):
        """Format zero uptime."""
        assert redis_panel._format_uptime(0) == "0s"

    def test_format_latency_zero(self, redis_panel):
        """Format zero latency."""
        assert redis_panel._format_latency(0) == "0.00"

    def test_format_memory_zero(self, redis_panel):
        """Format zero memory."""
        result = redis_panel._format_memory(0)
        assert "0" in result


@pytest.mark.unit
class TestIntervalConfiguration:
    """Test refresh interval configuration."""

    def test_default_interval(self):
        """Default interval is 5000ms."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({}, component_id="test")
        assert panel.interval_ms == 5000

    def test_config_interval_override(self):
        """Config interval overrides default."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({"interval_ms": 2000}, component_id="test")
        assert panel.interval_ms == 2000

    def test_env_var_interval_override(self, monkeypatch):
        """Environment variable overrides default."""
        monkeypatch.setenv("JUNIPER_CANOPY_REDIS_REFRESH_INTERVAL_MS", "3000")

        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({}, component_id="test")
        assert panel.interval_ms == 3000

    def test_invalid_env_var_uses_default(self, monkeypatch):
        """Invalid env var falls back to default."""
        monkeypatch.setenv("JUNIPER_CANOPY_REDIS_REFRESH_INTERVAL_MS", "invalid")

        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({}, component_id="test")
        assert panel.interval_ms == 5000

    def test_config_priority_over_env(self, monkeypatch):
        """Config takes priority over environment variable."""
        monkeypatch.setenv("JUNIPER_CANOPY_REDIS_REFRESH_INTERVAL_MS", "3000")

        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({"interval_ms": 1000}, component_id="test")
        assert panel.interval_ms == 1000


@pytest.mark.unit
class TestApiTimeout:
    """Test API timeout configuration."""

    def test_default_timeout(self):
        """Default timeout is 2 seconds."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({}, component_id="test")
        assert panel.api_timeout == 2

    def test_config_timeout_override(self):
        """Config timeout overrides default."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({"api_timeout": 5}, component_id="test")
        assert panel.api_timeout == 5


@pytest.mark.unit
class TestComponentId:
    """Test component ID handling."""

    def test_default_component_id(self):
        """Default component id is 'redis-panel'."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({})
        assert panel.component_id == "redis-panel"

    def test_custom_component_id(self):
        """Custom component id is used."""
        from frontend.components.redis_panel import RedisPanel

        panel = RedisPanel({}, component_id="custom-redis")
        assert panel.component_id == "custom-redis"

    def test_component_id_in_layout(self, redis_panel):
        """Component id is reflected in layout."""
        layout = redis_panel.get_layout()
        assert layout.id == "test-redis-panel"


@pytest.mark.unit
class TestBaseComponentInheritance:
    """Test BaseComponent inheritance."""

    def test_inherits_from_base_component(self, redis_panel):
        """RedisPanel inherits from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(redis_panel, BaseComponent)

    def test_has_logger(self, redis_panel):
        """RedisPanel has logger attribute."""
        assert hasattr(redis_panel, "logger")

    def test_has_config(self, redis_panel):
        """RedisPanel has config attribute."""
        assert hasattr(redis_panel, "config")


@pytest.mark.unit
class TestLayoutOutputIds:
    """Test that layout output IDs match callback outputs."""

    def test_status_badge_id_matches(self, redis_panel):
        """Status badge ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-status-badge" in layout_str

    def test_mode_badge_id_matches(self, redis_panel):
        """Mode badge ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-mode-badge" in layout_str

    def test_version_id_matches(self, redis_panel):
        """Version ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-version" in layout_str

    def test_uptime_id_matches(self, redis_panel):
        """Uptime ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-uptime" in layout_str

    def test_clients_id_matches(self, redis_panel):
        """Clients ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-clients" in layout_str

    def test_latency_id_matches(self, redis_panel):
        """Latency ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-latency" in layout_str

    def test_memory_id_matches(self, redis_panel):
        """Memory ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-memory" in layout_str

    def test_ops_sec_id_matches(self, redis_panel):
        """Ops/sec ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-ops-sec" in layout_str

    def test_hit_rate_id_matches(self, redis_panel):
        """Hit rate ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-hit-rate" in layout_str

    def test_keyspace_id_matches(self, redis_panel):
        """Keyspace ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-keyspace" in layout_str

    def test_refresh_interval_id_matches(self, redis_panel):
        """Refresh interval ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-refresh-interval" in layout_str

    def test_error_display_id_matches(self, redis_panel):
        """Error display ID matches expected pattern."""
        layout = redis_panel.get_layout()
        layout_str = str(layout)
        assert f"{redis_panel.component_id}-error-display" in layout_str


@pytest.mark.unit
class TestCallbackExecution:
    """Test callback function execution with mocked API responses."""

    def test_callback_success_up_status(self):
        """Test callback with successful UP status response."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            # Mock status response
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "UP",
                "mode": "LIVE",
                "health": {
                    "version": "7.2.0",
                    "uptime_seconds": 3600,
                    "connected_clients": 5,
                    "latency_ms": 1.23,
                },
            }

            # Mock metrics response
            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {
                "memory_used_bytes": 1024 * 1024,
                "ops_per_sec": 100,
                "hit_rate": 0.85,
                "keyspace": {"db0": {"keys": 50}},
            }

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UP"  # status_text
            assert result[1] == "success"  # status_color
            assert result[2] == "LIVE"  # mode_text
            assert result[3] == "primary"  # mode_color

    def test_callback_success_down_status(self):
        """Test callback with DOWN status response."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "DOWN",
                "mode": "LIVE",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "DOWN"  # status_text
            assert result[1] == "danger"  # status_color

    def test_callback_success_disabled_status(self):
        """Test callback with DISABLED status response."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "DISABLED",
                "mode": "DISABLED",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "DISABLED"  # status_text
            assert result[1] == "warning"  # status_color
            assert result[2] == "DISABLED"  # mode_text
            assert result[3] == "secondary"  # mode_color

    def test_callback_success_demo_mode(self):
        """Test callback with DEMO mode response."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "UP",
                "mode": "DEMO",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[2] == "DEMO"  # mode_text
            assert result[3] == "info"  # mode_color

    def test_callback_status_timeout(self):
        """Test callback handles status API timeout."""
        import requests

        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Timeout")

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UNAVAILABLE"  # status_text
            assert result[4] is not None  # error_children (Alert component)

    def test_callback_status_connection_error(self):
        """Test callback handles status API connection error."""
        import requests

        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UNAVAILABLE"  # status_text
            assert result[4] is not None  # error_children

    def test_callback_status_generic_exception(self):
        """Test callback handles generic exception during status fetch."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            mock_get.side_effect = ValueError("Unexpected error")

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[4] is not None  # error_children

    def test_callback_metrics_timeout(self):
        """Test callback handles metrics API timeout."""
        import requests

        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            # Status succeeds
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {"status": "UP", "mode": "LIVE", "health": {}}

            # Metrics times out
            mock_get.side_effect = [status_response, requests.exceptions.Timeout("Timeout")]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UP"  # status worked
            assert result[4] is not None  # error from metrics timeout

    def test_callback_metrics_connection_error(self):
        """Test callback handles metrics API connection error."""
        import requests

        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {"status": "UP", "mode": "LIVE", "health": {}}

            mock_get.side_effect = [status_response, requests.exceptions.ConnectionError("Connection refused")]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UP"
            assert result[4] is not None

    def test_callback_metrics_generic_exception(self):
        """Test callback handles generic exception during metrics fetch."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {"status": "UP", "mode": "LIVE", "health": {}}

            mock_get.side_effect = [status_response, ValueError("Unexpected")]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[4] is not None

    def test_callback_unknown_status(self):
        """Test callback handles unknown status value."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "UNKNOWN_STATUS",
                "mode": "UNKNOWN_MODE",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UNKNOWN_STATUS"  # raw status passed through
            assert result[1] == "secondary"  # fallback color
            assert result[2] == "UNKNOWN_MODE"  # raw mode passed through
            assert result[3] == "info"  # fallback mode color

    def test_callback_connected_status(self):
        """Test callback handles CONNECTED status (alias for UP)."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "CONNECTED",
                "mode": "LIVE",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UP"  # CONNECTED maps to UP
            assert result[1] == "success"

    def test_callback_disconnected_status(self):
        """Test callback handles DISCONNECTED status (alias for DOWN)."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "DISCONNECTED",
                "mode": "LIVE",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "DOWN"  # DISCONNECTED maps to DOWN
            assert result[1] == "danger"

    def test_callback_non_200_status_response(self):
        """Test callback handles non-200 status response."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 500

            metrics_response = MagicMock()
            metrics_response.status_code = 200
            metrics_response.json.return_value = {}

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            # Should use defaults when status_code != 200
            assert result[0] == "UNAVAILABLE"

    def test_callback_non_200_metrics_response(self):
        """Test callback handles non-200 metrics response."""
        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            status_response = MagicMock()
            status_response.status_code = 200
            status_response.json.return_value = {
                "status": "UP",
                "mode": "LIVE",
                "health": {},
            }

            metrics_response = MagicMock()
            metrics_response.status_code = 500

            mock_get.side_effect = [status_response, metrics_response]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            assert result[0] == "UP"  # Status worked
            assert result[9] == "--"  # memory uses default

    def test_callback_no_error_when_status_fails_but_has_existing_error(self):
        """Test that metrics timeout doesn't overwrite existing status error."""
        import requests

        from frontend.components.redis_panel import RedisPanel

        with patch("frontend.components.redis_panel.requests.get") as mock_get:
            # Both fail with different errors
            mock_get.side_effect = [
                requests.exceptions.Timeout("Status timeout"),
                requests.exceptions.Timeout("Metrics timeout"),
            ]

            panel = RedisPanel({}, component_id="test-redis")
            mock_app = MagicMock()
            mock_app.callback = MagicMock(return_value=lambda f: f)
            panel.register_callbacks(mock_app)
            callback_fn = panel._cb_update_redis_panel

            result = callback_fn(1)

            # First error should be preserved
            assert result[4] is not None
            # Error message should contain reference to timeout
            error_str = str(result[4]).lower()
            assert "timeout" in error_str or "timed out" in error_str


@pytest.mark.unit
class TestFormattingEdgeCases:
    """Test formatting helper edge cases for full coverage."""

    def test_format_uptime_invalid_type(self, redis_panel):
        """Format uptime with invalid type returns default."""
        assert redis_panel._format_uptime("invalid") == "--"

    def test_format_uptime_negative(self, redis_panel):
        """Format negative uptime."""
        result = redis_panel._format_uptime(-10)
        # Negative seconds would be unusual but shouldn't crash
        assert "-" in result or "--" in result

    def test_format_latency_invalid_type(self, redis_panel):
        """Format latency with invalid type returns default."""
        assert redis_panel._format_latency("not-a-number") == "--"

    def test_format_memory_invalid_type(self, redis_panel):
        """Format memory with invalid type returns default."""
        assert redis_panel._format_memory("not-a-number") == "--"

    def test_format_hit_rate_invalid_type(self, redis_panel):
        """Format hit rate with invalid type returns default."""
        assert redis_panel._format_hit_rate("not-a-number") == "--"

    def test_format_keyspace_string(self, redis_panel):
        """Format keyspace with string value."""
        result = redis_panel._format_keyspace("some-string")
        assert result == "some-string"
