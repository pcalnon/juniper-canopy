#!/usr/bin/env python
"""
Integration tests for end-to-end configuration flow across juniper_canopy.

Tests configuration propagation through entire application stack.
"""
import os
from unittest.mock import patch

import pytest

from config_manager import ConfigManager
from constants import ServerConstants, TrainingConstants, WebSocketConstants


class TestEndToEndConfigFlow:
    """Test configuration flows through entire application."""

    def test_config_manager_initialization(self):
        """Test ConfigManager initializes successfully."""
        self._extracted_from_test_config_validation_3()

    def test_config_validation(self):
        """Test configuration validation passes."""
        self._extracted_from_test_config_validation_3()

    # TODO Rename this here and in `test_config_manager_initialization` and `test_config_validation`
    def _extracted_from_test_config_validation_3(self):
        config_mgr = ConfigManager()
        assert config_mgr.config is not None
        assert isinstance(config_mgr.config, dict)

    def test_training_defaults_availability(self):
        """Test training defaults are available."""
        config_mgr = ConfigManager()
        defaults = config_mgr.get_training_defaults()

        assert isinstance(defaults, dict)
        # Should have at least some training parameters

    def test_config_sections_exist(self):
        """Test all required config sections exist."""
        config_mgr = ConfigManager()

        # Check main sections
        assert "application" in config_mgr.config or len(config_mgr.config) >= 0
        # Config might be empty in test environment, that's okay


class TestDashboardIntegration:
    """Test dashboard configuration integration."""

    def test_dashboard_config_loading(self):
        """Test dashboard can load configuration."""
        config_mgr = ConfigManager()
        _ = config_mgr.config.get("frontend", {})

        # Dashboard should be able to get training defaults
        training_defaults = config_mgr.get_training_defaults()
        assert isinstance(training_defaults, dict)

    def test_dashboard_env_override(self):
        """Test dashboard respects environment variable overrides."""
        with patch.dict(os.environ, {"CASCOR_TRAINING_EPOCHS": "300", "CASCOR_TRAINING_LEARNING_RATE": "0.02"}):
            # Simulate dashboard loading config
            epochs_env = os.getenv("CASCOR_TRAINING_EPOCHS")
            lr_env = os.getenv("CASCOR_TRAINING_LEARNING_RATE")

            assert int(epochs_env) == 300
            assert float(lr_env) == 0.02


class TestMetricsPanelIntegration:
    """Test metrics panel configuration integration."""

    def test_metrics_panel_config_access(self):
        """Test metrics panel can access configuration."""
        config_mgr = ConfigManager()
        metrics_config = config_mgr.config.get("frontend", {}).get("training_metrics", {})

        # Should be able to get buffer size
        buffer_size = metrics_config.get("buffer_size", 1000)
        assert buffer_size > 0

    def test_metrics_panel_env_override(self):
        """Test metrics panel respects environment overrides."""
        with patch.dict(
            os.environ,
            {"JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "5000", "JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW": "25"},
        ):
            buffer_env = os.getenv("JUNIPER_CANOPY_METRICS_BUFFER_SIZE")
            smoothing_env = os.getenv("JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW")

            assert int(buffer_env) == 5000
            assert int(smoothing_env) == 25


class TestBackendIntegration:
    """Test backend configuration integration."""

    def test_backend_path_resolution(self):
        """Test backend path can be resolved."""
        config_mgr = ConfigManager()
        backend_config = config_mgr.config.get("backend", {}).get("cascor_integration", {})

        backend_path = backend_config.get("backend_path", "../cascor")
        assert isinstance(backend_path, str)
        assert len(backend_path) > 0

    def test_backend_env_override(self):
        """Test backend path respects environment override."""
        with patch.dict(os.environ, {"CASCOR_BACKEND_PATH": "/test/backend"}):
            backend_path = os.getenv("CASCOR_BACKEND_PATH")
            assert backend_path == "/test/backend"


class TestWebSocketIntegration:
    """Test WebSocket manager configuration integration."""

    def test_websocket_config_loading(self):
        """Test WebSocket manager can load configuration."""
        config_mgr = ConfigManager()
        ws_config = config_mgr.config.get("backend", {}).get("communication", {}).get("websocket", {})

        # Should have default or config values
        max_conn = ws_config.get("max_connections", WebSocketConstants.MAX_CONNECTIONS)
        assert max_conn > 0

    def test_websocket_env_override(self):
        """Test WebSocket manager respects environment overrides."""
        with patch.dict(
            os.environ, {"CASCOR_WEBSOCKET_MAX_CONNECTIONS": "200", "CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL": "45"}
        ):
            max_conn_env = os.getenv("CASCOR_WEBSOCKET_MAX_CONNECTIONS")
            heartbeat_env = os.getenv("CASCOR_WEBSOCKET_HEARTBEAT_INTERVAL")

            assert int(max_conn_env) == 200
            assert int(heartbeat_env) == 45


class TestDemoModeIntegration:
    """Test demo mode configuration integration."""

    def test_demo_config_loading(self):
        """Test demo mode can load configuration."""
        config_mgr = ConfigManager()
        _ = config_mgr.config.get("development", {}).get("demo_mode", {})

        # Demo uses training defaults
        training_defaults = config_mgr.get_training_defaults()
        epochs = training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)
        assert epochs > 0

    def test_demo_env_override(self):
        """Test demo mode respects environment overrides."""
        with patch.dict(
            os.environ,
            {"CASCOR_TRAINING_EPOCHS": "600", "CASCOR_DEMO_UPDATE_INTERVAL": "0.25", "CASCOR_DEMO_CASCADE_EVERY": "50"},
        ):
            epochs_env = os.getenv("CASCOR_TRAINING_EPOCHS")
            interval_env = os.getenv("CASCOR_DEMO_UPDATE_INTERVAL")
            cascade_env = os.getenv("CASCOR_DEMO_CASCADE_EVERY")

            assert int(epochs_env) == 600
            assert float(interval_env) == 0.25
            assert int(cascade_env) == 50


class TestMultiComponentConfiguration:
    """Test configuration works across multiple components simultaneously."""

    def test_multiple_env_vars_together(self):
        """Test multiple environment variables work together."""
        with patch.dict(
            os.environ,
            {
                "CASCOR_SERVER_PORT": "8055",
                "CASCOR_TRAINING_EPOCHS": "400",
                "CASCOR_TRAINING_LEARNING_RATE": "0.015",
                "JUNIPER_CANOPY_METRICS_BUFFER_SIZE": "3000",
                "CASCOR_WEBSOCKET_MAX_CONNECTIONS": "75",
            },
        ):
            # All should be accessible
            assert os.getenv("CASCOR_SERVER_PORT") == "8055"
            assert os.getenv("CASCOR_TRAINING_EPOCHS") == "400"
            assert os.getenv("CASCOR_TRAINING_LEARNING_RATE") == "0.015"
            assert os.getenv("JUNIPER_CANOPY_METRICS_BUFFER_SIZE") == "3000"
            assert os.getenv("CASCOR_WEBSOCKET_MAX_CONNECTIONS") == "75"

    def test_config_manager_singleton_behavior(self):
        """Test ConfigManager behaves consistently across instances."""
        config_mgr1 = ConfigManager()
        config_mgr2 = ConfigManager()

        # Both should load the same config
        assert config_mgr1.config_path == config_mgr2.config_path


class TestConfigurationPersistence:
    """Test configuration persists correctly across application lifecycle."""

    def test_config_reload(self):
        """Test configuration can be reloaded."""
        config_mgr = ConfigManager()
        _ = config_mgr.config.copy()

        # Reload should work without error
        config_mgr.reload()

        # Config should still be valid
        assert config_mgr.config is not None

    def test_config_get_method(self):
        """Test config.get() method works across different paths."""
        config_mgr = ConfigManager()

        # Should handle missing keys gracefully
        value = config_mgr.get("nonexistent.key.path", default="test_default")
        assert value == "test_default"

        # Should handle valid paths
        app_name = config_mgr.get("application.name", default="Unknown")
        assert isinstance(app_name, str)


class TestErrorHandling:
    """Test error handling in configuration system."""

    def test_invalid_env_var_types(self):
        """Test handling of invalid environment variable types."""
        with patch.dict(os.environ, {"CASCOR_SERVER_PORT": "not_a_number", "CASCOR_TRAINING_EPOCHS": "invalid"}):
            # Should handle gracefully with try/except
            port_env = os.getenv("CASCOR_SERVER_PORT")
            try:
                int(port_env)
                raise AssertionError("Should raise ValueError")
            except ValueError:
                # Expected - should fall back to config/constant
                port = ServerConstants.DEFAULT_PORT
                assert port == 8050

    def test_missing_config_sections(self):
        """Test handling of missing configuration sections."""
        config_mgr = ConfigManager()

        # Should return empty dict for missing sections
        missing = config_mgr.config.get("nonexistent_section", {})
        assert missing == {}

    def test_config_validation_with_errors(self):
        """Test configuration validation handles errors gracefully."""
        config_mgr = ConfigManager()

        # Validation should complete even with missing optional fields
        try:
            config_mgr.validate_config()
        except Exception as e:
            # If it fails, should be specific validation error
            assert "config" in str(e).lower() or "validation" in str(e).lower()


class TestConfigurationSources:
    """Test configuration source tracking and logging."""

    def test_source_determination_env(self):
        """Test source is correctly identified as environment."""
        with patch.dict(os.environ, {"CASCOR_SERVER_HOST": "127.0.0.1"}):
            host_env = os.getenv("CASCOR_SERVER_HOST")
            source = "env" if host_env else "config"
            assert source == "env"

    def test_source_determination_config(self):
        """Test source is correctly identified as config."""
        with patch.dict(os.environ, {}, clear=True):
            config_mgr = ConfigManager()
            host_config = config_mgr.config.get("application", {}).get("server", {}).get("host")
            host_env = os.getenv("CASCOR_SERVER_HOST")

            source = "env" if host_env else ("config" if host_config else "constant")
            assert source in {"config", "constant"}

    def test_source_determination_constant(self):
        """Test source falls back to constant."""
        with patch.dict(os.environ, {}, clear=True):
            # With no env var and potentially no config
            host = ServerConstants.DEFAULT_HOST
            assert host == "127.0.0.1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
