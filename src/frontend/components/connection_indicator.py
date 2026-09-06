#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# Application:   juniper_canopy
# Purpose:       WebSocket connection status indicator badge (Phase B)
#
# Author:        Paul Calnon
# Version:       0.1.0
# File Name:     connection_indicator.py
#
# Created Date:  2026-04-12
# Last Modified: 2026-04-12
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    4-state badge component showing WebSocket connection status:
#    connected (green), reconnecting (yellow), offline (red), demo (gray).
#    Updates via ws-connection-status Dash store.
#
#####################################################################################################################################################################################################

from dash import html


def connection_indicator_layout():
    """Return the connection indicator badge element.

    The badge text and color are updated by a clientside callback
    registered in dashboard_manager.py that reads ws-connection-status.
    """
    return html.Span(
        id="ws-connection-indicator",
        children="WS: --",
        style={
            "display": "inline-block",
            "padding": "2px 8px",
            "borderRadius": "4px",
            "fontSize": "11px",
            "fontWeight": "bold",
            "backgroundColor": "#6c757d",
            "color": "#fff",
            "marginLeft": "8px",
            "verticalAlign": "middle",
        },
    )


# Clientside callback JS for updating the indicator from the
# ws-connection-status store plus the stream-health-store (N2).
# Returns [children, style] for the badge.
#
# N2 degraded-mode dimension (training-runtime defects plan §4 I-1 / §5 T2):
# the browser socket being open is NOT end-to-end health — in the 2026-07-10
# incident the badge showed a green "WS: Connected" for 12+ hours while the
# canopy→cascor relay behind it was dead. The badge now also consumes
# `stream-health-store` (fed by GET /api/stream_health from the relay /
# control-supervisor liveness state) and downgrades an otherwise-green badge:
#   - upstream "reconnecting" (relay disconnected)      → amber "WS: Upstream reconnecting"
#   - upstream "degraded" (connected but frame-starved) → amber "WS: Upstream degraded"
# Absent/"n/a" stream health (demo mode, store not yet populated) preserves
# the original 4-state behavior.
CONNECTION_INDICATOR_JS = """
function(wsStatus, streamHealth) {
    if (!wsStatus) return [window.dash_clientside.no_update, window.dash_clientside.no_update];

    var baseStyle = {
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: "bold",
        color: "#fff",
        marginLeft: "8px",
        verticalAlign: "middle"
    };

    // PR 2 (demo-mode honesty): the mode comes from the SERVER, via
    // GET /api/stream_health, because the browser cannot know it. This branch was
    // previously keyed on `wsStatus.mode`, which websocket_client.js and
    // ws_dash_bridge.js both hardcode to "live" — so "WS: Demo" was unreachable dead
    // code, and canopy rendered a green "WS: Connected" over simulated data whenever a
    // cold start could not reach cascor. `wsStatus.mode` is still honoured first so a
    // future client that learns its own mode is not overridden by a stale store.
    var mode = (wsStatus && wsStatus.mode !== "live" && wsStatus.mode) || (streamHealth && streamHealth.mode);
    if (mode === "demo") {
        baseStyle.backgroundColor = "#6c757d";
        // §4.12 / G9: demo mode is SUPPOSED to run on juniper-data — that is the dogfooding the
        // platform depends on. When it falls back to its own local generator it is no longer
        // demonstrating the platform at all, and until now said so only in the log. Red rather
        // than grey, because this is a different claim from "these numbers are simulated": the
        // data itself never came from the platform.
        if (streamHealth && streamHealth.dataset_source === "local") {
            baseStyle.backgroundColor = "#dc3545";
            baseStyle.color = "#fff";
            return ["WS: Demo — LOCAL data, not juniper-data", baseStyle];
        }
        return ["WS: Demo", baseStyle];
    }
    if (wsStatus.connected) {
        var upstream = streamHealth && streamHealth.overall;
        if (upstream === "reconnecting" || upstream === "degraded") {
            baseStyle.backgroundColor = "#ffc107";
            baseStyle.color = "#212529";
            return [upstream === "reconnecting" ? "WS: Upstream reconnecting" : "WS: Upstream degraded", baseStyle];
        }
        baseStyle.backgroundColor = "#28a745";
        return ["WS: Connected", baseStyle];
    }
    if (wsStatus.reconnecting) {
        baseStyle.backgroundColor = "#ffc107";
        baseStyle.color = "#212529";
        return ["WS: Reconnecting", baseStyle];
    }
    baseStyle.backgroundColor = "#dc3545";
    return ["WS: Offline", baseStyle];
}
"""
