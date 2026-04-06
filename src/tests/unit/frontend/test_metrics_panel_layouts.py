#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_metrics_panel_layouts.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-09
# Last Modified: 2026-01-09
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for MetricsPanel layout save/load handlers (P3-4)
#####################################################################
"""Unit tests for MetricsPanel layout save/load functionality."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.components.metrics_panel import MetricsPanel  # noqa: E402


@pytest.fixture
def config():
    """Minimal config for metrics panel."""
    return {
        "max_data_points": 100,
        "update_interval": 500,
    }


@pytest.fixture
def metrics_panel(config):
    """Create MetricsPanel instance."""
    return MetricsPanel(config, component_id="test-panel")


@pytest.mark.unit
class TestFetchLayoutOptionsHandler:
    """Tests for _fetch_layout_options_handler method."""

    def test_fetch_layout_options_success(self, metrics_panel):
        """Should return list of layout options on success."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "layouts": [
                    {"name": "layout1", "created": "2026-01-09T10:00:00Z"},
                    {"name": "layout2", "created": "2026-01-09T11:00:00Z"},
                ],
                "total": 2,
            }
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_layout_options_handler()

            assert len(result) == 2
            assert result[0] == {"label": "layout1", "value": "layout1"}
            assert result[1] == {"label": "layout2", "value": "layout2"}

    def test_fetch_layout_options_empty(self, metrics_panel):
        """Should return empty list when no layouts exist."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"layouts": [], "total": 0}
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_layout_options_handler()

            assert result == []

    def test_fetch_layout_options_api_error(self, metrics_panel):
        """Should return empty list on API error."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = metrics_panel._fetch_layout_options_handler()

            assert result == []

    def test_fetch_layout_options_network_error(self, metrics_panel):
        """Should return empty list on network error."""
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            result = metrics_panel._fetch_layout_options_handler()

            assert result == []


@pytest.mark.unit
class TestSaveLayoutHandler:
    """Tests for _save_layout_handler method."""

    def test_save_layout_no_clicks(self, metrics_panel):
        """Should return empty status when no clicks."""
        result = metrics_panel._save_layout_handler(None, "test", {})
        assert result == ("", None, "")

    def test_save_layout_empty_name(self, metrics_panel):
        """Should return warning when name is empty."""
        result = metrics_panel._save_layout_handler(1, "", {})
        assert "Please enter a layout name" in result[0]

    def test_save_layout_whitespace_name(self, metrics_panel):
        """Should return warning when name is only whitespace."""
        result = metrics_panel._save_layout_handler(1, "   ", {})
        assert "Please enter a layout name" in result[0]

    def test_save_layout_success(self, metrics_panel):
        """Should save layout successfully."""
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"name": "test", "message": "Layout saved"}
            mock_post.return_value = mock_response

            result = metrics_panel._save_layout_handler(1, "test", {"zoom": "data"})

            assert "saved" in result[0]
            assert result[1] == {"refresh": True}
            assert result[2] == ""

    def test_save_layout_api_error(self, metrics_panel):
        """Should handle API error."""
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"detail": "Invalid name"}
            mock_post.return_value = mock_response

            result = metrics_panel._save_layout_handler(1, "test", {})

            assert "Failed" in result[0]

    def test_save_layout_timeout(self, metrics_panel):
        """Should handle timeout."""
        import requests

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout()

            result = metrics_panel._save_layout_handler(1, "test", {})

            assert "timed out" in result[0]

    def test_save_layout_network_error(self, metrics_panel):
        """Should handle network error."""
        with patch("requests.post") as mock_post:
            mock_post.side_effect = Exception("Connection refused")

            result = metrics_panel._save_layout_handler(1, "test", {})

            assert "Error" in result[0]


@pytest.mark.unit
class TestLoadLayoutHandler:
    """Tests for _load_layout_handler method."""

    def test_load_layout_no_clicks(self, metrics_panel):
        """Should return empty status when no clicks."""
        result = metrics_panel._load_layout_handler(None, "test")
        assert result == ("", {})

    def test_load_layout_no_selection(self, metrics_panel):
        """Should return warning when no layout selected."""
        result = metrics_panel._load_layout_handler(1, None)
        assert "Please select a layout" in result[0]

    def test_load_layout_success(self, metrics_panel):
        """Should load layout successfully."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "name": "test",
                "zoom_ranges": {"xaxis": [0, 100]},
            }
            mock_get.return_value = mock_response

            result = metrics_panel._load_layout_handler(1, "test")

            assert "loaded" in result[0]
            assert result[1] == {"xaxis": [0, 100]}

    def test_load_layout_not_found(self, metrics_panel):
        """Should handle not found error."""
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            result = metrics_panel._load_layout_handler(1, "missing")

            assert "not found" in result[0]

    def test_load_layout_timeout(self, metrics_panel):
        """Should handle timeout."""
        import requests

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            result = metrics_panel._load_layout_handler(1, "test")

            assert "timed out" in result[0]


@pytest.mark.unit
class TestDeleteLayoutHandler:
    """Tests for _delete_layout_handler method."""

    def test_delete_layout_no_clicks(self, metrics_panel):
        """Should return empty status when no clicks."""
        result = metrics_panel._delete_layout_handler(None, "test")
        assert result == ("", None, "test")

    def test_delete_layout_no_selection(self, metrics_panel):
        """Should return warning when no layout selected."""
        result = metrics_panel._delete_layout_handler(1, None)
        assert "Please select a layout" in result[0]

    def test_delete_layout_success(self, metrics_panel):
        """Should delete layout successfully."""
        with patch("requests.delete") as mock_delete:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"name": "test", "message": "Deleted"}
            mock_delete.return_value = mock_response

            result = metrics_panel._delete_layout_handler(1, "test")

            assert "deleted" in result[0]
            assert result[1] == {"refresh": True}
            assert result[2] is None

    def test_delete_layout_not_found(self, metrics_panel):
        """Should handle not found error."""
        with patch("requests.delete") as mock_delete:
            mock_response = Mock()
            mock_response.status_code = 404
            mock_delete.return_value = mock_response

            result = metrics_panel._delete_layout_handler(1, "missing")

            assert "not found" in result[0]

    def test_delete_layout_timeout(self, metrics_panel):
        """Should handle timeout."""
        import requests

        with patch("requests.delete") as mock_delete:
            mock_delete.side_effect = requests.exceptions.Timeout()

            result = metrics_panel._delete_layout_handler(1, "test")

            assert "timed out" in result[0]


@pytest.mark.unit
class TestLayoutControlsLayout:
    """Tests for layout controls UI elements."""

    def test_layout_controls_present_in_layout(self, metrics_panel):
        """Should include layout controls in get_layout()."""
        layout = metrics_panel.get_layout()
        layout_html = str(layout)

        assert "layout-controls" in layout_html
        assert "save-layout-btn" in layout_html
        assert "load-layout-btn" in layout_html
        assert "delete-layout-btn" in layout_html
        assert "layout-name-input" in layout_html
        assert "layout-dropdown" in layout_html

    def test_layout_store_present(self, metrics_panel):
        """Should include layout store in get_layout()."""
        layout = metrics_panel.get_layout()
        layout_html = str(layout)

        assert "layout-store" in layout_html

    def test_layout_status_present(self, metrics_panel):
        """Should include layout status div in get_layout()."""
        layout = metrics_panel.get_layout()
        layout_html = str(layout)

        assert "layout-status" in layout_html
