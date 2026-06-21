#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     dataset_plotter.py
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This file contains the code to Display the Dataset for the Cascade Correlation Neural Network prototype
#       in the Juniper prototype Frontend for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#
# Dataset Plotter Component
#
# Visualization of training and test datasets with scatter plots,
# class labels, and data distribution.
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
from typing import Any, Dict, List, Optional

import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output, State
from plotly.subplots import make_subplots

from canopy_constants import DashboardConstants, SecurityConstants
from frontend.internal_api import internal_api_headers

from ..base_component import BaseComponent, create_empty_plot


class DatasetPlotter(BaseComponent):
    """
    Dataset visualization component.

    Displays:
    - Scatter plots of input data
    - Class labels with color coding
    - Training vs test data split
    - Data distribution statistics
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "dataset-plotter"):
        """
        Initialize dataset plotter component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        # Configuration
        self.default_colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]

        # Current dataset
        self.current_dataset: Optional[Dict[str, Any]] = None

        self.logger.info("DatasetPlotter initialized")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for dataset plotter.

        Returns:
            Dash Div containing the dataset visualization
        """
        is_dark = False
        return html.Div(
            [
                # Header with controls
                html.Div(
                    [
                        html.H3("Dataset Visualization", style={"display": "inline-block"}),
                        html.Div(
                            [
                                dbc.Button(
                                    "⟳ Generate Dataset",
                                    id=f"{self.component_id}-generate-btn",
                                    color="primary",
                                    size="sm",
                                    style={"marginRight": "15px"},
                                ),
                                html.Label("Dataset:", style={"marginRight": "10px"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-dataset-selector",
                                    options=[],  # Populated dynamically
                                    value=None,
                                    placeholder="Select dataset...",
                                    style={"width": "200px", "display": "inline-block"},
                                ),
                                # Explicit Load action: an on-change callback would
                                # fire when populate_dataset_selector sets the value
                                # on every page load and reset training on refresh, so
                                # the selected generator is loaded only on click.
                                dbc.Button(
                                    "Load",
                                    id=f"{self.component_id}-load-selected-btn",
                                    color="secondary",
                                    size="sm",
                                    style={"marginLeft": "10px"},
                                ),
                                html.Span(
                                    id=f"{self.component_id}-load-status",
                                    style={"marginLeft": "10px", "fontSize": "0.85em", "color": "var(--text-muted)"},
                                ),
                                html.Label("Split:", style={"marginLeft": "20px", "marginRight": "10px"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-split-selector",
                                    options=[
                                        {"label": "All Data", "value": "all"},
                                        {"label": "Training Only", "value": "train"},
                                        {"label": "Test Only", "value": "test"},
                                    ],
                                    value="all",
                                    style={"width": "150px", "display": "inline-block"},
                                ),
                            ],
                            style={"display": "inline-flex", "alignItems": "center", "float": "right"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                # Dataset modal — three tabs: Generate / Upload File / Fetch URL (CAN-016b).
                # The Generate tab keeps the original spiral parameters and confirm
                # button; the Upload tab adds a dcc.Upload + import-file button; the
                # URL tab adds a text input + fetch-and-import button. Each tab has
                # its own confirm button so dashboard_manager can wire them
                # independently without context-aware footer logic.
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Dataset")),
                        dbc.ModalBody(
                            [
                                dbc.Tabs(
                                    [
                                        dbc.Tab(
                                            html.Div(
                                                [
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Samples"),
                                                                    dbc.Input(id=f"{self.component_id}-gen-samples", type="number", value=200, min=20, max=2000, step=10),
                                                                ],
                                                                width=6,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Spirals"),
                                                                    dbc.Input(id=f"{self.component_id}-gen-spirals", type="number", value=2, min=2, max=6, step=1),
                                                                ],
                                                                width=6,
                                                            ),
                                                        ],
                                                        className="mb-3",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Rotations"),
                                                                    dbc.Input(id=f"{self.component_id}-gen-rotations", type="number", value=1.5, min=0.1, max=10.0, step=0.1),
                                                                ],
                                                                width=6,
                                                            ),
                                                            dbc.Col(
                                                                [
                                                                    dbc.Label("Noise"),
                                                                    dbc.Input(id=f"{self.component_id}-gen-noise", type="number", value=0.1, min=0.0, max=1.0, step=0.01),
                                                                ],
                                                                width=6,
                                                            ),
                                                        ],
                                                        className="mb-3",
                                                    ),
                                                    dbc.Button("Generate", id=f"{self.component_id}-gen-confirm", color="primary"),
                                                    html.Div(id=f"{self.component_id}-gen-status", style={"color": "var(--text-muted)", "fontSize": "0.85em", "marginTop": "10px"}),
                                                ],
                                                style={"paddingTop": "15px"},
                                            ),
                                            label="Generate",
                                            tab_id=f"{self.component_id}-tab-generate",
                                        ),
                                        dbc.Tab(
                                            html.Div(
                                                [
                                                    html.Small(
                                                        "Upload a CSV file. Last column = integer class label; preceding columns = numeric features. Header row auto-detected. Limits: 10 MB, 50,000 rows, 100 features.",
                                                        style={"color": "var(--text-muted)", "display": "block", "marginBottom": "10px"},
                                                    ),
                                                    dcc.Upload(
                                                        id=f"{self.component_id}-import-file-upload",
                                                        children=html.Div(["Drag and drop or ", html.A("select a CSV file")]),
                                                        multiple=False,
                                                        accept=".csv,text/csv",
                                                        style={
                                                            "width": "100%",
                                                            "height": "60px",
                                                            "lineHeight": "60px",
                                                            "borderWidth": "1px",
                                                            "borderStyle": "dashed",
                                                            "borderRadius": "5px",
                                                            "textAlign": "center",
                                                            "marginBottom": "10px",
                                                        },
                                                    ),
                                                    html.Div(
                                                        id=f"{self.component_id}-import-file-name",
                                                        style={"color": "var(--text-muted)", "fontSize": "0.85em", "marginBottom": "10px"},
                                                    ),
                                                    dbc.Button("Import File", id=f"{self.component_id}-import-file-confirm", color="primary", disabled=True),
                                                    html.Div(id=f"{self.component_id}-import-file-status", style={"color": "var(--text-muted)", "fontSize": "0.85em", "marginTop": "10px"}),
                                                ],
                                                style={"paddingTop": "15px"},
                                            ),
                                            label="Upload File",
                                            tab_id=f"{self.component_id}-tab-upload",
                                        ),
                                        dbc.Tab(
                                            html.Div(
                                                [
                                                    html.Small(
                                                        "Fetch a CSV from an http(s) URL. Same format and limits as Upload File. The canopy server performs the fetch — confirm the URL is reachable from the server's network.",
                                                        style={"color": "var(--text-muted)", "display": "block", "marginBottom": "10px"},
                                                    ),
                                                    dbc.Input(
                                                        id=f"{self.component_id}-import-url-input",
                                                        type="url",
                                                        placeholder="https://example.com/dataset.csv",
                                                        style={"marginBottom": "10px"},
                                                    ),
                                                    dbc.Button("Fetch & Import", id=f"{self.component_id}-import-url-confirm", color="primary"),
                                                    html.Div(id=f"{self.component_id}-import-url-status", style={"color": "var(--text-muted)", "fontSize": "0.85em", "marginTop": "10px"}),
                                                ],
                                                style={"paddingTop": "15px"},
                                            ),
                                            label="Fetch URL",
                                            tab_id=f"{self.component_id}-tab-url",
                                        ),
                                    ],
                                    id=f"{self.component_id}-modal-tabs",
                                    active_tab=f"{self.component_id}-tab-generate",
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            [
                                dbc.Button("Cancel", id=f"{self.component_id}-gen-cancel", color="secondary"),
                            ]
                        ),
                    ],
                    id=f"{self.component_id}-generate-modal",
                    is_open=False,
                    centered=True,
                ),
                # Dataset statistics
                html.Div(
                    [
                        html.Div(
                            [html.Strong("Samples: "), html.Span(id=f"{self.component_id}-sample-count", children="0")],
                            style={"display": "inline-block", "marginRight": "20px"},
                        ),
                        html.Div(
                            [
                                html.Strong("Features: "),
                                html.Span(id=f"{self.component_id}-feature-count", children="0"),
                            ],
                            style={"display": "inline-block", "marginRight": "20px"},
                        ),
                        html.Div(
                            [html.Strong("Classes: "), html.Span(id=f"{self.component_id}-class-count", children="0")],
                            style={"display": "inline-block", "marginRight": "20px"},
                        ),
                        html.Div(
                            [
                                html.Strong("Balance: "),
                                html.Span(id=f"{self.component_id}-balance-info", children="N/A"),
                            ],
                            style={"display": "inline-block"},
                        ),
                    ],
                    id=f"{self.component_id}-stats-summary",
                    style={
                        "marginBottom": "15px",
                        "padding": "10px",
                        "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
                        "borderRadius": "3px",
                    },
                ),
                # Sequence (3-D) controls — CANOPY-3D-2 (Phase 2a / 2b).
                # Shown only for sequence datasets (toggle_sequence_controls). A mode toggle
                # switches between comparing signals (within one window) and comparing
                # windows (of one signal) — vary one axis at a time; the arrangement toggle
                # (small multiples ⇄ overlay) applies to both modes.
                html.Div(
                    [
                        html.Label("Compare:", style={"marginRight": "10px", "fontWeight": "bold"}),
                        dbc.RadioItems(
                            id=f"{self.component_id}-seq-mode",
                            options=[
                                {"label": "Signals", "value": "signals"},
                                {"label": "Windows", "value": "windows"},
                            ],
                            value="signals",
                            inline=True,
                            className="btn-group",
                            inputClassName="btn-check",
                            labelClassName="btn btn-outline-secondary btn-sm",
                            labelCheckedClassName="active",
                        ),
                        # Signals mode: one window, multi-select signals.
                        html.Div(
                            [
                                html.Label("Window:", style={"marginLeft": "20px", "marginRight": "10px", "fontWeight": "bold"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-seq-window-single",
                                    options=[],
                                    value=None,
                                    clearable=False,
                                    style={"minWidth": "120px"},
                                ),
                                html.Label("Signals:", style={"marginLeft": "16px", "marginRight": "10px", "fontWeight": "bold"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-seq-signal-select",
                                    options=[],
                                    value=None,
                                    multi=True,
                                    placeholder="All signals",
                                    style={"minWidth": "240px"},
                                ),
                            ],
                            id=f"{self.component_id}-seq-group-signals",
                            style={"display": "flex", "alignItems": "center"},
                        ),
                        # Windows mode: one signal, multi-select windows.
                        html.Div(
                            [
                                html.Label("Signal:", style={"marginLeft": "20px", "marginRight": "10px", "fontWeight": "bold"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-seq-signal-single",
                                    options=[],
                                    value=None,
                                    clearable=False,
                                    style={"minWidth": "150px"},
                                ),
                                html.Label("Windows:", style={"marginLeft": "16px", "marginRight": "10px", "fontWeight": "bold"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-seq-window-multi",
                                    options=[],
                                    value=None,
                                    multi=True,
                                    placeholder="Select windows",
                                    style={"minWidth": "240px"},
                                ),
                            ],
                            id=f"{self.component_id}-seq-group-windows",
                            style={"display": "none", "alignItems": "center"},
                        ),
                        html.Label("Arrange:", style={"marginLeft": "20px", "marginRight": "10px", "fontWeight": "bold"}),
                        dbc.RadioItems(
                            id=f"{self.component_id}-seq-arrange",
                            options=[
                                {"label": "Small multiples", "value": "small_multiples"},
                                {"label": "Overlay", "value": "overlay"},
                            ],
                            value="small_multiples",
                            inline=True,
                            className="btn-group",
                            inputClassName="btn-check",
                            labelClassName="btn btn-outline-primary btn-sm",
                            labelCheckedClassName="active",
                        ),
                        dbc.Checklist(
                            id=f"{self.component_id}-seq-target-toggle",
                            options=[{"label": "Show target", "value": "on"}],
                            value=[],
                            switch=True,
                            inline=True,
                            style={"marginLeft": "20px"},
                        ),
                        dbc.Checklist(
                            id=f"{self.component_id}-seq-grid-toggle",
                            options=[{"label": "Advanced: full-cross grid", "value": "on"}],
                            value=[],
                            switch=True,
                            inline=True,
                            style={"marginLeft": "20px"},
                        ),
                    ],
                    id=f"{self.component_id}-seq-controls",
                    style={"display": "none", "alignItems": "center", "marginBottom": "12px", "flexWrap": "wrap", "gap": "6px"},
                ),
                # Viz area: a flex row — the main plots (scatter + Δt strip + optional
                # regression target) and a collapsible characterization side companion
                # (CANOPY-3D-2, Phase 2c). The companion hides for 2-D tabular datasets so
                # the main column expands to full width.
                html.Div(
                    [
                        html.Div(
                            [
                                # Main scatter plot
                                dcc.Graph(
                                    id=f"{self.component_id}-scatter-plot",
                                    config={"displayModeBar": True, "displaylogo": False},
                                    style={"height": "800px", "maxWidth": "900px", "margin": "0 auto"},
                                ),
                                # Feature distribution histograms / Δt strip
                                dcc.Graph(
                                    id=f"{self.component_id}-distribution-plot",
                                    config={"displayModeBar": False},
                                    style={"height": "30vh", "maxHeight": "450px", "minHeight": "250px"},
                                ),
                                # Optional regression-target companion (shown via the toggle)
                                dcc.Graph(
                                    id=f"{self.component_id}-seq-target-plot",
                                    config={"displayModeBar": False},
                                    style={"display": "none", "height": "240px"},
                                ),
                            ],
                            style={"flex": "1", "minWidth": "0"},
                        ),
                        # Characterization side companion — on by default, collapsible.
                        html.Div(
                            [
                                html.Div(
                                    [html.Span("▾ ", id=f"{self.component_id}-seq-char-icon"), "Characterization"],
                                    id=f"{self.component_id}-seq-char-toggle",
                                    style={"cursor": "pointer", "fontWeight": "bold", "marginBottom": "8px"},
                                ),
                                dbc.Collapse(
                                    [
                                        html.Div(id=f"{self.component_id}-seq-char-stats", style={"fontSize": "0.85em", "marginBottom": "10px"}),
                                        dcc.Graph(id=f"{self.component_id}-seq-char-dt-hist", config={"displayModeBar": False}, style={"height": "200px"}),
                                        dcc.Graph(id=f"{self.component_id}-seq-char-target-dist", config={"displayModeBar": False}, style={"height": "200px"}),
                                    ],
                                    id=f"{self.component_id}-seq-char-collapse",
                                    is_open=True,
                                ),
                            ],
                            id=f"{self.component_id}-seq-char-companion",
                            style={"display": "none", "width": "340px", "flexShrink": "0", "paddingLeft": "12px"},
                        ),
                    ],
                    style={"display": "flex", "gap": "16px", "alignItems": "flex-start"},
                ),
                # Advanced full-cross grid (M4, Phase 3) — opt-in expert view, hidden by
                # default; a scrollable faceted grid of signals × windows (capped at 100
                # cells). Toggled by seq-grid-toggle; sequence-only.
                html.Div(
                    dcc.Graph(
                        id=f"{self.component_id}-seq-grid-plot",
                        config={"displayModeBar": True, "displaylogo": False},
                    ),
                    id=f"{self.component_id}-seq-grid-container",
                    style={"display": "none"},
                ),
                # Dataset data store
                dcc.Store(id=f"{self.component_id}-dataset-store", data=None),
            ],
            style={"padding": "20px"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for dataset plotter.

        Args:
            app: Dash application instance
        """

        # PERF-CN-01: prevent_initial_call=False — must render initial empty
        # scatter/distribution plots and stats placeholders on mount; theme-aware
        # so it must redraw when theme changes too.
        @app.callback(
            [
                Output(f"{self.component_id}-scatter-plot", "figure"),
                Output(f"{self.component_id}-distribution-plot", "figure"),
                Output(f"{self.component_id}-sample-count", "children"),
                Output(f"{self.component_id}-feature-count", "children"),
                Output(f"{self.component_id}-class-count", "children"),
                Output(f"{self.component_id}-balance-info", "children"),
            ],
            [
                Input(f"{self.component_id}-dataset-store", "data"),
                Input(f"{self.component_id}-split-selector", "value"),
                Input("theme-state", "data"),
                Input(f"{self.component_id}-seq-signal-select", "value"),
                Input(f"{self.component_id}-seq-arrange", "value"),
                Input(f"{self.component_id}-seq-mode", "value"),
                Input(f"{self.component_id}-seq-window-single", "value"),
                Input(f"{self.component_id}-seq-signal-single", "value"),
                Input(f"{self.component_id}-seq-window-multi", "value"),
            ],
            prevent_initial_call=False,
        )
        def update_dataset_plots(dataset: Optional[Dict[str, Any]], split: str, theme: str, seq_signals: Optional[List[int]] = None, seq_arrange: str = "small_multiples", seq_mode: str = "signals", seq_window: Optional[int] = None, seq_signal: Optional[int] = None, seq_windows: Optional[List[int]] = None):
            """
            Update dataset visualizations.

            Args:
                dataset: Dataset dictionary
                split: Data split to display ('all', 'train', 'test')
                theme: Current theme ("light" or "dark")
                seq_signals / seq_arrange / seq_mode / seq_window / seq_signal / seq_windows:
                    3-D sequence controls (ignored for 2-D tabular datasets).

            Returns:
                Tuple of updated components
            """
            return self._process_dataset_update(dataset, split, theme, seq_signals, seq_arrange, seq_mode, seq_window, seq_signal, seq_windows)

        # PERF-CN-01: prevent_initial_call=False — theme-driven styling must be
        # applied on mount so the stats summary matches the active theme.
        @app.callback(
            Output(f"{self.component_id}-stats-summary", "style"),
            Input("theme-state", "data"),
            prevent_initial_call=False,
        )
        def update_stats_summary_theme(theme):
            """Update stats summary background for dark mode."""
            is_dark = theme == "dark" if theme else False
            return {
                "marginBottom": "15px",
                "padding": "10px",
                "backgroundColor": "#2d2d2d" if is_dark else "#f8f9fa",
                "color": "#e9ecef" if is_dark else "#212529",
                "borderRadius": "3px",
            }

        # ── Populate dataset selector dropdown from available generators ──
        # PERF-CN-01: prevent_initial_call=False — must hit /api/dataset/generators
        # on mount to populate the dropdown (the params-init-interval fires once
        # at app load specifically to drive this initial fetch).
        @app.callback(
            [
                Output(f"{self.component_id}-dataset-selector", "options"),
                Output(f"{self.component_id}-dataset-selector", "value"),
            ],
            Input("params-init-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def populate_dataset_selector(n):
            """Fetch available dataset generators and populate the dropdown."""
            import requests as _requests

            try:
                from flask import request as _flask_request

                origin = f"{_flask_request.scheme}://{_flask_request.host}"
            except RuntimeError:
                origin = SecurityConstants.CORS_LOCAL_ORIGIN

            options = []
            current_value = None
            try:
                resp = _requests.get(f"{origin}/api/dataset/generators", timeout=DashboardConstants.DASHBOARD_GET_TIMEOUT, headers=internal_api_headers())
                if resp.ok:
                    data = resp.json()
                    generators = data.get("generators", [])
                    for gen in generators:
                        name = gen.get("name", "")
                        display = gen.get("display_name", name.capitalize())
                        options.append({"label": display, "value": name})
                    # Default to "spiral" if available
                    gen_names = [g.get("name") for g in generators]
                    if "spiral" in gen_names:
                        current_value = "spiral"
                    elif options:
                        current_value = options[0]["value"]
            except Exception:
                # Fallback: provide basic generator list
                # XREPO-01 / DC-01 (2026-04-24): dropdown ``value``
                # fields must match the juniper-data server registry
                # keys. Circles uses ``"circles"`` (plural).
                options = [
                    {"label": "Spiral", "value": "spiral"},
                    {"label": "XOR", "value": "xor"},
                    {"label": "Circles", "value": "circles"},
                    {"label": "Moon", "value": "moon"},
                ]
                current_value = "spiral"
            return options, current_value

        # ── Sequence (3-D) controls: populate selectors + visibility (CANOPY-3D-2) ──
        # Phase 2a/2b: the mode toggle, signal/window selectors and arrangement toggle are
        # meaningful only for 3-D sequence datasets, so they populate from / show with the
        # loaded dataset and stay hidden (and empty) for 2-D tabular datasets.
        # PERF-CN-01: prevent_initial_call=False — controls must reach a correct initial
        # state on mount (hidden, empty) before any dataset loads.
        @app.callback(
            [
                Output(f"{self.component_id}-seq-signal-select", "options"),
                Output(f"{self.component_id}-seq-signal-select", "value"),
                Output(f"{self.component_id}-seq-window-single", "options"),
                Output(f"{self.component_id}-seq-window-single", "value"),
                Output(f"{self.component_id}-seq-signal-single", "options"),
                Output(f"{self.component_id}-seq-signal-single", "value"),
                Output(f"{self.component_id}-seq-window-multi", "options"),
                Output(f"{self.component_id}-seq-window-multi", "value"),
            ],
            Input(f"{self.component_id}-dataset-store", "data"),
            prevent_initial_call=False,
        )
        def populate_sequence_controls(dataset):
            """Populate the signal / window selectors from the loaded sequence dataset."""
            return self._sequence_control_options(dataset)

        @app.callback(
            Output(f"{self.component_id}-seq-controls", "style"),
            Input(f"{self.component_id}-dataset-store", "data"),
            prevent_initial_call=False,
        )
        def toggle_sequence_controls(dataset):
            """Show the sequence control bar only when a sequence dataset is loaded."""
            is_seq = bool(dataset) and dataset.get("dataset_kind") == "sequence"
            return {
                "display": "flex" if is_seq else "none",
                "alignItems": "center",
                "marginBottom": "12px",
                "flexWrap": "wrap",
                "gap": "6px",
            }

        @app.callback(
            [
                Output(f"{self.component_id}-seq-group-signals", "style"),
                Output(f"{self.component_id}-seq-group-windows", "style"),
            ],
            Input(f"{self.component_id}-seq-mode", "value"),
            prevent_initial_call=False,
        )
        def toggle_sequence_mode_groups(mode):
            """Show only the controls for the active comparison mode (signals vs windows)."""
            shown = {"display": "flex", "alignItems": "center"}
            hidden = {"display": "none"}
            if mode == "windows":
                return hidden, shown
            return shown, hidden

        # ── Sequence (3-D) companions: target view + characterization (CANOPY-3D-2 / 2c) ──
        # Separate callbacks (the core update_dataset_plots is unchanged): an optional
        # regression-target graph (toggled) and a collapsible characterization side
        # companion (Δt + target histograms + W/L/F stats), both sequence-only.
        @app.callback(
            [
                Output(f"{self.component_id}-seq-target-plot", "figure"),
                Output(f"{self.component_id}-seq-target-plot", "style"),
            ],
            [
                Input(f"{self.component_id}-dataset-store", "data"),
                Input(f"{self.component_id}-seq-target-toggle", "value"),
                Input(f"{self.component_id}-seq-mode", "value"),
                Input(f"{self.component_id}-seq-window-single", "value"),
                Input(f"{self.component_id}-seq-window-multi", "value"),
                Input("theme-state", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_sequence_target(dataset, toggle, seq_mode, seq_window, seq_windows, theme):
            """Render the regression-target companion for the primary window (when toggled on)."""
            return self._process_target_update(dataset, toggle, seq_mode, seq_window, seq_windows, theme)

        @app.callback(
            [
                Output(f"{self.component_id}-seq-char-dt-hist", "figure"),
                Output(f"{self.component_id}-seq-char-target-dist", "figure"),
                Output(f"{self.component_id}-seq-char-stats", "children"),
                Output(f"{self.component_id}-seq-char-companion", "style"),
            ],
            [
                Input(f"{self.component_id}-dataset-store", "data"),
                Input("theme-state", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_sequence_characterization(dataset, theme):
            """Render the characterization companion (Δt + target histograms + W/L/F stats)."""
            return self._process_characterization_update(dataset, theme)

        @app.callback(
            [
                Output(f"{self.component_id}-seq-char-collapse", "is_open"),
                Output(f"{self.component_id}-seq-char-icon", "children"),
            ],
            Input(f"{self.component_id}-seq-char-toggle", "n_clicks"),
            State(f"{self.component_id}-seq-char-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_characterization_collapse(n_clicks, is_open):
            """Collapse / expand the characterization companion."""
            new_open = not is_open
            return new_open, "▾ " if new_open else "▸ "

        # ── Advanced full-cross grid (M4, Phase 3) — opt-in, sequence-only ──
        @app.callback(
            [
                Output(f"{self.component_id}-seq-grid-plot", "figure"),
                Output(f"{self.component_id}-seq-grid-container", "style"),
            ],
            [
                Input(f"{self.component_id}-dataset-store", "data"),
                Input(f"{self.component_id}-seq-grid-toggle", "value"),
                Input("theme-state", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_sequence_grid(dataset, toggle, theme):
            """Render the advanced full-cross (signals × windows) grid when toggled on."""
            return self._process_grid_update(dataset, toggle, theme)

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _process_dataset_update(self, dataset: Optional[Dict[str, Any]], split: str, theme: str, seq_signals: Optional[List[int]] = None, seq_arrange: str = "small_multiples", seq_mode: str = "signals", seq_window: Optional[int] = None, seq_signal: Optional[int] = None, seq_windows: Optional[List[int]] = None) -> tuple:
        """
        Process dataset update and return visualization components.

        This method contains the logic for the update_dataset_plots callback,
        extracted for testability.

        Args:
            dataset: Dataset dictionary
            split: Data split to display ('all', 'train', 'test')
            theme: Current theme ("light" or "dark")

        Returns:
            Tuple of (scatter_fig, dist_fig, sample_count, feature_count, class_count, balance_info)
        """
        if not dataset:
            empty_fig = create_empty_plot("No dataset loaded", theme)
            return empty_fig, empty_fig, "0", "0", "0", "N/A"

        # CANOPY-3D-1: 3-D sequence datasets render via a distinct branch (feature
        # small-multiples over real time + a Δt strip); dispatch before any 2-D logic.
        if dataset.get("dataset_kind") == "sequence":
            return self._process_sequence_update(dataset, theme, seq_signals, seq_arrange, seq_mode, seq_window, seq_signal, seq_windows)

        # Filter data by split
        filtered_data = self._filter_by_split(dataset, split)

        # Check for metadata-only dataset (service mode without data arrays)
        inputs = filtered_data.get("inputs", [])
        if not inputs and (dataset.get("num_samples") or dataset.get("num_features")):
            scatter_fig = create_empty_plot("Dataset loaded (metadata only)", theme)
            dist_fig = create_empty_plot("Distribution unavailable", theme)
            return (
                scatter_fig,
                dist_fig,
                str(dataset.get("num_samples", 0)),
                str(dataset.get("num_features", 0)),
                str(dataset.get("num_classes", 0)),
                "N/A",
            )

        # Create plots
        scatter_fig = self._create_scatter_plot(filtered_data, theme)
        dist_fig = self._create_distribution_plot(filtered_data, theme)

        # Calculate statistics
        n_samples = len(inputs)
        n_features = len(inputs[0]) if inputs else 0
        targets = filtered_data.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0

        # Class balance
        balance_info = self._calculate_balance(targets) if targets else "N/A"

        return (scatter_fig, dist_fig, str(n_samples), str(n_features), str(unique_classes), balance_info)

    def _process_sequence_update(self, dataset: Dict[str, Any], theme: str, seq_signals: Optional[List[int]] = None, seq_arrange: str = "small_multiples", seq_mode: str = "signals", seq_window: Optional[int] = None, seq_signal: Optional[int] = None, seq_windows: Optional[List[int]] = None) -> tuple:
        """CANOPY-3D-1/2: render a 3-D sequence (time-series) dataset.

        Two comparison modes (vary one axis at a time): ``signals`` (default) plots
        multi-selected signals within one window; ``windows`` plots one signal across
        multi-selected windows. Both arrange as small-multiples or a normalized overlay,
        with a Δt strip for the primary window. Returns the same 6-tuple as the tabular
        path so the ``update_dataset_plots`` callback Outputs are unchanged.
        """
        seq = dataset.get("sequence", {})
        if seq_mode == "windows":
            scatter_fig = self._create_windows_plot(seq, theme, seq_signal, seq_windows, seq_arrange)
            primary_window = seq_windows[0] if seq_windows else 0
        else:
            primary_window = seq_window if isinstance(seq_window, int) and seq_window >= 0 else 0
            scatter_fig = self._create_sequence_plot(seq, theme, seq_signals, seq_arrange, primary_window)
        dist_fig = self._create_dt_strip(seq, theme, primary_window)
        return (
            scatter_fig,
            dist_fig,
            str(dataset.get("n_windows", 0)),
            str(dataset.get("n_features", 0)),
            "0",
            "N/A",
        )

    def _window_arrays(self, seq: Dict[str, Any], window: int) -> tuple:
        """Resolve ``(X, dt)`` numpy arrays for a window index.

        Prefers the capped multi-window store (``windows_X`` / ``windows_dt``, Phase 2b);
        falls back to the single window-0 view (``X`` / ``dt``) for legacy / minimal dicts.
        """
        windows_X = seq.get("windows_X")
        windows_dt = seq.get("windows_dt")
        if windows_X and isinstance(window, int) and 0 <= window < len(windows_X):
            X = np.array(windows_X[window], dtype=float)
            dt = np.array(windows_dt[window], dtype=float) if windows_dt and window < len(windows_dt) else np.array([], dtype=float)
            return X, dt
        return np.array(seq.get("X", []), dtype=float), np.array(seq.get("dt", []), dtype=float)

    def _plot_normalized_series(self, series: list, theme: str, arrangement: str, title: str) -> go.Figure:
        """Render per-normalized 1-D series over cumulative-Δt time.

        ``series`` = list of ``(t, values, name, color)``. ``small_multiples`` normalizes
        each series and stacks them with a vertical offset (first on top); ``overlay``
        normalizes each onto one shared [0, 1] axis (design R2 — legible across mixed
        scales).
        """
        if not series:
            return create_empty_plot("No data to plot", theme)
        overlay = arrangement == "overlay"
        count = len(series)
        fig = go.Figure()
        for pos, (t, values, name, color) in enumerate(series):
            vals = np.asarray(values, dtype=float)
            span = float(vals.max() - vals.min()) if vals.size else 0.0
            norm = (vals - vals.min()) / (span + 1e-9) if vals.size else vals
            # overlay: shared normalized axis; small-multiple: stack, first selected on top.
            offset = 0.0 if overlay else (count - 1 - pos) * 1.15
            fig.add_trace(
                go.Scatter(
                    x=t,
                    y=norm + offset,
                    mode="lines+markers",
                    name=name,
                    line={"color": color},
                    marker={"size": 4},
                )
            )
        is_dark = theme == "dark"
        yaxis: Dict[str, Any] = {"title": "normalized value"} if overlay else {"title": "(offset, normalized)", "showticklabels": False}
        fig.update_layout(
            title=title,
            xaxis_title="time (cumulative Δt)",
            yaxis=yaxis,
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            showlegend=True,
            hovermode="closest",
        )
        return fig

    def _create_sequence_plot(self, seq: Dict[str, Any], theme: str = "light", signals: Optional[List[int]] = None, arrangement: str = "small_multiples", window: int = 0) -> go.Figure:
        """Compare-signals: selected signals of one window over real (cumulative-Δt) time.

        ``signals`` selects feature indices (``None`` / empty → all); stale / out-of-range
        indices are dropped (fall back to all). ``window`` indexes the stored windows
        (Phase 2b; window 0 is the default). Arrangement is handled by
        ``_plot_normalized_series``.
        """
        win_idx = window if isinstance(window, int) and window >= 0 else 0
        X, dt = self._window_arrays(seq, win_idx)
        labels = seq.get("feature_labels", [])
        if X.ndim != 2 or X.shape[0] == 0:
            return create_empty_plot("No sequence data available", theme)
        length, n_features = X.shape

        # Resolve selected feature indices, guarding stale / out-of-range selections.
        selected = [int(i) for i in (signals or []) if isinstance(i, (int, float)) and 0 <= int(i) < n_features]
        if not selected:
            selected = list(range(n_features))

        t = np.cumsum(dt) if dt.size == length else np.arange(length, dtype=float)
        series = [(t, X[:, i], labels[i] if i < len(labels) else f"Feature {i}", self.default_colors[i % len(self.default_colors)]) for i in selected]
        overlay = arrangement == "overlay"
        title = f"Signals — window {win_idx} ({'overlay, normalized' if overlay else 'small multiples'}, real time)"
        return self._plot_normalized_series(series, theme, arrangement, title)

    def _create_windows_plot(self, seq: Dict[str, Any], theme: str = "light", signal: Optional[int] = None, windows: Optional[List[int]] = None, arrangement: str = "small_multiples") -> go.Figure:
        """Compare-windows: one signal across selected windows over real (cumulative-Δt) time.

        ``signal`` is the feature index (defaults to 0); ``windows`` selects window indices
        (``None`` / empty → the first few stored). Each window keeps its own Δt (sampling is
        irregular per window), so every series uses its own cumulative-time x-axis, each
        starting near 0 for comparison.
        """
        windows_X = seq.get("windows_X")
        labels = seq.get("feature_labels", [])
        n_stored = len(windows_X) if windows_X else 1
        first_X, _ = self._window_arrays(seq, 0)
        if first_X.ndim != 2 or first_X.shape[0] == 0:
            return create_empty_plot("No sequence data available", theme)
        n_features = first_X.shape[1]

        sig = int(signal) if isinstance(signal, (int, float)) and 0 <= int(signal) < n_features else 0
        selected = [int(w) for w in (windows or []) if isinstance(w, (int, float)) and 0 <= int(w) < n_stored]
        if not selected:
            selected = list(range(min(n_stored, 3)))  # default: the first few windows

        series = []
        for w in selected:
            X, dt = self._window_arrays(seq, w)
            if X.ndim != 2 or X.shape[0] == 0 or sig >= X.shape[1]:
                continue
            length = X.shape[0]
            t = np.cumsum(dt) if dt.size == length else np.arange(length, dtype=float)
            series.append((t, X[:, sig], f"Window {w}", self.default_colors[w % len(self.default_colors)]))
        sig_label = labels[sig] if sig < len(labels) else f"Feature {sig}"
        overlay = arrangement == "overlay"
        title = f"Windows — {sig_label} ({'overlay, normalized' if overlay else 'small multiples'}, real time)"
        return self._plot_normalized_series(series, theme, arrangement, title)

    def _create_dt_strip(self, seq: Dict[str, Any], theme: str = "light", window: int = 0) -> go.Figure:
        """Per-step Δt strip for a window over real time — the irregular-sampling companion."""
        _, dt = self._window_arrays(seq, window if isinstance(window, int) and window >= 0 else 0)
        if dt.size == 0:
            return create_empty_plot("No Δt available", theme)
        t = np.cumsum(dt)
        is_dark = theme == "dark"
        fig = go.Figure(go.Bar(x=t, y=dt, marker_color="#888888"))
        fig.update_layout(
            title="Δt per step (sampling intervals)",
            xaxis_title="time (cumulative Δt)",
            yaxis_title="Δt",
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            showlegend=False,
        )
        return fig

    def _sequence_control_options(self, dataset: Optional[Dict[str, Any]]) -> tuple:
        """Options + defaults for all sequence selectors; empties for non-sequence datasets.

        Returns an 8-tuple matching ``populate_sequence_controls``'s Outputs:
        (signal-multi options, value), (window-single options, value),
        (signal-single options, value), (window-multi options, value). Signals default to
        all selected; window-single to 0; signal-single to the first signal; window-multi
        to the first few windows. Window options come from the capped multi-window store.
        """
        empty: tuple = ([], None, [], None, [], None, [], None)
        if not dataset or dataset.get("dataset_kind") != "sequence":
            return empty
        seq = dataset.get("sequence", {})
        labels = seq.get("feature_labels", [])
        n_signals = len(labels)
        windows_X = seq.get("windows_X")
        n_windows = len(windows_X) if windows_X else int(dataset.get("n_windows_stored", 1) or 1)

        signal_opts = [{"label": str(lab), "value": i} for i, lab in enumerate(labels)]
        window_opts = [{"label": f"Window {w}", "value": w} for w in range(n_windows)]
        return (
            signal_opts,
            list(range(n_signals)),  # signal-multi: all selected
            window_opts,
            0 if n_windows else None,  # window-single: first window
            signal_opts,
            0 if n_signals else None,  # signal-single: first signal
            window_opts,
            list(range(min(n_windows, 3))),  # window-multi: the first few windows
        )

    def _process_target_update(self, dataset: Optional[Dict[str, Any]], toggle: Optional[List[str]], seq_mode: str, seq_window: Optional[int], seq_windows: Optional[List[int]], theme: str) -> tuple:
        """Figure + style for the optional regression-target companion (Phase 2c).

        Hidden unless the toggle is on AND the dataset is a sequence. The target shown is the
        primary window's (the selected window in signals mode; the first selected window in
        windows mode).
        """
        hidden = {"display": "none", "height": "240px"}
        on = bool(toggle) and "on" in (toggle or [])
        if not on or not dataset or dataset.get("dataset_kind") != "sequence":
            return create_empty_plot("", theme), hidden
        seq = dataset.get("sequence", {})
        if seq_mode == "windows":
            window = seq_windows[0] if seq_windows else 0
        else:
            window = seq_window if isinstance(seq_window, int) and seq_window >= 0 else 0
        return self._create_target_plot(seq, theme, window), {"display": "block", "height": "240px"}

    def _create_target_plot(self, seq: Dict[str, Any], theme: str, window: int) -> go.Figure:
        """Bar of a window's regression target (labelled by feature when lengths match)."""
        windows_y = seq.get("windows_y") or []
        idx = window if isinstance(window, int) and 0 <= window < len(windows_y) else 0
        if not windows_y or idx >= len(windows_y):
            return create_empty_plot("No target available", theme)
        target = np.asarray(windows_y[idx], dtype=float).ravel()
        labels = seq.get("feature_labels", [])
        names = [str(lab) for lab in labels] if target.size == len(labels) and labels else [f"t{j}" for j in range(target.size)]
        is_dark = theme == "dark"
        fig = go.Figure(go.Bar(x=names, y=target.tolist(), marker_color="#9b59b6"))
        fig.update_layout(
            title=f"Regression target — window {idx}",
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            showlegend=False,
            margin={"l": 40, "r": 10, "t": 40, "b": 30},
        )
        return fig

    def _process_characterization_update(self, dataset: Optional[Dict[str, Any]], theme: str) -> tuple:
        """Figures + stats + companion style for the characterization side companion (Phase 2c).

        Whole-dataset Δt and target histograms (precomputed at load over ALL windows) plus a
        W / L / F stats block. Hidden for non-sequence datasets.
        """
        if not dataset or dataset.get("dataset_kind") != "sequence":
            empty = create_empty_plot("", theme)
            return empty, empty, "", {"display": "none"}
        seq = dataset.get("sequence", {})
        dt_fig = self._create_hist_plot(seq.get("dt_hist"), theme, "Δt distribution (all windows)", "#888888")
        tgt_fig = self._create_hist_plot(seq.get("target_hist"), theme, "Target distribution (all windows)", "#2ecc71")
        stats = self._sequence_stats_children(dataset)
        companion_style = {"display": "block", "width": "340px", "flexShrink": "0", "paddingLeft": "12px"}
        return dt_fig, tgt_fig, stats, companion_style

    def _create_hist_plot(self, hist: Optional[Dict[str, Any]], theme: str, title: str, color: str) -> go.Figure:
        """Bar chart from a precomputed ``{edges, counts}`` histogram (or an empty plot)."""
        if not hist or not hist.get("counts"):
            return create_empty_plot("No data", theme)
        edges = hist["edges"]
        counts = hist["counts"]
        centers = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
        widths = [edges[i + 1] - edges[i] for i in range(len(counts))]
        is_dark = theme == "dark"
        fig = go.Figure(go.Bar(x=centers, y=counts, width=widths, marker_color=color))
        fig.update_layout(
            title=title,
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            showlegend=False,
            bargap=0,
            margin={"l": 40, "r": 10, "t": 40, "b": 30},
        )
        return fig

    def _sequence_stats_children(self, dataset: Dict[str, Any]) -> list:
        """W / L / F summary lines for the characterization companion."""
        n_windows = dataset.get("n_windows", 0)
        n_stored = dataset.get("n_windows_stored", n_windows)
        lookback = dataset.get("lookback", 0)
        n_features = dataset.get("n_features", 0)
        note = "" if n_stored >= n_windows else f" (showing first {n_stored})"
        return [
            html.Div([html.Strong("Windows: "), f"{n_windows}{note}"]),
            html.Div([html.Strong("Lookback: "), str(lookback)]),
            html.Div([html.Strong("Features: "), str(n_features)]),
        ]

    def _process_grid_update(self, dataset: Optional[Dict[str, Any]], toggle: Optional[List[str]], theme: str) -> tuple:
        """Figure + container style for the advanced full-cross grid (Phase 3, M4).

        Hidden unless toggled on AND the dataset is a sequence. The grid is capped at 100
        cells (window rows trimmed so ``windows × signals <= 100``); a scrollable container
        keeps it navigable at scale.
        """
        hidden = {"display": "none"}
        on = bool(toggle) and "on" in (toggle or [])
        if not on or not dataset or dataset.get("dataset_kind") != "sequence":
            return create_empty_plot("", theme), hidden
        seq = dataset.get("sequence", {})
        fig = self._create_grid_plot(seq, theme)
        shown = {
            "display": "block",
            "maxHeight": "640px",
            "overflowY": "auto",
            "marginTop": "12px",
            "border": "1px solid rgba(128,128,128,0.35)",
            "borderRadius": "3px",
        }
        return fig, shown

    def _create_grid_plot(self, seq: Dict[str, Any], theme: str = "light") -> go.Figure:
        """Faceted grid: every signal (cols) × window (rows), normalized over cumulative-Δt.

        Capped at 100 cells — the window rows are trimmed so ``rows × cols <= 100`` (design
        M4). Each cell is a normalized line; per-cell zoom is available via the modebar and
        the container scrolls vertically.
        """
        windows_X = seq.get("windows_X") or ([seq["X"]] if seq.get("X") is not None else [])
        if not windows_X:
            return create_empty_plot("No sequence data available", theme)
        first = np.asarray(windows_X[0], dtype=float)
        if first.ndim != 2 or first.shape[0] == 0:
            return create_empty_plot("No sequence data available", theme)
        n_features = first.shape[1]
        labels = seq.get("feature_labels", [])
        n_stored = len(windows_X)

        cap = 100
        max_windows = max(1, cap // max(n_features, 1))
        n_win = min(n_stored, max_windows)
        sig_names = [str(labels[i]) if i < len(labels) else f"Feature {i}" for i in range(n_features)]
        win_titles = [f"W{w}" for w in range(n_win)]

        hs = min(0.03, 1.0 / max(n_features, 2))
        vs = min(0.02, 1.0 / max(n_win, 2))
        fig = make_subplots(rows=n_win, cols=n_features, column_titles=sig_names, row_titles=win_titles, horizontal_spacing=hs, vertical_spacing=vs)
        for r in range(n_win):
            X, dt = self._window_arrays(seq, r)
            if X.ndim != 2 or X.shape[0] == 0:
                continue
            length = X.shape[0]
            t = np.cumsum(dt) if dt.size == length else np.arange(length, dtype=float)
            for c in range(n_features):
                col = X[:, c]
                span = float(col.max() - col.min())
                norm = (col - col.min()) / (span + 1e-9)
                fig.add_trace(
                    go.Scatter(x=t, y=norm, mode="lines", line={"color": self.default_colors[c % len(self.default_colors)], "width": 1}, showlegend=False),
                    row=r + 1,
                    col=c + 1,
                )
        is_dark = theme == "dark"
        capped = "" if n_win >= n_stored else f" (first {n_win} of {n_stored} windows)"
        fig.update_layout(
            title=f"Full-cross grid — {n_features} signals × {n_win} windows{capped}",
            height=max(260, n_win * 150),
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            margin={"l": 40, "r": 20, "t": 60, "b": 30},
        )
        fig.update_xaxes(showticklabels=False)
        fig.update_yaxes(showticklabels=False)
        return fig

    def _filter_by_split(self, dataset: Dict[str, Any], split: str) -> Dict[str, Any]:
        """
        Filter dataset by split type.

        Args:
            dataset: Full dataset
            split: Split type ('all', 'train', 'test')

        Returns:
            Filtered dataset
        """
        if split == "all" or "split_indices" not in dataset:
            return dataset

        # If split indices are provided in dataset
        split_indices = dataset.get("split_indices", {})

        if split == "train":
            indices = split_indices.get("train", [])
        elif split == "test":
            indices = split_indices.get("test", [])
        else:
            return dataset

        # Filter inputs and targets
        inputs = dataset.get("inputs", [])
        targets = dataset.get("targets", [])

        filtered_inputs = [inputs[i] for i in indices if i < len(inputs)]
        filtered_targets = [targets[i] for i in indices if i < len(targets)]

        return {**dataset, "inputs": filtered_inputs, "targets": filtered_targets}

    def _create_scatter_plot(self, dataset: Dict[str, Any], theme: str = "light") -> go.Figure:
        """
        Create scatter plot of dataset.

        Args:
            dataset: Dataset dictionary with inputs and targets
            theme: Current theme ("light" or "dark")

        Returns:
            Plotly figure object
        """
        inputs = dataset.get("inputs", [])
        targets = dataset.get("targets", [])

        if len(inputs) == 0:
            return create_empty_plot("No data available", theme)

        # Convert to numpy arrays
        X = np.array(inputs)
        y = np.array(targets)

        n_features = X.shape[1] if len(X.shape) > 1 else 1

        fig = go.Figure()

        if n_features == 1:
            # 1D data: plot as line with y=0
            unique_classes = np.unique(y)
            for i, cls in enumerate(unique_classes):
                mask = y == cls
                color = self.default_colors[i % len(self.default_colors)]

                fig.add_trace(
                    go.Scatter(
                        x=X[mask].flatten(),
                        y=np.zeros(mask.sum()),
                        mode="markers",
                        name=f"Class {cls}",
                        marker={"size": 10, "color": color},
                    )
                )

            fig.update_layout(title="1D Dataset Visualization", xaxis_title="Feature 0", yaxis={"showticklabels": False})

        elif n_features >= 2:
            # 2D scatter (use first two features)
            unique_classes = np.unique(y)
            for i, cls in enumerate(unique_classes):
                mask = y == cls
                color = self.default_colors[i % len(self.default_colors)]

                fig.add_trace(
                    go.Scatter(
                        x=X[mask, 0],
                        y=X[mask, 1],
                        mode="markers",
                        name=f"Class {cls}",
                        marker={"size": 8, "color": color, "opacity": 0.7},
                    )
                )

            fig.update_layout(title="Dataset Scatter Plot (First 2 Features)", xaxis_title="Feature 0", yaxis_title="Feature 1", yaxis={"scaleanchor": "x", "scaleratio": 1})

        is_dark = theme == "dark"
        fig.update_layout(
            hovermode="closest",
            showlegend=True,
            legend={"x": 0.7, "y": 0.95},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            font={"color": "#e9ecef" if is_dark else "#212529"},
            margin={"l": 50, "r": 20, "t": 40, "b": 40},
        )

        return fig

    def _create_distribution_plot(self, dataset: Dict[str, Any], theme: str = "light") -> go.Figure:
        """
        Create feature distribution histograms.

        Args:
            dataset: Dataset dictionary
            theme: Current theme ("light" or "dark")

        Returns:
            Plotly figure with distribution plots
        """
        inputs = dataset.get("inputs", [])

        if len(inputs) == 0:
            return create_empty_plot("No data for distribution", theme)

        X = np.array(inputs)
        n_features = X.shape[1] if len(X.shape) > 1 else 1

        # Limit to first 4 features for display
        n_plots = min(n_features, 4)

        # Create subplots
        fig = make_subplots(rows=1, cols=n_plots, subplot_titles=[f"Feature {i}" for i in range(n_plots)])

        for i in range(n_plots):
            feature_data = X[:, i] if len(X.shape) > 1 else X

            fig.add_trace(
                go.Histogram(x=feature_data, nbinsx=30, marker={"color": "#3498db"}, showlegend=False),
                row=1,
                col=i + 1,
            )

        is_dark = theme == "dark"
        fig.update_layout(
            title="Feature Distributions",
            height=400,
            margin={"l": 40, "r": 20, "t": 60, "b": 40},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            font={"color": "#e9ecef" if is_dark else "#212529"},
        )

        return fig

    def _calculate_balance(self, targets: List[Any]) -> str:
        """
        Calculate class balance information.

        Args:
            targets: List of target labels

        Returns:
            Balance information string
        """
        if not targets:
            return "N/A"

        unique, counts = np.unique(targets, return_counts=True)

        if len(unique) == 0:
            return "N/A"

        # Calculate percentage of largest class
        max_count = max(counts)
        total = sum(counts)
        balance_pct = (max_count / total) * 100

        if balance_pct > 70:
            return f"Imbalanced ({balance_pct:.0f}%)"
        elif balance_pct < 55:
            return "Balanced"
        else:
            return f"Moderate ({balance_pct:.0f}%)"

    def load_dataset(self, dataset: Dict[str, Any]):
        """
        Load a new dataset.

        Args:
            dataset: Dataset dictionary with 'inputs' and 'targets'
        """
        self.current_dataset = dataset
        self.logger.info(f"Dataset loaded: {len(dataset.get('inputs', []))} samples")

    def get_dataset(self) -> Optional[Dict[str, Any]]:
        """
        Get current dataset.

        Returns:
            Current dataset dictionary or None
        """
        return self.current_dataset
