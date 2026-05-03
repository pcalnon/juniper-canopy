#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     network_editor_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-05-03
# Last Modified: 2026-05-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Network Editor UI component (Phase 6E CAN-015h, h-5).
#    Drives the cascor mutation endpoints via the canopy
#    /api/v1/network/{weights,hidden-units} proxies.
#
#####################################################################
"""Network editor panel — surgical mutations on a restored snapshot.

V1 surface (per Phase 6E CAN-015h design):

- Idle state when the cascor FSM is not ``Investigating``.
  Restoring a snapshot from the Snapshots tab transitions the
  FSM into ``Investigating`` and unlocks the active state.
- Active state:
  - Topology readout — input size, output size, hidden unit list.
  - Append-hidden-unit form (tail-only in V1).
  - Remove-hidden-unit form (index picker + Delete button).
  - Patch-weights form (target picker + values textarea).

Each form posts JSON to the matching canopy proxy route under
``/api/v1/network/...`` which forwards to the adapter; the adapter
talks to the cascor ``PATCH /v1/network/weights`` /
``POST /v1/network/hidden-units`` /
``DELETE /v1/network/hidden-units/{idx}`` endpoints landed in
CAN-015h-1, h-2, h-3 (see juniper-cascor PRs #199, #200, #201).

The h-6 follow-up wires this panel into the snapshot panel's
B-5 confirm-modal pattern and adds the "snapshot first?" prompt
prior to destructive operations.
"""

from typing import Any, Dict, List, Optional

import dash
import dash_bootstrap_components as dbc
import requests
from dash import Input, Output, State, dcc, html

from ..base_component import BaseComponent

# Activation choices mirror the cascor side's accepted set; we send
# the label verbatim and the cascor add-hidden-unit route validates it
# against ``ACTIVATION_FN_REGISTRY``. Anything not in this list will
# be rejected upstream with a 422.
_ACTIVATION_CHOICES = ["Tanh", "Sigmoid", "ReLU", "Linear"]

# Patch targets accepted by PATCH /v1/network/weights. The cascor
# layer enforces shape and NaN/Inf validation; we just send the
# label through. ``hidden_unit_*`` targets require a
# ``hidden_unit_index``.
_PATCH_TARGETS = [
    {"label": "Output weights", "value": "output_weights"},
    {"label": "Output bias", "value": "output_bias"},
    {"label": "Hidden unit weights", "value": "hidden_unit_weights"},
    {"label": "Hidden unit bias", "value": "hidden_unit_bias"},
]


class NetworkEditorPanel(BaseComponent):
    """Network Editor: surgical topology + weight mutations."""

    def __init__(self, config: Dict[str, Any], component_id: str = "network-editor-panel"):
        super().__init__(config, component_id)
        self._api_base_url = config.get("api_base_url", "")
        self.api_timeout = float(config.get("api_timeout", 5))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def get_layout(self):
        idle_state = self._build_idle_state()
        active_state = self._build_active_state()

        return html.Div(
            [
                html.H4("Network Editor", style={"marginBottom": "10px"}),
                html.P(
                    "Surgical edits to the loaded network — append/remove " "hidden units and patch individual parameter groups. " "Available only while the cascor FSM is in the " "Investigating state, which is entered by restoring a " "snapshot from the Snapshots tab.",
                    style={"fontSize": "0.85rem", "color": "var(--text-muted)"},
                ),
                html.Div(idle_state, id=f"{self.component_id}-idle", style={"display": "block"}),
                html.Div(active_state, id=f"{self.component_id}-active", style={"display": "none"}),
                html.Div(id=f"{self.component_id}-status", style={"marginTop": "10px"}),
                # Polled FSM state — we don't have a Store carrying
                # cascor's state_machine summary, so the panel pulls it
                # itself via /api/status on a 2s tick. The interval is
                # cheap and only fires while the user is on this tab.
                dcc.Interval(id=f"{self.component_id}-fsm-poll", interval=2000, n_intervals=0),
                # Topology snapshot for the readout + remove-unit
                # picker. Refreshed every poll tick when active.
                dcc.Store(id=f"{self.component_id}-topology-store", data=None),
            ],
            id=f"{self.component_id}-root",
            style={"padding": "10px"},
        )

    def _build_idle_state(self):
        return dbc.Card(
            dbc.CardBody(
                [
                    html.H5("Editor disabled", style={"color": "var(--text-muted)"}),
                    html.P(
                        [
                            "Restore a snapshot from the ",
                            html.B("Snapshots"),
                            " tab to enter the ",
                            html.Code("Investigating"),
                            " state. Once the FSM is in Investigating the " "editor will unlock automatically.",
                        ],
                        style={"fontSize": "0.85rem"},
                    ),
                    html.Div(
                        dbc.Badge(
                            "FSM: --",
                            id=f"{self.component_id}-idle-fsm-badge",
                            color="secondary",
                            className="me-2",
                        ),
                        style={"marginTop": "8px"},
                    ),
                ]
            ),
            color="light",
            outline=True,
        )

    def _build_active_state(self):
        return html.Div(
            [
                # Topology readout
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Topology", style={"marginBottom": "8px"}),
                            html.Div(
                                id=f"{self.component_id}-topology-readout",
                                style={"fontSize": "0.85rem"},
                            ),
                        ]
                    ),
                    style={"marginBottom": "12px"},
                ),
                # Append hidden unit
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Append hidden unit", style={"marginBottom": "8px"}),
                            html.P(
                                [
                                    "Appends one unit at the cascade tail. The weight vector length must equal ",
                                    html.Code("input_size + num_existing_hidden_units"),
                                    ". The new unit's output column is initialized to zero so it contributes " "nothing until you patch the output layer or re-train.",
                                ],
                                style={"fontSize": "0.8rem", "color": "var(--text-muted)"},
                            ),
                            dbc.Label("Weights (comma-separated)", html_for=f"{self.component_id}-add-weights"),
                            dbc.Textarea(
                                id=f"{self.component_id}-add-weights",
                                placeholder="0.1, -0.2, 0.05, ...",
                                rows=2,
                                style={"fontFamily": "monospace", "fontSize": "0.8rem"},
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Bias", html_for=f"{self.component_id}-add-bias"),
                                            dbc.Input(
                                                id=f"{self.component_id}-add-bias",
                                                type="number",
                                                value=0.0,
                                                step=0.01,
                                            ),
                                        ],
                                        width=6,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Activation", html_for=f"{self.component_id}-add-activation"),
                                            dbc.Select(
                                                id=f"{self.component_id}-add-activation",
                                                options=[{"label": a, "value": a} for a in _ACTIVATION_CHOICES],
                                                value="Tanh",
                                            ),
                                        ],
                                        width=6,
                                    ),
                                ],
                                className="g-2 mb-2",
                            ),
                            dbc.Button(
                                "Append unit",
                                id=f"{self.component_id}-add-submit",
                                color="primary",
                                size="sm",
                            ),
                        ]
                    ),
                    style={"marginBottom": "12px"},
                ),
                # Remove hidden unit
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Remove hidden unit", style={"marginBottom": "8px"}),
                            html.P(
                                "Drops the unit at the chosen index and rebuilds " "the cascade so the forward-pass shape invariant " "still holds. The optimizer is dropped — fresh " "training will rebuild it.",
                                style={"fontSize": "0.8rem", "color": "var(--text-muted)"},
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Unit index", html_for=f"{self.component_id}-remove-idx"),
                                            dbc.Select(
                                                id=f"{self.component_id}-remove-idx",
                                                options=[],
                                                placeholder="Select a unit",
                                            ),
                                        ],
                                        width=6,
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "Delete unit",
                                            id=f"{self.component_id}-remove-submit",
                                            color="danger",
                                            size="sm",
                                            style={"marginTop": "30px"},
                                        ),
                                        width=6,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ]
                    ),
                    style={"marginBottom": "12px"},
                ),
                # Patch weights
                dbc.Card(
                    dbc.CardBody(
                        [
                            html.H5("Patch weights", style={"marginBottom": "8px"}),
                            html.P(
                                "Surgically rewrites a single parameter group. " "The cascor side validates shape, dtype, and " "NaN/Inf — invalid patches are rejected without " "touching network state.",
                                style={"fontSize": "0.8rem", "color": "var(--text-muted)"},
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            dbc.Label("Target", html_for=f"{self.component_id}-patch-target"),
                                            dbc.Select(
                                                id=f"{self.component_id}-patch-target",
                                                options=_PATCH_TARGETS,
                                                value="output_weights",
                                            ),
                                        ],
                                        width=6,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Label("Hidden unit index", html_for=f"{self.component_id}-patch-idx"),
                                            dbc.Input(
                                                id=f"{self.component_id}-patch-idx",
                                                type="number",
                                                min=0,
                                                step=1,
                                                placeholder="Required for hidden_unit_* targets",
                                            ),
                                        ],
                                        width=6,
                                    ),
                                ],
                                className="g-2 mb-2",
                            ),
                            dbc.Label("Values (comma-separated, row-major)", html_for=f"{self.component_id}-patch-values"),
                            dbc.Textarea(
                                id=f"{self.component_id}-patch-values",
                                placeholder="0.1, 0.2, 0.3, ...",
                                rows=3,
                                style={"fontFamily": "monospace", "fontSize": "0.8rem"},
                            ),
                            dbc.Button(
                                "Apply patch",
                                id=f"{self.component_id}-patch-submit",
                                color="primary",
                                size="sm",
                            ),
                        ]
                    ),
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_investigating(status: Dict[str, Any]) -> bool:
        """Return True iff the cascor FSM is in ``Investigating``.

        ``/api/status`` returns the lifecycle's full status dict which
        nests the FSM summary under ``state_machine``; we tolerate
        both the unwrapped shape and a top-level ``status`` field for
        older / partial responses.
        """
        if not isinstance(status, dict):
            return False
        sm = status.get("state_machine") or {}
        name = (sm.get("status") or status.get("status") or "").upper()
        return name == "INVESTIGATING"

    @staticmethod
    def _parse_float_list(text: Optional[str]) -> List[float]:
        """Parse a comma/whitespace-separated string into a list of floats.

        Tolerates trailing commas and whitespace. Raises ``ValueError``
        on any unparseable token so the callback can surface a clear
        error to the user.
        """
        if not text or not text.strip():
            return []
        cleaned = text.replace("\n", ",").replace(";", ",")
        out: List[float] = []
        for tok in cleaned.split(","):
            tok = tok.strip()
            if not tok:
                continue
            out.append(float(tok))
        return out

    def _post_json(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Issue a JSON request to a canopy proxy route.

        Returns ``{"success": bool, "data"|"error": ...}`` mirroring
        the replay-player panel's convention.
        """
        url = f"{self._api_base_url}{path}"
        try:
            if method == "POST":
                resp = requests.post(url, json=body or {}, timeout=self.api_timeout + 5)
            elif method == "PATCH":
                resp = requests.patch(url, json=body or {}, timeout=self.api_timeout + 5)
            elif method == "DELETE":
                resp = requests.delete(url, timeout=self.api_timeout + 5)
            else:
                return {"success": False, "error": f"Unsupported method {method!r}"}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Service unavailable"}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}

        if 200 <= resp.status_code < 300:
            try:
                return {"success": True, "data": resp.json()}
            except ValueError:
                return {"success": True, "data": {}}
        try:
            detail = resp.json().get("detail", f"HTTP {resp.status_code}")
        except ValueError:
            detail = f"HTTP {resp.status_code}"
        return {"success": False, "error": detail}

    @staticmethod
    def _status_alert(success: bool, message: str):
        return dbc.Alert(message, color="success" if success else "danger", style={"fontSize": "0.85rem"})

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def register_callbacks(self, app):
        component_id = self.component_id

        @app.callback(
            Output(f"{component_id}-idle", "style"),
            Output(f"{component_id}-active", "style"),
            Output(f"{component_id}-idle-fsm-badge", "children"),
            Output(f"{component_id}-topology-store", "data"),
            Input(f"{component_id}-fsm-poll", "n_intervals"),
        )
        def poll_fsm_and_topology(_n):
            """Poll /api/status; flip idle/active visibility on Investigating.

            Also pulls /api/network/topology when active so the
            readout + remove-unit dropdown stay current.
            """
            try:
                status_resp = requests.get(
                    f"{self._api_base_url}/api/status",
                    timeout=self.api_timeout,
                )
                status = status_resp.json() if status_resp.status_code == 200 else {}
            except Exception:  # noqa: BLE001
                status = {}

            sm = status.get("state_machine") or {}
            fsm_name = (sm.get("status") or status.get("status") or "Unknown").title()
            badge_text = f"FSM: {fsm_name}"

            if not self._is_investigating(status):
                return (
                    {"display": "block"},
                    {"display": "none"},
                    badge_text,
                    None,
                )

            # Active — fetch topology for the readout / remove picker.
            topology: Optional[Dict[str, Any]] = None
            try:
                topo_resp = requests.get(
                    f"{self._api_base_url}/api/network/topology",
                    timeout=self.api_timeout,
                )
                if topo_resp.status_code == 200:
                    topology = topo_resp.json()
            except Exception:  # noqa: BLE001
                topology = None

            return (
                {"display": "none"},
                {"display": "block"},
                badge_text,
                topology,
            )

        @app.callback(
            Output(f"{component_id}-topology-readout", "children"),
            Output(f"{component_id}-remove-idx", "options"),
            Input(f"{component_id}-topology-store", "data"),
        )
        def render_topology(topology):
            if not topology:
                return html.Em("No topology loaded.", style={"color": "var(--text-muted)"}), []
            input_size = topology.get("input_size") or topology.get("input_units") or 0
            output_size = topology.get("output_size") or topology.get("output_units") or 0
            hidden_units = topology.get("hidden_units")
            if isinstance(hidden_units, int):
                num_hidden = hidden_units
                unit_rows: List[Any] = []
            else:
                hidden_units = hidden_units or []
                num_hidden = len(hidden_units)
                unit_rows = [
                    html.Tr(
                        [
                            html.Td(str(i)),
                            html.Td(str(u.get("activation", "?"))),
                            html.Td(str(len(u.get("weights", [])))),
                        ]
                    )
                    for i, u in enumerate(hidden_units)
                    if isinstance(u, dict)
                ]

            readout: List[Any] = [
                html.Div(f"Inputs: {input_size}    Outputs: {output_size}    Hidden units: {num_hidden}"),
            ]
            if unit_rows:
                readout.append(
                    dbc.Table(
                        [
                            html.Thead(html.Tr([html.Th("Index"), html.Th("Activation"), html.Th("Weight count")])),
                            html.Tbody(unit_rows),
                        ],
                        bordered=True,
                        size="sm",
                        striped=True,
                        style={"marginTop": "8px"},
                    )
                )
            options = [{"label": f"Unit {i}", "value": i} for i in range(num_hidden)]
            return readout, options

        @app.callback(
            Output(f"{component_id}-status", "children", allow_duplicate=True),
            Input(f"{component_id}-add-submit", "n_clicks"),
            State(f"{component_id}-add-weights", "value"),
            State(f"{component_id}-add-bias", "value"),
            State(f"{component_id}-add-activation", "value"),
            prevent_initial_call=True,
        )
        def on_add_unit(n_clicks, weights_text, bias, activation):
            if not n_clicks:
                return dash.no_update
            try:
                weights = self._parse_float_list(weights_text)
            except ValueError as e:
                return self._status_alert(False, f"Could not parse weights: {e}")
            if not weights:
                return self._status_alert(False, "Weights are required.")
            try:
                bias_val = float(bias) if bias is not None else 0.0
            except (TypeError, ValueError):
                return self._status_alert(False, "Bias must be numeric.")
            result = self._post_json(
                "POST",
                "/api/v1/network/hidden-units",
                {"weights": weights, "bias": bias_val, "activation": activation or "Tanh"},
            )
            if result["success"]:
                data = result["data"]
                idx = data.get("unit_index")
                total = data.get("num_hidden_units")
                return self._status_alert(True, f"Appended unit at index {idx} (now {total} hidden units).")
            return self._status_alert(False, f"Add failed: {result['error']}")

        @app.callback(
            Output(f"{component_id}-status", "children", allow_duplicate=True),
            Input(f"{component_id}-remove-submit", "n_clicks"),
            State(f"{component_id}-remove-idx", "value"),
            prevent_initial_call=True,
        )
        def on_remove_unit(n_clicks, idx):
            if not n_clicks:
                return dash.no_update
            if idx is None or idx == "":
                return self._status_alert(False, "Pick a unit to delete.")
            try:
                idx_int = int(idx)
            except (TypeError, ValueError):
                return self._status_alert(False, "Invalid unit index.")
            result = self._post_json("DELETE", f"/api/v1/network/hidden-units/{idx_int}")
            if result["success"]:
                data = result["data"]
                total = data.get("num_hidden_units")
                return self._status_alert(True, f"Removed unit {idx_int} (now {total} hidden units).")
            return self._status_alert(False, f"Remove failed: {result['error']}")

        @app.callback(
            Output(f"{component_id}-status", "children", allow_duplicate=True),
            Input(f"{component_id}-patch-submit", "n_clicks"),
            State(f"{component_id}-patch-target", "value"),
            State(f"{component_id}-patch-idx", "value"),
            State(f"{component_id}-patch-values", "value"),
            prevent_initial_call=True,
        )
        def on_patch_weights(n_clicks, target, hidden_idx, values_text):
            if not n_clicks:
                return dash.no_update
            if not target:
                return self._status_alert(False, "Pick a patch target.")
            try:
                values = self._parse_float_list(values_text)
            except ValueError as e:
                return self._status_alert(False, f"Could not parse values: {e}")
            if not values:
                return self._status_alert(False, "Values are required.")

            field_map = {
                "output_weights": "weights",
                "output_bias": "bias",
                "hidden_unit_weights": "weights",
                "hidden_unit_bias": "bias",
            }
            field = field_map.get(target, "weights")
            body: Dict[str, Any] = {
                "target": target,
                "field": field,
                "values": values,
                "dtype": "float32",
            }
            if target.startswith("hidden_unit_"):
                if hidden_idx is None or hidden_idx == "":
                    return self._status_alert(False, "hidden_unit_index is required for hidden_unit_* targets.")
                try:
                    body["hidden_unit_index"] = int(hidden_idx)
                except (TypeError, ValueError):
                    return self._status_alert(False, "hidden_unit_index must be an integer.")

            result = self._post_json("PATCH", "/api/v1/network/weights", body)
            if result["success"]:
                return self._status_alert(True, f"Patched {target}.{field} ({len(values)} values).")
            return self._status_alert(False, f"Patch failed: {result['error']}")
