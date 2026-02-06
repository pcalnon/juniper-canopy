#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     dashboard_manager.py
# Author:        Paul Calnon
# Version:       0.2.0
#
# Date:          2025-10-11
# Last Modified: 2026-01-07
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#
#####################################################################################################################################################################################################
# Notes:
#
#     Dashboard Manager Module
#
#     Central coordination hub for all frontend components, managing layout,
#     routing, and component lifecycle.
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

import logging
import os
import time
from typing import Any, Dict, List
from urllib.parse import urljoin

import dash
import dash_bootstrap_components as dbc
import requests
from dash import dcc, html
from dash.dependencies import Input, Output
from flask import request

from canopy_constants import DashboardConstants, TrainingConstants
from config_manager import ConfigManager

from .base_component import BaseComponent
from .callback_context import get_callback_context
from .components.about_panel import AboutPanel
from .components.cassandra_panel import CassandraPanel
from .components.dataset_plotter import DatasetPlotter
from .components.decision_boundary import DecisionBoundary
from .components.hdf5_snapshots_panel import HDF5SnapshotsPanel
from .components.metrics_panel import MetricsPanel
from .components.network_visualizer import NetworkVisualizer
from .components.redis_panel import RedisPanel


class DashboardManager:
    """
    Central dashboard manager for Juniper Canopy.

    Manages:
    - Dashboard layout
    - Component registration
    - Callback coordination
    - Session management
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize dashboard manager.
        Args:
            config: Frontend configuration dictionary
        """
        self.logger = logging.getLogger(__name__)
        self.config = config

        # Initialize ConfigManager for training defaults
        self.config_mgr = ConfigManager()

        # Get training defaults with environment variable support
        self.training_defaults = self._get_training_defaults_with_env()

        # Get assets folder path (relative to this file)
        from pathlib import Path

        assets_path = Path(__file__).parent / "assets"

        # Initialize Dash app with Bootstrap theme. Creates standalone Flask server that
        # will be mounted to FastAPI via WSGIMiddleware. Use requests_pathname_prefix
        # instead of url_base_pathname to avoid double-pathing when mounted at
        # /dashboard by FastAPI
        self.app = dash.Dash(
            __name__,
            requests_pathname_prefix="/dashboard/",  # Dashboard accessible: /dashboard/
            suppress_callback_exceptions=True,
            title="Juniper Canopy Dashboard",
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            assets_folder=str(assets_path),  # WebSocket client and other assets
        )

        # Registered components
        self.components: List[BaseComponent] = []

        # Initialize core components
        self._initialize_components()

        # Set up layout
        self._setup_layout()

        # Set up callbacks
        self._setup_callbacks()

        self.logger.info("DashboardManager initialized with all MVP components")

    def _get_training_defaults_with_env(self) -> Dict[str, float]:
        """
        Get training parameter defaults with environment variable override support.

        Configuration hierarchy (highest to lowest priority):
        1. Environment variables (CASCOR_TRAINING_*)
        2. YAML configuration (conf/app_config.yaml)
        3. Constants module (TrainingConstants)

        Returns:
            Dictionary with learning_rate, hidden_units, epochs
        """
        defaults = self.config_mgr.get_training_defaults()

        # Apply environment variable overrides
        if lr_env := os.getenv("CASCOR_TRAINING_LEARNING_RATE"):
            try:
                defaults["learning_rate"] = float(lr_env)
                self.logger.info(f"Learning rate overridden by env var: {lr_env}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_TRAINING_LEARNING_RATE: {lr_env}")

        if hu_env := os.getenv("CASCOR_TRAINING_HIDDEN_UNITS"):
            try:
                defaults["hidden_units"] = int(hu_env)
                self.logger.info(f"Hidden units overridden by env var: {hu_env}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_TRAINING_HIDDEN_UNITS: {hu_env}")

        if epochs_env := os.getenv("CASCOR_TRAINING_EPOCHS"):
            try:
                defaults["epochs"] = int(epochs_env)
                self.logger.info(f"Epochs overridden by env var: {epochs_env}")
            except ValueError:
                self.logger.warning(f"Invalid CASCOR_TRAINING_EPOCHS: {epochs_env}")

        # Fallback to constants if not in config
        if "learning_rate" not in defaults:
            defaults["learning_rate"] = TrainingConstants.DEFAULT_LEARNING_RATE
        if "hidden_units" not in defaults:
            defaults["hidden_units"] = TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS
        if "epochs" not in defaults:
            defaults["epochs"] = TrainingConstants.DEFAULT_TRAINING_EPOCHS

        return defaults

    def _initialize_components(self):
        """Initialize all dashboard components."""
        # Create component instances
        self.metrics_panel = MetricsPanel(self.config.get("metrics_panel", {}), component_id="metrics-panel")

        self.network_visualizer = NetworkVisualizer(self.config.get("network_visualizer", {}), component_id="network-visualizer")

        self.dataset_plotter = DatasetPlotter(self.config.get("dataset_plotter", {}), component_id="dataset-plotter")

        self.decision_boundary = DecisionBoundary(self.config.get("decision_boundary", {}), component_id="decision-boundary")

        self.about_panel = AboutPanel(self.config.get("about_panel", {}), component_id="about-panel")

        self.hdf5_snapshots_panel = HDF5SnapshotsPanel(self.config.get("hdf5_snapshots_panel", {}), component_id="hdf5-snapshots-panel")

        # P3-6: Redis Monitoring Panel
        self.redis_panel = RedisPanel(self.config.get("redis_panel", {}), component_id="redis-panel")

        # P3-7: Cassandra Monitoring Panel
        self.cassandra_panel = CassandraPanel(self.config.get("cassandra_panel", {}), component_id="cassandra-panel")

        # Register components
        self.register_component(self.metrics_panel)
        self.register_component(self.network_visualizer)
        self.register_component(self.dataset_plotter)
        self.register_component(self.decision_boundary)
        self.register_component(self.about_panel)
        self.register_component(self.hdf5_snapshots_panel)
        self.register_component(self.redis_panel)
        self.register_component(self.cassandra_panel)

        self.logger.info("All MVP components initialized and registered")

    def _setup_layout(self):
        """Set up dashboard layout with all MVP components."""
        self.app.layout = dbc.Container(
            [
                # Header with Dark Mode Toggle
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H1(
                                    "Juniper Canopy Dashboard",
                                    className="text-center",
                                    style={"color": "#2c3e50", "marginTop": "20px"},
                                ),
                                html.P(
                                    "Real-time monitoring for Cascade Correlation Neural Networks",
                                    className="text-center text-muted",
                                ),
                            ],
                            width=10,
                        ),
                        dbc.Col(
                            [
                                html.Button(
                                    "🌙",
                                    id="dark-mode-toggle",
                                    n_clicks=0,
                                    title="Toggle Dark Mode",
                                    style={"marginTop": "20px"},
                                )
                            ],
                            width=2,
                            className="text-end",
                        ),
                    ]
                ),
                html.Hr(),
                # Dark mode state store (persisted in localStorage)
                dcc.Store(id="dark-mode-store", storage_type="local", data=False),
                # Theme state for components (tracks current theme)
                dcc.Store(id="theme-state", data="light"),
                # Unified Top Status Bar - Connection, Status, Phase, Metrics, and Latency
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        # Latency indicator (colored circle)
                                                        html.Span(
                                                            "●",
                                                            id="status-indicator",
                                                            style={
                                                                "fontSize": "16px",
                                                                "color": "#28a745",
                                                                "marginRight": "12px",
                                                            },
                                                        ),
                                                        # Status with label
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Status: ",
                                                                    style={"color": "#6c757d"},
                                                                ),
                                                                html.Span(
                                                                    id="top-status-display",
                                                                    children="Stopped",
                                                                    style={"fontWeight": "bold", "color": "#6c757d"},
                                                                ),
                                                            ],
                                                            style={"marginRight": "8px"},
                                                        ),
                                                        html.Span(
                                                            " | ",
                                                            style={"color": "#6c757d", "marginRight": "8px"},
                                                        ),
                                                        # Phase with label
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Phase: ",
                                                                    style={"color": "#6c757d"},
                                                                ),
                                                                html.Span(
                                                                    id="top-phase-display",
                                                                    children="Idle",
                                                                    style={"fontWeight": "bold", "color": "#6c757d"},
                                                                ),
                                                            ],
                                                            style={"marginRight": "8px"},
                                                        ),
                                                        html.Span(
                                                            " | ",
                                                            style={"color": "#6c757d", "marginRight": "8px"},
                                                        ),
                                                        # Epoch display
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Epoch: ",
                                                                    style={"color": "#6c757d"},
                                                                ),
                                                                html.Span(
                                                                    id="top-epoch-display",
                                                                    children="0",
                                                                    style={"fontWeight": "bold", "color": "#17a2b8"},
                                                                ),
                                                            ],
                                                            style={"marginRight": "8px"},
                                                        ),
                                                        html.Span(
                                                            " | ",
                                                            style={"color": "#6c757d", "marginRight": "8px"},
                                                        ),
                                                        # Hidden Units display
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Hidden Units: ",
                                                                    style={"color": "#6c757d"},
                                                                ),
                                                                html.Span(
                                                                    id="top-hidden-units-display",
                                                                    children="0",
                                                                    style={"fontWeight": "bold", "color": "#17a2b8"},
                                                                ),
                                                            ],
                                                            style={"marginRight": "20px"},
                                                        ),
                                                        # Latency display (right side)
                                                        html.Span(
                                                            id="latency-display",
                                                            children="",
                                                            style={
                                                                "marginLeft": "auto",
                                                                "color": "#6c757d",
                                                                "fontSize": "0.9em",
                                                            },
                                                        ),
                                                    ],
                                                    style={
                                                        "display": "flex",
                                                        "alignItems": "center",
                                                        "flexWrap": "wrap",
                                                    },
                                                ),
                                            ],
                                            className="py-2",
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                            ],
                            width=12,
                        ),
                    ]
                ),
                # Hidden element to keep old connection-status for backward compat
                html.Div(id="connection-status", style={"display": "none"}),
                # Main content area with tabs
                dbc.Row(
                    [
                        # Left sidebar - Controls and Information
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H5("Training Controls")),
                                        dbc.CardBody(
                                            [
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            "▶ Start Training",
                                                            id="start-button",
                                                            className="mb-2 w-100 training-control-btn btn-start",
                                                        ),
                                                        dbc.Button(
                                                            "⏸ Pause Training",
                                                            id="pause-button",
                                                            className="mb-2 w-100 training-control-btn btn-pause",
                                                        ),
                                                        dbc.Button(
                                                            "⏯ Resume Training",
                                                            id="resume-button",
                                                            className="mb-2 w-100 training-control-btn btn-resume",
                                                        ),
                                                        dbc.Button(
                                                            "⏹ Stop Training",
                                                            id="stop-button",
                                                            className="mb-2 w-100 training-control-btn btn-stop",
                                                        ),
                                                    ],
                                                    className="training-button-group",
                                                ),
                                                html.Hr(className="my-3"),
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            "↻ Reset Training",
                                                            id="reset-button",
                                                            className="mb-2 w-100 training-control-btn btn-reset",
                                                        ),
                                                    ],
                                                    className="training-button-group",
                                                ),
                                                html.Hr(),
                                                html.P("Learning Rate:", className="mb-1 fw-bold"),
                                                dbc.Input(
                                                    id="learning-rate-input",
                                                    type="number",
                                                    value=self.training_defaults.get("learning_rate", TrainingConstants.DEFAULT_LEARNING_RATE),
                                                    step=0.001,
                                                    min=self.config_mgr.get_training_param_config("learning_rate").get("min", TrainingConstants.MIN_LEARNING_RATE),
                                                    max=self.config_mgr.get_training_param_config("learning_rate").get("max", TrainingConstants.MAX_LEARNING_RATE),
                                                    className="mb-2",
                                                    debounce=True,
                                                ),
                                                html.P("Max Hidden Units:", className="mb-1 fw-bold"),
                                                dbc.Input(
                                                    id="max-hidden-units-input",
                                                    type="number",
                                                    value=self.training_defaults.get("hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS),
                                                    step=1,
                                                    min=self.config_mgr.get_training_param_config("hidden_units").get("min", TrainingConstants.MIN_HIDDEN_UNITS),
                                                    max=self.config_mgr.get_training_param_config("hidden_units").get("max", TrainingConstants.MAX_HIDDEN_UNITS),
                                                    className="mb-2",
                                                    debounce=True,
                                                ),
                                                html.P("Maximum Epochs:", className="mb-1 fw-bold"),
                                                dbc.Input(
                                                    id="max-epochs-input",
                                                    type="number",
                                                    value=self.training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS),
                                                    step=1,
                                                    min=self.config_mgr.get_training_param_config("epochs").get("min", TrainingConstants.MIN_TRAINING_EPOCHS),
                                                    max=self.config_mgr.get_training_param_config("epochs").get("max", TrainingConstants.MAX_TRAINING_EPOCHS),
                                                    className="mb-2",
                                                    debounce=True,
                                                ),
                                                html.Hr(),
                                                html.Div(
                                                    [
                                                        dbc.Button(
                                                            "Apply Parameters",
                                                            id="apply-params-button",
                                                            className="w-100 mb-2",
                                                            color="primary",
                                                            disabled=True,
                                                        ),
                                                        html.Div(
                                                            id="params-status",
                                                            children="",
                                                            style={
                                                                "fontSize": "0.85em",
                                                                "color": "#6c757d",
                                                                "textAlign": "center",
                                                            },
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
                                            html.H5(
                                                "Network Information",
                                                id="network-info-header",
                                                style={"cursor": "pointer", "userSelect": "none"},
                                            ),
                                            id="network-info-card-header",
                                        ),
                                        dbc.Collapse(
                                            dbc.CardBody(
                                                [
                                                    html.Div(id="network-info-panel"),
                                                    html.Hr(),
                                                    html.H6(
                                                        "Network Information: Details",
                                                        id="network-info-details-header",
                                                        style={
                                                            "cursor": "pointer",
                                                            "userSelect": "none",
                                                            "marginTop": "10px",
                                                        },
                                                    ),
                                                    dbc.Collapse(
                                                        html.Div(id="network-info-details-panel", style={"marginTop": "10px"}),
                                                        id="network-info-details-collapse",
                                                        is_open=False,
                                                    ),
                                                ]
                                            ),
                                            id="network-info-collapse",
                                            is_open=True,
                                        ),
                                    ]
                                ),
                            ],
                            width=3,
                        ),
                        # Right panel - Visualizations with tabs
                        dbc.Col(
                            [
                                dbc.Tabs(
                                    [
                                        dbc.Tab(
                                            self.metrics_panel.get_layout(),
                                            label="Training Metrics",
                                            tab_id="metrics",
                                        ),
                                        dbc.Tab(
                                            self.network_visualizer.get_layout(),
                                            label="Network Topology",
                                            tab_id="topology",
                                        ),
                                        dbc.Tab(
                                            self.decision_boundary.get_layout(),
                                            label="Decision Boundaries",
                                            tab_id="boundaries",
                                        ),
                                        dbc.Tab(
                                            self.dataset_plotter.get_layout(),
                                            label="Dataset View",
                                            tab_id="dataset",
                                        ),
                                        dbc.Tab(
                                            self.hdf5_snapshots_panel.get_layout(),
                                            label="HDF5 Snapshots",
                                            tab_id="snapshots",
                                        ),
                                        dbc.Tab(
                                            self.redis_panel.get_layout(),
                                            label="Redis",
                                            tab_id="redis",
                                        ),
                                        dbc.Tab(
                                            self.cassandra_panel.get_layout(),
                                            label="Cassandra",
                                            tab_id="cassandra",
                                        ),
                                        dbc.Tab(
                                            self.about_panel.get_layout(),
                                            label="About",
                                            tab_id="about",
                                        ),
                                    ],
                                    id="visualization-tabs",
                                    active_tab="metrics",
                                )
                            ],
                            width=9,
                        ),
                    ]
                ),
                # Update intervals
                dcc.Interval(id="fast-update-interval", interval=DashboardConstants.FAST_UPDATE_INTERVAL_MS, n_intervals=0),
                dcc.Interval(id="slow-update-interval", interval=DashboardConstants.SLOW_UPDATE_INTERVAL_MS, n_intervals=0),
                # Hidden div to store WebSocket data
                html.Div(id="websocket-data", style={"display": "none"}),
                dcc.Store(id="training-control-action", data=None),
                # Parameter state store (tracks last known backend state)
                dcc.Store(
                    id="backend-params-state",
                    data={
                        "learning_rate": TrainingConstants.DEFAULT_LEARNING_RATE,
                        "max_hidden_units": TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS,
                        "max_epochs": TrainingConstants.DEFAULT_TRAINING_EPOCHS,
                    },
                ),
                # Button state management stores
                dcc.Store(
                    id="button-states",
                    data={
                        "start": {"disabled": False, "loading": False, "timestamp": 0},
                        "pause": {"disabled": False, "loading": False, "timestamp": 0},
                        "stop": {"disabled": False, "loading": False, "timestamp": 0},
                        "resume": {"disabled": False, "loading": False, "timestamp": 0},
                        "reset": {"disabled": False, "loading": False, "timestamp": 0},
                    },
                ),
                dcc.Store(id="last-button-click", data={"button": None, "timestamp": 0}),
                # Stores for parameter tracking
                dcc.Store(
                    id="pending-params-store",
                    data={"learning_rate": None, "max_hidden_units": None, "max_epochs": None},
                ),
                dcc.Store(
                    id="applied-params-store",
                    data={},
                ),
            ],
            fluid=True,
        )

    def _api_url(self, path: str) -> str:
        """
        Build API URL from Flask request context.

        Handles WSGI mount at /dashboard/ correctly by using origin (scheme + host)
        instead of host_url which includes the mount path.

        Args:
            path: API path (e.g., "/api/health")

        Returns:
            Full API URL (e.g., "http://localhost:8050/api/health")
        """
        origin = f"{request.scheme}://{request.host}"
        return urljoin(f"{origin}/", path.lstrip("/"))

    def _setup_callbacks(self):
        """Set up dashboard callbacks."""
        self._setup_theme_callbacks()  # Define theme callbacks
        self._setup_status_bar_callbacks()  # Define Status Bar callbacks
        self._setup_network_callbacks()  # Define Network callbacks
        self._setup_datastore_callbacks()  # Component data store updaters
        self._setup_button_action_callbacks()  # Define button action callbacks
        self._setup_backend_callbacks()  # Define backend callbacks

    # Define theme callbacks
    def _setup_theme_callbacks(self):
        """Set up dashboard theme callbacks."""

        @self.app.callback(
            [
                Output("dark-mode-store", "data"),
                Output("dark-mode-toggle", "children"),
            ],
            Input("dark-mode-toggle", "n_clicks"),
            prevent_initial_call=True,
        )
        def toggle_dark_mode(n_clicks):
            """Toggle dark mode on button click."""
            return self._toggle_dark_mode_handler(n_clicks=n_clicks)

        @self.app.callback(
            Output("theme-state", "data"),
            Input("dark-mode-store", "data"),
        )
        def update_theme_state(is_dark):
            """Update theme state based on dark mode store."""
            return self._update_theme_state_handler(is_dark=is_dark)

        self.app.clientside_callback(
            """
            function(is_dark) {
                const root = document.documentElement;
                if (is_dark) {
                    root.classList.add('dark-mode');
                } else {
                    root.classList.remove('dark-mode');
                }
                return is_dark;
            }
            """,
            Output("dark-mode-store", "data", allow_duplicate=True),
            Input("dark-mode-store", "data"),
            prevent_initial_call=True,
        )

    # Define Status Bar callbacks
    def _setup_status_bar_callbacks(self):

        @self.app.callback(
            [
                Output("status-indicator", "style"),
                Output("connection-status", "children"),
                Output("latency-display", "children"),
                Output("top-status-display", "children"),
                Output("top-status-display", "style"),
                Output("top-phase-display", "children"),
                Output("top-phase-display", "style"),
                Output("top-epoch-display", "children"),
                Output("top-hidden-units-display", "children"),
            ],
            Input("fast-update-interval", "n_intervals"),
        )
        def update_unified_status_bar(n_intervals):
            """Update unified status bar with all state info."""
            return self._update_unified_status_bar_handler(n_intervals=n_intervals)

    # Define Network callbacks
    def _setup_network_callbacks(self):

        @self.app.callback(
            Output("network-info-panel", "children"),
            Input("slow-update-interval", "n_intervals"),
        )
        def update_network_info(n):
            """Update network information panel from API."""
            return self._update_network_info_handler(n=n)

        @self.app.callback(
            Output("network-info-collapse", "is_open"),
            Input("network-info-header", "n_clicks"),
            prevent_initial_call=True,
        )
        def toggle_network_info(n):
            """Toggle Network Information section collapse state."""
            return self._toggle_network_info_handler(n=n)

        @self.app.callback(
            Output("network-info-details-collapse", "is_open"),
            Input("network-info-details-header", "n_clicks"),
            prevent_initial_call=True,
        )
        def toggle_network_info_details(n):
            """Toggle Network Information: Details section collapse state."""
            return self._toggle_network_info_details_handler(n=n)

        @self.app.callback(
            Output("network-info-details-panel", "children"),
            Input("slow-update-interval", "n_intervals"),
        )
        def update_network_info_details(n):
            """Update detailed network information panel from API."""
            return self._update_network_info_details_handler(n=n)

    # Component data store updaters
    def _setup_datastore_callbacks(self):

        @self.app.callback(
            Output("metrics-panel-metrics-store", "data"),
            Input("fast-update-interval", "n_intervals"),
        )
        def update_metrics_store(n):
            """Fetch metrics history from API and update metrics panel store."""
            return self._update_metrics_store_handler(n=n)

        @self.app.callback(
            Output("network-visualizer-topology-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
        )
        def update_topology_store(n, active_tab):
            """Fetch topology from API and update network visualizer store."""
            # Only update if topology tab is active
            return self._update_topology_store_handler(n=n, active_tab=active_tab)

        @self.app.callback(
            Output("dataset-plotter-dataset-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
        )
        def update_dataset_store(n, active_tab):
            """Fetch dataset from API and update dataset plotter store."""
            return self._update_dataset_store_handler(n=n, active_tab=active_tab)

        @self.app.callback(
            Output("decision-boundary-boundary-data", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
        )
        def update_boundary_store(n, active_tab):
            """Fetch decision boundary from API and update decision boundary store."""
            return self._update_boundary_store_handler(n=n, active_tab=active_tab)

        @self.app.callback(
            Output("decision-boundary-dataset-data", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
        )
        def update_boundary_dataset_store(n, active_tab):
            """Sync dataset data to decision boundary component."""
            return self._update_boundary_dataset_store_handler(n=n, active_tab=active_tab)

    # Define button action callbacks
    def _setup_button_action_callbacks(self):

        @self.app.callback(
            [
                Output("training-control-action", "data"),
                Output("button-states", "data"),
            ],
            [
                Input("start-button", "n_clicks"),
                Input("pause-button", "n_clicks"),
                Input("stop-button", "n_clicks"),
                Input("resume-button", "n_clicks"),
                Input("reset-button", "n_clicks"),
            ],
            [
                dash.dependencies.State("last-button-click", "data"),
                dash.dependencies.State("button-states", "data"),
            ],
            prevent_initial_call=True,
        )
        def handle_training_buttons(start_clicks, pause_clicks, stop_clicks, resume_clicks, reset_clicks, last_click, button_states, **kwargs):
            """Handle training control button clicks with debouncing and optimistic UI."""
            return self._handle_training_buttons_handler(
                start_clicks=start_clicks,
                pause_clicks=pause_clicks,
                stop_clicks=stop_clicks,
                resume_clicks=resume_clicks,
                reset_clicks=reset_clicks,
                last_click=last_click,
                button_states=button_states,
                **kwargs,
            )

        @self.app.callback(
            Output("last-button-click", "data"),
            Input("training-control-action", "data"),
        )
        def update_last_click(action):
            """Update last button click timestamp for debouncing."""
            return self._update_last_click_handler(action=action)

        @self.app.callback(
            [
                Output("start-button", "disabled"),
                Output("start-button", "children"),
                Output("pause-button", "disabled"),
                Output("pause-button", "children"),
                Output("stop-button", "disabled"),
                Output("stop-button", "children"),
                Output("resume-button", "disabled"),
                Output("resume-button", "children"),
                Output("reset-button", "disabled"),
                Output("reset-button", "children"),
            ],
            Input("button-states", "data"),
        )
        def update_button_appearance(button_states):
            """Update button states (disabled/loading) with visual feedback."""
            return self._update_button_appearance_handler(button_states=button_states)

        @self.app.callback(
            Output("button-states", "data", allow_duplicate=True),
            [
                Input("training-control-action", "data"),
                Input("fast-update-interval", "n_intervals"),
            ],
            dash.dependencies.State("button-states", "data"),
            prevent_initial_call=True,
        )
        def handle_button_timeout_and_acks(action, n_intervals, button_states):
            """Re-enable buttons after timeout (5s) or on control acknowledgment."""
            return self._handle_button_timeout_and_acks_handler(action=action, n_intervals=n_intervals, button_states=button_states)

    # Define backend callbacks
    def _setup_backend_callbacks(self):

        @self.app.callback(
            [
                Output("learning-rate-input", "value"),
                Output("max-hidden-units-input", "value"),
                Output("max-epochs-input", "value"),
            ],
            Input("backend-params-state", "data"),
            prevent_initial_call=True,
        )
        def sync_input_values_from_backend(backend_state):
            """Sync input values from backend state (only when backend changes)."""
            return self._sync_input_values_from_backend_handler(backend_state=backend_state)

        @self.app.callback(
            Output("backend-params-state", "data"),
            Input("slow-update-interval", "n_intervals"),
        )
        def sync_backend_params(n):
            """Sync backend parameter state to store."""
            return self._sync_backend_params_handler(n=n)

        @self.app.callback(
            Output("training-control-action", "data", allow_duplicate=True),
            [
                Input("learning-rate-input", "value"),
                Input("max-hidden-units-input", "value"),
            ],
            prevent_initial_call=True,
        )
        def handle_parameter_changes(learning_rate, max_hidden_units):
            """Handle parameter input changes - now just logs, actual send is via Apply button."""
            return self._handle_parameter_changes_handler(learning_rate=learning_rate, max_hidden_units=max_hidden_units)

        # Track parameter changes to enable/disable Apply button
        @self.app.callback(
            [
                Output("apply-params-button", "disabled"),
                Output("params-status", "children"),
            ],
            [
                Input("learning-rate-input", "value"),
                Input("max-hidden-units-input", "value"),
                Input("max-epochs-input", "value"),
                Input("applied-params-store", "data"),
            ],
        )
        def track_param_changes(lr, hu, epochs, applied):
            """Enable Apply button when parameters differ from applied values."""
            return self._track_param_changes_handler(lr, hu, epochs, applied)

        # Handle Apply button click
        @self.app.callback(
            [
                Output("applied-params-store", "data"),
                Output("params-status", "children", allow_duplicate=True),
            ],
            Input("apply-params-button", "n_clicks"),
            [
                dash.dependencies.State("learning-rate-input", "value"),
                dash.dependencies.State("max-hidden-units-input", "value"),
                dash.dependencies.State("max-epochs-input", "value"),
            ],
            prevent_initial_call=True,
        )
        def apply_parameters(n_clicks, lr, hu, epochs):
            """Apply parameters to backend and update applied store."""
            return self._apply_parameters_handler(n_clicks, lr, hu, epochs)

        # Initialize applied-params-store from backend on load
        @self.app.callback(
            Output("applied-params-store", "data", allow_duplicate=True),
            Input("slow-update-interval", "n_intervals"),
            dash.dependencies.State("applied-params-store", "data"),
            prevent_initial_call=True,
        )
        def init_applied_params(n, current):
            """Initialize applied params from backend if empty."""
            return self._init_applied_params_handler(n, current)

    # Define event handlers for callbacks
    def _toggle_dark_mode_handler(self, n_clicks=None):
        """Toggle dark mode on button click."""
        is_dark = (n_clicks % 2) == 1
        icon = "☀️" if is_dark else "🌙"
        return is_dark, icon

    def _update_theme_state_handler(self, is_dark=None):
        """Update theme state based on dark mode store."""
        return "dark" if is_dark else "light"

    def _update_unified_status_bar_handler(self, n_intervals=None):
        """
        Update unified status bar with all state info from /api/status.

        Returns tuple of 9 elements:
        - status_indicator style (latency color)
        - connection_status children (hidden, for backward compat)
        - latency_display children
        - top_status_display children
        - top_status_display style
        - top_phase_display children
        - top_phase_display style
        - top_epoch_display children
        - top_hidden_units_display children
        """
        error_indicator = {"fontSize": "16px", "color": "#dc3545", "marginRight": "12px"}
        error_style = {"fontWeight": "bold", "color": "#dc3545"}

        try:
            # Measure latency
            start_time = time.time()
            health_response = requests.get(self._api_url("/api/health"), timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            latency_ms = (time.time() - start_time) * 1000

            # Get current status (now includes FSM-based status and phase)
            status_response = requests.get(self._api_url("/api/status"), timeout=DashboardConstants.API_TIMEOUT_SECONDS)

            if health_response.status_code == 200 and status_response.status_code == 200:
                return self._build_unified_status_bar_content(status_response, latency_ms)
            else:
                return (
                    error_indicator,
                    "Backend Unavailable",
                    "Latency: --",
                    "Error",
                    error_style,
                    "Error",
                    error_style,
                    "--",
                    "--",
                )
        except Exception as e:
            self.logger.warning(f"Status bar update failed: {type(e).__name__}: {e}")
            return (
                error_indicator,
                "Connection Error",
                "Latency: --",
                "Error",
                error_style,
                "Error",
                error_style,
                "--",
                "--",
            )

    def _build_unified_status_bar_content(self, status_response, latency_ms):
        """Build unified status bar content from /api/status response."""
        status_data = status_response.json()

        # Determine latency indicator color
        if latency_ms < 100:
            latency_color = "#28a745"  # Green - excellent
        elif latency_ms < 500:
            latency_color = "#ffc107"  # Orange - acceptable
        else:
            latency_color = "#dc3545"  # Red - slow

        latency_indicator_style = {"fontSize": "16px", "color": latency_color, "marginRight": "12px"}
        latency_text = f"Latency: {latency_ms:.0f}ms"

        # Get raw values from backend (now using FSM-based values)
        is_running = status_data.get("is_running", False)
        is_paused = status_data.get("is_paused", False)
        is_completed = status_data.get("completed", False)
        is_failed = status_data.get("failed", False)
        raw_phase = status_data.get("phase", "idle")
        epoch = status_data.get("current_epoch", 0)
        hidden_units = status_data.get("hidden_units", 0)

        # Determine display status (terminal states take priority)
        if is_failed:
            status = "Failed"
        elif is_completed:
            status = "Completed"
        elif is_running and not is_paused:
            status = "Running"
        elif is_paused:
            status = "Paused"
        else:
            status = "Stopped"

        # Map phase to display value
        phase_map = {
            "idle": "Idle",
            "output": "Output Training",
            "candidate": "Candidate Pool",
            "inference": "Inference",
        }
        phase = phase_map.get(raw_phase.lower(), raw_phase.title())

        # Determine status color
        status_colors = {
            "Running": "#28a745",  # Green
            "Paused": "#ffc107",  # Orange
            "Stopped": "#6c757d",  # Gray
            "Completed": "#17a2b8",  # Cyan
            "Failed": "#dc3545",  # Red
        }
        status_color = status_colors.get(status, "#6c757d")

        # Determine phase color
        phase_colors = {
            "Output Training": "#007bff",  # Blue
            "Candidate Pool": "#17a2b8",  # Cyan
            "Inference": "#6f42c1",  # Purple
            "Idle": "#6c757d",  # Gray
        }
        phase_color = phase_colors.get(phase, "#6c757d")

        status_style = {"fontWeight": "bold", "color": status_color}
        phase_style = {"fontWeight": "bold", "color": phase_color}

        # Build connection status text for backward compat (hidden element)
        connection_status = f"Status: {status} | Phase: {phase}"

        return (
            latency_indicator_style,
            connection_status,
            latency_text,
            status,
            status_style,
            phase,
            phase_style,
            str(epoch),
            str(hidden_units),
        )

    def _sync_input_values_from_backend_handler(self, backend_state=None):
        """Sync input values from backend state (only when backend changes)."""
        if backend_state:
            return (
                backend_state.get("learning_rate", 0.01),
                backend_state.get("max_hidden_units", 10),
                backend_state.get("max_epochs", 200),
            )
        return dash.no_update, dash.no_update, dash.no_update

    def _update_network_info_handler(self, n=None):
        """Update network information panel from API."""
        try:
            url = self._api_url("/api/status")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            status = response.json()

            return html.Div(
                [
                    html.P(
                        [
                            html.Strong("Input Nodes: "),
                            str(status.get("input_size", 0)),
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Hidden Units: "),
                            str(status.get("hidden_units", 0)),
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Output Nodes: "),
                            str(status.get("output_size", 0)),
                        ]
                    ),
                    html.Hr(),
                    html.P(
                        [
                            html.Strong("Current Epoch: "),
                            str(status.get("current_epoch", 0)),
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Training Phase: "),
                            status.get("current_phase", "Idle"),
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Network Connected: "),
                            "Yes" if status.get("network_connected") else "No",
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Monitoring: "),
                            ("Active" if status.get("monitoring_active") else "Inactive"),
                        ]
                    ),
                ]
            )
        except Exception as e:
            self.logger.warning(f"Failed to fetch network info: {e}")
            return html.Div(
                [
                    html.P("Unable to fetch network info", style={"color": "orange"}),
                    html.P([html.Small(f"Error: {str(e)}")], style={"color": "gray"}),
                ]
            )

    def _toggle_network_info_handler(self, n=None):
        """Toggle Network Information section collapse state."""
        return n % 2 == 1 if n else True

    def _toggle_network_info_details_handler(self, n=None):
        """Toggle Network Information: Details section collapse state."""
        return n % 2 == 1 if n else False

    def _update_network_info_details_handler(self, n=None):
        """Update detailed network information panel from API."""
        try:
            url = self._api_url("/api/network/stats")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            stats = response.json()

            # Use the metrics_panel helper to create the detailed table
            return self.metrics_panel._create_network_info_table(stats)
        except Exception as e:
            self.logger.warning(f"Failed to fetch network stats: {e}")
            return html.Div(
                [
                    html.P("Unable to fetch detailed network info", style={"color": "orange", "fontSize": "14px"}),
                    html.P([html.Small(f"Error: {str(e)}")], style={"color": "gray", "fontSize": "12px"}),
                ]
            )

    def _update_metrics_store_handler(self, n=None):
        """Fetch metrics history from API and update metrics panel store."""
        try:
            url = self._api_url("/api/metrics/history?limit=100")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            payload = response.json()

            # Normalize to a list for the Store (handle different API envelopes)
            if isinstance(payload, dict):
                if isinstance(payload.get("history"), list):
                    metrics = payload["history"]
                elif isinstance(payload.get("data"), list):
                    metrics = payload["data"]
                else:
                    metrics = []
            elif isinstance(payload, list):
                metrics = payload
            else:
                metrics = []

            self.logger.debug(f"Fetched {len(metrics)} metrics from {url}")
            return metrics
        except Exception as e:
            self.logger.warning(f"Failed to fetch metrics from API: {type(e).__name__}: {e}")
            return []

    def _update_topology_store_handler(self, n=None, active_tab=None):
        """Fetch topology from API and update network visualizer store."""
        # Only update if topology tab is active
        if active_tab != "topology":
            return dash.no_update

        try:
            url = self._api_url("/api/topology")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            topology = response.json()
            self.logger.debug(f"Fetched topology from {url}: {topology.get('total_connections', 0)} connections")
            return topology
        except Exception as e:
            self.logger.warning(f"Failed to fetch topology from API: {type(e).__name__}: {e}")
            return {}

    def _update_dataset_store_handler(self, n=None, active_tab=None):
        """Fetch dataset from API and update dataset plotter store."""
        # Only update if dataset tab is active
        if active_tab != "dataset":
            return dash.no_update

        try:
            url = self._api_url("/api/dataset")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            dataset = response.json()
            self.logger.debug(f"Fetched dataset from {url}: {dataset.get('num_samples', 0)} samples")
            return dataset
        except Exception as e:
            self.logger.warning(f"Failed to fetch dataset from API: {type(e).__name__}: {e}")
            return None

    def _update_boundary_store_handler(self, n=None, active_tab=None):
        """Fetch decision boundary from API and update decision boundary store."""
        # Only update if boundaries tab is active
        if active_tab != "boundaries":
            return dash.no_update

        try:
            url = self._api_url("/api/decision_boundary")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            boundary_data = response.json()
            self.logger.debug(f"Fetched decision boundary from {url}")
            return boundary_data
        except Exception as e:
            self.logger.warning(f"Failed to fetch decision boundary from API: {type(e).__name__}: {e}")
            return None

    def _update_boundary_dataset_store_handler(self, n=None, active_tab=None):
        """Sync dataset data to decision boundary component."""
        # Only update if boundaries tab is active
        if active_tab != "boundaries":
            return dash.no_update

        try:
            url = self._api_url("/api/dataset")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            return response.json()
        except Exception as e:
            self.logger.warning(f"Failed to fetch dataset for boundary from API: {type(e).__name__}: {e}")
            return None

    def _handle_training_buttons_handler(
        self,
        start_clicks=None,
        pause_clicks=None,
        stop_clicks=None,
        resume_clicks=None,
        reset_clicks=None,
        last_click=None,
        button_states=None,
        **kwargs,
    ):
        """Handle training control button clicks with debouncing and optimistic UI."""
        outputs_list = kwargs.get("outputs_list")
        self.logger.debug(f"Handling training control button clicks: {outputs_list}")

        ctx = get_callback_context()
        trigger = kwargs.get("trigger") or ctx.get_triggered_id()
        current_time = time.time()

        # Debouncing: prevent duplicate clicks within 500ms
        if last_click and last_click.get("button") == trigger:
            time_since_last = current_time - last_click.get("timestamp", 0)
            if time_since_last < 0.5:
                self.logger.debug(f"Debounced click on {trigger} ({time_since_last * 1000:.0f}ms)")
                return dash.no_update, dash.no_update

        # Map button to command
        button_map = {
            "start-button": "start",
            "pause-button": "pause",
            "stop-button": "stop",
            "resume-button": "resume",
            "reset-button": "reset",
        }

        command = button_map.get(trigger)
        if not command:
            return dash.no_update, dash.no_update

        # Set button to loading state (optimistic UI) with timestamp
        new_button_states = button_states.copy()
        new_button_states[command] = {"disabled": True, "loading": True, "timestamp": current_time}

        try:
            url = self._api_url(f"/api/train/{command}")
            response = requests.post(url, timeout=2)
            response.raise_for_status()
            success = True
        except Exception as e:
            self.logger.warning(f"Training control failed: {type(e).__name__}: {e}")
            success = False
            # Re-enable button on error
            new_button_states[command] = {"disabled": False, "loading": False, "timestamp": 0}
        return {"last": trigger, "ts": current_time, "success": success}, new_button_states

    def _update_last_click_handler(self, action=None):
        """Update last button click timestamp for debouncing."""
        if action and action.get("last"):
            return {"button": action["last"], "timestamp": action.get("ts", 0)}
        return dash.no_update

    def _update_button_appearance_handler(self, button_states=None):
        """Update button states (disabled/loading) with visual feedback."""

        def get_button_props(cmd, label, icon):
            state = button_states.get(cmd, {"disabled": False, "loading": False, "timestamp": 0})
            disabled = state.get("disabled", False)
            loading = state.get("loading", False)
            text = f"⏳ {label}..." if loading else f"{icon} {label}"
            return disabled, text

        start_disabled, start_text = get_button_props("start", "Start Training", "▶")
        pause_disabled, pause_text = get_button_props("pause", "Pause Training", "⏸")
        stop_disabled, stop_text = get_button_props("stop", "Stop Training", "⏹")
        resume_disabled, resume_text = get_button_props("resume", "Resume Training", "⏯")
        reset_disabled, reset_text = get_button_props("reset", "Reset Training", "↻")

        return (
            start_disabled,
            start_text,
            pause_disabled,
            pause_text,
            stop_disabled,
            stop_text,
            resume_disabled,
            resume_text,
            reset_disabled,
            reset_text,
        )

    def _handle_button_timeout_and_acks_handler(self, action=None, n_intervals=None, button_states=None, **kwargs):
        """Re-enable buttons after timeout (2s) based on their individual timestamps."""
        if not button_states:
            return dash.no_update

        current_time = time.time()
        new_states = {}
        changed = False

        for cmd, state in button_states.items():
            timestamp = state.get("timestamp", 0)
            is_loading = state.get("loading", False)

            if is_loading and timestamp > 0:
                elapsed = current_time - timestamp
                # Reset after 2 seconds timeout
                if elapsed > 2.0:
                    new_states[cmd] = {"disabled": False, "loading": False, "timestamp": 0}
                    changed = True
                    self.logger.debug(f"Button {cmd} reset after {elapsed:.1f}s timeout")
                else:
                    new_states[cmd] = state
            else:
                new_states[cmd] = state

        return new_states if changed else dash.no_update

    def _sync_backend_params_handler(self, n=None):
        """Sync backend parameter state to store."""
        try:
            state_response = requests.get(self._api_url("/api/state"), timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if state_response.status_code == 200:
                state = state_response.json()
                return {
                    "learning_rate": state.get("learning_rate", 0.01),
                    "max_hidden_units": state.get("max_hidden_units", 10),
                    "max_epochs": state.get("max_epochs", 200),
                }
        except Exception as e:
            self.logger.warning(f"Failed to sync backend params: {e}")
        return dash.no_update

    def _handle_parameter_changes_handler(self, learning_rate=None, max_hidden_units=None, **kwargs):
        """Handle parameter input changes - now just logs, actual send is via Apply button."""
        ctx = get_callback_context()
        trigger = kwargs.get("trigger") or ctx.get_triggered_id()

        if trigger == "learning-rate-input":
            self.logger.debug(f"Learning rate changed to {learning_rate} (pending)")
        elif trigger == "max-hidden-units-input":
            self.logger.debug(f"Max hidden units changed to {max_hidden_units} (pending)")

        return dash.no_update

    def _track_param_changes_handler(self, lr, hu, epochs, applied):
        """Enable Apply button when parameters differ from applied values.

        Uses float tolerance for learning_rate comparison to handle floating-point
        precision issues that can occur with step-based input adjustments.

        Args:
            lr: Current learning rate input value
            hu: Current max hidden units input value
            epochs: Current max epochs input value
            applied: Dictionary of currently applied parameter values

        Returns:
            Tuple of (disabled, status) where disabled is True if no changes
        """
        if not applied:
            return True, ""

        def float_equal(a, b, tol=1e-9):
            """Compare floats with tolerance to handle precision issues."""
            if a is None or b is None:
                return a == b
            try:
                return abs(float(a) - float(b)) < tol
            except (TypeError, ValueError):
                return False

        # Use float tolerance for learning_rate comparison
        lr_changed = not float_equal(lr, applied.get("learning_rate"))
        hu_changed = hu != applied.get("max_hidden_units")
        epochs_changed = epochs != applied.get("max_epochs")

        has_changes = lr_changed or hu_changed or epochs_changed

        status = "⚠️ Unsaved changes" if has_changes else ""
        return not has_changes, status

    def _apply_parameters_handler(self, n_clicks, lr, hu, epochs):
        """Apply parameters to backend and update applied store."""
        if not n_clicks:
            return dash.no_update, dash.no_update

        params = {
            "learning_rate": float(lr) if lr is not None else 0.01,
            "max_hidden_units": int(hu) if hu is not None else 10,
            "max_epochs": int(epochs) if epochs is not None else 200,
        }

        try:
            response = requests.post(
                self._api_url("/api/set_params"),
                json=params,
                timeout=2,
            )
            if response.status_code == 200:
                self.logger.info(f"Parameters applied: {params}")
                return params, "✓ Parameters applied"
            self.logger.warning(f"Failed to apply: {response.status_code} {response.text}")
            return dash.no_update, "❌ Failed to apply"
        except Exception as e:
            self.logger.warning(f"Apply failed: {e}")
            return dash.no_update, f"❌ Error: {str(e)[:30]}"

    def _init_applied_params_handler(self, n, current):
        """Initialize applied params from backend if empty."""
        if current:
            return dash.no_update
        try:
            response = requests.get(self._api_url("/api/state"), timeout=2)
            if response.status_code == 200:
                state = response.json()
                return {
                    "learning_rate": state.get("learning_rate", 0.01),
                    "max_hidden_units": state.get("max_hidden_units", 10),
                    "max_epochs": state.get("max_epochs", 200),
                }
        except Exception as e:
            self.logger.warning(f"Failed to initialize applied params: {e}")
        return dash.no_update

    def register_component(self, component: BaseComponent):
        """
        Register a dashboard component.

        Args:
            component: Component to register
        """
        self.components.append(component)
        component.initialize()
        component.register_callbacks(self.app)
        self.logger.info(f"Registered component: {component.get_component_id()}")

    def get_component(self, component_id: str) -> BaseComponent:
        """
        Get a registered component by ID.

        Args:
            component_id: Component identifier

        Returns:
            Component instance or None
        """
        return next(
            (component for component in self.components if component.get_component_id() == component_id),
            None,
        )

    # TODO: move magic numbers into constants
    def start_server(self, host: str = "127.0.0.1", port: int = 8050, debug: bool = True):
        """
        Start the Dash development server.

        Args:
            host: Server host
            port: Server port
            debug: Debug mode flag
        """
        self.logger.info(f"Starting Dash server on {host}:{port}")
        self.app.run_server(host=host, port=port, debug=debug)

    def get_app(self):
        """
        Get Dash app instance.

        Returns:
            Dash app
        """
        return self.app
