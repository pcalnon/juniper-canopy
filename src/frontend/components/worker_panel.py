#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     worker_panel.py
# Author:        Paul Calnon
# Version:       1.1.0
#
# Date:          2026-03-31
# Last Modified: 2026-07-22
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Worker monitoring panel: aggregate cluster stats plus a per-worker roster table
#    (id, kind local/remote, status, health, last-heartbeat, current task) driven by
#    the shared, tab-gated worker store. N10 (training-runtime defects plan §4-U U-5)
#    adds the local/remote distinction: cascor's registry models remote WebSocket
#    workers only, so remote workers are labeled ``remote`` and — because the local
#    in-process candidate pool is not individually reported by the CasCor API — an
#    honest "local not individually reported" note is shown rather than fabricated
#    local records. Demo mode shows one clearly-labeled ``local`` + one ``remote``.
#
#####################################################################################################################################################################################################
import time
from datetime import datetime, timezone

import dash_bootstrap_components as dbc
from dash import dcc, html

from ..base_component import BaseComponent

# Relative-age threshold (seconds) below which a heartbeat is shown as "Ns ago"
# rather than an absolute UTC clock — recent liveness is the useful signal.
HEARTBEAT_RELATIVE_WINDOW_S = 120


class WorkerPanel(BaseComponent):
    """
    Worker monitoring panel component.

    Displays:
    - Aggregate worker statistics (total, idle, busy, stale)
    - Task throughput (completed, failed, average health)
    - A per-worker roster table with the local/remote kind, status, health,
      last-heartbeat, and current task.

    Data arrives via the shared ``worker-panel-workers-store`` (filled by the
    dashboard's tab-gated slow poll of ``/api/v1/workers/list`` + ``/stats``); the
    panel itself no longer owns a refresh interval (N10 — the topology-tab N1
    posture: tab-gated + empty-guarded).
    """

    def __init__(self, config, component_id: str = "worker-panel"):
        super().__init__(config, component_id)
        self.logger.info(f"WorkerPanel initialized (store-driven) id={self.component_id}")

    def get_layout(self) -> html.Div:
        return html.Div(
            [
                # Roster data source — filled by the dashboard's tab-gated slow
                # poll (frontend.dashboard_manager._update_workers_store_handler).
                dcc.Store(id=f"{self.component_id}-workers-store", data=None),
                html.Div(
                    [
                        html.H3(
                            "Workers",
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
                # Per-worker roster (table + honest local-scope note)
                html.Div(
                    id=f"{self.component_id}-worker-list",
                    style={"marginTop": "10px"},
                ),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "900px", "margin": "0 auto"},
        )

    def register_callbacks(self, app):
        from dash.dependencies import Input, Output

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
            Input(f"{self.component_id}-workers-store", "data"),
            prevent_initial_call=False,
        )
        def render_worker_panel(store_data):
            return WorkerPanel._render_from_store(store_data)

        self._cb_render_worker_panel = render_worker_panel
        self.logger.debug(f"Callbacks registered for {self.component_id}")

    @staticmethod
    def _render_from_store(store_data):
        """Pure render of the 10-tuple panel outputs from the worker store payload.

        ``store_data`` is ``None`` until the tab-gated poll first fills the store
        (i.e. before the Workers tab is visited), in which case a LOADING placeholder
        is shown. Otherwise it carries ``{"stats": {...}, "workers": [...],
        "count": int, "local_reported": bool, "error": str|None}``.
        """
        status_text = "LOADING"
        status_color = "secondary"
        error_children = None
        total = idle = busy = stale = tasks_done = avg_health = "--"
        worker_list = html.Div("No data available", style={"color": "var(--text-muted)", "fontStyle": "italic"})

        if not store_data or not isinstance(store_data, dict):
            return (status_text, status_color, error_children, total, idle, busy, stale, tasks_done, avg_health, worker_list)

        stats = store_data.get("stats") or {}
        workers = store_data.get("workers") or []
        local_reported = bool(store_data.get("local_reported", False))
        upstream_error = store_data.get("error")

        if stats:
            total_val = stats.get("total", len(workers))
            stale_val = stats.get("stale", 0)
            total = str(total_val)
            idle = str(stats.get("idle", 0))
            busy = str(stats.get("busy", 0))
            stale = str(stale_val)
            completed = stats.get("total_tasks_completed", 0)
            failed = stats.get("total_tasks_failed", 0)
            tasks_done = f"{completed} / {failed} fail"
            health = stats.get("average_health_score", 0) or 0
            avg_health = f"{health:.1%}"

            if total_val == 0:
                status_text, status_color = "NO WORKERS", "warning"
            elif stale_val > 0:
                status_text, status_color = "DEGRADED", "warning"
            else:
                status_text, status_color = "HEALTHY", "success"
        else:
            # Roster available but aggregate stats endpoint was unreachable — still
            # show the roster and a coarse status derived from the worker count.
            total = str(len(workers))
            if workers:
                status_text, status_color = "HEALTHY", "success"
            else:
                status_text, status_color = "NO WORKERS", "warning"

        if upstream_error:
            error_children = dbc.Alert(f"Worker data degraded: {upstream_error}", color="warning", dismissable=True)

        worker_list = WorkerPanel._render_worker_list(workers, local_reported)

        return (status_text, status_color, error_children, total, idle, busy, stale, tasks_done, avg_health, worker_list)

    @staticmethod
    def _render_worker_list(workers, local_reported: bool) -> html.Div:
        """Render the roster: a per-worker table (or an empty-state alert) plus,
        when the backend does not individually report local workers, an honest note
        clarifying that only remote registered workers are listed."""
        children = []
        if workers:
            children.append(WorkerPanel._render_workers_table(workers))
        else:
            children.append(dbc.Alert("No workers connected", color="info", className="mt-2"))

        if not local_reported:
            children.append(
                html.Div(
                    html.Small(
                        "Local in-process workers are not individually reported by the CasCor API; " "only remote registered workers are listed above.",
                        style={"color": "var(--text-muted)", "fontStyle": "italic"},
                    ),
                    className="mt-2",
                    id="worker-panel-local-note",
                )
            )
        return html.Div(children)

    @staticmethod
    def _render_workers_table(workers) -> dbc.Table:
        """Build the worker roster table (id, kind, status, health, last-heartbeat, current task)."""
        header = html.Thead(
            html.Tr(
                [
                    html.Th("Worker ID", style={"width": "28%"}),
                    html.Th("Kind", style={"width": "12%"}),
                    html.Th("Status", style={"width": "12%"}),
                    html.Th("Health", style={"width": "12%"}),
                    html.Th("Last Heartbeat", style={"width": "16%"}),
                    html.Th("Current Task", style={"width": "20%"}),
                ]
            )
        )
        body = html.Tbody([WorkerPanel._render_worker_row(w) for w in workers])
        return dbc.Table([header, body], bordered=True, hover=True, responsive=True, size="sm", className="mb-0")

    @staticmethod
    def _render_worker_row(worker: dict) -> html.Tr:
        worker_id = worker.get("worker_id", "unknown")
        kind = str(worker.get("kind") or "remote").lower()
        is_idle = worker.get("idle", False)
        health = worker.get("health_score", 0) or 0
        active_task = worker.get("active_task_id")
        last_heartbeat = worker.get("last_heartbeat")

        kind_color = "info" if kind == "local" else "secondary"
        status_badge = dbc.Badge("IDLE", color="success") if is_idle else dbc.Badge("BUSY", color="primary")

        if health >= 0.9:
            health_color = "success"
        elif health >= 0.7:
            health_color = "warning"
        else:
            health_color = "danger"

        heartbeat_str = "--"
        if last_heartbeat:
            try:
                heartbeat_str = WorkerPanel._format_heartbeat(last_heartbeat)
            except (ValueError, OSError, TypeError):
                heartbeat_str = "--"

        task_cell = html.Code(active_task, style={"fontSize": "11px"}) if active_task else html.Small("—", style={"color": "var(--text-muted)"})

        return html.Tr(
            [
                html.Td(html.Code(worker_id, style={"fontSize": "12px"})),
                html.Td(dbc.Badge(kind.upper(), color=kind_color, className="px-2")),
                html.Td(status_badge),
                html.Td(dbc.Badge(f"{health:.0%}", color=health_color, style={"fontSize": "11px"})),
                html.Td(html.Small(heartbeat_str)),
                html.Td(task_cell),
            ]
        )

    @staticmethod
    def _format_heartbeat(timestamp) -> str:
        """Format a heartbeat epoch as a relative age ("Ns ago") when recent, else
        an absolute UTC clock — recent liveness being the useful signal."""
        ts = float(timestamp)
        age = time.time() - ts
        if age < 0:
            age = 0
        if age < HEARTBEAT_RELATIVE_WINDOW_S:
            return f"{int(age)}s ago"
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S UTC")
