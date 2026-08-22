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

from canopy_constants import CascorPatchBounds, DashboardConstants, TrainingConstants
from dataset_schema import apply_availability_gate, generator_name_for_type, is_generator_available, parse_schema_fields, unavailable_reason
from frontend.internal_api import internal_api_headers
from model_registry import DEFAULT_DATASET_TYPE, DEFAULT_MODEL_KEY, MODELS, dataset_default_params, dataset_model_hint, gated_dataset_options, get_dataset_spec, get_model_spec, model_is_trainable, model_matches_search, model_reason
from settings import get_settings

from . import ui_standards
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
function(start_clicks, pause_clicks, stop_clicks, resume_clicks, reset_clicks, last_click, button_states, oneshot_start_body) {
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

    // Phase D §S10: push the *real* async outcome into the training-control-
    // action store so the surface_training_control_outcome callback can render a
    // dismissable danger alert. Without this a rejected command (WS error ack or
    // REST non-2xx) only ever reached the browser console — the "dead button"
    // class. See notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md.
    function reportFailure(detail) {
        try {
            if (dc && typeof dc.set_props === 'function') {
                dc.set_props('training-control-action', {
                    data: { last: triggerId, ts: Date.now() / 1000.0, success: false, command: command, detail: String(detail || '').slice(0, 300) }
                });
            }
        } catch (e) {
            console.error('[Phase D] reportFailure failed for ' + command + ':', e);
        }
    }

    function restFallback(reason) {
        if (reason) {
            console.warn('[Phase D] REST fallback (' + command + '):', reason);
        }
        try {
            // A1-iv-3c: a one-shot Start carries the dataset-ref body (generator + registry
            // params); every other command and a live-model Start post no body (route unchanged).
            var fetchOpts = { method: 'POST', credentials: 'same-origin' };
            if (command === 'start' && oneshot_start_body) {
                fetchOpts.headers = { 'Content-Type': 'application/json' };
                fetchOpts.body = JSON.stringify(oneshot_start_body);
            }
            // PR-1 (Start-Training 401 fix): attach the CSRF token (bootstrapped
            // and cached by websocket_client.js on page load) so the keyless REST
            // fallback satisfies require_browser_control_auth on the server. The
            // session cookie already rides on credentials:'same-origin'. Skipped
            // when no token is set (CSRF disabled -> server falls back to Origin-only).
            if (window.__canopy_csrf) {
                fetchOpts.headers = Object.assign({}, fetchOpts.headers || {}, { 'X-CSRF-Token': window.__canopy_csrf });
            }
            fetch('/api/train/' + command, fetchOpts)
                .then(function(resp) {
                    if (!resp.ok) {
                        console.warn('[Phase D] REST /api/train/' + command + ' returned ' + resp.status);
                        resp.text().then(function(body) {
                            var msg = '';
                            try {
                                var parsed = JSON.parse(body);
                                msg = (parsed && parsed.error && (parsed.error.message || parsed.error.detail)) || (parsed && (parsed.message || parsed.detail)) || '';
                            } catch (e) {
                                msg = body || '';
                            }
                            reportFailure('HTTP ' + resp.status + (msg ? ': ' + msg : ''));
                        }).catch(function() {
                            reportFailure('HTTP ' + resp.status);
                        });
                    }
                })
                .catch(function(err) {
                    console.error('[Phase D] REST /api/train/' + command + ' failed:', err);
                    reportFailure((err && err.message) || 'request failed');
                });
        } catch (err) {
            console.error('[Phase D] REST fallback threw for ' + command + ':', err);
            reportFailure((err && err.message) || 'request error');
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
            // A1-iv-3c: attach the one-shot dataset-ref body as the WS ``params`` (the /ws/control
            // start handler feeds it to _recurrence_start_kwargs); a live-model Start sends none.
            var sendMsg = { command: command, command_id: commandId };
            if (command === 'start' && oneshot_start_body) {
                sendMsg.params = oneshot_start_body;
            }
            var sendPromise = ws.send(sendMsg);
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


# A1-iii-b1: viz tabs that are cascade-network-specific and meaningless for a one-shot
# (recurrence / LMU) model — hidden when the active model's execution is "one_shot".
_CASCADE_ONLY_TAB_IDS = frozenset({"candidates", "topology", "evolution", "boundaries", "workers"})


# N3b (canopy training-runtime defects plan, I-6 / Q3): the restart confirm modal's
# expandable granular section allows in-place MODIFICATION of what the restart will do
# (N3 shipped it read-only VERIFY). These tuples are the single source of truth wiring
# each modal field id to its logical key + display label, shared by the layout builders,
# the open/summary/execute handlers, and the tests — so the field set cannot drift.
#
# Dataset = exactly the fields ``StageDatasetRequest`` carries (an edit re-stages via the
# existing ``/api/stage_dataset`` route). Params = a focused, restart-relevant subset of
# the training meta-params, every one governed by N5's ``CascorPatchBounds`` so the same
# clamp → apply → applied/skipped machinery handles them (no duplicated bounds/toast
# logic). (field_id, key, label).
# F-CANOPY-017: distinguishes "caller omitted this optional kwarg" from "the
# widget delivered None". Only the latter is an invalid-input signal; see
# ``_apply_parameters_handler``.
_UNSET = object()

RESTART_MODAL_DATASET_FIELDS = (
    ("restart-ds-type", "dataset_type", "Dataset type"),
    ("restart-ds-samples", "n_samples", "Samples"),
    ("restart-ds-noise", "noise", "Noise"),
    ("restart-ds-rotations", "rotations", "Spiral rotations"),
    ("restart-ds-spirals", "n_spirals", "Spirals"),
)
RESTART_MODAL_PARAM_FIELDS = (
    ("restart-p-nn-learning-rate", "nn_learning_rate", "Learning rate"),
    ("restart-p-nn-max-hidden-units", "nn_max_hidden_units", "Max hidden units"),
    ("restart-p-nn-patience", "nn_patience", "Patience"),
    ("restart-p-cn-pool-size", "cn_pool_size", "Candidate pool size"),
    ("restart-p-cn-selected", "cn_selected_candidates", "Selected candidates"),
    ("restart-p-cn-corr-thresh", "cn_correlation_threshold", "Correlation threshold"),
)


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
                # Phase 2 P2-4 (Issue #3): Experimental Functions gate state.
                # The Switch in the sidebar (Network Information section)
                # writes here via callback; downstream P2-5 reads here to
                # decide whether to render the Live Dataset Switch button.
                # Reconciled to cascor's authoritative state on page load
                # and on every Switch change (F2.10). Persisted to
                # localStorage so the toggle survives page reloads — but
                # the on-load reconciliation overrides stale persistence
                # if cascor's gate is currently closed.
                dcc.Store(
                    id="experimental-flags-store",
                    storage_type="local",
                    data={"experimental_functions": False},
                ),
                # Phase 2 P2-5 (Issue #3): training status mirror store.
                # The existing /api/status poller writes its response here
                # each fast-update-interval tick so gate callbacks (Live
                # Dataset Switch enable/disable + future P2-7 timeline)
                # subscribe to a single source instead of each hitting
                # the REST endpoint themselves. ``memory`` storage —
                # rebuilt on every page reload from /api/status.
                dcc.Store(
                    id="training-status-store",
                    storage_type="memory",
                    data={"is_running": False, "phase": "idle"},
                ),
                # Phase 2 P2-5 (Issue #3): live-swap in-flight tracker.
                # ``in_flight=True`` while the POST /api/live_dataset_swap
                # is awaiting cascor's response (5–30 s for real fetches).
                # Drives the progress-alert visibility + Cancel-button
                # enable state. ``memory`` storage — a page reload during
                # an in-flight swap clears this client-side view, but
                # cascor's swap continues server-side (the user can fetch
                # the result via /api/history/dataset_swaps once the
                # post-swap event records).
                dcc.Store(
                    id="live-swap-in-flight-store",
                    storage_type="memory",
                    data={"in_flight": False},
                ),
                # Phase 2 P2-7 (Issue #3): dataset_swap event feed for
                # the three P2-7 panels (replay timeline marker, History
                # paired-diff, Snapshots tab badges). Populated each
                # slow-update-interval tick from /api/history/dataset_swaps
                # (proxies cascor follow-up B). Shared across panels so
                # they all render against a single source of truth.
                # ``memory`` storage — rebuilt from the route on each
                # page load.
                dcc.Store(
                    id="dataset-swap-events-store",
                    storage_type="memory",
                    data={"events": []},
                ),
                # P2-7 follow-up (Issue #3): per-snapshot swap history,
                # hydrated when the active replay session loads a
                # snapshot. Separate from the live store above so the
                # ReplayPlayerPanel can render two trace groups (live
                # markers AND snapshot-history markers) without one
                # source clobbering the other. Cleared when no snapshot
                # is loaded.
                dcc.Store(
                    id="loaded-snapshot-swap-events-store",
                    storage_type="memory",
                    data={"events": [], "snapshot_id": None},
                ),
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
                                                                    style={"color": "var(--text-muted)"},
                                                                ),
                                                                html.Span(
                                                                    id="top-status-display",
                                                                    children="Stopped",
                                                                    style={"fontWeight": "bold", "color": "var(--text-muted)"},
                                                                ),
                                                            ],
                                                            style={"marginRight": "8px"},
                                                        ),
                                                        html.Span(
                                                            " | ",
                                                            style={"color": "var(--text-muted)", "marginRight": "8px"},
                                                        ),
                                                        # Phase with label
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Phase: ",
                                                                    style={"color": "var(--text-muted)"},
                                                                ),
                                                                html.Span(
                                                                    id="top-phase-display",
                                                                    children="Idle",
                                                                    style={"fontWeight": "bold", "color": "var(--text-muted)"},
                                                                ),
                                                            ],
                                                            style={"marginRight": "8px"},
                                                        ),
                                                        html.Span(
                                                            " | ",
                                                            style={"color": "var(--text-muted)", "marginRight": "8px"},
                                                        ),
                                                        # Step display — completed training steps
                                                        # (``current_epoch``); NOT an inner output epoch.
                                                        # N6/C2b: relabelled from "Epoch" to "Step" to
                                                        # match the C2b counter contract (the S12
                                                        # "Epoch: 10000 vs 12" confusion).
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Step: ",
                                                                    style={"color": "var(--text-muted)"},
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
                                                            style={"color": "var(--text-muted)", "marginRight": "8px"},
                                                        ),
                                                        # Hidden Units display — installed cascade units
                                                        # vs the reconciled ``max_hidden_units`` cap.
                                                        # N6/C2b: relabelled from "Iteration" to "Hidden
                                                        # Units"; this segment (id ``top-hidden-units-display``)
                                                        # always showed the unit count — only the label was
                                                        # wrong (S12's "Iteration: 0 / 10000"). The true
                                                        # growth "Iteration" (grow_iteration/grow_max) lives
                                                        # in the Network Info panel.
                                                        html.Span(
                                                            [
                                                                html.Span(
                                                                    "Hidden Units: ",
                                                                    style={"color": "var(--text-muted)"},
                                                                ),
                                                                html.Span(
                                                                    id="top-hidden-units-display",
                                                                    children="0",
                                                                    style={"fontWeight": "bold", "color": "#17a2b8"},
                                                                ),
                                                            ],
                                                            # A1-iii-b1: id so a one_shot (recurrence) model can hide
                                                            # this cascade-only hidden-units segment. The id keeps its
                                                            # historical name (``status-iteration-segment``) so the
                                                            # ``toggle_iteration_segment`` callback wiring is stable.
                                                            id="status-iteration-segment",
                                                            style={"marginRight": "20px"},
                                                        ),
                                                        # Latency display (right side)
                                                        html.Span(
                                                            id="latency-display",
                                                            children="",
                                                            style={
                                                                "marginLeft": "auto",
                                                                "color": "var(--text-muted)",
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
                                                # A1-iv-5 / D8 (§5.7): when a non-live model is selected it is shown +
                                                # selectable but NOT trainable — this status reason explains why Start is
                                                # disabled (filled by ``annotate_train_gate``). Empty/hidden for a live model.
                                                html.Div(id="train-gate-notice", className="mb-2"),
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
                                                                                step=1,
                                                                                min=TrainingConstants.MIN_MAX_GROWTH_ITERATIONS,
                                                                                max=TrainingConstants.MAX_MAX_GROWTH_ITERATIONS,
                                                                                className="mb-2",
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                                                            ),
                                                                            html.P("Maximum Total Epochs:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="nn-max-total-epochs-input",
                                                                                type="number",
                                                                                value=self.training_defaults.get("epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS),
                                                                                step=1,
                                                                                min=self._settings.get_training_param_config("epochs")["min"],
                                                                                max=self._settings.get_training_param_config("epochs")["max"],
                                                                                className="mb-2",
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                step="any",
                                                                                min=self._settings.get_training_param_config("learning_rate")["min"],
                                                                                max=self._settings.get_training_param_config("learning_rate")["max"],
                                                                                className="mb-2",
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                    step=1,
                                                                                                    min=TrainingConstants.MIN_PRESET_EPOCHS,
                                                                                                    max=TrainingConstants.MAX_PRESET_EPOCHS,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                    step="any",
                                                                                                    min=TrainingConstants.MIN_CONVERGENCE_THRESHOLD,
                                                                                                    max=TrainingConstants.MAX_CONVERGENCE_THRESHOLD,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                    # ── Model (A1b-1: dedicated selection surface) ──
                                                                    # The sidebar dropdown is replaced by a compact summary + a "▸ change"
                                                                    # button that opens the dedicated model-selection modal (D7/§5.1). The
                                                                    # full, gated model table lives there; the sidebar stays width-pinned and
                                                                    # carries no scale pressure as the model population grows.
                                                                    html.Div(
                                                                        [
                                                                            html.Hr(),
                                                                            html.P("Model:", className="mb-1 fw-bold mt-1"),
                                                                            html.Div(
                                                                                [
                                                                                    # ``nn-model-summary`` is KEPT (the select callback writes it);
                                                                                    # seeded with the default model so it reads honestly at first paint
                                                                                    # now that the dropdown no longer shows the current value.
                                                                                    html.Span(
                                                                                        self._initial_model_summary(),
                                                                                        id="nn-model-summary",
                                                                                        className="small text-muted",
                                                                                    ),
                                                                                    dbc.Button(
                                                                                        "▸ change",
                                                                                        id="nn-model-change-button",
                                                                                        color="link",
                                                                                        size="sm",
                                                                                        className="p-0 ms-2 align-baseline text-decoration-none",
                                                                                    ),
                                                                                ],
                                                                                className="ms-3 mb-2 d-flex align-items-baseline",
                                                                            ),
                                                                            # A1b-2 (§5.3): the reverse-gate annotation — names the model
                                                                            # constraint the CURRENT dataset imposes ("3-D models only"),
                                                                            # the dataset-side mirror of the table's per-row greying. Seeded
                                                                            # for the default dataset; updated by the dataset→hint callback.
                                                                            html.Div(
                                                                                self._initial_dataset_model_hint(),
                                                                                id="nn-model-dataset-hint",
                                                                                className="ms-3 mb-2 small text-muted fst-italic",
                                                                            ),
                                                                        ],
                                                                        id="sidebar-nn-model",
                                                                    ),
                                                                    # ── Spiral Dataset ──
                                                                    html.Div(
                                                                        [
                                                                            html.Hr(),
                                                                            html.H6(
                                                                                [
                                                                                    html.Span("▼", id="ctx-spiral-dataset-icon", className="collapse-icon"),
                                                                                    # N7 (U-6): the section title is renamed per selected dataset type
                                                                                    # (e.g. "Current Dataset — MNIST") by ``render_dataset_params`` so the
                                                                                    # left menu reflects the actually-selected type, not a fixed Spiral view.
                                                                                    html.Span(self._initial_dataset_section_title(), id="nn-dataset-section-title"),
                                                                                ],
                                                                                id="ctx-spiral-dataset-header",
                                                                                className="collapsible-header",
                                                                            ),
                                                                            dbc.Collapse(
                                                                                html.Div(
                                                                                    [
                                                                                        # N7 (I-7): the four spiral-form typed inputs render only for the
                                                                                        # spiral generator; ``render_dataset_params`` hides this block for
                                                                                        # other types, which render schema-driven fields into
                                                                                        # ``nn-dataset-schema-params`` and forward them via the generic
                                                                                        # ``params`` staging channel (not these typed fields).
                                                                                        html.Div(
                                                                                            [
                                                                                                html.P("Spiral:", className="mb-1 fw-bold mt-1"),
                                                                                                html.P("Rotations:", className="mb-1 ms-3"),
                                                                                                dbc.Input(
                                                                                                    id="nn-spiral-rotations-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_SPIRAL_ROTATIONS,
                                                                                                    step="any",
                                                                                                    min=TrainingConstants.MIN_SPIRAL_ROTATIONS,
                                                                                                    max=TrainingConstants.MAX_SPIRAL_ROTATIONS,
                                                                                                    className="mb-2 ms-3",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                                                                                    style={"width": "calc(100% - 1rem)"},
                                                                                                ),
                                                                                                html.P("Dataset:", className="mb-1 fw-bold mt-2"),
                                                                                                html.P("Elements:", className="mb-1 ms-3"),
                                                                                                dbc.Input(
                                                                                                    id="nn-dataset-elements-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_DATASET_ELEMENTS,
                                                                                                    step=1,
                                                                                                    min=TrainingConstants.MIN_DATASET_ELEMENTS,
                                                                                                    max=TrainingConstants.MAX_DATASET_ELEMENTS,
                                                                                                    className="mb-2 ms-3",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                                                                                    style={"width": "calc(100% - 1rem)"},
                                                                                                ),
                                                                                                html.P("Noise:", className="mb-1 ms-3"),
                                                                                                dbc.Input(
                                                                                                    id="nn-dataset-noise-input",
                                                                                                    type="number",
                                                                                                    value=TrainingConstants.DEFAULT_DATASET_NOISE,
                                                                                                    step="any",
                                                                                                    min=TrainingConstants.MIN_DATASET_NOISE,
                                                                                                    max=TrainingConstants.MAX_DATASET_NOISE,
                                                                                                    className="mb-2 ms-3",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                                                                                    style={"width": "calc(100% - 1rem)"},
                                                                                                ),
                                                                                            ],
                                                                                            id="nn-dataset-typed-fields",
                                                                                        ),
                                                                                        # FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.1
                                                                                        # Issue #3 Phase 1 — dataset_type selector
                                                                                        # routed through the new POST /v1/training/dataset
                                                                                        # endpoint (cascor #242). Apply Dataset stages
                                                                                        # the change; restart applies it (cold-swap).
                                                                                        html.P("Type:", className="mb-1 ms-3"),
                                                                                        dcc.Dropdown(
                                                                                            id="nn-dataset-type-dropdown",
                                                                                            options=gated_dataset_options(DEFAULT_MODEL_KEY),
                                                                                            value=DEFAULT_DATASET_TYPE,
                                                                                            clearable=False,
                                                                                            className="mb-2 ms-3",
                                                                                            style={"width": "calc(100% - 1rem)"},
                                                                                        ),
                                                                                        # N7 (I-7 / U-6): schema-driven parameter inputs for the selected
                                                                                        # non-spiral generator, rebuilt by ``render_dataset_params`` from the
                                                                                        # generator's JSON schema (labels/bounds/defaults). Each input carries a
                                                                                        # pattern-matching id ``{"type": "nn-gen-param", "name": <field>}`` and is
                                                                                        # read directly by ``apply_dataset`` into the generic ``params`` channel.
                                                                                        html.Div(id="nn-dataset-schema-params", className="ms-3"),
                                                                                        dbc.Button(
                                                                                            "Apply Dataset",
                                                                                            id="apply-dataset-button",
                                                                                            color="secondary",
                                                                                            outline=True,
                                                                                            size="sm",
                                                                                            className="mb-2 ms-3",
                                                                                            style={"width": "calc(100% - 1rem)"},
                                                                                        ),
                                                                                        # Phase 2 P2-5 (Issue #3): Live Dataset Switch
                                                                                        # button. Sibling of Apply Dataset — same form,
                                                                                        # two destinations (cold swap vs live swap).
                                                                                        # Spec §4.2: ``color="warning"``, default
                                                                                        # ``disabled=True`` (F2.3); gated by the
                                                                                        # experimental-flags-store + training-status-store
                                                                                        # combination (see
                                                                                        # _setup_live_dataset_switch_callbacks below).
                                                                                        dbc.Button(
                                                                                            "Live Dataset Switch",
                                                                                            id="live-dataset-switch-button",
                                                                                            color="warning",
                                                                                            outline=True,
                                                                                            size="sm",
                                                                                            disabled=True,
                                                                                            className="mb-2 ms-3",
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
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                                                            ),
                                                                            html.P("Correlation Threshold:", className="mb-1 fw-bold"),
                                                                            dbc.Input(
                                                                                id="cn-correlation-threshold-input",
                                                                                type="number",
                                                                                value=TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD,
                                                                                step="any",
                                                                                min=TrainingConstants.MIN_CANDIDATE_CORRELATION_THRESHOLD,
                                                                                max=TrainingConstants.MAX_CANDIDATE_CORRELATION_THRESHOLD,
                                                                                className="mb-2",
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                                                            ),
                                                                            # FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C2.2 — fast-feedback
                                                                            # validator for the (S, T, R, P) candidate-pool triple. The
                                                                            # cascor server's _validate_candidate_pool_triple stays
                                                                            # authoritative; this just mirrors the truth table client-side
                                                                            # so the user sees violations on input change instead of on
                                                                            # Apply-click.
                                                                            html.Div(
                                                                                id="cn-pool-triple-feedback",
                                                                                className="text-danger small mb-2",
                                                                                children="",
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
                                                                                                    step=1,
                                                                                                    min=TrainingConstants.MIN_CANDIDATE_TRAINING_ITERATIONS,
                                                                                                    max=TrainingConstants.MAX_CANDIDATE_TRAINING_ITERATIONS,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                    step="any",
                                                                                                    min=TrainingConstants.MIN_CANDIDATE_CONVERGENCE_THRESHOLD,
                                                                                                    max=TrainingConstants.MAX_CANDIDATE_CONVERGENCE_THRESHOLD,
                                                                                                    className="mb-2 ms-4",
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                            # F-CANOPY-022: value MUST be one of cascor's
                                                                                            # Literal["top","random","mixed"] (juniper-cascor
                                                                                            # api/models/training.py:159,:327). This shipped as
                                                                                            # "top_tier", which cascor rejected with a pydantic
                                                                                            # literal_error, so this option could never be applied.
                                                                                            {"label": "Add Top Tier Candidates", "value": "top"},
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
                                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                                                                debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
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
                                                # FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.2 P1
                                                # Issue #3 Phase 1 — pending dataset banner.
                                                # Visibility is driven by the status-bar
                                                # interval reading the cascor-side
                                                # `pending_dataset` field (cascor #242);
                                                # buttons offer the user the explicit
                                                # cold-swap restart or a Cancel out.
                                                dbc.Alert(
                                                    [
                                                        html.Span("Dataset change pending — restart training to apply.", className="me-2"),
                                                        html.Br(),
                                                        dbc.ButtonGroup(
                                                            [
                                                                dbc.Button(
                                                                    "Stop & Restart with new dataset",
                                                                    id="restart-with-new-dataset-button",
                                                                    color="primary",
                                                                    size="sm",
                                                                ),
                                                                dbc.Button(
                                                                    "Cancel pending change",
                                                                    id="cancel-pending-dataset-button",
                                                                    color="secondary",
                                                                    outline=True,
                                                                    size="sm",
                                                                ),
                                                            ],
                                                            className="mt-2",
                                                        ),
                                                    ],
                                                    id="pending-dataset-banner",
                                                    color="warning",
                                                    is_open=False,
                                                ),
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
                                                                "color": "var(--text-muted)",
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
                                # Phase 2 P2-4 (Issue #3): Experimental Functions gate.
                                # Sidebar location (under Network Information) is per
                                # ISSUE_3_PHASE_2_LIVE_DATASET_SWAP_2026-05-09 §4.1 — the
                                # toggle affects the whole session, not a single tab.
                                # F2.10: the cascor server is authoritative; this
                                # switch's value is reconciled to cascor's state on
                                # page load and on every change. The companion
                                # ``experimental-flags-store`` (declared near the
                                # other ``storage_type='local'`` stores) is what
                                # P2-5's Live Dataset Switch button reads.
                                html.Div(
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                html.H5("Experimental Functions", className="mb-0"),
                                            ),
                                            dbc.CardBody(
                                                [
                                                    dbc.Switch(
                                                        id="experimental-functions-toggle",
                                                        label="Enable Experimental Functions",
                                                        value=False,
                                                        persistence=True,
                                                        persistence_type="local",
                                                    ),
                                                    html.Div(
                                                        id="experimental-functions-alert",
                                                        className="mt-2",
                                                    ),
                                                ]
                                            ),
                                        ],
                                        className="mb-3",
                                    ),
                                    id="sidebar-experimental-functions-section",
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
                            id="sidebar-col",
                            # FRONTEND_ISSUES_PLAN_2026-05-09 §6.4 / Issue #6 —
                            # initial value matches the metrics tab (the default
                            # ``active_tab``); the per-tab callback below adjusts
                            # this on every tab change. Width values come from
                            # ``frontend.ui_standards`` — the single source of
                            # truth pinned by tests/regression/test_tab_sidebar_widths.py.
                            width=ui_standards.TAB_SIDEBAR_WIDTH["metrics"],
                        ),
                        # Right panel - Visualizations with tabs
                        dbc.Col(
                            [
                                dbc.Tabs(
                                    # A1-iii-b1: the tab list is built by a method so the
                                    # model-class suppression callback can rebuild it with the
                                    # cascade-only tabs filtered out for a one_shot model.
                                    self._all_visualization_tabs(),
                                    id="visualization-tabs",
                                    active_tab="metrics",
                                )
                            ],
                            id="visualization-col",
                            # FRONTEND_ISSUES_PLAN_2026-05-09 §6.4 / Issue #6 —
                            # complement of the sidebar width; the per-tab
                            # callback keeps the sum at GRID_COLUMNS=12.
                            width=ui_standards.visualization_width_for("metrics"),
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
                # A1-iii-b1: the active model's execution paradigm ("live" | "one_shot"),
                # hydrated from GET /api/train/status. Drives cascade-panel suppression — a
                # "one_shot" (recurrence) model hides the 5 cascade-only viz tabs + the
                # status-bar iteration segment. Defaults "live" so the full dashboard renders.
                dcc.Store(id="model-class-store", storage_type="memory", data="live"),
                # A1-iv-3a: the currently-selected model key, written by the sidebar picker's
                # POST /api/model/select callback (the runtime backend swap, A1-iv-2).
                dcc.Store(id="model-selection-store", storage_type="memory", data=DEFAULT_MODEL_KEY),
                # A1-iv-3c: the one-shot (recurrence) Start dataset-ref body — ``{"dataset": {...}}``
                # or None. A single Python callback resolves it from model-class-store +
                # nn-dataset-type-dropdown so BOTH training-button transports (the server-side REST
                # handler and the Phase D clientside WS/REST JS) forward the same generator + registry
                # params on Start; None for a live (cascor/demo) model leaves their start POST unchanged.
                dcc.Store(id="oneshot-start-params-store", storage_type="memory", data=None),
                # Update intervals
                dcc.Interval(id="fast-update-interval", interval=DashboardConstants.FAST_UPDATE_INTERVAL_MS, n_intervals=0),
                dcc.Interval(id="slow-update-interval", interval=DashboardConstants.SLOW_UPDATE_INTERVAL_MS, n_intervals=0),
                # One-shot interval for parameter initialization (fires once, 1s after load)
                dcc.Interval(id="params-init-interval", interval=1000, max_intervals=1, n_intervals=0),
                # CAN-000: pause periodic update intervals while the Apply Parameters
                # button is in flight, so a server roundtrip isn't racing against
                # interval-driven REST polls / clientside drains.
                dcc.Store(id="apply-in-flight", data=False),
                # E-3 (training-runtime defects plan §9): watchdog tick for the
                # apply-in-flight clamp. Deliberately NOT one of the two clamped
                # intervals — it must keep firing while they are disabled so a
                # stuck clamp can always be force-released clientside.
                dcc.Interval(id="apply-watchdog-interval", interval=DashboardConstants.APPLY_WATCHDOG_INTERVAL_MS, n_intervals=0),
                # FRONTEND_ISSUES_PLAN_2026-05-09 §2.5 C / Issue #2 — write-only
                # sink for the force-blur clientside callback. Dash requires
                # an Output target on every callback; this Store exists solely
                # to satisfy that contract without colliding with another
                # callback's output.
                dcc.Store(id="apply-blur-sink", data=None),
                # Phase B: WebSocket drain stores (structured objects, D-07)
                # N1 removed the then-dead-end ws-state-buffer / ws-candidate-progress
                # stores; N8 (WS-primary wiring, wave 4) re-attaches ws-state-buffer as
                # a live consumer — the drainState clientside callback below hydrates it
                # and the metrics-panel training-state store prefers it while WS is fresh.
                dcc.Store(id="ws-metrics-buffer", data={"events": [], "gen": 0, "last_drain_ms": 0}),
                dcc.Store(id="ws-topology-buffer", data=None),
                # N8: latest-only training-state frame (mirrors ws-topology-buffer's
                # shape). Fed by drainState; consumed by fetch_training_state as the
                # WS-primary source for the metrics-panel status strip.
                dcc.Store(id="ws-state-buffer", data=None),
                # N8: WS-data liveness (booleans only, so the value changes only on a
                # live↔stale transition). A fast-interval clientside callback computes
                # {metrics_live, state_live} from the bridge's frame-arrival clocks vs
                # WS_LIVENESS_WINDOW_MS. The metrics / training-state polls read this to
                # decide WS-primary (skip REST) vs REST fallback. Defaults stale so the
                # mount fetch and any WS-quiet tab always poll (anti-starvation).
                dcc.Store(id="ws-liveness-store", data={"metrics_live": False, "state_live": False}),
                dcc.Store(id="ws-cascade-add-buffer", data={"events": [], "gen": 0, "last_drain_ms": 0}),
                # P2-7 follow-up: WS push buffer for dataset_swap events.
                # Hydrated by a clientside drain of
                # ``window._juniperWsDrain._datasetSwapBuffer``; a
                # server-side merger then folds the events into
                # ``dataset-swap-events-store`` with dedupe.
                dcc.Store(id="ws-dataset-swap-buffer", data={"events": [], "gen": 0, "last_drain_ms": 0}),
                # P2-5 follow-up A+B: no-op sink for the clientside
                # callback that scrolls + pulses the Apply Dataset
                # button when the user dismisses the Live Switch modal
                # via "Return to Stop & Restart". The callback mutates
                # the DOM directly; this Store exists only to satisfy
                # Dash's "every clientside callback needs an Output".
                dcc.Store(id="live-switch-fallback-sink", data=None),
                dcc.Store(id="ws-connection-status", data={"connected": False, "reconnecting": False, "mode": "demo" if get_settings().demo_mode else "live"}),
                # N2: canopy→cascor stream health (relay + control supervisor),
                # polled from GET /api/stream_health on the slow interval. Feeds
                # the degraded-mode dimension of the WS badge — browser-socket-
                # open must not masquerade as end-to-end healthy.
                dcc.Store(id="stream-health-store", data=None),
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
                # Phase 2 P2-5 (Issue #3): Live Dataset Switch warning modal.
                # Per spec §4.3 — two-step warning + summary + accept/cancel.
                # ``backdrop="static"`` + ``keyboard=False`` force an
                # explicit choice (F2.4). The body's read-only summary
                # (Q3 hybrid) renders the current sidebar dataset config
                # so the user sees exactly what they're about to swap to.
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("In-flight dataset migration")),
                        dbc.ModalBody(
                            [
                                dbc.Alert(
                                    "Warning: in-flight dataset migration will potentially " "alter Network Architecture and will permanently affect " "History, Snapshots, and Training Replay.",
                                    color="warning",
                                    className="mb-3",
                                ),
                                html.P("You are about to swap to:", className="mb-2"),
                                dbc.ListGroup(
                                    [],  # populated by callback from sidebar State refs
                                    id="live-switch-dataset-summary",
                                    flush=True,
                                    className="mb-3",
                                ),
                                html.P(
                                    "Choose how to proceed:",
                                    className="mb-0 text-muted",
                                ),
                            ]
                        ),
                        dbc.ModalFooter(
                            [
                                dbc.Button(
                                    "Return to Stop & Restart",
                                    id="live-switch-fallback-button",
                                    color="secondary",
                                    outline=True,
                                ),
                                dbc.Button(
                                    "Accept and proceed with live switch",
                                    id="live-switch-accept-button",
                                    color="warning",
                                ),
                            ]
                        ),
                    ],
                    id="live-switch-modal",
                    is_open=False,
                    backdrop="static",
                    keyboard=False,
                    centered=True,
                ),
                # Phase 2 P2-5 (Issue #3): Live-swap progress alert.
                # Opens on Accept (modal closes); shows spinner + Cancel
                # button while cascor's POST is in flight (5–30 s for
                # real fetches). The Cancel callback fires DELETE
                # concurrently — see _setup_live_dataset_switch_callbacks.
                # Styled as a floating alert (position:fixed via CSS in
                # the className) so it stays visible regardless of which
                # tab the user is on while the swap completes.
                dbc.Alert(
                    [
                        dbc.Spinner(size="sm", color="light"),
                        html.Span(" Swapping dataset…", className="ms-2"),
                        dbc.Button(
                            "Cancel",
                            id="live-switch-cancel-button",
                            color="danger",
                            size="sm",
                            className="ms-3",
                        ),
                    ],
                    id="live-switch-progress-alert",
                    is_open=False,
                    color="info",
                    dismissable=False,
                    style={"position": "fixed", "top": "1rem", "right": "1rem", "zIndex": 1060, "minWidth": "20rem"},
                ),
                # Outcome alert — opens after the swap POST resolves
                # (success / cancelled / error). Auto-dismisses after 5s.
                html.Div(id="live-switch-outcome-alert", style={"position": "fixed", "top": "5rem", "right": "1rem", "zIndex": 1060, "minWidth": "20rem"}),
                # N3 (I-6): Restart-with-new-dataset confirm modal (Q3/Q4).
                # Replaces the pre-N3 fire-and-forget cold-swap — the sidebar
                # "Stop & Restart with new dataset" banner button now opens this
                # confirm dialog instead of silently POSTing. A simple confirm by
                # default (assumes all other meta-parameters / structures /
                # processes unchanged), leading with a start-fresh toggle (Q4,
                # default OFF) and an expandable granular VERIFY/MODIFY section
                # (Q3). N3b turns that section from read-only into in-place MODIFY:
                # the staged dataset config (re-staged via /api/stage_dataset) and
                # a focused set of restart-relevant training params (clamped +
                # applied through N5's CascorPatchBounds / /api/set_params
                # machinery) are editable before Confirm. Confirm →
                # (re-stage if edited) → (apply params if edited) →
                # POST /api/train/restart (stop → await stopped → start(staged));
                # every step's outcome renders in restart-outcome-alert (T4).
                # ``backdrop="static"`` + ``keyboard=False`` force an explicit
                # choice — N3 turns a button that stopped nothing into one that can
                # kill a multi-hour run (plan §11 skeptic #11).
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Confirm restart with new dataset")),
                        dbc.ModalBody(
                            [
                                dbc.Alert(
                                    "This stops the current run (if one is active), waits for it to settle, then restarts training with the staged dataset. Expand the section below to change the dataset or key training parameters before confirming; anything you leave unchanged is applied as-is.",
                                    color="info",
                                    className="mb-3",
                                ),
                                html.P("Restart plan:", className="mb-1 fw-semibold"),
                                dbc.ListGroup([], id="restart-confirm-summary", flush=True, className="mb-3"),
                                dbc.Switch(
                                    id="restart-start-fresh-toggle",
                                    label="Start fresh — discard the current model and its retained metrics/history (snapshots preserved)",
                                    value=False,
                                ),
                                html.Div(
                                    "Off (default): continue the current model, retaining metrics/history for cross-dataset continuity. On: rebuild a vanilla, untrained network — functionally a clean stack launch (on-disk snapshots are kept).",
                                    className="text-muted mb-3",
                                    style={"fontSize": "0.85em"},
                                ),
                                dbc.Button(
                                    "▸ Verify / modify what will happen",
                                    id="restart-granular-toggle",
                                    color="link",
                                    size="sm",
                                    className="p-0 mb-2",
                                ),
                                dbc.Collapse(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                # N3b: read-only context (current engine
                                                # state, populated on open) + the C5
                                                # start-fresh consequence semantics.
                                                html.Div(id="restart-granular-context", className="mb-2"),
                                                html.Div(
                                                    [
                                                        html.Div([html.Strong("Start fresh OFF: "), "continue the current model, retaining metrics/history (cross-dataset continuity)."], className="text-muted", style={"fontSize": "0.82em"}),
                                                        html.Div([html.Strong("Start fresh ON: "), "discard the model + retained metrics/history for a vanilla rebuild (snapshots preserved)."], className="text-muted mb-2", style={"fontSize": "0.82em"}),
                                                    ]
                                                ),
                                                html.Hr(className="my-2"),
                                                # N3b: editable staged-dataset config — the
                                                # StageDatasetRequest fields, defaulting to the
                                                # currently staged / current values; an edit
                                                # re-stages via /api/stage_dataset before the
                                                # restart proceeds.
                                                html.P("Dataset for the restart", className="fw-semibold mb-1"),
                                                self._build_restart_dataset_fields(),
                                                html.Hr(className="my-2"),
                                                # N3b: editable restart-relevant training params
                                                # — clamped + applied through N5's machinery
                                                # (CascorPatchBounds + /api/set_params partition)
                                                # BEFORE the stop→await→start orchestration.
                                                html.P("Key training parameters", className="fw-semibold mb-1"),
                                                html.Div(
                                                    "Edited values are clamped to the backend's accepted ranges and applied before the restart; unchanged fields are left as-is.",
                                                    className="text-muted mb-2",
                                                    style={"fontSize": "0.8em"},
                                                ),
                                                self._build_restart_param_fields(),
                                            ]
                                        )
                                    ),
                                    id="restart-granular-collapse",
                                    is_open=False,
                                ),
                                # N3b: baseline captured on open (staged dataset + current
                                # params) so Confirm re-stages / applies ONLY what the
                                # operator actually changed, and the verify summary can show
                                # the diff.
                                dcc.Store(id="restart-modal-baseline", data={}),
                            ]
                        ),
                        dbc.ModalFooter(
                            [
                                dbc.Button("Cancel", id="restart-cancel-button", color="secondary", outline=True),
                                dbc.Button("Confirm & Restart", id="restart-confirm-button", color="primary"),
                            ]
                        ),
                    ],
                    id="restart-confirm-modal",
                    is_open=False,
                    backdrop="static",
                    keyboard=False,
                    centered=True,
                ),
                # N3: restart progress alert — opens on Confirm (spinner while the
                # bounded stop → await → start POST is in flight). Split from the
                # outcome callback so the spinner shows before the POST returns.
                dbc.Alert(
                    [
                        dbc.Spinner(size="sm", color="light"),
                        html.Span(" Restarting training…", className="ms-2"),
                    ],
                    id="restart-progress-alert",
                    is_open=False,
                    color="info",
                    dismissable=False,
                    style={"position": "fixed", "top": "13rem", "right": "1rem", "zIndex": 1060, "minWidth": "20rem"},
                ),
                # N3: restart outcome alert — success (incl. instant-convergence)
                # or per-step failure (stop / await / start) with the upstream
                # detail. Mirrors the live-switch / training-control *-outcome-alert
                # idiom, but a DEDICATED surface (not the failure-only
                # training-control renderer) so a truthful SUCCESS outcome can be
                # shown too — the epoch-0 instant-convergence case must not read as
                # frozen (folded finding 2). Sequential with the progress alert
                # above (same slot: progress closes as this renders).
                html.Div(id="restart-outcome-alert", style={"position": "fixed", "top": "13rem", "right": "1rem", "zIndex": 1060, "minWidth": "20rem"}),
                # N3 (T4): Apply-Dataset staging outcome — surfaces a staging
                # failure that was previously silent (``return dash.no_update``).
                html.Div(id="dataset-stage-outcome-alert", style={"position": "fixed", "top": "17rem", "right": "1rem", "zIndex": 1060, "minWidth": "20rem"}),
                # Model-selection surface (A1b-1; design D7/§5.2): a dedicated full-width modal
                # opened from the sidebar "▸ change" button. ``toggle_model_modal`` fills the body
                # container with a custom ``dbc.Table`` (status badge + compatibility cell + a
                # per-row Select button disabled for incompatible models), gated against the
                # current dataset. ``size="xl"`` caps the width (dbc 2.0.4 / Bootstrap 5) and
                # ``scrollable`` scrolls the body as the model population grows — so the surface
                # scales to many models with no manual sizing (modal chosen over a Models tab: the
                # tab bar caps ``active_tab`` writers at two and is rebuilt by one-shot suppression;
                # a modal's ``is_open`` toggle sidesteps both — OQ-1).
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Select a Model")),
                        dbc.ModalBody(
                            [
                                # A1b search (§5.2): free-text filter over label + family + category + tags.
                                # ``type="search"`` gives a native clear (×); the integer-ms debounce
                                # (the repo standard — commits ~350 ms after the last keystroke, no blur
                                # needed, per the no-boolean-debounce convention) rebuilds the table as
                                # you type. Folded into ``toggle_model_modal`` (it owns the table
                                # container), so there is no racy second writer.
                                dbc.Input(
                                    id="model-search-input",
                                    type="search",
                                    value="",
                                    debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS,
                                    placeholder="Search models by name, family, category, or tag…",
                                    className="mb-3",
                                ),
                                html.Div(id="model-selection-table-container"),
                            ]
                        ),
                        dbc.ModalFooter(
                            dbc.Button("Close", id="model-selection-modal-close", color="secondary", outline=True),
                        ),
                    ],
                    id="model-selection-modal",
                    is_open=False,
                    size="xl",
                    scrollable=True,
                    centered=True,
                ),
                # Hidden div to store WebSocket data
                html.Div(id="websocket-data", style={"display": "none"}),
                dcc.Store(id="training-control-action", data=None),
                # Training-control outcome alert — surfaces a dismissable danger
                # alert when a Start/Pause/Stop/Resume/Reset command is rejected
                # (fed by BOTH the server-side handler and the Phase D clientside
                # JS via set_props). Offset below live-switch-outcome-alert
                # (top:5rem) so the two fixed surfaces never overlap. See
                # notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md.
                html.Div(id="training-control-outcome-alert", style={"position": "fixed", "top": "9rem", "right": "1rem", "zIndex": 1060, "minWidth": "20rem"}),
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

    def _all_visualization_tabs(self):
        """Return the full ordered list of right-panel ``dbc.Tab``s (A1-iii-b1).

        Extracted from ``get_layout`` so the model-class suppression callback
        (``_setup_model_class_callbacks``) can rebuild the tab bar with the 5 cascade-only
        tabs (candidates / topology / evolution / boundaries / workers) filtered out when a
        one-shot model is active.
        """
        # NOTE: one ``dbc.Tab`` per call with ``label=`` and ``tab_id=`` on SEPARATE lines
        # (trailing comma keeps Black from collapsing them at line-length 512). The UI test
        # ``test_sidebar_width._parse_tab_labels`` greps this source for the
        # ``label="X",\n  tab_id="y"`` pattern, so the multi-line shape is load-bearing.
        return [
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
        ]

    def _visible_tabs(self, model_class):
        """Return the right-panel tabs for the model class (A1-iii-b1).

        For a ``"one_shot"`` model the cascade-only tabs are dropped; otherwise the full list
        is returned unchanged. Pure (no Dash context) so the suppression logic is directly
        unit-testable. Deliberately does NOT touch ``active_tab`` — the dashboard keeps exactly
        two ``visualization-tabs.active_tab`` writers (Store-restore + tutorial trigger) to
        avoid a mount-time restore race, and the default active tab ("metrics") is never a
        cascade tab, so it survives the filter. (Resetting a hidden active tab on a *runtime*
        model swap belongs with A1-iv's model-switch flow.)
        """
        tabs = self._all_visualization_tabs()
        if model_class == "one_shot":
            tabs = [tab for tab in tabs if tab.tab_id not in _CASCADE_ONLY_TAB_IDS]
        return tabs

    def _setup_callbacks(self):
        """Set up dashboard callbacks."""
        self._setup_theme_callbacks()  # Define theme callbacks
        self._setup_sidebar_visibility_callback()  # Contextual sidebar visibility
        self._setup_status_bar_callbacks()  # Define Status Bar callbacks
        self._setup_network_callbacks()  # Define Network callbacks
        self._setup_datastore_callbacks()  # Component data store updaters
        self._setup_button_action_callbacks()  # Define button action callbacks
        self._setup_backend_callbacks()  # Define backend callbacks
        self._setup_experimental_functions_callbacks()  # P2-4 (Issue #3)
        self._setup_live_dataset_switch_callbacks()  # P2-5 (Issue #3)
        self._setup_restart_orchestration_callbacks()  # N3 (I-6): cold-swap confirm modal + stop→await→start
        self._setup_dataset_swap_observers_callbacks()  # P2-7 (Issue #3)
        self._setup_model_class_callbacks()  # A1-iii-b1: cascade-panel suppression for one-shot models
        self._setup_model_selection_callbacks()  # A1-iv-3a: sidebar model picker -> runtime backend swap

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

        # FRONTEND_ISSUES_PLAN_2026-05-09 §6.4 + §6.5 / Issue #6 — per-tab
        # sidebar width. Wide tabs (3/9) carry Network Parameters; narrow
        # tabs (2/10) reclaim viewport for content-dense visualisations or
        # mostly-static content. Widths come from ``frontend.ui_standards``;
        # the test suite pins both ends.
        @self.app.callback(
            [Output("sidebar-col", "width"), Output("visualization-col", "width")],
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=True,
        )
        def resize_sidebar_for_tab(active_tab: str):
            sidebar = ui_standards.TAB_SIDEBAR_WIDTH.get(active_tab, ui_standards.WIDE_SIDEBAR)
            return sidebar, ui_standards.GRID_COLUMNS - sidebar

    def _setup_model_class_callbacks(self):
        """A1-iii-b1: hydrate the model-class flag and suppress cascade-only panels for one-shot models.

        ``model-class-store`` is hydrated once from ``GET /api/train/status`` (which carries the
        active backend's ``execution`` paradigm). When it reads ``"one_shot"`` (a recurrence /
        LMU fit), the cascade-only viz tabs and the status-bar iteration segment are hidden — an
        LMU has no growing topology, decision boundary, candidate units, or worker pool.
        """

        @self.app.callback(
            Output("model-class-store", "data"),
            Input("params-init-interval", "n_intervals"),
            prevent_initial_call=True,
        )
        def hydrate_model_class(_n_intervals):
            """Read the active backend's execution paradigm from /api/train/status (once on mount)."""
            try:
                resp = requests.get(
                    self._api_url("/api/train/status"),
                    timeout=DashboardConstants.DASHBOARD_GET_TIMEOUT,
                    headers=internal_api_headers(),
                )
                if resp.ok and resp.json().get("execution") == "one_shot":
                    return "one_shot"
            except Exception as exc:
                # Transport hiccup → keep the default "live" (render the full dashboard).
                self.logger.debug("model-class hydration failed; defaulting to 'live': %s", exc)
            return "live"

        @self.app.callback(
            Output("visualization-tabs", "children"),
            Input("model-class-store", "data"),
            prevent_initial_call=True,
        )
        def suppress_cascade_tabs(model_class):
            """Rebuild the tab bar, dropping the cascade-only tabs when the model is one_shot."""
            return self._visible_tabs(model_class)

        @self.app.callback(
            Output("status-iteration-segment", "style"),
            Input("model-class-store", "data"),
            prevent_initial_call=True,
        )
        def toggle_iteration_segment(model_class):
            """Hide the status-bar Hidden Units segment (cascade-only) for a one_shot model."""
            base = {"marginRight": "20px"}
            return {**base, "display": "none"} if model_class == "one_shot" else base

    def _setup_model_selection_callbacks(self):
        """A1b-1: the dedicated model-selection surface drives the runtime backend swap.

        Selection moved from the sidebar dropdown (A1-iv-3a) to a per-row Select button in the
        ``model-selection-modal`` table (opened by the sidebar "▸ change" button). The chosen model
        POSTs its key to ``POST /api/model/select`` (A1-iv-2) — which re-creates the process-global
        backend — and mirrors the resulting execution paradigm into ``model-class-store``
        (``allow_duplicate``) so the A1-iii-b1 one-shot cascade-panel suppression follows the swap.
        The compact sidebar summary reflects the live selection + status; the modal then closes.
        ``gate_dataset_options`` (A1-iv-3b) and ``resolve_oneshot_start_body`` (A1-iv-3c) are
        UNCHANGED — they key off the stores, not the input control, so only the input side moved.
        """

        # A1b-1: the dedicated model-selection modal. The sidebar "▸ change" button opens it
        # (rebuilding the table against the CURRENT dataset value so its compatibility cells +
        # disabled Select buttons reflect it on open, §5.3); the Close button closes it. A1b search:
        # typing in ``model-search-input`` rebuilds the table filtered (§5.2) — folded in here (the
        # one callback that owns ``model-selection-table-container``) so there is no racy 2nd writer.
        @self.app.callback(
            Output("model-selection-modal", "is_open"),
            Output("model-selection-table-container", "children"),
            Input("nn-model-change-button", "n_clicks"),
            Input("model-selection-modal-close", "n_clicks"),
            Input("model-search-input", "value"),
            State("nn-dataset-type-dropdown", "value"),
            State("model-selection-store", "data"),
            prevent_initial_call=True,
        )
        def toggle_model_modal(_open_clicks, _close_clicks, search, dataset_value, selected_model):
            return self._toggle_model_modal_handler(dash.callback_context.triggered_id, dataset_value, selected_model, search)

        # A1b-1: a model is selected by the per-row Select button in the table (pattern-matching
        # ``{"type": "model-select-btn", "index": <key>}``), REPLACING the old nn-model-dropdown
        # Input. The clicked key is resolved from ``ctx.triggered_id`` and applied via the SAME
        # ``_select_model_handler`` (POST /api/model/select + store mirror, A1-iv-3a); the modal
        # then closes. Downstream gates are insulated — ``gate_dataset_options`` keys off
        # ``model-selection-store`` and ``resolve_oneshot_start_body`` off ``model-class-store``,
        # NOT the input control — so swapping the input side leaves every downstream gate intact.
        @self.app.callback(
            Output("model-selection-store", "data"),
            Output("model-class-store", "data", allow_duplicate=True),
            Output("nn-model-summary", "children"),
            Output("model-selection-modal", "is_open", allow_duplicate=True),
            Input({"type": "model-select-btn", "index": dash.ALL}, "n_clicks"),
            prevent_initial_call=True,
        )
        def select_model(n_clicks_list):
            return self._select_model_from_table_handler(n_clicks_list, dash.callback_context.triggered_id)

        # N7 (I-5): also fires once on mount (params-init-interval) so the availability gate is
        # applied at first paint, not only after a model change — an unavailable generator (its
        # optional data extra absent) is greyed with a reworded reason from the start.
        @self.app.callback(
            Output("nn-dataset-type-dropdown", "options"),
            Output("nn-dataset-type-dropdown", "value"),
            Input("model-selection-store", "data"),
            Input("params-init-interval", "n_intervals"),
            State("nn-dataset-type-dropdown", "value"),
            prevent_initial_call=True,
        )
        def gate_dataset_options(model_key, _init_intervals, current_value):
            return self._gate_dataset_options_handler(model_key, current_value)

        # N7 (I-7 / U-6): drive the sidebar dataset params from the SELECTED generator's schema.
        # Fires on dataset change AND once on mount (params-init-interval) so the panel is correct at
        # first paint. Renames the section per type (U-6), hides the spiral typed-field block for
        # non-spiral types, and renders schema-derived inputs into nn-dataset-schema-params (read by
        # apply_dataset into the generic ``params`` staging channel — the typed fields stay spiral-only).
        @self.app.callback(
            Output("nn-dataset-section-title", "children"),
            Output("nn-dataset-typed-fields", "style"),
            Output("nn-dataset-schema-params", "children"),
            Input("nn-dataset-type-dropdown", "value"),
            Input("params-init-interval", "n_intervals"),
            prevent_initial_call=True,
        )
        def render_dataset_params(dataset_value, _init_intervals):
            return self._render_dataset_params_handler(dataset_value)

        # A1-iv-3c: resolve the one-shot Start dataset-ref body in ONE place from the model-class
        # flag + the (gated) dataset generator, so both training-button transports forward the
        # same body. Re-fires on either Input so the store tracks model swaps and dataset snaps.
        @self.app.callback(
            Output("oneshot-start-params-store", "data"),
            Input("model-class-store", "data"),
            Input("nn-dataset-type-dropdown", "value"),
            prevent_initial_call=True,
        )
        def resolve_oneshot_start_body(model_class, dataset_generator):
            return self._resolve_oneshot_start_body_handler(model_class, dataset_generator)

        # A1b-2 (§5.3): the reactive reverse gate. Selecting a dataset annotates the sidebar with
        # the model constraint it imposes ("3-D models only"), the dataset-side mirror of the
        # table's per-row ``model_reason`` greying. Fires on every dataset change — a user pick OR
        # the forward-gate snap (``gate_dataset_options``) — so the hint always tracks the dataset.
        @self.app.callback(
            Output("nn-model-dataset-hint", "children"),
            Input("nn-dataset-type-dropdown", "value"),
            prevent_initial_call=True,
        )
        def annotate_model_hint(dataset_value):
            return self._dataset_model_hint_handler(dataset_value)

        # A1-iv-5 / D8 (§5.7): when the selected model is non-live, show a status reason near the
        # training controls explaining why Start is disabled. Cleared (hidden) for a live model.
        # Pairs with the Start force-disable in ``update_button_appearance`` (same model-selection
        # Input), so the gate and its explanation always move together.
        @self.app.callback(
            Output("train-gate-notice", "children"),
            Input("model-selection-store", "data"),
            prevent_initial_call=True,
        )
        def annotate_train_gate(model_key):
            return self._train_gate_notice_handler(model_key)

    @staticmethod
    def _resolve_oneshot_start_body_handler(model_class: "str | None", dataset_generator: "str | None") -> "dict[str, object] | None":
        """Build the one-shot Start dataset-ref body (A1-iv-3c), or None for a live model.

        For a one_shot (recurrence) model the Start button MUST forward a dataset reference, else
        ``RecurrenceBackend.start_training`` bails ("no dataset reference"). The generator is the
        gated dataset-dropdown value; its juniper-data params come from the registry's seeded
        ``default_params`` (single source of truth) — the synthetic n_samples/noise sidebar inputs
        do not apply to a 3-D sequence generator. Returns None for a live (cascor/demo) model so
        its bare reset-only start POST is unchanged. Stored in ``oneshot-start-params-store`` and
        read by BOTH training-button transports (server-side REST handler + Phase D clientside JS).
        """
        if model_class != "one_shot" or not dataset_generator:
            return None
        dataset_ref: dict[str, object] = {"generator": dataset_generator}
        params = dataset_default_params(dataset_generator)
        if params:
            dataset_ref["params"] = params
        return {"dataset": dataset_ref}

    def _gate_dataset_options_handler(self, model_key, current_value):
        """Gate the dataset dropdown against the selected model (A1-iv-3b) AND availability (N7 / I-5).

        Composes the model-compatibility gate (``gated_dataset_options`` — the D5 correctness gate:
        an incompatible dataset is disabled with a reason suffix) with the deployment-availability
        gate (``apply_availability_gate`` — a generator whose optional data extra is absent is
        disabled with a reworded reason). A missing/older availability surface degrades to
        all-available (flag-absent fallback). If the current selection became disabled, snap to the
        first enabled option (dataset-primary conflict policy, D5). Returns ``(no_update, no_update)``
        when there is no model yet (unchanged contract); the mount-time pass runs against the seeded
        ``model-selection-store`` (``DEFAULT_MODEL_KEY``), so the availability gate still applies at
        first paint.
        """
        if not model_key:
            return dash.no_update, dash.no_update
        options = apply_availability_gate(gated_dataset_options(model_key), self._fetch_generators())
        enabled = [option["value"] for option in options if not option.get("disabled")]
        if current_value in enabled or not enabled:
            return options, dash.no_update
        return options, enabled[0]

    # N7 (I-7 / U-6 / I-5): schema-driven dataset-panel plumbing. The generator list (name /
    # available / schema dicts) is fetched from canopy's own /api/dataset/generators proxy and
    # TTL-cached so the render + gate callbacks don't each pay a round-trip.
    _GENERATORS_CACHE_TTL_S: float = 30.0

    def _fetch_generators(self):
        """Return the /api/dataset/generators list (name/available/schema dicts), short-TTL-cached.

        Reuses canopy's own proxy route (which fetches juniper-data's /v1/generators via httpx and
        falls back to a built-in list when the service is down). Any error yields an empty list — the
        availability helpers then treat every generator as available (flag-absent fallback), so a
        down/older data service never greys the panel or hides its params.
        """
        now = time.monotonic()
        cached = getattr(self, "_generators_cache", None)
        if cached is not None and (now - cached[0]) < self._GENERATORS_CACHE_TTL_S:
            return cached[1]
        generators: list = []
        try:
            resp = requests.get(self._api_url("/api/dataset/generators"), timeout=DashboardConstants.DASHBOARD_GET_TIMEOUT, headers=internal_api_headers())
            if resp.ok:
                payload = resp.json()
                generators = payload.get("generators", []) if isinstance(payload, dict) else []
        except Exception as exc:  # noqa: BLE001 — a generator-fetch failure must never break the panel; degrade to all-available.
            self.logger.debug("Failed to fetch dataset generators: %s", exc)
            generators = []
        self._generators_cache = (now, generators or [])
        return self._generators_cache[1]

    @staticmethod
    def _generator_schema(gen_name, generators):
        """Return the JSON schema dict for generator ``gen_name`` from a /v1/generators list, or {}."""
        for entry in generators or ():
            if isinstance(entry, dict) and entry.get("name") == gen_name:
                schema = entry.get("schema")
                return schema if isinstance(schema, dict) else {}
        return {}

    def _initial_dataset_section_title(self):
        """Seed text for the U-6 dataset section title at first paint (renamed per type by callback)."""
        return self._dataset_section_title(DEFAULT_DATASET_TYPE)

    @staticmethod
    def _dataset_section_title(dataset_value):
        """'Current Dataset — <Label>' for U-6 (falls back to the raw value, then a bare title)."""
        spec = get_dataset_spec(dataset_value)
        label = spec.label if spec is not None else (dataset_value or "")
        return f"Current Dataset — {label}" if label else "Current Dataset"

    def _render_dataset_params_handler(self, dataset_value, generators=None):
        """Drive the U-6 title + spiral-block visibility + schema-driven params for the selected type (N7).

        Returns ``(section_title, typed_fields_style, schema_children)``:
        - spiral -> title, typed block shown, empty schema container (spiral keeps its typed fields);
        - other  -> title, typed block hidden, schema-derived inputs (pattern-matching ids) that
          ``apply_dataset`` forwards via the generic ``params`` channel. An unavailable generator
          still renders a reworded reason note (I-5). ``generators`` is injectable for tests.
        """
        if generators is None:
            generators = self._fetch_generators()
        title = self._dataset_section_title(dataset_value)
        gen_name = generator_name_for_type(dataset_value)
        if gen_name == "spiral":
            return title, {"display": "block"}, []
        fields = parse_schema_fields(self._generator_schema(gen_name, generators))
        available = is_generator_available(dataset_value, generators)
        return title, {"display": "none"}, self._build_schema_param_inputs(dataset_value, fields, available)

    @staticmethod
    def _build_schema_param_inputs(dataset_value, fields, available):
        """Build the schema-driven param inputs (+ unavailable/empty note) for a non-spiral type (N7).

        Each field becomes a labelled control with a pattern-matching id
        ``{"type": "nn-gen-param", "name": <field>}`` carrying its schema-derived label/bounds/default,
        so ``apply_dataset`` reads them via ``State({"type": "nn-gen-param", "name": ALL}, ...)`` into
        the generic ``params`` payload. number -> dbc.Input(type=number); boolean -> dbc.Checkbox;
        enum -> dcc.Dropdown; string -> dbc.Input(type=text).
        """
        children: list = []
        if not available:
            children.append(dbc.Alert(f"This dataset is {unavailable_reason(dataset_value)} — it cannot be staged until the deployment provides it.", color="warning", className="py-1 px-2 small mb-2"))
        if not fields:
            children.append(html.P("No adjustable parameters — sensible generator defaults are used.", className="mb-1 small text-muted fst-italic"))
            return children
        for gen_field in fields:
            field_id = {"type": "nn-gen-param", "name": gen_field.name}
            children.append(html.P(f"{gen_field.label}:", className="mb-1 ms-1 small"))
            if gen_field.input_type == "checkbox":
                children.append(dbc.Checkbox(id=field_id, value=bool(gen_field.default), className="mb-2 ms-1"))
            elif gen_field.input_type == "select":
                children.append(dcc.Dropdown(id=field_id, options=[{"label": choice, "value": choice} for choice in gen_field.options], value=gen_field.default, clearable=False, className="mb-2 ms-1", style={"width": "calc(100% - 0.5rem)"}))
            elif gen_field.input_type == "number":
                number_kwargs: dict = {}
                if gen_field.minimum is not None:
                    number_kwargs["min"] = gen_field.minimum
                if gen_field.maximum is not None:
                    number_kwargs["max"] = gen_field.maximum
                if gen_field.step is not None:
                    number_kwargs["step"] = gen_field.step
                children.append(dbc.Input(id=field_id, type="number", value=gen_field.default, debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS, className="mb-2 ms-1", style={"width": "calc(100% - 0.5rem)"}, **number_kwargs))
            else:
                children.append(dbc.Input(id=field_id, type="text", value=(gen_field.default if gen_field.default is not None else ""), debounce=True, className="mb-2 ms-1", style={"width": "calc(100% - 0.5rem)"}))
            if gen_field.description:
                children.append(html.P(gen_field.description, className="mb-2 ms-1 text-muted", style={"fontSize": "0.7rem"}))
        return children

    @staticmethod
    def _collect_generator_params(gen_values, gen_ids):
        """Zip pattern-matching (id, value) pairs into a ``{name: value}`` params dict, dropping blanks.

        ``None`` (a cleared Optional field) and ``""`` (a blank text field) are dropped so the
        generator falls back to its own schema default rather than being sent an empty value.
        """
        params: dict = {}
        for gen_id, value in zip(gen_ids or [], gen_values or [], strict=False):
            if not isinstance(gen_id, dict):
                continue
            name = gen_id.get("name")
            if not name or value is None or value == "":
                continue
            params[name] = value
        return params

    def _apply_dataset_handler(self, n_clicks, dataset_type, n_samples, noise, rotations, n_spirals, gen_values=None, gen_ids=None):
        """POST /api/stage_dataset with the current dataset-form values (N7 schema-aware).

        ``dataset_type`` is ALWAYS sent — cascor's ``_reload_dataset`` hard-requires it. For the
        spiral generator the typed convenience fields (elements/noise/rotations/number) are forwarded
        as before (the force-blur clientside callback commits the numeric inputs first, so they arrive
        as numbers, not Dash/React ``null`` — Issue #4). For any other generator the typed fields are
        omitted and the schema-driven inputs are collected into the generic ``nn_dataset_params``
        channel, which the adapter maps to cascor's ``StageDatasetRequest.params`` (cascor #396 merges
        typed + generic before ``create_dataset``) — so the staging dialect is preserved and non-spiral
        generators pass schema-true params without widening the typed fields.
        """
        if not n_clicks:
            return dash.no_update, dash.no_update
        payload: dict = {"nn_dataset_type": dataset_type}
        if generator_name_for_type(dataset_type) == "spiral":
            for _key, _value in (
                ("nn_dataset_elements", n_samples),
                ("nn_dataset_noise", noise),
                ("nn_spiral_rotations", rotations),
                ("nn_spiral_number", n_spirals),
            ):
                if _value is not None:
                    payload[_key] = _value
        else:
            params = self._collect_generator_params(gen_values, gen_ids)
            if params:
                payload["nn_dataset_params"] = params
        try:
            resp = requests.post(
                self._api_url("/api/stage_dataset"),
                json=payload,
                timeout=DashboardConstants.DASHBOARD_LONG_POST_TIMEOUT,
                headers=internal_api_headers(),
            )
            if resp.status_code == 200:
                self.logger.info("Dataset staged: %s", payload)
                return True, None  # open banner; clear any prior staging error
            detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
            self.logger.warning("Stage dataset failed: %s %s", resp.status_code, detail)
            return dash.no_update, dbc.Alert(f"Could not stage the dataset change: {detail}", color="danger", duration=8000, dismissable=True)
        except requests.RequestException as exc:
            self.logger.warning("Stage dataset exception: %s", exc)
            return dash.no_update, dbc.Alert(f"Backend unreachable while staging the dataset: {exc}", color="danger", duration=8000, dismissable=True)

    def _select_model_handler(self, model_key):
        """Apply a model selection via ``POST /api/model/select`` and mirror the result.

        Returns ``(model_selection_store, model_class_store, summary_text)``; on any failure all
        three are ``dash.no_update`` so a transient error leaves the UI on its prior model.
        """
        if not model_key:
            return dash.no_update, dash.no_update, dash.no_update
        try:
            resp = requests.post(
                self._api_url("/api/model/select"),
                json={"nn_model": model_key},
                timeout=DashboardConstants.API_TIMEOUT_SECONDS + 5,
                headers=internal_api_headers(),
            )
            if resp.ok:
                data = resp.json()
                return data.get("nn_model", model_key), data.get("execution", "live"), self._model_summary_text(data)
            self.logger.warning("Model select failed (%s): %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            self.logger.debug("Model select request failed: %s", exc)
        return dash.no_update, dash.no_update, dash.no_update

    def _toggle_model_modal_handler(self, triggered_id, dataset_value, selected_model, search=""):
        """Open/close the model-selection modal + live-filter the table (A1b-1 / A1b search).

        Opening (``nn-model-change-button``) rebuilds the table against the CURRENT dataset value
        (a ``State``) and the current search term so the per-row compatibility cells + disabled
        Select buttons reflect both on open (§5.3). Typing in the search box (``model-search-input``)
        rebuilds the table filtered (§5.2) while the modal stays open. Closing
        (``model-selection-modal-close``) leaves the table as-is. Returns ``(is_open, table_children)``.
        """
        if triggered_id == "model-selection-modal-close":
            return False, dash.no_update
        # change-button -> open + build; search-input -> keep open + rebuild filtered.
        is_open = True if triggered_id == "nn-model-change-button" else dash.no_update
        return is_open, self._build_model_selection_table(dataset_value, selected_model, search=search or "")

    def _select_model_from_table_handler(self, n_clicks_list, triggered_id):
        """Apply the model whose table Select button was clicked, then close the modal (A1b-1).

        The pattern-matching ``model-select-btn`` callback also fires once when the table is first
        inserted into the modal (every ``n_clicks`` is ``None``) — that no-click fire is guarded to
        a four-way ``no_update``. On a real click the model key is read from ``triggered_id["index"]``
        and applied via the shared ``_select_model_handler`` (POST /api/model/select + store mirror);
        the modal closes only when the selection actually applied (the handler no-ops on failure, so
        a transient error leaves the modal open on the prior model). Returns
        ``(model_selection_store, model_class_store, summary, modal_is_open)``.
        """
        if not isinstance(triggered_id, dict) or not any(n_clicks_list or []):
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        store, model_class, summary = self._select_model_handler(triggered_id.get("index"))
        is_open = False if store is not dash.no_update else dash.no_update
        return store, model_class, summary, is_open

    @staticmethod
    def _model_summary_text(data):
        """Compact 'Active: <label>' summary line for the sidebar model picker (A1-iv-3a)."""
        spec = get_model_spec(data.get("nn_model", ""))
        label = spec.label if spec is not None else data.get("nn_model", "?")
        status = data.get("status", "live")
        note = "" if status == "live" else f" · {status.replace('_', ' ')}"
        return f"Active: {label}{note}"

    def _initial_model_summary(self):
        """Seed text for the sidebar model summary at first paint (A1b-1).

        Resolves the default model's status from the registry so the summary reads honestly before
        any selection callback fires — the dropdown that previously showed the current value is gone,
        so the summary is now the only at-rest indicator of the active model.
        """
        spec = get_model_spec(DEFAULT_MODEL_KEY)
        status = spec.status if spec is not None else "live"
        return self._model_summary_text({"nn_model": DEFAULT_MODEL_KEY, "status": status})

    def _initial_dataset_model_hint(self):
        """Seed text for the sidebar reverse-gate hint at first paint (A1b-2; §5.3)."""
        return dataset_model_hint(DEFAULT_DATASET_TYPE) or ""

    @staticmethod
    def _dataset_model_hint_handler(dataset_value):
        """Sidebar reverse-gate annotation for the current dataset (A1b-2; §5.3).

        Returns the model-constraint phrase for ``dataset_value`` (e.g. "3-D Δt-aware models only"),
        or "" when no dataset is selected so the annotation clears rather than rendering "None".
        """
        return dataset_model_hint(dataset_value) or ""

    @staticmethod
    def _train_gate_notice_handler(model_key):
        """D8 Train-gate status notice for a non-live selected model (A1-iv-5; §5.7).

        Returns a warning ``dbc.Alert`` explaining why Start is disabled when the selected model is
        non-live (``coming_soon`` / ``experimental`` / ``deprecated`` / ``broken``), or ``None``
        (hidden) for a live / trainable model — the visible companion to the Start force-disable in
        ``_update_button_appearance_handler`` (both key off ``model_is_trainable``).
        """
        if model_is_trainable(model_key):
            return None
        spec = get_model_spec(model_key)
        label = spec.label if spec is not None else (model_key or "This model")
        status = spec.status.replace("_", " ") if spec is not None else "unavailable"
        return dbc.Alert(
            [
                html.Strong(f"{label} is {status}. "),
                html.Span("This model can be selected for inspection but is not trainable yet — Start is disabled."),
            ],
            color="warning",
            className="mb-0",
        )

    @staticmethod
    def _status_badge(status):
        """Lifecycle-status badge for the model table (D8) — distinct from incompatibility greying."""
        color = {
            "live": "success",
            "coming_soon": "info",
            "experimental": "warning",
            "deprecated": "secondary",
            "broken": "danger",
        }.get(status, "secondary")
        return dbc.Badge(status.replace("_", " "), color=color, className="text-uppercase")

    @staticmethod
    def _build_model_selection_table(dataset_value, selected_model, *, models=MODELS, search=""):
        """Build the custom ``dbc.Table`` of models for the selection modal (A1b; design §5.2).

        Rows = every model matching the optional ``search`` filter (label + family + category +
        tags, §5.2). Columns: Model / Category / Status / Compatibility / Select. Compatibility is
        computed against the currently-selected dataset (``dataset_value``) via ``model_reason``; an
        incompatible model shows the reason in its compatibility cell and its Select button is
        disabled. Per ratified option (a) a non-live model stays selectable here — ONLY
        *incompatible* models are disabled (non-live models are Train-gated at the controls, not in
        the table — A1-iv-5). The currently-active row is highlighted. A ``dash_table.DataTable`` is
        deliberately NOT used (OQ-4): the cells are rich components (a badge, a reason cell, a
        per-row disabled button) and there is no virtualization payoff at this row count.

        Degenerate states: a non-empty ``search`` that matches nothing renders a "no matches"
        message (§5.2); when a dataset is selected but **no** visible model can train it, a recovery
        message is rendered above the (all-greyed) table (the empty-compatible-set state, §5.8).
        ``models`` is injectable so both states are testable with the real seeds.
        """
        dataset = get_dataset_spec(dataset_value) if dataset_value else None
        visible = [model for model in models if model_matches_search(model, search or "")]
        # A1b search (§5.2): a non-empty query that matches nothing -> a clear "no matches" message,
        # distinct from the §5.8 empty-compatible-set state below (which is about the dataset).
        if not visible:
            return dbc.Alert(
                [html.Strong("No models match your search. "), html.Span("Clear the search box to see all models.")],
                color="secondary",
                className="mb-0",
                id="model-search-empty-alert",
            )
        header = html.Thead(html.Tr([html.Th(col) for col in ("Model", "Category", "Status", "Compatibility", "")]))
        rows = []
        compatible_count = 0
        for model in visible:
            reason = model_reason(model, dataset) if dataset is not None else None
            is_compatible = reason is None
            compatible_count += int(is_compatible)
            is_active = model.key == selected_model
            model_cell = [html.Strong(model.label)]
            if model.description:
                model_cell.extend([html.Br(), html.Span(model.description, className="text-muted small")])
            if is_compatible:
                compat_cell = html.Span("✓ compatible", className="text-success small")
            else:
                compat_cell = html.Span(reason, className="text-muted small fst-italic")
            select_button = dbc.Button(
                "Selected" if is_active else "Select",
                id={"type": "model-select-btn", "index": model.key},
                color="success" if is_active else "primary",
                outline=not is_active,
                size="sm",
                disabled=not is_compatible,
                title=(reason or ("Currently active" if is_active else "Select this model")),
            )
            rows.append(
                html.Tr(
                    [
                        html.Td(model_cell),
                        html.Td(model.category.replace("_", " ")),
                        html.Td(DashboardManager._status_badge(model.status)),
                        html.Td(compat_cell),
                        html.Td(select_button),
                    ],
                    className="table-active" if is_active else "",
                )
            )
        table = dbc.Table([header, html.Tbody(rows)], hover=True, responsive=True, className="align-middle mb-0")
        # Degenerate state (§5.8): a dataset is selected but NO model can train it — show a clear
        # recovery message above the (all-greyed) table rather than a silently-unusable list.
        if dataset is not None and compatible_count == 0:
            recovery = dbc.Alert(
                [
                    html.Strong("No compatible model. "),
                    html.Span("No model can train the selected dataset yet — switch the dataset in the sidebar, or choose a model that supports it once one is available."),
                ],
                color="warning",
                className="mb-3",
                id="model-selection-empty-alert",
            )
            return html.Div([recovery, table])
        return table

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

        # ── FRONTEND_ISSUES_PLAN_2026-05-09 §2.5 C / Issue #2 + Issue #4 ──
        # Force-blur the focused input on Apply-Parameters OR Apply-Dataset
        # click so any pending debounced numeric value commits BEFORE the
        # server-side State() reads. Closes the "type into a numeric input,
        # click Apply with the mouse without ever leaving the field, get the
        # OLD value POSTed" race. For Apply-Parameters this was the
        # most-reported facet of Issue #2; for Apply-Dataset the same race
        # dropped n_samples / noise (committed as null) so only the dataset_type
        # dropdown survived (Issue #4 — the modified-dataset-never-trains
        # repro). Pairs with §2.5 B (the debounce=350 sweep) which moves the
        # commit from "blur only" to "blur OR ~350 ms after last keystroke".
        self.app.clientside_callback(
            """
            function(params_clicks, dataset_clicks) {
                // Either Apply button blurs the focused element, committing a
                // pending numeric value before the server State() snapshot.
                // prevent_initial_call means we only run on a real click, so no
                // n_clicks guard is needed.
                if (document.activeElement
                        && typeof document.activeElement.blur === 'function') {
                    document.activeElement.blur();
                }
                return null;
            }
            """,
            Output("apply-blur-sink", "data"),
            [
                Input("apply-params-button", "n_clicks"),
                Input("apply-dataset-button", "n_clicks"),
            ],
            prevent_initial_call=True,
        )

        # ── FRONTEND_ISSUES_PLAN_2026-05-09 §1.5 C2.2 ──
        # Candidate-pool (S, T, R, P) triple fast-feedback validator. Mirrors
        # the truth table from cascor's _validate_candidate_pool_triple so the
        # user sees violations on input-change instead of on Apply-click.
        # Returns ("invalid_S", "invalid_T", "invalid_R", "feedback text").
        # Server stays authoritative; this is purely UX.
        self.app.clientside_callback(
            """
            function(s_raw, t_raw, r_raw, p_raw) {
                var s = (s_raw === null || s_raw === undefined || s_raw === '') ? null : Number(s_raw);
                var t = (t_raw === null || t_raw === undefined || t_raw === '') ? null : Number(t_raw);
                var r = (r_raw === null || r_raw === undefined || r_raw === '') ? null : Number(r_raw);
                var p = (p_raw === null || p_raw === undefined || p_raw === '') ? null : Number(p_raw);
                if (s === null || t === null || r === null || p === null
                    || isNaN(s) || isNaN(t) || isNaN(r) || isNaN(p)) {
                    return [false, false, false, ''];
                }
                if (!(s >= 1 && s <= p)) {
                    return [true, false, false,
                        'selected_candidates ' + s + ' not in [1, candidate_pool_size=' + p + ']'];
                }
                if (t < 0 || r < 0) {
                    return [false, t < 0, r < 0,
                        'top_candidates and random_candidates must be >= 0 (got T=' + t + ', R=' + r + ')'];
                }
                if (t > s || r > s) {
                    return [false, t > s, r > s,
                        'each component must be <= selected_candidates (S=' + s + ', T=' + t + ', R=' + r + ')'];
                }
                if (t === 0 && r === 0) {
                    return [false, true, true,
                        'top_candidates and random_candidates cannot both be 0'];
                }
                if (t === 0 && r !== s) {
                    return [false, false, true,
                        'with top_candidates=0, random_candidates must equal S=' + s + ' (got R=' + r + ')'];
                }
                if (r === 0 && t !== s) {
                    return [false, true, false,
                        'with random_candidates=0, top_candidates must equal S=' + s + ' (got T=' + t + ')'];
                }
                if (t > 0 && r > 0 && (t + r) !== s) {
                    return [false, true, true,
                        'top_candidates+random_candidates must equal S=' + s
                        + ' (got ' + t + '+' + r + '=' + (t + r) + ')'];
                }
                return [false, false, false, ''];
            }
            """,
            [
                Output("cn-selected-candidates-input", "invalid", allow_duplicate=True),
                Output("cn-top-candidates-input", "invalid", allow_duplicate=True),
                Output("cn-random-candidates-input", "invalid", allow_duplicate=True),
                Output("cn-pool-triple-feedback", "children", allow_duplicate=True),
            ],
            [
                Input("cn-selected-candidates-input", "value"),
                Input("cn-top-candidates-input", "value"),
                Input("cn-random-candidates-input", "value"),
                Input("cn-pool-size-input", "value"),
            ],
            prevent_initial_call=True,
        )

        # ── Layout persistence (active tab) ──
        # Persisted solely via the `layout-state-store` dcc.Store
        # (storage_type="local") and its equality-guarded read (CAN-016a
        # restore) / write (CAN-016a stamp) clientside callbacks defined in the
        # visualization-callback setup. The earlier hand-rolled
        # `localStorage['juniper_canopy_active_tab']` pair was removed in the #1
        # tab-feedback-loop fix: a redundant second persistence system whose
        # mount restore raced the Store, plus an Input→Output self-edge on
        # `active_tab`, drove the tab-toggle loop.

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
        # flight. The dashboard stops firing REST polls and ws-buffer drains
        # the moment Apply is clicked and resumes when the clamp is released.
        #
        # E-3 (training-runtime defects plan §9): the original release relied
        # SOLELY on `applied-params-store` updating — but every failure path of
        # `_apply_parameters_handler` (non-200, 429-exhausted, retries-
        # exhausted) returned `dash.no_update` for that store, so one failed
        # Apply left the clamp stuck true and BOTH intervals disabled until a
        # page refresh: the pre-refresh total freeze of I-1 root cause 4
        # (the evening-502 pattern froze every interval-driven surface,
        # header included). The release is now triple-redundant:
        #   a. the apply_parameters server callback writes apply-in-flight =
        #      False directly on EVERY return path (see
        #      `_apply_in_flight_release`);
        #   b. the applied-params-store clientside release below still fires
        #      on the success path;
        #   c. a clientside watchdog force-clears a clamp older than
        #      APPLY_IN_FLIGHT_MAX_MS — covering the one class no server
        #      response can fix (the callback POST itself failing at the
        #      network level) plus any future stuck path.
        #
        # Clientside callbacks:
        #   1. apply-button click -> apply-in-flight = {in_flight, since}
        #   2. applied-params-store update -> apply-in-flight = false
        #   3. apply-in-flight -> {fast,slow}-update-interval.disabled
        #   4. watchdog tick -> force-clear an over-age in-flight clamp
        # The third callback fires on layout mount (prevent_initial_call=False)
        # so the intervals start in their default enabled state.
        self.app.clientside_callback(
            """
            function(nClicks) {
                if (!nClicks) return window.dash_clientside.no_update;
                // E-3: stamp the click time so the watchdog can age the clamp.
                return {in_flight: true, since: Date.now()};
            }
            """,
            Output("apply-in-flight", "data"),
            Input("apply-params-button", "n_clicks"),
            prevent_initial_call=True,
        )
        self.app.clientside_callback(
            """
            function(appliedData) {
                // applied-params-store updates on the success path; the
                // server callback additionally releases the clamp directly
                // on every path (E-3), so this is belt-and-braces.
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
        # E-3: clientside watchdog — force-release a stuck clamp. Runs on its
        # own always-enabled interval (the clamp disables the fast/slow
        # intervals, so neither can host its own rescue).
        self.app.clientside_callback(
            f"""
            function(n, inFlight) {{
                if (!inFlight || !inFlight.since) return window.dash_clientside.no_update;
                if (Date.now() - inFlight.since > {DashboardConstants.APPLY_IN_FLIGHT_MAX_MS}) {{
                    console.warn("apply-in-flight clamp exceeded {DashboardConstants.APPLY_IN_FLIGHT_MAX_MS}ms; watchdog force-released it (E-3)");
                    return false;
                }}
                return window.dash_clientside.no_update;
            }}
            """,
            Output("apply-in-flight", "data", allow_duplicate=True),
            Input("apply-watchdog-interval", "n_intervals"),
            dash.dependencies.State("apply-in-flight", "data"),
            prevent_initial_call=True,
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
            function(state, currentTab) {
                if (!state || !state.active_tab) return window.dash_clientside.no_update;
                // Equality guard (#1 tab-feedback-loop fix): only restore when
                // the persisted tab differs from the tab already shown. Without
                // it, every Writer-A store stamp echoes back through here and
                // re-asserts active_tab, re-triggering every Input(active_tab)
                // callback and feeding the tab-toggle race.
                if (state.active_tab === currentTab) return window.dash_clientside.no_update;
                return state.active_tab;
            }
            """,
            Output("visualization-tabs", "active_tab", allow_duplicate=True),
            Input("layout-state-store", "data"),
            State("visualization-tabs", "active_tab"),
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

        # N8: re-attach the ws-state-buffer drain (N1 removed it as write-only dead
        # machinery). Latest-only, mirroring the topology drain: hand the freshest
        # training-state frame to fetch_training_state, which prefers it over the REST
        # /api/state poll while the state stream is live.
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var s = window._juniperWsDrain.drainState();
                if (!s) return window.dash_clientside.no_update;
                return s;
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

        # N1: the ws-candidate-progress-buffer drain callback was removed — the
        # store had no Input consumer (same dead-end class as ws-state-buffer).
        # The JS ring buffer (drainCandidateProgress) stays for N8 (wave 4).

        # P2-7 follow-up: drain dataset_swap buffer → ws-dataset-swap-buffer store.
        # The server-side merger in _setup_dataset_swap_observers_callbacks
        # then folds these into dataset-swap-events-store with dedupe so
        # WS-push and slow-poll converge to the same authoritative list.
        self.app.clientside_callback(
            """
            function(n) {
                if (!window._juniperWsDrain) return window.dash_clientside.no_update;
                var events = window._juniperWsDrain.drainDatasetSwaps();
                if (!events || events.length === 0) return window.dash_clientside.no_update;
                window._juniperWsDrain._gen++;
                return {events: events, gen: window._juniperWsDrain._gen, last_drain_ms: Date.now()};
            }
            """,
            Output("ws-dataset-swap-buffer", "data"),
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

        # N8: WS-data liveness → ws-liveness-store. Each fast tick, compare the
        # bridge's per-class frame-arrival age (peekLiveness) against
        # WS_LIVENESS_WINDOW_MS and emit BOOLEANS ONLY, so the store value changes
        # only on a live↔stale transition (a fresh age of, say, 120 ms one tick and
        # 340 ms the next must not churn the store and re-trigger every downstream
        # poll). A null age (no frame of that class ever seen) reads stale, so a fresh
        # tab polls REST until the WS actually delivers — the anti-starvation posture.
        # This deliberately consults ONLY the ageing clocks, never the sticky
        # metricsReceived/topologyReceived flags that caused the N1 starvation.
        self.app.clientside_callback(
            f"""
            function(n) {{
                if (!window._juniperWsDrain || !window._juniperWsDrain.peekLiveness) {{
                    return window.dash_clientside.no_update;
                }}
                var live = window._juniperWsDrain.peekLiveness();
                var W = {DashboardConstants.WS_LIVENESS_WINDOW_MS};
                return {{
                    metrics_live: (live.metrics_age_ms !== null && live.metrics_age_ms <= W),
                    state_live: (live.state_age_ms !== null && live.state_age_ms <= W)
                }};
            }}
            """,
            Output("ws-liveness-store", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )

        # N2: poll canopy→cascor stream health into stream-health-store on the
        # slow interval. Server-side (not a clientside peek) because the truth
        # lives in the backend relay/supervisor liveness state, not in the
        # browser bridge.
        @self.app.callback(
            Output("stream-health-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )
        def update_stream_health(n):
            """Fetch /api/stream_health for the degraded-mode badge dimension."""
            return self._update_stream_health_handler(n)

        # Phase B: Connection indicator badge (4-state: connected/reconnecting/offline/demo,
        # N2: + upstream stream-health dimension — degraded/reconnecting downgrade a green badge)
        self.app.clientside_callback(
            CONNECTION_INDICATOR_JS,
            Output("ws-connection-indicator", "children"),
            Output("ws-connection-indicator", "style"),
            Input("ws-connection-status", "data"),
            Input("stream-health-store", "data"),
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
        # N8 (training-runtime defects plan §4 I-1, posture O1 / Q6): the O1 half —
        # a liveness-gated REST poll. It fires on EVERY fast tick (the interval Input
        # is the sole trigger, so it can never be starved) and reads the liveness
        # signal as STATE: while the metrics stream is fresh (metrics_live) in the
        # real-time window view it returns ``no_update`` (the WS-primary append
        # callback below owns the store), and the instant the stream goes stale it
        # re-engages the N1 REST poll on the next tick — the anti-sticky reset.
        #
        # CRITICAL (Dash execution model): ws-metrics-buffer is deliberately NOT an
        # Input here. Its clientside producer returns ``no_update`` whenever the WS is
        # quiet, and a chained Input whose producer no_updates makes Dash SKIP this
        # interval-only callback for that tick — which silently re-creates the I-1
        # starvation (the poll would fire only on WS pushes). The WS buffer is instead
        # consumed by a separate ``allow_duplicate`` append callback triggered ONLY by
        # ws-metrics-buffer. ws-liveness-store rides as State (never as an Input) for
        # the same reason.
        @self.app.callback(
            Output("metrics-panel-metrics-store", "data"),
            Input("fast-update-interval", "n_intervals"),
            Input("metrics-panel-display-mode-store", "data"),
            dash.dependencies.State("ws-liveness-store", "data"),
            dash.dependencies.State("metrics-panel-metrics-store", "data"),
            prevent_initial_call=False,
        )
        def update_metrics_store(n, display_mode_state, ws_liveness, current_metrics):
            """Liveness-gated REST poll for the metrics store (N8 O1 half)."""
            try:
                ctx = dash.callback_context
                trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""
            except dash.exceptions.MissingCallbackContextException:
                trigger = ""  # direct invocation (tests) — treated like a mount/mode-switch fetch
            ws_live = bool(ws_liveness and ws_liveness.get("metrics_live"))
            return self._update_metrics_store_handler(
                n=n,
                display_mode_state=display_mode_state,
                current_metrics=current_metrics,
                trigger=trigger,
                ws_live=ws_live,
            )

        # N8 (posture O3 half): WS-PRIMARY append. Triggered ONLY by a ws-metrics-buffer
        # change — which the clientside drain emits only when it actually drained events
        # (a WS frame arrived). So this callback fires exactly on WS pushes and is the
        # sole path that writes WS data into the store; when the WS is quiet it simply
        # does not fire (and the poll above carries the store). ``allow_duplicate`` lets
        # it co-own the store's Output with the poll; ``prevent_initial_call=True`` is
        # required for duplicate outputs. History-analysis modes (full/hidden_units)
        # opt out (Q6: they are non-real-time and want the complete REST history).
        @self.app.callback(
            Output("metrics-panel-metrics-store", "data", allow_duplicate=True),
            Input("ws-metrics-buffer", "data"),
            dash.dependencies.State("metrics-panel-display-mode-store", "data"),
            dash.dependencies.State("metrics-panel-metrics-store", "data"),
            prevent_initial_call=True,
        )
        def append_ws_metrics_store(ws_metrics_buffer, display_mode_state, current_metrics):
            """Accumulate drained WS metrics onto the store (N8 O3 half)."""
            return self._append_ws_metrics_store_handler(ws_metrics_buffer=ws_metrics_buffer, display_mode_state=display_mode_state, current_metrics=current_metrics)

        # PERF-CN-01: prevent_initial_call=False — must hit /api/network/topology
        # on mount (when the topology tab is active) so the network visualizer
        # has data before the first interval tick.
        @self.app.callback(
            Output("network-visualizer-topology-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("ws-topology-buffer", "data"),
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=False,
        )
        def update_topology_store(n, ws_topology, active_tab):
            """Fetch topology from API or accept WebSocket push.

            OI-2: WebSocket topology pushes (from cascade_add events) take
            priority over REST polling for near-real-time updates.
            N1 (training-runtime defects plan §4 I-2, posture O2): the REST
            fallback is no longer gated on WS connection state — the sticky
            ``topologyReceived`` gate starved long-lived tabs when ``cascade_add``
            frames stopped arriving. The poll stays tab-gated on the slow
            interval (see _update_topology_store_handler); the ``active_tab``
            Input refetches on tab switch. This is the correctness bridge until
            the WS-primary target lands (Q6/C6/N8).
            """
            ctx = dash.callback_context
            trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            # WebSocket push takes priority — provides near-real-time updates
            if "ws-topology-buffer" in trigger and ws_topology:
                from backend.cascor_service_adapter import CascorServiceAdapter

                # Defense against pre-fix cascor servers that broadcast a
                # count-only stub on cascade_add (``hidden_units`` as int).
                # Passing such a payload to ``_transform_topology`` collapses
                # the topology to inputs+outputs and zero hidden nodes (the
                # transform's ``isinstance(int, list) is False`` path drops
                # every hidden node and every cascade connection). When we
                # detect a stub, fall through to REST so we get a
                # structurally complete payload from /api/topology.
                if not CascorServiceAdapter._is_complete_topology(ws_topology):
                    return self._update_topology_store_handler(n=n, active_tab=active_tab)
                return CascorServiceAdapter._transform_topology(ws_topology)

            # REST fallback — only poll when topology tab is active. Deliberately
            # NOT WS-gated (N1): the former sticky topologyReceived gate meant
            # neither push nor poll updated the store once cascade_add frames
            # stopped arriving. cascade_add push above remains the fast path.
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

        # PERF-CN-01: prevent_initial_call=False — must hit the workers API on
        # mount (when the Workers tab is active) so the roster renders before the
        # first interval tick.
        # N10 (training-runtime defects plan §4-U U-5): the Workers tab polls on
        # the shared slow interval and is tab-gated to "workers" (the topology-tab
        # N1 posture), replacing the panel's former always-on 5 s self-interval.
        @self.app.callback(
            Output("worker-panel-workers-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            Input("visualization-tabs", "active_tab"),
            prevent_initial_call=False,
        )
        def update_workers_store(n, active_tab):
            """Fetch worker roster + aggregate stats and update the worker store."""
            return self._update_workers_store_handler(n=n, active_tab=active_tab)

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
            # F-CANOPY-029: this is a CallbackContextAdapter (frontend/callback_context.py),
            # NOT dash.callback_context -- it exposes get_triggered_id(), and reading the
            # raw-dash ``.triggered_id`` attribute on it raised AttributeError on every
            # click, so Dash returned 500 and this modal could never open. The adapter
            # swallows the underlying dash lookup's errors internally and returns None.
            trigger = ctx.get_triggered_id()
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

        @self.app.callback(
            [
                Output("dataset-plotter-load-status", "children"),
                Output("dataset-plotter-dataset-store", "data", allow_duplicate=True),
            ],
            Input("dataset-plotter-load-selected-btn", "n_clicks"),
            dash.dependencies.State("dataset-plotter-dataset-selector", "value"),
            prevent_initial_call=True,
        )
        def load_selected_dataset(n_clicks, generator):
            return self._load_selected_dataset_handler(n_clicks, generator)

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
            response = requests.post(url, json=payload, timeout=DashboardConstants.API_TIMEOUT_SECONDS + 5, headers=internal_api_headers())
            if response.ok:
                return "✅ Dataset generated", response.json()
            return f"❌ {response.json().get('error', 'Failed')}", dash.no_update
        except Exception as e:
            self.logger.warning(f"Dataset generation failed: {e}")
            return f"❌ Error: {e}", dash.no_update

    def _load_selected_dataset_handler(self, n_clicks, generator):
        """Load the dataset-plotter selector's chosen generator into the active dataset.

        Spiral is produced locally by the demo backend; every other generator is
        proxied to JuniperData by POST /api/dataset/generate (which returns 503 when
        the service is unavailable). The selector's value reaches the app here as a
        callback State (the wiring the L1 control-graph lint requires).
        """
        if not n_clicks or not generator:
            return dash.no_update, dash.no_update
        try:
            response = requests.post(
                self._api_url("/api/dataset/generate"),
                json={"generator": generator},
                timeout=DashboardConstants.API_TIMEOUT_SECONDS + 5,
                headers=internal_api_headers(),
            )
            if response.ok:
                return f"✅ Loaded '{generator}'", response.json()
            try:
                err = response.json().get("error", f"HTTP {response.status_code}")
            except Exception:
                err = f"HTTP {response.status_code}"
            return f"❌ {err}", dash.no_update
        except Exception as e:
            self.logger.warning(f"Load selected dataset failed: {e}")
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
            response = requests.post(url, files=files, timeout=DashboardConstants.API_TIMEOUT_SECONDS + 10, headers=internal_api_headers())
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
            response = requests.post(url, json={"url": url_value.strip()}, timeout=DashboardConstants.API_TIMEOUT_SECONDS + 15, headers=internal_api_headers())
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
                    # A1-iv-3c: the resolved one-shot Start dataset-ref body (or None); the
                    # clientside JS reads it as its 8th positional arg, the server-side handler
                    # as ``oneshot_start_body``. Appended last so existing arg positions hold.
                    dash.dependencies.State("oneshot-start-params-store", "data"),
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
                    # A1-iv-3c: the resolved one-shot Start dataset-ref body (or None); the
                    # clientside JS reads it as its 8th positional arg, the server-side handler
                    # as ``oneshot_start_body``. Appended last so existing arg positions hold.
                    dash.dependencies.State("oneshot-start-params-store", "data"),
                ],
                prevent_initial_call=True,
            )
            def handle_training_buttons(start_clicks, pause_clicks, stop_clicks, resume_clicks, reset_clicks, last_click, button_states, oneshot_start_body=None, **kwargs):
                """Handle training control button clicks with debouncing and optimistic UI."""
                return self._handle_training_buttons_handler(
                    start_clicks=start_clicks,
                    pause_clicks=pause_clicks,
                    stop_clicks=stop_clicks,
                    resume_clicks=resume_clicks,
                    reset_clicks=reset_clicks,
                    last_click=last_click,
                    button_states=button_states,
                    oneshot_start_body=oneshot_start_body,
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

        # Surface a rejected training-control command as a dismissable danger
        # alert. Registered unconditionally (outside the WS-vs-REST flag branch)
        # because BOTH transports write the outcome into training-control-action:
        # the server-side handler directly, the Phase D clientside JS via
        # set_props once the async WS/REST command resolves. See
        # notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md.
        @self.app.callback(
            Output("training-control-outcome-alert", "children"),
            Input("training-control-action", "data"),
            prevent_initial_call=True,
        )
        def surface_training_control_outcome(action):
            """Render the danger alert on failure; clear it on success."""
            return self._surface_training_control_outcome_handler(action=action)

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
            [
                Input("button-states", "data"),
                # A1-iv-5 / D8: re-evaluate the Start gate when the selected model changes — a
                # non-live model is shown + selectable but NOT trainable (§5.7), so Start is
                # force-disabled for it. Reading it in the SAME callback that owns
                # ``start-button.disabled`` combines the training-state and model-status factors in
                # one place — no racy second writer.
                Input("model-selection-store", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_button_appearance(button_states, model_key):
            """Update button states (disabled/loading) with visual feedback + the D8 Train-gate."""
            return self._update_button_appearance_handler(button_states=button_states, model_key=model_key)

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
                # E-3: release the apply-in-flight clamp on EVERY return path.
                # applied-params-store stays no_update on failure (it must only
                # record genuinely-applied params), so it cannot double as the
                # release signal — that reliance is what froze the dashboard.
                Output("apply-in-flight", "data", allow_duplicate=True),
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
                # init_output_weights (output-layer weight init: zero|random)
                dash.dependencies.State("nn-init-output-weights-dropdown", "value"),
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
            nn_init_output_weights,
        ):
            """Apply parameters to backend, update applied store, and ALWAYS release the in-flight clamp (E-3)."""
            try:
                store_value, status_msg = self._apply_parameters_handler(
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
                    nn_init_output_weights,
                )
            except Exception as e:  # E-3: a raising handler must not leave the clamp stuck
                self.logger.error(f"apply_parameters handler raised: {e}", exc_info=True)
                store_value, status_msg = dash.no_update, f"Error: {str(e)[:40]}"
            return store_value, status_msg, self._apply_in_flight_release(n_clicks)

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

        # ── FRONTEND_ISSUES_PLAN_2026-05-09 §3.5.1 + §3.5.2 P1 — Issue #3 Phase 1 ──
        # Apply Dataset / Cancel pending dataset change / banner visibility.

        @self.app.callback(
            [
                Output("pending-dataset-banner", "is_open", allow_duplicate=True),
                # N3 (T4): staging failures were silent (return dash.no_update);
                # surface them instead of leaving the operator guessing.
                Output("dataset-stage-outcome-alert", "children"),
            ],
            Input("apply-dataset-button", "n_clicks"),
            [
                dash.dependencies.State("nn-dataset-type-dropdown", "value"),
                dash.dependencies.State("nn-dataset-elements-input", "value"),
                dash.dependencies.State("nn-dataset-noise-input", "value"),
                dash.dependencies.State("nn-spiral-rotations-input", "value"),
                dash.dependencies.State("nn-spiral-number-input", "value"),
                # N7 (I-7): the schema-driven inputs for a non-spiral generator (read directly, so
                # there is no store-race with the Apply click). Empty for spiral / no-param types.
                dash.dependencies.State({"type": "nn-gen-param", "name": dash.ALL}, "value"),
                dash.dependencies.State({"type": "nn-gen-param", "name": dash.ALL}, "id"),
            ],
            prevent_initial_call=True,
        )
        def apply_dataset(n_clicks, dataset_type, n_samples, noise, rotations, n_spirals, gen_values, gen_ids):
            return self._apply_dataset_handler(n_clicks, dataset_type, n_samples, noise, rotations, n_spirals, gen_values, gen_ids)

        @self.app.callback(
            Output("pending-dataset-banner", "is_open", allow_duplicate=True),
            Input("cancel-pending-dataset-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def cancel_pending_dataset(n_clicks):
            """DELETE /api/cancel_pending_dataset; close the banner on success."""
            if not n_clicks:
                return dash.no_update
            try:
                resp = requests.delete(
                    self._api_url("/api/cancel_pending_dataset"),
                    timeout=DashboardConstants.DASHBOARD_LONG_POST_TIMEOUT,
                    headers=internal_api_headers(),
                )
                if resp.status_code == 200:
                    self.logger.info("Pending dataset change discarded")
                    return False  # close banner
                self.logger.warning("Cancel pending dataset failed: %s %s", resp.status_code, resp.text[:200])
                return dash.no_update
            except requests.RequestException as exc:
                self.logger.warning("Cancel pending dataset exception: %s", exc)
                return dash.no_update

        # N3 (I-6): the "Stop & Restart with new dataset" button
        # (``restart-with-new-dataset-button``) is now wired in
        # ``_setup_restart_orchestration_callbacks`` — it opens the confirm modal
        # (Q3/Q4) instead of firing the pre-N3 feedback-free
        # ``POST /api/train/start?reset=true``. The confirm flow runs the promised
        # stop → await stopped → start(staged) sequence and surfaces every step's
        # outcome. ``reconcile_pending_dataset_banner`` (below) still closes the
        # banner once cascor clears ``pending_dataset`` after a successful restart.

        @self.app.callback(
            Output("pending-dataset-banner", "is_open", allow_duplicate=True),
            Input("slow-update-interval", "n_intervals"),
            prevent_initial_call=True,
        )
        def reconcile_pending_dataset_banner(n_intervals):
            """Poll /api/status; reflect cascor-side pending_dataset state.

            Catches the case where the staged config was cleared by a successful
            ``start_training`` (cold-swap completed) or by another tab — keeps
            the banner in sync with the source of truth without us having to
            also wire it from the start/stop callbacks.
            """
            try:
                resp = requests.get(
                    self._api_url("/api/status"),
                    timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                    headers=internal_api_headers(),
                )
                if resp.status_code != 200:
                    return dash.no_update
                pending = resp.json().get("pending_dataset")
                return bool(pending)
            except requests.RequestException:
                return dash.no_update

    def _setup_experimental_functions_callbacks(self):
        """Phase 2 P2-4 (Issue #3): Experimental Functions gate UI <-> cascor.

        Two callbacks:

        1. **Load reconciliation** (fires once on mount via ``params-init-interval``):
           GETs canopy's ``/api/admin/experimental_functions`` proxy and writes
           the cascor-authoritative state into the Switch + Store. F2.10 — the
           Switch's last-session persistence is overridden if cascor's gate is
           closed (e.g., env-var lockdown).

        2. **User-toggle handler** (fires on Switch change):
           POSTs the new value to canopy's proxy. If cascor's response
           ``enabled`` differs from the requested value, the Switch is
           reverted to the authoritative state and a warning ``dbc.Alert``
           explains the override. On network / 502 errors the Switch
           reverts to its last-stored value and a danger alert surfaces.
        """

        @self.app.callback(
            [
                Output("experimental-functions-toggle", "value", allow_duplicate=True),
                Output("experimental-flags-store", "data", allow_duplicate=True),
                Output("experimental-functions-alert", "children", allow_duplicate=True),
            ],
            Input("params-init-interval", "n_intervals"),
            prevent_initial_call="initial_duplicate",
        )
        def load_reconcile_experimental_functions(n_intervals):
            """Page-load sync against cascor's authoritative gate state.

            ``params-init-interval`` is the canonical one-shot-on-mount
            trigger used elsewhere in the dashboard (e.g., params load).
            Fires once per session; ``max_intervals=1`` on the Interval
            component caps additional fires.
            """
            try:
                resp = requests.get(
                    self._api_url("/api/admin/experimental_functions"),
                    timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                    headers=internal_api_headers(),
                )
                if resp.status_code != 200:
                    # Defensive default — if cascor is unreachable on load,
                    # show the toggle as OFF (F2.10 safe default) and surface
                    # a soft warning so the user knows the toggle is local-only.
                    self.logger.warning("Experimental functions load failed: %s %s", resp.status_code, resp.text[:200])
                    return False, {"experimental_functions": False}, dbc.Alert("Could not reach backend; experimental functions disabled.", color="warning", duration=5000, dismissable=True)
                authoritative = bool(resp.json().get("data", {}).get("enabled", False))
                return authoritative, {"experimental_functions": authoritative}, None
            except requests.RequestException as exc:
                self.logger.warning("Experimental functions load exception: %s", exc)
                return False, {"experimental_functions": False}, dbc.Alert("Backend unreachable; experimental functions disabled.", color="warning", duration=5000, dismissable=True)

        @self.app.callback(
            [
                Output("experimental-functions-toggle", "value", allow_duplicate=True),
                Output("experimental-flags-store", "data", allow_duplicate=True),
                Output("experimental-functions-alert", "children", allow_duplicate=True),
            ],
            Input("experimental-functions-toggle", "value"),
            State("experimental-flags-store", "data"),
            prevent_initial_call=True,
        )
        def handle_experimental_functions_toggle(switch_value, store_data):
            """POST the new toggle value to cascor and reconcile UI state.

            F2.10 server-authoritative: the response's ``enabled`` value is
            what the UI must reflect, even if it differs from the request.
            """
            requested = bool(switch_value)
            try:
                resp = requests.post(
                    self._api_url("/api/admin/experimental_functions"),
                    json={"enabled": requested},
                    timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                    headers=internal_api_headers(),
                )
                if resp.status_code != 200:
                    # Revert to last-known-good (from the store) and surface
                    # a danger alert with cascor's error detail.
                    last_known = bool((store_data or {}).get("experimental_functions", False))
                    detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
                    self.logger.warning("Experimental functions toggle rejected: %s", detail)
                    return (
                        last_known,
                        {"experimental_functions": last_known},
                        dbc.Alert(f"Backend rejected toggle: {detail}", color="danger", duration=5000, dismissable=True),
                    )
                authoritative = bool(resp.json().get("data", {}).get("enabled", False))
                alert = None
                if authoritative != requested:
                    alert = dbc.Alert(
                        f"Server returned {authoritative!r}; the gate is server-authoritative (F2.10).",
                        color="warning",
                        duration=5000,
                        dismissable=True,
                    )
                return authoritative, {"experimental_functions": authoritative}, alert
            except requests.RequestException as exc:
                last_known = bool((store_data or {}).get("experimental_functions", False))
                self.logger.warning("Experimental functions toggle exception: %s", exc)
                return (
                    last_known,
                    {"experimental_functions": last_known},
                    dbc.Alert(f"Backend unreachable: {exc}", color="danger", duration=5000, dismissable=True),
                )

    def _setup_live_dataset_switch_callbacks(self):
        """Phase 2 P2-5 (Issue #3): Live Dataset Switch flow.

        Seven callbacks, each a thin wrapper around a class-level
        ``_*_handler`` method (P2-6 refactor — handlers are unit-tested
        in ``tests/unit/frontend/test_live_dataset_switch_handlers.py``):

        1. Training status mirror — refresh ``training-status-store``
           from ``/api/status`` each ``fast-update-interval`` tick.
        2. Gate — disable Live Switch button unless experimental flag
           AND training is running.
        3. Open warning modal + populate dataset summary.
        3b. Stop & Restart fallback closes modal (minimal interpretation).
        4. Accept → POST /api/live_dataset_swap → outcome alert.
        4b. Open progress alert immediately on Accept (split so spinner
            shows before the 5–30 s POST returns).
        5. Cancel during swap → DELETE /api/live_dataset_swap.

        Full design rationale lives in the §4.2 / §4.3 spec sections
        and the P2-5 PR (#275).
        """

        @self.app.callback(
            Output("training-status-store", "data"),
            Input("fast-update-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def update_training_status_store(n_intervals):
            return self._update_training_status_store_handler(n_intervals=n_intervals)

        @self.app.callback(
            Output("live-dataset-switch-button", "disabled"),
            Input("experimental-flags-store", "data"),
            Input("training-status-store", "data"),
            prevent_initial_call=False,
        )
        def gate_live_switch_button(flags, status):
            return self._gate_live_switch_button_handler(flags=flags, status=status)

        @self.app.callback(
            [
                Output("live-switch-modal", "is_open", allow_duplicate=True),
                Output("live-switch-dataset-summary", "children"),
            ],
            Input("live-dataset-switch-button", "n_clicks"),
            State("nn-dataset-type-dropdown", "value"),
            State("nn-dataset-elements-input", "value"),
            State("nn-dataset-noise-input", "value"),
            State("nn-spiral-number-input", "value"),
            State("nn-spiral-rotations-input", "value"),
            prevent_initial_call=True,
        )
        def open_live_switch_modal(n_clicks, dataset_type, n_samples, noise, n_spirals, rotations):
            return self._open_live_switch_modal_handler(n_clicks=n_clicks, dataset_type=dataset_type, n_samples=n_samples, noise=noise, n_spirals=n_spirals, rotations=rotations)

        @self.app.callback(
            Output("live-switch-modal", "is_open", allow_duplicate=True),
            Input("live-switch-fallback-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def close_live_switch_modal_on_fallback(n_clicks):
            return self._close_live_switch_modal_on_fallback_handler(n_clicks=n_clicks)

        # P2-5 follow-up A+B: when the user dismisses the Live Switch
        # modal with "Return to Stop & Restart", scroll the Apply
        # Dataset button into view (A) and briefly pulse it (B) so the
        # cold-swap affordance is visually surfaced. Pure client-side —
        # DOM mutation + setTimeout, no server round-trip. Removing
        # then re-adding the class restarts the CSS animation, so a
        # second cancel-click within the animation window re-triggers
        # the pulse cleanly.
        self.app.clientside_callback(
            """
            function(n_clicks) {
                if (!n_clicks) return window.dash_clientside.no_update;
                var btn = document.getElementById('apply-dataset-button');
                if (!btn) return window.dash_clientside.no_update;
                btn.classList.remove('attention-pulse');
                // Force a reflow so the class re-add restarts the animation
                // even if the user clicks cancel twice in quick succession.
                void btn.offsetWidth;
                btn.scrollIntoView({behavior: 'smooth', block: 'center'});
                btn.classList.add('attention-pulse');
                setTimeout(function() {
                    btn.classList.remove('attention-pulse');
                }, 1100);
                return window.dash_clientside.no_update;
            }
            """,
            Output("live-switch-fallback-sink", "data"),
            Input("live-switch-fallback-button", "n_clicks"),
            prevent_initial_call=True,
        )

        @self.app.callback(
            [
                Output("live-switch-modal", "is_open", allow_duplicate=True),
                Output("live-switch-progress-alert", "is_open", allow_duplicate=True),
                Output("live-switch-outcome-alert", "children"),
                Output("live-swap-in-flight-store", "data", allow_duplicate=True),
            ],
            Input("live-switch-accept-button", "n_clicks"),
            State("nn-dataset-type-dropdown", "value"),
            State("nn-dataset-elements-input", "value"),
            State("nn-dataset-noise-input", "value"),
            State("nn-spiral-number-input", "value"),
            State("nn-spiral-rotations-input", "value"),
            prevent_initial_call=True,
        )
        def accept_live_switch(n_clicks, dataset_type, n_samples, noise, n_spirals, rotations):
            return self._accept_live_switch_handler(n_clicks=n_clicks, dataset_type=dataset_type, n_samples=n_samples, noise=noise, n_spirals=n_spirals, rotations=rotations)

        @self.app.callback(
            [
                Output("live-switch-progress-alert", "is_open", allow_duplicate=True),
                Output("live-swap-in-flight-store", "data", allow_duplicate=True),
            ],
            Input("live-switch-accept-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def open_progress_alert_on_accept(n_clicks):
            return self._open_progress_alert_on_accept_handler(n_clicks=n_clicks)

        @self.app.callback(
            Output("live-switch-outcome-alert", "children", allow_duplicate=True),
            Input("live-switch-cancel-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def cancel_live_switch(n_clicks):
            return self._cancel_live_switch_handler(n_clicks=n_clicks)

    def _setup_restart_orchestration_callbacks(self):
        """N3 (canopy training-runtime defects plan, I-6): the cold-swap restart
        confirm modal (Q3/Q4) + the stop → await stopped → start(staged)
        orchestration that replaces the pre-N3 feedback-free callback.

        Five thin callbacks, each delegating to a class-level ``_*_handler`` so the
        branch logic is unit-testable by direct invocation:

        1. Open the confirm modal on the banner's "Stop & Restart" button; populate
           the read-only dataset summary + granular verify section and reset the
           start-fresh toggle to its default OFF (Q4) and the verify section closed.
        2. Toggle the expandable granular verify section (Q3).
        3. Cancel — close the modal.
        4. Open the progress spinner the instant Confirm is clicked (split so the
           spinner shows before the bounded stop→await→start POST returns).
        5. Execute — POST /api/train/restart {start_fresh, reset}; render every
           step's outcome (success incl. instant-convergence, or per-step failure
           with the upstream detail); close the modal + progress; keep the pending
           banner open on failure, close it on success.
        """

        @self.app.callback(
            [
                Output("restart-confirm-modal", "is_open", allow_duplicate=True),
                Output("restart-confirm-summary", "children", allow_duplicate=True),
                Output("restart-start-fresh-toggle", "value", allow_duplicate=True),
                Output("restart-granular-collapse", "is_open", allow_duplicate=True),
                Output("restart-granular-context", "children"),
                # N3b: editable staged-dataset field values (defaults on open).
                Output("restart-ds-type", "value"),
                Output("restart-ds-samples", "value"),
                Output("restart-ds-noise", "value"),
                Output("restart-ds-rotations", "value"),
                Output("restart-ds-spirals", "value"),
                # N3b: editable training-param field values (backend-seeded, clamped).
                Output("restart-p-nn-learning-rate", "value"),
                Output("restart-p-nn-max-hidden-units", "value"),
                Output("restart-p-nn-patience", "value"),
                Output("restart-p-cn-pool-size", "value"),
                Output("restart-p-cn-selected", "value"),
                Output("restart-p-cn-corr-thresh", "value"),
                # N3b: the baseline captured on open for the Confirm-time diff.
                Output("restart-modal-baseline", "data"),
            ],
            Input("restart-with-new-dataset-button", "n_clicks"),
            [
                dash.dependencies.State("nn-dataset-type-dropdown", "value"),
                dash.dependencies.State("nn-dataset-elements-input", "value"),
                dash.dependencies.State("nn-dataset-noise-input", "value"),
                dash.dependencies.State("nn-spiral-rotations-input", "value"),
                dash.dependencies.State("nn-spiral-number-input", "value"),
            ],
            prevent_initial_call=True,
        )
        def open_restart_confirm_modal(n_clicks, dataset_type, n_samples, noise, rotations, n_spirals):
            return self._open_restart_confirm_modal_handler(n_clicks=n_clicks, dataset_type=dataset_type, n_samples=n_samples, noise=noise, rotations=rotations, n_spirals=n_spirals)

        @self.app.callback(
            Output("restart-granular-collapse", "is_open", allow_duplicate=True),
            Input("restart-granular-toggle", "n_clicks"),
            dash.dependencies.State("restart-granular-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_restart_granular(n_clicks, is_open):
            if not n_clicks:
                return dash.no_update
            return not is_open

        # N3b: keep the "Restart plan" summary in sync with the operator's in-place
        # edits — any change to a dataset or param field re-renders the summary so
        # every modification is reflected before Confirm (plan §4 I-6 item 4). The
        # baseline (captured on open) is read as State so the summary shows param
        # deltas, not just current values.
        @self.app.callback(
            Output("restart-confirm-summary", "children", allow_duplicate=True),
            [
                Input("restart-ds-type", "value"),
                Input("restart-ds-samples", "value"),
                Input("restart-ds-noise", "value"),
                Input("restart-ds-rotations", "value"),
                Input("restart-ds-spirals", "value"),
                Input("restart-p-nn-learning-rate", "value"),
                Input("restart-p-nn-max-hidden-units", "value"),
                Input("restart-p-nn-patience", "value"),
                Input("restart-p-cn-pool-size", "value"),
                Input("restart-p-cn-selected", "value"),
                Input("restart-p-cn-corr-thresh", "value"),
            ],
            dash.dependencies.State("restart-modal-baseline", "data"),
            prevent_initial_call=True,
        )
        def refresh_restart_summary(ds_type, ds_samples, ds_noise, ds_rot, ds_spirals, p_lr, p_hu, p_pat, p_pool, p_sel, p_corr, baseline):
            dataset_vals = {"dataset_type": ds_type, "n_samples": ds_samples, "noise": ds_noise, "rotations": ds_rot, "n_spirals": ds_spirals}
            param_vals = {"nn_learning_rate": p_lr, "nn_max_hidden_units": p_hu, "nn_patience": p_pat, "cn_pool_size": p_pool, "cn_selected_candidates": p_sel, "cn_correlation_threshold": p_corr}
            return self._build_restart_summary(dataset_vals, param_vals, baseline)

        @self.app.callback(
            Output("restart-confirm-modal", "is_open", allow_duplicate=True),
            Input("restart-cancel-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def cancel_restart_confirm(n_clicks):
            if not n_clicks:
                return dash.no_update
            return False

        @self.app.callback(
            Output("restart-progress-alert", "is_open", allow_duplicate=True),
            Input("restart-confirm-button", "n_clicks"),
            prevent_initial_call=True,
        )
        def open_restart_progress(n_clicks):
            if not n_clicks:
                return dash.no_update
            return True

        @self.app.callback(
            [
                Output("restart-confirm-modal", "is_open", allow_duplicate=True),
                Output("restart-progress-alert", "is_open", allow_duplicate=True),
                Output("restart-outcome-alert", "children"),
                Output("pending-dataset-banner", "is_open", allow_duplicate=True),
            ],
            Input("restart-confirm-button", "n_clicks"),
            [
                dash.dependencies.State("restart-start-fresh-toggle", "value"),
                # N3b: the operator's in-place edits + the open-time baseline.
                dash.dependencies.State("restart-ds-type", "value"),
                dash.dependencies.State("restart-ds-samples", "value"),
                dash.dependencies.State("restart-ds-noise", "value"),
                dash.dependencies.State("restart-ds-rotations", "value"),
                dash.dependencies.State("restart-ds-spirals", "value"),
                dash.dependencies.State("restart-p-nn-learning-rate", "value"),
                dash.dependencies.State("restart-p-nn-max-hidden-units", "value"),
                dash.dependencies.State("restart-p-nn-patience", "value"),
                dash.dependencies.State("restart-p-cn-pool-size", "value"),
                dash.dependencies.State("restart-p-cn-selected", "value"),
                dash.dependencies.State("restart-p-cn-corr-thresh", "value"),
                dash.dependencies.State("restart-modal-baseline", "data"),
            ],
            prevent_initial_call=True,
        )
        def execute_restart(n_clicks, start_fresh, ds_type, ds_samples, ds_noise, ds_rot, ds_spirals, p_lr, p_hu, p_pat, p_pool, p_sel, p_corr, baseline):
            dataset_vals = {"dataset_type": ds_type, "n_samples": ds_samples, "noise": ds_noise, "rotations": ds_rot, "n_spirals": ds_spirals}
            param_vals = {"nn_learning_rate": p_lr, "nn_max_hidden_units": p_hu, "nn_patience": p_pat, "cn_pool_size": p_pool, "cn_selected_candidates": p_sel, "cn_correlation_threshold": p_corr}
            return self._execute_restart_handler(n_clicks=n_clicks, start_fresh=start_fresh, dataset_vals=dataset_vals, param_vals=param_vals, baseline=baseline)

    # ------------------------------------------------------------------
    # N3 (I-6) restart-orchestration handlers — extracted from the
    # ``_setup_restart_orchestration_callbacks`` closures so each branch is
    # unit-testable via direct invocation (mirrors the P2-5/P2-6 live-switch
    # handler pattern). See tests/unit/frontend/test_restart_orchestration_handlers.py.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # N3b (I-6 / Q3) restart-modal granular-MODIFY builders + helpers.
    # The N3 granular section was read-only VERIFY; N3b makes the staged
    # dataset config and a focused set of restart-relevant training params
    # editable in place. Layout builders are static (fields exist in the
    # tree at registration time; values are populated on open); the diff /
    # re-stage / apply logic is factored into unit-testable helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def _build_restart_dataset_fields():
        """Editable staged-dataset config (the ``StageDatasetRequest`` fields).

        Distinct ids from the sidebar's ``nn-dataset-*`` inputs (Dash ids are
        global). Populated on open from the currently staged / current values; an
        edit re-stages via the existing ``/api/stage_dataset`` route on Confirm.
        """

        def _num(label, _id, step, minimum=None):
            return html.Div(
                [
                    dbc.Label(label, html_for=_id, size="sm", className="mb-0"),
                    dbc.Input(id=_id, type="number", step=step, min=minimum, size="sm", debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS, className="mb-2"),
                ]
            )

        return html.Div(
            [
                dbc.Label("Type", html_for="restart-ds-type", size="sm", className="mb-0"),
                dcc.Dropdown(id="restart-ds-type", options=gated_dataset_options(DEFAULT_MODEL_KEY), value=DEFAULT_DATASET_TYPE, clearable=False, className="mb-2"),
                _num("Samples", "restart-ds-samples", 1, 1),
                _num("Noise", "restart-ds-noise", "any", 0),
                _num("Spiral rotations", "restart-ds-rotations", "any", 0),
                _num("Spirals", "restart-ds-spirals", 1, 1),
            ]
        )

    @staticmethod
    def _build_restart_param_fields():
        """Editable, restart-relevant training params (all CascorPatchBounds-governed).

        Grouped Network / Candidate. Values are backend-seeded (clamped) on open;
        an edit is clamped + applied through N5's ``/api/set_params`` machinery
        before the stop→await→start orchestration.
        """

        def _num(label, _id, step, minimum=None):
            return html.Div(
                [
                    dbc.Label(label, html_for=_id, size="sm", className="mb-0"),
                    dbc.Input(id=_id, type="number", step=step, min=minimum, size="sm", debounce=DashboardConstants.NUMERIC_INPUT_DEBOUNCE_MS, className="mb-2"),
                ]
            )

        return html.Div(
            [
                html.Div("Network", className="fw-semibold small text-muted mb-1"),
                _num("Learning rate", "restart-p-nn-learning-rate", "any", 0),
                _num("Max hidden units", "restart-p-nn-max-hidden-units", 1, 1),
                _num("Patience", "restart-p-nn-patience", 1, 1),
                html.Div("Candidate", className="fw-semibold small text-muted mb-1 mt-2"),
                _num("Candidate pool size", "restart-p-cn-pool-size", 1, 1),
                _num("Selected candidates", "restart-p-cn-selected", 1, 1),
                _num("Correlation threshold", "restart-p-cn-corr-thresh", "any", 0),
            ]
        )

    def _open_restart_confirm_modal_handler(self, n_clicks=None, dataset_type=None, n_samples=None, noise=None, rotations=None, n_spirals=None):
        """Open the confirm modal + seed the editable dataset / param fields.

        Returns the 17-tuple wired in ``_setup_restart_orchestration_callbacks``:
        ``(modal_open, summary_rows, start_fresh_value, granular_open, context,
        ds_type, ds_samples, ds_noise, ds_rotations, ds_spirals, p_lr, p_hu,
        p_patience, p_pool, p_selected, p_corr, baseline)``.

        The start-fresh toggle resets to its ratified default OFF (Q4) and the
        granular section collapses on every open. The dataset fields default to
        the sidebar selection (the currently staged / current config); the param
        fields are seeded from a best-effort ``/api/state`` read, clamped to
        cascor's PATCH bounds via N5's ``CascorPatchBounds`` (a status hiccup
        degrades to blank param fields — the modal still opens, and an untouched
        field is never applied). The baseline captures both so Confirm acts on
        exactly what the operator changed.
        """
        if not n_clicks:
            return (dash.no_update,) * 17
        dataset_vals = {"dataset_type": dataset_type, "n_samples": n_samples, "noise": noise, "rotations": rotations, "n_spirals": n_spirals}
        param_vals, context = self._read_restart_param_seed()
        baseline = {"dataset": dict(dataset_vals), "params": dict(param_vals)}
        summary = self._build_restart_summary(dataset_vals, param_vals, baseline)
        return (
            True,
            summary,
            False,
            False,
            context,
            dataset_vals["dataset_type"],
            dataset_vals["n_samples"],
            dataset_vals["noise"],
            dataset_vals["rotations"],
            dataset_vals["n_spirals"],
            param_vals.get("nn_learning_rate"),
            param_vals.get("nn_max_hidden_units"),
            param_vals.get("nn_patience"),
            param_vals.get("cn_pool_size"),
            param_vals.get("cn_selected_candidates"),
            param_vals.get("cn_correlation_threshold"),
            baseline,
        )

    def _read_restart_param_seed(self):
        """Best-effort backend read for the modal's editable params + context line.

        Returns ``(param_vals, context_component)``. Reads ``/api/state`` (the
        ``nn_*``/``cn_*`` surface the params panel also seeds from) and clamps each
        exposed value to cascor's PATCH bounds via N5's ``CascorPatchBounds`` so a
        backend-echoed out-of-range default seeds an admissible value. Never
        raises — an unreachable backend yields blank fields (``None``) and an
        "unavailable" context note; the modal still opens and unchanged fields are
        not applied on Confirm.
        """
        keys = [key for _id, key, _label in RESTART_MODAL_PARAM_FIELDS]
        try:
            resp = requests.get(
                self._api_url("/api/state"),
                timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                headers=internal_api_headers(),
            )
            if resp.status_code == 200:
                state = resp.json() or {}
                raw = {key: state.get(key) for key in keys if state.get(key) is not None}
                clamped, _ = CascorPatchBounds.clamp_params(raw)
                param_vals = {key: clamped.get(key) for key in keys}
                ctx_items = []
                for label, key in (("Current epoch", "current_epoch"), ("Hidden units", "hidden_units"), ("Status", "status")):
                    if state.get(key) is not None:
                        ctx_items.append(html.Span(f"{label}: {state.get(key)}", className="me-3"))
                context = html.Div(ctx_items or [html.Em("Current model state read from the backend.")], className="text-muted", style={"fontSize": "0.85em"})
                return param_vals, context
        except requests.RequestException:
            pass
        context = html.Div(html.Em("Current parameters unavailable (backend not reachable) — fields left blank; unchanged fields are not applied."), className="text-muted", style={"fontSize": "0.85em"})
        return dict.fromkeys(keys), context

    @staticmethod
    def _values_differ(a, b):
        """Tolerant equality for modal edits: numeric-aware (``300`` == ``300.0``),
        string fallback (``"xor"`` != ``"moons"``), ``None``-aware."""
        if a is None and b is None:
            return False
        if a is None or b is None:
            return True
        try:
            return float(a) != float(b)
        except (TypeError, ValueError):
            return str(a) != str(b)

    @classmethod
    def _restart_dataset_changed(cls, dataset_vals, baseline_dataset):
        """True iff the operator edited any staged-dataset field vs. the baseline."""
        dataset_vals = dataset_vals or {}
        baseline_dataset = baseline_dataset or {}
        return any(cls._values_differ(dataset_vals.get(key), baseline_dataset.get(key)) for _id, key, _label in RESTART_MODAL_DATASET_FIELDS)

    @classmethod
    def _restart_param_updates(cls, param_vals, baseline_params):
        """The ``{canopy_key: value}`` subset the operator actually edited.

        Only fields that differ from the open-time baseline AND are non-``None``
        are included — so an untouched Confirm applies nothing (the simple-confirm
        default), and a param the backend could not seed (blank field) is not
        forced onto cascor.
        """
        param_vals = param_vals or {}
        baseline_params = baseline_params or {}
        updates = {}
        for _id, key, _label in RESTART_MODAL_PARAM_FIELDS:
            new = param_vals.get(key)
            if new is None:
                continue
            if cls._values_differ(new, baseline_params.get(key)):
                updates[key] = new
        return updates

    @classmethod
    def _build_restart_summary(cls, dataset_vals, param_vals, baseline):
        """Render the "Restart plan" summary — reflects every in-place edit (item 4).

        Lists the dataset config that will be applied plus, when the operator has
        changed a param field from its open-time baseline, a "Parameter changes"
        block showing ``old → new``. Returns a list of ``dbc.ListGroupItem`` (the
        ``restart-confirm-summary`` ListGroup children).
        """
        dataset_vals = dataset_vals or {}
        baseline = baseline if isinstance(baseline, dict) else {}
        baseline_params = baseline.get("params") or {}
        rows = []
        for _id, key, label in RESTART_MODAL_DATASET_FIELDS:
            value = dataset_vals.get(key)
            if value is None:
                continue
            rows.append(dbc.ListGroupItem([html.Strong(f"{label}: "), html.Span(str(value))]))
        if not rows:
            rows = [dbc.ListGroupItem(html.Em("No dataset config selected — the currently staged change will be applied."), color="warning")]
        changes = []
        for _id, key, label in RESTART_MODAL_PARAM_FIELDS:
            new = (param_vals or {}).get(key)
            if new is None:
                continue
            if cls._values_differ(new, baseline_params.get(key)):
                old = baseline_params.get(key)
                changes.append(dbc.ListGroupItem([html.Strong(f"{label}: "), html.Span(f"{old} → {new}")], color="info"))
        if changes:
            rows.append(dbc.ListGroupItem(html.Em("Parameter changes to apply before restart:"), className="fw-semibold"))
            rows.extend(changes)
        return rows

    @staticmethod
    def _describe_dataset(dataset_vals):
        """Short human label for a re-staged dataset (outcome-alert note)."""
        dataset_vals = dataset_vals or {}
        dtype = dataset_vals.get("dataset_type") or "current"
        n = dataset_vals.get("n_samples")
        return f"{dtype} ({n} samples)" if n is not None else str(dtype)

    def _restage_dataset(self, dataset_vals):
        """Re-stage the (edited) dataset via the existing ``/api/stage_dataset`` route.

        Returns ``(ok, detail)``. Mirrors the ``apply_dataset`` callback's payload
        contract: ``nn_dataset_type`` is always sent; the optional numeric / spiral
        fields only when present. N3b uses the ROUTE (not a new staging path) so
        the cascor-side ``StageDatasetRequest`` stays the single authoritative
        validator.
        """
        dataset_vals = dataset_vals or {}
        payload = {}
        dtype = dataset_vals.get("dataset_type")
        if dtype is not None:
            payload["nn_dataset_type"] = dtype
        for key, pkey in (("n_samples", "nn_dataset_elements"), ("noise", "nn_dataset_noise"), ("rotations", "nn_spiral_rotations"), ("n_spirals", "nn_spiral_number")):
            value = dataset_vals.get(key)
            if value is not None:
                payload[pkey] = value
        try:
            resp = requests.post(
                self._api_url("/api/stage_dataset"),
                json=payload,
                timeout=DashboardConstants.DASHBOARD_LONG_POST_TIMEOUT,
                headers=internal_api_headers(),
            )
            if resp.status_code == 200:
                self.logger.info("Restart modal re-staged dataset: %s", payload)
                return True, ""
            detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
            self.logger.warning("Restart modal re-stage failed: %s %s", resp.status_code, detail)
            return False, detail
        except requests.RequestException as exc:
            self.logger.warning("Restart modal re-stage exception: %s", exc)
            return False, f"backend unreachable: {exc}"

    def _execute_restart_handler(self, n_clicks=None, start_fresh=None, dataset_vals=None, param_vals=None, baseline=None):
        """Confirm: (re-stage edited dataset) → (apply edited params) → restart.

        Returns ``(modal_open, progress_open, outcome_alert, banner_open)``. N3b
        sequences the two modify phases BEFORE the N3 stop→await→start
        orchestration and reports what each did in the outcome:

        1. If the operator edited a dataset field, re-stage via
           ``/api/stage_dataset``. A staging failure aborts the restart (banner
           stays open, reason surfaced) — never restart with a stale dataset.
        2. If the operator edited a param field, clamp + apply through N5's shared
           apply core (``_apply_params_via_backend`` → ``CascorPatchBounds`` +
           ``/api/set_params`` + applied/skipped toast). An apply failure aborts
           the restart, carrying the verbatim rejection detail (T1); any re-stage
           already done survives.
        3. ``POST /api/train/restart`` (unchanged N3 orchestration). Success closes
           the modal + banner; a 409/504/unreachable failure keeps the banner open
           so the staged change survives and the operator can retry (plan §8).

        An untouched Confirm skips phases 1-2 entirely — the ratified simple-confirm
        default (assumes all other params/structures unchanged).
        """
        if not n_clicks:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        baseline = baseline if isinstance(baseline, dict) else {}
        dataset_vals = dataset_vals if isinstance(dataset_vals, dict) else {}
        param_vals = param_vals if isinstance(param_vals, dict) else {}
        restage_note = None
        apply_note = None

        # Phase 1 — re-stage the dataset if edited.
        if self._restart_dataset_changed(dataset_vals, baseline.get("dataset") or {}):
            ok, detail = self._restage_dataset(dataset_vals)
            if not ok:
                outcome = self._render_restart_outcome({"message": f"Could not re-stage the dataset change: {detail}"}, ok=False)
                return False, False, outcome, dash.no_update
            restage_note = self._describe_dataset(dataset_vals)

        # Phase 2 — apply edited params through N5's machinery, before orchestration.
        param_updates = self._restart_param_updates(param_vals, baseline.get("params") or {})
        if param_updates:
            applied, toast = self._apply_params_via_backend(param_updates)
            if applied is dash.no_update:
                msg = f"Re-staged dataset to {restage_note}, but could not apply parameters: {toast}" if restage_note else f"Could not apply parameters: {toast}"
                outcome = self._render_restart_outcome({"message": msg}, ok=False)
                return False, False, outcome, dash.no_update
            apply_note = toast

        # Phase 3 — the N3 stop → await stopped → start(staged) orchestration.
        payload = {"start_fresh": bool(start_fresh), "reset": True}
        try:
            resp = requests.post(
                self._api_url("/api/train/restart"),
                json=payload,
                timeout=DashboardConstants.DASHBOARD_RESTART_POST_TIMEOUT,
                headers=internal_api_headers(),
            )
            data = {}
            try:
                data = resp.json() or {}
            except ValueError:
                data = {}
            if resp.status_code == 200 and data.get("success"):
                self.logger.info("Restart orchestration succeeded: %s", data.get("steps"))
                return False, False, self._render_restart_outcome(data, ok=True, restage_note=restage_note, apply_note=apply_note), False
            detail = data.get("message") or (resp.text[:300] if resp.text else f"HTTP {resp.status_code}")
            self.logger.warning("Restart orchestration failed (%s): %s", resp.status_code, detail)
            return False, False, self._render_restart_outcome(data if data else {"message": detail}, ok=False, restage_note=restage_note, apply_note=apply_note), dash.no_update
        except requests.RequestException as exc:
            self.logger.warning("Restart orchestration exception: %s", exc)
            return False, False, dbc.Alert([html.Strong("Restart failed. "), html.Span(f"Backend unreachable: {exc}")], color="danger", dismissable=True, duration=10000), dash.no_update

    @staticmethod
    def _render_restart_outcome(data, ok, restage_note=None, apply_note=None):
        """Build the restart outcome alert from the route's structured result.

        ``ok`` is the success flag (200 + ``success``). N3b prepends what the modal
        re-staged / applied (``restage_note`` / ``apply_note``) so the outcome
        reports the full restart result (item 4). On success the alert enumerates
        the steps that ran (stop/await/start) and — folded finding 2 — notes an
        instant-convergence run truthfully instead of letting it read as frozen. On
        failure the alert carries the upstream ``message`` (the 409 refusal reason,
        the 504 stop-await timeout, etc.) verbatim (T1), and flags a retriable
        timeout so the operator knows the staged change survived.
        """
        data = data if isinstance(data, dict) else {}
        prelude = []
        if restage_note:
            prelude.append(f"Re-staged dataset to {restage_note}. ")
        if apply_note:
            prelude.append(f"{apply_note}. ")
        prefix = "".join(prelude)
        if ok:
            start_fresh = bool(data.get("start_fresh"))
            was_active = bool(data.get("was_active"))
            parts = ["Restart complete. "]
            if was_active:
                parts.append("Stopped the running model, then ")
            else:
                parts.append("Started ")
            parts.append("a fresh model." if start_fresh else "continued the current model.")
            if data.get("instant_complete"):
                parts.append(" The new run converged immediately (epoch 0) — see the metrics panel for its final values.")
            return dbc.Alert([html.Strong("Restart succeeded. "), html.Span(prefix + "".join(parts))], color="success", dismissable=True, duration=8000)
        detail = str(data.get("message") or "the backend rejected the restart.").strip()
        if data.get("retriable"):
            detail += " The dataset change is still staged — you can retry."
        return dbc.Alert([html.Strong("Restart failed. "), html.Span(prefix + detail)], color="danger", dismissable=True, duration=10000)

    def _setup_dataset_swap_observers_callbacks(self):
        """Phase 2 P2-7 (Issue #3): poll ``dataset-swap-events-store``.

        Single polling callback that fires each ``slow-update-interval``
        tick to hydrate the events store from ``/api/history/dataset_swaps``.
        The three P2-7 consumer panels (replay timeline marker, History
        paired-diff, Snapshots tab badges) all read from this store —
        none re-issue the HTTP call themselves.

        Delegates to ``_poll_dataset_swap_events_handler`` so the branch
        logic is unit-testable.
        """

        @self.app.callback(
            Output("dataset-swap-events-store", "data"),
            Input("slow-update-interval", "n_intervals"),
            prevent_initial_call=False,
        )
        def poll_dataset_swap_events(n_intervals):
            return self._poll_dataset_swap_events_handler(n_intervals=n_intervals)

        # P2-7 follow-up: hydrate the per-snapshot swap history store on
        # ``replay-player-session`` changes. We only fetch when the
        # active snapshot_id transitions — not on every speed/seek tick —
        # so the snapshot's swap history is held against the loaded
        # session, not re-fetched on minor session mutations.
        @self.app.callback(
            Output("loaded-snapshot-swap-events-store", "data"),
            Input("replay-player-session", "data"),
            State("loaded-snapshot-swap-events-store", "data"),
            prevent_initial_call=False,
        )
        def hydrate_loaded_snapshot_swap_events(session, prior):
            return self._hydrate_loaded_snapshot_swap_events_handler(session=session, prior=prior)

        # P2-7 follow-up: WS-push merger for dataset_swap events.
        # The slow-poll above is the authoritative source — runs every
        # slow-update-interval tick and overwrites the store with the
        # full event list from cascor's REST endpoint. This merger
        # layered on top is a latency-shortener: when a swap arrives
        # over WS, the new event lands in the store within one
        # fast-update-interval tick instead of waiting for the next
        # slow poll. Dedupe keys off (timestamp, pre_swap_snapshot_id)
        # so a swap that arrives via both paths is held exactly once.
        @self.app.callback(
            Output("dataset-swap-events-store", "data", allow_duplicate=True),
            Input("ws-dataset-swap-buffer", "data"),
            State("dataset-swap-events-store", "data"),
            prevent_initial_call=True,
        )
        def merge_ws_dataset_swap_events(ws_buffer, current_store):
            return self._merge_ws_dataset_swap_events_handler(ws_buffer=ws_buffer, current_store=current_store)

    # ------------------------------------------------------------------
    # P2-5 (Issue #3) Live Dataset Switch handlers — extracted from
    # ``_setup_live_dataset_switch_callbacks`` closures in P2-6 so each
    # branch is unit-testable via direct invocation. Behaviour preserved
    # bit-for-bit from P2-5 (#275); only the call site changed.
    # See ``tests/unit/frontend/test_live_dataset_switch_handlers.py``.
    # ------------------------------------------------------------------

    def _poll_dataset_swap_events_handler(self, n_intervals=None):
        """Hydrate the ``dataset-swap-events-store`` from the canopy proxy.

        Returns ``{"events": [...]}`` on success — list always present,
        empty when no swaps yet. ``dash.no_update`` on backend hiccup so
        the prior store value (typically the same events) stays put.
        """
        try:
            resp = requests.get(
                self._api_url("/api/history/dataset_swaps"),
                timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                headers=internal_api_headers(),
            )
            if resp.status_code != 200:
                return dash.no_update
            data = (resp.json() or {}).get("data", {}) or {}
            events = data.get("events", []) or []
            return {"events": list(events)}
        except requests.RequestException:
            return dash.no_update

    @staticmethod
    def _merge_ws_dataset_swap_events_handler(ws_buffer=None, current_store=None):
        """Merge WS-pushed dataset_swap events into the live store.

        P2-7 follow-up. Dedupe key is
        ``(timestamp, pre_swap_snapshot_id)`` — together these uniquely
        identify a swap event:

        * ``timestamp`` is set by cascor at swap time (ISO-8601 UTC,
          one per `swap_dataset_live` call).
        * ``pre_swap_snapshot_id`` is the *exact* HDF5 file id captured
          before the swap; cascor's collision-suffix loop guarantees
          this is unique per snapshot.

        If both fields are present the pair is the dedupe key. If
        ``timestamp`` is missing on a pushed event (defensive — should
        never happen on a well-formed cascor frame), it is appended
        unconditionally and dedupe falls back to identity.

        Returns ``dash.no_update`` when the buffer is empty / unset —
        keeps callback cache stable and avoids touching the store on
        trivial buffer churn.
        """
        if not isinstance(ws_buffer, dict):
            return dash.no_update
        ws_events = ws_buffer.get("events") or []
        if not ws_events:
            return dash.no_update

        existing = []
        if isinstance(current_store, dict):
            existing = list(current_store.get("events") or [])

        seen = set()
        for ev in existing:
            if not isinstance(ev, dict):
                continue
            ts = ev.get("timestamp")
            pre_id = ev.get("pre_swap_snapshot_id")
            if ts is not None:
                seen.add((ts, pre_id))

        merged = list(existing)
        for ev in ws_events:
            if not isinstance(ev, dict):
                continue
            ts = ev.get("timestamp")
            pre_id = ev.get("pre_swap_snapshot_id")
            if ts is None:
                merged.append(ev)
                continue
            key = (ts, pre_id)
            if key in seen:
                continue
            seen.add(key)
            merged.append(ev)

        merged.sort(key=lambda e: e.get("timestamp") or "")
        return {"events": merged}

    def _hydrate_loaded_snapshot_swap_events_handler(self, session=None, prior=None):
        """Hydrate ``loaded-snapshot-swap-events-store`` (P2-7 follow-up).

        Fires when ``replay-player-session`` changes. We only touch the
        backend when the active ``snapshot_id`` actually transitions —
        speed / seek / play-state changes leave the store alone so the
        same loaded snapshot's history doesn't get re-fetched on every
        control button click.

        Returns:
          * ``{"events": [], "snapshot_id": None}`` when no session is
            active (cleared replay).
          * ``{"events": [...], "snapshot_id": <id>}`` after a successful
            fetch.
          * ``dash.no_update`` when the snapshot_id hasn't changed (keeps
            the previously-loaded history in place across session ticks).
          * ``{"events": [], "snapshot_id": <id>}`` on a non-200 / network
            error so the timeline degrades to live-event-only rendering
            rather than surfacing a UI error.
        """
        prior = prior if isinstance(prior, dict) else {}
        prior_snapshot_id = prior.get("snapshot_id")

        snapshot_id = None
        if isinstance(session, dict):
            snapshot_id = session.get("snapshot_id")

        if snapshot_id is None:
            if prior_snapshot_id is None:
                return dash.no_update
            return {"events": [], "snapshot_id": None}

        if snapshot_id == prior_snapshot_id:
            return dash.no_update

        try:
            resp = requests.get(
                self._api_url(f"/api/snapshots/{snapshot_id}/history/dataset_swaps"),
                timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                headers=internal_api_headers(),
            )
            if resp.status_code != 200:
                return {"events": [], "snapshot_id": snapshot_id}
            data = (resp.json() or {}).get("data", {}) or {}
            events = data.get("events", []) or []
            return {"events": list(events), "snapshot_id": snapshot_id}
        except requests.RequestException:
            return {"events": [], "snapshot_id": snapshot_id}

    def _update_training_status_store_handler(self, n_intervals=None):
        """Populate ``training-status-store`` from ``/api/status``.

        Returns ``{"is_running": bool, "phase": str}`` on success,
        ``dash.no_update`` on non-200 / network error so a transient
        backend hiccup doesn't blow away the prior store value.
        """
        try:
            resp = requests.get(
                self._api_url("/api/status"),
                timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                headers=internal_api_headers(),
            )
            if resp.status_code != 200:
                return dash.no_update
            payload = resp.json() or {}
            return {
                "is_running": bool(payload.get("is_running", False)),
                "phase": str(payload.get("phase", "idle")),
            }
        except requests.RequestException:
            return dash.no_update

    def _gate_live_switch_button_handler(self, flags=None, status=None):
        """Gate the Live Dataset Switch button.

        Returns ``disabled=True`` unless BOTH stores agree:
        ``experimental-flags-store.experimental_functions`` is True AND
        ``training-status-store.is_running`` is True (F2.3 + F2.5).
        """
        flags_ok = bool(flags and flags.get("experimental_functions"))
        running = bool(status and status.get("is_running"))
        return not (flags_ok and running)

    def _open_live_switch_modal_handler(self, n_clicks=None, dataset_type=None, n_samples=None, noise=None, n_spirals=None, rotations=None):
        """Open the warning modal + populate the read-only dataset summary.

        Returns ``(is_open, summary_rows)``. The summary is built from
        the State values of the sidebar dataset inputs at click time —
        Q3 hybrid: "here's what we're about to swap to" so the user
        sees the exact config before confirming.
        """
        if not n_clicks:
            return dash.no_update, dash.no_update
        rows = []
        for label, value in (
            ("Dataset type", dataset_type),
            ("Samples", n_samples),
            ("Noise", noise),
            ("Spirals", n_spirals),
            ("Spiral rotations", rotations),
        ):
            if value is None:
                continue
            rows.append(dbc.ListGroupItem([html.Strong(f"{label}: "), html.Span(str(value))]))
        if not rows:
            rows = [dbc.ListGroupItem(html.Em("No dataset config selected in the sidebar."), color="warning")]
        return True, rows

    def _close_live_switch_modal_on_fallback_handler(self, n_clicks=None):
        """Close the modal on "Return to Stop & Restart" click.

        Minimal interpretation per Q2 — see PHASE_2_P2_5_FOLLOWUPS for
        the three deferred active-interpretation polish items.
        """
        if not n_clicks:
            return dash.no_update
        return False

    def _accept_live_switch_handler(self, n_clicks=None, dataset_type=None, n_samples=None, noise=None, n_spirals=None, rotations=None):  # noqa: C901
        """POST ``/api/live_dataset_swap`` and reconcile the UI to the response.

        Returns ``(modal_open, progress_open, outcome_alert, in_flight)``.

        Three response branches:
          * 200 + ``status == "cancelled"`` → info alert "swap cancelled"
          * 200 + other status → success alert with the pre-swap snapshot id
          * non-200 → danger alert with cascor's error string verbatim
            (spec §4.3: "failure shows the server error verbatim")
          * RequestException → danger alert with the exception detail

        On every branch the modal + progress alert close and in_flight=False.
        """
        if not n_clicks:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        payload = {
            "nn_dataset_type": dataset_type,
            "nn_dataset_elements": n_samples,
            "nn_dataset_noise": noise,
            "nn_spiral_number": n_spirals,
            "nn_spiral_rotations": rotations,
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        try:
            resp = requests.post(
                self._api_url("/api/live_dataset_swap"),
                json=payload,
                timeout=DashboardConstants.DASHBOARD_LONG_POST_TIMEOUT,
                headers=internal_api_headers(),
            )
            if resp.status_code == 200:
                data = (resp.json() or {}).get("data", {}) or {}
                swap_status = data.get("status")
                if swap_status == "cancelled":
                    outcome = dbc.Alert("Live dataset swap cancelled.", color="info", duration=5000, dismissable=True)
                else:
                    pre_snap = data.get("pre_swap_snapshot_id") or "n/a"
                    outcome = dbc.Alert(["Live dataset swap complete. Pre-swap snapshot: ", html.Code(pre_snap)], color="success", duration=5000, dismissable=True)
                return False, False, outcome, {"in_flight": False}
            detail = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
            self.logger.warning("Live dataset swap rejected: %s", detail)
            outcome = dbc.Alert(f"Live dataset swap failed: {detail}", color="danger", duration=5000, dismissable=True)
            return False, False, outcome, {"in_flight": False}
        except requests.RequestException as exc:
            self.logger.warning("Live dataset swap exception: %s", exc)
            outcome = dbc.Alert(f"Backend unreachable: {exc}", color="danger", duration=5000, dismissable=True)
            return False, False, outcome, {"in_flight": False}

    def _open_progress_alert_on_accept_handler(self, n_clicks=None):
        """Open the progress alert + flip in_flight=True the moment Accept
        is clicked.

        Returns ``(progress_open, in_flight)``. Split from the Accept POST
        handler so the user sees the spinner immediately rather than
        waiting for the (5–30 s) POST to return. Dash runs both callbacks
        on the worker pool; this one returns near-instantly.
        """
        if not n_clicks:
            return dash.no_update, dash.no_update
        return True, {"in_flight": True}

    def _cancel_live_switch_handler(self, n_clicks=None):
        """DELETE ``/api/live_dataset_swap`` to cancel an in-flight swap.

        Returns ``dash.no_update`` on success — the "cancelled" outcome
        alert is rendered by ``_accept_live_switch_handler`` when its
        POST returns with ``status="cancelled"``. Suppressing this
        callback's outcome avoids double-rendering the alert.

        Non-200 / RequestException → warning alert ("cancel had no
        effect" / "cancel failed: ..."). Cascor 404 (no swap in
        progress) is the common case and surfaces here as a warning.
        """
        if not n_clicks:
            return dash.no_update
        try:
            resp = requests.delete(
                self._api_url("/api/live_dataset_swap"),
                timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS,
                headers=internal_api_headers(),
            )
            if resp.status_code == 200:
                self.logger.info("Live swap cancel signal sent")
                return dash.no_update
            detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
            self.logger.warning("Live swap cancel rejected: %s", detail)
            return dbc.Alert(f"Cancel had no effect: {detail}", color="warning", duration=5000, dismissable=True)
        except requests.RequestException as exc:
            self.logger.warning("Live swap cancel exception: %s", exc)
            return dbc.Alert(f"Cancel failed: {exc}", color="warning", duration=5000, dismissable=True)

    # Define event handlers for callbacks
    def _toggle_dark_mode_handler(self, current_dark_mode=None):
        """Toggle dark mode on button click."""
        is_dark = not current_dark_mode
        icon = "☀️" if is_dark else "🌙"
        return is_dark, icon

    def _update_theme_state_handler(self, is_dark=None):
        """Update theme state based on dark mode store."""
        return "dark" if is_dark else "light"

    @staticmethod
    def _classify_response_failure(response) -> tuple[str, str]:
        """Map a non-OK HTTP response to (status_label, detail_label) pair.

        Used by both the status-bar handler (via ``_status_bar_error_tuple``)
        and the network-info panel handlers so the labels stay in lockstep —
        a 429 surfacing on the status bar simultaneously surfaces as the
        same "Rate Limited" message on the network-info panels.
        """
        code = response.status_code
        if code == 429:
            return ("Rate Limited", f"Rate limited (HTTP {code})")
        if code in (401, 403):
            return ("Unauthorized", f"Auth failed (HTTP {code})")
        if code >= 500:
            return ("Backend Error", f"Backend error (HTTP {code})")
        return ("Backend Unavailable", f"Backend unavailable (HTTP {code})")

    @staticmethod
    def _classify_exception_failure(exc) -> tuple[str, str]:
        """Map a request exception to (status_label, detail_label) pair."""
        if isinstance(exc, requests.Timeout):
            return ("Backend Timeout", "Backend timed out")
        if isinstance(exc, requests.ConnectionError):
            return ("Unreachable", "Backend unreachable")
        return ("Error", f"Connection Error ({type(exc).__name__})")

    def _network_info_error_div(self, panel_label: str, status_label: str, detail: str):
        """Build the error placeholder for the network-info panels.

        Mirrors PR #340's status-bar diagnosability so the operator can
        distinguish a transient rate limit from a real backend outage on
        the Network Information panel and its Details counterpart. Replaces
        the previous opaque "Unable to fetch network info" / "Unable to
        fetch network stats" / "Unable to fetch detailed network info"
        messages.
        """
        return html.Div(
            [
                html.P(f"{panel_label}: {status_label}", style={"color": "orange"}),
                html.P([html.Small(detail)], style={"color": "gray", "fontSize": "12px"}),
            ]
        )

    def _status_bar_error_tuple(self, status_label: str, connection_label: str):
        """Build the 9-element status-bar tuple for a FAILED /api/status poll.

        ``status_label`` is shown (red) in the status display; ``connection_label``
        is the hidden backward-compat element. Phase/epoch/units collapse to "--".
        Replaces the previous bare "Error" so the operator can tell a transient
        rate limit from an auth failure, a 5xx, a timeout, or an unreachable
        backend (#3 "Error"-label diagnosability).
        """
        error_indicator = {"fontSize": "16px", "color": "#dc3545", "marginRight": "12px"}
        error_style = {"fontWeight": "bold", "color": "#dc3545"}
        neutral_style = {"fontWeight": "bold", "color": "#6c757d"}
        return (
            error_indicator,
            connection_label,
            "Latency: --",
            status_label,
            error_style,
            "--",
            neutral_style,
            "--",
            "--",
        )

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
        try:
            # Single request: /api/status provides all needed info and doubles as health check.
            # Use fast timeout since this fires every tick.
            start_time = time.time()
            status_response = requests.get(self._api_url("/api/status"), timeout=DashboardConstants.FAST_API_TIMEOUT_SECONDS, headers=internal_api_headers())
            latency_ms = (time.time() - start_time) * 1000

            if status_response.status_code == 200:
                return self._build_unified_status_bar_content(status_response, latency_ms)
            # Non-200: surface a specific, actionable label instead of a bare "Error"
            # so a transient rate limit isn't confused with a real backend outage.
            # Dominant "Error" cause on the deployed stack: canopy's own rate
            # limiter throttling the dashboard's own polling (see #2a).
            status_label, detail = self._classify_response_failure(status_response)
            return self._status_bar_error_tuple(status_label, detail)
        except (requests.Timeout, requests.ConnectionError) as e:
            self.logger.warning(f"Status bar update failed: {type(e).__name__}")
            status_label, detail = self._classify_exception_failure(e)
            return self._status_bar_error_tuple(status_label, detail)
        except Exception as e:
            self.logger.warning(f"Status bar update failed: {type(e).__name__}: {e}")
            return self._status_bar_error_tuple("Error", "Connection Error")

    @staticmethod
    def _completion_reason_label(reason):
        """Map a cascor grow_network ``completion_reason`` to a status-bar suffix.

        cascor #320 emits one of five reasons on ``/api/status``; collapse them
        to a short operator-facing phrase. ``residual_collapsed`` /
        ``below_threshold`` are both genuine convergence; ``no_candidate`` is the
        0-unit stall. Unknown / missing reasons return ``None`` (no suffix), so a
        cascor that predates the field degrades gracefully.
        """
        return {
            "residual_collapsed": "converged",
            "below_threshold": "converged",
            "no_candidate": "stalled (0 new units)",
            "early_stopped": "early stopped",
            "max_iterations": "max iterations",
        }.get(reason)

    @staticmethod
    def _counter_displays(status):
        """N6 (training-runtime-defects plan §4 I-1c / §5 S12): map the reconciled
        cascor status surface to the dashboard's Step / Hidden-Units / Iteration /
        Epoch display strings, per the C2b counter contract.

        Field meanings are the single source of truth documented in juniper-cascor
        ``docs/api/JUNIPER_CASCOR_API_REFERENCE.md`` ("Counter semantics (C2b)"):

        - ``current_epoch`` / ``current_step`` — completed **training steps** (one
          initial output-training pass plus one per cascade growth iteration), NOT
          inner output-training epochs; single-writer and monotonic. Rendered as
          "Step" (the pre-C2b "Epoch" label conflated this with an inner epoch —
          the S12 "Epoch: 10000 vs 12" confusion).
        - ``hidden_units`` / ``max_hidden_units`` — installed cascade units vs the
          growth-capacity cap (C2b reconciled ``max_hidden_units`` to the live
          network's effective value; pre-C2b the divergent surfaces showed a stale
          ``10000`` denominator).
        - ``grow_iteration`` / ``grow_max`` — cascade growth iteration vs
          ``max_iterations``. The TRUE "Iteration" counter, distinct from the
          hidden-unit count it was previously conflated with.
        - ``output_epoch`` / ``candidate_epoch`` (with ``*_total_epochs``) — live
          within-pass inner-epoch progress, phase-qualified. These reset to 0 at
          each phase entry BY DESIGN, so "0 / N" is the correct render, not a
          regression or a blank.
        - ``max_epochs`` is the C2b DERIVED total-epoch budget — a whole-run budget
          in inner-epoch units. It is deliberately NOT paired with the (step-unit)
          "Step" counter as a fraction (they are different units); it is surfaced
          as the Parameters panel's "Maximum Total Epochs" budget instead.

        Returns display strings under the keys ``step``, ``hidden_units``,
        ``iteration`` and ``phase_epoch``. Missing fields (e.g. a pre-C2b cascor,
        or demo mode which has no within-pass output epoch) degrade to a plain
        count or the em-dash placeholder rather than raising.
        """
        status = status if isinstance(status, dict) else {}

        # Step — completed training steps (monotonic). ``current_epoch`` is the
        # canonical field; ``current_step`` is its alias.
        step_val = status.get("current_epoch")
        if step_val is None:
            step_val = status.get("current_step", 0)
        step = str(step_val if step_val is not None else 0)

        # Hidden Units — installed / capacity (reconciled denominator).
        hidden = status.get("hidden_units", 0) or 0
        max_hidden = status.get("max_hidden_units")
        hidden_units = f"{hidden} / {max_hidden}" if max_hidden else str(hidden)

        # Iteration — the true cascade growth iteration vs its ``max_iterations``
        # cap (``grow_max``); NOT the hidden-unit count.
        grow_iteration = status.get("grow_iteration")
        grow_max = status.get("grow_max")
        if grow_iteration is not None and grow_max:
            iteration = f"{grow_iteration} / {grow_max}"
        elif grow_iteration is not None:
            iteration = str(grow_iteration)
        else:
            iteration = "—"

        # Epoch — the phase-qualified within-pass inner epoch ("Epoch 12 (output)"),
        # which is what "epoch" genuinely means here. Resets to 0 at phase entry by
        # design; "0 / N (phase)" must render (never blank) so the reset does not
        # read as a regression.
        phase = (status.get("phase") or "").lower()
        phase_epoch = "—"
        if phase == "output":
            total = status.get("output_total_epochs")
            if total:
                phase_epoch = f"{status.get('output_epoch') or 0} / {total} (output)"
        elif phase == "candidate":
            total = status.get("candidate_total_epochs")
            if total:
                phase_epoch = f"{status.get('candidate_epoch') or 0} / {total} (candidate)"

        return {"step": step, "hidden_units": hidden_units, "iteration": iteration, "phase_epoch": phase_epoch}

    def _build_unified_status_bar_content(self, status_response, latency_ms):
        """Build unified status bar content from /api/status response."""
        status_data = status_response.json()

        # Adapter-error fall-through: when the canopy → cascor circuit
        # breaker is OPEN (or the underlying cascor client raised),
        # ``CascorServiceAdapter.get_training_status`` returns
        # ``{"is_training": False, "error": <reason>}`` — see
        # ``src/backend/cascor_service_adapter.py:1264-1272``. The
        # ``service_backend.get_status`` shim passes that dict through
        # unchanged because it isn't shaped like a cascor-nested
        # response (``is_cascor_nested`` is False), so the
        # ``/api/status`` route returns HTTP 200 with the error marker.
        # Without this guard every status field falls back to its
        # ``False`` / ``0`` default and the existing ``elif`` chain
        # renders "Stopped" — indistinguishable from a legitimate
        # idle / never-started state, even though the backend is
        # actually unreachable. This was the deferred follow-up in
        # PR #340 ("handle the circuit-open 200 explicitly instead
        # of as Stopped").
        error_marker = status_data.get("error") if isinstance(status_data, dict) else None
        if error_marker:
            return self._status_bar_error_tuple("Unreachable", f"Backend unreachable ({error_marker})")

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
        # N6/C2b: derive the header counter strings from the reconciled surface.
        # ``step`` = completed training steps (``current_epoch``); ``hidden_units``
        # = installed / capacity with the reconciled denominator. See
        # ``_counter_displays`` for the full contract.
        counters = self._counter_displays(status_data)

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

        # Issue #3 follow-up: on a completed run, append cascor's grow_network
        # completion_reason so the operator sees *why* it stopped (converged vs a
        # 0-unit stall) instead of a bare "Completed". Display-only — status_color
        # above keys off the base "Completed".
        if status == "Completed":
            completion_label = self._completion_reason_label(status_data.get("completion_reason"))
            if completion_label:
                status = f"{status} — {completion_label}"

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
            counters["step"],
            counters["hidden_units"],
        )

    def _update_network_info_handler(self, n=None):
        """Update network information panel from API."""
        try:
            url = self._api_url("/api/status")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not response.ok:
                self.logger.warning(f"Status API returned {response.status_code}")
                status_label, detail = self._classify_response_failure(response)
                return self._network_info_error_div("Network Info", status_label, detail)
            status = response.json()

            # N6/C2b: derive each counter's display against its correct
            # denominator from the reconciled status surface (see
            # ``_counter_displays``): Hidden Units carries the reconciled
            # ``max_hidden_units`` cap, Iteration is the true growth iteration
            # (``grow_iteration``/``grow_max``, previously mislabelled as the
            # unit count), and the phase-qualified within-pass Epoch renders
            # "N / M (phase)".
            counters = self._counter_displays(status)

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
                            counters["hidden_units"],
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
                            counters["step"],
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Epoch (in phase): "),
                            counters["phase_epoch"],
                        ]
                    ),
                    html.P(
                        [
                            html.Strong("Iteration: "),
                            counters["iteration"],
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
        except (requests.Timeout, requests.ConnectionError) as e:
            self.logger.warning(f"Failed to fetch network info: {type(e).__name__}")
            status_label, detail = self._classify_exception_failure(e)
            return self._network_info_error_div("Network Info", status_label, detail)
        except Exception as e:
            self.logger.warning(f"Failed to fetch network info: {e}")
            return self._network_info_error_div("Network Info", "Error", f"{type(e).__name__}: {e}")

    def _update_network_info_details_handler(self, n=None):
        """Update detailed network information panel from API."""
        try:
            url = self._api_url("/api/network/stats")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not response.ok:
                self.logger.warning(f"Network stats API returned {response.status_code}")
                status_label, detail = self._classify_response_failure(response)
                return self._network_info_error_div("Network Stats", status_label, detail)
            stats = response.json()

            # Use the metrics_panel helper to create the detailed table
            return self.metrics_panel._create_network_info_table(stats)
        except (requests.Timeout, requests.ConnectionError) as e:
            self.logger.warning(f"Failed to fetch network stats: {type(e).__name__}")
            status_label, detail = self._classify_exception_failure(e)
            return self._network_info_error_div("Network Stats", status_label, detail)
        except Exception as e:
            self.logger.warning(f"Failed to fetch network stats: {e}")
            return self._network_info_error_div("Network Stats", "Error", f"{type(e).__name__}: {e}")

    def _append_ws_metrics_store_handler(self, ws_metrics_buffer=None, display_mode_state=None, current_metrics=None):
        """N8 (posture O3): accumulate drained WS metrics onto the store.

        Runs only when ``ws-metrics-buffer`` changes — i.e. the clientside drain
        actually produced events (a WS frame arrived). Appends them onto the
        last-known-good store, bounded to the display window so the figure rebuild +
        tiles track a scrolling live window (matching the REST window fetch's
        ``limit=window_size``). Because it is triggered ONLY by real WS pushes it can
        never starve the store when the stream is quiet — the liveness-gated poll
        (``_update_metrics_store_handler``) is the sole writer then. History-analysis
        modes (``full`` / ``hidden_units``) opt out: they are non-real-time and want
        the complete REST history, which a WS window would truncate.
        """
        mode_state = display_mode_state if isinstance(display_mode_state, dict) else {}
        if mode_state.get("mode", "window") in ("full", "hidden_units"):
            return dash.no_update
        ws_events = [e for e in ((ws_metrics_buffer or {}).get("events") or []) if isinstance(e, dict)]
        if not ws_events:
            return dash.no_update
        window_size = mode_state.get("window_size", 100) or 100
        merged = (current_metrics if isinstance(current_metrics, list) else []) + ws_events
        return merged[-window_size:] if len(merged) > window_size else merged

    def _update_metrics_store_handler(self, n=None, display_mode_state=None, current_metrics=None, trigger=None, ws_live=None):
        """Liveness-gated REST poll for the metrics-panel store (N8 posture O1).

        Fires on every fast-interval tick (the interval is the sole trigger, so the
        callback can never be starved — see the callback's Dash-model note on why the
        WS buffer must NOT be an Input here). Two regimes:

        1. **Demoted while WS-primary is live** — when the metrics stream is fresh
           (``ws_live``) in the real-time ``window`` view, return ``dash.no_update``:
           the REST fetch is SKIPPED and the ``allow_duplicate`` append callback
           (``_append_ws_metrics_store_handler``) owns the store from the WS buffer.
        2. **Liveness-gated REST fallback (O1)** — when the stream is stale/absent
           (``ws_live`` falsy — the default for every non-WS caller, so the N1 poll is
           preserved exactly), poll ``/api/metrics/history``. ``ws_live`` is derived
           from the bridge's frame-arrival age (never the sticky ``metricsReceived``
           flag), so a stream that goes quiet flips stale within
           ``WS_LIVENESS_WINDOW_MS`` and this poll re-engages on the next tick — the
           anti-sticky guarantee that killed the N1-era starvation.
           ``full`` / ``hidden_units`` (history-analysis) modes are NOT WS-gated: they
           always poll (Q6: polling is correct for non-real-time surfaces).

        Guard rails (both validation-mandated, plan §8 rows 1-2):

        - **Empty-guard**: when the fetch is empty or errored AND the store
          already holds data, return ``dash.no_update`` so the last-known-good
          store survives — cascor clears metrics post-run, and a 1 Hz poll would
          otherwise blank a completed run's charts. A genuinely empty fetch with an
          empty store passes through unchanged.
        - **Bounded full-history fetch**: ``full`` / ``hidden_units`` display
          modes fetch the complete history (``limit=0`` → up to 10k rows), so
          interval-driven ticks only refetch every
          ``FULL_HISTORY_POLL_TICK_MODULUS``-th tick (~0.2 Hz); a display-mode
          switch (or a direct/mount invocation) still fetches immediately.
        """
        mode_state = display_mode_state if isinstance(display_mode_state, dict) else {}
        mode = mode_state.get("mode", "window")
        full_fetch = mode in ("full", "hidden_units")

        # N8 poll demotion (O1): while WS-primary is live in the real-time window view,
        # skip the REST fetch — the append callback carries the store. History-analysis
        # modes ignore the gate and always poll.
        if ws_live and not full_fetch:
            return dash.no_update

        if full_fetch and trigger and trigger.startswith("fast-update-interval") and n and n % DashboardConstants.FULL_HISTORY_POLL_TICK_MODULUS != 0:
            return dash.no_update

        try:
            limit = 0 if full_fetch else mode_state.get("window_size", 100)  # 0 = fetch all
            url = self._api_url(f"/api/metrics/history?limit={limit}")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not response.ok:
                self.logger.warning(f"Metrics history API returned {response.status_code}")
                return dash.no_update if current_metrics else []
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

            if not metrics and current_metrics:
                # Empty-guard: preserve the last-known-good store (see docstring).
                return dash.no_update

            # Phase B: Track REST polling bandwidth (P0 motivator proof metric)
            if not hasattr(self, "_rest_bytes_gauge"):
                try:
                    from juniper_observability import register_or_reuse
                    from prometheus_client import Gauge

                    self._rest_bytes_gauge = register_or_reuse(
                        Gauge,
                        "canopy_rest_polling_bytes_per_sec",
                        "REST polling response size in bytes (per endpoint)",
                        ["endpoint"],
                    )
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
            return dash.no_update if current_metrics else []

    def _update_topology_store_handler(self, n=None, active_tab=None):
        """Fetch topology from API and update network visualizer store.

        Failure paths deliberately return ``dash.no_update`` (same last-known-good
        posture as the metrics handler's N1 empty-guard) so a transient upstream
        error never blanks the network view.
        """
        # Only update if topology tab is active
        if active_tab != "topology":
            return dash.no_update

        try:
            url = self._api_url("/api/topology")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not response.ok:
                self.logger.warning(f"Topology API returned {response.status_code}")
                return dash.no_update
            result = response.json()
            # Unwrap success envelope: {"status": "success", "data": {...}}
            topology = result.get("data", result) if isinstance(result, dict) else result
            # Graph-format payloads (the demo backend emits them directly) pass
            # through UNTRANSFORMED — critically, without importing the service
            # adapter: ``backend.cascor_service_adapter`` hard-imports
            # ``juniper_cascor_client``, which is the optional [juniper-cascor]
            # extra and legitimately absent in demo-only installs (and the CI UI
            # env). Pre-fix, that ModuleNotFoundError landed in the broad except
            # below → silent ``no_update`` on every dispatch → a permanently
            # empty Network Topology panel in any client-less env (the
            # 2026-07-12..14 UI-leg red; regression pin:
            # test_topology_store_fetches_on_tab_switch_with_ws_silent).
            if isinstance(topology, dict) and "input_units" in topology:
                self.logger.debug(f"Fetched topology from {url}: {len(topology.get('connections', []))} connections (graph-format passthrough)")
                return topology
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
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not response.ok:
                self.logger.warning(f"Raw topology API returned {response.status_code}")
                return dash.no_update
            return response.json()
        except Exception as e:
            self.logger.warning(f"Failed to fetch raw topology from API: {type(e).__name__}: {e}")
            return dash.no_update

    def _update_workers_store_handler(self, n=None, active_tab=None):
        """Fetch the worker roster (+ aggregate stats) and update the worker store (N10, U-5).

        Tab-gated to the Workers tab and empty-guarded: any upstream error or a
        non-OK roster response returns ``dash.no_update`` (same last-known-good
        posture as the topology/metrics N1 handlers) so a transient hiccup never
        blanks the roster. The proxy (``GET /api/v1/workers/list``) already annotates
        each worker's ``kind`` and a ``local_reported`` honesty flag — cascor models
        remote WS workers only, so ``local_reported`` is ``False`` in service mode and
        the panel renders an honest "local not individually reported" note. Aggregate
        stats are best-effort: the roster table renders even if ``/stats`` is down.
        """
        if active_tab != "workers":
            return dash.no_update

        try:
            list_resp = requests.get(self._api_url("/api/v1/workers/list"), timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not list_resp.ok:
                self.logger.warning(f"Workers list API returned {list_resp.status_code}")
                return dash.no_update
            list_data = list_resp.json()
        except Exception as e:
            self.logger.warning(f"Failed to fetch worker list from API: {type(e).__name__}: {e}")
            return dash.no_update

        if not isinstance(list_data, dict):
            return dash.no_update

        workers = list_data.get("workers", []) or []
        payload = {
            "workers": workers,
            "count": list_data.get("count", len(workers)),
            "local_reported": bool(list_data.get("local_reported", False)),
            "error": list_data.get("error"),
            "stats": {},
        }

        # Aggregate stats are non-fatal — cascor computes ``stale`` from its own
        # heartbeat-timeout, so we prefer its numbers over recomputing client-side.
        try:
            stats_resp = requests.get(self._api_url("/api/v1/workers/stats"), timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if stats_resp.ok:
                stats_data = stats_resp.json()
                if isinstance(stats_data, dict):
                    payload["stats"] = stats_data
        except Exception as e:
            self.logger.debug(f"Worker stats fetch failed (non-fatal): {type(e).__name__}: {e}")

        return payload

    def _update_dataset_store_handler(self, n=None, active_tab=None):
        """Fetch dataset from API and update dataset plotter store."""
        # Only update if dataset tab is active
        if active_tab != "dataset":
            return dash.no_update

        try:
            url = self._api_url("/api/dataset")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
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
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
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
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
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
        oneshot_start_body=None,
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

        detail = ""
        try:
            url = self._api_url(f"/api/train/{command}")
            # A1-iv-3c: a one-shot (recurrence) Start forwards the dataset-ref body so the fit has
            # a generator + registry params; every other command and the live (cascor/demo) Start
            # send no body, so the route sees ``body=None`` and their start path is unchanged.
            post_kwargs = {"timeout": DashboardConstants.DASHBOARD_POST_TIMEOUT, "headers": internal_api_headers()}
            if command == "start" and oneshot_start_body:
                post_kwargs["json"] = oneshot_start_body
            response = requests.post(url, **post_kwargs)
            response.raise_for_status()
            success = True
        except Exception as e:
            success = False
            detail = self._extract_training_error_detail(e)
            self.logger.warning(f"Training control '{command}' failed: {detail}")
            # Re-enable button on error
            new_button_states[command] = {"disabled": False, "loading": False, "timestamp": 0}
        # ``command`` + ``detail`` feed the training-control-outcome-alert render
        # callback so a rejected command surfaces a dismissable danger alert
        # instead of silently bouncing the button back. See
        # notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md.
        return {"last": trigger, "ts": current_time, "success": success, "command": command, "detail": detail}, new_button_states

    @staticmethod
    def _extract_training_error_detail(exc: Exception) -> str:
        """Best-effort human-readable reason for a failed training-control POST.

        Prefers the backend's structured error message (cascor returns
        ``{"error": {"message": ...}}``; after cascor#332 a rejected Start names
        the specific reason, e.g. "Training cannot be started: Training data not
        provided"), then the raw response body, then the exception string. Never
        raises — error surfacing must not itself fail.
        """
        response = getattr(exc, "response", None)
        if response is not None:
            status = getattr(response, "status_code", None)
            message = None
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    err = payload.get("error")
                    if isinstance(err, dict):
                        message = err.get("message") or err.get("detail")
                    message = message or payload.get("message") or payload.get("detail")
            except Exception:
                message = None
            if not message:
                try:
                    body = (response.text or "").strip()
                    message = body[:300] if body else None
                except Exception:
                    message = None
            if message and status is not None:
                return f"HTTP {status}: {message}"
            if message:
                return str(message)
            if status is not None:
                return f"HTTP {status}"
        return f"{type(exc).__name__}: {exc}"

    def _update_last_click_handler(self, action=None):
        """Update last button click timestamp for debouncing."""
        if action and action.get("last"):
            return {"button": action["last"], "timestamp": action.get("ts", 0)}
        return dash.no_update

    # Human-readable labels for the outcome alert (matches the button captions).
    _TRAINING_COMMAND_LABELS = {"start": "Start", "pause": "Pause", "stop": "Stop", "resume": "Resume", "reset": "Reset"}

    def _surface_training_control_outcome_handler(self, action=None):
        """Render a dismissable danger alert when a training-control command failed.

        Both transports feed this single callback via the ``training-control-action``
        store: the server-side REST handler writes ``success``/``command``/``detail``
        directly, and the Phase D clientside JS writes the real *async* WS/REST
        outcome into the same store via ``dash_clientside.set_props`` once the command
        resolves. On success (or no action yet) we clear the surface — a later
        successful command dismisses any stale error — because the optimistic button
        state and the status broadcast already convey success. Only *failures* get an
        alert. See notes/CANOPY_TRAINING_CONTROL_ERROR_SURFACING_DESIGN_2026-06-14.md.
        """
        if not action or action.get("success", True):
            return None
        command = action.get("command") or ""
        label = self._TRAINING_COMMAND_LABELS.get(command, command.capitalize() or "Command")
        detail = (action.get("detail") or "").strip() or "the backend rejected the request."
        return dbc.Alert(
            [html.Strong(f"{label} failed. "), html.Span(detail)],
            color="danger",
            dismissable=True,
            duration=8000,
        )

    def _update_button_appearance_handler(self, button_states=None, model_key=None):
        """Update button states (disabled/loading) with visual feedback.

        A1-iv-5 / D8 Train-gate: when the selected model is non-live (``coming_soon`` /
        ``experimental`` / ``deprecated`` / ``broken``), the Start button is force-disabled
        regardless of training state — a non-live model is shown and selectable for inspection but
        not trainable (design §5.7). The pause / stop / resume / reset controls follow
        ``button-states`` unchanged. Live models (the common path) are entirely unaffected.
        """

        def get_button_props(cmd, label, icon):
            state = (button_states or {}).get(cmd, {"disabled": False, "loading": False, "timestamp": 0})
            disabled = state.get("disabled", False)
            loading = state.get("loading", False)
            text = f"⏳ {label}..." if loading else f"{icon} {label}"
            return disabled, text

        start_disabled, start_text = get_button_props("start", "Start Training", "▶")
        # D8 Train-gate: a non-live model can be selected (to inspect) but not trained.
        if not model_is_trainable(model_key):
            start_disabled = True
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
        """Enable/disable sub-inputs based on candidate selection mode.

        F-CANOPY-022: ``top_tier`` is the pre-fix value of this radio and is
        still accepted here so a persisted ``applied-params-store`` (or a
        browser session open across the upgrade) keeps gating correctly. The
        shipped option value is now ``top``, matching cascor's schema.
        """
        if selection_mode in ("top", "top_tier"):
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
        nn_output_epochs=_UNSET,
        nn_optimizer_type=_UNSET,
        nn_activation_function=_UNSET,
        nn_init_output_weights=_UNSET,
    ):
        """Apply parameters to backend and update applied store."""
        if not n_clicks:
            return dash.no_update, dash.no_update

        def checkbox_to_bool(v):
            return "enabled" in (v or [])

        # ── F-CANOPY-017 ──────────────────────────────────────────────────
        # A numeric ``dbc.Input`` whose current content fails HTML5 validity
        # (out of range, or — before the step sweep below — off the step grid)
        # delivers ``None`` as its Dash State. ``None`` therefore means "this
        # widget holds no committed value", NEVER "restore the factory
        # default". Substituting ``TrainingConstants.DEFAULT_*`` for it, as
        # this dict did, silently replaced the operator's live backend value
        # with a hardcoded constant: typing 0.0733 into the learning rate and
        # clicking Apply POSTed 0.01, which is neither the typed value nor the
        # 0.0789 that was live. The dirty tracker had already lit the Apply
        # button and shown "Unsaved changes", so it read as a pending edit.
        #
        # Refuse loudly instead. Omitting the keys is not an option: the
        # backend contract is the full form (see the 27-key body in
        # src/tests/ui/test_param_roundtrip_visible.py), so a partial payload
        # risks a wholesale 422.
        # ``_UNSET`` (the four late-added kwargs' default) means "this caller did
        # not supply the argument at all" — a signature contract, distinct from
        # ``None``, which means "the widget delivered no value". Only the latter
        # is the defect above; an omitted kwarg keeps its documented default.
        invalid_fields: list[str] = []

        def _num(value, label, cast, default=None):
            if value is _UNSET:
                return default
            if value is None:
                invalid_fields.append(label)
                return None
            try:
                return cast(value)
            except (TypeError, ValueError):
                invalid_fields.append(label)
                return None

        def _choice(value, default):
            return default if value is _UNSET or not value else value

        params = {
            "nn_max_iterations": _num(nn_max_iter, "Maximum Iterations", int),
            "nn_max_total_epochs": _num(nn_max_epochs, "Maximum Total Epochs", int),
            "nn_learning_rate": _num(nn_lr, "Learning Rate", float),
            "nn_max_hidden_units": _num(nn_max_hu, "Maximum Hidden Units", int),
            "nn_multi_node_layers": checkbox_to_bool(nn_multi_node),
            "nn_growth_trigger": nn_growth_trigger or TrainingConstants.DEFAULT_GROWTH_TRIGGER,
            "nn_growth_preset_epochs": _num(nn_growth_epochs, "Growth: Number of Epochs", int),
            "nn_growth_convergence_threshold": _num(nn_growth_conv_thresh, "Growth: Convergence Threshold", float),
            "nn_patience": _num(nn_patience, "Patience", int),
            "nn_spiral_rotations": _num(nn_spiral_rot, "Spiral Rotations", float),
            "nn_spiral_number": _num(nn_spiral_num, "Spiral Number", int),
            # #2b: nn_dataset_* are canopy-local and travel on /api/stage_dataset
            # (Issue #4 cold-swap), so they're no longer duplicated onto the
            # set_params payload (they were never mapped to cascor from here).
            "cn_pool_size": _num(cn_pool_size, "Candidate Pool Size", int),
            "cn_correlation_threshold": _num(cn_corr_thresh, "Correlation Threshold", float),
            "cn_selected_candidates": _num(cn_selected, "Selected Candidates", int),
            # #2b: cn_training_complete is a read-only status flag, not an
            # editable parameter — dropped from the set_params payload.
            "cn_training_iterations": _num(cn_training_iter, "Candidate Training Iterations", int),
            "cn_training_convergence_threshold": _num(cn_training_conv_thresh, "Candidate Convergence Threshold", float),
            "cn_patience": _num(cn_patience, "Candidate Patience", int),
            "cn_multi_candidate": checkbox_to_bool(cn_multi_cand),
            "cn_candidate_selection": cn_cand_selection,
            "cn_top_candidates": _num(cn_top_cands, "Top Candidates", int),
            "cn_random_candidates": _num(cn_random_cands, "Random Candidates", int),
            "nn_output_epochs": _num(nn_output_epochs, "Output Epochs (per pass)", int, TrainingConstants.DEFAULT_OUTPUT_EPOCHS),
            "nn_optimizer_type": _choice(nn_optimizer_type, TrainingConstants.DEFAULT_OPTIMIZER_TYPE),
            "nn_activation_function_name": _choice(nn_activation_function, TrainingConstants.DEFAULT_ACTIVATION_FUNCTION),
            "nn_init_output_weights": _choice(nn_init_output_weights, TrainingConstants.DEFAULT_INIT_OUTPUT_WEIGHTS),
        }

        if invalid_fields:
            preview = ", ".join(invalid_fields[:5]) + ("…" if len(invalid_fields) > 5 else "")
            self.logger.warning(f"Apply refused — {len(invalid_fields)} field(s) hold no valid value: {invalid_fields}")
            return dash.no_update, f"Nothing applied — {len(invalid_fields)} field(s) hold no valid value: {preview}. Correct them and Apply again."

        # N5 (I-4) / N3b: apply through the shared clamp → POST → applied/skipped
        # core so the params panel and the N3b restart modal go through identical
        # machinery (CascorPatchBounds clamp, ``_compose_apply_toast``, verbatim
        # rejection detail) — never a duplicated bounds/toast path.
        return self._apply_params_via_backend(params)

    def _apply_params_via_backend(self, params):
        """Shared apply core: clamp to cascor's PATCH bounds, POST /api/set_params
        (with the retry/backoff budget), return ``(applied_or_no_update, toast)``.

        Behind BOTH ``_apply_parameters_handler`` (the params panel) and the N3b
        restart modal's granular param apply, so N5's clamp (``CascorPatchBounds``),
        the applied/skipped toast (``_compose_apply_toast``), and the verbatim
        rejection detail (``_extract_apply_error_detail``) are called into once,
        never duplicated. ``applied`` is the clamped params dict on success
        (truthy) or ``dash.no_update`` on any failure; ``toast`` always carries the
        human-readable result / reason.
        """
        # N5 (I-4): defensively clamp submitted values to cascor's PATCH bounds
        # (mirrored in ``CascorPatchBounds``) before the POST, so a single
        # out-of-range field cannot wholesale-422 the whole form the way cascor's
        # pre-C2b epochs_max default did. Any clamp is surfaced in the toast
        # rather than silently changing the operator's intent.
        params, clamp_violations = CascorPatchBounds.clamp_params(params)

        max_retries = DashboardConstants.DASHBOARD_SET_PARAMS_MAX_RETRIES
        last_error = None
        for attempt in range(max_retries):
            try:
                response = requests.post(self._api_url("/api/set_params"), json=params, timeout=DashboardConstants.DASHBOARD_LONG_POST_TIMEOUT, headers=internal_api_headers())
                if response.status_code == 200:
                    # Verify parameters were applied by reading back state
                    try:
                        verify_resp = requests.get(self._api_url("/api/state"), timeout=DashboardConstants.DASHBOARD_GET_TIMEOUT, headers=internal_api_headers())
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
                    # N5 (I-4 / T3 + behavior 1): compose the toast from the
                    # adapter's own ``skipped`` (canopy keys with no cascor
                    # mapping — the pre-existing C1a "not yet supported" format),
                    # cascor's C2a ``applied``/``skipped_detail`` partition (what
                    # the live network took vs. declined, with the reason), and any
                    # client-side clamp note. See ``_compose_apply_toast``.
                    return params, self._compose_apply_toast(response, params, clamp_violations)
                elif response.status_code == 429:
                    # #2a: rate limited. Back off and retry within the existing
                    # retry budget instead of returning immediately. Honor the
                    # limiter's ``Retry-After`` (security.py sets it to the
                    # window reset in seconds) but cap the sleep — this runs on
                    # a Dash callback thread and the advertised value may be the
                    # full limiter window. After #345 exempted canopy's own
                    # self-calls, a 429 here means a genuine downstream limit,
                    # so this is a thin resilience net, not a hot path.
                    if attempt < max_retries - 1:
                        sleep_s = min(
                            self._parse_retry_after(response.headers.get("Retry-After")),
                            DashboardConstants.DASHBOARD_RETRY_AFTER_MAX_SLEEP_S,
                        )
                        self.logger.warning(f"Rate limited (429) on attempt {attempt + 1}/{max_retries}; backing off {sleep_s:.2f}s before retry")
                        time.sleep(sleep_s)
                        continue
                    self.logger.warning("Rate limited (429) — retries exhausted")
                    return dash.no_update, "Rate limited — please try again in a few seconds"
                else:
                    # N5 (I-4 / T1): carry the upstream rejection detail verbatim
                    # (truncated) into the toast instead of the bare status code —
                    # the evening-502s hid cascor's specific bound-violation reason
                    # (e.g. ``epochs_max le=1_000_000``) behind "Failed to apply
                    # (502)". Same pattern N4's snapshot toast now uses.
                    detail = self._extract_apply_error_detail(response)
                    self.logger.warning(f"Failed to apply: {response.status_code} {response.text}")
                    return dash.no_update, detail
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

    @staticmethod
    def _compose_apply_toast(response, params, clamp_violations):
        """Build the ``params-status`` toast for a 200 apply (N5, I-4 / T3).

        Renders, in order of specificity:

          * the adapter's own ``skipped`` (canopy keys with no cascor mapping —
            "not yet supported by the backend", the pre-existing §1.5 C1a
            format), else
          * cascor's C2a ``skipped_detail`` (``{key, reason}`` — ``not-updatable``
            / ``no-such-attribute`` / ``null-value``: what the live network
            declined and why; ``applied`` gives the took-count), else
          * the plain success line.

        A client-side clamp note (N5 behavior 1) is appended in every case. All
        three field reads are type-guarded because existing tests patch
        ``requests.post`` with a bare ``MagicMock`` whose ``.json()`` may return a
        Mock; only concretely-typed values are used, so a stubbed response falls
        through to "Parameters applied".
        """
        body = None
        try:
            body = response.json()
        except (ValueError, AttributeError):
            body = None

        adapter_skipped: list = []
        applied: list = []
        skipped_detail: list = []
        if isinstance(body, dict):
            cand = body.get("skipped")
            if isinstance(cand, list) and all(isinstance(k, str) for k in cand):
                adapter_skipped = cand
            cand = body.get("applied")
            if isinstance(cand, list) and all(isinstance(k, str) for k in cand):
                applied = cand
            cand = body.get("skipped_detail")
            if isinstance(cand, list) and all(isinstance(e, dict) and "key" in e for e in cand):
                skipped_detail = cand

        clamp_note = ""
        if clamp_violations:
            cparts = [f"{v['key']}→{v['clamped']}" for v in clamp_violations[:3]]
            clamp_note = f" (clamped to bounds: {', '.join(cparts)}" + ("…" if len(clamp_violations) > 3 else "") + ")"

        total = len(params)
        if adapter_skipped:
            applied_count = max(total - len(adapter_skipped), 0)
            preview = ", ".join(adapter_skipped[:5]) + ("…" if len(adapter_skipped) > 5 else "")
            return f"Applied {applied_count} of {total} parameter(s); {len(adapter_skipped)} not yet supported by the backend: {preview}{clamp_note}"
        if skipped_detail:
            applied_count = len(applied) if applied else max(total - len(skipped_detail), 0)
            parts = [f"{e['key']} ({e.get('reason', 'skipped')})" for e in skipped_detail[:5]]
            preview = ", ".join(parts) + ("…" if len(skipped_detail) > 5 else "")
            return f"Applied {applied_count} parameter(s); {len(skipped_detail)} skipped: {preview}{clamp_note}"
        return f"Parameters applied{clamp_note}"

    @staticmethod
    def _extract_apply_error_detail(response) -> str:
        """Best-effort verbatim rejection reason for a non-2xx apply (N5, I-4 / T1).

        Mirrors ``_extract_training_error_detail`` but reads a ``requests.Response``
        (the apply flow holds a response, not an exception). Prefers a structured
        backend message — canopy's ``/api/set_params`` 502 payload carries
        ``{"error": "Backend rejected parameters: <cascor detail>"}`` and cascor's
        own 4xx bodies use ``{"error": {"message": ...}}`` / ``detail`` — then
        falls back to the raw body text (truncated), then the bare status code.
        Never raises; error surfacing must not itself fail.
        """
        status = getattr(response, "status_code", None)
        message = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                err = payload.get("error")
                if isinstance(err, dict):
                    message = err.get("message") or err.get("detail")
                elif isinstance(err, str):
                    message = err
                message = message or payload.get("detail") or payload.get("message")
        except Exception:
            message = None
        if not message:
            try:
                body = (response.text or "").strip()
                message = body[:300] if body else None
            except Exception:
                message = None
        if message and status is not None:
            return f"Failed to apply (HTTP {status}): {str(message)[:300]}"
        if message:
            return f"Failed to apply: {str(message)[:300]}"
        if status is not None:
            return f"Failed to apply ({status})"
        return "Failed to apply"

    def _parse_retry_after(self, value):
        """Parse a ``Retry-After`` header into an (uncapped) sleep in seconds.

        canopy's rate limiter advertises ``Retry-After`` as integer
        delta-seconds (see ``security.py``). Per RFC 9110 the header may also be
        an HTTP-date; that form never originates from our own limiter, so we do
        not honor it and fall back to ``DASHBOARD_RETRY_AFTER_FALLBACK_S``.
        Missing, negative, or non-numeric values use the same fallback. The
        caller is responsible for capping the result at
        ``DASHBOARD_RETRY_AFTER_MAX_SLEEP_S``.
        """
        fallback = DashboardConstants.DASHBOARD_RETRY_AFTER_FALLBACK_S
        if value is None:
            return fallback
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return fallback
        return seconds if seconds >= 0 else fallback

    def _apply_in_flight_release(self, n_clicks):
        """E-3: value for the apply callback's `apply-in-flight` Output.

        Returns ``False`` (release the clamp) whenever the callback ran for a
        real click — the apply attempt is over by the time the server callback
        returns, success or failure alike. Returns ``dash.no_update`` for the
        no-click guard path (nothing armed the clamp). This is the
        server-side half of the E-3 fix; the clientside watchdog covers the
        request-never-completed class.
        """
        return False if n_clicks else dash.no_update

    def _update_stream_health_handler(self, n=None):
        """N2: poll /api/stream_health into stream-health-store for the badge.

        On fetch failure returns ``dash.no_update`` (the badge then falls back
        to browser-socket truth alone — an unreachable canopy already turns
        the badge red via the socket state).
        """
        try:
            url = self._api_url("/api/stream_health")
            response = requests.get(url, timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
            if not response.ok:
                self.logger.debug(f"Stream health API returned {response.status_code}")
                return dash.no_update
            return response.json()
        except Exception as e:
            self.logger.debug(f"Failed to fetch stream health: {e}")
            return dash.no_update

    def _init_params_from_backend_handler(self, n, current_applied):
        """Initialize input values and applied params from backend on first load."""
        NUM_OUTPUTS = 28
        if current_applied:
            return (dash.no_update,) * NUM_OUTPUTS
        try:
            response = requests.get(self._api_url("/api/state"), timeout=DashboardConstants.API_TIMEOUT_SECONDS, headers=internal_api_headers())
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

                # N5 (I-4): clamp backend-seeded values into cascor's PATCH bounds
                # (``CascorPatchBounds``) before they populate the form, so a
                # backend that echoes an out-of-range default (the pre-C2b
                # ``epochs_max``=1e11 class) can't seed a form that is doomed to a
                # wholesale 422 on the first apply. Re-read the bounded locals so
                # BOTH the visible inputs and the applied-params store carry the
                # clamped (admissible) value — otherwise they would disagree and
                # falsely show "unsaved changes".
                applied, seed_violations = CascorPatchBounds.clamp_params(applied)
                if seed_violations:
                    self.logger.warning(f"init_params_from_backend: clamped {len(seed_violations)} backend-seeded value(s) to PATCH bounds: {seed_violations}")
                    nn_max_iter = applied["nn_max_iterations"]
                    nn_max_epochs = applied["nn_max_total_epochs"]
                    nn_lr = applied["nn_learning_rate"]
                    nn_max_hu = applied["nn_max_hidden_units"]
                    nn_growth_conv_thresh = applied["nn_growth_convergence_threshold"]
                    nn_patience = applied["nn_patience"]
                    nn_output_epochs = applied["nn_output_epochs"]
                    cn_pool_size = applied["cn_pool_size"]
                    cn_corr_thresh = applied["cn_correlation_threshold"]
                    cn_selected = applied["cn_selected_candidates"]
                    cn_training_iter = applied["cn_training_iterations"]
                    cn_training_conv_thresh = applied["cn_training_convergence_threshold"]
                    cn_patience = applied["cn_patience"]
                    cn_top_cands = applied["cn_top_candidates"]
                    cn_random_cands = applied["cn_random_candidates"]

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
