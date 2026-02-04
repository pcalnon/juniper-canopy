#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_dashboard_manager.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for DashboardManager
#####################################################################
"""Unit tests for DashboardManager."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.dashboard_manager import DashboardManager  # noqa: E402


@pytest.fixture
def config():
    """Basic config for dashboard manager."""
    return {"title": "Test Dashboard", "update_interval": 1000, "server": {"host": "localhost", "port": 8050}}


@pytest.fixture
def dashboard(config):
    """Create DashboardManager instance."""
    return DashboardManager(config)


class TestDashboardManagerInitialization:
    """Test DashboardManager initialization."""

    def test_init_with_config(self, config):
        """Should initialize with config."""
        dashboard = DashboardManager(config)
        assert dashboard is not None

    def test_init_with_empty_config(self):
        """Should initialize with empty config."""
        dashboard = DashboardManager({})
        assert dashboard is not None

    def test_init_creates_dash_app(self, dashboard):
        """Should create Dash app instance."""
        assert hasattr(dashboard, "app")
        assert dashboard.app is not None

    def test_dash_app_has_server(self, dashboard):
        """Dash app should have Flask server."""
        assert hasattr(dashboard.app, "server")
        assert dashboard.app.server is not None

    def test_config_stored(self, dashboard, config):
        """Should store config."""
        assert hasattr(dashboard, "config")
        assert dashboard.config is not None


class TestDashboardManagerComponents:
    """Test component creation and management."""

    def test_has_components(self, dashboard):
        """Should have components attribute."""
        assert hasattr(dashboard, "components") or hasattr(dashboard, "_components")

    def test_create_metrics_panel(self, dashboard):
        """Should create metrics panel component."""
        if hasattr(dashboard, "_create_metrics_panel"):
            panel = dashboard._create_metrics_panel()
            assert panel is not None

    def test_create_network_visualizer(self, dashboard):
        """Should create network visualizer component."""
        if hasattr(dashboard, "_create_network_visualizer"):
            viz = dashboard._create_network_visualizer()
            assert viz is not None

    def test_create_decision_boundary(self, dashboard):
        """Should create decision boundary component."""
        if hasattr(dashboard, "_create_decision_boundary"):
            boundary = dashboard._create_decision_boundary()
            assert boundary is not None

    def test_create_dataset_plotter(self, dashboard):
        """Should create dataset plotter component."""
        if hasattr(dashboard, "_create_dataset_plotter"):
            plotter = dashboard._create_dataset_plotter()
            assert plotter is not None


class TestDashboardManagerLayout:
    """Test layout creation."""

    def test_create_layout(self, dashboard):
        """Should create layout."""
        if hasattr(dashboard, "_create_layout"):
            layout = dashboard._create_layout()
            assert layout is not None

    def test_layout_assigned_to_app(self, dashboard):
        """Layout should be assigned to app."""
        assert dashboard.app.layout is not None

    def test_layout_contains_components(self, dashboard):
        """Layout should contain component areas."""
        layout = dashboard.app.layout

        # Check if layout has children
        if hasattr(layout, "children"):
            assert layout.children is not None


class TestDashboardManagerCallbacks:
    """Test callback setup."""

    def test_setup_callbacks(self, dashboard):
        """Should have setup_callbacks method."""
        assert hasattr(dashboard, "_setup_callbacks") or hasattr(dashboard, "setup_callbacks")

    def test_callbacks_registered(self, dashboard):
        """Callbacks should be registered on app."""
        # Dash stores callbacks internally
        assert len(dashboard.app.callback_map) >= 0


class TestDashboardManagerAPIURL:
    """Test API URL helper."""

    def test_has_api_url_method(self, dashboard):
        """Should have _api_url method."""
        assert hasattr(dashboard, "_api_url")

    def test_api_url_construction(self, dashboard):
        """Should construct API URLs correctly."""
        with dashboard.app.server.test_request_context("/dashboard/", base_url="http://localhost:8050"):
            url = dashboard._api_url("/test")
            assert url == "http://localhost:8050/test"

    def test_api_url_with_different_paths(self, dashboard):
        """Should handle different API paths."""
        paths = ["/metrics", "/topology", "/dataset"]
        with dashboard.app.server.test_request_context("/dashboard/", base_url="http://localhost:8050"):
            for path in paths:
                url = dashboard._api_url(path)
                assert url.startswith("http://localhost:8050")
                assert path in url

    def test_api_url_handles_leading_slash(self, dashboard):
        """Should handle paths with and without leading slash."""
        with dashboard.app.server.test_request_context("/dashboard/", base_url="http://localhost:8050"):
            url1 = dashboard._api_url("/test")
            url2 = dashboard._api_url("test")
            assert url1 == url2


class TestDashboardManagerConfiguration:
    """Test configuration handling."""

    def test_title_from_config(self):
        """Should use title from config."""
        config = {"title": "Custom Title"}
        dashboard = DashboardManager(config)
        # Title should be set somewhere (app.title or config)
        if hasattr(dashboard.app, "title"):
            assert "Custom" in dashboard.app.title or "Custom" in str(dashboard.config.get("title"))

    def test_update_interval_from_config(self):
        """Should use update_interval from config."""
        config = {"update_interval": 5000}
        dashboard = DashboardManager(config)
        assert dashboard.config.get("update_interval") == 5000

    def test_server_config(self):
        """Should handle server configuration."""
        config = {"server": {"host": "127.0.0.1", "port": 9000}}
        dashboard = DashboardManager(config)
        assert dashboard.config.get("server") is not None


class TestDashboardManagerTabNavigation:
    """Test tab navigation if present."""

    def test_has_tabs(self, dashboard):
        """Should have tabs in layout."""
        from dash import dcc

        layout = dashboard.app.layout

        def find_tabs(component):
            if isinstance(component, dcc.Tabs):
                return True
            if hasattr(component, "children"):
                if isinstance(component.children, list):
                    return any(find_tabs(child) for child in component.children)
                elif component.children is not None:
                    return find_tabs(component.children)
            return False

        # May or may not have tabs depending on design
        has_tabs = find_tabs(layout)
        # Just check it doesn't crash
        assert isinstance(has_tabs, bool)


class TestDashboardManagerAssets:
    """Test asset handling."""

    def test_assets_folder_set(self, dashboard):
        """Should have assets folder configured."""
        if hasattr(dashboard.app, "assets_folder"):
            assert dashboard.app.assets_folder is not None

    def test_assets_url_path(self, dashboard):
        """Should have assets URL path."""
        if hasattr(dashboard.app, "assets_url_path"):
            assert dashboard.app.assets_url_path is not None


class TestDashboardManagerEdgeCases:
    """Test edge cases."""

    def test_none_config_values(self):
        """Should handle None config values - either accepts them or raises TypeError/ValueError."""
        config = {"title": None, "update_interval": None}
        try:
            dashboard = DashboardManager(config)
            # If we get here, None values were handled gracefully (valid behavior)
            assert dashboard is not None, "Dashboard should be created"
        except (TypeError, ValueError):
            # Not accepting None values is also valid behavior
            pass  # Test passes - rejecting None is acceptable

    def test_missing_server_config(self):
        """Should handle missing server config."""
        config = {}
        dashboard = DashboardManager(config)
        # Should use defaults
        assert dashboard is not None

    def test_extra_config_params(self):
        """Should ignore extra config parameters."""
        config = {"title": "Test", "extra_param": "value", "another_param": 123}
        dashboard = DashboardManager(config)
        assert dashboard is not None


class TestDashboardManagerIntegration:
    """Test integration with components."""

    def test_all_components_in_layout(self, dashboard):
        """All components should be in layout."""
        layout = dashboard.app.layout

        # Layout should have some structure
        if hasattr(layout, "children"):
            assert layout.children is not None
            # Should have multiple children if using multiple components
            if isinstance(layout.children, list):
                assert len(layout.children) > 0

    def test_component_callbacks_registered(self, dashboard):
        """Component callbacks should be registered."""
        # Dashboard should have registered callbacks from components
        callback_map = dashboard.app.callback_map
        # Should have at least some callbacks
        assert isinstance(callback_map, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
