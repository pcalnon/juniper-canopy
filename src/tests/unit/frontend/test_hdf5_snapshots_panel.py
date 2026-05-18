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
                    if isinstance(inner, html.H3) and "Snapshots" in str(inner.children):
                        has_title = True
                        break
        assert has_title, "Layout should contain H3 title 'Snapshots'"

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

    def test_register_callbacks_creates_callbacks(self, panel):
        """Should register all callbacks (create, table, selection, detail, restore, history)."""
        mock_app = MagicMock()
        callback_count = 0

        def mock_callback(*args, **kwargs):
            nonlocal callback_count
            callback_count += 1
            return lambda f: f

        mock_app.callback = mock_callback

        panel.register_callbacks(mock_app)

        # Should have 9 callbacks:
        # P3-1: create_snapshot, update_snapshots_table, select_snapshot, update_detail_panel
        # P3-2: open_restore_modal, close_restore_modal, confirm_restore
        # P3-3: toggle_history
        # P2-7: render_dataset_swap_diffs (Issue #3)
        assert callback_count == 9


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
# P3-1: Create Snapshot Handler Tests
# =============================================================================


class TestHDF5SnapshotsCreateHandler:
    """Test HDF5SnapshotsPanel create snapshot handler."""

    def test_create_snapshot_success(self, panel):
        """Should return success on 201 response."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "snapshot_20260108_143022",
            "name": "snapshot_20260108_143022.h5",
            "timestamp": "2026-01-08T14:30:22Z",
            "size_bytes": 1048576,
            "message": "Demo snapshot created successfully",
        }

        with patch("requests.post", return_value=mock_response):
            result = panel._create_snapshot_handler()
            assert result["success"] is True
            assert result["snapshot"]["id"] == "snapshot_20260108_143022"
            assert "message" in result

    def test_create_snapshot_with_custom_name(self, panel):
        """Should pass custom name to API."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "my_custom_snapshot",
            "name": "my_custom_snapshot.h5",
            "timestamp": "2026-01-08T14:30:22Z",
            "size_bytes": 1048576,
            "message": "Snapshot created successfully",
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = panel._create_snapshot_handler(name="my_custom_snapshot")
            assert result["success"] is True

            # Verify the name was passed as a parameter
            call_kwargs = mock_post.call_args
            assert call_kwargs.kwargs.get("params", {}).get("name") == "my_custom_snapshot"

    def test_create_snapshot_with_description(self, panel):
        """Should pass description to API."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "snapshot_001",
            "message": "Snapshot created successfully",
        }

        with patch("requests.post", return_value=mock_response) as mock_post:
            result = panel._create_snapshot_handler(description="Test description")
            assert result["success"] is True

            # Verify the description was passed as a parameter
            call_kwargs = mock_post.call_args
            assert call_kwargs.kwargs.get("params", {}).get("description") == "Test description"

    def test_create_snapshot_server_error(self, panel):
        """Should return error on 500 response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"detail": "Internal server error"}'
        mock_response.json.return_value = {"detail": "Internal server error"}

        with patch("requests.post", return_value=mock_response):
            result = panel._create_snapshot_handler()
            assert result["success"] is False
            assert "error" in result

    def test_create_snapshot_timeout(self, panel):
        """Should handle timeout gracefully."""
        import requests

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            result = panel._create_snapshot_handler()
            assert result["success"] is False
            assert "timed out" in result["error"].lower()

    def test_create_snapshot_connection_error(self, panel):
        """Should handle connection error gracefully."""
        import requests

        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            result = panel._create_snapshot_handler()
            assert result["success"] is False
            assert "unavailable" in result["error"].lower()

    def test_create_snapshot_generic_exception(self, panel):
        """Should handle generic exception gracefully."""
        with patch("requests.post", side_effect=Exception("Unknown error")):
            result = panel._create_snapshot_handler()
            assert result["success"] is False
            assert "Unknown error" in result["error"]


# =============================================================================
# P3-1: Create Snapshot Layout Tests
# =============================================================================


class TestHDF5SnapshotsCreateLayout:
    """Test HDF5SnapshotsPanel create snapshot layout elements."""

    def test_layout_has_create_button(self, panel):
        """Layout should have create snapshot button."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "create-button" in layout_str

    def test_layout_has_create_name_input(self, panel):
        """Layout should have name input for create."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "create-name" in layout_str

    def test_layout_has_create_description_input(self, panel):
        """Layout should have description input for create."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "create-description" in layout_str

    def test_layout_has_create_status(self, panel):
        """Layout should have create status area."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "create-status" in layout_str

    def test_layout_has_refresh_trigger_store(self, panel):
        """Layout should have refresh trigger store."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "refresh-trigger" in layout_str

    def test_create_section_has_card_header(self, panel):
        """Create section should have 'Create New Snapshot' header."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Create New Snapshot" in layout_str


# =============================================================================
# Module Constants Tests
# =============================================================================


# =============================================================================
# P3-2: Restore Snapshot Handler Tests
# =============================================================================


class TestHDF5SnapshotsRestoreHandler:
    """Test HDF5SnapshotsPanel restore snapshot handler (P3-2)."""

    def test_restore_snapshot_success(self, panel):
        """Should return success on 200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "message": "Restored from snapshot 'demo_001'",
            "snapshot_id": "demo_001",
            "restored_at": "2026-01-09T10:30:00Z",
        }

        with patch("requests.post", return_value=mock_response):
            result = panel._restore_snapshot_handler("demo_001")
            assert result["success"] is True
            assert "message" in result
            assert result["data"]["snapshot_id"] == "demo_001"

    def test_restore_snapshot_conflict_409(self, panel):
        """Should return error on 409 (training running) response."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "Cannot restore while training is running"}

        with patch("requests.post", return_value=mock_response):
            result = panel._restore_snapshot_handler("demo_001")
            assert result["success"] is False
            assert "running" in result["error"].lower()

    def test_restore_snapshot_not_found_404(self, panel):
        """Should return error on 404 (snapshot not found) response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Snapshot not found"}

        with patch("requests.post", return_value=mock_response):
            result = panel._restore_snapshot_handler("nonexistent")
            assert result["success"] is False
            assert "not found" in result["error"].lower()

    def test_restore_snapshot_server_error(self, panel):
        """Should return error on 500 response."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = '{"detail": "Internal server error"}'
        mock_response.json.return_value = {"detail": "Internal server error"}

        with patch("requests.post", return_value=mock_response):
            result = panel._restore_snapshot_handler("demo_001")
            assert result["success"] is False
            assert "error" in result

    def test_restore_snapshot_timeout(self, panel):
        """Should handle timeout gracefully."""
        import requests

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            result = panel._restore_snapshot_handler("demo_001")
            assert result["success"] is False
            assert "timed out" in result["error"].lower()

    def test_restore_snapshot_connection_error(self, panel):
        """Should handle connection error gracefully."""
        import requests

        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            result = panel._restore_snapshot_handler("demo_001")
            assert result["success"] is False
            assert "unavailable" in result["error"].lower()

    def test_restore_snapshot_empty_id(self, panel):
        """Should return error for empty snapshot ID."""
        result = panel._restore_snapshot_handler("")
        assert result["success"] is False
        assert "no snapshot id" in result["error"].lower()

    def test_restore_snapshot_none_id(self, panel):
        """Should return error for None snapshot ID."""
        result = panel._restore_snapshot_handler(None)
        assert result["success"] is False


# =============================================================================
# P3-2: Restore Snapshot Layout Tests
# =============================================================================


class TestHDF5SnapshotsRestoreLayout:
    """Test HDF5SnapshotsPanel restore snapshot layout elements (P3-2)."""

    def test_layout_has_restore_modal(self, panel):
        """Layout should have restore confirmation modal."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "restore-modal" in layout_str

    def test_layout_has_restore_confirm_button(self, panel):
        """Layout should have restore confirm button."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "restore-confirm" in layout_str

    def test_layout_has_restore_cancel_button(self, panel):
        """Layout should have restore cancel button."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "restore-cancel" in layout_str

    def test_layout_has_restore_status(self, panel):
        """Layout should have restore status area."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "restore-status" in layout_str

    def test_layout_has_restore_pending_id_store(self, panel):
        """Layout should have restore pending ID store."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "restore-pending-id" in layout_str


# =============================================================================
# P3-3: History Handler Tests
# =============================================================================


class TestHDF5SnapshotsHistoryHandler:
    """Test HDF5SnapshotsPanel history handler (P3-3)."""

    def test_fetch_history_success(self, panel):
        """Should return history entries on successful API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "history": [
                {
                    "action": "create",
                    "snapshot_id": "snapshot_001",
                    "timestamp": "2026-01-09T10:30:00Z",
                    "message": "Created snapshot",
                },
                {
                    "action": "restore",
                    "snapshot_id": "demo_001",
                    "timestamp": "2026-01-09T11:00:00Z",
                    "message": "Restored from snapshot",
                },
            ],
            "total": 2,
        }

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_history_handler()
            assert len(result["history"]) == 2
            assert result["total"] == 2
            assert result["history"][0]["action"] == "create"

    def test_fetch_history_empty(self, panel):
        """Should handle empty history."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"history": [], "total": 0}

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_history_handler()
            assert result["history"] == []
            assert result["total"] == 0

    def test_fetch_history_with_limit(self, panel):
        """Should pass limit parameter to API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"history": [], "total": 0}

        with patch("requests.get", return_value=mock_response) as mock_get:
            panel._fetch_history_handler(limit=10)
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs.get("params", {}).get("limit") == 10

    def test_fetch_history_non_200_status(self, panel):
        """Should handle non-200 status code."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("requests.get", return_value=mock_response):
            result = panel._fetch_history_handler()
            assert result["history"] == []
            assert "API error" in result.get("message", "")

    def test_fetch_history_timeout(self, panel):
        """Should handle timeout gracefully."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.Timeout):
            result = panel._fetch_history_handler()
            assert result["history"] == []
            assert "timed out" in result["message"].lower()

    def test_fetch_history_connection_error(self, panel):
        """Should handle connection error gracefully."""
        import requests

        with patch("requests.get", side_effect=requests.exceptions.ConnectionError):
            result = panel._fetch_history_handler()
            assert result["history"] == []
            assert "unavailable" in result["message"].lower()


# =============================================================================
# P3-3: History Layout Tests
# =============================================================================


class TestHDF5SnapshotsHistoryLayout:
    """Test HDF5SnapshotsPanel history layout elements (P3-3)."""

    def test_layout_has_history_section(self, panel):
        """Layout should have history section."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "history-collapse" in layout_str

    def test_layout_has_history_toggle(self, panel):
        """Layout should have history toggle button."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "history-toggle" in layout_str

    def test_layout_has_history_content(self, panel):
        """Layout should have history content area."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "history-content" in layout_str

    def test_layout_has_snapshot_history_title(self, panel):
        """Layout should have 'Snapshot History' in title."""
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Snapshot History" in layout_str


class TestModuleConstants:
    """Test module-level constants."""

    def test_default_refresh_interval_is_reasonable(self):
        """Default refresh interval should be reasonable (5-30 seconds)."""
        assert 5000 <= DEFAULT_REFRESH_INTERVAL_MS <= 30000

    def test_default_refresh_interval_is_integer(self):
        """Default refresh interval should be an integer."""
        assert isinstance(DEFAULT_REFRESH_INTERVAL_MS, int)


# =============================================================================
# Phase 6E Sprint B (B-5, CAN-015e): snapshot UX entry points
# =============================================================================


class TestSnapshotOpHandlerB5:
    """Tests for ``_invoke_snapshot_op_handler`` covering all four operations."""

    @pytest.mark.parametrize("operation", ["restore", "replay", "resume", "retrain"])
    def test_invokes_correct_endpoint(self, panel, operation):
        captured = {}

        def fake_post(url, timeout=None, headers=None):
            captured["url"] = url
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "snapshot_id": "demo_001",
                "operation": operation,
                "fsm_state": "idle",
                "time_index": 0,
                "training_params": {},
                "message": f"{operation} ok",
            }
            return mock_response

        with patch("requests.post", side_effect=fake_post):
            result = panel._invoke_snapshot_op_handler("demo_001", operation)

        assert result["success"] is True
        assert captured["url"].endswith(f"/api/v1/snapshots/demo_001/{operation}")
        assert result["data"]["operation"] == operation

    def test_unknown_operation_rejected(self, panel):
        result = panel._invoke_snapshot_op_handler("demo_001", "delete")
        assert result["success"] is False
        assert "delete" in result["error"]

    def test_empty_snapshot_id_rejected(self, panel):
        result = panel._invoke_snapshot_op_handler("", "replay")
        assert result["success"] is False
        assert "no snapshot" in result["error"].lower()

    def test_409_conflict_returns_friendly_error(self, panel):
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "Training is running"}
        with patch("requests.post", return_value=mock_response):
            result = panel._invoke_snapshot_op_handler("demo_001", "resume")
        assert result["success"] is False
        assert "running" in result["error"].lower()

    def test_404_returns_not_found(self, panel):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Snapshot not found"}
        with patch("requests.post", return_value=mock_response):
            result = panel._invoke_snapshot_op_handler("nope", "retrain")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_501_demo_mode_returns_friendly_error(self, panel):
        mock_response = MagicMock()
        mock_response.status_code = 501
        mock_response.json.return_value = {"detail": "Live cascor backend required"}
        with patch("requests.post", return_value=mock_response):
            result = panel._invoke_snapshot_op_handler("demo_001", "replay")
        assert result["success"] is False
        assert "cascor" in result["error"].lower()

    def test_legacy_restore_handler_forwards_to_invoke(self, panel):
        with patch.object(panel, "_invoke_snapshot_op_handler") as mock_invoke:
            mock_invoke.return_value = {"success": True}
            panel._restore_snapshot_handler("demo_001")
            mock_invoke.assert_called_once_with("demo_001", "restore")


class TestSnapshotPanelB5Layout:
    """Layout-level assertions for the new UX surfaces."""

    def test_layout_has_context_menu_trigger_store(self, panel):
        layout_str = str(panel.get_layout())
        assert "context-menu-trigger" in layout_str

    def test_op_descriptions_cover_all_four(self, panel):
        for op in ("restore", "replay", "resume", "retrain"):
            assert op in panel._OP_DESCRIPTIONS
            assert panel._OP_DESCRIPTIONS[op]

    def test_op_confirm_labels_cover_all_four(self, panel):
        for op in ("restore", "replay", "resume", "retrain"):
            assert op in panel._OP_CONFIRM_LABELS

    def test_build_op_confirm_body_includes_snapshot_id(self, panel):
        body = panel._build_op_confirm_body("demo_001", "replay")
        assert "demo_001" in str(body)

    def test_build_op_confirm_body_includes_operation_description(self, panel):
        body = panel._build_op_confirm_body("demo_001", "retrain")
        assert "fresh training" in str(body).lower() or "starting point" in str(body).lower()
