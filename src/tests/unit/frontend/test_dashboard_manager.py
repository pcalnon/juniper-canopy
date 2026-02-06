#!/usr/bin/env python
"""Tests for DashboardManager component registration and initialization."""

from unittest.mock import MagicMock

import pytest

from frontend.base_component import BaseComponent
from frontend.dashboard_manager import DashboardManager


class FakeComponent(BaseComponent):
    """Spy component for tracking registration calls."""

    def __init__(self, config, component_id):
        super().__init__(config, component_id)
        self.initialize_called = False
        self.register_callbacks_called = False
        self.callbacks_app = None

    def get_layout(self):
        """Return minimal layout."""
        return {"type": "div", "children": []}

    def register_callbacks(self, app):
        """Track callback registration."""
        self.register_callbacks_called = True
        self.callbacks_app = app

    def initialize(self):
        """Track initialization."""
        super().initialize()
        self.initialize_called = True


@pytest.fixture
def minimal_config():
    """Minimal DashboardManager configuration."""
    return {
        "metrics_panel": {},
        "network_visualizer": {},
        "dataset_plotter": {},
        "decision_boundary": {},
    }


@pytest.fixture
def dashboard_manager(minimal_config):
    """DashboardManager instance for testing."""
    return DashboardManager(minimal_config)


class TestDashboardManagerRegistration:
    """Test component registration in DashboardManager."""

    def test_component_registration_calls_initialize(self, dashboard_manager):
        """Test that register_component calls component.initialize()."""
        fake_component = FakeComponent({}, "test-component")
        assert not fake_component.initialize_called

        dashboard_manager.register_component(fake_component)

        assert fake_component.initialize_called
        assert fake_component.is_initialized

    def test_component_registration_calls_register_callbacks(self, dashboard_manager):
        """Test that register_component calls component.register_callbacks(app)."""
        fake_component = FakeComponent({}, "test-component")
        assert not fake_component.register_callbacks_called

        dashboard_manager.register_component(fake_component)

        assert fake_component.register_callbacks_called
        assert fake_component.callbacks_app is dashboard_manager.app

    def test_register_component_appends_to_components_list(self, dashboard_manager):
        """Test that register_component appends component to components list."""
        fake_component = FakeComponent({}, "test-component")
        initial_count = len(dashboard_manager.components)

        dashboard_manager.register_component(fake_component)

        assert len(dashboard_manager.components) == initial_count + 1
        assert fake_component in dashboard_manager.components

    def test_register_component_order(self, dashboard_manager):
        """Test that components are registered in order."""
        comp1 = FakeComponent({}, "component-1")
        comp2 = FakeComponent({}, "component-2")

        dashboard_manager.register_component(comp1)
        dashboard_manager.register_component(comp2)

        assert comp1.initialize_called
        assert comp2.initialize_called
        assert comp1.register_callbacks_called
        assert comp2.register_callbacks_called


class TestDashboardManagerAPIURL:
    """Test _api_url method with Flask request context."""

    def test_api_url_construction(self, dashboard_manager):
        """Test _api_url constructs URLs correctly in Flask context."""
        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050", path="/dashboard/"):
            url = dashboard_manager._api_url("/api/health")
            assert url == "http://localhost:8050/api/health"

    def test_api_url_strips_leading_slash(self, dashboard_manager):
        """Test _api_url handles paths with and without leading slash."""
        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050", path="/dashboard/"):
            url1 = dashboard_manager._api_url("/api/metrics")
            url2 = dashboard_manager._api_url("api/metrics")
            assert url1 == url2
            assert url1 == "http://localhost:8050/api/metrics"

    def test_api_url_preserves_query_params(self, dashboard_manager):
        """Test _api_url preserves query parameters."""
        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050", path="/dashboard/"):
            url = dashboard_manager._api_url("/api/metrics?limit=100")
            assert url == "http://localhost:8050/api/metrics?limit=100"

    def test_api_url_different_hosts(self, dashboard_manager):
        """Test _api_url works with different host configurations."""
        with dashboard_manager.app.server.test_request_context(base_url="http://127.0.0.1:9000", path="/dashboard/"):
            url = dashboard_manager._api_url("/api/status")
            assert url == "http://127.0.0.1:9000/api/status"


class TestDashboardManagerInitialization:
    """Test DashboardManager initialization."""

    def test_dashboard_manager_creates_app(self, minimal_config):
        """Test that DashboardManager creates a Dash app."""
        dm = DashboardManager(minimal_config)
        assert dm.app is not None
        assert hasattr(dm.app, "callback")

    def test_dashboard_manager_registers_default_components(self, minimal_config):
        """Test that DashboardManager registers all default components."""
        dm = DashboardManager(minimal_config)
        # 8 default components: metrics, network, dataset, decision, about, hdf5_snapshots, redis, cassandra
        assert len(dm.components) == 8  # metrics, network, dataset, decision, about, hdf5_snapshots, redis, cassandra

    def test_dashboard_manager_components_initialized(self, minimal_config):
        """Test that all default components are initialized."""
        dm = DashboardManager(minimal_config)
        for component in dm.components:
            assert component.is_initialized

    def test_dashboard_manager_has_layout(self, minimal_config):
        """Test that DashboardManager creates app layout."""
        dm = DashboardManager(minimal_config)
        assert dm.app.layout is not None

    def test_dashboard_manager_config_passed_to_components(self, minimal_config):
        """Test that component-specific config is passed to components."""
        config = {
            "metrics_panel": {"max_data_points": 500},
            "network_visualizer": {"update_interval": 2000},
            "dataset_plotter": {},
            "decision_boundary": {},
        }
        dm = DashboardManager(config)

        assert dm.metrics_panel.config.get("max_data_points") == 500
        assert dm.network_visualizer.config.get("update_interval") == 2000


class TestDashboardManagerCallbacks:
    """Test that callbacks are registered."""

    def test_callbacks_registered(self, minimal_config):
        """Test that callbacks are registered to app."""
        dm = DashboardManager(minimal_config)
        # Check that app has callbacks registered (callback_map is populated)
        assert len(dm.app.callback_map) > 0

    def test_component_callbacks_registered(self, minimal_config):
        """Test that component callbacks are registered during initialization."""
        dm = DashboardManager(minimal_config)
        _ = len(dm.app.callback_map)  # Store initial count (unused)

        # Register a new component and verify callback count increases
        fake_component = FakeComponent({}, "new-component")
        fake_component.register_callbacks = MagicMock()

        dm.register_component(fake_component)

        # Verify register_callbacks was called
        fake_component.register_callbacks.assert_called_once_with(dm.app)


class TestDashboardManagerComponentRetrieval:
    """Test component retrieval by ID."""

    def test_get_component_returns_registered_component(self, dashboard_manager):
        """Test get_component returns a registered component by ID."""
        fake_component = FakeComponent({}, "retrievable-component")
        dashboard_manager.register_component(fake_component)

        retrieved = dashboard_manager.get_component("retrievable-component")
        assert retrieved is fake_component

    def test_get_component_returns_none_for_unknown_id(self, dashboard_manager):
        """Test get_component returns None for unknown component ID."""
        retrieved = dashboard_manager.get_component("nonexistent-component")
        assert retrieved is None

    def test_get_component_retrieves_default_components(self, dashboard_manager):
        """Test that default components can be retrieved by ID."""
        metrics = dashboard_manager.get_component("metrics-panel")
        assert metrics is dashboard_manager.metrics_panel

        network = dashboard_manager.get_component("network-visualizer")
        assert network is dashboard_manager.network_visualizer

        dataset = dashboard_manager.get_component("dataset-plotter")
        assert dataset is dashboard_manager.dataset_plotter

        boundary = dashboard_manager.get_component("decision-boundary")
        assert boundary is dashboard_manager.decision_boundary


class TestDashboardManagerTrainingDefaults:
    """Test _get_training_defaults_with_env method."""

    def test_env_override_learning_rate(self, minimal_config, monkeypatch):
        """Test CASCOR_TRAINING_LEARNING_RATE env var override."""
        monkeypatch.setenv("CASCOR_TRAINING_LEARNING_RATE", "0.05")
        dm = DashboardManager(minimal_config)
        defaults = dm._get_training_defaults_with_env()
        assert defaults["learning_rate"] == 0.05

    def test_env_override_hidden_units(self, minimal_config, monkeypatch):
        """Test CASCOR_TRAINING_HIDDEN_UNITS env var override."""
        monkeypatch.setenv("CASCOR_TRAINING_HIDDEN_UNITS", "20")
        dm = DashboardManager(minimal_config)
        defaults = dm._get_training_defaults_with_env()
        assert defaults["hidden_units"] == 20

    def test_env_override_epochs(self, minimal_config, monkeypatch):
        """Test CASCOR_TRAINING_EPOCHS env var override."""
        monkeypatch.setenv("CASCOR_TRAINING_EPOCHS", "500")
        dm = DashboardManager(minimal_config)
        defaults = dm._get_training_defaults_with_env()
        assert defaults["epochs"] == 500

    def test_env_override_invalid_learning_rate(self, minimal_config, monkeypatch):
        """Test invalid CASCOR_TRAINING_LEARNING_RATE is ignored with warning."""
        monkeypatch.setenv("CASCOR_TRAINING_LEARNING_RATE", "not_a_float")
        dm = DashboardManager(minimal_config)
        defaults = dm._get_training_defaults_with_env()
        assert "learning_rate" in defaults
        assert isinstance(defaults["learning_rate"], (int, float))

    def test_env_override_invalid_hidden_units(self, minimal_config, monkeypatch):
        """Test invalid CASCOR_TRAINING_HIDDEN_UNITS is ignored with warning."""
        monkeypatch.setenv("CASCOR_TRAINING_HIDDEN_UNITS", "not_an_int")
        dm = DashboardManager(minimal_config)
        defaults = dm._get_training_defaults_with_env()
        assert "hidden_units" in defaults
        assert isinstance(defaults["hidden_units"], int)

    def test_env_override_invalid_epochs(self, minimal_config, monkeypatch):
        """Test invalid CASCOR_TRAINING_EPOCHS is ignored with warning."""
        monkeypatch.setenv("CASCOR_TRAINING_EPOCHS", "not_an_int")
        dm = DashboardManager(minimal_config)
        defaults = dm._get_training_defaults_with_env()
        assert "epochs" in defaults
        assert isinstance(defaults["epochs"], int)

    def test_fallback_to_constants(self, minimal_config, monkeypatch):
        """Test that constants are used as fallback when config is missing keys."""
        from canopy_constants import TrainingConstants

        dm = DashboardManager(minimal_config)
        dm.config_mgr.get_training_defaults = MagicMock(return_value={})
        defaults = dm._get_training_defaults_with_env()
        assert defaults["learning_rate"] == TrainingConstants.DEFAULT_LEARNING_RATE
        assert defaults["hidden_units"] == TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS
        assert defaults["epochs"] == TrainingConstants.DEFAULT_TRAINING_EPOCHS


class TestDashboardManagerHandlers:
    """Test callback handler methods."""

    def test_toggle_dark_mode_handler_odd_clicks(self, dashboard_manager):
        """Test dark mode toggle returns dark on odd clicks."""
        is_dark, icon = dashboard_manager._toggle_dark_mode_handler(n_clicks=1)
        assert is_dark is True
        assert icon == "☀️"

    def test_toggle_dark_mode_handler_even_clicks(self, dashboard_manager):
        """Test dark mode toggle returns light on even clicks."""
        is_dark, icon = dashboard_manager._toggle_dark_mode_handler(n_clicks=2)
        assert is_dark is False
        assert icon == "🌙"

    def test_update_theme_state_handler_dark(self, dashboard_manager):
        """Test theme state handler returns 'dark' when is_dark=True."""
        result = dashboard_manager._update_theme_state_handler(is_dark=True)
        assert result == "dark"

    def test_update_theme_state_handler_light(self, dashboard_manager):
        """Test theme state handler returns 'light' when is_dark=False."""
        result = dashboard_manager._update_theme_state_handler(is_dark=False)
        assert result == "light"

    def test_toggle_network_info_handler_odd(self, dashboard_manager):
        """Test network info toggle returns True on odd clicks."""
        result = dashboard_manager._toggle_network_info_handler(n=1)
        assert result is True

    def test_toggle_network_info_handler_even(self, dashboard_manager):
        """Test network info toggle returns False on even clicks."""
        result = dashboard_manager._toggle_network_info_handler(n=2)
        assert result is False

    def test_toggle_network_info_handler_none(self, dashboard_manager):
        """Test network info toggle returns True on None (initial)."""
        result = dashboard_manager._toggle_network_info_handler(n=None)
        assert result is True

    def test_toggle_network_info_details_handler_odd(self, dashboard_manager):
        """Test network info details toggle returns True on odd clicks."""
        result = dashboard_manager._toggle_network_info_details_handler(n=1)
        assert result is True

    def test_toggle_network_info_details_handler_even(self, dashboard_manager):
        """Test network info details toggle returns False on even clicks."""
        result = dashboard_manager._toggle_network_info_details_handler(n=2)
        assert result is False

    def test_toggle_network_info_details_handler_none(self, dashboard_manager):
        """Test network info details toggle returns False on None (initial)."""
        result = dashboard_manager._toggle_network_info_details_handler(n=None)
        assert result is False

    def test_sync_input_values_from_backend_handler_with_state(self, dashboard_manager):
        """Test sync_input_values returns backend state values."""
        backend_state = {"learning_rate": 0.02, "max_hidden_units": 15, "max_epochs": 300}
        result = dashboard_manager._sync_input_values_from_backend_handler(backend_state=backend_state)
        assert result == (0.02, 15, 300)

    def test_sync_input_values_from_backend_handler_none(self, dashboard_manager):
        """Test sync_input_values returns no_update when state is None."""
        import dash

        result = dashboard_manager._sync_input_values_from_backend_handler(backend_state=None)
        assert result == (dash.no_update, dash.no_update, dash.no_update)

    def test_update_topology_store_handler_inactive_tab(self, dashboard_manager):
        """Test topology store handler returns no_update when tab is inactive."""
        import dash

        result = dashboard_manager._update_topology_store_handler(n=1, active_tab="metrics")
        assert result == dash.no_update

    def test_update_dataset_store_handler_inactive_tab(self, dashboard_manager):
        """Test dataset store handler returns no_update when tab is inactive."""
        import dash

        result = dashboard_manager._update_dataset_store_handler(n=1, active_tab="topology")
        assert result == dash.no_update

    def test_update_boundary_store_handler_inactive_tab(self, dashboard_manager):
        """Test boundary store handler returns no_update when tab is inactive."""
        import dash

        result = dashboard_manager._update_boundary_store_handler(n=1, active_tab="dataset")
        assert result == dash.no_update

    def test_update_boundary_dataset_store_handler_inactive_tab(self, dashboard_manager):
        """Test boundary dataset store handler returns no_update when tab is inactive."""
        import dash

        result = dashboard_manager._update_boundary_dataset_store_handler(n=1, active_tab="topology")
        assert result == dash.no_update


class TestDashboardManagerHandlersWithMocking:
    """Test callback handler methods that require mocking HTTP requests."""

    def test_update_metrics_store_handler_success(self, dashboard_manager, mocker):
        """Test metrics store handler fetches and returns metrics."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"history": [{"epoch": 1, "loss": 0.5}]}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)
            assert result == [{"epoch": 1, "loss": 0.5}]

    def test_update_metrics_store_handler_with_data_envelope(self, dashboard_manager, mocker):
        """Test metrics store handler handles 'data' envelope."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"epoch": 2, "loss": 0.3}]}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)
            assert result == [{"epoch": 2, "loss": 0.3}]

    def test_update_metrics_store_handler_with_list(self, dashboard_manager, mocker):
        """Test metrics store handler handles direct list response."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"epoch": 3, "loss": 0.1}]
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)
            assert result == [{"epoch": 3, "loss": 0.1}]

    def test_update_metrics_store_handler_empty_dict(self, dashboard_manager, mocker):
        """Test metrics store handler returns empty list for empty dict."""
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)
            assert result == []

    def test_update_metrics_store_handler_exception(self, dashboard_manager, mocker):
        """Test metrics store handler returns empty list on exception."""
        mocker.patch("requests.get", side_effect=Exception("Connection error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)
            assert result == []

    def test_update_topology_store_handler_success(self, dashboard_manager, mocker):
        """Test topology store handler fetches and returns topology."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"nodes": [], "total_connections": 5}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_topology_store_handler(n=1, active_tab="topology")
            assert result == {"nodes": [], "total_connections": 5}

    def test_update_topology_store_handler_exception(self, dashboard_manager, mocker):
        """Test topology store handler returns empty dict on exception."""
        mocker.patch("requests.get", side_effect=Exception("Timeout"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_topology_store_handler(n=1, active_tab="topology")
            assert result == {}

    def test_update_dataset_store_handler_success(self, dashboard_manager, mocker):
        """Test dataset store handler fetches and returns dataset."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"num_samples": 100, "data": []}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_dataset_store_handler(n=1, active_tab="dataset")
            assert result == {"num_samples": 100, "data": []}

    def test_update_dataset_store_handler_exception(self, dashboard_manager, mocker):
        """Test dataset store handler returns None on exception."""
        mocker.patch("requests.get", side_effect=Exception("Server error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_dataset_store_handler(n=1, active_tab="dataset")
            assert result is None

    def test_update_boundary_store_handler_success(self, dashboard_manager, mocker):
        """Test boundary store handler fetches and returns boundary data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"grid": [], "predictions": []}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_store_handler(n=1, active_tab="boundaries")
            assert result == {"grid": [], "predictions": []}

    def test_update_boundary_store_handler_exception(self, dashboard_manager, mocker):
        """Test boundary store handler returns None on exception."""
        mocker.patch("requests.get", side_effect=Exception("Network error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_store_handler(n=1, active_tab="boundaries")
            assert result is None

    def test_update_boundary_dataset_store_handler_success(self, dashboard_manager, mocker):
        """Test boundary dataset store handler fetches and returns data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"samples": []}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_dataset_store_handler(n=1, active_tab="boundaries")
            assert result == {"samples": []}

    def test_update_boundary_dataset_store_handler_exception(self, dashboard_manager, mocker):
        """Test boundary dataset store handler returns None on exception."""
        mocker.patch("requests.get", side_effect=Exception("API down"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_boundary_dataset_store_handler(n=1, active_tab="boundaries")
            assert result is None

    def test_update_network_info_handler_success(self, dashboard_manager, mocker):
        """Test network info handler fetches and returns HTML panel."""
        from dash import html

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "input_size": 2,
            "hidden_units": 5,
            "output_size": 1,
            "current_epoch": 50,
            "current_phase": "Training",
            "network_connected": True,
            "monitoring_active": True,
        }
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_handler(n=1)
            assert isinstance(result, html.Div)

    def test_update_network_info_handler_exception(self, dashboard_manager, mocker):
        """Test network info handler returns error panel on exception."""
        from dash import html

        mocker.patch("requests.get", side_effect=Exception("Connection failed"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_handler(n=1)
            assert isinstance(result, html.Div)

    def test_update_network_info_details_handler_success(self, dashboard_manager, mocker):
        """Test network info details handler fetches and returns detailed table."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"total_weights": 100, "active_units": 5}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_details_handler(n=1)
            assert result is not None

    def test_update_network_info_details_handler_exception(self, dashboard_manager, mocker):
        """Test network info details handler returns error panel on exception."""
        from dash import html

        mocker.patch("requests.get", side_effect=Exception("Stats unavailable"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_network_info_details_handler(n=1)
            assert isinstance(result, html.Div)


class TestBuildUnifiedStatusBarContent:
    """Test _build_unified_status_bar_content method."""

    def test_build_status_running(self, dashboard_manager):
        """Test status bar content for running state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "output",
            "current_epoch": 42,
            "hidden_units": 3,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50.0)
        assert result[3] == "Running"
        assert result[5] == "Output Training"
        assert result[7] == "42"
        assert result[8] == "3"

    def test_build_status_paused(self, dashboard_manager):
        """Test status bar content for paused state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": True,
            "completed": False,
            "failed": False,
            "phase": "candidate",
            "current_epoch": 100,
            "hidden_units": 5,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=200.0)
        assert result[3] == "Paused"
        assert result[5] == "Candidate Pool"

    def test_build_status_completed(self, dashboard_manager):
        """Test status bar content for completed state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": False,
            "is_paused": False,
            "completed": True,
            "failed": False,
            "phase": "idle",
            "current_epoch": 200,
            "hidden_units": 10,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=600.0)
        assert result[3] == "Completed"

    def test_build_status_failed(self, dashboard_manager):
        """Test status bar content for failed state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": False,
            "is_paused": False,
            "completed": False,
            "failed": True,
            "phase": "idle",
            "current_epoch": 50,
            "hidden_units": 2,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50.0)
        assert result[3] == "Failed"

    def test_build_status_stopped(self, dashboard_manager):
        """Test status bar content for stopped state."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": False,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "idle",
            "current_epoch": 0,
            "hidden_units": 0,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50.0)
        assert result[3] == "Stopped"
        assert result[5] == "Idle"

    def test_build_status_latency_colors(self, dashboard_manager):
        """Test latency indicator colors based on latency value."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": False,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "idle",
            "current_epoch": 0,
            "hidden_units": 0,
        }

        result_green = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50.0)
        assert result_green[0]["color"] == "#28a745"

        result_orange = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=300.0)
        assert result_orange[0]["color"] == "#ffc107"

        result_red = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=600.0)
        assert result_red[0]["color"] == "#dc3545"

    def test_build_status_phase_inference(self, dashboard_manager):
        """Test status bar content for inference phase."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "inference",
            "current_epoch": 150,
            "hidden_units": 7,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50.0)
        assert result[5] == "Inference"

    def test_build_status_unknown_phase(self, dashboard_manager):
        """Test status bar content for unknown phase (falls back to title case)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "custom_phase",
            "current_epoch": 10,
            "hidden_units": 1,
        }
        result = dashboard_manager._build_unified_status_bar_content(mock_response, latency_ms=50.0)
        assert result[5] == "Custom_Phase"


class TestTrainingButtonHandlers:
    """Test training button handler methods."""

    def test_update_last_click_handler_with_action(self, dashboard_manager):
        """Test update_last_click returns button and timestamp when action provided."""
        action = {"last": "start-button", "ts": 1234567890.0}
        result = dashboard_manager._update_last_click_handler(action=action)
        assert result == {"button": "start-button", "timestamp": 1234567890.0}

    def test_update_last_click_handler_no_action(self, dashboard_manager):
        """Test update_last_click returns no_update when no action."""
        import dash

        result = dashboard_manager._update_last_click_handler(action=None)
        assert result == dash.no_update

    def test_update_last_click_handler_empty_action(self, dashboard_manager):
        """Test update_last_click returns no_update when action has no 'last'."""
        import dash

        result = dashboard_manager._update_last_click_handler(action={})
        assert result == dash.no_update

    def test_update_button_appearance_handler_normal_state(self, dashboard_manager):
        """Test button appearance for normal (non-loading) state."""
        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }
        result = dashboard_manager._update_button_appearance_handler(button_states=button_states)
        assert result[0] is False
        assert "▶" in result[1]
        assert "⏳" not in result[1]

    def test_update_button_appearance_handler_loading_state(self, dashboard_manager):
        """Test button appearance for loading state."""
        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": 100},
            "pause": {"disabled": False, "loading": False, "timestamp": 0},
            "stop": {"disabled": False, "loading": False, "timestamp": 0},
            "resume": {"disabled": False, "loading": False, "timestamp": 0},
            "reset": {"disabled": False, "loading": False, "timestamp": 0},
        }
        result = dashboard_manager._update_button_appearance_handler(button_states=button_states)
        assert result[0] is True
        assert "⏳" in result[1]

    def test_handle_button_timeout_no_states(self, dashboard_manager):
        """Test button timeout handler returns no_update with no button states."""
        import dash

        result = dashboard_manager._handle_button_timeout_and_acks_handler(button_states=None)
        assert result == dash.no_update

    def test_handle_button_timeout_not_expired(self, dashboard_manager):
        """Test button timeout handler returns no_update when not yet expired."""
        import time

        import dash

        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": time.time()},
        }
        result = dashboard_manager._handle_button_timeout_and_acks_handler(button_states=button_states)
        assert result == dash.no_update

    def test_handle_button_timeout_expired(self, dashboard_manager):
        """Test button timeout handler resets button after timeout."""
        import time

        button_states = {
            "start": {"disabled": True, "loading": True, "timestamp": time.time() - 3.0},
        }
        result = dashboard_manager._handle_button_timeout_and_acks_handler(button_states=button_states)
        assert result["start"]["disabled"] is False
        assert result["start"]["loading"] is False

    def test_handle_button_timeout_non_loading_preserved(self, dashboard_manager):
        """Test button timeout handler preserves non-loading button states."""
        import time

        import dash

        button_states = {
            "start": {"disabled": False, "loading": False, "timestamp": 0},
        }
        result = dashboard_manager._handle_button_timeout_and_acks_handler(button_states=button_states)
        assert result == dash.no_update

    def test_sync_backend_params_handler_success(self, dashboard_manager, mocker):
        """Test sync_backend_params fetches and returns params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"learning_rate": 0.02, "max_hidden_units": 15, "max_epochs": 300}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._sync_backend_params_handler(n=1)
            assert result == {"learning_rate": 0.02, "max_hidden_units": 15, "max_epochs": 300}

    def test_sync_backend_params_handler_error(self, dashboard_manager, mocker):
        """Test sync_backend_params returns no_update on error."""
        import dash

        mocker.patch("requests.get", side_effect=Exception("Connection error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._sync_backend_params_handler(n=1)
            assert result == dash.no_update

    def test_sync_backend_params_handler_non_200(self, dashboard_manager, mocker):
        """Test sync_backend_params returns no_update on non-200 status."""
        import dash

        mock_response = MagicMock()
        mock_response.status_code = 500
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._sync_backend_params_handler(n=1)
            assert result == dash.no_update

    def test_handle_parameter_changes_handler(self, dashboard_manager):
        """Test parameter changes handler returns no_update (logs only)."""
        import dash

        result = dashboard_manager._handle_parameter_changes_handler(learning_rate=0.05, max_hidden_units=20)
        assert result == dash.no_update


class TestParameterHandlers:
    """Test parameter tracking and application handlers."""

    def test_track_param_changes_no_applied(self, dashboard_manager):
        """Test track_param_changes returns disabled when no applied state."""
        disabled, status = dashboard_manager._track_param_changes_handler(0.01, 10, 200, None)
        assert disabled is True
        assert status == ""

    def test_track_param_changes_no_changes(self, dashboard_manager):
        """Test track_param_changes returns disabled when no changes."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(0.01, 10, 200, applied)
        assert disabled is True
        assert status == ""

    def test_track_param_changes_lr_changed(self, dashboard_manager):
        """Test track_param_changes detects learning_rate changes."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(0.05, 10, 200, applied)
        assert disabled is False
        assert "Unsaved" in status

    def test_track_param_changes_hu_changed(self, dashboard_manager):
        """Test track_param_changes detects hidden_units changes."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(0.01, 15, 200, applied)
        assert disabled is False
        assert "Unsaved" in status

    def test_track_param_changes_epochs_changed(self, dashboard_manager):
        """Test track_param_changes detects epochs changes."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(0.01, 10, 500, applied)
        assert disabled is False
        assert "Unsaved" in status

    def test_track_param_changes_float_tolerance(self, dashboard_manager):
        """Test track_param_changes uses float tolerance for learning_rate."""
        applied = {"learning_rate": 0.01, "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(0.01 + 1e-10, 10, 200, applied)
        assert disabled is True
        assert status == ""

    def test_apply_parameters_no_clicks(self, dashboard_manager):
        """Test apply_parameters returns no_update when no clicks."""
        import dash

        result, msg = dashboard_manager._apply_parameters_handler(None, 0.01, 10, 200)
        assert result == dash.no_update
        assert msg == dash.no_update

    def test_apply_parameters_success(self, dashboard_manager, mocker):
        """Test apply_parameters successfully applies parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mocker.patch("requests.post", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result, msg = dashboard_manager._apply_parameters_handler(1, 0.05, 15, 300)
            assert result["learning_rate"] == 0.05
            assert result["max_hidden_units"] == 15
            assert result["max_epochs"] == 300
            assert "applied" in msg.lower()

    def test_apply_parameters_failure(self, dashboard_manager, mocker):
        """Test apply_parameters returns error on failure."""
        import dash

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mocker.patch("requests.post", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result, msg = dashboard_manager._apply_parameters_handler(1, 0.05, 15, 300)
            assert result == dash.no_update
            assert "Failed" in msg

    def test_apply_parameters_exception(self, dashboard_manager, mocker):
        """Test apply_parameters returns error on exception."""
        import dash

        mocker.patch("requests.post", side_effect=Exception("Network error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result, msg = dashboard_manager._apply_parameters_handler(1, 0.05, 15, 300)
            assert result == dash.no_update
            assert "Error" in msg

    def test_init_applied_params_with_existing(self, dashboard_manager):
        """Test init_applied_params returns no_update when current exists."""
        import dash

        result = dashboard_manager._init_applied_params_handler(1, {"learning_rate": 0.01})
        assert result == dash.no_update

    def test_init_applied_params_success(self, dashboard_manager, mocker):
        """Test init_applied_params fetches from backend when empty."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"learning_rate": 0.02, "max_hidden_units": 15, "max_epochs": 300}
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._init_applied_params_handler(1, None)
            assert result["learning_rate"] == 0.02

    def test_init_applied_params_error(self, dashboard_manager, mocker):
        """Test init_applied_params returns no_update on error."""
        import dash

        mocker.patch("requests.get", side_effect=Exception("Connection error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._init_applied_params_handler(1, None)
            assert result == dash.no_update

    def test_track_param_changes_none_values(self, dashboard_manager):
        """Test track_param_changes handles None values in float comparison."""
        applied = {"learning_rate": None, "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(None, 10, 200, applied)
        assert disabled is True

    def test_track_param_changes_invalid_float(self, dashboard_manager):
        """Test track_param_changes handles invalid float conversion."""
        applied = {"learning_rate": "invalid", "max_hidden_units": 10, "max_epochs": 200}
        disabled, status = dashboard_manager._track_param_changes_handler(0.01, 10, 200, applied)
        assert disabled is False


class TestHandleTrainingButtons:
    """Test _handle_training_buttons_handler method."""

    def test_handle_training_buttons_no_trigger(self, dashboard_manager):
        """Test handler returns no_update when no trigger."""
        import dash

        result = dashboard_manager._handle_training_buttons_handler(
            start_clicks=None,
            pause_clicks=None,
            stop_clicks=None,
            resume_clicks=None,
            reset_clicks=None,
            last_click=None,
            button_states={},
            trigger=None,
        )
        assert result == (dash.no_update, dash.no_update)

    def test_handle_training_buttons_debounced(self, dashboard_manager):
        """Test handler debounces duplicate clicks within 500ms."""
        import time

        import dash

        current_time = time.time()
        last_click = {"button": "start-button", "timestamp": current_time - 0.1}
        result = dashboard_manager._handle_training_buttons_handler(
            start_clicks=1,
            pause_clicks=None,
            stop_clicks=None,
            resume_clicks=None,
            reset_clicks=None,
            last_click=last_click,
            button_states={},
            trigger="start-button",
        )
        assert result == (dash.no_update, dash.no_update)

    def test_handle_training_buttons_success(self, dashboard_manager, mocker):
        """Test handler successfully sends command."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mocker.patch("requests.post", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            action, states = dashboard_manager._handle_training_buttons_handler(
                start_clicks=1,
                pause_clicks=None,
                stop_clicks=None,
                resume_clicks=None,
                reset_clicks=None,
                last_click=None,
                button_states={},
                trigger="start-button",
            )
            assert action["success"] is True
            assert action["last"] == "start-button"
            assert states["start"]["loading"] is True

    def test_handle_training_buttons_failure(self, dashboard_manager, mocker):
        """Test handler handles command failure."""
        mocker.patch("requests.post", side_effect=Exception("Connection error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            action, states = dashboard_manager._handle_training_buttons_handler(
                start_clicks=1,
                pause_clicks=None,
                stop_clicks=None,
                resume_clicks=None,
                reset_clicks=None,
                last_click=None,
                button_states={},
                trigger="start-button",
            )
            assert action["success"] is False
            assert states["start"]["loading"] is False

    def test_handle_training_buttons_pause(self, dashboard_manager, mocker):
        """Test handler sends pause command."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mocker.patch("requests.post", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            action, states = dashboard_manager._handle_training_buttons_handler(
                start_clicks=None,
                pause_clicks=1,
                stop_clicks=None,
                resume_clicks=None,
                reset_clicks=None,
                last_click=None,
                button_states={},
                trigger="pause-button",
            )
            assert action["last"] == "pause-button"
            assert states["pause"]["loading"] is True


class TestDashboardManagerMiscMethods:
    """Test miscellaneous DashboardManager methods."""

    def test_get_app_returns_dash_app(self, dashboard_manager):
        """Test get_app returns the Dash app instance."""
        app = dashboard_manager.get_app()
        assert app is dashboard_manager.app

    def test_handle_parameter_changes_lr_trigger(self, dashboard_manager):
        """Test parameter changes handler with learning-rate-input trigger."""
        import dash

        result = dashboard_manager._handle_parameter_changes_handler(learning_rate=0.05, max_hidden_units=10, trigger="learning-rate-input")
        assert result == dash.no_update

    def test_handle_parameter_changes_hu_trigger(self, dashboard_manager):
        """Test parameter changes handler with max-hidden-units-input trigger."""
        import dash

        result = dashboard_manager._handle_parameter_changes_handler(learning_rate=0.01, max_hidden_units=20, trigger="max-hidden-units-input")
        assert result == dash.no_update

    def test_update_metrics_store_non_list_non_dict(self, dashboard_manager, mocker):
        """Test metrics store handler handles unexpected payload type."""
        mock_response = MagicMock()
        mock_response.json.return_value = "unexpected_string"
        mocker.patch("requests.get", return_value=mock_response)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_metrics_store_handler(n=1)
            assert result == []

    def test_update_unified_status_bar_handler_success(self, dashboard_manager, mocker):
        """Test unified status bar handler fetches and returns status bar content."""
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200

        mock_status_response = MagicMock()
        mock_status_response.status_code = 200
        mock_status_response.json.return_value = {
            "is_running": True,
            "is_paused": False,
            "completed": False,
            "failed": False,
            "phase": "output",
            "current_epoch": 42,
            "hidden_units": 3,
        }

        def mock_get(url, **kwargs):
            if "health" in url:
                return mock_health_response
            return mock_status_response

        mocker.patch("requests.get", side_effect=mock_get)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)
            assert len(result) == 9
            assert result[3] == "Running"

    def test_update_unified_status_bar_handler_error_status(self, dashboard_manager, mocker):
        """Test unified status bar handler handles non-200 status."""
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200

        mock_status_response = MagicMock()
        mock_status_response.status_code = 500

        def mock_get(url, **kwargs):
            if "health" in url:
                return mock_health_response
            return mock_status_response

        mocker.patch("requests.get", side_effect=mock_get)

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)
            assert len(result) == 9
            assert result[3] == "Error"

    def test_update_unified_status_bar_handler_exception(self, dashboard_manager, mocker):
        """Test unified status bar handler handles exception."""
        mocker.patch("requests.get", side_effect=Exception("Connection error"))

        with dashboard_manager.app.server.test_request_context(base_url="http://localhost:8050"):
            result = dashboard_manager._update_unified_status_bar_handler(n_intervals=1)
            assert len(result) == 9
            assert result[3] == "Error"
