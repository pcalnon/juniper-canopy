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

from ..base_component import BaseComponent

# Default refresh interval in milliseconds
DEFAULT_REFRESH_INTERVAL_MS = 10000  # 10 seconds

# Default API base URL
DEFAULT_API_BASE_URL = "http://localhost:8050"


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
                # Header with title and controls
                html.Div(
                    [
                        html.H3(
                            "HDF5 Snapshots",
                            style={"display": "inline-block", "marginRight": "20px", "color": "#2c3e50"},
                        ),
                        dbc.Button(
                            "🔄 Refresh",
                            id=f"{self.component_id}-refresh-button",
                            color="primary",
                            size="sm",
                            className="me-2",
                        ),
                        html.Span(
                            id=f"{self.component_id}-status",
                            children="Loading snapshots...",
                            style={"fontSize": "0.9rem", "color": "#6c757d", "marginLeft": "10px"},
                        ),
                    ],
                    style={"marginBottom": "15px"},
                ),
                # Create Snapshot section (P3-1)
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Create New Snapshot", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
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
                    style={"fontSize": "14px", "color": "#6c757d", "marginBottom": "20px"},
                ),
                html.Hr(),
                # Snapshots table card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Available Snapshots", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
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
                                                style={"backgroundColor": "#e9ecef"},
                                            )
                                        ),
                                        html.Tbody(id=f"{self.component_id}-table-body"),
                                    ],
                                    id=f"{self.component_id}-table",
                                    style={
                                        "width": "100%",
                                        "borderCollapse": "collapse",
                                        "border": "1px solid #dee2e6",
                                    },
                                ),
                                # Empty state message
                                html.Div(
                                    id=f"{self.component_id}-empty-state",
                                    children="No snapshots available.",
                                    style={
                                        "marginTop": "15px",
                                        "color": "#6c757d",
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
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            id=f"{self.component_id}-detail-panel",
                            children=html.P(
                                "Select a snapshot from the table above to view its details.",
                                style={"color": "#6c757d", "fontStyle": "italic"},
                            ),
                        ),
                    ],
                    className="mb-3",
                ),
                # Restore confirmation modal (P3-2)
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Confirm Restore")),
                        dbc.ModalBody(
                            id=f"{self.component_id}-restore-modal-body",
                            children="Are you sure you want to restore from this snapshot?",
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
                                    "Restore",
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
                                style={"color": "#2c3e50", "fontWeight": "500"},
                            ),
                            style={"backgroundColor": "#f8f9fa"},
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
                # Store for snapshot ID pending restore (P3-2)
                dcc.Store(id=f"{self.component_id}-restore-pending-id", data=None),
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
                f"{DEFAULT_API_BASE_URL}/api/v1/snapshots",
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
            return self._parse_snapshots_response()
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
            "http://localhost:8050/api/v1/snapshots",
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
                f"http://localhost:8050/api/v1/snapshots/{snapshot_id}",
                timeout=self.api_timeout,
            )
            if resp.status_code != 200:
                self.logger.warning(f"Snapshot detail API returned status {resp.status_code}")
                return {}

            return resp.json()

        except requests.exceptions.Timeout:
            self.logger.warning(f"Snapshot detail request timed out for {snapshot_id}")
            return {}
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"Cannot connect to snapshot detail API for {snapshot_id}")
            return {}
        except Exception as e:
            self.logger.warning(f"Failed to fetch snapshot detail for {snapshot_id}: {e}")
            return {}

    def _restore_snapshot_handler(self, snapshot_id: str) -> Dict[str, Any]:
        """
        Restore from a snapshot via the backend API (P3-2).

        Args:
            snapshot_id: The snapshot ID to restore from

        Returns:
            Dict with restore result or error information
        """
        if not snapshot_id:
            return {"success": False, "error": "No snapshot ID provided"}

        try:
            resp = requests.post(
                f"{DEFAULT_API_BASE_URL}/api/v1/snapshots/{snapshot_id}/restore",
                timeout=self.api_timeout + 5,  # Allow extra time for restore
            )

            if resp.status_code == 200:
                data = resp.json()
                self.logger.info(f"Restored from snapshot: {snapshot_id}")
                return {"success": True, "data": data, "message": data.get("message", "Restored successfully")}
            elif resp.status_code == 409:
                error_detail = resp.json().get("detail", "Training is running")
                self.logger.warning(f"Cannot restore: {error_detail}")
                return {"success": False, "error": error_detail}
            elif resp.status_code == 404:
                self.logger.warning(f"Snapshot not found: {snapshot_id}")
                return {"success": False, "error": "Snapshot not found"}
            else:
                error_detail = resp.json().get("detail", "Unknown error") if resp.text else f"HTTP {resp.status_code}"
                self.logger.warning(f"Failed to restore snapshot: {error_detail}")
                return {"success": False, "error": error_detail}

        except requests.exceptions.Timeout:
            self.logger.warning("Restore snapshot request timed out")
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.logger.warning("Cannot connect to snapshot API for restore")
            return {"success": False, "error": "Service unavailable"}
        except Exception as e:
            self.logger.warning(f"Failed to restore snapshot: {e}")
            return {"success": False, "error": str(e)}

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
                f"{DEFAULT_API_BASE_URL}/api/v1/snapshots/history",
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

                rows.append(
                    html.Tr(
                        [
                            html.Td(name, style={"padding": "10px", "borderBottom": "1px solid #dee2e6"}),
                            html.Td(timestamp, style={"padding": "10px", "borderBottom": "1px solid #dee2e6"}),
                            html.Td(size, style={"padding": "10px", "borderBottom": "1px solid #dee2e6"}),
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
                                        dbc.Button(
                                            "🔄 Restore",
                                            id={"type": f"{self.component_id}-restore-btn", "index": snapshot_id},
                                            size="sm",
                                            color="warning",
                                            outline=True,
                                        ),
                                    ],
                                    style={"display": "flex", "gap": "5px"},
                                ),
                                style={"padding": "10px", "borderBottom": "1px solid #dee2e6"},
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
                    "color": "#6c757d",
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
                    style={"color": "#6c757d", "fontStyle": "italic"},
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
                            style={"color": "#6c757d", "fontSize": "0.9rem"},
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
                items.append(html.H6("HDF5 Attributes", style={"color": "#2c3e50", "marginBottom": "10px"}))
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
            #     Output(f"{self.component_id}-restore-modal", "is_open"),
            #     Output(f"{self.component_id}-restore-modal-body", "children"),
            #     Output(f"{self.component_id}-restore-pending-id", "data"),
            #     Input({"type": f"{self.component_id}-restore-btn", "index": ALL}, "n_clicks"),
            #     State({"type": f"{self.component_id}-restore-btn", "index": ALL}, "id"),
            #     State(f"{self.component_id}-restore-modal", "is_open"),
            #     prevent_initial_call=True,
            # )
            Output(f"{self.component_id}-restore-modal", "is_open"),
            Output(f"{self.component_id}-restore-modal-body", "children"),
            Output(f"{self.component_id}-restore-pending-id", "data"),
            Input({"type": f"{self.component_id}-restore-btn", "index": ALL}, "n_clicks"),
            State({"type": f"{self.component_id}-restore-btn", "index": ALL}, "id"),
            State(f"{self.component_id}-restore-modal", "is_open"),
            prevent_initial_call=True,
        )
        def open_restore_modal(n_clicks_list, ids, is_open):
            """Open restore confirmation modal when Restore button clicked."""
            if not n_clicks_list or not any(n_clicks_list):
                return False, "", None

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

            with contextlib.suppress(json.JSONDecodeError, IndexError):
                id_str = prop_id.rsplit(".", 1)[0]
                id_dict = json.loads(id_str)
                snapshot_id = id_dict.get("index")
                if snapshot_id:
                    modal_body = html.Div(
                        [
                            html.P("Are you sure you want to restore from snapshot:"),
                            html.P(
                                html.Strong(snapshot_id),
                                style={
                                    "fontFamily": "monospace",
                                    "fontSize": "1.1rem",
                                },
                            ),
                            html.P(
                                "⚠️ Training must be paused or stopped to restore.",
                                style={"color": "#856404", "fontSize": "0.9rem"},
                            ),
                        ]
                    )
                    return True, modal_body, snapshot_id

            # except (json.JSONDecodeError, IndexError):
            #     pass

            return False, "", None

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

        # Callback: Modal confirm button → perform restore (P3-2)
        @app.callback(
            Output(f"{self.component_id}-restore-modal", "is_open", allow_duplicate=True),
            Output(f"{self.component_id}-restore-status", "children"),
            Output(f"{self.component_id}-refresh-trigger", "data", allow_duplicate=True),
            Input(f"{self.component_id}-restore-confirm", "n_clicks"),
            State(f"{self.component_id}-restore-pending-id", "data"),
            State(f"{self.component_id}-refresh-trigger", "data"),
            prevent_initial_call=True,
        )
        def confirm_restore(n_clicks, snapshot_id, current_trigger):
            """Perform restore when confirmed."""
            if not n_clicks or not snapshot_id:
                return dash.no_update, dash.no_update, dash.no_update

            result = self._restore_snapshot_handler(snapshot_id)

            if result.get("success"):
                message = result.get("message", "Restored successfully")
                status_content = html.Div(
                    [
                        html.Span("✅ ", style={"color": "#28a745"}),
                        html.Span(f"{message}"),
                    ],
                    style={"color": "#28a745", "padding": "10px", "backgroundColor": "#d4edda", "borderRadius": "5px"},
                )
                return False, status_content, (current_trigger or 0) + 1
            else:
                error = result.get("error", "Unknown error")
                status_content = html.Div(
                    [
                        html.Span("❌ ", style={"color": "#dc3545"}),
                        html.Span(f"Failed to restore: {error}"),
                    ],
                    style={"color": "#dc3545", "padding": "10px", "backgroundColor": "#f8d7da", "borderRadius": "5px"},
                )
                return False, status_content, current_trigger or 0

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
                        style={"color": "#6c757d", "fontStyle": "italic"},
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
                        action_icon, action_color = action_config.get(action, ("•", "#6c757d"))

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
                                        style={"color": "#6c757d", "fontSize": "0.85rem", "marginRight": "10px"},
                                    ),
                                    html.Span(
                                        message,
                                        style={"color": "#495057", "fontSize": "0.9rem"},
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
        self._cb_open_restore_modal = open_restore_modal
        self._cb_close_restore_modal = close_restore_modal
        self._cb_confirm_restore = confirm_restore
        self._cb_toggle_history = toggle_history

        self.logger.debug(f"Callbacks registered for {self.component_id}")
