#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     parameters_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-03-31
# Last Modified: 2026-03-31
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Parameters panel component displaying a read-only summary of all meta parameters
#    organized into Network Training, Dataset, and Candidate Training sections.
#
#####################################################################################################################################################################################################
# Notes:
#
# Parameters Panel Component
#
# Display-only panel showing current applied parameter values in organized tables.
# Editing is done via the sidebar controls; this panel provides an at-a-glance overview.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#   - Initial implementation
#
#####################################################################################################################################################################################################
from typing import Any, Dict

import dash_bootstrap_components as dbc
from dash import dcc, html

from canopy_constants import TrainingConstants

from ..base_component import BaseComponent

# Parameter definitions: (key, display_name, default, min, max)
NETWORK_TRAINING_PARAMS = [
    ("max_iterations", "Maximum Growth Iterations", TrainingConstants.DEFAULT_MAX_GROWTH_ITERATIONS, TrainingConstants.MIN_MAX_GROWTH_ITERATIONS, TrainingConstants.MAX_MAX_GROWTH_ITERATIONS),
    ("max_total_epochs", "Maximum Total Epochs", TrainingConstants.DEFAULT_TRAINING_EPOCHS, TrainingConstants.MIN_TRAINING_EPOCHS, TrainingConstants.MAX_TRAINING_EPOCHS),
    ("learning_rate", "Learning Rate", TrainingConstants.DEFAULT_LEARNING_RATE, TrainingConstants.MIN_LEARNING_RATE, TrainingConstants.MAX_LEARNING_RATE),
    ("max_hidden_units", "Maximum Hidden Units", TrainingConstants.DEFAULT_MAX_HIDDEN_UNITS, TrainingConstants.MIN_HIDDEN_UNITS, TrainingConstants.MAX_HIDDEN_UNITS),
    ("multi_node_layers", "Multi-Node Layers", TrainingConstants.DEFAULT_MULTI_NODE_LAYERS, "—", "—"),
    ("growth_trigger", "Growth Trigger", TrainingConstants.DEFAULT_GROWTH_TRIGGER, "—", "—"),
    ("growth_preset_epochs", "Growth Preset Epochs", TrainingConstants.DEFAULT_PRESET_EPOCHS, TrainingConstants.MIN_PRESET_EPOCHS, TrainingConstants.MAX_PRESET_EPOCHS),
    ("growth_convergence_threshold", "Growth Convergence Threshold", TrainingConstants.DEFAULT_CONVERGENCE_THRESHOLD, TrainingConstants.MIN_CONVERGENCE_THRESHOLD, TrainingConstants.MAX_CONVERGENCE_THRESHOLD),
]

DATASET_PARAMS = [
    ("spiral_rotations", "Spiral Rotations", TrainingConstants.DEFAULT_SPIRAL_ROTATIONS, TrainingConstants.MIN_SPIRAL_ROTATIONS, TrainingConstants.MAX_SPIRAL_ROTATIONS),
    ("spiral_number", "Spiral Number", TrainingConstants.DEFAULT_SPIRAL_NUMBER, TrainingConstants.MIN_SPIRAL_NUMBER, TrainingConstants.MAX_SPIRAL_NUMBER),
    ("dataset_elements", "Dataset Elements", TrainingConstants.DEFAULT_DATASET_ELEMENTS, TrainingConstants.MIN_DATASET_ELEMENTS, TrainingConstants.MAX_DATASET_ELEMENTS),
    ("dataset_noise", "Dataset Noise", TrainingConstants.DEFAULT_DATASET_NOISE, TrainingConstants.MIN_DATASET_NOISE, TrainingConstants.MAX_DATASET_NOISE),
]

CANDIDATE_TRAINING_PARAMS = [
    ("pool_size", "Pool Size", TrainingConstants.DEFAULT_CANDIDATE_POOL_SIZE, TrainingConstants.MIN_CANDIDATE_POOL_SIZE, TrainingConstants.MAX_CANDIDATE_POOL_SIZE),
    ("correlation_threshold", "Correlation Threshold", TrainingConstants.DEFAULT_CANDIDATE_CORRELATION_THRESHOLD, TrainingConstants.MIN_CANDIDATE_CORRELATION_THRESHOLD, TrainingConstants.MAX_CANDIDATE_CORRELATION_THRESHOLD),
    ("selected_candidates", "Selected Candidates", TrainingConstants.DEFAULT_SELECTED_CANDIDATES, TrainingConstants.MIN_SELECTED_CANDIDATES, TrainingConstants.MAX_SELECTED_CANDIDATES),
    ("training_complete", "Training Complete", TrainingConstants.DEFAULT_CN_TRAINING_COMPLETE, "—", "—"),
    ("training_iterations", "Training Iterations", TrainingConstants.DEFAULT_CANDIDATE_TRAINING_ITERATIONS, TrainingConstants.MIN_CANDIDATE_TRAINING_ITERATIONS, TrainingConstants.MAX_CANDIDATE_TRAINING_ITERATIONS),
    ("training_convergence_threshold", "Training Convergence Threshold", TrainingConstants.DEFAULT_CANDIDATE_CONVERGENCE_THRESHOLD, TrainingConstants.MIN_CANDIDATE_CONVERGENCE_THRESHOLD, TrainingConstants.MAX_CANDIDATE_CONVERGENCE_THRESHOLD),
    ("multi_candidate", "Multi-Candidate", TrainingConstants.DEFAULT_MULTI_CANDIDATE_ENABLED, "—", "—"),
    ("candidate_selection", "Candidate Selection", "—", "—", "—"),
    ("top_candidates", "Top Candidates", TrainingConstants.DEFAULT_TOP_CANDIDATES_COUNT, TrainingConstants.MIN_TOP_CANDIDATES_COUNT, TrainingConstants.MAX_TOP_CANDIDATES_COUNT),
    ("random_candidates", "Random Candidates", TrainingConstants.DEFAULT_RANDOM_CANDIDATES_COUNT, TrainingConstants.MIN_RANDOM_CANDIDATES_COUNT, TrainingConstants.MAX_RANDOM_CANDIDATES_COUNT),
]


def _build_table(params, data, pinned_keys=None):
    """Build a dbc.Table from parameter definitions and current data.

    CAN-005: when ``pinned_keys`` is provided, each row gains a pin
    checkbox in a leading column. Toggling the checkbox writes to
    ``pinned-params-store``; the canopy sidebar mirrors the current
    value of every pinned param in a read-only "Pinned Parameters"
    card so the user can see the values they care about at a glance
    from any tab.
    """
    pinned_set = set(pinned_keys or [])
    header_cells = []
    if pinned_keys is not None:
        header_cells.append(html.Th("Pin", style={"width": "44px"}))
    header_cells.extend(
        [
            html.Th("Parameter"),
            html.Th("Current Value"),
            html.Th("Min"),
            html.Th("Max"),
            html.Th("Default"),
        ]
    )
    header = html.Thead(html.Tr(header_cells))

    rows = []
    for key, name, default, min_val, max_val in params:
        current = data.get(key, "—")
        if isinstance(current, bool):
            current = "Enabled" if current else "Disabled"
        elif isinstance(current, list):
            current = "Enabled" if "enabled" in current else "Disabled"

        cells = []
        if pinned_keys is not None:
            cells.append(
                html.Td(
                    dbc.Checkbox(
                        id={"type": "param-pin", "key": key},
                        value=key in pinned_set,
                        # Empty visible label; aria text lives on the table cell
                        label="",
                        label_class_name="visually-hidden",
                    ),
                    style={"textAlign": "center"},
                )
            )
        cells.extend(
            [
                html.Td(name),
                html.Td(html.Strong(str(current))),
                html.Td(str(min_val)),
                html.Td(str(max_val)),
                html.Td(str(default)),
            ]
        )
        rows.append(html.Tr(cells))

    body = html.Tbody(rows)
    return dbc.Table(
        [header, body],
        bordered=True,
        hover=True,
        responsive=True,
        size="sm",
        className="mb-0",
    )


# CAN-005: name lookup for the sidebar's "Pinned Parameters" mirror.
# Concatenated here so dashboard_manager can render pinned param rows
# without re-importing each per-section list.
ALL_PARAMS = NETWORK_TRAINING_PARAMS + DATASET_PARAMS + CANDIDATE_TRAINING_PARAMS
PARAM_DISPLAY_NAMES = {key: name for (key, name, *_rest) in ALL_PARAMS}


class ParametersPanel(BaseComponent):
    """
    Parameters panel component displaying read-only summary of all meta parameters.

    Shows:
    - Network Training parameters
    - Dataset parameters
    - Candidate Training parameters

    Each section is presented as a card with a summary table showing
    parameter name, current value, min, max, and default columns.
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "parameters-panel"):
        """
        Initialize parameters panel component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)
        self.logger.info("ParametersPanel initialized")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for parameters panel.

        Returns:
            Dash Div containing the parameters overview
        """
        return html.Div(
            [
                html.Div(
                    [
                        html.H3(
                            "Meta Parameters",
                            style={"color": "var(--header-color)", "marginBottom": "5px"},
                        ),
                        html.P(
                            "Read-only overview of current applied parameter values. " "Use the sidebar controls to edit parameters.",
                            style={"fontSize": "13px", "color": "var(--text-muted)", "marginBottom": "20px"},
                        ),
                    ],
                ),
                # Network Training card
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Network Training", className="mb-0")),
                        dbc.CardBody(
                            html.Div(id=f"{self.component_id}-network-table"),
                        ),
                    ],
                    className="mb-3",
                ),
                # Dataset card
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Dataset", className="mb-0")),
                        dbc.CardBody(
                            html.Div(id=f"{self.component_id}-dataset-table"),
                        ),
                    ],
                    className="mb-3",
                ),
                # Candidate Training card
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("Candidate Training", className="mb-0")),
                        dbc.CardBody(
                            html.Div(id=f"{self.component_id}-candidate-table"),
                        ),
                    ],
                    className="mb-3",
                ),
                # Store to receive parameter data
                dcc.Store(id=f"{self.component_id}-params-store", data={}),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "900px", "margin": "0 auto"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for parameters panel.

        Args:
            app: Dash application instance
        """
        from dash.dependencies import Input, Output

        # PERF-CN-01: prevent_initial_call=False — must render the parameter
        # tables on mount so the panel is not blank before the params-store is
        # populated by the parameters-applied flow.
        # CAN-005: also reads `pinned-params-store` so the table re-renders
        # the checkbox column with the current pin state.
        @app.callback(
            [
                Output(f"{self.component_id}-network-table", "children"),
                Output(f"{self.component_id}-dataset-table", "children"),
                Output(f"{self.component_id}-candidate-table", "children"),
            ],
            [
                Input(f"{self.component_id}-params-store", "data"),
                Input("pinned-params-store", "data"),
            ],
            prevent_initial_call=False,
        )
        def update_parameters_tables(data, pinned):
            """Update parameter tables when store data changes."""
            if not data:
                data = {}
            pinned_keys = list(pinned or [])
            network_data = {p[0]: data.get(p[0], p[2]) for p in NETWORK_TRAINING_PARAMS}
            dataset_data = {p[0]: data.get(p[0], p[2]) for p in DATASET_PARAMS}
            candidate_data = {p[0]: data.get(p[0], p[2]) for p in CANDIDATE_TRAINING_PARAMS}
            return (
                _build_table(NETWORK_TRAINING_PARAMS, network_data, pinned_keys=pinned_keys),
                _build_table(DATASET_PARAMS, dataset_data, pinned_keys=pinned_keys),
                _build_table(CANDIDATE_TRAINING_PARAMS, candidate_data, pinned_keys=pinned_keys),
            )

        self._cb_update_parameters_tables = update_parameters_tables

        self.logger.debug(f"Callbacks registered for {self.component_id}")
