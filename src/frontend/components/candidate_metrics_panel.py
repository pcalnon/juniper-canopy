#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     candidate_metrics_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-04-01
# Last Modified: 2026-04-01
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Candidate Metrics tab component for the Juniper Canopy dashboard.
#    Provides a dedicated view for candidate pool training status,
#    performance metrics, candidate rankings, loss visualization,
#    and pool history tracking.
#
#####################################################################################################################################################################################################
# Notes:
#
#     CandidateMetricsPanel Component
#
#     Real-time visualization of candidate pool training including:
#     - Pool status, phase, and epoch progress
#     - Top candidate rankings with correlation scores
#     - Candidate training loss plot (orange trace)
#     - Pool training metrics (avg loss, accuracy, precision, recall, F1)
#     - Historical pool tracking with expandable cards
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#
#####################################################################################################################################################################################################
import time
from typing import Any, Dict

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output, State

from settings import get_settings

from ..base_component import BaseComponent, create_empty_plot

# Maximum number of historical pool entries to retain in memory
MAX_POOL_HISTORY_ENTRIES = 20


class CandidateMetricsPanel(BaseComponent):
    """
    Candidate pool metrics visualization component.

    Displays real-time candidate pool training data including:
    - Pool status and training phase
    - Candidate epoch progress bar
    - Top candidate rankings table
    - Pool training metrics summary
    - Candidate training loss plot
    - Historical pool tracking with expandable cards
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "candidate-metrics-panel"):
        """
        Initialize candidate metrics panel component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        _settings = get_settings()
        self._api_base_url = f"http://127.0.0.1:{_settings.server.port}"

        # Update interval (milliseconds)
        self.update_interval = config.get("update_interval", 1000)

        self.logger.info(f"CandidateMetricsPanel initialized (interval={self.update_interval}ms)")

    def _api_url(self, path: str) -> str:
        """Build API URL for the given path."""
        return f"{self._api_base_url}{path}"

    def get_layout(self) -> html.Div:
        """
        Build the Candidate Metrics tab layout.

        Returns:
            Dash Div containing the complete candidate metrics layout
        """
        return html.Div(
            [
                # ── Status Section ──
                html.Div(
                    [
                        html.H4(
                            [
                                "Candidate Pool ",
                                html.Span(
                                    id=f"{self.component_id}-status-badge",
                                    style={"fontSize": "14px"},
                                ),
                            ],
                            style={"marginBottom": "15px"},
                        ),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Span("Phase: ", style={"fontWeight": "600"}),
                                        html.Span(id=f"{self.component_id}-phase", children="Idle"),
                                    ],
                                    style={"marginBottom": "5px"},
                                ),
                                html.Div(
                                    [
                                        html.Span("Pool Size: ", style={"fontWeight": "600"}),
                                        html.Span(id=f"{self.component_id}-pool-size", children="0"),
                                    ],
                                    style={"marginBottom": "10px"},
                                ),
                            ]
                        ),
                        # Candidate Epoch Progress Bar
                        html.Div(
                            [
                                html.P("Candidate Epoch Progress:", className="mb-1 fw-bold", style={"fontSize": "13px"}),
                                dbc.Progress(
                                    id=f"{self.component_id}-epoch-progress",
                                    value=0,
                                    label="",
                                    striped=True,
                                    animated=True,
                                    style={"height": "20px"},
                                    className="mb-3",
                                ),
                            ],
                            id=f"{self.component_id}-progress-section",
                            style={"display": "none"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # ── Pool Info Section (collapsible) ──
                html.Div(
                    [
                        html.H6(
                            [
                                html.Span(
                                    "▼",
                                    id=f"{self.component_id}-toggle-icon",
                                    style={"cursor": "pointer", "fontSize": "12px", "marginRight": "5px"},
                                ),
                                "Pool Details",
                            ],
                            id=f"{self.component_id}-candidate-toggle",
                            style={"cursor": "pointer", "marginBottom": "10px"},
                            className="collapsible-header",
                        ),
                        dbc.Collapse(
                            html.Div(id=f"{self.component_id}-pool-info", children=[]),
                            id=f"{self.component_id}-pool-collapse",
                            is_open=True,
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # ── Candidate Loss Plot ──
                html.Div(
                    [
                        html.H6("Candidate Training Loss", style={"marginBottom": "10px"}),
                        dcc.Graph(
                            id=f"{self.component_id}-loss-plot",
                            config={"displayModeBar": True, "scrollZoom": True},
                            style={"height": "350px"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # ── Pool History Section (collapsible) ──
                html.Div(
                    [
                        html.H6(
                            [
                                html.Span("▼", id=f"{self.component_id}-history-icon", className="collapse-icon"),
                                "Pool History",
                            ],
                            id=f"{self.component_id}-history-toggle",
                            className="collapsible-header",
                        ),
                        dbc.Collapse(
                            html.Div(
                                id=f"{self.component_id}-history-section",
                                children=[],
                            ),
                            id=f"{self.component_id}-history-collapse",
                            is_open=True,
                        ),
                    ],
                    style={"marginTop": "10px"},
                ),
                # ── Data Stores ──
                dcc.Store(id=f"{self.component_id}-training-state-store", data={}),
                dcc.Store(id=f"{self.component_id}-pool-history-store", storage_type="memory", data=[]),
                dcc.Interval(
                    id=f"{self.component_id}-update-interval",
                    interval=self.update_interval,
                    n_intervals=0,
                ),
            ],
            style={"padding": "15px"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for candidate metrics panel.

        Args:
            app: Dash application instance
        """

        # ── Fetch training state (only when tab is active) ──
        @app.callback(
            Output(f"{self.component_id}-training-state-store", "data"),
            [
                Input(f"{self.component_id}-update-interval", "n_intervals"),
                Input("visualization-tabs", "active_tab"),
            ],
        )
        def fetch_training_state(n_intervals, active_tab):
            if active_tab != "candidates":
                return dash.no_update
            return self._fetch_training_state()

        # ── Update status display ──
        @app.callback(
            [
                Output(f"{self.component_id}-status-badge", "children"),
                Output(f"{self.component_id}-status-badge", "style"),
                Output(f"{self.component_id}-phase", "children"),
                Output(f"{self.component_id}-pool-size", "children"),
            ],
            [Input(f"{self.component_id}-training-state-store", "data")],
        )
        def update_status_display(state):
            if not state:
                return "Inactive", self._get_status_style("idle"), "Idle", "0"
            pool_status = state.get("candidate_pool_status", "Inactive")
            pool_phase = state.get("candidate_pool_phase", "Idle")
            pool_size = state.get("candidate_pool_size", 0)
            return pool_status, self._get_status_style(pool_phase), pool_phase, str(pool_size)

        # ── Update epoch progress ──
        @app.callback(
            [
                Output(f"{self.component_id}-progress-section", "style"),
                Output(f"{self.component_id}-epoch-progress", "value"),
                Output(f"{self.component_id}-epoch-progress", "label"),
            ],
            [Input(f"{self.component_id}-training-state-store", "data")],
        )
        def update_epoch_progress(state):
            if not state:
                return {"display": "none"}, 0, ""
            cand_epoch = state.get("candidate_epoch")
            cand_total = state.get("candidate_total_epochs")
            if cand_epoch is not None and cand_total:
                pct = min(100, int(100 * cand_epoch / cand_total))
                label = f"{cand_epoch}/{cand_total}"
                return {"display": "block"}, pct, label
            return {"display": "none"}, 0, ""

        # ── Update pool info ──
        @app.callback(
            Output(f"{self.component_id}-pool-info", "children"),
            [Input(f"{self.component_id}-training-state-store", "data")],
        )
        def update_pool_info(state):
            if not state:
                return html.Div(
                    "No active candidate pool",
                    style={"color": "var(--text-muted)", "fontStyle": "italic", "padding": "10px"},
                )
            pool_status = state.get("candidate_pool_status", "Inactive")
            if pool_status == "Inactive":
                return html.Div(
                    "No active candidate pool",
                    style={"color": "var(--text-muted)", "fontStyle": "italic", "padding": "10px"},
                )
            return self._create_candidate_pool_display(state)

        # ── Update candidate loss plot ──
        @app.callback(
            Output(f"{self.component_id}-loss-plot", "figure"),
            [
                Input(f"{self.component_id}-training-state-store", "data"),
                Input("theme-state", "data"),
            ],
        )
        def update_loss_plot(state, theme):
            return self._create_candidate_loss_figure(state, theme=theme or "light")

        # ── Toggle pool details collapse ──
        @app.callback(
            [
                Output(f"{self.component_id}-pool-collapse", "is_open"),
                Output(f"{self.component_id}-toggle-icon", "children"),
            ],
            Input(f"{self.component_id}-candidate-toggle", "n_clicks"),
            State(f"{self.component_id}-pool-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_pool_details(n_clicks, is_open):
            if n_clicks:
                new_state = not is_open
                return new_state, "▼" if new_state else "▶"
            return is_open, "▼"

        # ── Update pool history ──
        @app.callback(
            Output(f"{self.component_id}-pool-history-store", "data"),
            Input(f"{self.component_id}-training-state-store", "data"),
            State(f"{self.component_id}-pool-history-store", "data"),
        )
        def update_pool_history(state, history):
            if not state:
                return history or []

            pool_status = state.get("candidate_pool_status", "Inactive")
            current_epoch = state.get("current_epoch", 0)

            if pool_status != "Inactive":
                pool_snapshot = {
                    "epoch": current_epoch,
                    "status": pool_status,
                    "phase": state.get("candidate_pool_phase", "Idle"),
                    "size": state.get("candidate_pool_size", 0),
                    "top_candidate_id": state.get("top_candidate_id", ""),
                    "top_candidate_score": state.get("top_candidate_score", 0.0),
                    "second_candidate_id": state.get("second_candidate_id", ""),
                    "second_candidate_score": state.get("second_candidate_score", 0.0),
                    "pool_metrics": state.get("pool_metrics", {}),
                    "timestamp": time.time(),
                }

                current_history = history or []
                existing = next((p for p in current_history if p.get("epoch") == current_epoch), None)

                if not existing:
                    current_history = [pool_snapshot] + current_history[: MAX_POOL_HISTORY_ENTRIES - 1]
                    return current_history

            return history or []

        # ── Render pool history ──
        @app.callback(
            Output(f"{self.component_id}-history-section", "children"),
            Input(f"{self.component_id}-pool-history-store", "data"),
        )
        def render_pool_history(history):
            return self._render_pool_history(history)

        # ── Toggle history collapse ──
        @app.callback(
            [
                Output(f"{self.component_id}-history-collapse", "is_open"),
                Output(f"{self.component_id}-history-icon", "children"),
            ],
            Input(f"{self.component_id}-history-toggle", "n_clicks"),
            State(f"{self.component_id}-history-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_history(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

    # ── Data Fetching ──

    def _fetch_training_state(self) -> Dict[str, Any]:
        """Fetch training state from backend API."""
        import requests

        try:
            response = requests.get(self._api_url("/api/state"), timeout=2)
            if response.status_code == 200:
                data: Dict[str, Any] = response.json()
                return data
        except Exception:
            self.logger.debug("Failed to fetch training state")
        return {}

    # ── Display Builders ──

    def _create_candidate_pool_display(self, state: Dict[str, Any]) -> html.Div:
        """
        Create candidate pool information display.

        Args:
            state: Training state dictionary with candidate pool data

        Returns:
            Dash Div with candidate pool information
        """
        top_cand_id = state.get("top_candidate_id", "")
        top_cand_score = state.get("top_candidate_score", 0.0)
        second_cand_id = state.get("second_candidate_id", "")
        second_cand_score = state.get("second_candidate_score", 0.0)
        pool_metrics = state.get("pool_metrics", {})

        # Top 2 candidates table
        candidate_rows = []
        if top_cand_id:
            candidate_rows.append(
                html.Tr(
                    [
                        html.Td("1", style={"padding": "6px 10px", "fontWeight": "600"}),
                        html.Td(top_cand_id, style={"padding": "6px 10px"}),
                        html.Td(f"{top_cand_score:.4f}", style={"padding": "6px 10px", "textAlign": "right"}),
                    ]
                )
            )
        if second_cand_id:
            candidate_rows.append(
                html.Tr(
                    [
                        html.Td("2", style={"padding": "6px 10px", "fontWeight": "600"}),
                        html.Td(second_cand_id, style={"padding": "6px 10px"}),
                        html.Td(f"{second_cand_score:.4f}", style={"padding": "6px 10px", "textAlign": "right"}),
                    ]
                )
            )

        candidates_table = html.Table(
            [
                html.Thead(
                    html.Tr(
                        [
                            html.Th(
                                "Rank",
                                style={"padding": "6px 10px", "textAlign": "left", "borderBottom": "2px solid var(--border-color)"},
                            ),
                            html.Th(
                                "Candidate ID",
                                style={"padding": "6px 10px", "textAlign": "left", "borderBottom": "2px solid var(--border-color)"},
                            ),
                            html.Th(
                                "Correlation",
                                style={
                                    "padding": "6px 10px",
                                    "textAlign": "right",
                                    "borderBottom": "2px solid var(--border-color)",
                                },
                            ),
                        ]
                    )
                ),
                (
                    html.Tbody(candidate_rows)
                    if candidate_rows
                    else html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(
                                        "No candidates",
                                        colSpan=3,
                                        style={"padding": "10px", "textAlign": "center", "color": "#888"},
                                    )
                                ]
                            )
                        ]
                    )
                ),
            ],
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "borderRadius": "4px",
                "marginBottom": "15px",
            },
        )

        # Pool metrics
        pool_metrics_rows = [
            ("Avg Loss", f"{pool_metrics.get('avg_loss', 0.0):.4f}"),
            ("Avg Accuracy", f"{pool_metrics.get('avg_accuracy', 0.0):.4f}"),
            ("Avg Precision", f"{pool_metrics.get('avg_precision', 0.0):.4f}"),
            ("Avg Recall", f"{pool_metrics.get('avg_recall', 0.0):.4f}"),
            ("Avg F1 Score", f"{pool_metrics.get('avg_f1_score', 0.0):.4f}"),
        ]

        pool_metrics_table = html.Table(
            [
                html.Tbody(
                    [
                        html.Tr(
                            [
                                html.Td(label, style={"fontWeight": "600", "padding": "4px 8px", "fontSize": "13px"}),
                                html.Td(value, style={"padding": "4px 8px", "fontSize": "13px", "textAlign": "right"}),
                            ]
                        )
                        for label, value in pool_metrics_rows
                    ]
                ),
            ],
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "borderRadius": "4px",
            },
        )

        return html.Div(
            [
                html.H6("Top 2 Candidates", style={"marginBottom": "10px"}),
                candidates_table,
                html.H6("Pool Training Metrics", style={"marginTop": "15px", "marginBottom": "10px"}),
                pool_metrics_table,
            ]
        )

    def _create_candidate_loss_figure(self, state: Dict[str, Any] = None, theme: str = "light") -> go.Figure:
        """
        Create candidate training loss plot.

        Args:
            state: Training state dictionary
            theme: Current theme ("light" or "dark")

        Returns:
            Plotly figure with candidate loss trace
        """
        fig = go.Figure()
        is_dark = theme == "dark"

        if not state:
            return create_empty_plot("No candidate data available", theme=theme)

        # Extract candidate-phase data from training history
        epochs = state.get("epochs", [])
        losses = state.get("losses", [])
        phases = state.get("phases", [])

        if not epochs or not losses or not phases:
            return create_empty_plot("No candidate data available", theme=theme)

        candidate_epochs = [e for e, p in zip(epochs, phases, strict=False) if "candidate" in p]
        candidate_losses = [lo for lo, p in zip(losses, phases, strict=False) if "candidate" in p]

        if candidate_epochs:
            is_dark = theme == "dark"
            fig.add_trace(
                go.Scatter(
                    x=candidate_epochs,
                    y=candidate_losses,
                    mode="lines+markers",
                    name="Candidate Training",
                    line={"color": "#ff7f0e", "width": 2},
                    marker={"size": 6},
                )
            )

            fig.update_layout(
                xaxis_title="Epoch",
                yaxis_title="Loss",
                template="plotly_dark" if is_dark else "plotly",
                plot_bgcolor="#242424" if is_dark else "#f8f9fa",
                paper_bgcolor="#242424" if is_dark else "#ffffff",
                font={"color": "#e9ecef" if is_dark else "#212529"},
                margin={"l": 50, "r": 20, "t": 20, "b": 40},
                showlegend=True,
                legend={"x": 0, "y": 1},
            )
        else:
            return create_empty_plot("No candidate data available", theme=theme)

        return fig

    def _get_status_style(self, phase: str) -> Dict[str, str]:
        """Get status badge style based on training phase."""
        base_style = {
            "display": "inline-block",
            "padding": "3px 8px",
            "color": "white",
            "borderRadius": "3px",
            "fontSize": "12px",
        }

        phase_lower = phase.lower() if phase else ""

        if "output" in phase_lower:
            base_style["backgroundColor"] = "#007bff"
        elif "candidate" in phase_lower:
            base_style["backgroundColor"] = "#ffc107"
            base_style["color"] = "#000"
        elif "complete" in phase_lower or "converged" in phase_lower:
            base_style["backgroundColor"] = "#28a745"
        else:
            base_style["backgroundColor"] = "#6c757d"

        return base_style

    def _render_pool_history(self, history) -> list:
        """Render historical candidate pools as expandable cards."""
        if not history:
            return [
                html.Div(
                    "No pool history yet",
                    style={"color": "var(--text-muted)", "fontStyle": "italic", "padding": "10px"},
                )
            ]

        history_items = []
        for pool in history:
            epoch = pool.get("epoch", 0)
            top_id = pool.get("top_candidate_id", "N/A")
            top_score = pool.get("top_candidate_score", 0.0)

            pm = pool.get("pool_metrics", {})
            metrics_rows = []
            if pm:
                metrics_rows = [
                    html.Hr(style={"margin": "8px 0"}),
                    html.P([html.Strong("Avg Loss: "), f"{pm.get('avg_loss', 0):.4f}"]),
                    html.P([html.Strong("Avg Accuracy: "), f"{pm.get('avg_accuracy', 0):.4f}"]),
                ]

            second_rows = []
            if pool.get("second_candidate_id"):
                second_rows = [
                    html.P([html.Strong("2nd Candidate: "), pool.get("second_candidate_id", "N/A")]),
                    html.P([html.Strong("2nd Score: "), f"{pool.get('second_candidate_score', 0.0):.4f}"]),
                ]

            history_items.append(
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.Div(
                                [
                                    html.Span(f"Pool @ Iteration {epoch}", style={"fontWeight": "600"}),
                                    html.Span(
                                        f" - Best: {top_id} ({top_score:.3f})",
                                        style={"color": "var(--text-muted)", "fontSize": "12px"},
                                    ),
                                ]
                            ),
                            style={"padding": "8px 12px", "cursor": "pointer"},
                            id={"type": f"{self.component_id}-history-pool-header", "index": epoch},
                        ),
                        dbc.Collapse(
                            dbc.CardBody(
                                html.Div(
                                    [
                                        html.P([html.Strong("Size: "), str(pool.get("size", 0))]),
                                        html.P([html.Strong("Top Candidate: "), pool.get("top_candidate_id", "N/A")]),
                                        html.P([html.Strong("Score: "), f"{pool.get('top_candidate_score', 0.0):.4f}"]),
                                    ]
                                    + second_rows
                                    + metrics_rows
                                ),
                                style={"padding": "10px"},
                            ),
                            id={"type": f"{self.component_id}-history-pool-collapse", "index": epoch},
                            is_open=False,
                        ),
                    ],
                    style={"marginBottom": "5px"},
                )
            )

        return history_items
