#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     worker_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-03-31
# Last Modified: 2026-03-31
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Remote worker monitoring panel component displaying connected worker status, health,
#    task throughput, and individual worker details from the CasCor worker registry.
#
#####################################################################################################################################################################################################
import os
from datetime import datetime, timezone
from typing import Any, Dict

import dash_bootstrap_components as dbc
import requests
from dash import dcc, html

from frontend.internal_api import internal_api_headers
from settings import get_settings

from ..base_component import BaseComponent

DEFAULT_REFRESH_INTERVAL_MS = 5000
DEFAULT_API_TIMEOUT = 3


class WorkerPanel(BaseComponent):
    """
    Remote worker monitoring panel component.

    Displays:
    - Aggregate worker statistics (total, idle, busy, stale)
    - Task throughput (completed, failed, average health)
    - Individual worker cards with capabilities and status
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "worker-panel"):
        super().__init__(config, component_id)

        if "interval_ms" in config:
            self.interval_ms = config["interval_ms"]
        elif interval_env := os.getenv("JUNIPER_CANOPY_WORKER_REFRESH_INTERVAL_MS"):
            try:
                self.interval_ms = int(interval_env)
                self.logger.info(f"Worker panel refresh interval overridden by env: {interval_env}ms")
            except ValueError:
                self.interval_ms = DEFAULT_REFRESH_INTERVAL_MS
        else:
            self.interval_ms = DEFAULT_REFRESH_INTERVAL_MS

        self.api_timeout = config.get("api_timeout", DEFAULT_API_TIMEOUT)
        self.logger.info(f"WorkerPanel initialized with interval_ms={self.interval_ms}")

    def _api_url(self, path: str) -> str:
        _settings = get_settings()
        base_url = self.config.get("api_base_url", f"http://127.0.0.1:{_settings.server.port}")
        return f"{base_url}{path}"

    def get_layout(self) -> html.Div:
        return html.Div(
            [
                html.Div(
                    [
                        html.H3(
                            "Remote Workers",
                            style={"display": "inline-block", "marginRight": "15px", "color": "var(--header-color)"},
                        ),
                        dbc.Badge(
                            id=f"{self.component_id}-status-badge",
                            children="LOADING",
                            color="secondary",
                            className="me-2",
                            style={"fontSize": "14px", "verticalAlign": "middle"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                html.Div(
                    id=f"{self.component_id}-error-display",
                    style={"marginBottom": "15px"},
                ),
                # Aggregate stats card
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Cluster Overview", className="mb-0")),
                        dbc.CardBody(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Div("Total", style={"fontWeight": "bold", "fontSize": "12px", "color": "var(--text-muted)"}),
                                            html.Div(id=f"{self.component_id}-total", children="--", style={"fontSize": "24px", "fontWeight": "bold"}),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div("Idle", style={"fontWeight": "bold", "fontSize": "12px", "color": "var(--text-muted)"}),
                                            html.Div(id=f"{self.component_id}-idle", children="--", style={"fontSize": "24px", "fontWeight": "bold", "color": "#28a745"}),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div("Busy", style={"fontWeight": "bold", "fontSize": "12px", "color": "var(--text-muted)"}),
                                            html.Div(id=f"{self.component_id}-busy", children="--", style={"fontSize": "24px", "fontWeight": "bold", "color": "#007bff"}),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div("Stale", style={"fontWeight": "bold", "fontSize": "12px", "color": "var(--text-muted)"}),
                                            html.Div(id=f"{self.component_id}-stale", children="--", style={"fontSize": "24px", "fontWeight": "bold", "color": "#dc3545"}),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div("Tasks Done", style={"fontWeight": "bold", "fontSize": "12px", "color": "var(--text-muted)"}),
                                            html.Div(id=f"{self.component_id}-tasks-done", children="--", style={"fontSize": "24px", "fontWeight": "bold"}),
                                        ],
                                        width=2,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Div("Avg Health", style={"fontWeight": "bold", "fontSize": "12px", "color": "var(--text-muted)"}),
                                            html.Div(id=f"{self.component_id}-avg-health", children="--", style={"fontSize": "24px", "fontWeight": "bold"}),
                                        ],
                                        width=2,
                                    ),
                                ]
                            ),
                        ),
                    ],
                    className="mb-3",
                ),
                # Individual worker list
                html.Div(
                    id=f"{self.component_id}-worker-list",
                    style={"marginTop": "10px"},
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
        from dash.dependencies import Input, Output

        # PERF-CN-01: prevent_initial_call=False — must hit the worker stats API
        # on mount to populate badges/counts before the first interval tick.
        @app.callback(
            [
                Output(f"{self.component_id}-status-badge", "children"),
                Output(f"{self.component_id}-status-badge", "color"),
                Output(f"{self.component_id}-error-display", "children"),
                Output(f"{self.component_id}-total", "children"),
                Output(f"{self.component_id}-idle", "children"),
                Output(f"{self.component_id}-busy", "children"),
                Output(f"{self.component_id}-stale", "children"),
                Output(f"{self.component_id}-tasks-done", "children"),
                Output(f"{self.component_id}-avg-health", "children"),
                Output(f"{self.component_id}-worker-list", "children"),
            ],
            Input(f"{self.component_id}-refresh-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def update_worker_panel(n_intervals):
            status_text = "UNAVAILABLE"
            status_color = "secondary"
            error_children = None
            total = "--"
            idle = "--"
            busy = "--"
            stale = "--"
            tasks_done = "--"
            avg_health = "--"
            worker_list = html.Div("No data available", style={"color": "var(--text-muted)", "fontStyle": "italic"})

            try:
                stats_resp = requests.get(
                    self._api_url("/api/v1/workers/stats"),
                    timeout=self.api_timeout,
                    headers=internal_api_headers(),
                )
                if stats_resp.status_code == 200:
                    data = stats_resp.json().get("data", {})
                    total_val = data.get("total", 0)
                    stale_val = data.get("stale", 0)
                    total = str(total_val)
                    idle = str(data.get("idle", 0))
                    busy = str(data.get("busy", 0))
                    stale = str(stale_val)
                    completed = data.get("total_tasks_completed", 0)
                    failed = data.get("total_tasks_failed", 0)
                    tasks_done = f"{completed} / {failed} fail"
                    health = data.get("average_health_score", 0)
                    avg_health = f"{health:.1%}"

                    if total_val == 0:
                        status_text = "NO WORKERS"
                        status_color = "warning"
                    elif stale_val > 0:
                        status_text = "DEGRADED"
                        status_color = "warning"
                    else:
                        status_text = "HEALTHY"
                        status_color = "success"

            except requests.exceptions.Timeout:
                error_children = dbc.Alert("Worker stats request timed out", color="warning", dismissable=True)
            except requests.exceptions.ConnectionError:
                error_children = dbc.Alert("Cannot connect to worker stats API", color="danger", dismissable=True)
            except Exception as e:
                error_children = dbc.Alert(f"Error fetching worker stats: {e}", color="danger", dismissable=True)

            try:
                list_resp = requests.get(
                    self._api_url("/api/v1/workers/list"),
                    timeout=self.api_timeout,
                    headers=internal_api_headers(),
                )
                if list_resp.status_code == 200:
                    data = list_resp.json().get("data", {})
                    workers = data.get("workers", [])
                    if workers:
                        worker_list = html.Div([self._render_worker_card(w) for w in workers])
                    else:
                        worker_list = dbc.Alert("No workers connected", color="info", className="mt-2")

            except requests.exceptions.Timeout:
                if error_children is None:
                    error_children = dbc.Alert("Worker list request timed out", color="warning", dismissable=True)
            except requests.exceptions.ConnectionError:
                pass
            except Exception as e:
                if error_children is None:
                    error_children = dbc.Alert(f"Error fetching worker list: {e}", color="danger", dismissable=True)

            return (
                status_text,
                status_color,
                error_children,
                total,
                idle,
                busy,
                stale,
                tasks_done,
                avg_health,
                worker_list,
            )

        self._cb_update_worker_panel = update_worker_panel
        self.logger.debug(f"Callbacks registered for {self.component_id}")

    @staticmethod
    def _render_worker_card(worker: dict) -> dbc.Card:
        worker_id = worker.get("worker_id", "unknown")
        is_idle = worker.get("idle", False)
        health = worker.get("health_score", 0)
        caps = worker.get("capabilities", {})
        completed = worker.get("tasks_completed", 0)
        failed = worker.get("tasks_failed", 0)
        active_task = worker.get("active_task_id")

        if health >= 0.9:
            health_color = "success"
        elif health >= 0.7:
            health_color = "warning"
        else:
            health_color = "danger"

        status_badge = dbc.Badge("IDLE", color="success", className="ms-2") if is_idle else dbc.Badge("BUSY", color="primary", className="ms-2")

        connected_at = worker.get("connected_at")
        connected_str = ""
        if connected_at:
            try:
                dt = datetime.fromtimestamp(connected_at, tz=timezone.utc)
                connected_str = dt.strftime("%H:%M:%S UTC")
            except (ValueError, OSError):
                connected_str = "--"

        cap_items = []
        if caps.get("cpu_cores"):
            cap_items.append(f"{caps['cpu_cores']} CPU")
        if caps.get("gpu"):
            cap_items.append("GPU")
        if caps.get("python"):
            cap_items.append(f"Py {caps['python']}")
        cap_text = " | ".join(cap_items) if cap_items else "No capability data"

        body_rows = [
            dbc.Row(
                [
                    dbc.Col(html.Small(f"Capabilities: {cap_text}", style={"color": "var(--text-muted)"}), width=12),
                ],
                className="mb-1",
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Small("Tasks: ", style={"fontWeight": "bold", "color": "var(--text-muted)"}),
                            html.Small(f"{completed} done, {failed} failed"),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Small("Health: ", style={"fontWeight": "bold", "color": "var(--text-muted)"}),
                            dbc.Badge(f"{health:.0%}", color=health_color, style={"fontSize": "11px"}),
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            html.Small("Connected: ", style={"fontWeight": "bold", "color": "var(--text-muted)"}),
                            html.Small(connected_str),
                        ],
                        width=4,
                    ),
                ],
            ),
        ]

        if active_task:
            body_rows.append(
                dbc.Row(
                    dbc.Col(
                        [
                            html.Small("Active task: ", style={"fontWeight": "bold", "color": "var(--text-muted)"}),
                            html.Code(active_task, style={"fontSize": "11px"}),
                        ],
                        width=12,
                    ),
                    className="mt-1",
                )
            )

        return dbc.Card(
            [
                dbc.CardHeader(
                    html.Div(
                        [html.Strong(worker_id), status_badge],
                        style={"display": "flex", "alignItems": "center"},
                    ),
                    style={"padding": "8px 12px"},
                ),
                dbc.CardBody(body_rows, style={"padding": "10px 12px"}),
            ],
            className="mb-2",
        )
