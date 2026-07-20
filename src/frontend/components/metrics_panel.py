#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     metrics_panel.py
# Author:        Paul Calnon
# Version:       1.5.0
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
# COMPLETED:
#
#####################################################################################################################################################################################################
# import logging
# from typing import Dict, Any, List, Optional
import os
from typing import Any, Dict, List, Tuple

# from plotly.subplots import make_subplots
import dash
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output, State

from canopy_constants import DashboardConstants
from frontend.internal_api import internal_api_headers
from settings import get_settings

from ..base_component import BaseComponent, create_empty_plot


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

        # Initialize settings for component configuration
        _settings = get_settings()
        self._api_base_url = f"http://127.0.0.1:{_settings.server.port}"

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

        self.smoothing_window = _settings.metrics_smoothing_window

        # Data buffers
        self.metrics_history: List[Dict[str, Any]] = []

        self.logger.info(f"MetricsPanel initialized: " f"update_interval={self.update_interval}ms, " f"max_data_points={self.max_data_points}, " f"smoothing_window={self.smoothing_window}")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for metrics panel.

        Returns:
            Dash Div containing the metrics visualization
        """
        is_dark = False
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
                        html.Div(
                            id=f"{self.component_id}-progress-detail",
                            children="",
                            style={
                                "display": "inline-block",
                                "marginLeft": "15px",
                                "fontSize": "13px",
                                "color": "#adb5bd",
                            },
                        ),
                        html.Span(
                            id=f"{self.component_id}-phase-duration",
                            children="",
                            style={
                                "display": "inline-block",
                                "marginLeft": "15px",
                                "fontSize": "13px",
                                "color": "#adb5bd",
                            },
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                # Layout Save/Load Controls (P3-4)
                html.Div(
                    id=f"{self.component_id}-layout-controls",
                    children=[
                        html.Div(
                            [
                                # Save Layout section
                                html.Div(
                                    [
                                        dbc.Input(
                                            id=f"{self.component_id}-layout-name-input",
                                            placeholder="Layout name...",
                                            type="text",
                                            size="sm",
                                            style={"width": "150px", "display": "inline-block"},
                                        ),
                                        dbc.Button(
                                            "💾 Save",
                                            id=f"{self.component_id}-save-layout-btn",
                                            size="sm",
                                            color="success",
                                            className="ms-2",
                                            title="Save current layout",
                                        ),
                                    ],
                                    style={"display": "inline-flex", "alignItems": "center"},
                                ),
                                html.Span("|", className="metrics-toolbar-divider", style={"margin": "0 15px"}),
                                # Load Layout section
                                html.Div(
                                    [
                                        dcc.Dropdown(
                                            id=f"{self.component_id}-layout-dropdown",
                                            placeholder="Select layout...",
                                            options=[],
                                            style={"width": "180px", "display": "inline-block"},
                                        ),
                                        dbc.Button(
                                            "📂 Load",
                                            id=f"{self.component_id}-load-layout-btn",
                                            size="sm",
                                            color="primary",
                                            className="ms-2",
                                            title="Load selected layout",
                                        ),
                                        dbc.Button(
                                            "🗑️",
                                            id=f"{self.component_id}-delete-layout-btn",
                                            size="sm",
                                            color="danger",
                                            outline=True,
                                            className="ms-1",
                                            title="Delete selected layout",
                                        ),
                                    ],
                                    style={"display": "inline-flex", "alignItems": "center"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        # Status message
                        html.Div(
                            id=f"{self.component_id}-layout-status",
                            children="",
                            className="metrics-layout-status",
                            style={
                                "marginTop": "5px",
                                "fontSize": "12px",
                            },
                        ),
                    ],
                    className="metrics-layout-toolbar",
                    style={
                        "marginBottom": "15px",
                        "padding": "10px",
                        "borderRadius": "5px",
                    },
                ),
                # Store for layout data
                dcc.Store(id=f"{self.component_id}-layout-store", data=None),
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
                                html.Span("|", style={"margin": "0 10px", "color": "var(--border-color)"}),
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
                        "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
                        "borderRadius": "5px",
                        "display": "none",
                    },
                ),
                # Display mode selector
                html.Div(
                    [
                        html.Label("Display Mode:", className="fw-bold me-3", style={"fontSize": "0.85em"}),
                        dbc.RadioItems(
                            id=f"{self.component_id}-display-mode",
                            options=[
                                {"label": "Sliding Window", "value": "window"},
                                {"label": "Full History", "value": "full"},
                                {"label": "Between Hidden Units", "value": "hidden_units"},
                            ],
                            value="window",
                            inline=True,
                            className="me-3",
                            style={"fontSize": "0.85em"},
                        ),
                        html.Div(
                            [
                                html.Label("Window:", className="me-2", style={"fontSize": "0.85em"}),
                                dbc.Input(
                                    id=f"{self.component_id}-window-size",
                                    type="number",
                                    value=DashboardConstants.DEFAULT_SLIDING_WINDOW_SIZE,
                                    min=10,
                                    max=1000,
                                    step=10,
                                    size="sm",
                                    style={"width": "80px", "display": "inline-block"},
                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                ),
                            ],
                            id=f"{self.component_id}-window-size-container",
                            style={"display": "inline-flex", "alignItems": "center"},
                        ),
                    ],
                    className="metrics-layout-toolbar",
                    style={
                        "marginBottom": "10px",
                        "padding": "8px 10px",
                        "borderRadius": "5px",
                        "display": "flex",
                        "alignItems": "center",
                    },
                ),
                # Display mode state store
                dcc.Store(id=f"{self.component_id}-display-mode-store", data={"mode": "window", "window_size": DashboardConstants.DEFAULT_SLIDING_WINDOW_SIZE}),
                # Current metrics display
                html.Div(
                    [
                        html.Div(
                            [
                                html.H5("Training Step"),
                                html.H2(id=f"{self.component_id}-current-epoch", children="0", style={"color": "#007bff"}),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                        html.Div(
                            [
                                html.H5("Loss"),
                                html.H2(id=f"{self.component_id}-current-loss", children="--", style={"color": "#dc3545"}),
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
                                html.H2(id=f"{self.component_id}-hidden-units", children="0", style={"color": "#17a2b8"}),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                        html.Div(
                            [
                                html.H5("Learning Rate"),
                                html.H2(id=f"{self.component_id}-current-lr", children="--", style={"color": "#6f42c1"}),
                            ],
                            className="metric-card",
                            style={"flex": "1", "textAlign": "center", "padding": "15px"},
                        ),
                    ],
                    id=f"{self.component_id}-classification-metrics",
                    style={"display": "flex", "justifyContent": "space-around", "marginBottom": "20px", "gap": "10px"},
                ),
                # A1-iii-b2: one-shot (recurrence / LMU) regression result card. Hidden for a
                # live model; for a one_shot model the classification cards + plots above/below
                # are hidden and this card is shown + populated by ``render_model_class_metrics``.
                html.Div(id=f"{self.component_id}-oneshot-result", style={"display": "none"}),
                # Training progress bars
                html.Div(
                    id=f"{self.component_id}-progress-bars",
                    children=[
                        html.Div(
                            [
                                html.Small("Cascade Iteration", style={"marginRight": "10px", "minWidth": "120px"}),
                                dbc.Progress(
                                    id=f"{self.component_id}-grow-progress",
                                    value=0,
                                    label="",
                                    color="info",
                                    striped=True,
                                    animated=True,
                                    style={"flex": "1", "height": "20px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center", "marginBottom": "5px"},
                        ),
                        html.Div(
                            [
                                html.Small("Candidate Epoch", style={"marginRight": "10px", "minWidth": "110px"}),
                                dbc.Progress(
                                    id=f"{self.component_id}-candidate-epoch-progress",
                                    value=0,
                                    label="",
                                    color="warning",
                                    striped=True,
                                    animated=True,
                                    style={"flex": "1", "height": "20px"},
                                ),
                            ],
                            style={"display": "flex", "alignItems": "center"},
                        ),
                    ],
                    style={"display": "none", "marginBottom": "15px", "padding": "0 10px"},
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
                # Candidate Pool Section moved to CandidateMetricsPanel (candidate_metrics_panel.py)
                # Data store for metrics. Hydrated by the dashboard-level
                # /api/metrics/history poll on every fast-interval tick (1 s) —
                # un-gated per N1 (the bridge posture until WS-primary lands,
                # Q6/C6/N8); the WS extendTraces path remains the chart fast path.
                dcc.Store(id=f"{self.component_id}-metrics-store", data=[]),
                dcc.Store(id=f"{self.component_id}-network-stats-store", data={}),
                dcc.Store(id=f"{self.component_id}-training-state-store", data={}),
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

        # PERF-CN-01: prevent_initial_call=False — must hit the API on mount to
        # populate network stats before the first interval tick.
        @app.callback(
            Output(f"{self.component_id}-network-stats-store", "data"),
            [Input(f"{self.component_id}-stats-update-interval", "n_intervals")],
            prevent_initial_call=False,
        )
        def fetch_network_stats(n_intervals):
            return self._fetch_network_stats_handler(n_intervals=n_intervals)

        # PERF-CN-01: prevent_initial_call=False — must hit the API on mount to
        # populate training state before the first interval tick.
        @app.callback(
            Output(f"{self.component_id}-training-state-store", "data"),
            [Input(f"{self.component_id}-stats-update-interval", "n_intervals")],
            prevent_initial_call=False,
        )
        def fetch_training_state(n_intervals):
            return self._fetch_training_state_handler(n_intervals=n_intervals)

        # Candidate pool callbacks moved to CandidateMetricsPanel (candidate_metrics_panel.py)

        # PERF-CN-01: prevent_initial_call=False — renders default progress text
        # on mount; training-state-store is populated on mount.
        @app.callback(
            Output(f"{self.component_id}-progress-detail", "children"),
            [Input(f"{self.component_id}-training-state-store", "data")],
            prevent_initial_call=False,
        )
        def update_progress_detail(state):
            return self._update_progress_detail_handler(state=state)

        # PERF-CN-01: prevent_initial_call=False — renders default LR text on mount.
        @app.callback(
            Output(f"{self.component_id}-current-lr", "children"),
            [Input(f"{self.component_id}-training-state-store", "data")],
            prevent_initial_call=False,
        )
        def update_learning_rate(state):
            return self._update_learning_rate_handler(state=state)

        # PERF-CN-01: prevent_initial_call=False — renders default phase-duration
        # text on mount.
        @app.callback(
            Output(f"{self.component_id}-phase-duration", "children"),
            [Input(f"{self.component_id}-training-state-store", "data")],
            prevent_initial_call=False,
        )
        def update_phase_duration(state):
            return self._update_phase_duration_handler(state=state)

        # PERF-CN-01: prevent_initial_call=False — renders progress bars in their
        # initial (zeroed) state on mount.
        @app.callback(
            [
                Output(f"{self.component_id}-progress-bars", "style"),
                Output(f"{self.component_id}-grow-progress", "value"),
                Output(f"{self.component_id}-grow-progress", "label"),
                Output(f"{self.component_id}-candidate-epoch-progress", "value"),
                Output(f"{self.component_id}-candidate-epoch-progress", "label"),
            ],
            [Input(f"{self.component_id}-training-state-store", "data")],
            prevent_initial_call=False,
        )
        def update_training_progress(state):
            return self._update_training_progress_handler(state=state)

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

        # PERF-CN-01: prevent_initial_call=False — must render initial empty
        # loss/accuracy plots and status text on mount; theme-aware so it must
        # also redraw when the theme store fires.
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
                Input(f"{self.component_id}-display-mode-store", "data"),
            ],
            [
                State(f"{self.component_id}-view-state", "data"),
                State(f"{self.component_id}-training-state-store", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_metrics_display(metrics_data: List[Dict[str, Any]], theme: str, display_mode_state: Dict, view_state: Dict, training_state: Dict):
            return self._update_metrics_display_handler(metrics_data=metrics_data, theme=theme, view_state=view_state, display_mode_state=display_mode_state, training_state=training_state)

        # A1-iii-b2: render the one-shot regression result for a recurrence (LMU) model and
        # hide the classification surface (the accuracy cards + per-epoch loss/accuracy plots
        # are meaningless for a single regression fit). Driven by the b1 ``model-class-store``;
        # re-fires on each metrics-store update so the result card fills in when the fit lands.
        @app.callback(
            [
                Output(f"{self.component_id}-oneshot-result", "children"),
                Output(f"{self.component_id}-oneshot-result", "style"),
                Output(f"{self.component_id}-classification-metrics", "style"),
                Output(f"{self.component_id}-loss-plot", "style"),
                Output(f"{self.component_id}-accuracy-plot", "style"),
            ],
            [
                Input("model-class-store", "data"),
                Input(f"{self.component_id}-metrics-store", "data"),
            ],
            prevent_initial_call=False,
        )
        def render_model_class_metrics(model_class: str, metrics_data: List[Dict[str, Any]]):
            return self._render_model_class_metrics(model_class, metrics_data)

        # Phase B: Incremental chart update via Plotly.extendTraces (§S7).
        # When WS bridge pushes new metrics events, append them to the
        # existing chart traces without rebuilding the full figure.
        # Max 5000 points retained per trace to bound memory.
        #
        # GAP-WS-14: extends to validation overlays. The original landing only
        # fed trace 0 (Output Training / Accuracy); validation traces still
        # forced a full figure rebuild whenever val_loss / val_accuracy
        # changed. Trace indices vary at runtime depending on which optional
        # overlays are present, so we look them up by name rather than
        # hard-coding positions.
        app.clientside_callback(
            """
            function(wsBuffer, lossId, accId) {
                if (!wsBuffer || !wsBuffer.events || wsBuffer.events.length === 0) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update];
                }
                var events = wsBuffer.events;
                var epochs = [], losses = [], accuracies = [];
                var valEpochs = [], valLosses = [], valAccs = [];
                for (var i = 0; i < events.length; i++) {
                    var e = events[i];
                    var epoch = e.epoch || e.current_epoch || i;
                    var loss = e.loss || e.error || e.current_error;
                    var acc = e.accuracy || e.correct_percentage;
                    if (loss !== undefined && loss !== null) {
                        epochs.push(epoch);
                        losses.push(loss);
                        accuracies.push(acc !== undefined && acc !== null ? acc : 0);
                    }
                    // GAP-WS-14: collect validation values when present so the
                    // overlay traces stay in sync without forcing a rebuild.
                    var vLoss = (e.val_loss !== undefined) ? e.val_loss
                              : ((e.validation_loss !== undefined) ? e.validation_loss : null);
                    var vAcc = (e.val_accuracy !== undefined) ? e.val_accuracy
                             : ((e.validation_accuracy !== undefined) ? e.validation_accuracy : null);
                    if (vLoss !== null && vLoss !== undefined) {
                        valEpochs.push(epoch);
                        valLosses.push(vLoss);
                        valAccs.push(vAcc !== null && vAcc !== undefined ? vAcc : null);
                    }
                }
                if (epochs.length === 0 && valEpochs.length === 0) {
                    return [window.dash_clientside.no_update, window.dash_clientside.no_update];
                }

                // Locate optional traces by name. Positions vary depending on
                // whether candidate-training / validation overlays are
                // enabled in this view (GAP-WS-14).
                function findTraceIndex(el, name) {
                    if (!el || !el.data) return -1;
                    for (var k = 0; k < el.data.length; k++) {
                        if (el.data[k] && el.data[k].name === name) return k;
                    }
                    return -1;
                }

                // extendTraces on loss plot (trace 0 = Output Training)
                var lossEl = document.getElementById(lossId);
                if (lossEl && lossEl.data && lossEl.data.length > 0) {
                    if (epochs.length > 0) {
                        try {
                            Plotly.extendTraces(lossEl, {x: [epochs], y: [losses]}, [0], 5000);
                        } catch(e) {}
                    }
                    if (valEpochs.length > 0) {
                        var valLossIdx = findTraceIndex(lossEl, "Validation Loss");
                        if (valLossIdx >= 0) {
                            try {
                                Plotly.extendTraces(lossEl, {x: [valEpochs], y: [valLosses]}, [valLossIdx], 5000);
                            } catch(e) {}
                        }
                    }
                }
                // extendTraces on accuracy plot (trace 0 = Accuracy)
                var accEl = document.getElementById(accId);
                if (accEl && accEl.data && accEl.data.length > 0) {
                    if (epochs.length > 0) {
                        try {
                            Plotly.extendTraces(accEl, {x: [epochs], y: [accuracies]}, [0], 5000);
                        } catch(e) {}
                    }
                    if (valEpochs.length > 0) {
                        var valAccIdx = findTraceIndex(accEl, "Validation Accuracy");
                        if (valAccIdx >= 0) {
                            // Filter null val_accuracy values so the overlay
                            // only gains real points (the loss event may
                            // arrive before the matching accuracy).
                            var fEpochs = [], fAccs = [];
                            for (var j = 0; j < valEpochs.length; j++) {
                                if (valAccs[j] !== null && valAccs[j] !== undefined) {
                                    fEpochs.push(valEpochs[j]);
                                    fAccs.push(valAccs[j]);
                                }
                            }
                            if (fEpochs.length > 0) {
                                try {
                                    Plotly.extendTraces(accEl, {x: [fEpochs], y: [fAccs]}, [valAccIdx], 5000);
                                } catch(e) {}
                            }
                        }
                    }
                }
                return [window.dash_clientside.no_update, window.dash_clientside.no_update];
            }
            """,
            Output(f"{self.component_id}-loss-plot", "figure", allow_duplicate=True),
            Output(f"{self.component_id}-accuracy-plot", "figure", allow_duplicate=True),
            Input("ws-metrics-buffer", "data"),
            State(f"{self.component_id}-loss-plot", "id"),
            State(f"{self.component_id}-accuracy-plot", "id"),
            prevent_initial_call=True,
        )

        # Replay Controls Callbacks
        # PERF-CN-01: prevent_initial_call=False — theme-driven styling must be
        # applied on mount so the replay controls bar matches the active theme.
        @app.callback(
            Output(f"{self.component_id}-replay-controls", "style"),
            [
                Input(f"{self.component_id}-training-state-store", "data"),
                Input("theme-state", "data"),
            ],
            prevent_initial_call=False,
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

        # PERF-CN-01: prevent_initial_call=False — sets initial slider position
        # and "0 / 0" replay-position text on mount.
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
            prevent_initial_call=False,
        )
        def update_replay_ui(state, metrics_data):
            """Update replay slider and position display."""
            max_index = len(metrics_data) - 1 if metrics_data else 0
            current_index = state.get("current_index", 0) if state else 0

            slider_value = (current_index / max_index * 100) if max_index > 0 else 0
            position_text = f"{current_index} / {max_index}"

            return slider_value, 100, position_text

        # PERF-CN-01: prevent_initial_call=False — sets initial play-button icon
        # ("▶") on mount.
        @app.callback(
            Output(f"{self.component_id}-replay-play", "children"),
            Input(f"{self.component_id}-replay-state", "data"),
            prevent_initial_call=False,
        )
        def update_play_button(state):
            """Update play button icon based on replay state."""
            return "⏸" if state and state.get("mode") == "playing" else "▶"

        # Layout Save/Load Callbacks (P3-4)
        # PERF-CN-01: prevent_initial_call=False — must populate the saved-layouts
        # dropdown from the API on mount.
        @app.callback(
            Output(f"{self.component_id}-layout-dropdown", "options"),
            Input(f"{self.component_id}-layout-store", "data"),
            prevent_initial_call=False,
        )
        def refresh_layout_dropdown(layout_data):
            """Refresh layout dropdown options from API."""
            return self._fetch_layout_options_handler()

        @app.callback(
            [
                Output(f"{self.component_id}-layout-status", "children"),
                Output(f"{self.component_id}-layout-store", "data", allow_duplicate=True),
                Output(f"{self.component_id}-layout-name-input", "value"),
            ],
            Input(f"{self.component_id}-save-layout-btn", "n_clicks"),
            [
                State(f"{self.component_id}-layout-name-input", "value"),
                State(f"{self.component_id}-view-state", "data"),
            ],
            prevent_initial_call=True,
        )
        def save_layout(n_clicks, name, view_state):
            """Save current layout configuration."""
            return self._save_layout_handler(n_clicks, name, view_state)

        @app.callback(
            [
                Output(f"{self.component_id}-layout-status", "children", allow_duplicate=True),
                Output(f"{self.component_id}-view-state", "data", allow_duplicate=True),
            ],
            Input(f"{self.component_id}-load-layout-btn", "n_clicks"),
            State(f"{self.component_id}-layout-dropdown", "value"),
            prevent_initial_call=True,
        )
        def load_layout(n_clicks, layout_name):
            """Load selected layout configuration."""
            return self._load_layout_handler(n_clicks, layout_name)

        @app.callback(
            [
                Output(f"{self.component_id}-layout-status", "children", allow_duplicate=True),
                Output(f"{self.component_id}-layout-store", "data", allow_duplicate=True),
                Output(f"{self.component_id}-layout-dropdown", "value"),
            ],
            Input(f"{self.component_id}-delete-layout-btn", "n_clicks"),
            State(f"{self.component_id}-layout-dropdown", "value"),
            prevent_initial_call=True,
        )
        def delete_layout(n_clicks, layout_name):
            """Delete selected layout."""
            return self._delete_layout_handler(n_clicks, layout_name)

        # Display mode callbacks
        # PERF-CN-01: prevent_initial_call=True — display-mode-store is already
        # seeded with sensible defaults at layout time, so the initial fire would
        # only re-emit the same values. React only to actual user changes.
        @app.callback(
            [
                Output(f"{self.component_id}-display-mode-store", "data"),
                Output(f"{self.component_id}-window-size-container", "style"),
            ],
            [
                Input(f"{self.component_id}-display-mode", "value"),
                Input(f"{self.component_id}-window-size", "value"),
            ],
            prevent_initial_call=True,
        )
        def update_display_mode(mode, window_size):
            """Update display mode state and show/hide window size input."""
            window_size = max(10, min(1000, window_size or 100))
            show_window = {"display": "inline-flex", "alignItems": "center"} if mode == "window" else {"display": "none"}
            return {"mode": mode, "window_size": window_size}, show_window

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
            response = requests.get(f"{self._api_base_url}/api/network/stats", timeout=2, headers=internal_api_headers())
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
            response = requests.get(f"{self._api_base_url}/api/state", timeout=2, headers=internal_api_headers())
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.debug(f"Failed to fetch training state: {e}")

        return {}

    def _update_progress_detail_handler(self, state=None):
        """Build inline progress text from training state progress fields."""
        if not state:
            return ""
        status = (state.get("status") or "").upper()
        if status in ("STOPPED", "IDLE", ""):
            return ""

        parts = []
        phase_detail = state.get("phase_detail", "")
        if phase_detail:
            parts.append(phase_detail.replace("_", " ").title())

        grow_iter = state.get("grow_iteration")
        grow_max = state.get("grow_max")
        if grow_iter is not None and grow_max:
            parts.append(f"Growth Iteration {grow_iter}/{grow_max}")

        best_corr = state.get("best_correlation")
        if best_corr:
            parts.append(f"Best Corr: {best_corr:.4f}")

        cand_trained = state.get("candidates_trained")
        cand_total = state.get("candidates_total")
        if cand_trained is not None and cand_total:
            parts.append(f"Candidates: {cand_trained}/{cand_total}")

        cand_epoch = state.get("candidate_epoch")
        cand_total_epochs = state.get("candidate_total_epochs")
        if cand_epoch and cand_total_epochs:
            pct = int(100 * cand_epoch / cand_total_epochs)
            parts.append(f"Candidate Epoch: {cand_epoch}/{cand_total_epochs} ({pct}%)")

        return " | ".join(parts) if parts else ""

    def _update_learning_rate_handler(self, state=None):
        """Update learning rate card from training state."""
        if not state:
            return "--"
        lr = state.get("learning_rate")
        if lr is not None:
            return f"{lr:.6f}"
        return "--"

    def _update_training_progress_handler(self, state=None):
        """Update grow iteration and candidate epoch progress bars."""
        hidden_style = {"display": "none", "marginBottom": "15px", "padding": "0 10px"}
        visible_style = {"display": "block", "marginBottom": "15px", "padding": "0 10px"}

        if not state:
            return hidden_style, 0, "", 0, ""

        status = (state.get("status") or "").upper()
        if status in ("STOPPED", "IDLE", ""):
            return hidden_style, 0, "", 0, ""

        grow_iter = state.get("grow_iteration")
        # Use max_hidden_units as the practical growth-progress target (units are
        # added one per admitted iteration), falling back to grow_max. N6/C2b: grow_max
        # is ``max_iterations`` (the cascade growth-iteration cap), NOT max_epochs —
        # the effective growth ceiling is ``min(max_iterations, max_hidden_units)``.
        grow_max = state.get("max_hidden_units") or state.get("grow_max")
        cand_epoch = state.get("candidate_epoch")
        cand_total = state.get("candidate_total_epochs")

        has_grow = grow_iter is not None and grow_max
        has_cand = cand_epoch is not None and cand_total

        if not has_grow and not has_cand:
            return hidden_style, 0, "", 0, ""

        grow_pct = min(100, int(100 * grow_iter / grow_max)) if has_grow else 0
        grow_label = f"{grow_iter}/{grow_max}" if has_grow else ""
        cand_pct = min(100, int(100 * cand_epoch / cand_total)) if has_cand else 0
        cand_label = f"{cand_epoch}/{cand_total}" if has_cand else ""

        return visible_style, grow_pct, grow_label, cand_pct, cand_label

    def _update_phase_duration_handler(self, state=None):
        """Compute and display elapsed time since phase_started_at."""
        if not state:
            return ""
        status = (state.get("status") or "").upper()
        if status in ("STOPPED", "IDLE", ""):
            return ""
        phase_started = state.get("phase_started_at")
        if not phase_started:
            return ""
        from datetime import datetime, timezone

        try:
            started = datetime.fromisoformat(phase_started)
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            elapsed = datetime.now(timezone.utc) - started
            total_seconds = int(elapsed.total_seconds())
            if total_seconds < 0:
                return ""
            minutes, seconds = divmod(total_seconds, 60)
            return f"Phase Duration: {minutes}m {seconds}s"
        except (ValueError, TypeError):
            return ""

    def _update_metrics_display_handler(self, metrics_data: List[Dict[str, Any]] = None, theme: str = None, view_state: Dict = None, display_mode_state: Dict = None, training_state: Dict = None):
        """
        Update all metrics visualizations and displays.

        Args:
            metrics_data: List of metrics dictionaries
            theme: Current theme ("light" or "dark")
            view_state: User's saved view state (zoom ranges)
            display_mode_state: Display mode configuration (mode, window_size)
            training_state: Training state dictionary (for max_hidden_units)

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
            empty_fig = create_empty_plot(theme=theme)
            return (empty_fig, empty_fig, "0", "--", "--", "0", "Status: Idle", self._get_status_style("idle"))

        # Apply display mode filtering
        mode_state = display_mode_state or {"mode": "window", "window_size": 100}
        mode = mode_state.get("mode", "window")
        plot_data = metrics_data

        if mode == "hidden_units" and len(metrics_data) > 1:
            # Show data between the last two hidden unit additions
            hidden_unit_epochs = []
            prev_hu = 0
            for m in metrics_data:
                hu = m.get("network_topology", {}).get("hidden_units", 0)
                if hu > prev_hu:
                    hidden_unit_epochs.append(m.get("epoch", 0))
                prev_hu = hu
            if len(hidden_unit_epochs) >= 2:
                start_epoch = hidden_unit_epochs[-2]
                plot_data = [m for m in metrics_data if m.get("epoch", 0) >= start_epoch]
            elif len(hidden_unit_epochs) == 1:
                start_epoch = hidden_unit_epochs[-1]
                plot_data = [m for m in metrics_data if m.get("epoch", 0) >= start_epoch]

        # Create plots
        loss_fig = self._create_loss_plot(plot_data, theme)
        accuracy_fig = self._create_accuracy_plot(plot_data, theme)

        # Apply adaptive Y-axis scaling for loss chart (percentile-based clamping)
        # Only apply when the user hasn't manually zoomed the Y-axis
        user_has_y_zoom = view_state and view_state.get("loss_yaxis_range")
        if not user_has_y_zoom:
            loss_values = [m.get("metrics", {}).get("loss", 0) for m in plot_data]
            if len(loss_values) >= 2:
                p95 = float(np.percentile(loss_values, 95))
                if p95 > 0:
                    loss_fig.update_layout(yaxis_range=[0, p95 * 1.1])

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
        # N6/C2b: metrics rows carry a ``kind`` discriminator — ``training_step``
        # rows number ``epoch`` as completed training steps; ``output_epoch`` rows
        # number ``epoch`` as the within-pass inner epoch (sampled ~every 25th
        # epoch). The "Training Step" tile must show the completed-step count, so
        # prefer the latest ``training_step`` row (or the authoritative
        # ``training_state.current_epoch``); never a within-pass inner epoch — that
        # was the tile-level "Training Step: 10000 vs 12" flip-flop (S12/I-1c).
        # Rows without ``kind`` default to ``training_step`` (pre-C2b / demo rows
        # used step numbering), so legacy payloads are unaffected. During a
        # candidate phase no new ``training_step`` rows arrive (metrics freeze), so
        # this holds the last step value instead of blanking.
        step_rows = [m for m in metrics_data if m.get("kind", "training_step") == "training_step"]
        if step_rows:
            current_epoch = step_rows[-1].get("epoch", 0)
        elif isinstance(training_state, dict) and training_state.get("current_epoch") is not None:
            current_epoch = training_state.get("current_epoch")
        else:
            current_epoch = latest.get("epoch", 0)
        current_loss = latest.get("metrics", {}).get("loss", 0)
        current_accuracy = latest.get("metrics", {}).get("accuracy", 0)
        hidden_units = latest.get("network_topology", {}).get("hidden_units", 0)
        phase = latest.get("phase", "idle")

        # Format current values
        loss_str = f"{current_loss:.4f}" if isinstance(current_loss, (int, float)) else "--"
        accuracy_str = f"{current_accuracy:.2%}" if isinstance(current_accuracy, (int, float)) else "--"

        # Format hidden units as "N / max" when max is available
        max_hu = (training_state or {}).get("max_hidden_units") or (training_state or {}).get("nn_max_hidden_units")
        hu_str = f"{hidden_units} / {max_hu}" if max_hu else str(hidden_units)

        # Status text and style
        status_text = f'Status: {phase.replace("_", " ").title()}'
        status_style = self._get_status_style(phase)

        return (
            loss_fig,
            accuracy_fig,
            str(current_epoch),
            loss_str,
            accuracy_str,
            hu_str,
            status_text,
            status_style,
        )

    # Layout Save/Load Handlers (P3-4)
    def _fetch_layout_options_handler(self) -> List[Dict[str, str]]:
        """
        Fetch available layout options from the API.

        Returns:
            List of dropdown options with label and value
        """
        import requests

        try:
            response = requests.get(f"{self._api_base_url}/api/v1/metrics/layouts", timeout=2, headers=internal_api_headers())
            if response.status_code == 200:
                data = response.json()
                layouts = data.get("layouts", [])
                return [{"label": layout["name"], "value": layout["name"]} for layout in layouts]
        except Exception as e:
            self.logger.debug(f"Failed to fetch layouts: {e}")

        return []

    def _save_layout_handler(self, n_clicks, name: str, view_state: dict):
        """
        Handle save layout button click.

        Args:
            n_clicks: Number of button clicks
            name: Layout name from input
            view_state: Current view state with zoom ranges

        Returns:
            Tuple of (status message, layout store data, cleared input value)
        """
        import requests

        if not n_clicks:
            return "", None, ""

        if not name or not name.strip():
            return "⚠️ Please enter a layout name", None, name

        try:
            response = requests.post(
                f"{self._api_base_url}/api/v1/metrics/layouts",
                params={
                    "name": name.strip(),
                    "smoothing_window": self.smoothing_window,
                },
                json={
                    "zoom_ranges": view_state or {},
                },
                timeout=5,
                headers=internal_api_headers(),
            )

            if response.status_code == 201:
                return f"✅ Layout '{name}' saved", {"refresh": True}, ""
            else:
                error = response.json().get("detail", "Unknown error")
                return f"❌ Failed: {error}", None, name

        except requests.exceptions.Timeout:
            return "❌ Request timed out", None, name
        except Exception as e:
            self.logger.error(f"Failed to save layout: {e}")
            return f"❌ Error: {str(e)}", None, name

    def _load_layout_handler(self, n_clicks, layout_name: str):
        """
        Handle load layout button click.

        Args:
            n_clicks: Number of button clicks
            layout_name: Selected layout name

        Returns:
            Tuple of (status message, updated view state)
        """
        import requests

        if not n_clicks:
            return "", {}

        if not layout_name:
            return "⚠️ Please select a layout", {}

        try:
            response = requests.get(
                f"{self._api_base_url}/api/v1/metrics/layouts/{layout_name}",
                timeout=2,
                headers=internal_api_headers(),
            )

            if response.status_code == 200:
                layout_data = response.json()
                zoom_ranges = layout_data.get("zoom_ranges", {})

                return f"✅ Layout '{layout_name}' loaded", zoom_ranges

            elif response.status_code == 404:
                return f"❌ Layout '{layout_name}' not found", {}
            else:
                error = response.json().get("detail", "Unknown error")
                return f"❌ Failed: {error}", {}

        except requests.exceptions.Timeout:
            return "❌ Request timed out", {}
        except Exception as e:
            self.logger.error(f"Failed to load layout: {e}")
            return f"❌ Error: {str(e)}", {}

    def _delete_layout_handler(self, n_clicks, layout_name: str):
        """
        Handle delete layout button click.

        Args:
            n_clicks: Number of button clicks
            layout_name: Selected layout name

        Returns:
            Tuple of (status message, layout store data, cleared dropdown value)
        """
        import requests

        if not n_clicks:
            return "", None, layout_name

        if not layout_name:
            return "⚠️ Please select a layout to delete", None, layout_name

        try:
            response = requests.delete(
                f"{self._api_base_url}/api/v1/metrics/layouts/{layout_name}",
                timeout=5,
                headers=internal_api_headers(),
            )

            if response.status_code == 200:
                return f"✅ Layout '{layout_name}' deleted", {"refresh": True}, None

            elif response.status_code == 404:
                return f"❌ Layout '{layout_name}' not found", None, layout_name
            else:
                error = response.json().get("detail", "Unknown error")
                return f"❌ Failed: {error}", None, layout_name

        except requests.exceptions.Timeout:
            return "❌ Request timed out", None, layout_name
        except Exception as e:
            self.logger.error(f"Failed to delete layout: {e}")
            return f"❌ Error: {str(e)}", None, layout_name

    def _render_model_class_metrics(self, model_class: str, metrics_data: List[Dict[str, Any]]):
        """Toggle the metrics surface by model class (A1-iii-b2).

        Returns ``(oneshot_children, oneshot_style, classification_style, loss_plot_style,
        accuracy_plot_style)``. For a ``"one_shot"`` model the regression result card is shown
        and the classification cards + both per-epoch plots are hidden; otherwise the normal
        (live) surface is shown and the result card stays hidden. Pure — directly unit-testable.
        """
        cards_style = {"display": "flex", "justifyContent": "space-around", "marginBottom": "20px", "gap": "10px"}
        plot_style = {"height": "300px"}
        if model_class == "one_shot":
            hidden_cards = {**cards_style, "display": "none"}
            hidden_plot = {**plot_style, "display": "none"}
            return self._build_oneshot_result(metrics_data), {"display": "block", "marginBottom": "20px"}, hidden_cards, hidden_plot, hidden_plot
        # live (demo / cascor): classification surface visible, result card hidden
        return [], {"display": "none"}, cards_style, plot_style, plot_style

    def _build_oneshot_result(self, metrics_data: List[Dict[str, Any]]):
        """Build the one-shot regression result card from the latest metrics (A1-iii-b2).

        ``metrics_data`` is ``RecurrenceBackend.get_metrics_history()`` — a single flat point
        ``{r2, mse, rmse, mae, loss, epoch}`` once the fit lands, or empty while it runs (then a
        spinner is shown). Regression-generic: never an accuracy/percentage readout.
        """
        if not metrics_data:
            return html.Div(
                [
                    dbc.Spinner(size="sm", color="primary"),
                    html.Span("  Awaiting recurrence (LMU) fit result…", style={"marginLeft": "8px", "color": "var(--text-muted)"}),
                ],
                style={"textAlign": "center", "padding": "30px"},
            )
        latest = metrics_data[-1] if isinstance(metrics_data, list) else metrics_data

        def _fmt(key: str) -> str:
            value = latest.get(key)
            return f"{value:.4f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else "--"

        cards = [
            html.Div(
                [html.H5(label, style={"color": "var(--text-muted)", "marginBottom": "4px"}), html.H3(_fmt(key), style={"color": color})],
                className="metric-card",
                style={"flex": "1", "textAlign": "center", "padding": "12px"},
            )
            for label, key, color in (
                ("R²", "r2", "#28a745"),
                ("RMSE", "rmse", "#dc3545"),
                ("MSE", "mse", "#fd7e14"),
                ("MAE", "mae", "#6f42c1"),
                ("Loss", "loss", "#17a2b8"),
            )
        ]
        return html.Div(
            [
                html.H5("Recurrence (LMU) — final regression metrics", style={"marginBottom": "12px"}),
                html.Div(cards, style={"display": "flex", "justifyContent": "space-around", "gap": "10px"}),
            ]
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
        epochs, losses, phases = self._parse_metrics(metrics_data=metrics_data)

        # Create figure with phase-colored scatter
        fig = self._create_phase_colored_scatter(fig=go.Figure(), epochs=epochs, losses=losses, phases=phases)
        self._add_validation_overlay(fig, metrics_data, "val_loss", "Validation Loss", "#ff6b6b")
        fig = self._add_phase_bg_bands(fig=fig, epochs=epochs, phases=phases)
        fig, epoch = self._add_hidden_unit_markers(metrics_data=metrics_data, fig=fig, theme=theme, epochs=epochs)

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

    def _create_phase_colored_scatter(self, fig: go.Figure = None, epochs: list = None, losses: list = None, phases: list = None) -> go.Figure:
        """
        Create phase-colored scatter plot from epochs, losses, and phases.
        """
        # Separate data by phase for coloring
        output_epochs = [out_epoch for out_epoch, phase in zip(epochs, phases, strict=False) if "output" in phase]
        output_losses = [out_loss for out_loss, phase in zip(losses, phases, strict=False) if "output" in phase]
        candidate_epochs = [cand_epoch for cand_epoch, phase in zip(epochs, phases, strict=False) if "candidate" in phase]
        candidate_losses = [cand_loss for cand_loss, phase in zip(losses, phases, strict=False) if "candidate" in phase]
        fig = self._output_add_trace(fig=fig, output_epochs=output_epochs, output_losses=output_losses)
        fig = self._candidate_add_trace(fig=fig, candidate_epochs=candidate_epochs, candidate_losses=candidate_losses)
        return fig

    def _output_add_trace(self, fig: go.Figure = None, output_epochs: list = None, output_losses: list = None) -> go.Figure:
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

    def _candidate_add_trace(self, fig: go.Figure = None, candidate_epochs: list = None, candidate_losses: list = None) -> go.Figure:
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

    @staticmethod
    def _add_validation_overlay(fig: go.Figure, metrics_data: List[Dict[str, Any]], field_name: str, trace_name: str, color: str) -> go.Figure:
        """Add a dashed validation overlay trace to an existing plot.

        Args:
            fig: Existing plotly figure to add trace to.
            metrics_data: List of metrics dictionaries.
            field_name: Key inside metrics dict (e.g. "val_loss").
            trace_name: Legend label for the trace.
            color: CSS color string.
        """
        epochs = []
        values = []
        for m in metrics_data:
            val = m.get("metrics", {}).get(field_name)
            if val is not None:
                epochs.append(m.get("epoch", 0))
                values.append(val)
        if epochs:
            fig.add_trace(
                go.Scatter(
                    x=epochs,
                    y=values,
                    mode="lines",
                    name=trace_name,
                    line={"color": color, "width": 2, "dash": "dash"},
                )
            )
        return fig

    @staticmethod
    def _phase_band_color(phase: str) -> str:
        """Return the background band fill color for a training phase, or None."""
        if phase is None:
            return None
        if "candidate" in phase:
            return "rgba(255, 193, 7, 0.08)"
        if "output" in phase:
            return "rgba(0, 123, 255, 0.06)"
        return None

    def _add_phase_bg_bands(self, fig: go.Figure = None, epochs: list = None, phases: list = None) -> go.Figure:
        # Add phase background bands
        current_phase = None
        phase_start = None
        fig, current_phase, phase_start = self._end_prev_phase_band(fig=fig, epochs=epochs, phases=phases, current_phase=current_phase, phase_start=phase_start)
        fig, current_phase, phase_start = self._candidate_final_band(fig=fig, epochs=epochs, current_phase=current_phase, phase_start=phase_start)
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
                fillcolor = self._phase_band_color(current_phase)
                if fillcolor is not None and phase_start is not None:
                    fig.add_shape(
                        type="rect",
                        x0=phase_start,
                        x1=epochs[i - 1] if i > 0 else phase_start,
                        y0=0,
                        y1=1,
                        yref="paper",
                        fillcolor=fillcolor,
                        line_width=0,
                        layer="below",
                    )
                current_phase = phase
                phase_start = epoch
        return (fig, current_phase, phase_start)

    def _candidate_final_band(self, fig: go.Figure = None, epochs: list = None, current_phase: str = None, phase_start: float = None) -> Tuple[go.Figure, str, float]:
        # Final band if ended in a phase with a background color
        fillcolor = self._phase_band_color(current_phase)
        if fillcolor is not None and phase_start is not None:
            fig.add_shape(
                type="rect",
                x0=phase_start,
                x1=epochs[-1],
                y0=0,
                y1=1,
                yref="paper",
                fillcolor=fillcolor,
                line_width=0,
                layer="below",
            )
        return (fig, current_phase, phase_start)

    def _add_hidden_unit_markers(self, metrics_data: List[Dict[str, Any]], fig: go.Figure = None, theme: str = "light", epochs: list = None) -> Tuple[go.Figure, list]:
        fig = self._hidden_unit_addition_markers(metrics_data=metrics_data, fig=fig, theme=theme)
        fig = self._training_loss_per_time(fig=fig, theme=theme)
        return (fig, epochs)

    def _hidden_unit_addition_markers(self, metrics_data: List[Dict[str, Any]], fig: go.Figure = None, theme: str = "light") -> go.Figure:
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
            xaxis_title="Iteration",
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

        self._add_validation_overlay(fig, metrics_data, "val_accuracy", "Validation Accuracy", "#82e0aa")

        # Add phase background bands (reuse shared method)
        fig = self._add_phase_bg_bands(fig=fig, epochs=epochs, phases=phases)

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
            xaxis_title="Iteration",
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

    def _create_network_info_table(self, stats: Dict[str, Any]) -> html.Div:
        """
        Create network information table from statistics.

        Args:
            stats: Network statistics dictionary

        Returns:
            Dash Div with formatted table
        """
        if not stats:
            return html.Div("Loading network information...", style={"color": "var(--text-muted)", "fontSize": "14px"})

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
                        style={"borderBottom": "1px solid var(--border-color)"},
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
                "borderRadius": "4px",
            },
        )
