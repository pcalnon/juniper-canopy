#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     decision_boundary.py
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
#    This file contains the code to Display the Decision Boundary for the Cascade Correlation Neural Network prototype
#       in the Juniper prototype Frontend for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#
# Decision Boundary Component
#
# Visualization of learned decision boundaries and regions
# from the trained Cascade Correlation network.
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
from typing import Any, Callable, Dict, Optional

import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output

from ..base_component import BaseComponent, create_empty_plot


class DecisionBoundary(BaseComponent):
    """
    Decision boundary visualization component.

    Displays:
    - Contour plot of decision regions
    - Data points overlaid on boundaries
    - Confidence/probability regions
    - Real-time updates as network trains
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "decision-boundary"):
        """
        Initialize decision boundary component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        # Configuration
        self.resolution = config.get("boundary_resolution", 100)
        self.show_confidence = config.get("show_confidence", True)

        # Network prediction function (set externally)
        self.predict_fn: Optional[Callable] = None

        # Current data
        self.dataset: Optional[Dict[str, Any]] = None
        self.data_bounds: Optional[Dict[str, tuple]] = None

        self.logger.info(f"DecisionBoundary initialized with resolution={self.resolution}")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for decision boundary component.

        Returns:
            Dash Div containing the boundary visualization
        """
        return html.Div(
            [
                # Header with controls
                html.Div(
                    [
                        html.H3("Decision Boundary", style={"display": "inline-block"}),
                        html.Div(
                            [
                                html.Label("Resolution:", style={"marginRight": "10px"}),
                                dcc.Slider(
                                    id=f"{self.component_id}-resolution-slider",
                                    min=50,
                                    max=200,
                                    step=25,
                                    value=self.resolution,
                                    marks={50: "50", 100: "100", 150: "150", 200: "200"},
                                    tooltip={"placement": "bottom", "always_visible": False},
                                ),
                                html.Label("Show Confidence:", style={"marginLeft": "20px", "marginRight": "10px"}),
                                dcc.Checklist(
                                    id=f"{self.component_id}-show-confidence",
                                    options=[{"label": "", "value": "show"}],
                                    value=["show"] if self.show_confidence else [],
                                    style={"display": "inline-block"},
                                ),
                            ],
                            style={"display": "inline-block", "float": "right", "width": "400px"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                # Status indicator with refresh button
                html.Div(
                    [
                        html.Div(
                            id=f"{self.component_id}-status",
                            children="Status: No network loaded",
                            style={
                                "padding": "5px 10px",
                                "backgroundColor": "#6c757d",
                                "color": "white",
                                "borderRadius": "3px",
                                "display": "inline-block",
                            },
                        ),
                        dbc.Button(
                            "↻ Refresh",
                            id=f"{self.component_id}-refresh-btn",
                            size="sm",
                            color="secondary",
                            outline=True,
                            className="ms-3",
                            title="Recalculate decision boundary with current network state",
                        ),
                    ],
                    style={"marginBottom": "10px", "display": "flex", "alignItems": "center"},
                ),
                # Main boundary plot
                dcc.Graph(
                    id=f"{self.component_id}-plot",
                    config={"displayModeBar": True, "displaylogo": False},
                    style={"height": "800px", "maxWidth": "900px", "margin": "0 auto"},
                ),
                # Data stores (updates driven by dashboard_manager slow-update-interval)
                dcc.Store(id=f"{self.component_id}-boundary-data", data=None),
                dcc.Store(id=f"{self.component_id}-dataset-data", data=None),
            ],
            style={"padding": "20px"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for decision boundary component.

        Args:
            app: Dash application instance
        """

        # PERF-CN-01: prevent_initial_call=False — must render initial empty
        # decision-boundary plot and status text on mount; theme-aware so it
        # must redraw when the theme store fires.
        @app.callback(
            [Output(f"{self.component_id}-plot", "figure"), Output(f"{self.component_id}-status", "children")],
            [
                Input(f"{self.component_id}-boundary-data", "data"),
                Input(f"{self.component_id}-dataset-data", "data"),
                Input(f"{self.component_id}-resolution-slider", "value"),
                Input(f"{self.component_id}-show-confidence", "value"),
                Input("theme-state", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_boundary_plot(
            boundary_data: Optional[Dict[str, Any]],
            dataset: Optional[Dict[str, Any]],
            resolution: int,
            show_confidence: list,
            theme: str,
        ):
            """
            Update decision boundary visualization.

            Args:
                boundary_data: Pre-computed boundary data
                dataset: Dataset for overlay
                resolution: Grid resolution
                show_confidence: Whether to show confidence regions
                theme: Current theme ("light" or "dark")

            Returns:
                Tuple of (figure, status_text)
            """
            if not boundary_data and not self.predict_fn:
                empty_fig = create_empty_plot("No network loaded", theme)
                return empty_fig, "Status: No network loaded"

            # Update resolution
            self.resolution = resolution
            show_conf = "show" in show_confidence

            # Create boundary plot
            if boundary_data:
                fig = self._create_boundary_plot(boundary_data, dataset, show_conf, theme)
                status = "Status: Displaying decision boundary"
            else:
                # Compute boundary if predict function available
                if self.predict_fn and dataset:
                    computed_boundary = self._compute_decision_boundary(dataset)
                    fig = self._create_boundary_plot(computed_boundary, dataset, show_conf, theme)
                    status = "Status: Live boundary computation"
                else:
                    fig = create_empty_plot("Waiting for network predictions...", theme)
                    status = "Status: Waiting for data"

            return fig, status

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _compute_decision_boundary(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute decision boundary from network predictions.

        Args:
            dataset: Dataset to determine boundaries for

        Returns:
            Dictionary with meshgrid and predictions
        """
        if not self.predict_fn:
            return {}

        inputs = np.array(dataset.get("inputs", []))

        if len(inputs) == 0 or inputs.shape[1] < 2:
            return {}

        # Determine bounds from data
        x_min, x_max = inputs[:, 0].min() - 1, inputs[:, 0].max() + 1
        y_min, y_max = inputs[:, 1].min() - 1, inputs[:, 1].max() + 1

        # Create meshgrid
        xx, yy = np.meshgrid(np.linspace(x_min, x_max, self.resolution), np.linspace(y_min, y_max, self.resolution))

        # Predict on grid
        grid_points = np.c_[xx.ravel(), yy.ravel()]

        try:
            predictions = self.predict_fn(grid_points)

            # Handle different prediction formats
            if len(predictions.shape) > 1:
                # Multi-output: use first output or argmax
                if predictions.shape[1] > 1:
                    Z = np.argmax(predictions, axis=1)
                else:
                    Z = predictions[:, 0]
            else:
                Z = predictions

            Z = Z.reshape(xx.shape)

        except Exception as e:
            self.logger.error(f"Error computing predictions: {e}")
            return {}

        return {
            "xx": xx.tolist(),
            "yy": yy.tolist(),
            "Z": Z.tolist(),
            "bounds": {"x_min": float(x_min), "x_max": float(x_max), "y_min": float(y_min), "y_max": float(y_max)},
        }

    def _create_boundary_plot(
        self,
        boundary_data: Dict[str, Any],
        dataset: Optional[Dict[str, Any]],
        show_confidence: bool,
        theme: str = "light",
    ) -> go.Figure:
        """
        Create decision boundary visualization.

        Args:
            boundary_data: Boundary grid data
            dataset: Dataset for overlay
            show_confidence: Whether to show confidence contours
            theme: Current theme ("light" or "dark")

        Returns:
            Plotly figure object
        """
        fig = go.Figure()

        # Extract boundary data
        xx = np.array(boundary_data.get("xx", []))
        yy = np.array(boundary_data.get("yy", []))
        Z = np.array(boundary_data.get("Z", []))

        if len(xx) == 0 or len(yy) == 0 or len(Z) == 0:
            return create_empty_plot("No boundary data available", theme)

        # Add contour/heatmap for decision regions
        if show_confidence:
            # Contour plot with confidence levels
            fig.add_trace(
                go.Contour(
                    x=xx[0],
                    y=yy[:, 0],
                    z=Z,
                    colorscale="RdYlBu",
                    showscale=True,
                    colorbar={"title": "Prediction"},
                    contours={"coloring": "heatmap", "showlabels": True},
                    hoverinfo="x+y+z",
                    name="Decision Boundary",
                )
            )
        else:
            # Simple filled contours
            fig.add_trace(
                go.Contour(
                    x=xx[0],
                    y=yy[:, 0],
                    z=Z,
                    colorscale="RdYlBu",
                    showscale=False,
                    contours={"coloring": "fill"},
                    hoverinfo="skip",
                    name="Decision Regions",
                )
            )

        # Overlay data points if available
        if dataset:
            inputs = np.array(dataset.get("inputs", []))
            targets = np.array(dataset.get("targets", []))

            if len(inputs) > 0 and inputs.shape[1] >= 2:
                unique_classes = np.unique(targets)
                colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6"]

                for i, cls in enumerate(unique_classes):
                    mask = targets == cls
                    color = colors[i % len(colors)]

                    fig.add_trace(
                        go.Scatter(
                            x=inputs[mask, 0],
                            y=inputs[mask, 1],
                            mode="markers",
                            name=f"Class {cls}",
                            marker={"size": 8, "color": color, "line": {"width": 1, "color": "white"}},
                        )
                    )

        # Update layout
        is_dark = theme == "dark"
        fig.update_layout(
            title="Decision Boundary Visualization",
            xaxis_title="Feature 0",
            yaxis_title="Feature 1",
            yaxis={"scaleanchor": "x", "scaleratio": 1},
            hovermode="closest",
            showlegend=True,
            legend={"x": 0.02, "y": 0.98},
            margin={"l": 50, "r": 20, "t": 40, "b": 40},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            font={"color": "#e9ecef" if is_dark else "#212529"},
        )

        return fig

    def set_prediction_function(self, predict_fn: Callable):
        """
        Set the network prediction function for real-time boundary computation.

        Args:
            predict_fn: Function that takes inputs and returns predictions
        """
        self.predict_fn = predict_fn
        self.logger.info("Prediction function registered")

    def update_dataset(self, dataset: Dict[str, Any]):
        """
        Update the dataset for boundary visualization.

        Args:
            dataset: Dataset dictionary
        """
        self.dataset = dataset

        # Update bounds
        if dataset:
            inputs = np.array(dataset.get("inputs", []))
            if len(inputs) > 0 and inputs.shape[1] >= 2:
                self.data_bounds = {
                    "x": (inputs[:, 0].min(), inputs[:, 0].max()),
                    "y": (inputs[:, 1].min(), inputs[:, 1].max()),
                }

        self.logger.debug("Dataset updated for boundary visualization")

    def compute_and_cache_boundary(self) -> Optional[Dict[str, Any]]:
        """
        Compute boundary data for caching.

        Returns:
            Boundary data dictionary or None
        """
        return self._compute_decision_boundary(self.dataset) if self.dataset else None
