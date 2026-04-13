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


# Clientside callback JS for updating the indicator from ws-connection-status store.
# Returns [children, style] for the badge.
CONNECTION_INDICATOR_JS = """
function(wsStatus) {
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

    if (wsStatus.mode === "demo") {
        baseStyle.backgroundColor = "#6c757d";
        return ["WS: Demo", baseStyle];
    }
    if (wsStatus.connected) {
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
