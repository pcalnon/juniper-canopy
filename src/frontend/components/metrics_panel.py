#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     metrics_panel.py
# Author:        Paul Calnon
# Version:       1.4.0
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This file contains the code to Display the Metrics Panel for the Cascade Correlation
#       Neural Network prototype in the Juniper prototype Frontend for monitoring
#       and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#
#     Metrics Panel Component
#
#     Real-time visualization of training metrics including loss, accuracy,
#     learning rate, and training phase indicators.
#     Color-coded plots for output vs candidate training phases.
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
# import logging
# from typing import Dict, Any, List, Optional
import os
import time
from typing import Any, Dict, List, Tuple

# from plotly.subplots import make_subplots
import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output, State

from config_manager import ConfigManager

from ..base_component import BaseComponent

# from constants import DashboardConstants


class MetricsPanel(BaseComponent):
    """
    Training metrics visualization component.

    Displays real-time plots of:
    - Training loss over epochs
    - Accuracy over epochs
    - Learning rate schedule
    - Training phase indicators (output training vs candidate training)
    - Current network statistics
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "metrics-panel"):
        """
        Initialize metrics panel component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        # Initialize ConfigManager for component configuration
        self.config_mgr = ConfigManager()

        # Get metrics panel configuration with environment variable support
        # Configuration hierarchy:
        # 1. Component config dict passed in (highest priority for test compatibility)
        # 2. Environment variables (JUNIPER_CANOPY_METRICS_*)
        # 3. Component defaults (1000 for both max_data_points and update_interval)
        # Note: YAML config is NOT used for max_data_points and update_interval to maintain
        # test compatibility and clear component defaults

        metrics_config = self.config_mgr.config.get("frontend", {}).get("training_metrics", {})

        # Update interval (milliseconds)
        # Priority: 1. Passed config, 2. Environment variable, 3. Default (1000ms)
        if "update_interval" in config:
            self.update_interval = config["update_interval"]
        elif update_interval_env := os.getenv("JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS"):
            try:
                self.update_interval = int(update_interval_env)
                self.logger.info(f"Update interval overridden by env var: {update_interval_env}ms")
            except ValueError:
                self.logger.warning(f"Invalid JUNIPER_CANOPY_METRICS_UPDATE_INTERVAL_MS: {update_interval_env}")
                self.update_interval = 1000  # Default: 1000ms
        else:
            self.update_interval = 1000  # Default: 1000ms

        # Buffer size (max data points)
        # Priority: 1. Passed config, 2. Environment variable, 3. Default (1000)
        if "max_data_points" in config:
            self.max_data_points = config["max_data_points"]
        elif buffer_size_env := os.getenv("JUNIPER_CANOPY_METRICS_BUFFER_SIZE"):
            try:
                self.max_data_points = int(buffer_size_env)
                self.logger.info(f"Buffer size overridden by env var: {buffer_size_env}")
            except ValueError:
                self.logger.warning(f"Invalid JUNIPER_CANOPY_METRICS_BUFFER_SIZE: {buffer_size_env}")
                self.max_data_points = 1000  # Default: 1000
        else:
            self.max_data_points = 1000  # Default: 1000

        if smoothing_env := os.getenv("JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW"):
            try:
                self.smoothing_window = int(smoothing_env)
                self.logger.info(f"Smoothing window overridden by env var: {smoothing_env}")
            except ValueError:
                self.logger.warning(f"Invalid JUNIPER_CANOPY_METRICS_SMOOTHING_WINDOW: {smoothing_env}")
                self.smoothing_window = metrics_config.get("smoothing_window", 10)
        else:
            self.smoothing_window = metrics_config.get("smoothing_window", 10)

        # Data buffers
        self.metrics_history: List[Dict[str, Any]] = []

        self.logger.info(
            f"MetricsPanel initialized: "
            f"update_interval={self.update_interval}ms, "
            f"max_data_points={self.max_data_points}, "
            f"smoothing_window={self.smoothing_window}"
        )

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for metrics panel.

        Returns:
            Dash Div containing the metrics visualization
        """
        return html.Div(
            [
                # Header
                html.Div(
                    [
                        html.H3("Training Metrics", style={"display": "inline-block"}),
                        html.Div(
                            id=f"{self.component_id}-status",
                            children="Status: Idle",
                            style={
                                "display": "inline-block",
                                "marginLeft": "20px",
                                "padding": "5px 10px",
                                "backgroundColor": "#6c757d",
                                "color": "white",
                                "borderRadius": "3px",
                                "fontSize": "14px",
                            },
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                # Replay Controls
                html.Div(
                    id=f"{self.component_id}-replay-controls",
                    children=[
                        html.Div(
                            [
                                dbc.Button(
                                    "⏮",
                                    id=f"{self.component_id}-replay-start",
                                    size="sm",
                                    color="secondary",
                                    className="me-1",
                                    title="Go to start",
                                ),
                                dbc.Button(
                                    "◀",
                                    id=f"{self.component_id}-replay-step-back",
                                    size="sm",
                                    color="secondary",
                                    className="me-1",
                                    title="Step backward",
                                ),
                                dbc.Button(
                                    "▶",
                                    id=f"{self.component_id}-replay-play",
                                    size="sm",
                                    color="primary",
                                    className="me-1",
                                    title="Play/Pause",
                                ),
                                dbc.Button(
                                    "▶",
                                    id=f"{self.component_id}-replay-step-forward",
                                    size="sm",
                                    color="secondary",
                                    className="me-1",
                                    title="Step forward",
                                ),
                                dbc.Button(
                                    "⏭",
                                    id=f"{self.component_id}-replay-end",
                                    size="sm",
                                    color="secondary",
                                    className="me-1",
                                    title="Go to end",
                                ),
                                html.Span("|", style={"margin": "0 10px", "color": "#ccc"}),
                                dbc.ButtonGroup(
                                    [
                                        dbc.Button(
                                            "1x",
                                            id=f"{self.component_id}-speed-1x",
                                            size="sm",
                                            color="info",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "2x",
                                            id=f"{self.component_id}-speed-2x",
                                            size="sm",
                                            color="info",
                                            outline=True,
                                        ),
                                        dbc.Button(
                                            "4x",
                                            id=f"{self.component_id}-speed-4x",
                                            size="sm",
                                            color="info",
                                            outline=True,
                                        ),
                                    ],
                                    size="sm",
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
                        ),
                        # Progress slider
                        html.Div(
                            [
                                html.Span(
                                    id=f"{self.component_id}-replay-position",
                                    children="0 / 0",
                                    style={"marginRight": "10px", "fontSize": "12px", "minWidth": "60px"},
                                ),
                                dcc.Slider(
                                    id=f"{self.component_id}-replay-slider",
                                    min=0,
                                    max=100,
                                    value=0,
                                    marks=None,
                                    tooltip={"placement": "bottom", "always_visible": False},
                                    updatemode="drag",
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                    ],
                    style={
                        "marginBottom": "15px",
                        "padding": "10px",
                        "backgroundColor": "#f8f9fa",
                        "borderRadius": "5px",
                        "display": "none",
                    },
                ),
                # Current metrics display
                html.Div(
                    [
                        html.Div(
                            [
                                html.H5("Current Epoch"),
                                html.H2(
                                    id=f"{self.component_id}-current-epoch", children="0", style={"color": "#007bff"}
                                ),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                        html.Div(
                            [
                                html.H5("Loss"),
                                html.H2(
                                    id=f"{self.component_id}-current-loss", children="--", style={"color": "#dc3545"}
                                ),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                        html.Div(
                            [
                                html.H5("Accuracy"),
                                html.H2(
                                    id=f"{self.component_id}-current-accuracy",
                                    children="--",
                                    style={"color": "#28a745"},
                                ),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                        html.Div(
                            [
                                html.H5("Hidden Units"),
                                html.H2(
                                    id=f"{self.component_id}-hidden-units", children="0", style={"color": "#17a2b8"}
                                ),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                    ],
                    style={"display": "flex", "justifyContent": "space-around", "marginBottom": "20px", "gap": "10px"},
                ),
                # Plots
                dcc.Graph(
                    id=f"{self.component_id}-loss-plot",
                    config={"displayModeBar": True, "displaylogo": False},
                    style={"height": "300px"},
                ),
                dcc.Graph(
                    id=f"{self.component_id}-accuracy-plot",
                    config={"displayModeBar": True, "displaylogo": False},
                    style={"height": "300px"},
                ),
                # Network Information: Details section has been moved to left sidebar in dashboard_manager.py
                # Candidate Pool Section - always visible with collapsible content
                html.Div(
                    id=f"{self.component_id}-candidate-pool-section",
                    children=[
                        html.H4(
                            [
                                "Candidate Pool ",
                                html.Span(
                                    "▼",
                                    id=f"{self.component_id}-candidate-toggle-icon",
                                    style={"cursor": "pointer", "fontSize": "12px", "marginLeft": "5px"},
                                ),
                            ],
                            id=f"{self.component_id}-candidate-toggle",
                            style={"marginTop": "20px", "marginBottom": "10px", "cursor": "pointer"},
                        ),
                        dbc.Collapse(
                            id=f"{self.component_id}-candidate-collapse",
                            is_open=True,
                            children=[
                                html.Div(id=f"{self.component_id}-candidate-pool-info", children=[]),
                            ],
                        ),
                        # Historical pools section
                        html.Div(
                            id=f"{self.component_id}-candidate-history-section",
                            children=[],
                            style={"marginTop": "10px"},
                        ),
                    ],
                    style={"marginTop": "20px"},
                ),
                # Data store for metrics
                dcc.Store(id=f"{self.component_id}-metrics-store", data=[]),
                dcc.Store(id=f"{self.component_id}-network-stats-store", data={}),
                dcc.Store(id=f"{self.component_id}-training-state-store", data={}),
                # Candidate pool history store (keyed by pool ID, contains all completed pools)
                dcc.Store(id=f"{self.component_id}-candidate-pools-history", data=[]),
                # View state store for preserving graph zoom/pan
                dcc.Store(
                    id=f"{self.component_id}-view-state",
                    data={
                        "loss_xaxis_range": None,
                        "loss_yaxis_range": None,
                        "accuracy_xaxis_range": None,
                        "accuracy_yaxis_range": None,
                    },
                ),
                # Update interval
                dcc.Interval(id=f"{self.component_id}-update-interval", interval=self.update_interval, n_intervals=0),
                dcc.Interval(id=f"{self.component_id}-stats-update-interval", interval=5000, n_intervals=0),
                # Replay functionality stores
                dcc.Store(
                    id=f"{self.component_id}-replay-state",
                    data={
                        "mode": "stopped",
                        "speed": 1.0,
                        "current_index": 0,
                        "start_index": 0,
                        "end_index": None,
                    },
                ),
                dcc.Interval(
                    id=f"{self.component_id}-replay-interval",
                    interval=1000,
                    disabled=True,
                    n_intervals=0,
                ),
            ],
            style={"padding": "20px"},
        )

    # NOTE: Network info callback moved to dashboard_manager.py (now in left sidebar)
    def register_callbacks(self, app):
        """
        Register Dash callbacks for metrics panel.

        Args:
            app: Dash application instance
        """

        @app.callback(
            Output(f"{self.component_id}-network-stats-store", "data"),
            [Input(f"{self.component_id}-stats-update-interval", "n_intervals")],
        )
        def fetch_network_stats(n_intervals):
            return self._fetch_network_stats_handler(n_intervals=n_intervals)

        @app.callback(
            Output(f"{self.component_id}-training-state-store", "data"),
            [Input(f"{self.component_id}-stats-update-interval", "n_intervals")],
        )
        def fetch_training_state(n_intervals):
            return self._fetch_training_state_handler(n_intervals=n_intervals)

        # NOTE: Network info callback moved to dashboard_manager.py (now in left sidebar)
        @app.callback(
            [
                Output(f"{self.component_id}-candidate-pool-info", "children"),
                Output(f"{self.component_id}-candidate-pool-section", "style"),
            ],
            [Input(f"{self.component_id}-training-state-store", "data")],
        )
        def update_candidate_pool(state):
            return self._update_candidate_pool_handler(state=state)

        @app.callback(
            [
                Output(f"{self.component_id}-candidate-collapse", "is_open"),
                Output(f"{self.component_id}-candidate-toggle-icon", "children"),
            ],
            Input(f"{self.component_id}-candidate-toggle", "n_clicks"),
            State(f"{self.component_id}-candidate-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_candidate_section(n_clicks, is_open):
            """Toggle candidate pool section visibility."""
            if n_clicks:
                new_state = not is_open
                icon = "▼" if new_state else "▶"
                return new_state, icon
            return is_open, "▼"

        @app.callback(
            Output(f"{self.component_id}-candidate-pools-history", "data"),
            Input(f"{self.component_id}-training-state-store", "data"),
            State(f"{self.component_id}-candidate-pools-history", "data"),
        )
        def update_candidate_history(state, history):
            """Update candidate pool history when a pool completes."""
            if not state:
                return history or []

            pool_status = state.get("candidate_pool_status", "Inactive")
            pool_phase = state.get("candidate_pool_phase", "Idle")
            current_epoch = state.get("current_epoch", 0)

            # Create pool snapshot if we have active pool data
            if pool_status != "Inactive":
                pool_snapshot = {
                    "epoch": current_epoch,
                    "status": pool_status,
                    "phase": pool_phase,
                    "size": state.get("candidate_pool_size", 0),
                    "top_candidate_id": state.get("top_candidate_id", ""),
                    "top_candidate_score": state.get("top_candidate_score", 0.0),
                    "second_candidate_id": state.get("second_candidate_id", ""),
                    "second_candidate_score": state.get("second_candidate_score", 0.0),
                    "pool_metrics": state.get("pool_metrics", {}),
                    "timestamp": time.time(),
                }

                # Check if this pool is already in history (by epoch)
                current_history = history or []
                existing = next((p for p in current_history if p.get("epoch") == current_epoch), None)

                if not existing:
                    # Add new pool to history (max 10 entries)
                    current_history = [pool_snapshot] + current_history[:9]
                    return current_history

            return history or []

        @app.callback(
            Output(f"{self.component_id}-candidate-history-section", "children"),
            Input(f"{self.component_id}-candidate-pools-history", "data"),
        )
        def render_candidate_history(history):
            """Render historical candidate pools as collapsed sections."""
            if not history or len(history) <= 1:
                return []

            # Skip the first (current) pool, show rest as collapsed
            history_items = []
            for pool in history[1:]:
                epoch = pool.get("epoch", 0)
                top_id = pool.get("top_candidate_id", "N/A")
                top_score = pool.get("top_candidate_score", 0.0)

                history_items.append(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.Div(
                                    [
                                        html.Span(f"Pool @ Epoch {epoch}", style={"fontWeight": "600"}),
                                        html.Span(
                                            f" - Best: {top_id} ({top_score:.3f})",
                                            style={"color": "#6c757d", "fontSize": "12px"},
                                        ),
                                    ]
                                ),
                                style={"padding": "8px 12px", "cursor": "pointer"},
                                id={"type": "history-pool-header", "index": epoch},
                            ),
                            dbc.Collapse(
                                dbc.CardBody(
                                    html.Div(
                                        [
                                            html.P([html.Strong("Size: "), str(pool.get("size", 0))]),
                                            html.P(
                                                [html.Strong("Top Candidate: "), pool.get("top_candidate_id", "N/A")]
                                            ),
                                            html.P(
                                                [html.Strong("Score: "), f"{pool.get('top_candidate_score', 0.0):.4f}"]
                                            ),
                                        ]
                                    ),
                                    style={"padding": "10px"},
                                ),
                                id={"type": "history-pool-collapse", "index": epoch},
                                is_open=False,
                            ),
                        ],
                        style={"marginBottom": "5px"},
                    )
                )

            if history_items:
                return html.Div(
                    [
                        html.H6(
                            "Previous Pools", style={"marginTop": "15px", "marginBottom": "10px", "color": "#6c757d"}
                        ),
                        *history_items,
                    ]
                )
            return []

        @app.callback(
            Output(f"{self.component_id}-view-state", "data"),
            [
                Input(f"{self.component_id}-loss-plot", "relayoutData"),
                Input(f"{self.component_id}-accuracy-plot", "relayoutData"),
            ],
            State(f"{self.component_id}-view-state", "data"),
            prevent_initial_call=True,
        )
        def capture_view_state(loss_relayout, accuracy_relayout, current_state):
            """Capture user's zoom/pan state from graphs."""
            ctx = dash.callback_context
            if not ctx.triggered:
                return current_state or {}

            trigger = ctx.triggered[0]["prop_id"].split(".")[0]
            new_state = current_state.copy() if current_state else {}

            if "loss-plot" in trigger and loss_relayout:
                if "xaxis.range[0]" in loss_relayout:
                    new_state["loss_xaxis_range"] = [
                        loss_relayout["xaxis.range[0]"],
                        loss_relayout["xaxis.range[1]"],
                    ]
                if "yaxis.range[0]" in loss_relayout:
                    new_state["loss_yaxis_range"] = [
                        loss_relayout["yaxis.range[0]"],
                        loss_relayout["yaxis.range[1]"],
                    ]
                if loss_relayout.get("xaxis.autorange"):
                    new_state["loss_xaxis_range"] = None
                if loss_relayout.get("yaxis.autorange"):
                    new_state["loss_yaxis_range"] = None

            if "accuracy-plot" in trigger and accuracy_relayout:
                if "xaxis.range[0]" in accuracy_relayout:
                    new_state["accuracy_xaxis_range"] = [
                        accuracy_relayout["xaxis.range[0]"],
                        accuracy_relayout["xaxis.range[1]"],
                    ]
                if "yaxis.range[0]" in accuracy_relayout:
                    new_state["accuracy_yaxis_range"] = [
                        accuracy_relayout["yaxis.range[0]"],
                        accuracy_relayout["yaxis.range[1]"],
                    ]
                if accuracy_relayout.get("xaxis.autorange"):
                    new_state["accuracy_xaxis_range"] = None
                if accuracy_relayout.get("yaxis.autorange"):
                    new_state["accuracy_yaxis_range"] = None

            return new_state

        @app.callback(
            [
                Output(f"{self.component_id}-loss-plot", "figure"),
                Output(f"{self.component_id}-accuracy-plot", "figure"),
                Output(f"{self.component_id}-current-epoch", "children"),
                Output(f"{self.component_id}-current-loss", "children"),
                Output(f"{self.component_id}-current-accuracy", "children"),
                Output(f"{self.component_id}-hidden-units", "children"),
                Output(f"{self.component_id}-status", "children"),
                Output(f"{self.component_id}-status", "style"),
            ],
            [
                Input(f"{self.component_id}-metrics-store", "data"),
                Input("theme-state", "data"),
            ],
            State(f"{self.component_id}-view-state", "data"),
        )
        def update_metrics_display(metrics_data: List[Dict[str, Any]], theme: str, view_state: Dict):
            return self._update_metrics_display_handler(metrics_data=metrics_data, theme=theme, view_state=view_state)

        # Replay Controls Callbacks
        @app.callback(
            Output(f"{self.component_id}-replay-controls", "style"),
            [
                Input(f"{self.component_id}-training-state-store", "data"),
                Input("theme-state", "data"),
            ],
        )
        def toggle_replay_visibility(state, theme):
            """Show replay controls when training is not running."""
            is_dark = theme == "dark" if theme else False
            base_style = {
                "marginBottom": "15px",
                "padding": "10px",
                "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
                "borderRadius": "5px",
            }

            if not state:
                return {**base_style, "display": "block"}

            status = state.get("status", "STOPPED").upper()
            if status in ["STOPPED", "PAUSED", "COMPLETED", "FAILED"]:
                return {**base_style, "display": "block"}
            return {**base_style, "display": "none"}

        @app.callback(
            [
                Output(f"{self.component_id}-replay-state", "data"),
                Output(f"{self.component_id}-replay-interval", "disabled"),
                Output(f"{self.component_id}-replay-interval", "interval"),
            ],
            [
                Input(f"{self.component_id}-replay-play", "n_clicks"),
                Input(f"{self.component_id}-replay-step-back", "n_clicks"),
                Input(f"{self.component_id}-replay-step-forward", "n_clicks"),
                Input(f"{self.component_id}-replay-start", "n_clicks"),
                Input(f"{self.component_id}-replay-end", "n_clicks"),
                Input(f"{self.component_id}-speed-1x", "n_clicks"),
                Input(f"{self.component_id}-speed-2x", "n_clicks"),
                Input(f"{self.component_id}-speed-4x", "n_clicks"),
                Input(f"{self.component_id}-replay-slider", "value"),
            ],
            [
                State(f"{self.component_id}-replay-state", "data"),
                State(f"{self.component_id}-metrics-store", "data"),
            ],
            prevent_initial_call=True,
        )
        def handle_replay_controls(
            play_clicks,
            back_clicks,
            forward_clicks,
            start_clicks,
            end_clicks,
            speed_1x,
            speed_2x,
            speed_4x,
            slider_value,
            current_state,
            metrics_data,
        ):
            """Handle replay control button clicks."""
            ctx = dash.callback_context
            if not ctx.triggered:
                return current_state, True, 1000

            trigger = ctx.triggered[0]["prop_id"].split(".")[0]
            state = (
                current_state.copy()
                if current_state
                else {
                    "mode": "stopped",
                    "speed": 1.0,
                    "current_index": 0,
                    "start_index": 0,
                    "end_index": None,
                }
            )

            max_index = len(metrics_data) - 1 if metrics_data else 0
            state["end_index"] = state.get("end_index") or max_index

            if "replay-play" in trigger:
                state["mode"] = "paused" if state["mode"] == "playing" else "playing"
            elif "step-back" in trigger:
                state["mode"] = "paused"
                state["current_index"] = max(0, state["current_index"] - 1)
            elif "step-forward" in trigger:
                state["mode"] = "paused"
                state["current_index"] = min(max_index, state["current_index"] + 1)
            elif "replay-start" in trigger:
                state["current_index"] = state["start_index"]
                state["mode"] = "paused"
            elif "replay-end" in trigger:
                state["current_index"] = state["end_index"] or max_index
                state["mode"] = "paused"
            elif "speed-1x" in trigger:
                state["speed"] = 1.0
            elif "speed-2x" in trigger:
                state["speed"] = 2.0
            elif "speed-4x" in trigger:
                state["speed"] = 4.0
            elif "replay-slider" in trigger:
                state["current_index"] = int((slider_value / 100) * max_index) if max_index > 0 else 0
                state["mode"] = "paused"

            base_interval = 1000
            interval = int(base_interval / state["speed"])
            disabled = state["mode"] != "playing"

            return state, disabled, interval

        @app.callback(
            Output(f"{self.component_id}-replay-state", "data", allow_duplicate=True),
            Input(f"{self.component_id}-replay-interval", "n_intervals"),
            [
                State(f"{self.component_id}-replay-state", "data"),
                State(f"{self.component_id}-metrics-store", "data"),
            ],
            prevent_initial_call=True,
        )
        def replay_tick(n_intervals, state, metrics_data):
            """Advance replay by one step on interval tick."""
            if not state or state["mode"] != "playing":
                return state

            max_index = len(metrics_data) - 1 if metrics_data else 0
            end_index = state.get("end_index") or max_index

            new_index = state["current_index"] + 1
            if new_index > end_index:
                state["mode"] = "stopped"
                state["current_index"] = end_index
            else:
                state["current_index"] = new_index

            return state

        @app.callback(
            [
                Output(f"{self.component_id}-replay-slider", "value"),
                Output(f"{self.component_id}-replay-slider", "max"),
                Output(f"{self.component_id}-replay-position", "children"),
            ],
            [
                Input(f"{self.component_id}-replay-state", "data"),
                Input(f"{self.component_id}-metrics-store", "data"),
            ],
        )
        def update_replay_ui(state, metrics_data):
            """Update replay slider and position display."""
            max_index = len(metrics_data) - 1 if metrics_data else 0
            current_index = state.get("current_index", 0) if state else 0

            slider_value = (current_index / max_index * 100) if max_index > 0 else 0
            position_text = f"{current_index} / {max_index}"

            return slider_value, 100, position_text

        @app.callback(
            Output(f"{self.component_id}-replay-play", "children"),
            Input(f"{self.component_id}-replay-state", "data"),
        )
        def update_play_button(state):
            """Update play button icon based on replay state."""
            return "⏸" if state and state.get("mode") == "playing" else "▶"

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _fetch_network_stats_handler(self, n_intervals=None):
        # sourcery skip: class-extract-method
        """
        Fetch network statistics from API periodically.

        Args:
            n_intervals: Number of intervals elapsed

        Returns:
            Network statistics dictionary
        """
        import requests

        try:
            response = requests.get("http://localhost:8050/api/network/stats", timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.debug(f"Failed to fetch network stats: {e}")

        return {}

    def _fetch_training_state_handler(self, n_intervals=None):
        """
        Fetch training state from API periodically.

        Args:
            n_intervals: Number of intervals elapsed

        Returns:
            Training state dictionary
        """
        import requests

        try:
            response = requests.get("http://localhost:8050/api/state", timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.debug(f"Failed to fetch training state: {e}")

        return {}

    def _update_candidate_pool_handler(self, state=None):
        """
        Update candidate pool display.

        Args:
            state: Training state dictionary

        Returns:
            Tuple of (pool info children, section style)
        """
        if not state:
            return [], {"marginTop": "20px"}

        pool_status = state.get("candidate_pool_status", "Inactive")

        if pool_status == "Inactive":
            return html.Div(
                "No active candidate pool",
                style={"color": "#6c757d", "fontStyle": "italic", "padding": "10px"},
            ), {"marginTop": "20px"}

        return self._create_candidate_pool_display(state), {"marginTop": "20px"}

    def _update_metrics_display_handler(
        self, metrics_data: List[Dict[str, Any]] = None, theme: str = None, view_state: Dict = None
    ):
        """
        Update all metrics visualizations and displays.

        Args:
            metrics_data: List of metrics dictionaries
            theme: Current theme ("light" or "dark")
            view_state: User's saved view state (zoom ranges)

        Returns:
            Tuple of updated components
        """
        # Normalize API/store payload to a list of metric dicts (backward-compatible)
        if isinstance(metrics_data, dict):
            if isinstance(metrics_data.get("history"), list):
                metrics_data = metrics_data["history"]
            elif isinstance(metrics_data.get("data"), list):
                metrics_data = metrics_data["data"]
            else:
                metrics_data = []
        elif not isinstance(metrics_data, list):
            metrics_data = []

        if not metrics_data:
            # Return empty/default state
            empty_fig = self._create_empty_plot(theme)
            return (empty_fig, empty_fig, "0", "--", "--", "0", "Status: Idle", self._get_status_style("idle"))

        # Create plots
        loss_fig = self._create_loss_plot(metrics_data, theme)
        accuracy_fig = self._create_accuracy_plot(metrics_data, theme)

        # Apply stored view state to preserve user's zoom/pan
        if view_state:
            if view_state.get("loss_xaxis_range"):
                loss_fig.update_layout(xaxis_range=view_state["loss_xaxis_range"])
            if view_state.get("loss_yaxis_range"):
                loss_fig.update_layout(yaxis_range=view_state["loss_yaxis_range"])
            if view_state.get("accuracy_xaxis_range"):
                accuracy_fig.update_layout(xaxis_range=view_state["accuracy_xaxis_range"])
            if view_state.get("accuracy_yaxis_range"):
                accuracy_fig.update_layout(yaxis_range=view_state["accuracy_yaxis_range"])

        # Get current values
        latest = metrics_data[-1]
        current_epoch = latest.get("epoch", 0)
        current_loss = latest.get("metrics", {}).get("loss", 0)
        current_accuracy = latest.get("metrics", {}).get("accuracy", 0)
        hidden_units = latest.get("network_topology", {}).get("hidden_units", 0)
        phase = latest.get("phase", "idle")

        # Format current values
        loss_str = f"{current_loss:.4f}" if isinstance(current_loss, (int, float)) else "--"
        accuracy_str = f"{current_accuracy:.2%}" if isinstance(current_accuracy, (int, float)) else "--"

        # Status text and style
        status_text = f'Status: {phase.replace("_", " ").title()}'
        status_style = self._get_status_style(phase)

        return (
            loss_fig,
            accuracy_fig,
            str(current_epoch),
            loss_str,
            accuracy_str,
            str(hidden_units),
            status_text,
            status_style,
        )

    def _create_loss_plot(self, metrics_data: List[Dict[str, Any]], theme: str = "light") -> go.Figure:
        """
        Create loss plot from metrics data.

        Args:
            metrics_data: List of metrics dictionaries
            theme: Current theme ("light" or "dark")

        Returns:
            Plotly figure object
        """
        (epochs, losses, phases) = self._parse_metrics(metrics_data=metrics_data)

        # Create figure with phase-colored scatter
        fig = self._create_phase_colored_scatter(fig=go.Figure(), epochs=epochs, losses=losses, phases=phases)
        fig = self._add_phase_bg_bands(fig=fig, epochs=epochs, phases=phases)
        (fig, epoch) = self._add_hidden_unit_markers(metrics_data=metrics_data, fig=fig, theme=theme, epochs=epochs)

        return fig

    def _parse_metrics(self, metrics_data: List[Dict[str, Any]]) -> Tuple[List, List, List]:
        """
        Parse metrics data into separate lists.
        Args:
            metrics_data: List of metrics dictionaries
        Returns:
            Tuple of epochs, losses, and phases:
                epochs: List of epochs
                losses: List of losses
                phases: List of phases
        """
        epochs = []
        losses = []
        phases = []

        for metric in metrics_data:
            epochs.append(metric.get("epoch", 0))
            losses.append(metric.get("metrics", {}).get("loss", 0))
            phases.append(metric.get("phase", "unknown"))

        return (epochs, losses, phases)

    def _create_phase_colored_scatter(
        self, fig: go.Figure = None, epochs: list = None, losses: list = None, phases: list = None
    ) -> go.Figure:
        """
        Create phase-colored scatter plot from epochs, losses, and phases.
        """
        # Separate data by phase for coloring
        output_epochs = [out_epoch for out_epoch, phase in zip(epochs, phases, strict=False) if "output" in phase]
        output_losses = [out_loss for out_loss, phase in zip(losses, phases, strict=False) if "output" in phase]
        candidate_epochs = [
            cand_epoch for cand_epoch, phase in zip(epochs, phases, strict=False) if "candidate" in phase
        ]
        candidate_losses = [cand_loss for cand_loss, phase in zip(losses, phases, strict=False) if "candidate" in phase]
        fig = self._output_add_trace(fig=fig, output_epochs=output_epochs, output_losses=output_losses)
        fig = self._candidate_add_trace(fig=fig, candidate_epochs=candidate_epochs, candidate_losses=candidate_losses)
        return fig

    def _output_add_trace(
        self, fig: go.Figure = None, output_epochs: list = None, output_losses: list = None
    ) -> go.Figure:
        if output_epochs:
            fig.add_trace(
                go.Scatter(
                    x=output_epochs,
                    y=output_losses,
                    mode="lines+markers",
                    name="Output Training",
                    line={"color": "#1f77b4", "width": 2},
                    marker={"size": 6},
                )
            )
        return fig

    def _candidate_add_trace(
        self, fig: go.Figure = None, candidate_epochs: list = None, candidate_losses: list = None
    ) -> go.Figure:
        if candidate_epochs:
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

        return fig

    def _add_phase_bg_bands(self, fig: go.Figure = None, epochs: list = None, phases: list = None) -> go.Figure:
        # Add phase background bands
        current_phase = None
        phase_start = None
        (fig, current_phase, phase_start) = self._end_prev_phase_band(
            fig=fig, epochs=epochs, phases=phases, current_phase=current_phase, phase_start=phase_start
        )
        (fig, current_phase, phase_start) = self._candidate_final_band(
            fig=fig, epochs=epochs, current_phase=current_phase, phase_start=phase_start
        )
        return fig

    def _end_prev_phase_band(
        self,
        fig: go.Figure = None,
        epochs: list = None,
        phases: list = None,
        current_phase: str = None,
        phase_start: float = None,
    ) -> Tuple[go.Figure, str, float]:
        for i, (epoch, phase) in enumerate(zip(epochs, phases, strict=True)):
            if phase != current_phase:
                # End previous phase band
                if current_phase is not None and "candidate" in current_phase and phase_start is not None:
                    fig.add_shape(
                        type="rect",
                        x0=phase_start,
                        x1=epochs[i - 1] if i > 0 else phase_start,
                        y0=0,
                        y1=1,
                        yref="paper",
                        fillcolor="rgba(255, 193, 7, 0.08)",  # Light yellow for candidate
                        line_width=0,
                        layer="below",
                    )
                current_phase = phase
                phase_start = epoch
        return (fig, current_phase, phase_start)

    def _candidate_final_band(
        self, fig: go.Figure = None, epochs: list = None, current_phase: str = None, phase_start: float = None
    ) -> Tuple[go.Figure, str, float]:
        # Final band if ended in candidate
        if current_phase is not None and "candidate" in current_phase and phase_start is not None:
            fig.add_shape(
                type="rect",
                x0=phase_start,
                x1=epochs[-1],
                y0=0,
                y1=1,
                yref="paper",
                fillcolor="rgba(255, 193, 7, 0.08)",
                line_width=0,
                layer="below",
            )
        return (fig, current_phase, phase_start)

    def _add_hidden_unit_markers(
        self, metrics_data: List[Dict[str, Any]], fig: go.Figure = None, theme: str = "light", epochs: list = None
    ) -> Tuple[go.Figure, list]:
        (fig) = self._hidden_unit_addition_markers(metrics_data=metrics_data, fig=fig, theme=theme)
        fig = self._training_loss_per_time(fig=fig, theme=theme)
        return (fig, epochs)

    def _hidden_unit_addition_markers(
        self, metrics_data: List[Dict[str, Any]], fig: go.Figure = None, theme: str = "light"
    ) -> go.Figure:
        # Add hidden unit addition markers
        for i in range(1, len(metrics_data)):
            prev_hidden = metrics_data[i - 1].get("network_topology", {}).get("hidden_units", 0)
            curr_hidden = metrics_data[i].get("network_topology", {}).get("hidden_units", 0)

            if curr_hidden > prev_hidden:
                epoch = metrics_data[i].get("epoch", 0)
                # Add vertical line
                fig.add_vline(
                    x=epoch,
                    line_dash="dash",
                    line_color="#17a2b8",
                    line_width=2,
                    annotation_text=f"+Unit #{curr_hidden}",
                    annotation_position="top",
                )
        return fig

    def _training_loss_per_time(self, fig: go.Figure = None, theme: str = "light") -> go.Figure:
        is_dark = theme == "dark"
        fig.update_layout(
            title="Training Loss Over Time",
            xaxis_title="Epoch",
            yaxis_title="Loss",
            hovermode="closest",
            showlegend=True,
            legend={"x": 0.7, "y": 0.95},
            margin={"l": 50, "r": 20, "t": 40, "b": 40},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            font={"color": "#e9ecef" if is_dark else "#212529"},
        )
        return fig

    def _create_accuracy_plot(self, metrics_data: List[Dict[str, Any]], theme: str = "light") -> go.Figure:
        """
        Create accuracy plot from metrics data.

        Args:
            metrics_data: List of metrics dictionaries
            theme: Current theme ("light" or "dark")

        Returns:
            Plotly figure object
        """
        epochs = []
        accuracies = []
        phases = []

        for metric in metrics_data:
            epochs.append(metric.get("epoch", 0))
            acc = metric.get("metrics", {}).get("accuracy", 0)
            phases.append(metric.get("phase", "unknown"))
            # Only include accuracy for output training phases
            if "output" in metric.get("phase", ""):
                accuracies.append(acc)
            else:
                accuracies.append(None)  # Gap in plot for candidate training

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=epochs,
                y=accuracies,
                mode="lines+markers",
                name="Accuracy",
                line={"color": "#28a745", "width": 2},
                marker={"size": 6},
                fill="tozeroy",
                fillcolor="rgba(40, 167, 69, 0.1)",
            )
        )

        # Add phase background bands
        current_phase = None
        phase_start = None

        for i, (epoch, phase) in enumerate(zip(epochs, phases, strict=True)):
            if phase != current_phase:
                # End previous phase band
                if current_phase is not None and "candidate" in current_phase and phase_start is not None:
                    fig.add_shape(
                        type="rect",
                        x0=phase_start,
                        x1=epochs[i - 1] if i > 0 else phase_start,
                        y0=0,
                        y1=1,
                        yref="paper",
                        fillcolor="rgba(255, 193, 7, 0.08)",  # Light yellow for candidate
                        line_width=0,
                        layer="below",
                    )
                current_phase = phase
                phase_start = epoch

        # Final band if ended in candidate
        if current_phase is not None and "candidate" in current_phase and phase_start is not None:
            fig.add_shape(
                type="rect",
                x0=phase_start,
                x1=epochs[-1],
                y0=0,
                y1=1,
                yref="paper",
                fillcolor="rgba(255, 193, 7, 0.08)",
                line_width=0,
                layer="below",
            )

        # Add hidden unit addition markers
        for i in range(1, len(metrics_data)):
            prev_hidden = metrics_data[i - 1].get("network_topology", {}).get("hidden_units", 0)
            curr_hidden = metrics_data[i].get("network_topology", {}).get("hidden_units", 0)

            if curr_hidden > prev_hidden:
                epoch = metrics_data[i].get("epoch", 0)
                # Add vertical line
                fig.add_vline(
                    x=epoch,
                    line_dash="dash",
                    line_color="#17a2b8",
                    line_width=2,
                    annotation_text=f"+Unit #{curr_hidden}",
                    annotation_position="top",
                )

        is_dark = theme == "dark"
        fig.update_layout(
            title="Training Accuracy Over Time",
            xaxis_title="Epoch",
            yaxis_title="Accuracy",
            yaxis={"range": [0, 1.0]},
            hovermode="closest",
            margin={"l": 50, "r": 20, "t": 40, "b": 40},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            font={"color": "#e9ecef" if is_dark else "#212529"},
        )

        return fig

    def _create_empty_plot(self, theme: str = "light") -> go.Figure:
        """
        Create empty placeholder plot.

        Args:
            theme: Current theme ("light" or "dark")

        Returns:
            Empty Plotly figure
        """
        fig = go.Figure()

        is_dark = theme == "dark"
        text_color = "#adb5bd" if is_dark else "#6c757d"

        fig.add_annotation(
            text="No data available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": text_color},
        )

        fig.update_layout(
            xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
            yaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            margin={"l": 20, "r": 20, "t": 20, "b": 20},
        )

        return fig

    def _get_status_style(self, phase: str) -> Dict[str, str]:
        """
        Get status badge style based on training phase.

        Args:
            phase: Current training phase

        Returns:
            Style dictionary for status badge
        """
        base_style = {
            "display": "inline-block",
            "marginLeft": "20px",
            "padding": "5px 10px",
            "color": "white",
            "borderRadius": "3px",
            "fontSize": "14px",
        }

        if "output" in phase.lower():
            base_style["backgroundColor"] = "#007bff"  # Blue
        elif "candidate" in phase.lower():
            base_style["backgroundColor"] = "#ffc107"  # Yellow/Orange
            base_style["color"] = "#000"
        elif "complete" in phase.lower() or "converged" in phase.lower():
            base_style["backgroundColor"] = "#28a745"  # Green
        else:
            base_style["backgroundColor"] = "#6c757d"  # Gray (idle)

        return base_style

    def add_metrics(self, metrics: Dict[str, Any]):
        """
        Add new metrics to the history buffer.

        Args:
            metrics: Metrics dictionary to add
        """
        self.metrics_history.append(metrics)

        # Trim buffer if exceeds max size
        if len(self.metrics_history) > self.max_data_points:
            self.metrics_history = self.metrics_history[-self.max_data_points :]

    def clear_metrics(self):
        """Clear all metrics history."""
        self.metrics_history = []
        self.logger.info("Metrics history cleared")

    def get_metrics_history(self) -> List[Dict[str, Any]]:
        """
        Get current metrics history.

        Returns:
            List of metrics dictionaries
        """
        return self.metrics_history.copy()

    def _create_candidate_pool_display(self, state: Dict[str, Any]) -> html.Div:
        """
        Create candidate pool information display.

        Args:
            state: Training state dictionary with candidate pool data

        Returns:
            Dash Div with candidate pool information
        """
        pool_status = state.get("candidate_pool_status", "Inactive")
        pool_phase = state.get("candidate_pool_phase", "Idle")
        pool_size = state.get("candidate_pool_size", 0)
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
                                style={"padding": "6px 10px", "textAlign": "left", "borderBottom": "2px solid #dee2e6"},
                            ),
                            html.Th(
                                "Candidate ID",
                                style={"padding": "6px 10px", "textAlign": "left", "borderBottom": "2px solid #dee2e6"},
                            ),
                            html.Th(
                                "Correlation",
                                style={
                                    "padding": "6px 10px",
                                    "textAlign": "right",
                                    "borderBottom": "2px solid #dee2e6",
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
                "backgroundColor": "#f8f9fa",
                "border": "1px solid #dee2e6",
                "borderRadius": "4px",
                "marginBottom": "15px",
            },
        )

        # Pool status info
        pool_info = html.Div(
            [
                html.Div(
                    [
                        html.Span("Status: ", style={"fontWeight": "600"}),
                        html.Span(pool_status, style={"color": "#28a745" if pool_status == "Active" else "#6c757d"}),
                    ],
                    style={"marginBottom": "5px"},
                ),
                html.Div(
                    [
                        html.Span("Phase: ", style={"fontWeight": "600"}),
                        html.Span(pool_phase),
                    ],
                    style={"marginBottom": "5px"},
                ),
                html.Div(
                    [
                        html.Span("Pool Size: ", style={"fontWeight": "600"}),
                        html.Span(str(pool_size)),
                    ],
                    style={"marginBottom": "15px"},
                ),
            ]
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
                "backgroundColor": "#f8f9fa",
                "border": "1px solid #dee2e6",
                "borderRadius": "4px",
            },
        )

        return html.Div(
            [
                html.H5("Top 2 Candidates", style={"marginBottom": "10px"}),
                candidates_table,
                pool_info,
                html.H5("Pool Training Metrics", style={"marginTop": "15px", "marginBottom": "10px"}),
                pool_metrics_table,
            ]
        )

    def _create_network_info_table(self, stats: Dict[str, Any]) -> html.Div:
        """
        Create network information table from statistics.

        Args:
            stats: Network statistics dictionary

        Returns:
            Dash Div with formatted table
        """
        if not stats:
            return html.Div("Loading network information...", style={"color": "#888", "fontSize": "14px"})

        weight_stats = stats.get("weight_statistics", {})
        z_dist = weight_stats.get("z_score_distribution", {})

        rows = [
            ("Threshold Function", stats.get("threshold_function", "N/A")),
            ("Optimizer", stats.get("optimizer", "N/A")),
            ("Total Nodes", stats.get("total_nodes", 0)),
            ("Total Edges", stats.get("total_edges", 0)),
            ("Total Connections", stats.get("total_connections", 0)),
            ("", ""),
            ("Total Weights", weight_stats.get("total_weights", 0)),
            ("Positive Weights", weight_stats.get("positive_weights", 0)),
            ("Negative Weights", weight_stats.get("negative_weights", 0)),
            ("Zero Weights", weight_stats.get("zero_weights", 0)),
            ("", ""),
            ("Mean", f"{weight_stats.get('mean', 0):.4f}"),
            ("Std Dev", f"{weight_stats.get('std_dev', 0):.4f}"),
            ("Variance", f"{weight_stats.get('variance', 0):.4f}"),
            ("Skewness", f"{weight_stats.get('skewness', 0):.4f}"),
            ("Kurtosis", f"{weight_stats.get('kurtosis', 0):.4f}"),
            ("", ""),
            ("Median", f"{weight_stats.get('median', 0):.4f}"),
            ("MAD", f"{weight_stats.get('mad', 0):.4f}"),
            ("Median AD", f"{weight_stats.get('median_ad', 0):.4f}"),
            ("IQR", f"{weight_stats.get('iqr', 0):.4f}"),
            ("", ""),
            ("Within ±1σ", z_dist.get("within_1_sigma", 0)),
            ("Within ±2σ", z_dist.get("within_2_sigma", 0)),
            ("Within ±3σ", z_dist.get("within_3_sigma", 0)),
            ("Beyond ±3σ", z_dist.get("beyond_3_sigma", 0)),
        ]

        table_rows = []
        for label, value in rows:
            if label == "":
                table_rows.append(
                    html.Tr(
                        [html.Td("", colSpan=2, style={"height": "5px", "padding": "0"})],
                        style={"borderBottom": "1px solid #e0e0e0"},
                    )
                )
            else:
                table_rows.append(
                    html.Tr(
                        [
                            html.Td(label, style={"fontWeight": "600", "padding": "4px 8px", "fontSize": "13px"}),
                            html.Td(str(value), style={"padding": "4px 8px", "fontSize": "13px", "textAlign": "right"}),
                        ]
                    )
                )

        return html.Table(
            [html.Tbody(table_rows)],
            style={
                "width": "100%",
                "borderCollapse": "collapse",
                "backgroundColor": "#f8f9fa",
                "border": "1px solid #dee2e6",
                "borderRadius": "4px",
            },
        )
