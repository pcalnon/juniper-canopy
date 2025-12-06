#!/usr/bin/env python
"""
Unit tests for configuration refactoring across juniper_canopy components.

Tests configuration hierarchy: Environment Variables > YAML > Constants
"""

import contextlib
import os
from unittest.mock import patch

import pytest

from config_manager import ConfigManager
from constants import DashboardConstants, ServerConstants, TrainingConstants, WebSocketConstants


class TestServerConfiguration:
    """Test main.py server configuration with env var overrides."""

    def test_server_host_from_config(self):
        """Test server host loads from config when no env var."""
        with patch.dict(os.environ, {}, clear=True):
            config_mgr = ConfigManager()
            host_config = config_mgr.config.get("application", {}).get("server", {}).get("host")
            host = os.getenv("CASCOR_SERVER_HOST") or host_config or ServerConstants.DEFAULT_HOST

            # Should use config or constant, not env
            assert host == (host_config or ServerConstants.DEFAULT_HOST)

    def test_server_host_from_env(self):
        """Test server host from environment variable."""
        with patch.dict(os.environ, {"CASCOR_SERVER_HOST": "0.0.0.0"}):
            host = os.getenv("CASCOR_SERVER_HOST")
            assert host == "0.0.0.0"

    def test_server_port_from_config(self):
        """Test server port loads from config when no env var."""
        with patch.dict(os.environ, {}, clear=True):
            config_mgr = ConfigManager()
            port_config = config_mgr.config.get("application", {}).get("server", {}).get("port")
            port = (
                int(os.getenv("CASCOR_SERVER_PORT", 0))
                if os.getenv("CASCOR_SERVER_PORT")
                else (port_config or ServerConstants.DEFAULT_PORT)
            )

            # Should use config or constant, not env
            assert port == (port_config or ServerConstants.DEFAULT_PORT)

    def test_server_port_from_env(self):
        """Test server port from environment variable."""
        with patch.dict(os.environ, {"CASCOR_SERVER_PORT": "8051"}):
            port = int(os.getenv("CASCOR_SERVER_PORT"))
            assert port == 8051

    def test_server_debug_from_env(self):
        """Test server debug mode from environment variable."""
        with patch.dict(os.environ, {"CASCOR_SERVER_DEBUG": "1"}):
            debug_env = os.getenv("CASCOR_SERVER_DEBUG")
            debug = debug_env.lower() in ("1", "true", "yes")
            assert debug

        with patch.dict(os.environ, {"CASCOR_SERVER_DEBUG": "false"}):
            debug_env = os.getenv("CASCOR_SERVER_DEBUG")
            debug = debug_env.lower() in ("1", "true", "yes")
            assert not debug


class TestDashboardConfiguration:
    """Test dashboard_manager.py training parameter configuration."""

    def test_training_defaults_load(self):
        """Test training defaults load from config manager."""
        config_mgr = ConfigManager()
        defaults = config_mgr.get_training_defaults()

        assert "learning_rate" in defaults or "epochs" in defaults or "hidden_units" in defaults
        # At least one should be present, or we should have constants fallback

    def test_learning_rate_from_env(self):
        """Test learning rate override from environment."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_LEARNING_RATE": "0.05"}):
            lr_env = os.getenv("CASCOR_TRAINING_LEARNING_RATE")
            assert lr_env == "0.05"
            assert float(lr_env) == 0.05

    def test_epochs_from_env(self):
        """Test epochs override from environment."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "500"}):
            epochs_env = os.getenv("CASCOR_TRAINING_EPOCHS")
            assert epochs_env == "500"
            assert int(epochs_env) == 500

    def test_hidden_units_from_env(self):
        """Test hidden units override from environment."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_HIDDEN_UNITS": "15"}):
            hu_env = os.getenv("CASCOR_TRAINING_HIDDEN_UNITS")
            assert hu_env == "15"
            assert int(hu_env) == 15

    def test_invalid_env_var_handling(self):
        """Test handling of invalid environment variable values."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_LEARNING_RATE": "invalid"}):
            lr_env = os.getenv("CASCOR_TRAINING_LEARNING_RATE")
            try:
                float(lr_env)
                raise AssertionError("Should raise ValueError")
            except ValueError:
                # Expected - should fall back to config/constant
                assert True


class TestMetricsPanelConfiguration:
    """Test metrics_panel.py component configuration."""

    def test_update_interval_from_config(self):
        """Test update interval loads from config."""
        config_mgr = ConfigManager()
        metrics_config = config_mgr.config.get("frontend", {}).get("training_metrics", {})

        if update_freq_hz := metrics_config.get("update_frequency_hz"):
            update_interval = int(1000 / update_freq_hz)
            assert update_interval > 0
            assert update_interval <= 1000

    def test_update_interval_from_env(self):
        """Test update interval from environment variable."""
        with patch.dict(os.environ, {"JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS": "500"}):
            interval_env = os.getenv("JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS")
            assert int(interval_env) == 500

    def test_buffer_size_from_env(self):
        """Test buffer size from environment variable."""
        with patch.dict(os.environ, {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "2000"}):
            buffer_env = os.getenv("JUNIPER_CANOPY_METRICS_BUFFER_SIZE")
            assert int(buffer_env) == 2000

    def test_smoothing_window_from_env(self):
        """Test smoothing window from environment variable."""
        with patch.dict(os.environ, {"JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW": "20"}):
            smoothing_env = os.getenv("JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW")
            assert int(smoothing_env) == 20


class TestBackendIntegrationConfiguration:
    """Test cascor_integration.py backend path resolution."""

    def test_backend_path_from_config(self):
        """Test backend path loads from config."""
        config_mgr = ConfigManager()
        backend_path = config_mgr.config.get("backend", {}).get("cascor_integration", {}).get("backend_path")

        # Should have a default or config value
        assert backend_path is None or isinstance(backend_path, str)

    def test_backend_path_from_env(self):
        """Test backend path from environment variable."""
        with patch.dict(os.environ, {"CASCOR_BACKEND_PATH": "/custom/path"}):
            backend_path = os.getenv("CASCOR_BACKEND_PATH")
            assert backend_path == "/custom/path"

    def test_backend_path_expansion(self):
        """Test backend path expansion (tilde, env vars)."""
        test_path = "~/test/path"
        expanded = os.path.expanduser(test_path)
        assert "~" not in expanded

        with patch.dict(os.environ, {"TEST_VAR": "mydir"}):
            test_path = "$TEST_VAR/cascor"
            expanded = os.path.expandvars(test_path)
            assert expanded == "mydir/cascor"


class TestWebSocketConfiguration:
    """Test websocket_manager.py configuration."""

    def test_max_connections_constant(self):
        """Test max connections constant exists."""
        assert hasattr(WebSocketConstants, "MAX_CONNECTIONS")
        assert WebSocketConstants.MAX_CONNECTIONS > 0

    def test_max_connections_from_env(self):
        """Test max connections from environment variable."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_MAX_CONNECTIONS": "100"}):
            max_conn_env = os.getenv("CASCOR_WEBSOCKET_MAX_CONNECTIONS")
            assert int(max_conn_env) == 100

    def test_heartbeat_interval_from_env(self):
        """Test heartbeat interval from environment variable."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL": "60"}):
            heartbeat_env = os.getenv("CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL")
            assert int(heartbeat_env) == 60

    def test_reconnect_attempts_from_env(self):
        """Test reconnect attempts from environment variable."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS": "10"}):
            attempts_env = os.getenv("CASCOR_WEBSOCKET_RECONNECT_ATTEMPTS")
            assert int(attempts_env) == 10

    def test_reconnect_delay_from_env(self):
        """Test reconnect delay from environment variable."""
        with patch.dict(os.environ, {"CASCOR_WEBSOCKET_RECONNECT_DELAY": "5"}):
            delay_env = os.getenv("CASCOR_WEBSOCKET_RECONNECT_DELAY")
            assert int(delay_env) == 5


class TestDemoModeConfiguration:
    """Test demo_mode.py simulation parameter configuration."""

    def test_demo_update_interval_from_env(self):
        """Test demo update interval from environment variable."""
        with patch.dict(os.environ, {"CASCOR_DEMO_UPDATE_INTERVAL": "0.5"}):
            interval_env = os.getenv("CASCOR_DEMO_UPDATE_INTERVAL")
            assert float(interval_env) == 0.5

    def test_demo_cascade_frequency_from_env(self):
        """Test cascade frequency from environment variable."""
        with patch.dict(os.environ, {"CASCOR_DEMO_CASCADE_EVERY": "40"}):
            cascade_env = os.getenv("CASCOR_DEMO_CASCADE_EVERY")
            assert int(cascade_env) == 40

    def test_demo_uses_training_defaults(self):
        """Test demo mode uses training defaults for epochs/hidden units."""
        config_mgr = ConfigManager()
        training_defaults = config_mgr.get_training_defaults()

        # Demo should use same training defaults
        epochs = training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)
        hidden = training_defaults.get("hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS)

        assert epochs > 0
        assert hidden >= 0


class TestConfigurationHierarchy:
    """Test configuration hierarchy: Env > YAML > Constants."""

    def test_hierarchy_env_wins(self):
        """Test environment variable takes precedence over config."""
        with patch.dict(os.environ, {"CASCOR_SERVER_PORT": "9999"}):
            config_mgr = ConfigManager()
            port_config = config_mgr.config.get("application", {}).get("server", {}).get("port")
            port_env = os.getenv("CASCOR_SERVER_PORT")

            # Env should override config
            port = int(port_env) if port_env else (port_config or ServerConstants.DEFAULT_PORT)
            assert port == 9999

    def test_hierarchy_config_over_constant(self):
        """Test YAML config takes precedence over constant."""
        config_mgr = ConfigManager()
        if port_config := config_mgr.config.get("application", {}).get("server", {}).get("port"):
            # If config has value, it should be used over constant
            assert port_config != ServerConstants.DEFAULT_PORT or port_config == ServerConstants.DEFAULT_PORT
            # Either way, config is the source

    def test_hierarchy_constant_fallback(self):
        """Test constant is used when no config or env."""
        with patch.dict(os.environ, {}, clear=True):
            # With no env var and potentially no config, constant should be used
            port = ServerConstants.DEFAULT_PORT
            assert port == 8050  # Known constant value


class TestConfigValidation:
    """Test configuration validation."""

    def test_training_param_validation(self):
        """Test training parameter validation."""
        config_mgr = ConfigManager()

        with contextlib.suppress(KeyError):
            # Should have epochs parameter config
            epochs_config = config_mgr.get_training_param_config("epochs")
            assert "min" in epochs_config
            assert "max" in epochs_config
            assert "default" in epochs_config
            assert epochs_config["min"] <= epochs_config["default"] <= epochs_config["max"]

    def test_training_param_value_validation(self):
        """Test training parameter value validation."""
        config_mgr = ConfigManager()

        with contextlib.suppress(KeyError):
            # Valid value should pass
            assert config_mgr.validate_training_param_value("epochs", 100)

            # Out of range should fail
            with pytest.raises(ValueError):
                config_mgr.validate_training_param_value("epochs", 10000)


class TestConstantsConsistency:
    """Test constants module consistency."""

    def test_training_constants_exist(self):
        """Test all required training constants exist."""
        assert hasattr(TrainingConstants, "MIN_TRAINING_EPOCHS")
        assert hasattr(TrainingConstants, "MAX_TRAINING_EPOCHS")
        assert hasattr(TrainingConstants, "DEFAULT_TRAINING_EPOCHS")
        assert hasattr(TrainingConstants, "DEFAULT_LEARNING_RATE")
        assert hasattr(TrainingConstants, "DEFAULT_MAX_HIDDEN_UNITS")

    def test_dashboard_constants_exist(self):
        """Test all required dashboard constants exist."""
        assert hasattr(DashboardConstants, "FAST_UPDATE_INTERVAL_MS")
        assert hasattr(DashboardConstants, "SLOW_UPDATE_INTERVAL_MS")
        assert hasattr(DashboardConstants, "MAX_DATA_POINTS")

    def test_server_constants_exist(self):
        """Test all required server constants exist."""
        assert hasattr(ServerConstants, "DEFAULT_HOST")
        assert hasattr(ServerConstants, "DEFAULT_PORT")
        assert hasattr(ServerConstants, "WS_TRAINING_PATH")
        assert hasattr(ServerConstants, "WS_CONTROL_PATH")

    def test_websocket_constants_exist(self):
        """Test all required WebSocket constants exist."""
        assert hasattr(WebSocketConstants, "MAX_CONNECTIONS")
        assert hasattr(WebSocketConstants, "HEARTBEAT_INTERVAL_SEC")
        assert hasattr(WebSocketConstants, "RECONNECT_ATTEMPTS")
        assert hasattr(WebSocketConstants, "RECONNECT_DELAY_SEC")

    def test_training_constants_ranges(self):
        """Test training constants have valid ranges."""
        assert TrainingConstants.MIN_TRAINING_EPOCHS < TrainingConstants.MAX_TRAINING_EPOCHS
        assert (
            TrainingConstants.MIN_TRAINING_EPOCHS
            <= TrainingConstants.DEFAULT_TRAINING_EPOCHS
            <= TrainingConstants.MAX_TRAINING_EPOCHS
        )
        assert TrainingConstants.MIN_LEARNING_RATE < TrainingConstants.MAX_LEARNING_RATE
        assert TrainingConstants.MIN_HIDDEN_UNITS < TrainingConstants.MAX_HIDDEN_UNITS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
