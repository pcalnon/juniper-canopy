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

import dash
import dash_bootstrap_components as dbc
import requests
from dash import dcc, html
from dash.dependencies import Input, Output, State

from canopy_constants import DashboardConstants, TrainingConstants
from settings import get_settings

from .base_component import BaseComponent
from .callback_context import get_callback_context
from .components.about_panel import AboutPanel
from .components.candidate_metrics_panel import CandidateMetricsPanel
from .components.cassandra_panel import CassandraPanel
from .components.connection_indicator import CONNECTION_INDICATOR_JS, connection_indicator_layout
from .components.dataset_plotter import DatasetPlotter
from .components.decision_boundary import DecisionBoundary
from .components.hdf5_snapshots_panel import HDF5SnapshotsPanel
from .components.metrics_panel import MetricsPanel
from .components.network_editor_panel import NetworkEditorPanel
from .components.network_evolution import MAX_SNAPSHOTS as _EVOLUTION_MAX_SNAPSHOTS
from .components.network_evolution import NetworkEvolution
from .components.network_visualizer import NetworkVisualizer
from .components.parameters_panel import ParametersPanel
from .components.redis_panel import RedisPanel
from .components.replay_player_panel import ReplayPlayerPanel
from .components.tutorial_panel import TutorialPanel
from .components.worker_panel import WorkerPanel
from .tooltips import CONTROL_TOOLTIPS
from .walkthrough_steps import get_walkthrough_steps as _walkthrough_steps  # CAN-019

# from urllib.parse import urljoin


# from flask import request


# ──────────────────────────────────────────────────────────────────────
# Phase D §S10.3 (P12b) — training button clientside callback
# ──────────────────────────────────────────────────────────────────────
# Registered in place of the server-side ``handle_training_buttons``
# when ``settings.enable_ws_control_buttons`` is True. Routes button
# clicks through ``window.cascorControlWS.send(...)`` with automatic
# REST fallback if the WS is unavailable, the send() promise rejects,
# or the server returns a timeout/error envelope.
#
# Contract — inputs and outputs mirror the server-side callback, so
# the rest of the dashboard (optimistic button-states store, debounce
# store, timeout sweeper) keeps working unchanged. The JS is otherwise
# a straight port of ``_handle_training_buttons_handler``:
#
#   * Debouncing: 500ms same-button guard via the last-button-click store.
#   * Trigger mapping: ``start-button`` → "start", etc.
#   * Optimistic UI: set ``button-states[command] = {disabled, loading,
#     timestamp}`` synchronously so the button flips to "pending".
#   * Routing decision: if ``window.cascorControlWS`` is open, call
#     ``send({command, command_id})`` and handle the promise
#     asynchronously. Success → keep optimistic state (the existing
#     timeout sweeper + state-broadcast cleans up). Rejection → REST
#     fallback via ``fetch('/api/train/<command>', {method:'POST'})``.
#   * Disconnected path: straight REST via fetch, no WS attempt.
#
# The synchronous return value is the same dict/state tuple the
# server-side handler produced, so existing Dash outputs
# (``training-control-action``, ``button-states``) keep their shape.
PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS = r"""
function(start_clicks, pause_clicks, stop_clicks, resume_clicks, reset_clicks, last_click, button_states) {
    var dc = window.dash_clientside || {};
    var no_update = (dc.no_update !== undefined) ? dc.no_update : null;
    var ctx = dc.callback_context || {};
    var triggered = ctx.triggered || [];
    if (!triggered.length || triggered[0].value === null || triggered[0].value === undefined) {
        return [no_update, no_update];
    }

    var triggerId = triggered[0].prop_id.split('.')[0];
    var buttonMap = {
        'start-button': 'start',
        'pause-button': 'pause',
        'stop-button': 'stop',
        'resume-button': 'resume',
        'reset-button': 'reset'
    };
    var command = buttonMap[triggerId];
    if (!command) {
        return [no_update, no_update];
    }

    var now = Date.now() / 1000.0;

    // Debounce: ignore same-button clicks within 500ms.
    if (last_click && last_click.button === triggerId) {
        var sinceLast = now - (last_click.timestamp || 0);
        if (sinceLast < 0.5) {
            return [no_update, no_update];
        }
    }

    // Optimistic UI: flip the clicked button to loading immediately.
    var newStates = Object.assign({}, button_states || {});
    newStates[command] = { disabled: true, loading: true, timestamp: now };

    function restFallback(reason) {
        if (reason) {
            console.warn('[Phase D] REST fallback (' + command + '):', reason);
        }
        try {
            fetch('/api/train/' + command, { method: 'POST', credentials: 'same-origin' })
                .then(function(resp) {
                    if (!resp.ok) {
                        console.warn('[Phase D] REST /api/train/' + command + ' returned ' + resp.status);
                    }
                })
                .catch(function(err) {
                    console.error('[Phase D] REST /api/train/' + command + ' failed:', err);
                });
        } catch (err) {
            console.error('[Phase D] REST fallback threw for ' + command + ':', err);
        }
    }

    var ws = window.cascorControlWS;
    var wsReady = !!(ws && ws.connected && ws.ws && ws.ws.readyState === 1 /* OPEN */);

    if (wsReady && typeof ws.send === 'function') {
        var commandId;
        try {
            commandId = (ws.constructor && typeof ws.constructor._uuidv4 === 'function')
                ? ws.constructor._uuidv4()
                : ('btn-' + now.toFixed(3) + '-' + Math.floor(Math.random() * 1e9).toString(16));
        } catch (e) {
            commandId = 'btn-' + now.toFixed(3) + '-' + Math.floor(Math.random() * 1e9).toString(16);
        }
        try {
            var sendPromise = ws.send({ command: command, command_id: commandId });
            if (sendPromise && typeof sendPromise.then === 'function') {
                sendPromise
                    .then(function(data) {
                        console.log('[Phase D] WS command success:', command, data && data.command_id);
                    })
                    .catch(function(err) {
                        restFallback('WS rejected: ' + (err && err.message));
                    });
            } else {
                // send() returned something non-thenable — treat as failure.
                restFallback('send() returned non-promise value');
            }
        } catch (err) {
            restFallback('send() threw: ' + err);
        }
        return [
            { last: triggerId, ts: now, success: true, transport: 'ws', command_id: commandId },
            newStates
        ];
    }

    // Fast path: WS unavailable — go straight to REST.
    restFallback(wsReady ? null : 'WS not connected');
    return [
        { last: triggerId, ts: now, success: true, transport: 'rest' },
        newStates
    ];
}
"""


# ── Sidebar Contextual Visibility Configuration ──
# Defines which sidebar sections are visible for each tab.
# Sections not listed (or with False) are hidden via display:none.
# Training Controls card is always visible and not included here.
SIDEBAR_SECTION_IDS = [
    "sidebar-meta-params-card",
    "sidebar-nn-section",
    "sidebar-nn-top-params",
    "sidebar-nn-growth-triggers",
    "sidebar-nn-multi-node-layers",
    "sidebar-nn-spiral-dataset",
    "sidebar-nn-cn-divider",
    "sidebar-cn-section",
    "sidebar-cn-pool-params",
    "sidebar-cn-pool-training",
    "sidebar-cn-multi-candidate",
    "sidebar-apply-section",
    "sidebar-params-divider",
    "sidebar-network-info-section",
]

TAB_SIDEBAR_CONFIG = {
    "metrics": {
        "sidebar-meta-params-card": True,
        "sidebar-nn-section": True,
        "sidebar-nn-top-params": True,
        "sidebar-nn-growth-triggers": True,
        "sidebar-nn-multi-node-layers": False,
        "sidebar-nn-spiral-dataset": False,
        "sidebar-nn-cn-divider": False,
        "sidebar-cn-section": False,
        "sidebar-cn-pool-params": False,
        "sidebar-cn-pool-training": False,
        "sidebar-cn-multi-candidate": False,
        "sidebar-apply-section": True,
        "sidebar-params-divider": False,
        "sidebar-network-info-section": True,
    },
    "candidates": {
        "sidebar-meta-params-card": True,
        "sidebar-nn-section": False,
        "sidebar-nn-top-params": False,
        "sidebar-nn-growth-triggers": False,
        "sidebar-nn-multi-node-layers": True,
        "sidebar-nn-spiral-dataset": False,
        "sidebar-nn-cn-divider": False,
        "sidebar-cn-section": True,
        "sidebar-cn-pool-params": True,
        "sidebar-cn-pool-training": True,
        "sidebar-cn-multi-candidate": False,
        "sidebar-apply-section": True,
        "sidebar-params-divider": False,
        "sidebar-network-info-section": False,
    },
    "topology": {
        "sidebar-meta-params-card": True,
        "sidebar-nn-section": True,
        "sidebar-nn-top-params": True,
        "sidebar-nn-growth-triggers": False,
        "sidebar-nn-multi-node-layers": True,
        "sidebar-nn-spiral-dataset": False,
        "sidebar-nn-cn-divider": False,
        "sidebar-cn-section": False,
        "sidebar-cn-pool-params": False,
        "sidebar-cn-pool-training": False,
        "sidebar-cn-multi-candidate": False,
        "sidebar-apply-section": True,
        "sidebar-params-divider": False,
        "sidebar-network-info-section": True,
    },
    "boundaries": {
        "sidebar-meta-params-card": True,
        "sidebar-nn-section": False,
        "sidebar-nn-top-params": False,
        "sidebar-nn-growth-triggers": False,
        "sidebar-nn-multi-node-layers": False,
        "sidebar-nn-spiral-dataset": False,
        "sidebar-nn-cn-divider": False,
        "sidebar-cn-section": True,
        "sidebar-cn-pool-params": True,
        "sidebar-cn-pool-training": False,
        "sidebar-cn-multi-candidate": False,
        "sidebar-apply-section": True,
        "sidebar-params-divider": False,
        "sidebar-network-info-section": True,
    },
    "dataset": {
        "sidebar-meta-params-card": True,
        "sidebar-nn-section": True,
        "sidebar-nn-top-params": False,
        "sidebar-nn-growth-triggers": False,
        "sidebar-nn-multi-node-layers": False,
        "sidebar-nn-spiral-dataset": True,
        "sidebar-nn-cn-divider": False,
        "sidebar-cn-section": False,
        "sidebar-cn-pool-params": False,
        "sidebar-cn-pool-training": False,
        "sidebar-cn-multi-candidate": False,
        "sidebar-apply-section": True,
        "sidebar-params-divider": False,
        "sidebar-network-info-section": True,
    },
    # Tabs with only Training Controls visible:
    "snapshots": {},
    "redis": {},
    "cassandra": {},
    "workers": {},
    "about": {},
    "parameters": {},
    "tutorial": {},
}

# Dynamic card header text per tab
TAB_HEADER_MAP = {
    "metrics": "Network Parameters",
    "topology": "Network Parameters",
    "candidates": "Candidate Parameters",
    "boundaries": "Candidate Parameters",
    "dataset": "Dataset Parameters",
}


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

        # Initialize settings for training defaults
        self._settings = get_settings()
        self._api_base_url = f"http://127.0.0.1:{self._settings.server.port}"

        # Base URL for API calls (avoids dependency on Flask request context)
        self._api_base_url = f"http://127.0.0.1:{self._settings.server.port}"

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
        defaults = self._settings.get_training_defaults()

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

        self.candidate_metrics_panel = CandidateMetricsPanel(self.config.get("candidate_metrics_panel", {}), component_id="candidate-metrics-panel")

        self.network_visualizer = NetworkVisualizer(self.config.get("network_visualizer", {}), component_id="network-visualizer")

        self.dataset_plotter = DatasetPlotter(self.config.get("dataset_plotter", {}), component_id="dataset-plotter")

        self.decision_boundary = DecisionBoundary(self.config.get("decision_boundary", {}), component_id="decision-boundary")

        self.about_panel = AboutPanel(self.config.get("about_panel", {}), component_id="about-panel")

        self.hdf5_snapshots_panel = HDF5SnapshotsPanel(self.config.get("hdf5_snapshots_panel", {}), component_id="hdf5-snapshots-panel")

        # Phase 6E Sprint B B-6 (CAN-015f): replay player UI for snapshot
        # playback sessions. Bound to the ``replay-player-session`` Store
        # which is populated by the snapshots panel after a successful
        # POST /api/v1/snapshots/{id}/replay.
        self.replay_player_panel = ReplayPlayerPanel(
            self.config.get("replay_player_panel", {}),
            component_id="replay-player-panel",
        )

        # Phase 6E CAN-015h (h-5): network editor — surgical
        # mutations on a restored snapshot. Idle when the cascor
        # FSM is not Investigating; active state exposes append /
        # remove / patch forms that talk to the canopy proxies
        # under /api/v1/network/.
        self.network_editor_panel = NetworkEditorPanel(
            self.config.get("network_editor_panel", {}),
            component_id="network-editor-panel",
        )

        # P3-6: Redis Monitoring Panel
        self.redis_panel = RedisPanel(self.config.get("redis_panel", {}), component_id="redis-panel")

        # P3-7: Cassandra Monitoring Panel
        self.cassandra_panel = CassandraPanel(self.config.get("cassandra_panel", {}), component_id="cassandra-panel")

        # Parameters Panel
        self.parameters_panel = ParametersPanel(self.config.get("parameters_panel", {}), component_id="parameters-panel")
        self.tutorial_panel = TutorialPanel(self.config.get("tutorial_panel", {}), component_id="tutorial-panel")
        # Network Evolution: small-multiples cascade-growth timeline.
        self.network_evolution = NetworkEvolution(self.config.get("network_evolution", {}), component_id="network-evolution")

        # Remote Worker Monitoring Panel
        self.worker_panel = WorkerPanel(self.config.get("worker_panel", {}), component_id="worker-panel")

        # Register components
        self.register_component(self.metrics_panel)
        self.register_component(self.candidate_metrics_panel)
        self.register_component(self.network_visualizer)
        self.register_component(self.dataset_plotter)
        self.register_component(self.decision_boundary)
        self.register_component(self.about_panel)
        self.register_component(self.hdf5_snapshots_panel)
        self.register_component(self.replay_player_panel)
        self.register_component(self.network_editor_panel)
        self.register_component(self.redis_panel)
        self.register_component(self.cassandra_panel)
        self.register_component(self.parameters_panel)
        self.register_component(self.tutorial_panel)
        self.register_component(self.network_evolution)
        self.register_component(self.worker_panel)

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
                                    className="text-center text-body",
                                    style={"marginTop": "20px"},
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
                                                        # Iteration (Hidden Units) display
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Iteration: ",
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
                                                        # Phase B: WebSocket connection indicator badge
                                                        connection_indicator_layout(),
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
                                            ]
                                        ),
                                    ],
                                    className="mb-3",
                                ),
                                dbc.Card(
                                    [
                                        dbc.CardHeader(html.H5("Meta Parameters", id="sidebar-meta-params-header")),
                                        dbc.CardBody(
                                            [
                                                # ── Neural Network Subsection ──
                                                html.Div(
                                                    [
                                                        html.H6(
                                                            [
                                                                html.Span("▼", id="nn-subsection-icon", className="collapse-icon"),
                                                                "Neural Network",
                                                            ],
                                                            id="nn-subsection-header",
                                                            className="collapsible-header",
                                                        ),
                                                        dbc.Collapse(
                                                            html.Div(
                                                                [
                                                                    # ── Top-level NN params ──
                                                                    html.Div(
                                                                        [
                                                                            html.P("Maximum Iterations:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="nn-max-iterations-input",
                                                                                type="number",
                                                                                value=self.training_defaults.get("max_iterations", TrainingConstants.DEFAULT_MAX_GROWTH_ITERATIONS),
                                                                                step=100,
                                                                                min=TrainingConstants.MIN_MAX_GROWTH_ITERATIONS,
                                                                                max=TrainingConstants.MAX_MAX_GROWTH_ITERATIONS,
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                            html.P("Maximum Total Epochs:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="nn-max-total-epochs-input",
                                                                                type="number",
                                                                                value=self.training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS),
                                                                                step=1000,
                                                                                min=self._settings.get_training_param_config("epochs")["min"],
                                                                                max=self._settings.get_training_param_config("epochs")["max"],
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                            html.P("Output Epochs (per pass):", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="nn-output-epochs-input",
                                                                                type="number",
                                                                                value=self.training_defaults.get("output_epochs", TrainingConstants.DEFAULT_OUTPUT_EPOCHS),
                                                                                step=1,
                                                                                min=TrainingConstants.MIN_OUTPUT_EPOCHS,
                                                                                max=TrainingConstants.MAX_OUTPUT_EPOCHS,
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                            html.P("Output Weight Init:", className="mb-1 fw-bold"),
                                                                            dcc.Dropdown(
                                                                                id="nn-init-output-weights-dropdown",
                                                                                options=[{"label": v.title(), "value": v} for v in TrainingConstants.INIT_OUTPUT_WEIGHTS_OPTIONS],
                                                                                value=self.training_defaults.get("init_output_weights", TrainingConstants.DEFAULT_INIT_OUTPUT_WEIGHTS),
                                                                                clearable=False,
                                                                                className="mb-2",
                                                                            ),
                                                                            html.P("Output Optimizer:", className="mb-1 fw-bold"),
                                                                            dcc.Dropdown(
                                                                                id="nn-optimizer-type-dropdown",
                                                                                options=[{"label": v, "value": v} for v in TrainingConstants.OPTIMIZER_TYPE_OPTIONS],
                                                                                value=self.training_defaults.get("optimizer_type", TrainingConstants.DEFAULT_OPTIMIZER_TYPE),
                                                                                clearable=False,
                                                                                className="mb-2",
                                                                            ),
                                                                            html.P("Activation Function:", className="mb-1 fw-bold"),
                                                                            dcc.Dropdown(
                                                                                id="nn-activation-function-dropdown",
                                                                                options=[{"label": v, "value": v} for v in TrainingConstants.ACTIVATION_FUNCTION_OPTIONS],
                                                                                value=self.training_defaults.get("activation_function_name", TrainingConstants.DEFAULT_ACTIVATION_FUNCTION),
                                                                                clearable=False,
                                                                                className="mb-2",
                                                                            ),
                                                                            html.P("Learning Rate:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="nn-learning-rate-input",
                                                                                type="number",
                                                                                value=self.training_defaults.get("learning_rate", TrainingConstants.DEFAULT_LEARNING_RATE),
                                                                                step=0.001,
                                                                                min=self._settings.get_training_param_config("learning_rate")["min"],
                                                                                max=self._settings.get_training_param_config("learning_rate")["max"],
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                            html.P("Maximum Hidden Units:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="nn-max-hidden-units-input",
                                                                                type="number",
                                                                                value=self.training_defaults.get("hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS),
                                                                                step=1,
                                                                                min=self._settings.get_training_param_config("hidden_units")["min"],
                                                                                max=self._settings.get_training_param_config("hidden_units")["max"],
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                        ],
                                                                        id="sidebar-nn-top-params",
                                                                    ),
                                                                    # ── Multi-Node Layers ──
                                                                    html.Div(
                                                                        [
                                                                            html.H6(
                                                                                [
                                                                                    html.Span("▼", id="ctx-multi-node-icon", className="collapse-icon"),
                                                                                    "Multi-Node Layers",
                                                                                ],
                                                                                id="ctx-multi-node-header",
                                                                                className="collapsible-header",
                                                                            ),
                                                                            dbc.Collapse(
                                                                                html.Div(
                                                                                    [
                                                                                        dcc.Checklist(
                                                                                            id="nn-multi-node-layers-checkbox",
                                                                                            options=[{"label": " Enable multi-node layers", "value": "enabled"}],
                                                                                            value=[],
                                                                                            className="mb-2",
                                                                                        ),
                                                                                    ]
                                                                                ),
                                                                                id="ctx-multi-node-collapse",
                                                                                is_open=True,
                                                                            ),
                                                                        ],
                                                                        id="sidebar-nn-multi-node-layers",
                                                                    ),
                                                                    # ── Network Growth Triggers ──
                                                                    html.Div(
                                                                        [
                                                                            html.Hr(),
                                                                            html.H6(
                                                                                [
                                                                                    html.Span("▼", id="ctx-growth-triggers-icon", className="collapse-icon"),
                                                                                    "Network Growth Triggers",
                                                                                ],
                                                                                id="ctx-growth-triggers-header",
                                                                                className="collapsible-header",
                                                                            ),
                                                                            dbc.Collapse(
                                                                                html.Div(
                                                                                    [
                                                                                        dbc.RadioItems(
                                                                                            id="nn-growth-trigger-radio",
                                                                                            options=[
                                                                                                {"label": "Preset Epochs", "value": "preset_epochs"},
                                                                                                {"label": "Convergence Detection", "value": "convergence"},
                                                                                            ],
                                                                                            value="convergence",
                                                                                            className="mb-2",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Number of Epochs:", className="mb-1 ms-4"),
                                                                                                dbc.Input(
                                                                                                    id="nn-growth-preset-epochs-input",
                                                                                                    type="number",
                                                                                                    value=self.training_defaults.get("preset_epochs", TrainingConstants.DEFAULT_PRESET_EPOCHS),
                                                                                                    step=10,
                                                                                                    min=TrainingConstants.MIN_PRESET_EPOCHS,
                                                                                                    max=TrainingConstants.MAX_PRESET_EPOCHS,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=True,
                                                                                                    disabled=True,
                                                                                                    style={"width": "calc(100% - 1.5rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="nn-growth-preset-epochs-container",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Convergence Threshold:", className="mb-1 ms-4"),
                                                                                                dbc.Input(
                                                                                                    id="nn-growth-convergence-threshold-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD,
                                                                                                    step=0.0001,
                                                                                                    min=TrainingConstants.MIN_CONVERGENCE_THRESHOLD,
                                                                                                    max=TrainingConstants.MAX_CONVERGENCE_THRESHOLD,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=True,
                                                                                                    disabled=False,
                                                                                                    style={"width": "calc(100% - 1.5rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="nn-growth-convergence-threshold-container",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Patience (epochs):", className="mb-1 ms-4"),
                                                                                                dbc.Input(
                                                                                                    id="nn-patience-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_PATIENCE,
                                                                                                    step=1,
                                                                                                    min=TrainingConstants.MIN_PATIENCE,
                                                                                                    max=TrainingConstants.MAX_PATIENCE,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=True,
                                                                                                    disabled=False,
                                                                                                    style={"width": "calc(100% - 1.5rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="nn-patience-container",
                                                                                        ),
                                                                                    ]
                                                                                ),
                                                                                id="ctx-growth-triggers-collapse",
                                                                                is_open=True,
                                                                            ),
                                                                        ],
                                                                        id="sidebar-nn-growth-triggers",
                                                                    ),
                                                                    # ── Spiral Dataset ──
                                                                    html.Div(
                                                                        [
                                                                            html.Hr(),
                                                                            html.H6(
                                                                                [
                                                                                    html.Span("▼", id="ctx-spiral-dataset-icon", className="collapse-icon"),
                                                                                    "Current Dataset",
                                                                                ],
                                                                                id="ctx-spiral-dataset-header",
                                                                                className="collapsible-header",
                                                                            ),
                                                                            dbc.Collapse(
                                                                                html.Div(
                                                                                    [
                                                                                        html.P("Spiral:", className="mb-1 fw-bold mt-1"),
                                                                                        html.P("Rotations:", className="mb-1 ms-3"),
                                                                                        dbc.Input(
                                                                                            id="nn-spiral-rotations-input",
                                                                                            type="number",
                                                                                            value=TrainingConstants.DEFAULT_SPIRAL_ROTATIONS,
                                                                                            step=0.5,
                                                                                            min=TrainingConstants.MIN_SPIRAL_ROTATIONS,
                                                                                            max=TrainingConstants.MAX_SPIRAL_ROTATIONS,
                                                                                            className="mb-2 ms-3",
                                                                                            debounce=True,
                                                                                            style={"width": "calc(100% - 1rem)"},
                                                                                        ),
                                                                                        html.P("Number:", className="mb-1 ms-3"),
                                                                                        dbc.Input(
                                                                                            id="nn-spiral-number-input",
                                                                                            type="number",
                                                                                            value=TrainingConstants.DEFAULT_SPIRAL_NUMBER,
                                                                                            step=1,
                                                                                            min=TrainingConstants.MIN_SPIRAL_NUMBER,
                                                                                            max=TrainingConstants.MAX_SPIRAL_NUMBER,
                                                                                            className="mb-2 ms-3",
                                                                                            debounce=True,
                                                                                            style={"width": "calc(100% - 1rem)"},
                                                                                        ),
                                                                                        html.P("Dataset:", className="mb-1 fw-bold mt-2"),
                                                                                        html.P("Elements:", className="mb-1 ms-3"),
                                                                                        dbc.Input(
                                                                                            id="nn-dataset-elements-input",
                                                                                            type="number",
                                                                                            value=TrainingConstants.DEFAULT_DATASET_ELEMENTS,
                                                                                            step=100,
                                                                                            min=TrainingConstants.MIN_DATASET_ELEMENTS,
                                                                                            max=TrainingConstants.MAX_DATASET_ELEMENTS,
                                                                                            className="mb-2 ms-3",
                                                                                            debounce=True,
                                                                                            style={"width": "calc(100% - 1rem)"},
                                                                                        ),
                                                                                        html.P("Noise:", className="mb-1 ms-3"),
                                                                                        dbc.Input(
                                                                                            id="nn-dataset-noise-input",
                                                                                            type="number",
                                                                                            value=TrainingConstants.DEFAULT_DATASET_NOISE,
                                                                                            step=0.05,
                                                                                            min=TrainingConstants.MIN_DATASET_NOISE,
                                                                                            max=TrainingConstants.MAX_DATASET_NOISE,
                                                                                            className="mb-2 ms-3",
                                                                                            debounce=True,
                                                                                            style={"width": "calc(100% - 1rem)"},
                                                                                        ),
                                                                                    ]
                                                                                ),
                                                                                id="ctx-spiral-dataset-collapse",
                                                                                is_open=True,
                                                                            ),
                                                                        ],
                                                                        id="sidebar-nn-spiral-dataset",
                                                                    ),
                                                                ]
                                                            ),
                                                            id="nn-subsection-collapse",
                                                            is_open=True,
                                                        ),
                                                    ],
                                                    id="sidebar-nn-section",
                                                ),
                                                html.Hr(id="sidebar-nn-cn-divider"),
                                                # ── Candidate Nodes Subsection ──
                                                html.Div(
                                                    [
                                                        html.H6(
                                                            [
                                                                html.Span("▶", id="cn-subsection-icon", className="collapse-icon"),
                                                                "Candidate Nodes",
                                                            ],
                                                            id="cn-subsection-header",
                                                            className="collapsible-header",
                                                        ),
                                                        dbc.Collapse(
                                                            html.Div(
                                                                [
                                                                    # ── Candidate Pool Meta Params ──
                                                                    html.Div(
                                                                        [
                                                                            html.P("Candidate Pool Size:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="cn-pool-size-input",
                                                                                type="number",
                                                                                value=TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE,
                                                                                step=1,
                                                                                min=TrainingConstants.MIN_CANDIDATE_POOL_SIZE,
                                                                                max=TrainingConstants.MAX_CANDIDATE_POOL_SIZE,
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                            html.P("Correlation Threshold:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="cn-correlation-threshold-input",
                                                                                type="number",
                                                                                value=TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD,
                                                                                step=0.0001,
                                                                                min=TrainingConstants.MIN_CANDIDATE_CORRELATION_THRESHOLD,
                                                                                max=TrainingConstants.MAX_CANDIDATE_CORRELATION_THRESHOLD,
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                            html.P("Selected Candidates:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="cn-selected-candidates-input",
                                                                                type="number",
                                                                                value=TrainingConstants.DEFAULT_SELECTED_CANDIDATES,
                                                                                step=1,
                                                                                min=TrainingConstants.MIN_SELECTED_CANDIDATES,
                                                                                max=TrainingConstants.MAX_SELECTED_CANDIDATES,
                                                                                className="mb-2",
                                                                                debounce=True,
                                                                            ),
                                                                        ],
                                                                        id="sidebar-cn-pool-params",
                                                                    ),
                                                                    # ── Pool Training Complete ──
                                                                    html.Div(
                                                                        [
                                                                            html.Hr(className="my-2"),
                                                                            html.H6(
                                                                                [
                                                                                    html.Span("▼", id="ctx-pool-training-icon", className="collapse-icon"),
                                                                                    "Pool Training Complete",
                                                                                ],
                                                                                id="ctx-pool-training-header",
                                                                                className="collapsible-header",
                                                                            ),
                                                                            dbc.Collapse(
                                                                                html.Div(
                                                                                    [
                                                                                        dbc.RadioItems(
                                                                                            id="cn-training-complete-radio",
                                                                                            options=[
                                                                                                {"label": "Preset Epochs", "value": "preset_epochs"},
                                                                                                {"label": "Convergence Detection", "value": "convergence"},
                                                                                            ],
                                                                                            value="preset_epochs",
                                                                                            className="mb-2",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Training Iterations:", className="mb-1 ms-4"),
                                                                                                dbc.Input(
                                                                                                    id="cn-training-iterations-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_CANDIDATE_TRAINING_ITERATIONS,
                                                                                                    step=10,
                                                                                                    min=TrainingConstants.MIN_CANDIDATE_TRAINING_ITERATIONS,
                                                                                                    max=TrainingConstants.MAX_CANDIDATE_TRAINING_ITERATIONS,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=True,
                                                                                                    disabled=False,
                                                                                                    style={"width": "calc(100% - 1.5rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="cn-training-iterations-container",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Convergence Threshold:", className="mb-1 ms-4"),
                                                                                                dbc.Input(
                                                                                                    id="cn-training-convergence-threshold-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD,
                                                                                                    step=0.00001,
                                                                                                    min=TrainingConstants.MIN_CANDIDATE_CONVERGENCE_THRESHOLD,
                                                                                                    max=TrainingConstants.MAX_CANDIDATE_CONVERGENCE_THRESHOLD,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=True,
                                                                                                    disabled=True,
                                                                                                    style={"width": "calc(100% - 1.5rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="cn-training-convergence-threshold-container",
                                                                                        ),
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Patience (epochs):", className="mb-1 ms-4"),
                                                                                                dbc.Input(
                                                                                                    id="cn-patience-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_CN_PATIENCE,
                                                                                                    step=1,
                                                                                                    min=TrainingConstants.MIN_CN_PATIENCE,
                                                                                                    max=TrainingConstants.MAX_CN_PATIENCE,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=True,
                                                                                                    disabled=False,
                                                                                                    style={"width": "calc(100% - 1.5rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="cn-patience-container",
                                                                                        ),
                                                                                    ]
                                                                                ),
                                                                                id="ctx-pool-training-collapse",
                                                                                is_open=True,
                                                                            ),
                                                                        ],
                                                                        id="sidebar-cn-pool-training",
                                                                    ),
                                                                    # ── Multi Candidate Selection ──
                                                                    html.Div(
                                                                        [
                                                                            html.Hr(className="my-2"),
                                                                            html.P("Multi Candidate Selection:", className="mb-1 fw-bold"),
                                                                            dcc.Checklist(
                                                                                id="cn-multi-candidate-checkbox",
                                                                                options=[{"label": " Enable multi-candidate selection", "value": "enabled"}],
                                                                                value=[],
                                                                                className="mb-2",
                                                                            ),
                                                                            html.Div(
                                                                                [
                                                                                    dbc.RadioItems(
                                                                                        id="cn-candidate-selection-radio",
                                                                                        options=[
                                                                                            {"label": "Add Top Tier Candidates", "value": "top_tier"},
                                                                                            {"label": "Add Random Candidates", "value": "random"},
                                                                                        ],
                                                                                        value=None,
                                                                                        className="mb-2",
                                                                                        style={"opacity": "0.5"},
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.P("Number of Top Candidates:", className="mb-1 ms-4"),
                                                                                            dbc.Input(
                                                                                                id="cn-top-candidates-input",
                                                                                                type="number",
                                                                                                value=TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT,
                                                                                                step=1,
                                                                                                min=TrainingConstants.MIN_TOP_CANDIDATES_COUNT,
                                                                                                max=TrainingConstants.MAX_TOP_CANDIDATES_COUNT,
                                                                                                className="mb-2 ms-4",
                                                                                                debounce=True,
                                                                                                disabled=True,
                                                                                                style={"width": "calc(100% - 1.5rem)"},
                                                                                            ),
                                                                                        ],
                                                                                        id="cn-top-candidates-container",
                                                                                    ),
                                                                                    html.Div(
                                                                                        [
                                                                                            html.P("Number of Random Candidates:", className="mb-1 ms-4"),
                                                                                            dbc.Input(
                                                                                                id="cn-random-candidates-input",
                                                                                                type="number",
                                                                                                value=TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT,
                                                                                                step=1,
                                                                                                min=TrainingConstants.MIN_RANDOM_CANDIDATES_COUNT,
                                                                                                max=TrainingConstants.MAX_RANDOM_CANDIDATES_COUNT,
                                                                                                className="mb-2 ms-4",
                                                                                                debounce=True,
                                                                                                disabled=True,
                                                                                                style={"width": "calc(100% - 1.5rem)"},
                                                                                            ),
                                                                                        ],
                                                                                        id="cn-random-candidates-container",
                                                                                    ),
                                                                                ],
                                                                                id="cn-multi-candidate-content",
                                                                            ),
                                                                        ],
                                                                        id="sidebar-cn-multi-candidate",
                                                                    ),
                                                                ]
                                                            ),
                                                            id="cn-subsection-collapse",
                                                            is_open=False,
                                                        ),
                                                    ],
                                                    id="sidebar-cn-section",
                                                ),
                                                html.Hr(id="sidebar-params-divider"),
                                                # ── Shared Apply Button ──
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
                                                    ],
                                                    id="sidebar-apply-section",
                                                ),
                                            ]
                                        ),
                                    ],
                                    className="mb-3",
                                    id="sidebar-meta-params-card",
                                ),
                                html.Div(
                                    [
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
                                                                [
                                                                    html.Span("▶", id="network-info-details-icon", className="collapse-icon"),
                                                                    "Network Information: Details",
                                                                ],
                                                                id="network-info-details-header",
                                                                className="collapsible-header",
                                                                style={"marginTop": "10px"},
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
                                    id="sidebar-network-info-section",
                                ),
                                # CAN-005: Pinned Parameters mirror.
                                # Hidden when nothing is pinned; otherwise
                                # shows name + current value rows for every
                                # parameter the user pinned via the
                                # Parameters tab. Read-only — editing still
                                # happens through the dedicated sidebar
                                # sections to avoid duplicate-id collisions.
                                html.Div(
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(html.H5("Pinned Parameters", className="mb-0")),
                                            dbc.CardBody(html.Div(id="sidebar-pinned-list")),
                                        ],
                                        className="mb-3",
                                    ),
                                    id="sidebar-pinned-card",
                                    style={"display": "none"},
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
                                            self.candidate_metrics_panel.get_layout(),
                                            label="Candidate Metrics",
                                            tab_id="candidates",
                                        ),
                                        dbc.Tab(
                                            self.network_visualizer.get_layout(),
                                            label="Network Topology",
                                            tab_id="topology",
                                        ),
                                        dbc.Tab(
                                            self.network_evolution.get_layout(),
                                            label="Network Evolution",
                                            tab_id="evolution",
                                        ),
                                        dbc.Tab(
                                            self.decision_boundary.get_layout(),
                                            label="Decision Boundary",
                                            tab_id="boundaries",
                                        ),
                                        dbc.Tab(
                                            self.dataset_plotter.get_layout(),
                                            label="Dataset View",
                                            tab_id="dataset",
                                        ),
                                        dbc.Tab(
                                            self.worker_panel.get_layout(),
                                            label="Workers",
                                            tab_id="workers",
                                        ),
                                        dbc.Tab(
                                            self.parameters_panel.get_layout(),
                                            label="Parameters",
                                            tab_id="parameters",
                                        ),
                                        dbc.Tab(
                                            self.hdf5_snapshots_panel.get_layout(),
                                            label="Snapshots",
                                            tab_id="snapshots",
                                        ),
                                        dbc.Tab(
                                            self.replay_player_panel.get_layout(),
                                            label="Replay",
                                            tab_id="replay",
                                        ),
                                        dbc.Tab(
                                            self.network_editor_panel.get_layout(),
                                            label="Network Editor",
                                            tab_id="network-editor",
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
                                            self.tutorial_panel.get_layout(),
                                            label="Tutorial",
                                            tab_id="tutorial",
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
                # CAN-005: pinned meta parameters persisted to localStorage.
                # The Parameters tab's pin checkboxes write here; the
                # `sidebar-pinned-card` reads it to render a read-only
                # name+value mirror visible from any tab.
                dcc.Store(id="pinned-params-store", storage_type="local", data=[]),
                # CAN-016a: dashboard layout state persisted to localStorage.
                # Currently captures the last-active tab so the dashboard
                # restores to whatever the user was looking at on the
                # previous session. Theme already persists via the
                # `dark-mode-store` Store; this is the same pattern.
                # Schema is open so future layout state (sidebar collapse,
                # window-size overrides, etc.) can be added without a
                # storage migration — unknown keys are ignored on read.
                dcc.Store(
                    id="layout-state-store",
                    storage_type="local",
                    data={"active_tab": "metrics"},
                ),
                # CAN-019: walkthrough tutorial state.
                #   walkthrough-steps-store holds the static step config (set
                #     once at mount from walkthrough_steps.WALKTHROUGH_STEPS).
                #   walkthrough-state-store holds {active, index} — toggled by
                #     the Tutorial-tab launch button and by the JS overlay's
                #     Skip / Done handlers (via dash_clientside.set_props).
                dcc.Store(id="walkthrough-steps-store", data=_walkthrough_steps()),
                dcc.Store(id="walkthrough-state-store", data={"active": False, "index": 0}),
                # Network Evolution: ring-buffered timeline of cascade-grow
                # snapshots, populated client-side from ws-cascade-add-buffer
                # events. Each entry is a tiny dict with counts only — full
                # connections lists would explode the store at 20×.
                dcc.Store(id="evolution-snapshots-store", data=[]),
                # Update intervals
                dcc.Interval(id="fast-update-interval", interval=DashboardConstants.FAST_UPDATE_INTERVAL_MS, n_intervals=0),
                dcc.Interval(id="slow-update-interval", interval=DashboardConstants.SLOW_UPDATE_INTERVAL_MS, n_intervals=0),
                # One-shot interval for parameter initialization (fires once, 1s after load)
                dcc.Interval(id="params-init-interval", interval=1000, max_intervals=1, n_intervals=0),
                # CAN-000: pause periodic update intervals while the Apply Parameters
                # button is in flight, so a server roundtrip isn't racing against
                # interval-driven REST polls / clientside drains.
                dcc.Store(id="apply-in-flight", data=False),
                # Phase B: WebSocket drain stores (structured objects, D-07)
                dcc.Store(id="ws-metrics-buffer", data={"events": [], "gen": 0, "last_drain_ms": 0}),
                dcc.Store(id="ws-topology-buffer", data=None),
                dcc.Store(id="ws-state-buffer", data=None),
                dcc.Store(id="ws-cascade-add-buffer", data={"events": [], "gen": 0, "last_drain_ms": 0}),
                dcc.Store(id="ws-candidate-progress-buffer", data={"events": [], "gen": 0, "last_drain_ms": 0}),
                dcc.Store(id="ws-connection-status", data={"connected": False, "reconnecting": False, "mode": "demo" if get_settings().demo_mode else "live"}),
                # GAP-WS-15: bridge for `settings.enable_raf_coalescer` → JS `window._juniperRafCoalescerEnabled`
                dcc.Store(id="ws-config-init", data=None),
                # Raw weight-oriented topology for heatmap view (OF-1)
                dcc.Store(id="network-visualizer-raw-topology-store", data=None),
                # Tooltips for parameter controls
                *[dbc.Tooltip(text, target=target_id, placement="top") for target_id, text in CONTROL_TOOLTIPS.items()],
                # CAN-018: right-click context menus reuse the same tooltip
                # source. The Store exposes the dict to clientside JS; the
                # tutorial-trigger Store is written by the JS context-menu's
                # "View tutorial" action and drives a clientside callback
                # that switches `visualization-tabs.active_tab` to "tutorial".
                dcc.Store(id="control-tooltips-store", data=CONTROL_TOOLTIPS),
                dcc.Store(id="context-menu-tutorial-trigger", data=None),
                # Getting Started welcome modal (shows on first visit)
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Welcome to Juniper Canopy")),
                        dbc.ModalBody(
                            [
                                html.P(
                                    "Juniper Canopy is a real-time monitoring dashboard for Cascade Correlation " "Neural Network training. Here's how to get started:",
                                    className="lead",
                                ),
                                html.Ol(
                                    [
                                        html.Li("Configure parameters in the sidebar (or use defaults)"),
                                        html.Li("Click Start to begin training"),
                                        html.Li("Watch metrics, topology, and decision boundaries update live"),
                                        html.Li("Save snapshots to checkpoint your progress"),
                                    ]
                                ),
                                html.P(
                                    [
                                        "See the ",
                                        html.Strong("Tutorial"),
                                        " tab for a complete reference guide.",
                                    ],
                                    className="text-muted",
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            dbc.Button("Get Started", id="welcome-modal-close", color="primary"),
                        ),
                    ],
                    id="welcome-modal",
                    is_open=False,
                    centered=True,
                    size="lg",
                ),
                # Hidden div to store WebSocket data
                html.Div(id="websocket-data", style={"display": "none"}),
                dcc.Store(id="training-control-action", data=None),
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
                # Store for tracking applied parameter values
                dcc.Store(
                    id="applied-params-store",
                    data={},
                ),
            ],
            fluid=True,
        )

    def _api_url(self, path: str) -> str:
        """
        Build API URL using settings-based server address.

        Uses the configured server port instead of Flask request context,
        which is unsafe outside of request handling (startup, background tasks).

        Args:
            path: API path (e.g., "/api/health")

        Returns:
            Full API URL (e.g., "http://127.0.0.1:8050/api/health")
        """
        return f"{self._api_base_url}/{path.lstrip('/')}"

    def _setup_callbacks(self):
        """Set up dashboard callbacks."""
        self._setup_theme_callbacks()  # Define theme callbacks
        self._setup_sidebar_visibility_callback()  # Contextual sidebar visibility
        self._setup_status_bar_callbacks()  # Define Status Bar callbacks
        self._setup_network_callbacks()  # Define Network callbacks
        self._setup_datastore_callbacks()  # Component data store updaters
        self._setup_button_action_callbacks()  # Define button action callbacks
        self._setup_backend_callbacks()  # Define backend callbacks

    def _setup_sidebar_visibility_callback(self):
        """Set up sidebar contextual visibility based on active tab."""

        @self.app.callback(
            [Output(section_id, "style") for section_id in SIDEBAR_SECTION_IDS]
            + [
                Output("nn-subsection-collapse", "is_open", allow_duplicate=True),
                Output("cn-subsection-collapse", "is_open", allow_duplicate=True),
                Output("sidebar-meta-params-header", "children"),
            ],
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=True,
        )
        def update_sidebar_visibility(active_tab):
            """Toggle sidebar section visibility based on active tab."""
            config = TAB_SIDEBAR_CONFIG.get(active_tab, {})
            styles = [{"display": "block"} if config.get(section_id, False) else {"display": "none"} for section_id in SIDEBAR_SECTION_IDS]
            # Auto-open NN/CN collapses when their content is contextually visible
            nn_open = config.get("sidebar-nn-section", False)
            cn_open = config.get("sidebar-cn-section", False)
            # Dynamic card header text
            header_text = TAB_HEADER_MAP.get(active_tab, "Meta Parameters")
            return styles + [nn_open, cn_open, header_text]

    # Define theme callbacks
    def _setup_theme_callbacks(self):
        """Set up dashboard theme callbacks."""

        @self.app.callback(
            [
                Output("dark-mode-store", "data"),
                Output("dark-mode-toggle", "children"),
            ],
            Input("dark-mode-toggle", "n_clicks"),
            State("dark-mode-store", "data"),
            prevent_initial_call=True,
        )
        def toggle_dark_mode(n_clicks, current_dark_mode):
            """Toggle dark mode on button click."""
            return self._toggle_dark_mode_handler(current_dark_mode=current_dark_mode)

        # PERF-CN-01: prevent_initial_call=False — must propagate the initial
        # dark-mode-store value to theme-state on mount so theme-aware components
        # render with the correct theme on first paint.
        @self.app.callback(
            Output("theme-state", "data"),
            Input("dark-mode-store", "data"),
            prevent_initial_call=False,
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

        # ── Welcome modal: show on first visit, dismiss with localStorage ──
        self.app.clientside_callback(
            """
            function(n) {
                if (!localStorage.getItem('juniper_canopy_welcomed')) {
                    return true;
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("welcome-modal", "is_open", allow_duplicate=True),
            Input("params-init-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        self.app.clientside_callback(
            """
            function(n) {
                localStorage.setItem('juniper_canopy_welcomed', '1');
                return false;
            }
            """,
            Output("welcome-modal", "is_open", allow_duplicate=True),
            Input("welcome-modal-close", "n_clicks"),
            prevent_initial_call=True,
        )

        # ── Layout persistence: save active tab to localStorage ──
        self.app.clientside_callback(
            """
            function(active_tab) {
                if (active_tab) {
                    localStorage.setItem('juniper_canopy_active_tab', active_tab);
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("visualization-tabs", "active_tab", allow_duplicate=True),
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=True,
        )

        # ── Layout persistence: restore active tab from localStorage on load ──
        self.app.clientside_callback(
            """
            function(n) {
                var saved = localStorage.getItem('juniper_canopy_active_tab');
                if (saved) {
                    return saved;
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("visualization-tabs", "active_tab", allow_duplicate=True),
            Input("params-init-interval", "n_intervals"),
            prevent_initial_call=True,
        )

    # Define Status Bar callbacks
    def _setup_status_bar_callbacks(self):

        # PERF-CN-01: prevent_initial_call=False — must populate the unified
        # status bar (connection, latency, phase, epoch, hidden units) on mount
        # before the first interval tick.
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
            prevent_initial_call=False,
        )
        def update_unified_status_bar(n_intervals):
            """Update unified status bar with all state info."""
            return self._update_unified_status_bar_handler(n_intervals=n_intervals)

    # Define Network callbacks
    def _setup_network_callbacks(self):

        # PERF-CN-01: prevent_initial_call=False — must populate the network
        # info panel from the API on mount before the first interval tick.
        @self.app.callback(
            Output("network-info-panel", "children"),
            Input("slow-update-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def update_network_info(n):
            """Update network information panel from API."""
            return self._update_network_info_handler(n=n)

        @self.app.callback(
            Output("network-info-collapse", "is_open"),
            Input("network-info-header", "n_clicks"),
            State("network-info-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_network_info(n, is_open):
            """Toggle Network Information section collapse state."""
            return not is_open

        @self.app.callback(
            [
                Output("network-info-details-collapse", "is_open"),
                Output("network-info-details-icon", "children"),
            ],
            Input("network-info-details-header", "n_clicks"),
            State("network-info-details-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_network_info_details(n, is_open):
            """Toggle Network Information: Details section collapse state."""
            new_state = not is_open
            icon = "▼" if new_state else "▶"
            return new_state, icon

        # PERF-CN-01: prevent_initial_call=False — must populate the network
        # info details panel from the API on mount before the first interval tick.
        @self.app.callback(
            Output("network-info-details-panel", "children"),
            Input("slow-update-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def update_network_info_details(n):
            """Update detailed network information panel from API."""
            return self._update_network_info_details_handler(n=n)

    # Component data store updaters
    def _setup_datastore_callbacks(self):

        # CAN-000: pause periodic update intervals while Apply Parameters is in
        # flight. The user-visible behavior fix is that the dashboard stops
        # firing REST polls and ws-buffer drains the moment Apply is clicked
        # and resumes the next time `applied-params-store` updates (the
        # apply_parameters server callback always writes that store, on both
        # success and failure paths, so resume is reliable).
        #
        # Three small clientside callbacks:
        #   1. apply-button click -> apply-in-flight = True
        #   2. applied-params-store update -> apply-in-flight = False
        #   3. apply-in-flight -> {fast,slow}-update-interval.disabled
        # The third callback fires on layout mount (prevent_initial_call=False)
        # so the intervals start in their default enabled state.
        self.app.clientside_callback(
            """
            function(nClicks) {
                if (!nClicks) return window.dash_clientside.no_update;
                return true;
            }
            """,
            Output("apply-in-flight", "data"),
            Input("apply-params-button", "n_clicks"),
            prevent_initial_call=True,
        )
        self.app.clientside_callback(
            """
            function(appliedData) {
                // applied-params-store is written by apply_parameters() on
                // every click, success or failure. Whenever it updates,
                // the in-flight clamp can come off.
                return false;
            }
            """,
            Output("apply-in-flight", "data", allow_duplicate=True),
            Input("applied-params-store", "data"),
            prevent_initial_call=True,
        )
        self.app.clientside_callback(
            """
            function(inFlight) {
                var disabled = Boolean(inFlight);
                return [disabled, disabled];
            }
            """,
            [
                Output("fast-update-interval", "disabled"),
                Output("slow-update-interval", "disabled"),
            ],
            Input("apply-in-flight", "data"),
            prevent_initial_call=False,
        )

        # CAN-018: hand the CONTROL_TOOLTIPS dict to the
        # context_menus.js asset on layout mount so it can intercept
        # right-clicks on every tooltipped control. The asset is
        # idempotent — repeat invocations only refresh the dict.
        # NOTE: this clientside_callback was clobbered during the
        # Phase-1/2 merge sequence and restored from PR #191's tip
        # (commit 52f905d) — see fix/track-6d-restore-clobbered-tests.
        self.app.clientside_callback(
            """
            function(tooltips) {
                if (window.juniperCanopy && window.juniperCanopy.installContextMenus) {
                    window.juniperCanopy.installContextMenus(tooltips || {});
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("control-tooltips-store", "data", allow_duplicate=True),
            Input("control-tooltips-store", "data"),
            prevent_initial_call="initial_duplicate",
        )

        # CAN-018: when the JS context-menu's "View tutorial" link is
        # clicked, it bumps `context-menu-tutorial-trigger`. Switch the
        # active tab so the user lands on the Tutorial tab.
        self.app.clientside_callback(
            """
            function(triggerTs) {
                if (!triggerTs) return window.dash_clientside.no_update;
                return "tutorial";
            }
            """,
            Output("visualization-tabs", "active_tab", allow_duplicate=True),
            Input("context-menu-tutorial-trigger", "data"),
            prevent_initial_call=True,
        )

        # CAN-016a: restore the persisted active tab on layout mount.
        # `layout-state-store` is `storage_type="local"`, so on a fresh
        # session it carries the layout default; on a returning session
        # it carries whatever was stamped at the last tab change.
        self.app.clientside_callback(
            """
            function(state) {
                if (!state || !state.active_tab) return window.dash_clientside.no_update;
                return state.active_tab;
            }
            """,
            Output("visualization-tabs", "active_tab", allow_duplicate=True),
            Input("layout-state-store", "data"),
            prevent_initial_call="initial_duplicate",
        )

        # CAN-019: launch the walkthrough overlay when the Tutorial-tab button
        # is clicked. Writes `{active: true, index: 0}` to the state store; the
        # overlay-driver callback below reacts to that and calls
        # window._juniperWalkthrough.show(steps, 0).
        self.app.clientside_callback(
            """
            function(nClicks) {
                if (!nClicks) return window.dash_clientside.no_update;
                return {active: true, index: 0};
            }
            """,
            Output("walkthrough-state-store", "data", allow_duplicate=True),
            Input("walkthrough-launch-btn", "n_clicks"),
            prevent_initial_call=True,
        )

        # CAN-019: drive the JS overlay from walkthrough-state-store changes.
        # Triggers on every state update — when active flips true, show the
        # step at the stored index; when false, hide the overlay (in case it
        # was dismissed via an external path like a programmatic `Esc`).
        self.app.clientside_callback(
            """
            function(state, steps) {
                if (!window._juniperWalkthrough) {
                    return window.dash_clientside.no_update;
                }
                if (state && state.active) {
                    var stepsArr = Array.isArray(steps) ? steps : [];
                    window._juniperWalkthrough.show(stepsArr, (state.index|0));
                } else {
                    window._juniperWalkthrough.hide();
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output("walkthrough-state-store", "data", allow_duplicate=True),
            Input("walkthrough-state-store", "data"),
            State("walkthrough-steps-store", "data"),
            prevent_initial_call=True,
        )

        # CAN-016a: stamp the layout-state-store whenever the active
        # tab changes. Spread-merge over the existing state so future
        # layout keys (sidebar collapse, etc.) co-exist without
        # collisions.
        self.app.clientside_callback(
            """
            function(activeTab, state) {
                if (!activeTab) return window.dash_clientside.no_update;
                var prev = state || {};
                if (prev.active_tab === activeTab) return window.dash_clientside.no_update;
                return Object.assign({}, prev, {active_tab: activeTab});
            }
            """,
            Output("layout-state-store", "data", allow_duplicate=True),
            Input("visualization-tabs", "active_tab"),
            State("layout-state-store", "data"),
            prevent_initial_call=True,
        )

        # Phase B: WebSocket drain callbacks.
        # WS connection and buffering handled by websocket_client.js + ws_dash_bridge.js.
        # These clientside callbacks drain ring buffers into Dash stores on each interval tick.

        # GAP-WS-15: bridge `settings.enable_raf_coalescer` -> JS at app load.
        # Fires on the layout-mount Input("ws-config-init", "id") so the JS
        # global is set before the first WS event arrives. The flag controls
        # whether the candidate_progress handler in ws_dash_bridge.js coalesces
        # 50Hz events into one push per requestAnimationFrame (latest-value-wins).
        raf_flag = "true" if getattr(self._settings, "enable_raf_coalescer", False) else "false"
        self.app.clientside_callback(
            f"""
            function() {{
                window._juniperRafCoalescerEnabled = {raf_flag};
                return {{rafCoalescer: {raf_flag}}};
            }}
            """,
            Output("ws-config-init", "data"),
            Input("ws-config-init", "id"),
            prevent_initial_call=False,
        )

        # Drain metrics buffer → ws-metrics-buffer store (D-07 structured object)
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var events = window._juniperWsDrain.drainMetrics();
                if (!events || events.length === 0) return window.dash_clientside.no_update;
                window._juniperWsDrain._gen++;
                return {events: events, gen: window._juniperWsDrain._gen, last_drain_ms: Date.now()};
            }
            """,
            Output("ws-metrics-buffer", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Drain topology buffer → ws-topology-buffer store
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var topo = window._juniperWsDrain.drainTopology();
                if (!topo) return window.dash_clientside.no_update;
                return topo;
            }
            """,
            Output("ws-topology-buffer", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Drain state buffer → ws-state-buffer store
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var state = window._juniperWsDrain.drainState();
                if (!state) return window.dash_clientside.no_update;
                return state;
            }
            """,
            Output("ws-state-buffer", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Drain cascade_add buffer → ws-cascade-add-buffer store
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var events = window._juniperWsDrain.drainCascadeAdd();
                if (!events || events.length === 0) return window.dash_clientside.no_update;
                window._juniperWsDrain._gen++;
                return {events: events, gen: window._juniperWsDrain._gen, last_drain_ms: Date.now()};
            }
            """,
            Output("ws-cascade-add-buffer", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Drain candidate_progress buffer → ws-candidate-progress-buffer store
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var events = window._juniperWsDrain.drainCandidateProgress();
                if (!events || events.length === 0) return window.dash_clientside.no_update;
                window._juniperWsDrain._gen++;
                return {events: events, gen: window._juniperWsDrain._gen, last_drain_ms: Date.now()};
            }
            """,
            Output("ws-candidate-progress-buffer", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Connection status → ws-connection-status store (peek, not drain)
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                return window._juniperWsDrain.peekConnectionStatus();
            }
            """,
            Output("ws-connection-status", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # Phase B: Connection indicator badge (4-state: connected/reconnecting/offline/demo)
        self.app.clientside_callback(
            CONNECTION_INDICATOR_JS,
            Output("ws-connection-indicator", "children"),
            Output("ws-connection-indicator", "style"),
            Input("ws-connection-status", "data"),
        )

        # Network Evolution: capture a snapshot whenever a ``cascade_add`` event
        # arrives over WebSocket. Reads the current topology from the existing
        # network-visualizer store (no need for a parallel data path). Bounded
        # to MAX_SNAPSHOTS — oldest evicted on overflow. Snapshots are pushed
        # to the head so the grid renders newest-first.
        #
        # Auto-clear semantics: when input_units changes (= different network /
        # dataset replacement) or hidden_units shrinks below the most recent
        # snapshot's count (= reset signal), wipe the timeline. This keeps a
        # session-bounded view and avoids carrying stale snapshots across runs.
        self.app.clientside_callback(
            f"""
            function(cascadeBuf, topology, snapshots) {{
                var snaps = Array.isArray(snapshots) ? snapshots : [];
                if (!topology) {{
                    return window.dash_clientside.no_update;
                }}
                var iu = (topology.input_units|0);
                var hu = (topology.hidden_units|0);
                var ou = (topology.output_units|0);

                // Auto-clear on dataset / network reset.
                if (snaps.length > 0) {{
                    var head = snaps[0];
                    if ((head.input_units|0) !== iu || hu < (head.hidden_units|0)) {{
                        snaps = [];
                    }}
                }}

                // Read epoch from metrics store if available.
                var epoch = null;
                try {{
                    if (window._juniperWsDrain && Array.isArray(window._juniperWsDrain._metricsBuffer)
                            && window._juniperWsDrain._metricsBuffer.length > 0) {{
                        var lastMetric = window._juniperWsDrain._metricsBuffer[window._juniperWsDrain._metricsBuffer.length - 1];
                        if (lastMetric && typeof lastMetric.epoch !== "undefined") {{
                            epoch = lastMetric.epoch;
                        }}
                    }}
                }} catch (e) {{ /* best-effort epoch tagging */ }}

                // De-dupe: only push if hidden_units differs from the head.
                if (snaps.length > 0 && (snaps[0].hidden_units|0) === hu
                        && (snaps[0].input_units|0) === iu
                        && (snaps[0].output_units|0) === ou) {{
                    return window.dash_clientside.no_update;
                }}

                var newSnap = {{
                    timestamp: Date.now(),
                    epoch: epoch,
                    input_units: iu,
                    hidden_units: hu,
                    output_units: ou,
                }};
                var next = [newSnap].concat(snaps);
                if (next.length > {_EVOLUTION_MAX_SNAPSHOTS}) {{
                    next = next.slice(0, {_EVOLUTION_MAX_SNAPSHOTS});
                }}
                return next;
            }}
            """,
            Output("evolution-snapshots-store", "data", allow_duplicate=True),
            [
                Input("ws-cascade-add-buffer", "data"),
                Input("network-visualizer-topology-store", "data"),
            ],
            State("evolution-snapshots-store", "data"),
            prevent_initial_call=True,
        )

        # Network Evolution: explicit Clear button wipes the snapshots store.
        self.app.clientside_callback(
            """
            function(nClicks) {
                if (!nClicks) return window.dash_clientside.no_update;
                return [];
            }
            """,
            Output("evolution-snapshots-store", "data", allow_duplicate=True),
            Input("network-evolution-clear-btn", "n_clicks"),
            prevent_initial_call=True,
        )

        # PERF-CN-01: prevent_initial_call=True — only needs to react when the
        # applied-params-store changes (which itself only changes after the
        # backend init or a user Apply). The parameters panel handles an empty
        # initial store via its own update_parameters_tables fallback.
        @self.app.callback(
            Output("parameters-panel-params-store", "data"),
            Input("applied-params-store", "data"),
            dash.dependencies.State("visualization-tabs", "active_tab"),
            prevent_initial_call=True,
        )
        def update_parameters_panel_store(applied_data, active_tab):
            """Propagate applied parameters to the parameters panel store.

            Strips nn_/cn_ prefixes so the parameters panel can look up
            values by their unprefixed canonical names.
            """
            if not applied_data:
                return {}
            stripped = {}
            for key, value in applied_data.items():
                if key.startswith("nn_"):
                    stripped[key[3:]] = value
                elif key.startswith("cn_"):
                    stripped[key[3:]] = value
                else:
                    stripped[key] = value
            return stripped

        # PERF-CN-01: prevent_initial_call=False — must hit /api/metrics/history
        # on mount to populate the metrics store before the first interval tick
        # (also drives the metrics panel's plots and stats).
        @self.app.callback(
            Output("metrics-panel-metrics-store", "data"),
            Input("fast-update-interval", "n_intervals"),
            dash.dependencies.State("metrics-panel-display-mode-store", "data"),
            dash.dependencies.State("ws-connection-status", "data"),
            prevent_initial_call=False,
        )
        def update_metrics_store(n, display_mode_state, ws_status):
            """Fetch metrics history from API and update metrics panel store.

            Phase B polling toggle: when WS bridge is connected, skip REST poll.
            Falls back to 1 Hz REST (D-05) when WS disconnected.
            """
            return self._update_metrics_store_handler(n=n, display_mode_state=display_mode_state, ws_status=ws_status)

        # PERF-CN-01: prevent_initial_call=False — must hit /api/network/topology
        # on mount (when the topology tab is active) so the network visualizer
        # has data before the first interval tick.
        @self.app.callback(
            Output("network-visualizer-topology-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("ws-topology-buffer", "data"),
            Input("visualization-tabs", "active_tab"),
            dash.dependencies.State("ws-connection-status", "data"),
            prevent_initial_call=False,
        )
        def update_topology_store(n, ws_topology, active_tab, ws_status):
            """Fetch topology from API or accept WebSocket push.

            OI-2: WebSocket topology pushes (from cascade_add events) take
            priority over REST polling for near-real-time updates.
            Phase B: skip REST poll when WS connected (D-54: REST paths preserved).
            """
            ctx = dash.callback_context
            trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            # WebSocket push takes priority — provides near-real-time updates
            if "ws-topology-buffer" in trigger and ws_topology:
                from backend.cascor_service_adapter import CascorServiceAdapter

                return CascorServiceAdapter._transform_topology(ws_topology)

            # Phase B: skip REST poll when WS bridge is connected.
            # GAP-WS-25: also require topologyReceived so we don't blank the
            # network view in the window between socket-open and the first
            # topology frame. Cascor only broadcasts `topology` on cascade_add
            # (grow events) — a fresh tab opened mid-training could otherwise
            # wait minutes for one, leaving the visualizer empty.
            settings = get_settings()
            if settings.ws_bridge_enabled and ws_status and ws_status.get("connected") and ws_status.get("topologyReceived"):
                return dash.no_update

            # REST fallback — only poll when topology tab is active
            return self._update_topology_store_handler(n=n, active_tab=active_tab)

        # PERF-CN-01: prevent_initial_call=False — must hit the raw-topology API
        # on mount when the topology tab is active and weight-matrix view is
        # selected, so the heatmap renders before the first interval tick.
        @self.app.callback(
            Output("network-visualizer-raw-topology-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
            State("network-visualizer-view-mode", "value"),
            prevent_initial_call=False,
        )
        def update_raw_topology_store(n, active_tab, view_mode):
            """Fetch raw weight-oriented topology for heatmap view (OF-1).

            Only polls when topology tab is active AND weight matrix view is selected.

            GAP-WS-25: deliberately NOT WS-gated — cascor does not broadcast
            raw weight matrices on /ws/training (only the structural `topology`
            event from cascade_add). REST is the only source for this view, so
            gating on ``ws_status.connected`` would blank the heatmap whenever
            the socket is up. Per-tab + per-view-mode gating already restricts
            polling to the heatmap surface.
            """
            return self._update_raw_topology_store_handler(n=n, active_tab=active_tab, view_mode=view_mode)

        # PERF-CN-01: prevent_initial_call=False — must hit /api/dataset on
        # mount when the dataset tab is active so the plotter has data before
        # the first interval tick.
        @self.app.callback(
            Output("dataset-plotter-dataset-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=False,
        )
        def update_dataset_store(n, active_tab):
            """Fetch dataset from API and update dataset plotter store."""
            return self._update_dataset_store_handler(n=n, active_tab=active_tab)

        # PERF-CN-01: prevent_initial_call=False — must hit /api/decision-boundary
        # on mount when the decision-boundary tab is active so the plot has data
        # before the first interval tick.
        @self.app.callback(
            Output("decision-boundary-boundary-data", "data"),
            Input("fast-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
            Input("decision-boundary-refresh-btn", "n_clicks"),
            Input("decision-boundary-resolution-slider", "value"),
            prevent_initial_call=False,
        )
        def update_boundary_store(n, active_tab, refresh_clicks, resolution):
            """Fetch decision boundary from API and update decision boundary store."""
            return self._update_boundary_store_handler(n=n, active_tab=active_tab, resolution=resolution)

        # PERF-CN-01: prevent_initial_call=False — must populate the decision-
        # boundary's dataset on mount when the tab is active so the plot has
        # the underlying scatter data before the first interval tick.
        @self.app.callback(
            Output("decision-boundary-dataset-data", "data"),
            Input("fast-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=False,
        )
        def update_boundary_dataset_store(n, active_tab):
            """Sync dataset data to decision boundary component."""
            return self._update_boundary_dataset_store_handler(n=n, active_tab=active_tab)

        # ── Dataset generation modal callbacks ──

        @self.app.callback(
            Output("dataset-plotter-generate-modal", "is_open"),
            [
                Input("dataset-plotter-generate-btn", "n_clicks"),
                Input("dataset-plotter-gen-cancel", "n_clicks"),
                Input("dataset-plotter-gen-confirm", "n_clicks"),
                # CAN-016b: import-file / import-url confirm clicks also close the modal.
                Input("dataset-plotter-import-file-confirm", "n_clicks"),
                Input("dataset-plotter-import-url-confirm", "n_clicks"),
            ],
            dash.dependencies.State("dataset-plotter-generate-modal", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_generate_modal(open_clicks, cancel_clicks, confirm_clicks, import_file_clicks, import_url_clicks, is_open):
            ctx = get_callback_context()
            trigger = ctx.triggered_id
            if trigger == "dataset-plotter-generate-btn":
                return True
            return False

        @self.app.callback(
            [
                Output("dataset-plotter-gen-status", "children"),
                Output("dataset-plotter-dataset-store", "data", allow_duplicate=True),
            ],
            Input("dataset-plotter-gen-confirm", "n_clicks"),
            [
                dash.dependencies.State("dataset-plotter-gen-samples", "value"),
                dash.dependencies.State("dataset-plotter-gen-spirals", "value"),
                dash.dependencies.State("dataset-plotter-gen-rotations", "value"),
                dash.dependencies.State("dataset-plotter-gen-noise", "value"),
            ],
            prevent_initial_call=True,
        )
        def generate_dataset(n_clicks, n_samples, n_spirals, n_rotations, noise):
            return self._generate_dataset_handler(n_samples, n_spirals, n_rotations, noise)

        # CAN-016b: enable the "Import File" button only after a file has been
        # selected (dcc.Upload populates `contents` + `filename`). Show the
        # filename as a small label below the upload widget for visual confirmation.
        @self.app.callback(
            [
                Output("dataset-plotter-import-file-name", "children"),
                Output("dataset-plotter-import-file-confirm", "disabled"),
            ],
            Input("dataset-plotter-import-file-upload", "filename"),
            prevent_initial_call=True,
        )
        def update_import_file_label(filename):
            if not filename:
                return "", True
            return f"Selected: {filename}", False

        # CAN-016b: file-upload import handler. dcc.Upload posts a base64
        # data-URL string in `contents`; we POST it as multipart to
        # /api/dataset/import-file via the handler below.
        @self.app.callback(
            [
                Output("dataset-plotter-import-file-status", "children"),
                Output("dataset-plotter-dataset-store", "data", allow_duplicate=True),
            ],
            Input("dataset-plotter-import-file-confirm", "n_clicks"),
            [
                dash.dependencies.State("dataset-plotter-import-file-upload", "contents"),
                dash.dependencies.State("dataset-plotter-import-file-upload", "filename"),
            ],
            prevent_initial_call=True,
        )
        def import_dataset_file(n_clicks, contents, filename):
            return self._import_dataset_file_handler(contents, filename)

        # CAN-016b: URL-fetch import handler. POSTs the URL to
        # /api/dataset/import-url; the canopy server fetches the CSV.
        @self.app.callback(
            [
                Output("dataset-plotter-import-url-status", "children"),
                Output("dataset-plotter-dataset-store", "data", allow_duplicate=True),
            ],
            Input("dataset-plotter-import-url-confirm", "n_clicks"),
            dash.dependencies.State("dataset-plotter-import-url-input", "value"),
            prevent_initial_call=True,
        )
        def import_dataset_url(n_clicks, url):
            return self._import_dataset_url_handler(url)

        # CAN-005: persist the set of pinned parameter keys whenever any
        # pin checkbox in the Parameters panel toggles. Pattern-match
        # ``{"type": "param-pin", "key": ALL}`` lets one callback receive
        # every checkbox's value + id without enumerating per-key
        # dependencies. The store is the source of truth for both the
        # Parameters tab table re-render and the sidebar mirror below.
        @self.app.callback(
            Output("pinned-params-store", "data"),
            Input({"type": "param-pin", "key": dash.ALL}, "value"),
            dash.dependencies.State({"type": "param-pin", "key": dash.ALL}, "id"),
            prevent_initial_call=True,
        )
        def update_pinned_params_store(values, ids):
            """Build the pinned-keys list from current checkbox state."""
            pinned = []
            for v, id_dict in zip(values or [], ids or [], strict=False):
                if v:
                    pinned.append(id_dict.get("key"))
            return [k for k in pinned if k]

        # CAN-005: render the sidebar's "Pinned Parameters" mirror.
        # When the pinned list is empty, hide the entire card so the
        # sidebar reclaims the vertical space. When populated, show
        # name+value rows, pulling values from the Parameters panel
        # store (already stripped of nn_/cn_ prefixes by
        # update_parameters_panel_store above).
        from .components.parameters_panel import PARAM_DISPLAY_NAMES

        @self.app.callback(
            [
                Output("sidebar-pinned-list", "children"),
                Output("sidebar-pinned-card", "style"),
            ],
            [
                Input("pinned-params-store", "data"),
                Input("parameters-panel-params-store", "data"),
            ],
            prevent_initial_call=False,
        )
        def render_sidebar_pinned_mirror(pinned, params):
            pinned_keys = list(pinned or [])
            if not pinned_keys:
                return [], {"display": "none"}
            params = params or {}
            rows = []
            for key in pinned_keys:
                display_name = PARAM_DISPLAY_NAMES.get(key, key)
                value = params.get(key, "—")
                if isinstance(value, bool):
                    value = "Enabled" if value else "Disabled"
                elif isinstance(value, list):
                    value = "Enabled" if "enabled" in value else "Disabled"
                rows.append(
                    html.Div(
                        [
                            html.Span(display_name, style={"fontSize": "0.85em", "color": "var(--text-muted)"}),
                            html.Strong(str(value), className="ms-2"),
                        ],
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "baseline",
                            "padding": "4px 0",
                            "borderBottom": "1px solid var(--bs-border-color, rgba(0,0,0,.08))",
                        },
                    )
                )
            return rows, {"display": "block"}

    def _generate_dataset_handler(self, n_samples, n_spirals, n_rotations, noise):
        """Handle dataset generation request."""
        try:
            url = self._api_url("/api/dataset/generate")
            payload = {
                "n_samples": int(n_samples or 200),
                "n_spirals": int(n_spirals or 2),
                "n_rotations": float(n_rotations or 1.5),
                "noise": float(noise or 0.1),
            }
            response = requests.post(url, json=payload, timeout=DashboardConstants.API_TIMEOUT_SECONDS + 5)
            if response.ok:
                return "✅ Dataset generated", response.json()
            return f"❌ {response.json().get('error', 'Failed')}", dash.no_update
        except Exception as e:
            self.logger.warning(f"Dataset generation failed: {e}")
            return f"❌ Error: {e}", dash.no_update

    def _import_dataset_file_handler(self, contents, filename):
        """CAN-016b: handle CSV file-upload import.

        ``dcc.Upload.contents`` is a data-URL like ``data:text/csv;base64,<b64>``.
        We strip the prefix, decode the base64 body, and POST the raw bytes as
        multipart to /api/dataset/import-file. The server-side handler validates
        format + size, parses, and replaces the active dataset.
        """
        if not contents:
            return "❌ No file selected", dash.no_update
        try:
            import base64

            if "," not in contents:
                return "❌ Invalid file payload (missing data-URL header)", dash.no_update
            _, b64_body = contents.split(",", 1)
            try:
                file_bytes = base64.b64decode(b64_body, validate=False)
            except (ValueError, TypeError) as exc:
                return f"❌ Could not decode upload: {exc}", dash.no_update

            url = self._api_url("/api/dataset/import-file")
            files = {"file": (filename or "upload.csv", file_bytes, "text/csv")}
            response = requests.post(url, files=files, timeout=DashboardConstants.API_TIMEOUT_SECONDS + 10)
            if response.ok:
                return f"✅ Imported {filename or 'file'}", response.json()
            try:
                err = response.json().get("error", f"HTTP {response.status_code}")
            except Exception:
                err = f"HTTP {response.status_code}"
            return f"❌ {err}", dash.no_update
        except Exception as e:
            self.logger.warning(f"Dataset import (file) failed: {e}")
            return f"❌ Error: {e}", dash.no_update

    def _import_dataset_url_handler(self, url_value):
        """CAN-016b: handle URL-fetch dataset import.

        Posts the URL as JSON to /api/dataset/import-url; the server-side
        handler does the fetch + parse + dataset replacement. The canopy
        server's network is what reaches the URL, not the user's browser —
        useful for fetching from internal hosts the user can't see directly.
        """
        if not url_value or not url_value.strip():
            return "❌ Enter a URL", dash.no_update
        try:
            url = self._api_url("/api/dataset/import-url")
            response = requests.post(url, json={"url": url_value.strip()}, timeout=DashboardConstants.API_TIMEOUT_SECONDS + 15)
            if response.ok:
                return f"✅ Imported from {url_value.strip()}", response.json()
            try:
                err = response.json().get("error", f"HTTP {response.status_code}")
            except Exception:
                err = f"HTTP {response.status_code}"
            return f"❌ {err}", dash.no_update
        except Exception as e:
            self.logger.warning(f"Dataset import (url) failed: {e}")
            return f"❌ Error: {e}", dash.no_update

    # Define button action callbacks
    def _setup_button_action_callbacks(self):

        # Phase D §S10.3 (P12b): when enable_ws_control_buttons is True, training
        # buttons route through ``window.cascorControlWS.send()`` via a Dash
        # clientside callback. The browser decides WS-vs-REST per click with
        # automatic REST fallback if the send() promise rejects. When the flag
        # is off (default), the pre-Phase-D server-side handler is registered
        # instead and keeps the existing behavior plus test fixtures untouched.
        if getattr(self._settings, "enable_ws_control_buttons", False):
            self.app.clientside_callback(
                PHASE_D_TRAINING_BUTTONS_CLIENTSIDE_JS,
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
            self.logger.info("Phase D: training buttons registered as CLIENTSIDE callback (enable_ws_control_buttons=True)")
        else:

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

        # PERF-CN-01: prevent_initial_call=True — only meaningful when an actual
        # control action has been dispatched; the empty initial training-control-
        # action store does not need a debounce timestamp.
        @self.app.callback(
            Output("last-button-click", "data"),
            Input("training-control-action", "data"),
            prevent_initial_call=True,
        )
        def update_last_click(action):
            """Update last button click timestamp for debouncing."""
            return self._update_last_click_handler(action=action)

        # PERF-CN-01: prevent_initial_call=False — must apply the initial
        # button-states (disabled/loading flags and labels) on mount so the
        # training control buttons render in their correct initial state.
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
            prevent_initial_call=False,
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

        # ── Collapsible section toggles ──

        @self.app.callback(
            [Output("nn-subsection-collapse", "is_open"), Output("nn-subsection-icon", "children")],
            Input("nn-subsection-header", "n_clicks"),
            dash.dependencies.State("nn-subsection-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_nn_subsection(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

        @self.app.callback(
            [Output("cn-subsection-collapse", "is_open"), Output("cn-subsection-icon", "children")],
            Input("cn-subsection-header", "n_clicks"),
            dash.dependencies.State("cn-subsection-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_cn_subsection(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

        # ── Contextual collapsible section toggles ──

        @self.app.callback(
            [Output("ctx-growth-triggers-collapse", "is_open"), Output("ctx-growth-triggers-icon", "children")],
            Input("ctx-growth-triggers-header", "n_clicks"),
            dash.dependencies.State("ctx-growth-triggers-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_ctx_growth_triggers(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

        @self.app.callback(
            [Output("ctx-multi-node-collapse", "is_open"), Output("ctx-multi-node-icon", "children")],
            Input("ctx-multi-node-header", "n_clicks"),
            dash.dependencies.State("ctx-multi-node-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_ctx_multi_node(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

        @self.app.callback(
            [Output("ctx-spiral-dataset-collapse", "is_open"), Output("ctx-spiral-dataset-icon", "children")],
            Input("ctx-spiral-dataset-header", "n_clicks"),
            dash.dependencies.State("ctx-spiral-dataset-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_ctx_spiral_dataset(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

        @self.app.callback(
            [Output("ctx-pool-training-collapse", "is_open"), Output("ctx-pool-training-icon", "children")],
            Input("ctx-pool-training-header", "n_clicks"),
            dash.dependencies.State("ctx-pool-training-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_ctx_pool_training(n_clicks, is_open):
            return not is_open, "▼" if not is_open else "▶"

        # ── Radio button enable/disable callbacks ──

        # PERF-CN-01: prevent_initial_call=False — must compute initial
        # disabled state on mount so the dependent inputs match the radio's
        # default selection (otherwise the inputs render in a stale state).
        @self.app.callback(
            [Output("nn-growth-preset-epochs-input", "disabled"), Output("nn-growth-convergence-threshold-input", "disabled")],
            Input("nn-growth-trigger-radio", "value"),
            prevent_initial_call=False,
        )
        def toggle_nn_growth_inputs(growth_trigger):
            return self._toggle_nn_growth_inputs_handler(growth_trigger)

        # PERF-CN-01: prevent_initial_call=False — same rationale as above:
        # initial disabled state must match the radio's default value on mount.
        @self.app.callback(
            [Output("cn-training-iterations-input", "disabled"), Output("cn-training-convergence-threshold-input", "disabled")],
            Input("cn-training-complete-radio", "value"),
            prevent_initial_call=False,
        )
        def toggle_cn_training_inputs(training_complete):
            return self._toggle_cn_training_inputs_handler(training_complete)

        # PERF-CN-01: prevent_initial_call=False — same rationale: initial
        # candidate-selection inputs disabled state depends on the radio default.
        @self.app.callback(
            [Output("cn-top-candidates-input", "disabled"), Output("cn-random-candidates-input", "disabled")],
            Input("cn-candidate-selection-radio", "value"),
            prevent_initial_call=False,
        )
        def toggle_cn_selection_inputs(selection_mode):
            return self._toggle_cn_selection_inputs_handler(selection_mode)

        # ── Multi candidate sub-group enable/disable ──

        @self.app.callback(
            [
                Output("cn-candidate-selection-radio", "style"),
                Output("cn-top-candidates-input", "disabled", allow_duplicate=True),
                Output("cn-random-candidates-input", "disabled", allow_duplicate=True),
            ],
            Input("cn-multi-candidate-checkbox", "value"),
            prevent_initial_call=True,
        )
        def toggle_cn_multi_candidate_subgroup(value):
            return self._toggle_cn_multi_candidate_subgroup_handler(value)

        # ── Cross-section checkbox sync ──

        @self.app.callback(
            [
                Output("nn-multi-node-layers-checkbox", "value", allow_duplicate=True),
                Output("cn-multi-candidate-checkbox", "value", allow_duplicate=True),
            ],
            [
                Input("nn-multi-node-layers-checkbox", "value"),
                Input("cn-multi-candidate-checkbox", "value"),
            ],
            prevent_initial_call=True,
        )
        def sync_multi_node_checkboxes(nn_value, cn_value):
            return self._sync_multi_node_checkboxes_handler(nn_value, cn_value)

        # ── Track parameter changes to enable/disable Apply button ──

        @self.app.callback(
            [
                Output("apply-params-button", "disabled"),
                Output("params-status", "children"),
            ],
            [
                # Neural Network (13)
                Input("nn-max-iterations-input", "value"),
                Input("nn-max-total-epochs-input", "value"),
                Input("nn-learning-rate-input", "value"),
                Input("nn-max-hidden-units-input", "value"),
                Input("nn-multi-node-layers-checkbox", "value"),
                Input("nn-growth-trigger-radio", "value"),
                Input("nn-growth-preset-epochs-input", "value"),
                Input("nn-growth-convergence-threshold-input", "value"),
                Input("nn-patience-input", "value"),
                Input("nn-spiral-rotations-input", "value"),
                Input("nn-spiral-number-input", "value"),
                Input("nn-dataset-elements-input", "value"),
                Input("nn-dataset-noise-input", "value"),
                # Candidate Nodes (10)
                Input("cn-pool-size-input", "value"),
                Input("cn-correlation-threshold-input", "value"),
                Input("cn-selected-candidates-input", "value"),
                Input("cn-training-complete-radio", "value"),
                Input("cn-training-iterations-input", "value"),
                Input("cn-training-convergence-threshold-input", "value"),
                Input("cn-patience-input", "value"),
                Input("cn-multi-candidate-checkbox", "value"),
                Input("cn-candidate-selection-radio", "value"),
                Input("cn-top-candidates-input", "value"),
                Input("cn-random-candidates-input", "value"),
                # Phase 6E A-1: output_epochs (per-output-pass epoch budget)
                Input("nn-output-epochs-input", "value"),
                # Phase 6E A-2: optimizer_type (output-layer optimizer)
                Input("nn-optimizer-type-dropdown", "value"),
                # Phase 6E A-3: activation_function_name (hidden-unit activation)
                Input("nn-activation-function-dropdown", "value"),
                # Store
                Input("applied-params-store", "data"),
            ],
            # PERF-CN-01: prevent_initial_call=False — must compute the initial
            # disabled state of the Apply button by comparing current input
            # values against the applied-params-store on mount.
            prevent_initial_call=False,
        )
        def track_param_changes(
            nn_max_iter,
            nn_max_epochs,
            nn_lr,
            nn_max_hu,
            nn_multi_node,
            nn_growth_trigger,
            nn_growth_epochs,
            nn_growth_conv_thresh,
            nn_patience,
            nn_spiral_rot,
            nn_spiral_num,
            nn_dataset_elem,
            nn_dataset_noise,
            cn_pool_size,
            cn_corr_thresh,
            cn_selected,
            cn_training_complete,
            cn_training_iter,
            cn_training_conv_thresh,
            cn_patience,
            cn_multi_cand,
            cn_cand_selection,
            cn_top_cands,
            cn_random_cands,
            nn_output_epochs,
            nn_optimizer_type,
            nn_activation_function,
            applied,
        ):
            """Enable Apply button when parameters differ from applied values."""
            return self._track_param_changes_handler(
                nn_max_iter,
                nn_max_epochs,
                nn_lr,
                nn_max_hu,
                nn_multi_node,
                nn_growth_trigger,
                nn_growth_epochs,
                nn_growth_conv_thresh,
                nn_patience,
                nn_spiral_rot,
                nn_spiral_num,
                nn_dataset_elem,
                nn_dataset_noise,
                cn_pool_size,
                cn_corr_thresh,
                cn_selected,
                cn_training_complete,
                cn_training_iter,
                cn_training_conv_thresh,
                cn_patience,
                cn_multi_cand,
                cn_cand_selection,
                cn_top_cands,
                cn_random_cands,
                nn_output_epochs,
                nn_optimizer_type,
                nn_activation_function,
                applied,
            )

        # ── Handle Apply button click ──

        @self.app.callback(
            [
                Output("applied-params-store", "data"),
                Output("params-status", "children", allow_duplicate=True),
            ],
            Input("apply-params-button", "n_clicks"),
            [
                # Neural Network (13)
                dash.dependencies.State("nn-max-iterations-input", "value"),
                dash.dependencies.State("nn-max-total-epochs-input", "value"),
                dash.dependencies.State("nn-learning-rate-input", "value"),
                dash.dependencies.State("nn-max-hidden-units-input", "value"),
                dash.dependencies.State("nn-multi-node-layers-checkbox", "value"),
                dash.dependencies.State("nn-growth-trigger-radio", "value"),
                dash.dependencies.State("nn-growth-preset-epochs-input", "value"),
                dash.dependencies.State("nn-growth-convergence-threshold-input", "value"),
                dash.dependencies.State("nn-patience-input", "value"),
                dash.dependencies.State("nn-spiral-rotations-input", "value"),
                dash.dependencies.State("nn-spiral-number-input", "value"),
                dash.dependencies.State("nn-dataset-elements-input", "value"),
                dash.dependencies.State("nn-dataset-noise-input", "value"),
                # Candidate Nodes (10)
                dash.dependencies.State("cn-pool-size-input", "value"),
                dash.dependencies.State("cn-correlation-threshold-input", "value"),
                dash.dependencies.State("cn-selected-candidates-input", "value"),
                dash.dependencies.State("cn-training-complete-radio", "value"),
                dash.dependencies.State("cn-training-iterations-input", "value"),
                dash.dependencies.State("cn-training-convergence-threshold-input", "value"),
                dash.dependencies.State("cn-patience-input", "value"),
                dash.dependencies.State("cn-multi-candidate-checkbox", "value"),
                dash.dependencies.State("cn-candidate-selection-radio", "value"),
                dash.dependencies.State("cn-top-candidates-input", "value"),
                dash.dependencies.State("cn-random-candidates-input", "value"),
                # Phase 6E A-1: output_epochs (per-output-pass epoch budget)
                dash.dependencies.State("nn-output-epochs-input", "value"),
                # Phase 6E A-2: optimizer_type (output-layer optimizer)
                dash.dependencies.State("nn-optimizer-type-dropdown", "value"),
                # Phase 6E A-3: activation_function_name (hidden-unit activation)
                dash.dependencies.State("nn-activation-function-dropdown", "value"),
            ],
            prevent_initial_call=True,
        )
        def apply_parameters(
            n_clicks,
            nn_max_iter,
            nn_max_epochs,
            nn_lr,
            nn_max_hu,
            nn_multi_node,
            nn_growth_trigger,
            nn_growth_epochs,
            nn_growth_conv_thresh,
            nn_patience,
            nn_spiral_rot,
            nn_spiral_num,
            nn_dataset_elem,
            nn_dataset_noise,
            cn_pool_size,
            cn_corr_thresh,
            cn_selected,
            cn_training_complete,
            cn_training_iter,
            cn_training_conv_thresh,
            cn_patience,
            cn_multi_cand,
            cn_cand_selection,
            cn_top_cands,
            cn_random_cands,
            nn_output_epochs,
            nn_optimizer_type,
            nn_activation_function,
        ):
            """Apply parameters to backend and update applied store."""
            return self._apply_parameters_handler(
                n_clicks,
                nn_max_iter,
                nn_max_epochs,
                nn_lr,
                nn_max_hu,
                nn_multi_node,
                nn_growth_trigger,
                nn_growth_epochs,
                nn_growth_conv_thresh,
                nn_patience,
                nn_spiral_rot,
                nn_spiral_num,
                nn_dataset_elem,
                nn_dataset_noise,
                cn_pool_size,
                cn_corr_thresh,
                cn_selected,
                cn_training_complete,
                cn_training_iter,
                cn_training_conv_thresh,
                cn_patience,
                cn_multi_cand,
                cn_cand_selection,
                cn_top_cands,
                cn_random_cands,
                nn_output_epochs,
                nn_optimizer_type,
                nn_activation_function,
            )

        # ── Initialize from backend on first load ──

        @self.app.callback(
            [
                # Neural Network (13)
                Output("nn-max-iterations-input", "value"),
                Output("nn-max-total-epochs-input", "value"),
                Output("nn-learning-rate-input", "value"),
                Output("nn-max-hidden-units-input", "value"),
                Output("nn-multi-node-layers-checkbox", "value"),
                Output("nn-growth-trigger-radio", "value"),
                Output("nn-growth-preset-epochs-input", "value"),
                Output("nn-growth-convergence-threshold-input", "value"),
                Output("nn-patience-input", "value"),
                Output("nn-spiral-rotations-input", "value"),
                Output("nn-spiral-number-input", "value"),
                Output("nn-dataset-elements-input", "value"),
                Output("nn-dataset-noise-input", "value"),
                # Candidate Nodes (10)
                Output("cn-pool-size-input", "value"),
                Output("cn-correlation-threshold-input", "value"),
                Output("cn-selected-candidates-input", "value"),
                Output("cn-training-complete-radio", "value"),
                Output("cn-training-iterations-input", "value"),
                Output("cn-training-convergence-threshold-input", "value"),
                Output("cn-patience-input", "value"),
                Output("cn-multi-candidate-checkbox", "value", allow_duplicate=True),
                Output("cn-candidate-selection-radio", "value"),
                Output("cn-top-candidates-input", "value"),
                Output("cn-random-candidates-input", "value"),
                # Phase 6E A-1: output_epochs (per-output-pass epoch budget)
                Output("nn-output-epochs-input", "value"),
                # Phase 6E A-2: optimizer_type (output-layer optimizer)
                Output("nn-optimizer-type-dropdown", "value"),
                # Phase 6E A-3: activation_function_name (hidden-unit activation)
                Output("nn-activation-function-dropdown", "value"),
                # Store
                Output("applied-params-store", "data", allow_duplicate=True),
            ],
            Input("params-init-interval", "n_intervals"),
            dash.dependencies.State("applied-params-store", "data"),
            prevent_initial_call=True,
        )
        def init_params_from_backend(n, current_applied):
            """Initialize input values and applied params from backend on first load."""
            return self._init_params_from_backend_handler(n, current_applied)

    # Define event handlers for callbacks
    def _toggle_dark_mode_handler(self, current_dark_mode=None):
        """Toggle dark mode on button click."""
        is_dark = not current_dark_mode
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
            # Single request: /api/status provides all needed info and doubles as health check.
            # Use fast timeout since this fires every tick.
            start_time = time.time()
            status_response = requests.get(self._api_url("/api/status"), timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS)
            latency_ms = (time.time() - start_time) * 1000

            if status_response.status_code == 200:
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
        max_hidden_units = status_data.get("max_hidden_units")

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
            f"{hidden_units} / {max_hidden_units}" if max_hidden_units else str(hidden_units),
        )

    def _update_network_info_handler(self, n=None):
        """Update network information panel from API."""
        try:
            url = self._api_url("/api/status")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Status API returned {response.status_code}")
                return html.Div("Unable to fetch network info", style={"color": "orange"})
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
                            html.Strong("Training Step: "),
                            str(status.get("current_epoch", 0)),
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Current Iteration: "),
                            str(status.get("hidden_units", 0)),
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
                + (
                    [
                        html.Hr(),
                        html.P([html.Strong("Dataset: "), str(status.get("dataset_name", ""))]),
                    ]
                    + ([html.P([html.Strong("Version: "), str(status["dataset_version"])])] if status.get("dataset_version") else [])
                    if status.get("dataset_name")
                    else []
                )
            )
        except Exception as e:
            self.logger.warning(f"Failed to fetch network info: {e}")
            return html.Div(
                [
                    html.P("Unable to fetch network info", style={"color": "orange"}),
                    html.P([html.Small(f"Error: {str(e)}")], style={"color": "gray"}),
                ]
            )

    def _update_network_info_details_handler(self, n=None):
        """Update detailed network information panel from API."""
        try:
            url = self._api_url("/api/network/stats")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Network stats API returned {response.status_code}")
                return html.Div("Unable to fetch network stats", style={"color": "orange"})
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

    def _update_metrics_store_handler(self, n=None, display_mode_state=None, ws_status=None):
        """Fetch metrics history from API and update metrics panel store.

        Phase B polling toggle: when WS bridge reports connected, skip REST poll
        to eliminate redundant traffic. Falls back to 1 Hz (every 10th tick at
        100ms fast interval) when WS is disconnected (D-05).

        GAP-WS-16: the gate now also requires ``metricsReceived`` so REST
        keeps polling during the brief window between socket-open and the
        first metrics frame (initial_metrics burst on fresh connect, or a
        live metrics broadcast on resume). Without this, a tab that
        connects while training is mid-stream sees an empty chart for one
        polling interval.
        """
        settings = get_settings()
        if settings.ws_bridge_enabled and ws_status and ws_status.get("connected") and ws_status.get("metricsReceived"):
            return dash.no_update

        try:
            mode_state = display_mode_state or {"mode": "window", "window_size": 100}
            mode = mode_state.get("mode", "window")
            if mode == "full" or mode == "hidden_units":
                limit = 0  # fetch all
            else:
                limit = mode_state.get("window_size", 100)
            url = self._api_url(f"/api/metrics/history?limit={limit}")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Metrics history API returned {response.status_code}")
                return []
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

            # Phase B: Track REST polling bandwidth (P0 motivator proof metric)
            if not hasattr(self, "_rest_bytes_gauge"):
                try:
                    from prometheus_client import REGISTRY, Gauge

                    metric_name = "canopy_rest_polling_bytes_per_sec"
                    try:
                        self._rest_bytes_gauge = Gauge(
                            metric_name,
                            "REST polling response size in bytes (per endpoint)",
                            ["endpoint"],
                        )
                    except ValueError:
                        # Already registered — adopt the existing
                        # collector. A second ``DashboardManager``
                        # instance in the same process (test fixture
                        # rebuilding the app, in-process re-init) would
                        # otherwise crash here on duplicate registration.
                        existing = REGISTRY._names_to_collectors.get(metric_name)
                        if existing is None:
                            raise
                        self._rest_bytes_gauge = existing
                except Exception:
                    self._rest_bytes_gauge = None
            if self._rest_bytes_gauge:
                try:
                    content_length = len(response.content) if hasattr(response, "content") else 0
                    self._rest_bytes_gauge.labels(endpoint="/api/metrics/history").set(content_length)
                except (TypeError, AttributeError):
                    pass

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
            if not response.ok:
                self.logger.warning(f"Topology API returned {response.status_code}")
                return dash.no_update
            result = response.json()
            # Unwrap success envelope: {"status": "success", "data": {...}}
            topology = result.get("data", result) if isinstance(result, dict) else result
            # Transform CasCor weight-oriented format to graph-oriented format
            # expected by NetworkVisualizer (input_units/output_units/connections)
            from backend.cascor_service_adapter import CascorServiceAdapter

            topology = CascorServiceAdapter._transform_topology(topology)
            self.logger.debug(f"Fetched topology from {url}: {len(topology.get('connections', []))} connections")
            return topology
        except Exception as e:
            self.logger.warning(f"Failed to fetch topology from API: {type(e).__name__}: {e}")
            return dash.no_update

    def _update_raw_topology_store_handler(self, n=None, active_tab=None, view_mode=None):
        """Fetch raw weight-oriented topology from API for heatmap view (OF-1)."""
        if active_tab != "topology" or view_mode != "weight_matrix":
            return dash.no_update

        try:
            url = self._api_url("/api/topology/raw")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Raw topology API returned {response.status_code}")
                return dash.no_update
            return response.json()
        except Exception as e:
            self.logger.warning(f"Failed to fetch raw topology from API: {type(e).__name__}: {e}")
            return dash.no_update

    def _update_dataset_store_handler(self, n=None, active_tab=None):
        """Fetch dataset from API and update dataset plotter store."""
        # Only update if dataset tab is active
        if active_tab != "dataset":
            return dash.no_update

        try:
            url = self._api_url("/api/dataset")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Dataset API returned {response.status_code}")
                return dash.no_update
            dataset = response.json()
            self.logger.debug(f"Fetched dataset from {url}: {dataset.get('num_samples', 0)} samples")
            return dataset
        except Exception as e:
            self.logger.warning(f"Failed to fetch dataset from API: {type(e).__name__}: {e}")
            return dash.no_update

    def _update_boundary_store_handler(self, n=None, active_tab=None, resolution=None):
        """Fetch decision boundary from API and update decision boundary store."""
        # Only update if boundaries tab is active
        if active_tab != "boundaries":
            return dash.no_update

        try:
            url = self._api_url("/api/decision_boundary")
            if resolution is not None:
                url = f"{url}?resolution={resolution}"
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Decision boundary API returned {response.status_code}")
                return dash.no_update
            boundary_data = response.json()
            self.logger.debug(f"Fetched decision boundary from {url}")
            return boundary_data
        except Exception as e:
            self.logger.warning(f"Failed to fetch decision boundary from API: {type(e).__name__}: {e}")
            return dash.no_update

    def _update_boundary_dataset_store_handler(self, n=None, active_tab=None):
        """Sync dataset data to decision boundary component."""
        # Only update if boundaries tab is active
        if active_tab != "boundaries":
            return dash.no_update

        try:
            url = self._api_url("/api/dataset")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if not response.ok:
                self.logger.warning(f"Boundary dataset API returned {response.status_code}")
                return dash.no_update
            return response.json()
        except Exception as e:
            self.logger.warning(f"Failed to fetch dataset for boundary from API: {type(e).__name__}: {e}")
            return dash.no_update

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
            response = requests.post(url, timeout=DashboardConstants.DASHBOARD_POST_TIMEOUT)
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
        """Re-enable buttons after the dashboard timeout based on their individual timestamps."""
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
                # Reset after the configured timeout threshold
                if elapsed > DashboardConstants.DASHBOARD_TIMEOUT_THRESHOLD:
                    new_states[cmd] = {"disabled": False, "loading": False, "timestamp": 0}
                    changed = True
                    self.logger.debug(f"Button {cmd} reset after {elapsed:.1f}s timeout")
                else:
                    new_states[cmd] = state
            else:
                new_states[cmd] = state

        return new_states if changed else dash.no_update

    def _toggle_nn_growth_inputs_handler(self, growth_trigger):
        """Enable/disable sub-inputs based on selected growth trigger."""
        if growth_trigger == "preset_epochs":
            return False, True
        return True, False

    def _toggle_cn_training_inputs_handler(self, training_complete):
        """Enable/disable sub-inputs based on pool training complete mode."""
        if training_complete == "preset_epochs":
            return False, True
        return True, False

    def _toggle_cn_selection_inputs_handler(self, selection_mode):
        """Enable/disable sub-inputs based on candidate selection mode."""
        if selection_mode == "top_tier":
            return False, True
        elif selection_mode == "random":
            return True, False
        return True, True

    def _toggle_cn_multi_candidate_subgroup_handler(self, value):
        """Enable/disable entire multi-candidate sub-group based on checkbox."""
        enabled = "enabled" in (value or [])
        if not enabled:
            return {"opacity": "0.5"}, True, True
        return {}, False, False

    def _sync_multi_node_checkboxes_handler(self, nn_value, cn_value):
        """Sync multi-node layers checkbox with multi-candidate selection checkbox."""
        ctx = dash.callback_context
        trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
        if trigger == "cn-multi-candidate-checkbox":
            cn_enabled = "enabled" in (cn_value or [])
            if cn_enabled:
                return ["enabled"], dash.no_update
            return dash.no_update, dash.no_update
        elif trigger == "nn-multi-node-layers-checkbox":
            return dash.no_update, dash.no_update
        return dash.no_update, dash.no_update

    def _track_param_changes_handler(
        self,
        nn_max_iter,
        nn_max_epochs,
        nn_lr,
        nn_max_hu,
        nn_multi_node,
        nn_growth_trigger,
        nn_growth_epochs,
        nn_growth_conv_thresh,
        nn_patience,
        nn_spiral_rot,
        nn_spiral_num,
        nn_dataset_elem,
        nn_dataset_noise,
        cn_pool_size,
        cn_corr_thresh,
        cn_selected,
        cn_training_complete,
        cn_training_iter,
        cn_training_conv_thresh,
        cn_patience,
        cn_multi_cand,
        cn_cand_selection,
        cn_top_cands,
        cn_random_cands,
        nn_output_epochs=None,
        nn_optimizer_type=None,
        nn_activation_function=None,
        applied=None,
    ):
        """Enable Apply button when parameters differ from applied values."""
        if not applied:
            return True, ""

        def float_equal(a, b, tol=1e-9):
            if a is None or b is None:
                return a == b
            try:
                return abs(float(a) - float(b)) < tol
            except (TypeError, ValueError):
                return False

        def checkbox_to_bool(checklist_value):
            return "enabled" in (checklist_value or [])

        comparisons = [
            (nn_max_iter, "nn_max_iterations", "int"),
            (nn_max_epochs, "nn_max_total_epochs", "int"),
            (nn_lr, "nn_learning_rate", "float"),
            (nn_max_hu, "nn_max_hidden_units", "int"),
            (nn_multi_node, "nn_multi_node_layers", "bool_checkbox"),
            (nn_growth_trigger, "nn_growth_trigger", "str"),
            (nn_growth_epochs, "nn_growth_preset_epochs", "int"),
            (nn_growth_conv_thresh, "nn_growth_convergence_threshold", "float"),
            (nn_patience, "nn_patience", "int"),
            (nn_spiral_rot, "nn_spiral_rotations", "float"),
            (nn_spiral_num, "nn_spiral_number", "int"),
            (nn_dataset_elem, "nn_dataset_elements", "int"),
            (nn_dataset_noise, "nn_dataset_noise", "float"),
            (cn_pool_size, "cn_pool_size", "int"),
            (cn_corr_thresh, "cn_correlation_threshold", "float"),
            (cn_selected, "cn_selected_candidates", "int"),
            (cn_training_complete, "cn_training_complete", "str"),
            (cn_training_iter, "cn_training_iterations", "int"),
            (cn_training_conv_thresh, "cn_training_convergence_threshold", "float"),
            (cn_patience, "cn_patience", "int"),
            (cn_multi_cand, "cn_multi_candidate", "bool_checkbox"),
            (cn_cand_selection, "cn_candidate_selection", "str"),
            (cn_top_cands, "cn_top_candidates", "int"),
            (cn_random_cands, "cn_random_candidates", "int"),
            (nn_output_epochs, "nn_output_epochs", "int"),
            (nn_optimizer_type, "nn_optimizer_type", "str"),
            (nn_activation_function, "nn_activation_function_name", "str"),
        ]

        has_changes = False
        for current, key, cmp_type in comparisons:
            stored = applied.get(key)
            if cmp_type == "float":
                if not float_equal(current, stored):
                    has_changes = True
                    break
            elif cmp_type == "bool_checkbox":
                if checkbox_to_bool(current) != stored:
                    has_changes = True
                    break
            elif cmp_type in ("int", "str") and current != stored:
                has_changes = True
                break

        if has_changes:
            return False, "⚠️ Unsaved changes"
        return True, dash.no_update

    def _apply_parameters_handler(
        self,
        n_clicks,
        nn_max_iter,
        nn_max_epochs,
        nn_lr,
        nn_max_hu,
        nn_multi_node,
        nn_growth_trigger,
        nn_growth_epochs,
        nn_growth_conv_thresh,
        nn_patience,
        nn_spiral_rot,
        nn_spiral_num,
        nn_dataset_elem,
        nn_dataset_noise,
        cn_pool_size,
        cn_corr_thresh,
        cn_selected,
        cn_training_complete,
        cn_training_iter,
        cn_training_conv_thresh,
        cn_patience,
        cn_multi_cand,
        cn_cand_selection,
        cn_top_cands,
        cn_random_cands,
        nn_output_epochs=None,
        nn_optimizer_type=None,
        nn_activation_function=None,
    ):
        """Apply parameters to backend and update applied store."""
        if not n_clicks:
            return dash.no_update, dash.no_update

        def checkbox_to_bool(v):
            return "enabled" in (v or [])

        params = {
            "nn_max_iterations": int(nn_max_iter) if nn_max_iter is not None else TrainingConstants.DEFAULT_MAX_GROWTH_ITERATIONS,
            "nn_max_total_epochs": int(nn_max_epochs) if nn_max_epochs is not None else TrainingConstants.DEFAULT_TRAINING_EPOCHS,
            "nn_learning_rate": float(nn_lr) if nn_lr is not None else TrainingConstants.DEFAULT_LEARNING_RATE,
            "nn_max_hidden_units": int(nn_max_hu) if nn_max_hu is not None else TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS,
            "nn_multi_node_layers": checkbox_to_bool(nn_multi_node),
            "nn_growth_trigger": nn_growth_trigger or TrainingConstants.DEFAULT_GROWTH_TRIGGER,
            "nn_growth_preset_epochs": int(nn_growth_epochs) if nn_growth_epochs is not None else TrainingConstants.DEFAULT_PRESET_EPOCHS,
            "nn_growth_convergence_threshold": float(nn_growth_conv_thresh) if nn_growth_conv_thresh is not None else TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD,
            "nn_patience": int(nn_patience) if nn_patience is not None else TrainingConstants.DEFAULT_PATIENCE,
            "nn_spiral_rotations": float(nn_spiral_rot) if nn_spiral_rot is not None else TrainingConstants.DEFAULT_SPIRAL_ROTATIONS,
            "nn_spiral_number": int(nn_spiral_num) if nn_spiral_num is not None else TrainingConstants.DEFAULT_SPIRAL_NUMBER,
            "nn_dataset_elements": int(nn_dataset_elem) if nn_dataset_elem is not None else TrainingConstants.DEFAULT_DATASET_ELEMENTS,
            "nn_dataset_noise": float(nn_dataset_noise) if nn_dataset_noise is not None else TrainingConstants.DEFAULT_DATASET_NOISE,
            "cn_pool_size": int(cn_pool_size) if cn_pool_size is not None else TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE,
            "cn_correlation_threshold": float(cn_corr_thresh) if cn_corr_thresh is not None else TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD,
            "cn_selected_candidates": int(cn_selected) if cn_selected is not None else TrainingConstants.DEFAULT_SELECTED_CANDIDATES,
            "cn_training_complete": cn_training_complete or TrainingConstants.DEFAULT_CN_TRAINING_COMPLETE,
            "cn_training_iterations": int(cn_training_iter) if cn_training_iter is not None else TrainingConstants.DEFAULT_CANDIDATE_TRAINING_ITERATIONS,
            "cn_training_convergence_threshold": float(cn_training_conv_thresh) if cn_training_conv_thresh is not None else TrainingConstants.DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD,
            "cn_patience": int(cn_patience) if cn_patience is not None else TrainingConstants.DEFAULT_CN_PATIENCE,
            "cn_multi_candidate": checkbox_to_bool(cn_multi_cand),
            "cn_candidate_selection": cn_cand_selection,
            "cn_top_candidates": int(cn_top_cands) if cn_top_cands is not None else TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT,
            "cn_random_candidates": int(cn_random_cands) if cn_random_cands is not None else TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT,
            "nn_output_epochs": int(nn_output_epochs) if nn_output_epochs is not None else TrainingConstants.DEFAULT_OUTPUT_EPOCHS,
            "nn_optimizer_type": nn_optimizer_type or TrainingConstants.DEFAULT_OPTIMIZER_TYPE,
            "nn_activation_function_name": nn_activation_function or TrainingConstants.DEFAULT_ACTIVATION_FUNCTION,
        }

        max_retries = DashboardConstants.DASHBOARD_SET_PARAMS_MAX_RETRIES
        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(self._api_url("/api/set_params"), json=params, timeout=DashboardConstants.DASHBOARD_LONG_POST_TIMEOUT)
                if response.status_code == 200:
                    # Verify parameters were applied by reading back state
                    try:
                        verify_resp = requests.get(self._api_url("/api/state"), timeout=DashboardConstants.DASHBOARD_GET_TIMEOUT)
                        if verify_resp.status_code == 200:
                            backend_state = verify_resp.json()
                            mismatched = []
                            for key, value in params.items():
                                backend_val = backend_state.get(key)
                                if backend_val is not None and str(backend_val) != str(value):
                                    mismatched.append(key)
                            if mismatched:
                                self.logger.warning(f"Parameter verification: {len(mismatched)} params not confirmed: {mismatched}")
                    except Exception as ve:
                        self.logger.debug(f"Parameter verification skipped: {ve}")
                    self.logger.info(f"Parameters applied (attempt {attempt + 1}): {params}")
                    return params, "Parameters applied"
                elif response.status_code == 429:
                    self.logger.warning("Rate limited (429) — returning error to client")
                    return dash.no_update, "Rate limited — please try again in a few seconds"
                else:
                    self.logger.warning(f"Failed to apply: {response.status_code} {response.text}")
                    return dash.no_update, f"Failed to apply ({response.status_code})"
            except requests.exceptions.Timeout:
                last_error = "Request timed out"
                self.logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
                continue
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Apply failed on attempt {attempt + 1}: {e}")
                continue
        self.logger.error(f"All {max_retries} parameter apply attempts failed: {last_error}")
        return dash.no_update, f"Error: {str(last_error)[:40]}"

    def _init_params_from_backend_handler(self, n, current_applied):
        """Initialize input values and applied params from backend on first load."""
        NUM_OUTPUTS = 28
        if current_applied:
            return (dash.no_update,) * NUM_OUTPUTS
        try:
            response = requests.get(self._api_url("/api/state"), timeout=DashboardConstants.API_TIMEOUT_SECONDS)
            if response.status_code == 200:
                state = response.json()
                nn_max_iter = state.get("nn_max_iterations", TrainingConstants.DEFAULT_MAX_GROWTH_ITERATIONS)
                nn_max_epochs = state.get("nn_max_total_epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS)
                nn_lr = state.get("nn_learning_rate", TrainingConstants.DEFAULT_LEARNING_RATE)
                nn_max_hu = state.get("nn_max_hidden_units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS)
                nn_multi_node = state.get("nn_multi_node_layers", TrainingConstants.DEFAULT_MULTI_NODE_LAYERS)
                nn_growth_trigger = state.get("nn_growth_trigger", TrainingConstants.DEFAULT_GROWTH_TRIGGER)
                nn_growth_epochs = state.get("nn_growth_preset_epochs", TrainingConstants.DEFAULT_PRESET_EPOCHS)
                nn_growth_conv_thresh = state.get("nn_growth_convergence_threshold", TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD)
                nn_patience = state.get("nn_patience", TrainingConstants.DEFAULT_PATIENCE)
                nn_spiral_rot = state.get("nn_spiral_rotations", TrainingConstants.DEFAULT_SPIRAL_ROTATIONS)
                nn_spiral_num = state.get("nn_spiral_number", TrainingConstants.DEFAULT_SPIRAL_NUMBER)
                nn_dataset_elem = state.get("nn_dataset_elements", TrainingConstants.DEFAULT_DATASET_ELEMENTS)
                nn_dataset_noise = state.get("nn_dataset_noise", TrainingConstants.DEFAULT_DATASET_NOISE)
                cn_pool_size = state.get("cn_pool_size", TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE)
                cn_corr_thresh = state.get("cn_correlation_threshold", TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD)
                cn_selected = state.get("cn_selected_candidates", TrainingConstants.DEFAULT_SELECTED_CANDIDATES)
                cn_training_complete = state.get("cn_training_complete", TrainingConstants.DEFAULT_CN_TRAINING_COMPLETE)
                cn_training_iter = state.get("cn_training_iterations", TrainingConstants.DEFAULT_CANDIDATE_TRAINING_ITERATIONS)
                cn_training_conv_thresh = state.get("cn_training_convergence_threshold", TrainingConstants.DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD)
                cn_patience = state.get("cn_patience", TrainingConstants.DEFAULT_CN_PATIENCE)
                cn_multi_cand = state.get("cn_multi_candidate", TrainingConstants.DEFAULT_MULTI_CANDIDATE_ENABLED)
                cn_cand_selection = state.get("cn_candidate_selection")
                cn_top_cands = state.get("cn_top_candidates", TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT)
                cn_random_cands = state.get("cn_random_candidates", TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT)
                nn_output_epochs = state.get("nn_output_epochs", TrainingConstants.DEFAULT_OUTPUT_EPOCHS)
                nn_optimizer_type = state.get("nn_optimizer_type", TrainingConstants.DEFAULT_OPTIMIZER_TYPE)
                nn_activation_function = state.get("nn_activation_function_name", TrainingConstants.DEFAULT_ACTIVATION_FUNCTION)

                applied = {
                    "nn_max_iterations": nn_max_iter,
                    "nn_max_total_epochs": nn_max_epochs,
                    "nn_learning_rate": nn_lr,
                    "nn_max_hidden_units": nn_max_hu,
                    "nn_multi_node_layers": nn_multi_node,
                    "nn_growth_trigger": nn_growth_trigger,
                    "nn_growth_preset_epochs": nn_growth_epochs,
                    "nn_growth_convergence_threshold": nn_growth_conv_thresh,
                    "nn_patience": nn_patience,
                    "nn_spiral_rotations": nn_spiral_rot,
                    "nn_spiral_number": nn_spiral_num,
                    "nn_dataset_elements": nn_dataset_elem,
                    "nn_dataset_noise": nn_dataset_noise,
                    "cn_pool_size": cn_pool_size,
                    "cn_correlation_threshold": cn_corr_thresh,
                    "cn_selected_candidates": cn_selected,
                    "cn_training_complete": cn_training_complete,
                    "cn_training_iterations": cn_training_iter,
                    "cn_training_convergence_threshold": cn_training_conv_thresh,
                    "cn_patience": cn_patience,
                    "cn_multi_candidate": cn_multi_cand,
                    "cn_candidate_selection": cn_cand_selection,
                    "cn_top_candidates": cn_top_cands,
                    "cn_random_candidates": cn_random_cands,
                    "nn_output_epochs": nn_output_epochs,
                    "nn_optimizer_type": nn_optimizer_type,
                    "nn_activation_function_name": nn_activation_function,
                }
                return (
                    nn_max_iter,
                    nn_max_epochs,
                    nn_lr,
                    nn_max_hu,
                    ["enabled"] if nn_multi_node else [],
                    nn_growth_trigger,
                    nn_growth_epochs,
                    nn_growth_conv_thresh,
                    nn_patience,
                    nn_spiral_rot,
                    nn_spiral_num,
                    nn_dataset_elem,
                    nn_dataset_noise,
                    cn_pool_size,
                    cn_corr_thresh,
                    cn_selected,
                    cn_training_complete,
                    cn_training_iter,
                    cn_training_conv_thresh,
                    cn_patience,
                    ["enabled"] if cn_multi_cand else [],
                    cn_cand_selection,
                    cn_top_cands,
                    cn_random_cands,
                    nn_output_epochs,
                    nn_optimizer_type,
                    nn_activation_function,
                    applied,
                )
        except Exception as e:
            self.logger.warning(f"Failed to initialize params from backend: {e}")
        return (dash.no_update,) * NUM_OUTPUTS

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
