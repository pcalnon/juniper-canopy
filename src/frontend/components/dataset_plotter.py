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

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output
from plotly.subplots import make_subplots

from ..base_component import BaseComponent


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
        return html.Div(
            [
                # Header with controls
                html.Div(
                    [
                        html.H3("Dataset Visualization", style={"display": "inline-block"}),
                        html.Div(
                            [
                                html.Label("Dataset:", style={"marginRight": "10px"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-dataset-selector",
                                    options=[],  # Populated dynamically
                                    value=None,
                                    placeholder="Select dataset...",
                                    style={"width": "200px", "display": "inline-block"},
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
                            style={"display": "inline-block", "float": "right"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
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
                    style={
                        "marginBottom": "15px",
                        "padding": "10px",
                        "backgroundColor": "#f8f9fa",
                        "borderRadius": "3px",
                    },
                ),
                # Main scatter plot
                dcc.Graph(
                    id=f"{self.component_id}-scatter-plot",
                    config={"displayModeBar": True, "displaylogo": False},
                    style={"height": "500px"},
                ),
                # Feature distribution histograms
                dcc.Graph(
                    id=f"{self.component_id}-distribution-plot",
                    config={"displayModeBar": False},
                    style={"height": "300px"},
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
            empty_fig = self._create_empty_plot("No dataset loaded", theme)
            return empty_fig, empty_fig, "0", "0", "0", "N/A"

        # Filter data by split
        filtered_data = self._filter_by_split(dataset, split)

        # Create plots
        scatter_fig = self._create_scatter_plot(filtered_data, theme)
        dist_fig = self._create_distribution_plot(filtered_data, theme)

        # Calculate statistics
        n_samples = len(filtered_data.get("inputs", []))
        n_features = len(filtered_data["inputs"][0]) if filtered_data.get("inputs") else 0
        targets = filtered_data.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0

        # Class balance
        balance_info = self._calculate_balance(targets) if targets else "N/A"

        return (scatter_fig, dist_fig, str(n_samples), str(n_features), str(unique_classes), balance_info)

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
            return self._create_empty_plot("No data available", theme)

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

            fig.update_layout(title="Dataset Scatter Plot (First 2 Features)", xaxis_title="Feature 0", yaxis_title="Feature 1")

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
            return self._create_empty_plot("No data for distribution", theme)

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
            height=300,
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

    def _create_empty_plot(self, message: str = "No data", theme: str = "light") -> go.Figure:
        """
        Create empty placeholder plot.

        Args:
            message: Message to display
            theme: Current theme ("light" or "dark")

        Returns:
            Empty Plotly figure
        """
        fig = go.Figure()

        is_dark = theme == "dark"
        text_color = "#adb5bd" if is_dark else "#6c757d"

        fig.add_annotation(
            text=message,
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
