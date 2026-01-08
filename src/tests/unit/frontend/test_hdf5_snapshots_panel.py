#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_hdf5_snapshots_panel.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-08
# Last Modified: 2026-01-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for HDF5SnapshotsPanel component (P2-4, P2-5)
#####################################################################
"""Unit tests for HDF5SnapshotsPanel component."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path before other imports
src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402
from dash import dcc, html  # noqa: E402

from frontend.components.hdf5_snapshots_panel import (  # noqa: E402
    DEFAULT_REFRESH_INTERVAL_MS,
    HDF5SnapshotsPanel,
)


@pytest.fixture
def config():
    """Basic config for HDF5 snapshots panel."""
    return {}


@pytest.fixture
def panel(config):
    """Create HDF5SnapshotsPanel instance."""
    return HDF5SnapshotsPanel(config, component_id="test-hdf5-snapshots")


@pytest.fixture
def custom_config():
    """Config with custom refresh interval."""
    return {
        "refresh_interval": 5000,
        "api_timeout": 5,
    }


# =============================================================================
# Initialization Tests
# =============================================================================


class TestHDF5SnapshotsPanelInitialization:
    """Test HDF5SnapshotsPanel initialization."""

    def test_init_default_config(self):
        """Should initialize with empty config."""
        panel = HDF5SnapshotsPanel({})
        assert panel is not None
        assert panel.component_id == "hdf5-snapshots-panel"

    def test_init_custom_id(self, config):
        """Should initialize with custom ID."""
        panel = HDF5SnapshotsPanel(config, component_id="custom-snapshots")
        assert panel.component_id == "custom-snapshots"

    def test_init_default_refresh_interval(self, panel):
        """Should use default refresh interval."""
        assert panel.refresh_interval == DEFAULT_REFRESH_INTERVAL_MS

    def test_init_custom_refresh_interval(self, custom_config):
        """Should use custom refresh interval from config."""
        panel = HDF5SnapshotsPanel(custom_config)
        assert panel.refresh_interval == 5000

    def test_init_custom_api_timeout(self, custom_config):
        """Should use custom API timeout from config."""
        panel = HDF5SnapshotsPanel(custom_config)
        assert panel.api_timeout == 5

    def test_init_default_api_timeout(self, panel):
        """Should use default API timeout."""
        assert panel.api_timeout == 2

    @patch.dict("os.environ", {"JUNIPER_CANOPY_SNAPSHOTS_REFRESH_INTERVAL_MS": "15000"})
    def test_init_env_var_refresh_interval(self):
        """Should use refresh interval from environment variable."""
        panel = HDF5SnapshotsPanel({})
        assert panel.refresh_interval == 15000

    @patch.dict("os.environ", {"JUNIPER_CANOPY_SNAPSHOTS_REFRESH_INTERVAL_MS": "invalid"})
    def test_init_invalid_env_var_uses_default(self):
        """Should use default if environment variable is invalid."""
        panel = HDF5SnapshotsPanel({})
        assert panel.refresh_interval == DEFAULT_REFRESH_INTERVAL_MS


# =============================================================================
# Layout Tests
# =============================================================================


class TestHDF5SnapshotsPanelLayout:
    """Test HDF5SnapshotsPanel layout structure."""

    def test_layout_returns_div(self, panel):
        """Layout should return an html.Div."""
        layout = panel.get_layout()
        assert isinstance(layout, html.Div)

    def test_layout_has_component_id(self, panel):
        """Layout should have the component ID."""
        layout = panel.get_layout()
        assert layout.id == "test-hdf5-snapshots"

    def test_layout_has_title(self, panel):
        """Layout should have H3 title."""
        layout = panel.get_layout()
        children = layout.children

        # Find H3 title
        has_title = False
        for child in children:
            if isinstance(child, html.Div):
                for inner in child.children if hasattr(child, "children") and child.children else []:
                    if isinstance(inner, html.H3) and "HDF5 Snapshots" in str(inner.children):
                        has_title = True
                        break
        assert has_title, "Layout should contain H3 title 'HDF5 Snapshots'"

    def test_layout_has_refresh_button(self, panel):
        """Layout should have refresh button."""
        self._check_for_arg_in_panel_layout(panel, "refresh-button")

    def test_layout_has_status_span(self, panel):
        """Layout should have status span."""
        self._check_for_arg_in_panel_layout(panel, "status")

    def test_layout_has_table(self, panel):
        """Layout should have table for snapshots."""
        self._check_for_arg_in_panel_layout(panel, "table")

    def test_layout_has_table_body(self, panel):
        """Layout should have table body element."""
        self._check_for_arg_in_panel_layout(panel, "table-body")

    def test_layout_has_detail_panel(self, panel):
        """Layout should have detail panel."""
        self._check_for_arg_in_panel_layout(panel, "detail-panel")

    def test_layout_has_refresh_interval(self, panel):
        """Layout should have dcc.Interval for auto-refresh."""
        self._check_for_arg_in_panel_layout(panel, "refresh-interval")

    def test_layout_has_snapshots_store(self, panel):
        """Layout should have dcc.Store for snapshots data."""
        self._check_for_arg_in_panel_layout(panel, "snapshots-store")

    def test_layout_has_selected_id_store(self, panel):
        """Layout should have dcc.Store for selected snapshot ID."""
        self._check_for_arg_in_panel_layout(panel, "selected-id")

    def _check_for_arg_in_panel_layout(self, panel, arg1):
        layout = panel.get_layout()
        layout_str = str(layout)
        assert arg1 in layout_str


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHDF5SnapshotsPanelHelpers:
    """Test HDF5SnapshotsPanel helper methods."""

    def test_format_size_bytes(self, panel):
        """Should format bytes correctly."""
        assert panel._format_size(512) == "512 B"

    def test_format_size_kilobytes(self, panel):
        """Should format kilobytes correctly."""
        self._validate_format_size(panel, 1536, "KB", "1.5")
        # result = panel._format_size(1536)  # 1.5 KB
        # assert "KB" in result
        # assert "1.5" in result

    def test_format_size_megabytes(self, panel):
        """Should format megabytes correctly."""
        self._validate_format_size(panel, 1048576, "MB", "1.00")
        # result = panel._format_size(1048576)  # 1 MB
        # assert "MB" in result
        # assert "1.00" in result

    def test_format_size_gigabytes(self, panel):
        """Should format gigabytes correctly."""
        self._validate_format_size(panel, 1073741824, "GB", "1.00")
        # result = panel._format_size(1073741824)  # 1 GB
        # assert "GB" in result
        # assert "1.00" in result

    def _validate_format_size(self, panel, arg1, arg2, arg3):
        result = panel._format_size(arg1)
        assert arg2 in result
        assert arg3 in result

    def test_format_size_zero(self, panel):
        """Should return dash for zero size."""
        assert panel._format_size(0) == "-"

    def test_format_size_negative(self, panel):
        """Should return dash for negative size."""
        assert panel._format_size(-100) == "-"

    def test_format_size_none(self, panel):
        """Should return dash for None."""
        assert panel._format_size(None) == "-"

    def test_format_timestamp_valid(self, panel):
        """Should format valid timestamp."""
        result = panel._format_timestamp("2026-01-08T10:30:00Z")
        assert "2026-01-08" in result
        assert "10:30:00" in result

    def test_format_timestamp_empty(self, panel):
        """Should return dash for empty timestamp."""
        assert panel._format_timestamp("") == "-"

    def test_format_timestamp_none(self, panel):
        """Should return dash for None."""
        assert panel._format_timestamp(None) == "-"


# =============================================================================
# Fetch Handler Tests
# =============================================================================


class TestHDF5SnapshotsFetchHandlers:
    """Test HDF5SnapshotsPanel fetch handler methods."""

    def test_fetch_snapshots_success(self, panel):
        """Should return snapshots on successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "snapshots": [
                {"id": "snap1", "name": "Snapshot 1", "timestamp": "2026-01-08T10:00:00Z", "size_bytes": 1024},
            ]
        }

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_snapshots_handler()
            assert "snapshots" in result
            assert len(result["snapshots"]) == 1
            assert result["snapshots"][0]["id"] == "snap1"

    def test_fetch_snapshots_non_200_status(self, panel):
        """Should return empty list on non-200 status."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_snapshots_handler()
            assert result["snapshots"] == []
            assert "error" in result.get("message", "").lower() or "500" in result.get("message", "")

    def test_fetch_snapshots_timeout(self):
        """Should handle timeout gracefully."""
        import requests

        from frontend.components.hdf5_snapshots_panel import HDF5SnapshotsPanel

        panel = HDF5SnapshotsPanel({})
        with patch(
            "frontend.components.hdf5_snapshots_panel.requests.get",
            side_effect=requests.exceptions.Timeout,
        ):
            result = panel._fetch_snapshots_handler()
            assert result["snapshots"] == []
            message = result.get("message", "")
            # Message is "Request timed out" - check for "timed out"
            assert "timed out" in message.lower(), f"Expected 'timed out' in message, got: {message!r}"

    def test_fetch_snapshots_connection_error(self, panel):
        """Should handle connection error gracefully."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            self._force_fetch_snapshots_error(panel)
            # result = panel._fetch_snapshots_handler()
            # assert result["snapshots"] == []
            # assert "unavailable" in result.get("message", "").lower()

    def test_fetch_snapshots_generic_exception(self, panel):
        """Should handle generic exception gracefully."""
        with patch("requests.get", side_effect=Exception("Unknown error")):
            self._force_fetch_snapshots_error(panel)
            # result = panel._fetch_snapshots_handler()
            # assert result["snapshots"] == []
            # assert "unavailable" in result.get("message", "").lower()

    def _force_fetch_snapshots_error(self, panel):
        result = panel._fetch_snapshots_handler()
        assert result["snapshots"] == []
        assert "unavailable" in result.get("message", "").lower()

    def test_fetch_snapshot_detail_success(self, panel):
        """Should return detail on successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "snap1",
            "name": "Snapshot 1",
            "timestamp": "2026-01-08T10:00:00Z",
            "size_bytes": 1024,
            "attributes": {"key": "value"},
        }

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_snapshot_detail_handler("snap1")
            assert result["id"] == "snap1"
            assert result["attributes"]["key"] == "value"

    def test_fetch_snapshot_detail_not_found(self, panel):
        """Should return empty dict on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_snapshot_detail_handler("nonexistent")
            assert result == {}

    def test_fetch_snapshot_detail_empty_id(self, panel):
        """Should return empty dict for empty ID."""
        result = panel._fetch_snapshot_detail_handler("")
        assert result == {}

    def test_fetch_snapshot_detail_none_id(self, panel):
        """Should return empty dict for None ID."""
        result = panel._fetch_snapshot_detail_handler(None)
        assert result == {}

    def test_fetch_snapshot_detail_timeout(self, panel):
        """Should handle timeout gracefully."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            result = panel._fetch_snapshot_detail_handler("snap1")
            assert result == {}

    def test_fetch_snapshot_detail_connection_error(self, panel):
        """Should handle connection error gracefully."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            result = panel._fetch_snapshot_detail_handler("snap1")
            assert result == {}


# =============================================================================
# Callback Registration Tests
# =============================================================================


class TestHDF5SnapshotsPanelCallbacks:
    """Test HDF5SnapshotsPanel callback registration."""

    def test_register_callbacks_no_exception(self, panel):
        """Should register callbacks without exception."""
        mock_app = MagicMock()
        mock_app.callback = MagicMock(return_value=lambda f: f)

        # Should not raise
        panel.register_callbacks(mock_app)

    def test_register_callbacks_creates_three_callbacks(self, panel):
        """Should register three callbacks (table, selection, detail)."""
        mock_app = MagicMock()
        callback_count = 0

        def mock_callback(*args, **kwargs):
            nonlocal callback_count
            callback_count += 1
            return lambda f: f

        mock_app.callback = mock_callback

        panel.register_callbacks(mock_app)

        # Should have 3 callbacks: update_snapshots_table, select_snapshot, update_detail_panel
        assert callback_count == 3


# =============================================================================
# Integration Tests (Component Interface)
# =============================================================================


class TestHDF5SnapshotsPanelInterface:
    """Test HDF5SnapshotsPanel conforms to BaseComponent interface."""

    def test_inherits_from_base_component(self, panel):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(panel, BaseComponent)

    def test_has_get_layout_method(self, panel):
        """Should have get_layout method."""
        assert hasattr(panel, "get_layout")
        assert callable(panel.get_layout)

    def test_has_register_callbacks_method(self, panel):
        """Should have register_callbacks method."""
        assert hasattr(panel, "register_callbacks")
        assert callable(panel.register_callbacks)

    def test_has_component_id(self, panel):
        """Should have component_id attribute."""
        assert hasattr(panel, "component_id")

    def test_has_config(self, panel):
        """Should have config attribute."""
        assert hasattr(panel, "config")

    def test_has_logger(self, panel):
        """Should have logger attribute."""
        assert hasattr(panel, "logger")


# =============================================================================
# Module Constants Tests
# =============================================================================


class TestModuleConstants:
    """Test module-level constants."""

    def test_default_refresh_interval_is_reasonable(self):
        """Default refresh interval should be reasonable (5-30 seconds)."""
        assert 5000 <= DEFAULT_REFRESH_INTERVAL_MS <= 30000

    def test_default_refresh_interval_is_integer(self):
        """Default refresh interval should be an integer."""
        assert isinstance(DEFAULT_REFRESH_INTERVAL_MS, int)
