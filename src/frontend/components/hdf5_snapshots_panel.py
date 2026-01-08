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
import os
from typing import Any, Dict, List

import dash_bootstrap_components as dbc
import requests
from dash import callback_context, dcc, html
from dash.dependencies import ALL, Input, Output, State

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
                # Description
                html.P(
                    "View and manage HDF5 training state snapshots. Snapshots contain saved network states "
                    "that can be loaded for analysis or resumed training.",
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
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "1000px", "margin": "0 auto"},
        )

    def _fetch_snapshots_handler(self, n_intervals: int = 0) -> Dict[str, Any]:
        """
        Fetch snapshots list from backend API.

        Args:
            n_intervals: Interval count (unused, for callback compatibility)

        Returns:
            Dict with 'snapshots' list and optional 'message'
        """
        try:
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

        except requests.exceptions.Timeout:
            self.logger.warning("Snapshots API request timed out")
            return {"snapshots": [], "message": "Request timed out"}
        except requests.exceptions.ConnectionError:
            self.logger.warning("Cannot connect to snapshots API")
            return {"snapshots": [], "message": "Service unavailable"}
        except Exception as e:
            self.logger.warning(f"Failed to fetch snapshots: {e}")
            return {"snapshots": [], "message": "Snapshot service unavailable"}

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

        # Callback: Refresh / auto-refresh → update snapshots table
        @app.callback(
            Output(f"{self.component_id}-table-body", "children"),
            Output(f"{self.component_id}-status", "children"),
            Output(f"{self.component_id}-empty-state", "style"),
            Output(f"{self.component_id}-snapshots-store", "data"),
            Input(f"{self.component_id}-refresh-interval", "n_intervals"),
            Input(f"{self.component_id}-refresh-button", "n_clicks"),
            prevent_initial_call=False,
        )
        def update_snapshots_table(n_intervals, n_clicks):
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
                                dbc.Button(
                                    "View Details",
                                    id={"type": f"{self.component_id}-view-btn", "index": snapshot_id},
                                    size="sm",
                                    color="info",
                                    outline=True,
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
                for n, id_obj in zip(n_clicks_list, ids):
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
                items.append(
                    html.Ul(attr_items, style={"listStyleType": "disc", "paddingLeft": "20px", "fontSize": "0.9rem"})
                )

            return html.Div(items)

        self.logger.debug(f"Callbacks registered for {self.component_id}")
