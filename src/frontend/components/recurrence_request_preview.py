#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       Read-only "effective request" preview for the recurrence one-shot Start (W1.2 / ruling R7)
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     recurrence_request_preview.py
# File Path:     JuniperCanopy/juniper_canopy/src/frontend/components/
#
# Date Created:  2026-10-08
# Last Modified: 2026-10-08
#
# License:       MIT License
# Copyright:     Copyright (c) 2024,2025,2026 Paul Calnon
#
# Description:
#     W1.2 of juniper-ml's plan notes/JUNIPER_2026-10-03_JUNIPER-RECURRENCE_EQUITIES-END-TO-END-AUDIT-AND-DEVELOPMENT-PLAN.md
#     (finding F-C2: "No preview of the effective request before Start"). Ruling R7's recommended
#     default, applied pending the owner's ruling, asks for "a read-only JSON 'effective request'
#     preview shown before Start and logged at INFO". This panel sits above the Start button, is
#     visible only for a one-shot (recurrence) model, and shows the exact POST /v1/train body the
#     next Start would send, as the backend resolves it (POST /api/recurrence/effective_request).
#
#####################################################################################################################################################################################################
# Notes:
#     - Its own module so DashboardManager carries only the wiring (an instance, one layout line).
#     - Refreshes on EVENTS, never on an interval: the one-shot Start body changing (model or
#       dataset), Apply finishing (``dataset-stage-outcome-alert`` has that one writer), the
#       pending-dataset banner opening or closing (a clientside edge detector, so the 5 s banner
#       poll costs no server dispatch), and the Refresh link.
#
#####################################################################################################################################################################################################
"""Read-only preview of the request the next recurrence Start sends (W1.2 / ruling R7)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import dash_bootstrap_components as dbc
import requests
from dash import Input, Output, State, dcc, html

from canopy_constants import DashboardConstants
from frontend.internal_api import internal_api_headers
from settings import get_settings

from ..base_component import BaseComponent

# The route that resolves the preview. Read-only on the server: nothing is staged, consumed or started.
EFFECTIVE_REQUEST_PATH = "/api/recurrence/effective_request"

# ``model-class-store`` value for a one-shot model -- the only class with a recurrence request to show.
_ONE_SHOT = "one_shot"

_HIDDEN: Dict[str, str] = {"display": "none"}
_SHOWN: Dict[str, str] = {"display": "block"}

# Clientside edge detector over ``pending-dataset-banner.is_open``. That prop is rewritten by the 5 s
# slow-lane poll whether or not it changed; refreshing the preview on every write would add a server
# dispatch (and an INFO log line) every five seconds. This emits only when the value CHANGES -- a
# dataset staged by another tab, cancelled, or consumed by a Start -- and idles with ``no_update``.
# Its consumer is not interval-driven, so the no_update chaining hazard (AGENTS.md) does not apply.
BANNER_EDGE_JS = """
function(isOpen, previous) {
    var open = Boolean(isOpen);
    if (previous && previous.open === open) {
        return window.dash_clientside.no_update;
    }
    return {open: open};
}
"""


class RecurrenceRequestPreview(BaseComponent):
    """The "effective request" panel: the exact recurrence ``POST /v1/train`` body, before Start."""

    def __init__(self, config: Dict[str, Any], component_id: str = "recurrence-request-preview"):
        super().__init__(config, component_id)
        self._api_base_url = config.get("api_base_url", f"http://127.0.0.1:{get_settings().server.port}")
        self.api_timeout = float(config.get("api_timeout", DashboardConstants.API_TIMEOUT_SECONDS))

    # ------------------------------------------------------------------ layout

    def get_layout(self) -> html.Div:
        cid = self.component_id
        return html.Div(
            [
                html.Div(
                    [
                        html.Small("Effective request (next Start)", className="fw-bold"),
                        dbc.Button("Refresh", id=f"{cid}-refresh", color="link", size="sm", className="p-0 ms-2"),
                    ],
                    className="d-flex align-items-baseline",
                ),
                html.Pre(id=f"{cid}-body", className="mb-1", style={"maxHeight": "14rem", "overflowY": "auto", "whiteSpace": "pre-wrap", "wordBreak": "break-word", "fontSize": "0.7rem"}, **{"aria-live": "polite"}),
                html.Div(id=f"{cid}-notes", className="text-muted", style={"fontSize": "0.7rem"}, **{"aria-live": "polite"}),
                dcc.Store(id=f"{cid}-banner-edge", data=None),
            ],
            id=cid,
            style=dict(_HIDDEN),
            className="mb-2",
            role="region",
            **{"aria-label": "Effective recurrence request for the next Start"},
        )

    # ------------------------------------------------------------------ callbacks

    def register_callbacks(self, app):
        cid = self.component_id
        app.clientside_callback(
            BANNER_EDGE_JS,
            Output(f"{cid}-banner-edge", "data"),
            Input("pending-dataset-banner", "is_open"),
            State(f"{cid}-banner-edge", "data"),
            prevent_initial_call=True,
        )

        @app.callback(
            Output(cid, "style"),
            Output(f"{cid}-body", "children"),
            Output(f"{cid}-notes", "children"),
            Input("oneshot-start-params-store", "data"),
            Input("dataset-stage-outcome-alert", "children"),
            Input(f"{cid}-banner-edge", "data"),
            Input(f"{cid}-refresh", "n_clicks"),
            State("model-class-store", "data"),
            prevent_initial_call=True,
        )
        def refresh_recurrence_request_preview(start_body, _stage_outcome, _banner_edge, _refresh_clicks, model_class):
            return self._refresh_handler(model_class=model_class, start_body=start_body)

    def _refresh_handler(self, *, model_class: Optional[str], start_body: Optional[Dict[str, Any]]) -> Tuple[Dict[str, str], str, Any]:
        """Return ``(panel_style, body_text, notes)`` for the current selection.

        Hidden, with no request made, unless the model is one-shot. Otherwise the panel asks the
        backend what the next Start would send, passing the same one-shot body Start would post, and
        renders the reply. A failure is shown in place of the body rather than raised: this panel
        explains a Start, it must never be the reason one cannot happen.
        """
        if model_class != _ONE_SHOT:
            return dict(_HIDDEN), "", ""
        try:
            resp = requests.post(f"{self._api_base_url}{EFFECTIVE_REQUEST_PATH}", json=start_body or {}, timeout=self.api_timeout, headers=internal_api_headers())
        except requests.RequestException as exc:
            return dict(_SHOWN), "", f"Could not compute the effective request: canopy did not answer ({type(exc).__name__})."
        try:
            payload = resp.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            return dict(_SHOWN), "", f"Could not compute the effective request: HTTP {resp.status_code} without a JSON body."
        if resp.status_code != 200 or not payload.get("ok"):
            return dict(_SHOWN), "", f"No request to preview: {payload.get('error') or f'HTTP {resp.status_code}'}"
        return dict(_SHOWN), json.dumps(payload.get("request"), indent=2), self._notes(payload)

    @staticmethod
    def _notes(payload: Dict[str, Any]) -> List[Any]:
        """Explain where the body came from and what the R7 shaping did, one short line each."""
        source = "the staged dataset (Apply)" if payload.get("source") == "staged" else "the Start body (dataset dropdown and registry defaults)"
        lines = [f"From {source}."]
        edited = payload.get("edited") or []
        if edited:
            lines.append(f"Edited in the form, so sent over the registry defaults: {', '.join(edited)}.")
        withheld = payload.get("not_forwarded") or []
        if withheld:
            lines.append(f"Staged but not sent (not a parameter of this generator, or held to the registry default): {', '.join(withheld)}.")
        if payload.get("fit_in_progress"):
            lines.append("A fit is in progress: Start is refused until it ends.")
        return [html.Div(line) for line in lines]
