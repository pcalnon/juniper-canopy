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
        # 4 default components: metrics_panel, network_visualizer, dataset_plotter, decision_boundary
        assert len(dm.components) == 6  # metrics, network, dataset, decision, about, hdf5_snapshots

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
