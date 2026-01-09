#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_hdf5_callbacks.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-09
# Last Modified: 2026-01-09
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Unit tests for HDF5SnapshotsPanel callback functions (P3-1, P3-2, P3-3)
#####################################################################
"""Unit tests for HDF5SnapshotsPanel callback functions.

These tests cover the Dash callback logic for creating, restoring,
and viewing snapshots as well as the history toggle functionality.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path before other imports
src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest
from dash import html

from frontend.components.hdf5_snapshots_panel import HDF5SnapshotsPanel

# =============================================================================
# Fixtures
# =============================================================================


class DummyApp:
    """Dummy Dash app for testing callbacks without running a server."""

    def callback(self, *args, **kwargs):
        """Return decorator that returns function unchanged."""

        def decorator(func):
            return func

        return decorator


@pytest.fixture
def config():
    """Basic config for HDF5 snapshots panel."""
    return {}


@pytest.fixture
def panel(config):
    """Create HDF5SnapshotsPanel instance."""
    return HDF5SnapshotsPanel(config, component_id="test-hdf5-snapshots")


@pytest.fixture
def registered_panel(panel):
    """Create panel with callbacks registered."""
    app = DummyApp()
    panel.register_callbacks(app)
    return panel


class FakeCtx:
    """Fake callback_context for testing."""

    def __init__(self, prop_id="", value=1):
        self.triggered = [{"prop_id": prop_id, "value": value}]


# =============================================================================
# P3-1: Create Snapshot Callback Tests
# =============================================================================


class TestCreateSnapshotCallback:
    """Test create_snapshot callback function (P3-1)."""

    def test_no_clicks_returns_unchanged(self, registered_panel):
        """Should return unchanged state when n_clicks is None."""
        result = registered_panel._cb_create_snapshot(None, "name", "desc", 5)

        assert result[0] == ""  # status empty
        assert result[1] == 5  # trigger unchanged
        assert result[2] == "name"  # name unchanged
        assert result[3] == "desc"  # description unchanged

    def test_zero_clicks_returns_unchanged(self, registered_panel):
        """Should return unchanged state when n_clicks is 0."""
        result = registered_panel._cb_create_snapshot(0, "test_name", "test_desc", 3)

        assert result[0] == ""
        assert result[1] == 3
        assert result[2] == "test_name"
        assert result[3] == "test_desc"

    def test_success_returns_status_and_clears_inputs(self, registered_panel):
        """Should return success status, increment trigger, and clear inputs."""
        with patch.object(
            registered_panel,
            "_create_snapshot_handler",
            return_value={
                "success": True,
                "snapshot": {"id": "snap_12345"},
                "message": "Created successfully",
            },
        ):
            result = registered_panel._cb_create_snapshot(1, "my_snap", "my_desc", 2)

        # First output is an html.Div with success styling
        status = result[0]
        assert isinstance(status, html.Div)
        status_str = str(status)
        assert "28a745" in status_str or "#28a745" in status_str  # Green color
        assert "snap_12345" in status_str

        # Trigger incremented
        assert result[1] == 3

        # Inputs cleared
        assert result[2] == ""
        assert result[3] == ""

    def test_error_returns_error_status_and_keeps_inputs(self, registered_panel):
        """Should return error status and keep inputs on failure."""
        with patch.object(
            registered_panel,
            "_create_snapshot_handler",
            return_value={
                "success": False,
                "error": "Backend not available",
            },
        ):
            result = registered_panel._cb_create_snapshot(1, "my_name", "my_desc", None)

        # First output is an html.Div with error styling
        status = result[0]
        assert isinstance(status, html.Div)
        status_str = str(status)
        assert "dc3545" in status_str or "#dc3545" in status_str  # Red color
        assert "Backend not available" in status_str

        # Trigger unchanged (None -> 0)
        assert result[1] == 0

        # Inputs kept
        assert result[2] == "my_name"
        assert result[3] == "my_desc"

    def test_handler_called_with_correct_args(self, registered_panel):
        """Should call handler with provided name and description."""
        mock_handler = MagicMock(return_value={"success": False, "error": "test"})
        with patch.object(registered_panel, "_create_snapshot_handler", mock_handler):
            registered_panel._cb_create_snapshot(1, "custom_name", "custom_desc", 0)

        mock_handler.assert_called_once_with(name="custom_name", description="custom_desc")


# =============================================================================
# Update Snapshots Table Callback Tests
# =============================================================================


class TestUpdateSnapshotsTableCallback:
    """Test update_snapshots_table callback function."""

    def test_returns_rows_for_snapshots(self, registered_panel):
        """Should return table rows for each snapshot."""
        mock_data = {
            "snapshots": [
                {
                    "id": "snap_001",
                    "name": "Snapshot One",
                    "timestamp": "2026-01-10T12:00:00Z",
                    "size_bytes": 2048,
                },
                {
                    "id": "snap_002",
                    "timestamp": "2026-01-11T13:30:00Z",
                    "size_bytes": 1048576,
                },
            ],
            "message": "Demo mode",
        }

        with patch.object(registered_panel, "_fetch_snapshots_handler", return_value=mock_data):
            rows, status, empty_style, store = registered_panel._cb_update_snapshots_table(0, 0, 0)

        # Should have 2 rows
        assert len(rows) == 2
        assert all(isinstance(row, html.Tr) for row in rows)

        # Status should mention count
        assert "2" in status
        assert "snapshot" in status.lower()

        # Empty state hidden
        assert empty_style.get("display") == "none"

        # Store has snapshots
        assert len(store["snapshots"]) == 2

    def test_empty_snapshots_shows_empty_state(self, registered_panel):
        """Should show empty state when no snapshots."""
        with patch.object(
            registered_panel,
            "_fetch_snapshots_handler",
            return_value={"snapshots": [], "message": "No data available"},
        ):
            rows, status, empty_style, store = registered_panel._cb_update_snapshots_table(0, 0, 0)

        assert len(rows) == 0
        assert "No data available" in status
        assert "display" not in empty_style or empty_style.get("display") != "none"
        assert len(store["snapshots"]) == 0

    def test_snapshot_with_name_uses_name(self, registered_panel):
        """Should use snapshot name if provided."""
        mock_data = {
            "snapshots": [{"id": "id1", "name": "Custom Name", "timestamp": "", "size_bytes": 0}],
            "message": None,
        }

        with patch.object(registered_panel, "_fetch_snapshots_handler", return_value=mock_data):
            rows, _, _, _ = registered_panel._cb_update_snapshots_table(1, 0, 0)

        # The name should appear in the first cell
        row_str = str(rows[0])
        assert "Custom Name" in row_str

    def test_snapshot_without_name_uses_id(self, registered_panel):
        """Should use snapshot ID if name not provided."""
        mock_data = {
            "snapshots": [{"id": "fallback_id", "timestamp": "", "size_bytes": 0}],
            "message": None,
        }

        with patch.object(registered_panel, "_fetch_snapshots_handler", return_value=mock_data):
            rows, _, _, _ = registered_panel._cb_update_snapshots_table(1, 0, 0)

        row_str = str(rows[0])
        assert "fallback_id" in row_str


# =============================================================================
# Select Snapshot Callback Tests
# =============================================================================


class TestSelectSnapshotCallback:
    """Test select_snapshot callback function."""

    def test_no_clicks_returns_none(self, registered_panel):
        """Should return None when no button clicked."""
        result = registered_panel._cb_select_snapshot(None, [])
        assert result is None

    def test_all_zeros_returns_none(self, registered_panel):
        """Should return None when all click counts are zero."""
        n_clicks_list = [0, 0, 0]
        ids = [
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_001"},
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_002"},
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_003"},
        ]

        result = registered_panel._cb_select_snapshot(n_clicks_list, ids)
        assert result is None

    def test_selects_clicked_button(self, registered_panel):
        """Should return snapshot ID of clicked button."""
        import frontend.components.hdf5_snapshots_panel as panel_module

        n_clicks_list = [0, 1, 0]
        ids = [
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_001"},
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_002"},
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_003"},
        ]

        triggered_id = '{"index":"snap_002","type":"test-hdf5-snapshots-view-btn"}.n_clicks'
        fake_ctx = FakeCtx(triggered_id, 1)

        with patch.object(panel_module, "callback_context", fake_ctx):
            result = registered_panel._cb_select_snapshot(n_clicks_list, ids)

        assert result == "snap_002"

    def test_no_triggered_returns_none(self, registered_panel):
        """Should return None when callback_context has no triggered."""
        import frontend.components.hdf5_snapshots_panel as panel_module

        n_clicks_list = [1, 0, 0]
        ids = [{"type": "test-hdf5-snapshots-view-btn", "index": "snap_001"}]

        fake_ctx = MagicMock()
        fake_ctx.triggered = []

        with patch.object(panel_module, "callback_context", fake_ctx):
            result = registered_panel._cb_select_snapshot(n_clicks_list, ids)

        assert result is None

    def test_fallback_to_max_clicks(self, registered_panel):
        """Should fallback to button with max clicks on parse error."""
        import frontend.components.hdf5_snapshots_panel as panel_module

        n_clicks_list = [2, 5, 1]
        ids = [
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_001"},
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_002"},
            {"type": "test-hdf5-snapshots-view-btn", "index": "snap_003"},
        ]

        # Invalid JSON prop_id should trigger fallback
        fake_ctx = FakeCtx("invalid_json.n_clicks", 1)

        with patch.object(panel_module, "callback_context", fake_ctx):
            result = registered_panel._cb_select_snapshot(n_clicks_list, ids)

        assert result == "snap_002"  # Has highest clicks (5)


# =============================================================================
# P3-2: Update Detail Panel Callback Tests
# =============================================================================


class TestUpdateDetailPanelCallback:
    """Test update_detail_panel callback function (P3-2)."""

    def test_no_selected_id_shows_placeholder(self, registered_panel):
        """Should show placeholder when no snapshot selected."""
        result = registered_panel._cb_update_detail_panel(None)

        assert isinstance(result, html.P)
        result_str = str(result)
        assert "Select a snapshot" in result_str

    def test_empty_selected_id_shows_placeholder(self, registered_panel):
        """Should show placeholder when selected ID is empty string."""
        result = registered_panel._cb_update_detail_panel("")

        assert isinstance(result, html.P)
        result_str = str(result)
        assert "Select a snapshot" in result_str

    def test_fetch_failure_shows_error(self, registered_panel):
        """Should show error when fetch fails."""
        with patch.object(registered_panel, "_fetch_snapshot_detail_handler", return_value={}):
            result = registered_panel._cb_update_detail_panel("snap_404")

        assert isinstance(result, html.Div)
        result_str = str(result)
        assert "Failed to load" in result_str or "snap_404" in result_str

    def test_success_shows_details(self, registered_panel):
        """Should show snapshot details on success."""
        mock_detail = {
            "id": "snap_test",
            "name": "Test Snapshot",
            "timestamp": "2026-01-10T14:30:00Z",
            "size_bytes": 4096,
            "path": "/path/to/snapshot.h5",
            "description": "Test description",
        }

        with patch.object(registered_panel, "_fetch_snapshot_detail_handler", return_value=mock_detail):
            result = registered_panel._cb_update_detail_panel("snap_test")

        result_str = str(result)
        assert "snap_test" in result_str
        assert "Test Snapshot" in result_str
        assert "2026-01-10" in result_str
        assert "/path/to/snapshot.h5" in result_str
        assert "Test description" in result_str

    def test_shows_hdf5_attributes(self, registered_panel):
        """Should show HDF5 attributes when available."""
        mock_detail = {
            "id": "snap_attrs",
            "name": "Snapshot with Attrs",
            "timestamp": "2026-01-10T12:00:00Z",
            "size_bytes": 1024,
            "attributes": {
                "epoch": 50,
                "learning_rate": 0.01,
                "hidden_units": 5,
            },
        }

        with patch.object(registered_panel, "_fetch_snapshot_detail_handler", return_value=mock_detail):
            result = registered_panel._cb_update_detail_panel("snap_attrs")

        result_str = str(result)
        assert "HDF5 Attributes" in result_str
        assert "epoch" in result_str
        assert "50" in result_str


# =============================================================================
# P3-2: Open Restore Modal Callback Tests
# =============================================================================


class TestOpenRestoreModalCallback:
    """Test open_restore_modal callback function (P3-2)."""

    def test_no_clicks_returns_closed(self, registered_panel):
        """Should return closed modal when no button clicked."""
        result = registered_panel._cb_open_restore_modal(None, [], False)

        assert result[0] is False  # Modal closed
        assert result[1] == ""  # Empty body
        assert result[2] is None  # No pending ID

    def test_all_zeros_returns_closed(self, registered_panel):
        """Should return closed modal when all click counts are zero."""
        n_clicks_list = [0, 0]
        ids = [
            {"type": "test-hdf5-snapshots-restore-btn", "index": "snap_001"},
            {"type": "test-hdf5-snapshots-restore-btn", "index": "snap_002"},
        ]

        result = registered_panel._cb_open_restore_modal(n_clicks_list, ids, False)

        assert result[0] is False
        assert result[1] == ""
        assert result[2] is None

    def test_opens_modal_with_snapshot_id(self, registered_panel):
        """Should open modal with correct snapshot ID."""
        import frontend.components.hdf5_snapshots_panel as panel_module

        n_clicks_list = [1, 0]
        ids = [
            {"type": "test-hdf5-snapshots-restore-btn", "index": "snap_restore"},
            {"type": "test-hdf5-snapshots-restore-btn", "index": "snap_002"},
        ]

        triggered_id = '{"index":"snap_restore","type":"test-hdf5-snapshots-restore-btn"}.n_clicks'
        fake_ctx = FakeCtx(triggered_id, 1)

        with patch.object(panel_module, "callback_context", fake_ctx):
            result = registered_panel._cb_open_restore_modal(n_clicks_list, ids, False)

        assert result[0] is True  # Modal open
        assert isinstance(result[1], html.Div)  # Modal body has content
        body_str = str(result[1])
        assert "snap_restore" in body_str
        assert result[2] == "snap_restore"  # Pending ID set

    def test_modal_shows_warning_message(self, registered_panel):
        """Should show warning about training state in modal."""
        import frontend.components.hdf5_snapshots_panel as panel_module

        n_clicks_list = [1]
        ids = [{"type": "test-hdf5-snapshots-restore-btn", "index": "test_snap"}]
        triggered_id = '{"index":"test_snap","type":"test-hdf5-snapshots-restore-btn"}.n_clicks'

        with patch.object(panel_module, "callback_context", FakeCtx(triggered_id, 1)):
            result = registered_panel._cb_open_restore_modal(n_clicks_list, ids, False)

        body_str = str(result[1])
        assert "paused or stopped" in body_str.lower() or "training" in body_str.lower()


# =============================================================================
# P3-2: Close Restore Modal Callback Tests
# =============================================================================


class TestCloseRestoreModalCallback:
    """Test close_restore_modal callback function (P3-2)."""

    def test_cancel_closes_modal(self, registered_panel):
        """Should return False to close modal on cancel click."""
        result = registered_panel._cb_close_restore_modal(1)
        assert result is False

    def test_no_clicks_returns_no_update(self, registered_panel):
        """Should return no_update when no clicks."""
        import dash

        result = registered_panel._cb_close_restore_modal(None)
        assert result == dash.no_update

    def test_zero_clicks_returns_no_update(self, registered_panel):
        """Should return no_update when clicks is 0."""
        import dash

        result = registered_panel._cb_close_restore_modal(0)
        assert result == dash.no_update


# =============================================================================
# P3-2: Confirm Restore Callback Tests
# =============================================================================


class TestConfirmRestoreCallback:
    """Test confirm_restore callback function (P3-2)."""

    def test_no_clicks_returns_no_update(self, registered_panel):
        """Should return no_update when no clicks."""
        import dash

        result = registered_panel._cb_confirm_restore(None, "snap_id", 0)

        assert result[0] == dash.no_update
        assert result[1] == dash.no_update
        assert result[2] == dash.no_update

    def test_no_snapshot_id_returns_no_update(self, registered_panel):
        """Should return no_update when no snapshot ID."""
        import dash

        result = registered_panel._cb_confirm_restore(1, None, 0)

        assert result[0] == dash.no_update
        assert result[1] == dash.no_update
        assert result[2] == dash.no_update

    def test_success_closes_modal_and_increments_trigger(self, registered_panel):
        """Should close modal and increment trigger on success."""
        with patch.object(
            registered_panel,
            "_restore_snapshot_handler",
            return_value={
                "success": True,
                "message": "Restored successfully",
                "data": {"snapshot_id": "snap_restore"},
            },
        ):
            result = registered_panel._cb_confirm_restore(1, "snap_restore", 5)

        # Modal closed
        assert result[0] is False

        # Status shows success
        status = result[1]
        assert isinstance(status, html.Div)
        status_str = str(status)
        assert "28a745" in status_str  # Green color
        assert "Restored" in status_str

        # Trigger incremented
        assert result[2] == 6

    def test_error_closes_modal_and_shows_error(self, registered_panel):
        """Should close modal and show error on failure."""
        with patch.object(
            registered_panel,
            "_restore_snapshot_handler",
            return_value={
                "success": False,
                "error": "Training is running",
            },
        ):
            result = registered_panel._cb_confirm_restore(1, "snap_id", 3)

        # Modal closed
        assert result[0] is False

        # Status shows error
        status = result[1]
        assert isinstance(status, html.Div)
        status_str = str(status)
        assert "dc3545" in status_str  # Red color
        assert "Training is running" in status_str

        # Trigger unchanged
        assert result[2] == 3

    def test_handler_called_with_correct_id(self, registered_panel):
        """Should call handler with correct snapshot ID."""
        mock_handler = MagicMock(return_value={"success": False, "error": "test"})

        with patch.object(registered_panel, "_restore_snapshot_handler", mock_handler):
            registered_panel._cb_confirm_restore(1, "specific_snap_id", 0)

        mock_handler.assert_called_once_with("specific_snap_id")


# =============================================================================
# P3-3: Toggle History Callback Tests
# =============================================================================


class TestToggleHistoryCallback:
    """Test toggle_history callback function (P3-3)."""

    def test_no_clicks_returns_no_update(self, registered_panel):
        """Should return no_update when no clicks."""
        import dash

        result = registered_panel._cb_toggle_history(None, False)

        assert result[0] == dash.no_update
        assert result[1] == dash.no_update
        assert result[2] == dash.no_update

    def test_opens_and_fetches_history(self, registered_panel):
        """Should open collapse and fetch history when opening."""
        mock_history = {
            "history": [
                {
                    "action": "create",
                    "snapshot_id": "snap_001",
                    "timestamp": "2026-01-09T10:30:00Z",
                    "message": "Created snapshot",
                },
                {
                    "action": "restore",
                    "snapshot_id": "snap_001",
                    "timestamp": "2026-01-09T11:00:00Z",
                    "message": "Restored from snapshot",
                },
            ],
            "total": 2,
        }

        with patch.object(registered_panel, "_fetch_history_handler", return_value=mock_history):
            result = registered_panel._cb_toggle_history(1, False)

        # Collapse opens
        assert result[0] is True

        # Icon changes to up arrow
        assert "▲" in result[1]

        # Content has history entries
        content_str = str(result[2])
        assert "snap_001" in content_str
        assert "CREATE" in content_str.upper() or "create" in content_str
        assert "RESTORE" in content_str.upper() or "restore" in content_str

    def test_closes_without_fetching(self, registered_panel):
        """Should close collapse without fetching when closing."""
        mock_handler = MagicMock()

        with patch.object(registered_panel, "_fetch_history_handler", mock_handler):
            result = registered_panel._cb_toggle_history(1, True)

        # Collapse closes
        assert result[0] is False

        # Icon changes to down arrow
        assert "▼" in result[1]

        # Handler not called
        mock_handler.assert_not_called()

    def test_empty_history_shows_message(self, registered_panel):
        """Should show empty message when no history."""
        with patch.object(
            registered_panel,
            "_fetch_history_handler",
            return_value={"history": [], "total": 0},
        ):
            result = registered_panel._cb_toggle_history(1, False)

        # Collapse opens
        assert result[0] is True

        # Content shows empty message
        content_str = str(result[2])
        assert "No snapshot activity" in content_str

    def test_history_entries_have_correct_icons(self, registered_panel):
        """Should show correct icons for different actions."""
        mock_history = {
            "history": [
                {"action": "create", "snapshot_id": "s1", "timestamp": "", "message": ""},
                {"action": "restore", "snapshot_id": "s2", "timestamp": "", "message": ""},
                {"action": "delete", "snapshot_id": "s3", "timestamp": "", "message": ""},
            ],
            "total": 3,
        }

        with patch.object(registered_panel, "_fetch_history_handler", return_value=mock_history):
            result = registered_panel._cb_toggle_history(1, False)

        content_str = str(result[2])
        assert "📸" in content_str  # Create icon
        assert "🔄" in content_str  # Restore icon
        assert "🗑️" in content_str  # Delete icon


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestCallbackEdgeCases:
    """Test edge cases in callbacks."""

    def test_create_with_none_trigger(self, registered_panel):
        """Should handle None current_trigger gracefully."""
        with patch.object(
            registered_panel,
            "_create_snapshot_handler",
            return_value={"success": True, "snapshot": {"id": "x"}, "message": "ok"},
        ):
            result = registered_panel._cb_create_snapshot(1, "", "", None)

        # None + 1 = 1
        assert result[1] == 1

    def test_confirm_restore_with_none_trigger(self, registered_panel):
        """Should handle None current_trigger gracefully."""
        with patch.object(
            registered_panel,
            "_restore_snapshot_handler",
            return_value={"success": True, "message": "ok"},
        ):
            result = registered_panel._cb_confirm_restore(1, "snap", None)

        # None + 1 = 1
        assert result[2] == 1

    def test_callback_functions_exposed(self, registered_panel):
        """All callback functions should be exposed after registration."""
        assert hasattr(registered_panel, "_cb_create_snapshot")
        assert hasattr(registered_panel, "_cb_update_snapshots_table")
        assert hasattr(registered_panel, "_cb_select_snapshot")
        assert hasattr(registered_panel, "_cb_update_detail_panel")
        assert hasattr(registered_panel, "_cb_open_restore_modal")
        assert hasattr(registered_panel, "_cb_close_restore_modal")
        assert hasattr(registered_panel, "_cb_confirm_restore")
        assert hasattr(registered_panel, "_cb_toggle_history")

        # All should be callable
        assert callable(registered_panel._cb_create_snapshot)
        assert callable(registered_panel._cb_update_snapshots_table)
        assert callable(registered_panel._cb_select_snapshot)
        assert callable(registered_panel._cb_update_detail_panel)
        assert callable(registered_panel._cb_open_restore_modal)
        assert callable(registered_panel._cb_close_restore_modal)
        assert callable(registered_panel._cb_confirm_restore)
        assert callable(registered_panel._cb_toggle_history)
