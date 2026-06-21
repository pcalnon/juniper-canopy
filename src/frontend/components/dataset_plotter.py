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
from dash.dependencies import Input, Output
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
                # Main scatter plot
                dcc.Graph(
                    id=f"{self.component_id}-scatter-plot",
                    config={"displayModeBar": True, "displaylogo": False},
                    style={"height": "800px", "maxWidth": "900px", "margin": "0 auto"},
                ),
                # Feature distribution histograms
                dcc.Graph(
                    id=f"{self.component_id}-distribution-plot",
                    config={"displayModeBar": False},
                    style={"height": "30vh", "maxHeight": "450px", "minHeight": "250px"},
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
            ],
            prevent_initial_call=False,
        )
        def update_dataset_plots(dataset: Optional[Dict[str, Any]], split: str, theme: str):
            """
            Update dataset visualizations.

            Args:
                dataset: Dataset dictionary
                split: Data split to display ('all', 'train', 'test')
                theme: Current theme ("light" or "dark")

            Returns:
                Tuple of updated components
            """
            return self._process_dataset_update(dataset, split, theme)

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

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _process_dataset_update(self, dataset: Optional[Dict[str, Any]], split: str, theme: str) -> tuple:
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
            return self._process_sequence_update(dataset, theme)

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

    def _process_sequence_update(self, dataset: Dict[str, Any], theme: str) -> tuple:
        """CANOPY-3D-1 (Phase 1): render a 3-D sequence (time-series) dataset.

        Compare-signals on window 0 — feature small-multiples over real (cumulative-Δt)
        time, plus a Δt strip. Returns the same 6-tuple as the tabular path so the
        ``update_dataset_plots`` callback Outputs are unchanged.
        """
        seq = dataset.get("sequence", {})
        scatter_fig = self._create_sequence_plot(seq, theme)
        dist_fig = self._create_dt_strip(seq, theme)
        return (
            scatter_fig,
            dist_fig,
            str(dataset.get("n_windows", 0)),
            str(dataset.get("n_features", 0)),
            "0",
            "N/A",
        )

    def _create_sequence_plot(self, seq: Dict[str, Any], theme: str = "light") -> go.Figure:
        """Window-0 feature small-multiples over real (cumulative-Δt) time (Phase 1)."""
        X = np.array(seq.get("X", []), dtype=float)  # (L, F)
        dt = np.array(seq.get("dt", []), dtype=float)  # (L,)
        labels = seq.get("feature_labels", [])
        if X.ndim != 2 or X.shape[0] == 0:
            return create_empty_plot("No sequence data available", theme)
        length, n_features = X.shape
        t = np.cumsum(dt) if dt.size == length else np.arange(length, dtype=float)
        fig = go.Figure()
        for i in range(n_features):
            col = X[:, i]
            span = float(col.max() - col.min())
            norm = (col - col.min()) / (span + 1e-9)
            fig.add_trace(
                go.Scatter(
                    x=t,
                    y=norm + (n_features - 1 - i) * 1.15,
                    mode="lines+markers",
                    name=labels[i] if i < len(labels) else f"Feature {i}",
                    line={"color": self.default_colors[i % len(self.default_colors)]},
                    marker={"size": 4},
                )
            )
        is_dark = theme == "dark"
        fig.update_layout(
            title="Sequence — feature small-multiples (window 0, real time)",
            xaxis_title="time (cumulative Δt)",
            yaxis={"title": "features (offset, normalized)", "showticklabels": False},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            showlegend=True,
            hovermode="closest",
        )
        return fig

    def _create_dt_strip(self, seq: Dict[str, Any], theme: str = "light") -> go.Figure:
        """Per-step Δt strip over real time — the irregular-sampling companion (Phase 1)."""
        dt = np.array(seq.get("dt", []), dtype=float)
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
