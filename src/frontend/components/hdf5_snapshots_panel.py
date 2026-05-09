#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     hdf5_snapshots_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-01-08
# Last Modified: 2026-01-08
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    HDF5 snapshots panel component displaying available training snapshots and their details.
#
#####################################################################################################################################################################################################
# Notes:
#
# HDF5 Snapshots Panel Component
#
# Panel displaying available HDF5 training state snapshots with auto-refresh and detail view.
# Provides list of snapshots with timestamp, size, and ability to view detailed metadata.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#   - Initial implementation for Phase 2 (P2-4, P2-5)
#
#####################################################################################################################################################################################################
import contextlib
import os
from typing import Any, Dict, List

import dash
import dash_bootstrap_components as dbc
import requests
from dash import callback_context, dcc, html
from dash.dependencies import ALL, Input, Output, State

from settings import get_settings

from ..base_component import BaseComponent

# Default refresh interval in milliseconds
DEFAULT_REFRESH_INTERVAL_MS = 10000  # 10 seconds


class HDF5SnapshotsPanel(BaseComponent):
    """
    Panel listing available HDF5 snapshots and showing details for a selected snapshot.

    Shows:
    - List of available snapshots in a table (Name/ID, Timestamp, Size)
    - Refresh button for manual refresh
    - Auto-refresh via dcc.Interval
    - Detail view when a snapshot is selected
    - Error handling for backend unavailability
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "hdf5-snapshots-panel"):
        """
        Initialize HDF5 snapshots panel component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        _settings = get_settings()
        self._api_base_url = f"http://127.0.0.1:{_settings.server.port}"

        # Refresh interval: config > env > default
        if "refresh_interval" in config:
            self.refresh_interval = config["refresh_interval"]
        elif interval_env := os.getenv("JUNIPER_CANOPY_SNAPSHOTS_REFRESH_INTERVAL_MS"):
            try:
                self.refresh_interval = int(interval_env)
                self.logger.info(f"Snapshots refresh interval overridden by env: {interval_env}ms")
            except ValueError:
                self.refresh_interval = DEFAULT_REFRESH_INTERVAL_MS
        else:
            self.refresh_interval = DEFAULT_REFRESH_INTERVAL_MS

        # API timeout in seconds
        self.api_timeout = config.get("api_timeout", 2)

        self.logger.info(f"HDF5SnapshotsPanel initialized with refresh_interval={self.refresh_interval}ms")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for HDF5 snapshots panel.

        Returns:
            Dash Div containing the snapshots panel
        """
        return html.Div(
            [
                # Header with title
                html.Div(
                    [
                        html.H3(
                            "Snapshots",
                            style={"display": "inline-block", "marginRight": "20px", "color": "var(--header-color)"},
                        ),
                    ],
                    style={"marginBottom": "15px"},
                ),
                # Create Snapshot section (P3-1)
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Create New Snapshot", className="mb-0"),
                        ),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.Label("Snapshot Name (optional):", size="sm"),
                                                dbc.Input(
                                                    id=f"{self.component_id}-create-name",
                                                    type="text",
                                                    placeholder="Auto-generated if empty",
                                                    size="sm",
                                                ),
                                            ],
                                            width=4,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.Label("Description (optional):", size="sm"),
                                                dbc.Input(
                                                    id=f"{self.component_id}-create-description",
                                                    type="text",
                                                    placeholder="Enter description",
                                                    size="sm",
                                                ),
                                            ],
                                            width=5,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.Label("\u00a0", size="sm"),  # Spacer for alignment
                                                html.Div(
                                                    dbc.Button(
                                                        "📸 Create Snapshot",
                                                        id=f"{self.component_id}-create-button",
                                                        color="success",
                                                        size="sm",
                                                        className="w-100",
                                                    ),
                                                ),
                                            ],
                                            width=3,
                                        ),
                                    ],
                                    className="g-2",
                                ),
                                # Create status message
                                html.Div(
                                    id=f"{self.component_id}-create-status",
                                    style={"marginTop": "10px", "fontSize": "0.9rem"},
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # Description
                html.P(
                    "View and manage HDF5 training state snapshots. Snapshots contain saved network states " "that can be loaded for analysis or resumed training.",
                    style={"fontSize": "14px", "color": "var(--text-muted)", "marginBottom": "20px"},
                ),
                html.Hr(),
                # Snapshots table card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.Div(
                                [
                                    html.H5("Available Snapshots", className="mb-0", style={"display": "inline-block"}),
                                    dbc.Button(
                                        "🔄 Refresh",
                                        id=f"{self.component_id}-refresh-button",
                                        color="primary",
                                        size="sm",
                                        className="ms-3",
                                    ),
                                    html.Span(
                                        id=f"{self.component_id}-status",
                                        children="Loading snapshots...",
                                        style={"fontSize": "0.9rem", "color": "var(--text-muted)", "marginLeft": "10px"},
                                    ),
                                ],
                                style={"display": "flex", "alignItems": "center"},
                            ),
                        ),
                        dbc.CardBody(
                            [
                                # Snapshot table
                                html.Table(
                                    [
                                        html.Thead(
                                            html.Tr(
                                                [
                                                    html.Th("Name / ID", style={"width": "40%", "padding": "10px"}),
                                                    html.Th("Timestamp", style={"width": "30%", "padding": "10px"}),
                                                    html.Th("Size", style={"width": "15%", "padding": "10px"}),
                                                    html.Th("", style={"width": "15%", "padding": "10px"}),
                                                ],
                                                style={"backgroundColor": "var(--bg-secondary)"},
                                            )
                                        ),
                                        html.Tbody(id=f"{self.component_id}-table-body"),
                                    ],
                                    id=f"{self.component_id}-table",
                                    style={
                                        "width": "100%",
                                        "borderCollapse": "collapse",
                                        "border": "1px solid var(--border-color, #dee2e6)",
                                    },
                                ),
                                # Empty state message
                                html.Div(
                                    id=f"{self.component_id}-empty-state",
                                    children="No snapshots available.",
                                    style={
                                        "marginTop": "15px",
                                        "color": "var(--text-muted)",
                                        "fontSize": "0.9rem",
                                        "textAlign": "center",
                                        "padding": "20px",
                                        "display": "none",
                                    },
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # Detail view card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Snapshot Details", className="mb-0"),
                        ),
                        dbc.CardBody(
                            id=f"{self.component_id}-detail-panel",
                            children=html.P(
                                "Select a snapshot from the table above to view its details.",
                                style={"color": "var(--text-muted)", "fontStyle": "italic"},
                            ),
                        ),
                    ],
                    className="mb-3",
                ),
                # Snapshot operation confirmation modal (CAN-015e
                # generalization of P3-2). Modal title and confirm button
                # label become generic to accommodate all four snapshot
                # operations (Restore / Replay / Resume / Retrain); the
                # body carries the operation-specific description and the
                # snapshot ID. Original element ids preserved
                # (``-restore-modal``, ``-restore-confirm``) so the
                # existing callback graph keeps wiring up without touching
                # downstream callbacks.
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Confirm Snapshot Operation")),
                        dbc.ModalBody(
                            id=f"{self.component_id}-restore-modal-body",
                            children="Are you sure?",
                        ),
                        dbc.ModalFooter(
                            [
                                dbc.Button(
                                    "Cancel",
                                    id=f"{self.component_id}-restore-cancel",
                                    color="secondary",
                                    className="me-2",
                                ),
                                dbc.Button(
                                    "Confirm",
                                    id=f"{self.component_id}-restore-confirm",
                                    color="warning",
                                ),
                            ]
                        ),
                    ],
                    id=f"{self.component_id}-restore-modal",
                    is_open=False,
                    centered=True,
                ),
                # Restore status message
                html.Div(
                    id=f"{self.component_id}-restore-status",
                    style={"marginBottom": "15px"},
                ),
                # History section (P3-3) - collapsible
                dbc.Card(
                    [
                        dbc.CardHeader(
                            dbc.Button(
                                [
                                    html.Span("📜 Snapshot History"),
                                    html.Span(
                                        id=f"{self.component_id}-history-toggle-icon",
                                        children=" ▼",
                                        style={"marginLeft": "10px"},
                                    ),
                                ],
                                id=f"{self.component_id}-history-toggle",
                                color="link",
                                className="p-0 text-decoration-none",
                                style={"color": "var(--header-color)", "fontWeight": "500"},
                            ),
                        ),
                        dbc.Collapse(
                            dbc.CardBody(
                                [
                                    html.Div(
                                        id=f"{self.component_id}-history-content",
                                        children="Loading history...",
                                    ),
                                ]
                            ),
                            id=f"{self.component_id}-history-collapse",
                            is_open=False,
                        ),
                    ],
                    className="mb-3",
                ),
                # Auto-refresh interval
                dcc.Interval(
                    id=f"{self.component_id}-refresh-interval",
                    interval=self.refresh_interval,
                    n_intervals=0,
                ),
                # Store for snapshots list
                dcc.Store(id=f"{self.component_id}-snapshots-store", data={"snapshots": []}),
                # Store for selected snapshot ID
                dcc.Store(id=f"{self.component_id}-selected-id", data=None),
                # Store for triggering table refresh after create (P3-1)
                dcc.Store(id=f"{self.component_id}-refresh-trigger", data=0),
                # Store for snapshot operation pending confirmation (CAN-015e
                # generalization of the P3-2 restore-pending-id; now holds a
                # ``{"id": ..., "operation": ...}`` dict, falling back to a
                # bare id string for legacy callers).
                dcc.Store(id=f"{self.component_id}-restore-pending-id", data=None),
                # CAN-015e (B-5): right-click context menu trigger. The
                # clientside ``snapshot_context_menu.js`` writes
                # ``{"snapshot_id": ..., "operation": ...}`` here when the
                # user picks an item from the row's right-click menu;
                # ``open_snapshot_op_modal`` watches this Store as a
                # second Input alongside the dropdown-item pattern.
                dcc.Store(id=f"{self.component_id}-context-menu-trigger", data=None),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "1000px", "margin": "0 auto"},
        )

    def _create_snapshot_handler(self, name: str = None, description: str = None) -> Dict[str, Any]:
        """
        Create a new snapshot via the backend API.

        Args:
            name: Optional custom name for the snapshot
            description: Optional description for the snapshot

        Returns:
            Dict with created snapshot data or error information
        """
        try:
            params = {}
            if name:
                params["name"] = name
            if description:
                params["description"] = description

            resp = requests.post(
                f"{self._api_base_url}/api/v1/snapshots",
                params=params,
                timeout=self.api_timeout + 3,  # Allow extra time for creation
            )

            if resp.status_code == 201:
                data = resp.json()
                self.logger.info(f"Created snapshot: {data.get('id')}")
                return {"success": True, "snapshot": data, "message": data.get("message", "Snapshot created")}
            else:
                error_detail = resp.json().get("detail", "Unknown error") if resp.text else f"HTTP {resp.status_code}"
                self.logger.warning(f"Failed to create snapshot: {error_detail}")
                return {"success": False, "error": error_detail}

        except requests.exceptions.Timeout:
            self.logger.warning("Create snapshot request timed out")
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.logger.warning("Cannot connect to snapshot API for create")
            return {"success": False, "error": "Service unavailable"}
        except Exception as e:
            self.logger.warning(f"Failed to create snapshot: {e}")
            return {"success": False, "error": str(e)}

    def _fetch_snapshots_handler(self, n_intervals: int = 0) -> Dict[str, Any]:
        """
        Fetch snapshots list from backend API.

        Args:
            n_intervals: Interval count (unused, for callback compatibility)

        Returns:
            Dict with 'snapshots' list and optional 'message'
        """
        try:
            return dict(self._parse_snapshots_response())
        except requests.exceptions.Timeout:
            self.logger.warning("Snapshots API request timed out")
            return {"snapshots": [], "message": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.logger.warning("Cannot connect to snapshots API")
            return {"snapshots": [], "message": "Service unavailable"}
        except Exception as e:
            self.logger.warning(f"Failed to fetch snapshots: {e}")
            return {"snapshots": [], "message": "Snapshot service unavailable"}

    def _parse_snapshots_response(self):
        """
        Parse snapshots list from backend API.

        Returns:
            Dict with 'snapshots' list and optional 'message'
        """
        self.logger.info("Fetching snapshots from API")
        resp = requests.get(
            f"{self._api_base_url}/api/v1/snapshots",
            timeout=self.api_timeout,
        )
        if resp.status_code != 200:
            self.logger.warning(f"Snapshots API returned status {resp.status_code}")
            return {"snapshots": [], "message": f"API error {resp.status_code}"}
        data = resp.json()
        snapshots = data.get("snapshots", [])
        message = data.get("message")
        return {"snapshots": snapshots, "message": message}

    def _fetch_snapshot_detail_handler(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Fetch details for a specific snapshot.

        Args:
            snapshot_id: The snapshot ID to fetch details for

        Returns:
            Snapshot detail dict or empty dict on failure
        """
        if not snapshot_id:
            return {}

        try:
            resp = requests.get(
                f"{self._api_base_url}/api/v1/snapshots/{snapshot_id}",
                timeout=self.api_timeout,
            )
            if resp.status_code != 200:
                self.logger.warning(f"Snapshot detail API returned status {resp.status_code}")
                return {}

            return dict(resp.json())

        except requests.exceptions.Timeout:
            self.logger.warning(f"Snapshot detail request timed out for {snapshot_id}")
            return {}
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"Cannot connect to snapshot detail API for {snapshot_id}")
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch snapshot detail for {snapshot_id}: {e}")
            return {}

    # CAN-015e (Phase 6E Sprint B B-5): per-operation modal-body
    # descriptions. Surfaced to the user in the confirmation modal so
    # they understand which of the four semantically-distinct snapshot
    # operations is about to fire (Restore / Replay / Resume / Retrain).
    _OP_DESCRIPTIONS: Dict[str, str] = {
        "restore": "Load this snapshot for inspection and modification. Training is NOT started — invoke Retrain or Resume to begin a training run.",
        "replay": "Start a read-only playback session of this snapshot's training history. Use the replay player controls to scrub through metric and topology evolution.",
        "resume": "Continue training from where this snapshot left off. The pre-resume history is preserved as read-only; new training extends past the snapshot's terminal epoch.",
        "retrain": "Use this snapshot's weights and topology as a starting point for a fresh training run. All history / counters / auto-snap-best ratchet are reset to time index 0.",
    }
    _OP_CONFIRM_LABELS: Dict[str, str] = {
        "restore": "Restore",
        "replay": "Start Replay",
        "resume": "Resume",
        "retrain": "Retrain",
    }

    def _build_op_confirm_body(self, snapshot_id: str, operation: str):
        """Build the modal body for a snapshot-operation confirmation."""
        return html.Div(
            [
                html.P(f"Confirm {operation.capitalize()} of snapshot:"),
                html.P(html.Strong(snapshot_id), style={"fontFamily": "monospace", "fontSize": "1.1rem"}),
                html.P(self._OP_DESCRIPTIONS.get(operation, ""), style={"fontSize": "0.9rem"}),
                html.P(
                    "⚠️ Training must be paused or stopped before any snapshot operation.",
                    style={"color": "var(--bs-warning-text-emphasis, #856404)", "fontSize": "0.85rem"},
                ),
            ]
        )

    def _invoke_snapshot_op_handler(self, snapshot_id: str, operation: str) -> Dict[str, Any]:
        """Invoke one of the four snapshot operation endpoints (CAN-015e).

        Routes to the canopy backend's
        ``/api/v1/snapshots/{id}/{operation}`` proxy which forwards to
        the cascor backend. ``operation`` must be one of ``restore`` /
        ``replay`` / ``resume`` / ``retrain``.
        """
        if not snapshot_id:
            return {"success": False, "error": "No snapshot ID provided"}
        if operation not in ("restore", "replay", "resume", "retrain"):
            return {"success": False, "error": f"Unknown operation: {operation!r}"}

        try:
            resp = requests.post(
                f"{self._api_base_url}/api/v1/snapshots/{snapshot_id}/{operation}",
                timeout=self.api_timeout + 5,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.logger.info("Snapshot %s %sd: %s", snapshot_id, operation, data)
                return {"success": True, "data": data, "message": data.get("message")}
            if resp.status_code == 409:
                error_detail = resp.json().get("detail", "Conflict — training may be running")
                self.logger.warning("Cannot %s snapshot %s: %s", operation, snapshot_id, error_detail)
                return {"success": False, "error": error_detail}
            if resp.status_code == 404:
                self.logger.warning("Snapshot not found: %s", snapshot_id)
                return {"success": False, "error": "Snapshot not found"}
            if resp.status_code == 501:
                error_detail = resp.json().get("detail", "Operation not supported in this mode")
                self.logger.warning("Snapshot %s %s rejected: %s", snapshot_id, operation, error_detail)
                return {"success": False, "error": error_detail}
            error_detail = resp.json().get("detail", "Unknown error") if resp.text else f"HTTP {resp.status_code}"
            self.logger.warning("Failed to %s snapshot %s: %s", operation, snapshot_id, error_detail)
            return {"success": False, "error": error_detail}
        except requests.exceptions.Timeout:
            self.logger.warning("Snapshot %s request timed out (op=%s)", snapshot_id, operation)
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.logger.warning("Cannot connect to snapshot API (op=%s)", operation)
            return {"success": False, "error": "Service unavailable"}
        except Exception as e:
            self.logger.warning("Snapshot %s failed (op=%s): %s", snapshot_id, operation, e)
            return {"success": False, "error": str(e)}

    def _restore_snapshot_handler(self, snapshot_id: str) -> Dict[str, Any]:
        """CAN-015e backward-compat shim — keep the legacy name alive
        for any code path that still calls it directly. Forwards to
        ``_invoke_snapshot_op_handler`` with operation=``restore``."""
        return self._invoke_snapshot_op_handler(snapshot_id, "restore")

    def _fetch_history_handler(self, limit: int = 50) -> Dict[str, Any]:
        """
        Fetch snapshot history from backend API (P3-3).

        Args:
            limit: Maximum number of history entries to fetch

        Returns:
            Dict with 'history' list and optional 'message'
        """
        try:
            resp = requests.get(
                f"{self._api_base_url}/api/v1/snapshots/history",
                params={"limit": limit},
                timeout=self.api_timeout,
            )

            if resp.status_code != 200:
                self.logger.warning(f"History API returned status {resp.status_code}")
                return {"history": [], "message": f"API error {resp.status_code}"}

            data = resp.json()
            return {"history": data.get("history", []), "total": data.get("total", 0), "message": data.get("message")}

        except requests.exceptions.Timeout:
            self.logger.warning("History API request timed out")
            return {"history": [], "message": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.logger.warning("Cannot connect to history API")
            return {"history": [], "message": "Service unavailable"}
        except Exception as e:
            self.logger.warning(f"Failed to fetch history: {e}")
            return {"history": [], "message": "History service unavailable"}

    def _format_size(self, size_bytes: int) -> str:
        """
        Format byte size to human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.5 MB")
        """
        if not size_bytes or size_bytes <= 0:
            return "-"

        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _format_timestamp(self, timestamp: str) -> str:
        """
        Format ISO timestamp to readable format.

        Args:
            timestamp: ISO 8601 timestamp string

        Returns:
            Formatted timestamp string
        """
        if not timestamp:
            return "-"

        # Remove 'Z' suffix and format
        clean_ts = timestamp.rstrip("Z")
        # Return as-is for now; could add more formatting later
        return clean_ts.replace("T", " ")

    def register_callbacks(self, app):
        """
        Register Dash callbacks for HDF5 snapshots panel.

        Args:
            app: Dash application instance
        """

        # Callback: Create Snapshot button → create snapshot and trigger refresh (P3-1)
        @app.callback(
            Output(f"{self.component_id}-create-status", "children"),
            Output(f"{self.component_id}-refresh-trigger", "data"),
            Output(f"{self.component_id}-create-name", "value"),
            Output(f"{self.component_id}-create-description", "value"),
            Input(f"{self.component_id}-create-button", "n_clicks"),
            State(f"{self.component_id}-create-name", "value"),
            State(f"{self.component_id}-create-description", "value"),
            State(f"{self.component_id}-refresh-trigger", "data"),
            prevent_initial_call=True,
        )
        def create_snapshot(n_clicks, name, description, current_trigger):
            """Handle create snapshot button click."""
            if not n_clicks:
                return "", current_trigger or 0, name, description

            result = self._create_snapshot_handler(name=name, description=description)

            if result.get("success"):
                snapshot = result.get("snapshot", {})
                snapshot_id = snapshot.get("id", "")
                message = result.get("message", "Snapshot created successfully")

                status_content = html.Div(
                    [
                        html.Span("✅ ", style={"color": "#28a745"}),
                        html.Span(f"{message}: "),
                        html.Strong(snapshot_id),
                    ],
                    style={"color": "#28a745"},
                )

                # Increment trigger to refresh table, clear inputs
                return status_content, (current_trigger or 0) + 1, "", ""
            else:
                error = result.get("error", "Unknown error")
                status_content = html.Div(
                    [
                        html.Span("❌ ", style={"color": "#dc3545"}),
                        html.Span(f"Failed to create snapshot: {error}"),
                    ],
                    style={"color": "#dc3545"},
                )
                # Don't clear inputs on error, keep trigger unchanged
                return status_content, current_trigger or 0, name, description

        # Callback: Refresh / auto-refresh → update snapshots table
        @app.callback(
            Output(f"{self.component_id}-table-body", "children"),
            Output(f"{self.component_id}-status", "children"),
            Output(f"{self.component_id}-empty-state", "style"),
            Output(f"{self.component_id}-snapshots-store", "data"),
            Input(f"{self.component_id}-refresh-interval", "n_intervals"),
            Input(f"{self.component_id}-refresh-button", "n_clicks"),
            Input(f"{self.component_id}-refresh-trigger", "data"),
            prevent_initial_call=False,
        )
        def update_snapshots_table(n_intervals, n_clicks, refresh_trigger):
            """Update the snapshots table with current data."""
            result = self._fetch_snapshots_handler(n_intervals)
            snapshots = result.get("snapshots", [])
            message = result.get("message")

            # Build table rows
            rows: List[html.Tr] = []
            for snapshot in snapshots:
                snapshot_id = snapshot.get("id", "")
                name = snapshot.get("name") or snapshot_id
                timestamp = self._format_timestamp(snapshot.get("timestamp", ""))
                size = self._format_size(snapshot.get("size_bytes", 0))

                # CAN-015e (Phase 6E Sprint B B-5): the per-row "Restore"
                # button is replaced with a dropdown exposing all four
                # snapshot operations from the cascor backend (Restore /
                # Replay / Resume / Retrain). The legacy
                # ``-restore-btn`` id is preserved as a hidden button so
                # the existing P3-2 confirmation-modal callback graph
                # keeps wiring up — it now fires from the dropdown items
                # via clientside id-pattern matching on
                # ``-snapshot-op-btn``. Each dropdown item carries a
                # composite id ``{type, index, operation}`` so a single
                # pattern-matching callback can route to the right
                # endpoint without duplicating the open-modal logic per
                # operation.
                rows.append(
                    html.Tr(
                        [
                            html.Td(name, style={"padding": "10px", "borderBottom": "1px solid var(--border-color, #dee2e6)"}),
                            html.Td(timestamp, style={"padding": "10px", "borderBottom": "1px solid var(--border-color, #dee2e6)"}),
                            html.Td(size, style={"padding": "10px", "borderBottom": "1px solid var(--border-color, #dee2e6)"}),
                            html.Td(
                                html.Div(
                                    [
                                        dbc.Button(
                                            "View Details",
                                            id={"type": f"{self.component_id}-view-btn", "index": snapshot_id},
                                            size="sm",
                                            color="info",
                                            outline=True,
                                            className="me-1",
                                        ),
                                        dbc.DropdownMenu(
                                            label="Load ▼",
                                            size="sm",
                                            color="warning",
                                            # ``outline=True`` matches the legacy Restore button styling.
                                            toggle_style={"borderColor": "#ffc107", "color": "#ffc107", "backgroundColor": "transparent"},
                                            children=[
                                                dbc.DropdownMenuItem(
                                                    [html.Span("🔄 ", className="me-1"), "Restore — load for inspection"],
                                                    id={"type": f"{self.component_id}-snapshot-op-btn", "index": snapshot_id, "op": "restore"},
                                                    n_clicks=0,
                                                ),
                                                dbc.DropdownMenuItem(
                                                    [html.Span("▶️ ", className="me-1"), "Replay — read-only playback"],
                                                    id={"type": f"{self.component_id}-snapshot-op-btn", "index": snapshot_id, "op": "replay"},
                                                    n_clicks=0,
                                                ),
                                                dbc.DropdownMenuItem(
                                                    [html.Span("⏯️ ", className="me-1"), "Resume — continue training"],
                                                    id={"type": f"{self.component_id}-snapshot-op-btn", "index": snapshot_id, "op": "resume"},
                                                    n_clicks=0,
                                                ),
                                                dbc.DropdownMenuItem(
                                                    [html.Span("🔁 ", className="me-1"), "Retrain — fresh run from these weights"],
                                                    id={"type": f"{self.component_id}-snapshot-op-btn", "index": snapshot_id, "op": "retrain"},
                                                    n_clicks=0,
                                                ),
                                            ],
                                        ),
                                    ],
                                    # ``data-snapshot-id`` exposes the row's snapshot ID to
                                    # the right-click context-menu JS handler (B-5: third UX
                                    # entry point per design doc §7).
                                    **{"data-snapshot-id": snapshot_id, "data-snapshot-row": "1"},
                                    style={"display": "flex", "gap": "5px"},
                                ),
                                style={"padding": "10px", "borderBottom": "1px solid var(--border-color, #dee2e6)"},
                            ),
                        ]
                    )
                )

            # Status text
            if snapshots:
                status_text = f"{len(snapshots)} snapshot(s) found"
                if message:
                    status_text += f" • {message}"
                empty_style = {"display": "none"}
            else:
                status_text = message or "No snapshots available"
                empty_style = {
                    "marginTop": "15px",
                    "color": "var(--text-muted)",
                    "fontSize": "0.9rem",
                    "textAlign": "center",
                    "padding": "20px",
                }

            return rows, status_text, empty_style, {"snapshots": snapshots}

        # Callback: View button click → update selected snapshot ID
        @app.callback(
            Output(f"{self.component_id}-selected-id", "data"),
            Input({"type": f"{self.component_id}-view-btn", "index": ALL}, "n_clicks"),
            State({"type": f"{self.component_id}-view-btn", "index": ALL}, "id"),
            prevent_initial_call=True,
        )
        def select_snapshot(n_clicks_list, ids):
            """Handle snapshot selection from table."""
            if not n_clicks_list or not any(n_clicks_list):
                return None

            ctx = callback_context
            if not ctx.triggered:
                return None

            # Find which button was clicked
            triggered = ctx.triggered[0]
            if not triggered.get("value"):
                return None

            # Extract the snapshot ID from the triggered button
            prop_id = triggered.get("prop_id", "")
            if not prop_id:
                return None

            # Parse the pattern-matching ID
            # Format: '{"index":"snapshot_id","type":"component-id-view-btn"}.n_clicks'
            try:
                import json

                id_str = prop_id.rsplit(".", 1)[0]
                id_dict = json.loads(id_str)
                return id_dict.get("index")
            except (json.JSONDecodeError, IndexError):
                # Fallback: find the button with highest n_clicks
                max_clicks = 0
                selected_id = None
                for n, id_obj in zip(n_clicks_list, ids, strict=True):
                    if n and n > max_clicks:
                        max_clicks = n
                        selected_id = id_obj.get("index")
                return selected_id

        # Callback: Selected ID → update detail panel
        @app.callback(
            Output(f"{self.component_id}-detail-panel", "children"),
            Input(f"{self.component_id}-selected-id", "data"),
            prevent_initial_call=True,
        )
        def update_detail_panel(selected_id):
            """Display snapshot details for selected snapshot."""
            if not selected_id:
                return html.P(
                    "Select a snapshot from the table above to view its details.",
                    style={"color": "var(--text-muted)", "fontStyle": "italic"},
                )

            detail = self._fetch_snapshot_detail_handler(selected_id)

            if not detail:
                return html.Div(
                    [
                        html.P(
                            f"Failed to load details for snapshot '{selected_id}'.",
                            style={"color": "#dc3545"},
                        ),
                        html.P(
                            "The snapshot may no longer exist or the service may be unavailable.",
                            style={"color": "var(--text-muted)", "fontSize": "0.9rem"},
                        ),
                    ]
                )

            # Build detail display
            items = [
                html.Div(
                    [
                        html.Strong("ID: "),
                        html.Span(detail.get("id", ""), style={"fontFamily": "monospace"}),
                    ],
                    style={"marginBottom": "8px"},
                ),
                html.Div(
                    [
                        html.Strong("Name: "),
                        html.Span(detail.get("name", "")),
                    ],
                    style={"marginBottom": "8px"},
                ),
                html.Div(
                    [
                        html.Strong("Timestamp: "),
                        html.Span(self._format_timestamp(detail.get("timestamp", ""))),
                    ],
                    style={"marginBottom": "8px"},
                ),
                html.Div(
                    [
                        html.Strong("Size: "),
                        html.Span(self._format_size(detail.get("size_bytes", 0))),
                    ],
                    style={"marginBottom": "8px"},
                ),
            ]

            # Add path if available
            if detail.get("path"):
                items.append(
                    html.Div(
                        [
                            html.Strong("Path: "),
                            html.Span(detail.get("path"), style={"fontFamily": "monospace", "fontSize": "0.9rem"}),
                        ],
                        style={"marginBottom": "8px"},
                    )
                )

            # Add description if available
            if detail.get("description"):
                items.append(
                    html.Div(
                        [
                            html.Strong("Description: "),
                            html.Span(detail.get("description")),
                        ],
                        style={"marginBottom": "8px"},
                    )
                )

            # Add attributes section if available
            attrs = detail.get("attributes")
            if attrs and isinstance(attrs, dict):
                items.append(html.Hr())
                items.append(html.H6("HDF5 Attributes", style={"color": "var(--header-color)", "marginBottom": "10px"}))
                attr_items = [
                    html.Li(
                        [html.Strong(f"{k}: "), html.Span(str(v))],
                        style={"marginBottom": "4px"},
                    )
                    for k, v in attrs.items()
                ]
                items.append(html.Ul(attr_items, style={"listStyleType": "disc", "paddingLeft": "20px", "fontSize": "0.9rem"}))

            return html.Div(items)

        # Callback: Restore button click → open modal with snapshot ID (P3-2)
        @app.callback(
            # CAN-015e (B-5): the open-modal callback now listens to the
            # generalized ``-snapshot-op-btn`` pattern, which carries the
            # ``op`` (one of ``restore`` / ``replay`` / ``resume`` /
            # ``retrain``) in its composite id. Same callback graph,
            # broader operation surface. Right-click context menu (third
            # entry point per design doc §7) writes to a separate Store
            # that flows into a sibling callback below.
            Output(f"{self.component_id}-restore-modal", "is_open"),
            Output(f"{self.component_id}-restore-modal-body", "children"),
            Output(f"{self.component_id}-restore-pending-id", "data"),
            Input({"type": f"{self.component_id}-snapshot-op-btn", "index": ALL, "op": ALL}, "n_clicks"),
            Input(f"{self.component_id}-context-menu-trigger", "data"),
            State(f"{self.component_id}-restore-modal", "is_open"),
            prevent_initial_call=True,
        )
        def open_snapshot_op_modal(_n_clicks_list, ctx_trigger, _is_open):
            """Open the snapshot-operation confirmation modal.

            Consolidated entry point for all three UX surfaces:
            - dropdown items on each snapshot row (the
              ``-snapshot-op-btn`` pattern-matched Inputs)
            - right-click context menu items (writes to
              ``-context-menu-trigger`` Store via clientside JS)

            Two-step modal selector: show a per-operation message, ask
            for confirmation, fire on confirm. The pending_id store
            grows to include the operation so the confirm callback
            knows which endpoint to call.
            """
            ctx = callback_context
            if not ctx.triggered:
                return False, "", None

            triggered = ctx.triggered[0]
            if not triggered.get("value"):
                return False, "", None

            prop_id = triggered.get("prop_id", "")
            if not prop_id:
                return False, "", None

            import json

            snapshot_id: str | None = None
            operation: str | None = None

            # Branch on which Input fired. The pattern-matched dropdown
            # items have prop_ids like ``{"index": "...", ...}.n_clicks``
            # while the context-menu Store fires with ``...-trigger.data``.
            if prop_id.endswith("-context-menu-trigger.data"):
                payload = triggered.get("value")
                if isinstance(payload, dict):
                    snapshot_id = payload.get("snapshot_id")
                    operation = payload.get("operation")
            else:
                with contextlib.suppress(json.JSONDecodeError, IndexError):
                    id_str = prop_id.rsplit(".", 1)[0]
                    id_dict = json.loads(id_str)
                    snapshot_id = id_dict.get("index")
                    operation = id_dict.get("op")

            if not snapshot_id or operation not in ("restore", "replay", "resume", "retrain"):
                return False, "", None

            modal_body = self._build_op_confirm_body(snapshot_id, operation)
            return True, modal_body, {"id": snapshot_id, "operation": operation}

        # Callback: Modal cancel button → close modal (P3-2)
        @app.callback(
            #     Output(f"{self.component_id}-restore-modal", "is_open", allow_duplicate=True),
            #     Input(f"{self.component_id}-restore-cancel", "n_clicks"),
            #     prevent_initial_call=True,
            # )
            Output(f"{self.component_id}-restore-modal", "is_open", allow_duplicate=True),
            Input(f"{self.component_id}-restore-cancel", "n_clicks"),
            prevent_initial_call=True,
        )
        def close_restore_modal(n_clicks):
            """Close restore modal on cancel."""
            # if n_clicks:
            #     return False
            # return dash.no_update
            return False if n_clicks else dash.no_update

        # Callback: Modal confirm button → perform the chosen snapshot operation
        # (CAN-015e generalization of the original P3-2 restore confirm).
        # CAN-015f (B-6): on a successful ``replay`` op, also populate the
        # ``replay-player-session`` Store and switch the active tab to
        # the Replay tab so the player UI is immediately interactive.
        @app.callback(
            Output(f"{self.component_id}-restore-modal", "is_open", allow_duplicate=True),
            Output(f"{self.component_id}-restore-status", "children"),
            Output(f"{self.component_id}-refresh-trigger", "data", allow_duplicate=True),
            Output("replay-player-session", "data", allow_duplicate=True),
            Output("visualization-tabs", "active_tab", allow_duplicate=True),
            Input(f"{self.component_id}-restore-confirm", "n_clicks"),
            State(f"{self.component_id}-restore-pending-id", "data"),
            State(f"{self.component_id}-refresh-trigger", "data"),
            prevent_initial_call=True,
        )
        def confirm_snapshot_op(n_clicks, pending, current_trigger):
            """Perform the chosen snapshot operation when confirmed.

            ``pending`` is the dict written by ``open_snapshot_op_modal``
            with keys ``id`` and ``operation``. Operations:
            ``restore`` / ``replay`` / ``resume`` / ``retrain``. The
            handler routes to the per-operation backend endpoint.
            """
            if not n_clicks or not pending:
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

            if isinstance(pending, dict):
                snapshot_id = pending.get("id")
                operation = pending.get("operation", "restore")
            else:
                # Backward compat: older state had a bare snapshot id string.
                snapshot_id = pending
                operation = "restore"

            if not snapshot_id or operation not in ("restore", "replay", "resume", "retrain"):
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

            result = self._invoke_snapshot_op_handler(snapshot_id, operation)
            verb = {"restore": "restored", "replay": "replay started", "resume": "resumed", "retrain": "ready to retrain"}[operation]

            if result.get("success"):
                message = result.get("message") or f"Snapshot {verb}"
                status_content = html.Div(
                    [
                        html.Span("✅ ", style={"color": "#28a745"}),
                        html.Span(f"{message}"),
                    ],
                    style={"color": "var(--success-color, #28a745)", "padding": "10px", "backgroundColor": "var(--bs-success-bg-subtle, #d4edda)", "borderRadius": "5px"},
                )
                # CAN-015f: hand off to the replay player on a successful
                # ``replay`` op. The cascor /replay response contains the
                # ``data`` block with snapshot_window/time_index/fsm_state
                # which the player consumes directly.
                replay_session: Any = dash.no_update
                active_tab: Any = dash.no_update
                if operation == "replay":
                    payload = result.get("data") or {}
                    inner = payload.get("data", payload)
                    if isinstance(inner, dict):
                        session = dict(inner)
                        session.setdefault("snapshot_id", snapshot_id)
                        session.setdefault("speed", 1.0)
                        session.setdefault("playing", False)
                        replay_session = session
                        active_tab = "replay"
                return False, status_content, (current_trigger or 0) + 1, replay_session, active_tab

            error = result.get("error", "Unknown error")
            status_content = html.Div(
                [
                    html.Span("❌ ", style={"color": "#dc3545"}),
                    html.Span(f"Failed ({operation}): {error}"),
                ],
                style={"color": "var(--danger-color, #dc3545)", "padding": "10px", "backgroundColor": "var(--bs-danger-bg-subtle, #f8d7da)", "borderRadius": "5px"},
            )
            return False, status_content, current_trigger or 0, dash.no_update, dash.no_update

        # Callback: Toggle history collapse (P3-3)
        @app.callback(
            Output(f"{self.component_id}-history-collapse", "is_open"),
            Output(f"{self.component_id}-history-toggle-icon", "children"),
            Output(f"{self.component_id}-history-content", "children"),
            Input(f"{self.component_id}-history-toggle", "n_clicks"),
            State(f"{self.component_id}-history-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_history(n_clicks, is_open):
            """Toggle history section and load history when opening."""
            if not n_clicks:
                return dash.no_update, dash.no_update, dash.no_update

            new_is_open = not is_open
            icon = " ▲" if new_is_open else " ▼"

            if new_is_open:
                # Fetch history when opening
                result = self._fetch_history_handler(limit=20)
                history = result.get("history", [])

                if not history:
                    content = html.P(
                        "No snapshot activity recorded yet.",
                        style={"color": "var(--text-muted)", "fontStyle": "italic"},
                    )
                else:
                    # Build history entries
                    entries = []
                    for entry in history:
                        action = entry.get("action", "unknown")
                        snapshot_id = entry.get("snapshot_id", "")
                        timestamp = entry.get("timestamp", "")
                        message = entry.get("message", "")

                        # Format timestamp
                        ts_formatted = self._format_timestamp(timestamp) if timestamp else ""

                        # Action icon and color
                        action_config = {
                            "create": ("📸", "#28a745"),
                            "restore": ("🔄", "#ffc107"),
                            "delete": ("🗑️", "#dc3545"),
                        }
                        action_icon, action_color = action_config.get(action, ("•", "var(--text-muted)"))

                        entries.append(
                            html.Div(
                                [
                                    html.Span(
                                        f"{action_icon} {action.upper()}",
                                        style={
                                            "fontWeight": "bold",
                                            "color": action_color,
                                            "marginRight": "10px",
                                            "minWidth": "100px",
                                            "display": "inline-block",
                                        },
                                    ),
                                    html.Span(
                                        snapshot_id,
                                        style={"fontFamily": "monospace", "marginRight": "10px"},
                                    ),
                                    html.Span(
                                        ts_formatted,
                                        style={"color": "var(--text-muted)", "fontSize": "0.85rem", "marginRight": "10px"},
                                    ),
                                    html.Span(
                                        message,
                                        style={"color": "var(--text-color)", "fontSize": "0.9rem"},
                                    ),
                                ],
                                style={
                                    "padding": "8px 0",
                                    "borderBottom": "1px solid #eee",
                                },
                            )
                        )

                    content = html.Div(entries)

                return True, icon, content
            else:
                return False, icon, "Loading history..."

        # Expose callback functions for unit testing
        self._cb_create_snapshot = create_snapshot
        self._cb_update_snapshots_table = update_snapshots_table
        self._cb_select_snapshot = select_snapshot
        self._cb_update_detail_panel = update_detail_panel
        self._cb_open_restore_modal = open_snapshot_op_modal
        self._cb_open_snapshot_op_modal = open_snapshot_op_modal
        self._cb_close_restore_modal = close_restore_modal
        self._cb_confirm_restore = confirm_snapshot_op
        self._cb_confirm_snapshot_op = confirm_snapshot_op
        self._cb_toggle_history = toggle_history

        self.logger.debug(f"Callbacks registered for {self.component_id}")
