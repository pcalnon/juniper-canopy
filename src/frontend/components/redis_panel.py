#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     redis_panel.py
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
#    Redis monitoring panel component displaying Redis connection status, health metrics,
#    and performance statistics.
#
#####################################################################################################################################################################################################
# Notes:
#
# Redis Monitoring Panel Component
#
# Real-time monitoring panel for Redis connection health, memory usage, operations
# per second, cache hit rate, and keyspace statistics. Supports DEMO/LIVE/DISABLED modes.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#   - Initial implementation for Redis monitoring dashboard
#
#####################################################################################################################################################################################################
import os
from typing import Any, Dict

import dash_bootstrap_components as dbc
import requests
from dash import dcc, html

from settings import get_settings

from ..base_component import BaseComponent

DEFAULT_REFRESH_INTERVAL_MS = 5000
DEFAULT_API_TIMEOUT = 2


class RedisPanel(BaseComponent):
    """
    Redis monitoring panel component.

    Displays:
    - Connection status (UP/DOWN/DISABLED/UNAVAILABLE)
    - Mode indicator (DEMO/LIVE/DISABLED)
    - Health metrics: version, uptime, connected clients, latency
    - Performance metrics: memory usage, ops/sec, hit rate, keyspace stats
    - Error messages when connection fails
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "redis-panel"):
        """
        Initialize Redis monitoring panel.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        if "interval_ms" in config:
            self.interval_ms = config["interval_ms"]
        elif interval_env := os.getenv("JUNIPER_CANOPY_REDIS_REFRESH_INTERVAL_MS"):
            try:
                self.interval_ms = int(interval_env)
                self.logger.info(f"Redis panel refresh interval overridden by env: {interval_env}ms")
            except ValueError:
                self.interval_ms = DEFAULT_REFRESH_INTERVAL_MS
        else:
            self.interval_ms = DEFAULT_REFRESH_INTERVAL_MS

        self.api_timeout = config.get("api_timeout", DEFAULT_API_TIMEOUT)

        self.logger.info(f"RedisPanel initialized with interval_ms={self.interval_ms}")

    def _api_url(self, path: str) -> str:
        """
        Build API URL for Redis endpoints.

        Args:
            path: API path (e.g., '/api/v1/redis/status')

        Returns:
            Full API URL
        """
        _settings = get_settings()
        base_url = self.config.get("api_base_url", f"http://127.0.0.1:{_settings.server.port}")
        return f"{base_url}{path}"

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for Redis monitoring panel.

        Returns:
            Dash Div containing the Redis monitoring interface
        """
        return html.Div(
            [
                html.Div(
                    [
                        html.H3(
                            "Redis Monitoring",
                            style={"display": "inline-block", "marginRight": "15px", "color": "#2c3e50"},
                        ),
                        dbc.Badge(
                            id=f"{self.component_id}-status-badge",
                            children="LOADING",
                            color="secondary",
                            className="me-2",
                            style={"fontSize": "14px", "verticalAlign": "middle"},
                        ),
                        dbc.Badge(
                            id=f"{self.component_id}-mode-badge",
                            children="...",
                            color="info",
                            className="me-2",
                            style={"fontSize": "12px", "verticalAlign": "middle"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                html.Div(
                    id=f"{self.component_id}-error-display",
                    style={"marginBottom": "15px"},
                ),
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Health", className="mb-0"),
                        ),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Version",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-version",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Uptime",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-uptime",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Connected Clients",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-clients",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Latency (ms)",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-latency",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Metrics", className="mb-0"),
                        ),
                        dbc.CardBody(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Memory Usage",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-memory",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Ops/sec",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-ops-sec",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Hit Rate",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-hit-rate",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                        dbc.Col(
                                            [
                                                html.Div(
                                                    "Keyspace",
                                                    style={
                                                        "fontWeight": "bold",
                                                        "fontSize": "12px",
                                                        "color": "#6c757d",
                                                    },
                                                ),
                                                html.Div(
                                                    id=f"{self.component_id}-keyspace",
                                                    children="--",
                                                    style={"fontSize": "16px"},
                                                ),
                                            ],
                                            width=3,
                                        ),
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                dcc.Interval(
                    id=f"{self.component_id}-refresh-interval",
                    interval=self.interval_ms,
                    n_intervals=0,
                ),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "900px", "margin": "0 auto"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for Redis panel.

        Args:
            app: Dash application instance
        """
        from dash.dependencies import Input, Output

        # PERF-CN-01: prevent_initial_call=False — must hit the Redis health API
        # on mount to populate panel fields before the first interval tick.
        @app.callback(
            [
                Output(f"{self.component_id}-status-badge", "children"),
                Output(f"{self.component_id}-status-badge", "color"),
                Output(f"{self.component_id}-mode-badge", "children"),
                Output(f"{self.component_id}-mode-badge", "color"),
                Output(f"{self.component_id}-error-display", "children"),
                Output(f"{self.component_id}-version", "children"),
                Output(f"{self.component_id}-uptime", "children"),
                Output(f"{self.component_id}-clients", "children"),
                Output(f"{self.component_id}-latency", "children"),
                Output(f"{self.component_id}-memory", "children"),
                Output(f"{self.component_id}-ops-sec", "children"),
                Output(f"{self.component_id}-hit-rate", "children"),
                Output(f"{self.component_id}-keyspace", "children"),
            ],
            Input(f"{self.component_id}-refresh-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def update_redis_panel(n_intervals):
            """Update all Redis panel fields from API."""
            status_text = "UNAVAILABLE"
            status_color = "secondary"
            mode_text = "..."
            mode_color = "info"
            error_children = None
            version = "--"
            uptime = "--"
            clients = "--"
            latency = "--"
            memory = "--"
            ops_sec = "--"
            hit_rate = "--"
            keyspace = "--"

            try:
                status_resp = requests.get(
                    self._api_url("/api/v1/redis/status"),
                    timeout=self.api_timeout,
                )
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    raw_status = status_data.get("status", "unknown").upper()
                    mode = status_data.get("mode", "unknown").upper()

                    if raw_status == "UP" or raw_status == "CONNECTED":
                        status_text = "UP"
                        status_color = "success"
                    elif raw_status == "DOWN" or raw_status == "DISCONNECTED":
                        status_text = "DOWN"
                        status_color = "danger"
                    elif raw_status == "DISABLED":
                        status_text = "DISABLED"
                        status_color = "warning"
                    else:
                        status_text = raw_status
                        status_color = "secondary"

                    if mode == "DEMO":
                        mode_text = "DEMO"
                        mode_color = "info"
                    elif mode == "LIVE":
                        mode_text = "LIVE"
                        mode_color = "primary"
                    elif mode == "DISABLED":
                        mode_text = "DISABLED"
                        mode_color = "secondary"
                    else:
                        mode_text = mode
                        mode_color = "info"

                    details = status_data.get("details", {})
                    version = details.get("version", "--")
                    uptime = self._format_uptime(details.get("uptime_seconds"))
                    clients = str(details.get("connected_clients", "--"))
                    latency = self._format_latency(details.get("latency_ms"))

            except requests.exceptions.Timeout:
                error_children = dbc.Alert("Redis status request timed out", color="warning", dismissable=True)
                self.logger.warning("Redis status API request timed out")
            except requests.exceptions.ConnectionError:
                error_children = dbc.Alert("Cannot connect to Redis status API", color="danger", dismissable=True)
                self.logger.warning("Cannot connect to Redis status API")
            except Exception as e:
                error_children = dbc.Alert(f"Error fetching Redis status: {e}", color="danger", dismissable=True)
                self.logger.warning(f"Error fetching Redis status: {e}")

            try:
                metrics_resp = requests.get(
                    self._api_url("/api/v1/redis/metrics"),
                    timeout=self.api_timeout,
                )
                if metrics_resp.status_code == 200:
                    metrics_data = metrics_resp.json()
                    metrics = metrics_data.get("metrics", {}) or {}
                    memory_data = metrics.get("memory", {})
                    stats_data = metrics.get("stats", {})
                    keyspace_data = metrics.get("keyspace", {})
                    memory = self._format_memory(memory_data.get("used_memory_bytes"))
                    ops_sec = str(stats_data.get("instantaneous_ops_per_sec", "--"))
                    hit_rate = self._format_hit_rate(stats_data.get("hit_rate_percent"))
                    keyspace = self._format_keyspace(keyspace_data)

            except requests.exceptions.Timeout:
                if error_children is None:
                    error_children = dbc.Alert("Redis metrics request timed out", color="warning", dismissable=True)
                self.logger.warning("Redis metrics API request timed out")
            except requests.exceptions.ConnectionError:
                if error_children is None:
                    error_children = dbc.Alert("Cannot connect to Redis metrics API", color="danger", dismissable=True)
                self.logger.warning("Cannot connect to Redis metrics API")
            except Exception as e:
                if error_children is None:
                    error_children = dbc.Alert(f"Error fetching Redis metrics: {e}", color="danger", dismissable=True)
                self.logger.warning(f"Error fetching Redis metrics: {e}")

            return (
                status_text,
                status_color,
                mode_text,
                mode_color,
                error_children,
                version,
                uptime,
                clients,
                latency,
                memory,
                ops_sec,
                hit_rate,
                keyspace,
            )

        self._cb_update_redis_panel = update_redis_panel

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _format_uptime(self, seconds: Any) -> str:
        """Format uptime seconds into human-readable string."""
        if seconds is None:
            return "--"
        try:
            seconds = int(seconds)
            if seconds < 60:
                return f"{seconds}s"
            elif seconds < 3600:
                return f"{seconds // 60}m {seconds % 60}s"
            elif seconds < 86400:
                hours = seconds // 3600
                mins = (seconds % 3600) // 60
                return f"{hours}h {mins}m"
            else:
                days = seconds // 86400
                hours = (seconds % 86400) // 3600
                return f"{days}d {hours}h"
        except (ValueError, TypeError):
            return "--"

    def _format_latency(self, latency_ms: Any) -> str:
        """Format latency value."""
        if latency_ms is None:
            return "--"
        try:
            return f"{float(latency_ms):.2f}"
        except (ValueError, TypeError):
            return "--"

    def _format_memory(self, bytes_val: Any) -> str:
        """Format memory bytes into human-readable string."""
        if bytes_val is None:
            return "--"
        try:
            bytes_val = int(bytes_val)
            if bytes_val < 1024:
                return f"{bytes_val} B"
            elif bytes_val < 1024 * 1024:
                return f"{bytes_val / 1024:.1f} KB"
            elif bytes_val < 1024 * 1024 * 1024:
                return f"{bytes_val / (1024 * 1024):.1f} MB"
            else:
                return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"
        except (ValueError, TypeError):
            return "--"

    def _format_hit_rate(self, rate: Any) -> str:
        """Format hit rate as percentage.

        Args:
            rate: Hit rate already expressed as a percentage (e.g. 85.5 for 85.5%).
        """
        if rate is None:
            return "--"
        try:
            return f"{float(rate):.1f}%"
        except (ValueError, TypeError):
            return "--"

    def _format_keyspace(self, keyspace: Any) -> str:
        """Format keyspace information."""
        if keyspace is None:
            return "--"
        if isinstance(keyspace, dict):
            total_keys = sum(db.get("keys", 0) for db in keyspace.values())
            return f"{total_keys} keys"
        elif isinstance(keyspace, (int, float)):
            return f"{int(keyspace)} keys"
        return str(keyspace)
