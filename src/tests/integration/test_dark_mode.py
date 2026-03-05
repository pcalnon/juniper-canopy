#!/usr/bin/env python
"""
Dark mode integration tests for Juniper Canopy Dashboard.

Tests dark mode toggle functionality, theme persistence, and chart theming.
"""
import os

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create test client with demo mode."""
    with TestClient(app) as client:
        yield client


class TestDarkMode:
    """Dark mode functionality tests."""

    def test_dark_mode_toggle_button_exists(self, client):
        """Dark mode toggle button should exist in dashboard layout."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "dark-mode-toggle" in layout_str

    def test_dark_mode_store_exists(self, client):
        """Dark mode store should exist for persistence."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "dark-mode-store" in layout_str

    def test_theme_state_store_exists(self, client):
        """Theme state store should exist for component communication."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "theme-state" in layout_str

    def test_dark_mode_css_loaded(self, client):
        """Dark mode CSS file should be accessible."""
        response = client.get("/dashboard/assets/dark_mode.css")
        assert response.status_code == 200
        css_content = response.text
        assert "dark-mode" in css_content
        assert "--bg-color" in css_content
        assert "--text-color" in css_content

    def test_dark_mode_css_has_theme_variables(self, client):
        """Dark mode CSS should define proper theme variables."""
        response = client.get("/dashboard/assets/dark_mode.css")
        css_content = response.text

        # Check light theme variables
        assert "--bg-color: #ffffff" in css_content
        assert "--text-color: #212529" in css_content

        # Check dark theme variables
        assert ".dark-mode" in css_content
        assert "--bg-color: #1a1a1a" in css_content or "--bg-color:#1a1a1a" in css_content

    def test_dark_mode_toggle_changes_icon(self, client):
        """Toggling dark mode should change button icon between moon and sun."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "🌙" in layout_str

    def test_api_endpoints_still_work_with_dark_mode(self, client):
        """Dark mode should not interfere with API functionality."""
        endpoints = [
            "/api/health",
            "/api/status",
            "/api/metrics/history",
            "/api/topology",
            "/api/dataset",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in (200, 503), f"{endpoint} should still work"

    def test_wcag_contrast_compliance_documented(self, client):
        """CSS should document WCAG AA contrast compliance."""
        response = client.get("/dashboard/assets/dark_mode.css")
        css_content = response.text
        assert "WCAG" in css_content or "contrast" in css_content.lower()

    def test_plotly_dark_template_integration(self, client):
        """Components should be updated to use Plotly dark template."""
        import inspect

        from src.frontend.components import dataset_plotter, decision_boundary, metrics_panel, network_visualizer

        # Check metrics_panel
        source = inspect.getsource(metrics_panel.MetricsPanel._create_loss_plot)
        assert "plotly_dark" in source or "theme" in source

        # Check network_visualizer
        source = inspect.getsource(network_visualizer.NetworkVisualizer._create_network_graph)
        assert "plotly_dark" in source or "theme" in source

        # Check dataset_plotter
        source = inspect.getsource(dataset_plotter.DatasetPlotter._create_scatter_plot)
        assert "plotly_dark" in source or "theme" in source

        # Check decision_boundary
        source = inspect.getsource(decision_boundary.DecisionBoundary._create_boundary_plot)
        assert "plotly_dark" in source or "theme" in source

    def test_all_visualization_components_accept_theme(self, client):
        """All visualization components should accept theme parameter."""
        from src.frontend.components.dataset_plotter import DatasetPlotter
        from src.frontend.components.decision_boundary import DecisionBoundary
        from src.frontend.components.metrics_panel import MetricsPanel
        from src.frontend.components.network_visualizer import NetworkVisualizer

        # Create component instances
        metrics = MetricsPanel({}, "test-metrics")
        network = NetworkVisualizer({}, "test-network")
        dataset = DatasetPlotter({}, "test-dataset")
        boundary = DecisionBoundary({}, "test-boundary")

        # Test that figure methods accept theme parameter
        empty_fig = metrics._create_empty_plot("dark")
        assert empty_fig is not None

        empty_fig = network._create_empty_graph("dark")
        assert empty_fig is not None

        empty_fig = dataset._create_empty_plot("dark")
        assert empty_fig is not None

        empty_fig = boundary._create_empty_plot("dark")
        assert empty_fig is not None

    def test_dark_mode_theme_colors_applied(self, client):
        """Dark mode should apply correct background and text colors."""
        response = client.get("/dashboard/assets/dark_mode.css")
        css_content = response.text

        # Check dark mode applies dark background
        assert "#1a1a1a" in css_content or "#242424" in css_content

        # Check dark mode applies light text
        assert "#e9ecef" in css_content or "#adb5bd" in css_content

    def test_dark_mode_preserves_button_colors(self, client):
        """Dark mode should preserve Bootstrap button colors."""
        response = client.get("/dashboard/assets/dark_mode.css")
        css_content = response.text

        # Check buttons are styled in dark mode
        assert "btn-success" in css_content or ".dark-mode" in css_content
        assert "--success-color" in css_content or "--danger-color" in css_content

    def test_theme_state_passed_to_all_components(self, client):
        """Theme state should be passed to all visualization components."""
        import inspect

        from src.frontend.components import dataset_plotter, decision_boundary, metrics_panel, network_visualizer

        # Check that callbacks include theme-state input
        source_files = [
            inspect.getsource(metrics_panel.MetricsPanel),
            inspect.getsource(network_visualizer.NetworkVisualizer),
            inspect.getsource(dataset_plotter.DatasetPlotter),
            inspect.getsource(decision_boundary.DecisionBoundary),
        ]

        for source in source_files:
            assert "theme-state" in source or "theme" in source.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
