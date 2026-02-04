#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# File Name:     cassandra_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-01-09
# Last Modified: 2026-01-09
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Cassandra monitoring panel component displaying cluster status, schema information,
#    and real-time health metrics for the Cassandra backend integration.
#
#####################################################################################################################################################################################################
# Notes:
#
# Cassandra Monitoring Panel Component
#
# Provides real-time monitoring of Cassandra cluster status including:
# - Connection status (UP/DOWN/DISABLED/UNAVAILABLE)
# - Mode indicator (DEMO/LIVE/DISABLED)
# - Cluster overview with host status table
# - Schema overview with keyspace and table counts
# - Error message display for connection issues
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#   - Initial implementation for Cassandra monitoring
#
#####################################################################################################################################################################################################
from typing import Any, Dict, List

import dash_bootstrap_components as dbc
import requests
from dash import dcc, html

from ..base_component import BaseComponent

# Default configuration values
DEFAULT_REFRESH_INTERVAL_MS = 10000
DEFAULT_API_TIMEOUT_SECONDS = 5


class CassandraPanel(BaseComponent):
    """
    Cassandra monitoring panel component.

    Displays:
    - Cluster connection status with visual indicator
    - Mode indicator (DEMO/LIVE/DISABLED)
    - Cluster overview with contact points, keyspace, and host table
    - Schema overview with keyspace count, table count, and replication strategies
    - Error messages when connection issues occur
    """

    # Status badge color mapping
    STATUS_COLORS = {
        "UP": "success",
        "DOWN": "danger",
        "DISABLED": "secondary",
        "UNAVAILABLE": "warning",
    }

    # Mode badge color mapping
    MODE_COLORS = {
        "DEMO": "info",
        "LIVE": "success",
        "DISABLED": "secondary",
    }

    def __init__(self, config: Dict[str, Any], component_id: str = "cassandra-panel"):
        """
        Initialize Cassandra monitoring panel.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        # Configuration with defaults
        self.interval_ms = config.get("interval_ms", DEFAULT_REFRESH_INTERVAL_MS)
        self.api_timeout = config.get("api_timeout", DEFAULT_API_TIMEOUT_SECONDS)

        self.logger.info(f"CassandraPanel initialized with refresh interval: {self.interval_ms}ms")

    def _api_url(self, path: str) -> str:
        """
        Build API URL for Cassandra endpoints.

        Uses relative paths which work correctly when served from the same origin.
        For absolute URLs, constructs from config or uses default localhost.

        Args:
            path: API path (e.g., "/api/v1/cassandra/status")

        Returns:
            API URL string
        """
        # Use relative path - works when served from same origin
        return path.lstrip("/")

    def _render_hosts_table(self, hosts: List[Dict[str, Any]]) -> html.Div:
        """
        Render the host status table.

        Args:
            hosts: List of host dictionaries with address, datacenter, rack, status

        Returns:
            Dash Div containing the hosts table
        """
        if not hosts:
            return html.P(
                "No hosts available",
                className="text-muted",
                style={"fontStyle": "italic"},
            )

        # Build table header
        header = html.Thead(
            html.Tr(
                [
                    html.Th("Address", style={"width": "30%"}),
                    html.Th("Datacenter", style={"width": "25%"}),
                    html.Th("Rack", style={"width": "25%"}),
                    html.Th("Status", style={"width": "20%"}),
                ]
            )
        )

        # Build table rows
        rows = []
        for host in hosts:
            status = host.get("status", "UNKNOWN")
            status_color = self.STATUS_COLORS.get(status, "secondary")

            rows.append(
                html.Tr(
                    [
                        html.Td(host.get("address", "N/A")),
                        html.Td(host.get("datacenter", "N/A")),
                        html.Td(host.get("rack", "N/A")),
                        html.Td(dbc.Badge(status, color=status_color, className="px-2")),
                    ]
                )
            )

        body = html.Tbody(rows)

        return dbc.Table(
            [header, body],
            bordered=True,
            hover=True,
            responsive=True,
            size="sm",
            className="mb-0",
        )

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for Cassandra monitoring panel.

        Returns:
            Dash Div containing the monitoring interface
        """
        return html.Div(
            [
                # Auto-refresh interval
                dcc.Interval(
                    id=f"{self.component_id}-interval",
                    interval=self.interval_ms,
                    n_intervals=0,
                ),
                # Header with status badge
                html.Div(
                    [
                        html.H3(
                            [
                                "Cassandra Monitoring ",
                                dbc.Badge(
                                    "UNAVAILABLE",
                                    id=f"{self.component_id}-status-badge",
                                    color="warning",
                                    className="ms-2",
                                    style={"fontSize": "14px", "verticalAlign": "middle"},
                                ),
                            ],
                            style={"color": "#2c3e50", "marginBottom": "10px"},
                        ),
                        # Mode indicator
                        html.Div(
                            [
                                html.Span("Mode: ", style={"fontWeight": "bold"}),
                                dbc.Badge(
                                    "DISABLED",
                                    id=f"{self.component_id}-mode-badge",
                                    color="secondary",
                                    className="ms-1",
                                    style={"fontSize": "12px"},
                                ),
                            ],
                            style={"marginBottom": "20px"},
                        ),
                    ]
                ),
                # Error message area
                html.Div(
                    id=f"{self.component_id}-error-area",
                    style={"marginBottom": "15px"},
                ),
                # Cluster Overview Card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Cluster Overview", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            [
                                # Contact Points
                                html.Div(
                                    [
                                        html.Strong("Contact Points: "),
                                        html.Span(
                                            "N/A",
                                            id=f"{self.component_id}-contact-points",
                                        ),
                                    ],
                                    className="mb-2",
                                ),
                                # Keyspace
                                html.Div(
                                    [
                                        html.Strong("Keyspace: "),
                                        html.Span(
                                            "N/A",
                                            id=f"{self.component_id}-keyspace",
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                # Hosts Table
                                html.Div(
                                    [
                                        html.H6("Hosts", className="mb-2"),
                                        html.Div(
                                            id=f"{self.component_id}-hosts-table",
                                            children=html.P(
                                                "Loading...",
                                                className="text-muted",
                                            ),
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # Schema Overview Card
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Schema Overview", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            [
                                # Keyspace Count
                                html.Div(
                                    [
                                        html.Strong("Keyspaces: "),
                                        html.Span(
                                            "0",
                                            id=f"{self.component_id}-keyspace-count",
                                        ),
                                    ],
                                    className="mb-2",
                                ),
                                # Table Count
                                html.Div(
                                    [
                                        html.Strong("Tables: "),
                                        html.Span(
                                            "0",
                                            id=f"{self.component_id}-table-count",
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                # Replication Strategies
                                html.Div(
                                    [
                                        html.H6("Replication Strategies", className="mb-2"),
                                        html.Ul(
                                            id=f"{self.component_id}-replication-strategies",
                                            children=[
                                                html.Li(
                                                    "No data available",
                                                    className="text-muted",
                                                )
                                            ],
                                            style={
                                                "listStyleType": "disc",
                                                "paddingLeft": "20px",
                                                "fontSize": "13px",
                                            },
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "800px", "margin": "0 auto"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for Cassandra panel.

        Args:
            app: Dash application instance
        """
        from dash.dependencies import Input, Output

        @app.callback(
            [
                Output(f"{self.component_id}-status-badge", "children"),
                Output(f"{self.component_id}-status-badge", "color"),
                Output(f"{self.component_id}-mode-badge", "children"),
                Output(f"{self.component_id}-mode-badge", "color"),
                Output(f"{self.component_id}-contact-points", "children"),
                Output(f"{self.component_id}-keyspace", "children"),
                Output(f"{self.component_id}-hosts-table", "children"),
                Output(f"{self.component_id}-keyspace-count", "children"),
                Output(f"{self.component_id}-table-count", "children"),
                Output(f"{self.component_id}-replication-strategies", "children"),
                Output(f"{self.component_id}-error-area", "children"),
            ],
            Input(f"{self.component_id}-interval", "n_intervals"),
        )
        def update_cassandra_panel(n_intervals):
            """
            Update all Cassandra panel fields from API.

            Args:
                n_intervals: Number of interval triggers

            Returns:
                Tuple of updated component values
            """
            # Default values
            status_text = "UNAVAILABLE"
            status_color = "warning"
            mode_text = "DISABLED"
            mode_color = "secondary"
            contact_points = "N/A"
            keyspace = "N/A"
            hosts_table = html.P("No data available", className="text-muted")
            keyspace_count = "0"
            table_count = "0"
            replication_strategies = [html.Li("No data available", className="text-muted")]
            error_area = None

            try:
                # Fetch status from API
                status_url = self._api_url("/api/v1/cassandra/status")
                status_response = requests.get(status_url, timeout=self.api_timeout)

                if status_response.status_code == 200:
                    status_data = status_response.json()

                    # Update status
                    status_text = status_data.get("status", "UNAVAILABLE")
                    status_color = self.STATUS_COLORS.get(status_text, "warning")

                    # Update mode
                    mode_text = status_data.get("mode", "DISABLED")
                    mode_color = self.MODE_COLORS.get(mode_text, "secondary")

                    # Update cluster info
                    contact_points = ", ".join(status_data.get("contact_points", [])) or "N/A"
                    keyspace = status_data.get("keyspace", "N/A")

                    # Update hosts table
                    hosts = status_data.get("hosts", [])
                    hosts_table = self._render_hosts_table(hosts)

                elif status_response.status_code == 503:
                    status_text = "DISABLED"
                    status_color = "secondary"
                    error_area = dbc.Alert(
                        "Cassandra integration is disabled.",
                        color="info",
                        dismissable=True,
                    )
                else:
                    error_area = dbc.Alert(
                        f"Failed to fetch status: HTTP {status_response.status_code}",
                        color="warning",
                        dismissable=True,
                    )

            except requests.exceptions.Timeout:
                error_area = dbc.Alert(
                    "Connection timeout - Cassandra API not responding.",
                    color="danger",
                    dismissable=True,
                )
            except requests.exceptions.ConnectionError:
                error_area = dbc.Alert(
                    "Connection error - Unable to reach Cassandra API.",
                    color="danger",
                    dismissable=True,
                )
            except Exception as e:
                self.logger.error(f"Error fetching Cassandra status: {e}")
                error_area = dbc.Alert(
                    f"Error: {str(e)}",
                    color="danger",
                    dismissable=True,
                )

            # Fetch metrics/schema info
            try:
                metrics_url = self._api_url("/api/v1/cassandra/metrics")
                metrics_response = requests.get(metrics_url, timeout=self.api_timeout)

                if metrics_response.status_code == 200:
                    metrics_data = metrics_response.json()

                    # Update schema info
                    schema = metrics_data.get("schema", {})
                    keyspace_count = str(schema.get("keyspace_count", 0))
                    table_count = str(schema.get("table_count", 0))

                    # Update replication strategies
                    strategies = schema.get("replication_strategies", [])
                    if strategies:
                        replication_strategies = [html.Li(strategy) for strategy in strategies]

            except requests.exceptions.Timeout:
                self.logger.debug("Metrics request timed out")
            except requests.exceptions.ConnectionError:
                self.logger.debug("Metrics connection error")
            except Exception as e:
                self.logger.debug(f"Error fetching metrics: {e}")

            return (
                status_text,
                status_color,
                mode_text,
                mode_color,
                contact_points,
                keyspace,
                hosts_table,
                keyspace_count,
                table_count,
                replication_strategies,
                error_area,
            )

        # Expose callback for unit testing
        self._cb_update_cassandra_panel = update_cassandra_panel

        self.logger.debug(f"Callbacks registered for {self.component_id}")
