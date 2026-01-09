#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_about_panel.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-07
# Last Modified: 2026-01-07
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for AboutPanel component (P2-3)
#####################################################################
"""Unit tests for AboutPanel component."""

import sys
from pathlib import Path

# Add src to path before other imports
src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402
from dash import html  # noqa: E402

from frontend.components.about_panel import (  # noqa: E402
    APP_NAME,
    APP_VERSION,
    COPYRIGHT_YEAR,
    AboutPanel,
)


@pytest.fixture
def config():
    """Basic config for about panel."""
    return {}


@pytest.fixture
def panel(config):
    """Create AboutPanel instance."""
    return AboutPanel(config, component_id="test-about")


@pytest.fixture
def custom_config():
    """Config with custom version and app name."""
    return {
        "version": "3.0.0-custom",
        "app_name": "Custom Juniper",
    }


class TestAboutPanelInitialization:
    """Test AboutPanel initialization."""

    def test_init_default_config(self):
        """Should initialize with empty config."""
        panel = AboutPanel({})
        assert panel is not None
        assert panel.component_id == "about-panel"

    def test_init_custom_id(self, config):
        """Should initialize with custom ID."""
        panel = AboutPanel(config, component_id="custom-about")
        assert panel.component_id == "custom-about"

    def test_init_default_version(self, panel):
        """Should use default version from module constants."""
        assert panel.version == APP_VERSION

    def test_init_default_app_name(self, panel):
        """Should use default app name from module constants."""
        assert panel.app_name == APP_NAME

    def test_init_custom_version(self, custom_config):
        """Should use custom version from config."""
        panel = AboutPanel(custom_config)
        assert panel.version == "3.0.0-custom"

    def test_init_custom_app_name(self, custom_config):
        """Should use custom app name from config."""
        panel = AboutPanel(custom_config)
        assert panel.app_name == "Custom Juniper"


class TestAboutPanelLayout:
    """Test AboutPanel layout structure."""

    def test_layout_returns_div(self, panel):
        """Layout should return an html.Div."""
        layout = panel.get_layout()
        assert isinstance(layout, html.Div)

    def test_layout_has_component_id(self, panel):
        """Layout should have the component ID."""
        layout = panel.get_layout()
        assert layout.id == "test-about"

    def test_layout_contains_version(self, panel):
        """Layout should display the version."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert APP_VERSION in layout_str

    def test_layout_contains_app_name(self, panel):
        """Layout should display the app name."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Juniper Canopy" in layout_str

    def test_layout_contains_license_info(self, panel):
        """Layout should contain license information."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "MIT License" in layout_str

    def test_layout_contains_copyright(self, panel):
        """Layout should contain copyright information."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert COPYRIGHT_YEAR in layout_str
        assert "Paul Calnon" in layout_str

    def test_layout_contains_credits_section(self, panel):
        """Layout should contain credits section."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Credits" in layout_str or "Acknowledgments" in layout_str

    def test_layout_contains_documentation_section(self, panel):
        """Layout should contain documentation links."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Documentation" in layout_str or "Support" in layout_str

    def test_layout_contains_contact_section(self, panel):
        """Layout should contain contact information."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Contact" in layout_str or "github" in layout_str.lower()

    def test_layout_contains_github_link(self, panel):
        """Layout should contain link to GitHub repository."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "github.com/pcalnon/Juniper" in layout_str

    def test_layout_contains_system_info_toggle(self, panel):
        """Layout should contain system information toggle."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "system-info" in layout_str.lower()


class TestAboutPanelContent:
    """Test AboutPanel content details."""

    def test_mentions_cascor(self, panel):
        """Layout should mention Cascade Correlation."""
        layout = panel.get_layout()
        layout_str = str(layout)
        # Either full name or abbreviation
        assert "Cascade Correlation" in layout_str or "CasCor" in layout_str

    def test_mentions_technologies(self, panel):
        """Layout should mention key technologies used."""
        layout = panel.get_layout()
        layout_str = str(layout)
        # Should mention at least some key technologies
        tech_mentioned = sum(1 for tech in ["Python", "FastAPI", "Dash", "Plotly", "NumPy"] if tech in layout_str)
        assert tech_mentioned >= 2, "Should mention at least 2 key technologies"

    def test_has_documentation_links(self, panel):
        """Layout should have documentation links."""
        layout = panel.get_layout()
        layout_str = str(layout)
        # Should have links to docs
        assert "docs/" in layout_str.lower() or "documentation" in layout_str.lower()


class TestAboutPanelIntegration:
    """Test AboutPanel integration patterns."""

    def test_can_be_registered_as_component(self, panel):
        """Panel should follow BaseComponent interface."""
        # Should have required methods
        assert hasattr(panel, "get_layout")
        assert hasattr(panel, "register_callbacks")
        assert hasattr(panel, "component_id")
        assert hasattr(panel, "config")
        assert hasattr(panel, "logger")

    def test_register_callbacks_does_not_fail(self, panel):
        """register_callbacks should not fail without an app."""
        # Create a mock app-like object
        from unittest.mock import MagicMock

        mock_app = MagicMock()
        mock_app.callback = MagicMock(return_value=lambda x: x)

        # Should not raise
        try:
            panel.register_callbacks(mock_app)
        except Exception as e:
            pytest.fail(f"register_callbacks raised unexpected exception: {e}")


class TestModuleConstants:
    """Test module-level constants."""

    def test_app_version_is_string(self):
        """APP_VERSION should be a string."""
        assert isinstance(APP_VERSION, str)

    def test_app_version_format(self):
        """APP_VERSION should follow semver-like format."""
        parts = APP_VERSION.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"

    def test_app_name_is_string(self):
        """APP_NAME should be a string."""
        assert isinstance(APP_NAME, str)

    def test_app_name_contains_juniper(self):
        """APP_NAME should contain Juniper."""
        assert "Juniper" in APP_NAME

    def test_copyright_year_format(self):
        """COPYRIGHT_YEAR should be in expected format."""
        assert isinstance(COPYRIGHT_YEAR, str)
        # Should be a year or range like "2024" or "2024-2026"
        assert "202" in COPYRIGHT_YEAR


# =============================================================================
# Callback Tests
# =============================================================================


class DummyApp:
    """Dummy Dash app for testing callbacks without running a server."""

    def callback(self, *args, **kwargs):
        """Return decorator that returns function unchanged."""

        def decorator(func):
            return func

        return decorator


@pytest.fixture
def registered_panel(panel):
    """Create panel with callbacks registered."""
    app = DummyApp()
    panel.register_callbacks(app)
    return panel


class TestAboutPanelCallbacks:
    """Test AboutPanel callback functions."""

    def test_toggle_system_info_opens_when_clicked(self, registered_panel):
        """Should return True (open) when clicked while closed."""
        result = registered_panel._cb_toggle_system_info(1, False)
        assert result is True

    def test_toggle_system_info_closes_when_clicked(self, registered_panel):
        """Should return False (closed) when clicked while open."""
        result = registered_panel._cb_toggle_system_info(1, True)
        assert result is False

    def test_toggle_system_info_no_clicks(self, registered_panel):
        """Should return current state when no clicks."""
        result = registered_panel._cb_toggle_system_info(None, True)
        assert result is True

        result = registered_panel._cb_toggle_system_info(0, False)
        assert result is False

    def test_update_system_info_closed_returns_empty(self, registered_panel):
        """Should return empty list when collapse is closed."""
        result = registered_panel._cb_update_system_info(False)
        assert result == []

    def test_update_system_info_open_returns_content(self, registered_panel):
        """Should return system info list when collapse is open."""
        result = registered_panel._cb_update_system_info(True)

        # Should be an html.Ul
        assert isinstance(result, html.Ul)

        # Should contain system info
        result_str = str(result)
        assert "Python Version" in result_str
        assert "Platform" in result_str
        assert "Architecture" in result_str
        assert "App Version" in result_str
        assert registered_panel.version in result_str

    def test_callbacks_exposed_after_registration(self, registered_panel):
        """Callback functions should be exposed after registration."""
        assert hasattr(registered_panel, "_cb_toggle_system_info")
        assert hasattr(registered_panel, "_cb_update_system_info")
        assert callable(registered_panel._cb_toggle_system_info)
        assert callable(registered_panel._cb_update_system_info)
