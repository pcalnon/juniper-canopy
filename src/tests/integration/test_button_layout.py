#!/usr/bin/env python
"""
Training Controls Button Layout Tests for Juniper Canopy Dashboard.

Tests button icons, color scheme, styling, and layout organization.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"
from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create test client with demo mode."""
    with TestClient(app) as client:
        yield client


class TestButtonLayout:
    """Training controls button layout and styling tests."""

    def test_start_button_has_icon(self, client):
        """Start button should have play icon."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "▶" in layout_str, "Start button should have play icon ▶"

    def test_pause_button_has_icon(self, client):
        """Pause button should have pause icon."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "⏸" in layout_str, "Pause button should have pause icon ⏸"

    def test_stop_button_has_icon(self, client):
        """Stop button should have stop icon."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "⏹" in layout_str, "Stop button should have stop icon ⏹"

    def test_resume_button_has_icon(self, client):
        """Resume button should have resume icon."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "⏯" in layout_str, "Resume button should have resume icon ⏯"

    def test_reset_button_has_icon(self, client):
        """Reset button should have reset icon."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "↻" in layout_str, "Reset button should have reset icon ↻"

    def test_buttons_have_custom_classes(self, client):
        """All buttons should have custom CSS classes for styling."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)

        assert "training-control-btn" in layout_str, "Buttons should have base training-control-btn class"
        assert "btn-start" in layout_str, "Start button should have btn-start class"
        assert "btn-pause" in layout_str, "Pause button should have btn-pause class"
        assert "btn-stop" in layout_str, "Stop button should have btn-stop class"
        assert "btn-resume" in layout_str, "Resume button should have btn-resume class"
        assert "btn-reset" in layout_str, "Reset button should have btn-reset class"

    def test_buttons_grouped_logically(self, client):
        """Buttons should be grouped in logical containers."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)

        assert "training-button-group" in layout_str, "Buttons should be in training-button-group containers"

    def test_controls_css_exists(self, client):
        """Controls CSS file should be accessible."""
        response = client.get("/dashboard/assets/controls.css")
        assert response.status_code == 200, "controls.css should be accessible"

    def test_controls_css_has_button_styles(self, client):
        """Controls CSS should define button styles."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert ".training-control-btn" in css_content, "CSS should define base button class"
        assert ".btn-start" in css_content, "CSS should define start button styles"
        assert ".btn-pause" in css_content, "CSS should define pause button styles"
        assert ".btn-stop" in css_content, "CSS should define stop button styles"
        assert ".btn-resume" in css_content, "CSS should define resume button styles"
        assert ".btn-reset" in css_content, "CSS should define reset button styles"

    def test_controls_css_has_color_scheme(self, client):
        """Controls CSS should define appropriate color scheme."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        # Check for green (start/resume)
        assert "#28a745" in css_content, "CSS should define green color for start/resume"

        # Check for yellow/orange (pause)
        assert "#ffc107" in css_content, "CSS should define yellow color for pause"

        # Check for red (stop)
        assert "#dc3545" in css_content, "CSS should define red color for stop"

        # Check for blue (reset)
        assert "#007bff" in css_content, "CSS should define blue color for reset"

    def test_controls_css_has_hover_states(self, client):
        """Controls CSS should define hover states."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert ":hover" in css_content, "CSS should define hover states"
        assert "transform" in css_content or "box-shadow" in css_content, "Hover should have visual feedback"

    def test_controls_css_has_click_animation(self, client):
        """Controls CSS should define click animations."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert ":active" in css_content, "CSS should define active/click states"
        assert "scale(0.95)" in css_content or "scale" in css_content, "Click should have scale animation"

    def test_controls_css_has_transitions(self, client):
        """Controls CSS should define smooth transitions."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert "transition" in css_content, "CSS should define transitions"
        assert "ease-in-out" in css_content or "ease" in css_content, "Transitions should have easing"

    def test_controls_css_has_min_size(self, client):
        """Controls CSS should define minimum button size for touch."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert "min-height" in css_content, "CSS should define minimum height"
        assert "min-width" in css_content or "min-height" in css_content, "Buttons should have minimum size"

    def test_controls_css_has_dark_mode(self, client):
        """Controls CSS should support dark mode."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert ".dark-mode" in css_content, "CSS should support dark mode"

    def test_controls_css_has_accessibility_focus(self, client):
        """Controls CSS should define focus styles for accessibility."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert ":focus" in css_content, "CSS should define focus states for accessibility"

    def test_button_layout_responsive(self, client):
        """Controls CSS should have responsive design."""
        response = client.get("/dashboard/assets/controls.css")
        css_content = response.text

        assert "@media" in css_content or "responsive" in css_content.lower(), "CSS should have responsive design"

    def test_start_button_exists(self, client):
        """Start button should exist in dashboard."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "start-button" in layout_str

    def test_pause_button_exists(self, client):
        """Pause button should exist in dashboard."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "pause-button" in layout_str

    def test_stop_button_exists(self, client):
        """Stop button should exist in dashboard."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "stop-button" in layout_str

    def test_resume_button_exists(self, client):
        """Resume button should exist in dashboard."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "resume-button" in layout_str

    def test_reset_button_exists(self, client):
        """Reset button should exist in dashboard."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)
        assert "reset-button" in layout_str

    def test_button_group_separation(self, client):
        """Control buttons should be separated from reset button."""
        from src.frontend.dashboard_manager import DashboardManager

        config = {}
        dm = DashboardManager(config)
        layout_str = str(dm.app.layout)

        # Should have multiple button groups or separator
        assert "training-button-group" in layout_str, "Should have button groups"
        assert layout_str.count("training-button-group") >= 2, "Should have multiple button groups for separation"
