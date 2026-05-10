#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     replay_player_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-05-02
# Last Modified: 2026-05-02
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    Replay player UI component (Phase 6E Sprint B B-6, CAN-015f).
#    Drives the cascor /v1/snapshots/{id}/replay/control endpoint via
#    the canopy /api/v1/snapshots/{id}/replay/control proxy.
#
#####################################################################
"""Replay player panel — V1 controls for snapshot replay sessions.

V1 surface (per Phase 6E Sprint B design §7):
- Play / Pause / Stop buttons
- Bidirectional speed slider (-10x .. 10x, with 0 == pause)
- Epoch scrubber: shows current_epoch / total_epochs
- Time-range selector to restrict playback to a sub-window

Wiring:
- Listens for ``replay-player-session`` Store updates (populated by
  the snapshots panel after a successful POST /replay).
- Each control writes to ``/api/v1/snapshots/{id}/replay/control``
  via ``_invoke_replay_control``.
- WebSocket events from the cascor backend update the Store via the
  websocket bridge (consumed in dashboard_manager).
"""

from typing import Any, Dict, Optional

import dash
import dash_bootstrap_components as dbc
import requests
from dash import Input, Output, State, dcc, html

from frontend.internal_api import internal_api_headers

from ..base_component import BaseComponent

# Speed slider config — bidirectional 0.1x .. 10x with 0 == pause.
# Negative values are encoded as backward playback in the cascor FSM.
SPEED_MIN = -10.0
SPEED_MAX = 10.0
SPEED_STEP = 0.1
SPEED_DEFAULT = 1.0

# CAN-015g (g-4): max number of replay-weight events held in the
# ``replay-weight-buffer`` Store at any time. LRU-evicted on overflow
# (oldest entry dropped). 100 entries × ~MB-scale tensors per entry =
# a few hundred MB peak — comfortable for a browser tab on most user
# machines. Tuned downward from the plan's "1000 entries" target
# because that figure didn't account for tensor size; revisit when /
# if a binary-WS-frame variant ships and per-event payload shrinks.
REPLAY_WEIGHT_BUFFER_MAX = 100
SPEED_MARKS = {
    -10: "-10×",
    -5: "-5×",
    -1: "-1×",
    0: "0",
    1: "1×",
    5: "5×",
    10: "10×",
}


class ReplayPlayerPanel(BaseComponent):
    """V1 replay player UI for snapshot playback sessions."""

    def __init__(self, config: Dict[str, Any], component_id: str = "replay-player-panel"):
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
                html.H4("Replay Player", style={"marginBottom": "15px"}),
                html.P(
                    "Read-only playback of a snapshot's training history. " "Start a replay session from the Snapshots tab to populate this panel.",
                    style={"fontSize": "0.85rem", "color": "var(--text-muted)"},
                ),
                # Two view modes; visibility flipped by the session-store callback.
                html.Div(idle_state, id=f"{self.component_id}-idle", style={"display": "block"}),
                html.Div(active_state, id=f"{self.component_id}-active", style={"display": "none"}),
                # Status / error line.
                html.Div(id=f"{self.component_id}-status", style={"marginTop": "10px"}),
                # Session state Store. Populated by the snapshots panel after POST
                # /replay, cleared on stop. Schema:
                #   {snapshot_id, fsm_state, time_index, range: [start, end] | None,
                #    speed, playing}
                dcc.Store(id="replay-player-session", data=None),
                # Trigger the player to issue a control request. The
                # callbacks below write here when buttons / sliders fire;
                # ``_dispatch_control`` watches it and calls the backend.
                dcc.Store(id=f"{self.component_id}-control-trigger", data=None),
                # CAN-015g (g-4): replay V2 weight payload buffer.
                # Drained from ``window._juniperWsDrain._replayWeightBuffer``
                # by the clientside callback below; capped at
                # ``REPLAY_WEIGHT_BUFFER_MAX`` entries so the Store
                # stays under a few-hundred-MB ceiling on long
                # sessions. Each entry is the V2 wire envelope:
                #   {sample_index, epoch, output_weights,
                #    output_bias, hidden_units}
                # where each tensor field is ``{dtype, shape, data}``
                # (base64 float32). Consumers (decision_boundary,
                # network_evolution, this panel's last-sample
                # readout) decode on demand.
                dcc.Store(id="replay-weight-buffer", data=[]),
                # Periodic drain trigger. Fires on the existing
                # fast-update interval (sourced from dashboard_manager)
                # so the player stays in sync with the replay session
                # without spawning a dedicated interval.
                dcc.Interval(id=f"{self.component_id}-weight-drain", interval=500, n_intervals=0),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "900px"},
        )

    def _build_idle_state(self):
        return html.Div(
            [
                html.Div(
                    "▶ No active replay session",
                    style={
                        "padding": "30px",
                        "textAlign": "center",
                        "color": "var(--text-muted)",
                        "border": "1px dashed var(--border-color, #dee2e6)",
                        "borderRadius": "6px",
                        "fontSize": "1rem",
                    },
                ),
            ]
        )

    def _build_active_state(self):
        return html.Div(
            [
                # Header row: snapshot id + FSM state badge + V2-weights badge
                html.Div(
                    [
                        html.Span("Snapshot: ", style={"fontWeight": "500"}),
                        html.Code(id=f"{self.component_id}-snapshot-id"),
                        html.Span(
                            id=f"{self.component_id}-fsm-badge",
                            style={
                                "marginLeft": "12px",
                                "padding": "2px 8px",
                                "borderRadius": "10px",
                                "fontSize": "0.75rem",
                                "backgroundColor": "var(--bs-info-bg-subtle, #cff4fc)",
                                "color": "var(--bs-info-text-emphasis, #055160)",
                            },
                        ),
                        # CAN-015g (g-4): V2 weights-available badge.
                        # Driven by the session Store's ``weights_available``
                        # field (g-2 added it). When true, also surface
                        # the latest received sample's epoch so the user
                        # knows playback has reached a sample-boundary.
                        html.Span(
                            id=f"{self.component_id}-weights-badge",
                            style={
                                "marginLeft": "8px",
                                "padding": "2px 8px",
                                "borderRadius": "10px",
                                "fontSize": "0.75rem",
                                "display": "none",  # hidden until session loads with V2
                            },
                        ),
                        html.Span(
                            id=f"{self.component_id}-last-sample-readout",
                            style={
                                "marginLeft": "8px",
                                "fontSize": "0.75rem",
                                "fontFamily": "monospace",
                                "color": "var(--text-muted)",
                            },
                        ),
                    ],
                    style={"marginBottom": "15px"},
                ),
                # Transport controls
                dbc.ButtonGroup(
                    [
                        dbc.Button(
                            "▶ Play",
                            id=f"{self.component_id}-play-btn",
                            color="success",
                            outline=True,
                            n_clicks=0,
                        ),
                        dbc.Button(
                            "⏸ Pause",
                            id=f"{self.component_id}-pause-btn",
                            color="warning",
                            outline=True,
                            n_clicks=0,
                        ),
                        dbc.Button(
                            "⏹ Stop",
                            id=f"{self.component_id}-stop-btn",
                            color="danger",
                            outline=True,
                            n_clicks=0,
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # Epoch scrubber
                html.Div(
                    [
                        html.Label("Epoch", style={"fontWeight": "500"}),
                        html.Span(
                            id=f"{self.component_id}-epoch-readout",
                            style={
                                "marginLeft": "10px",
                                "fontFamily": "monospace",
                                "fontSize": "0.95rem",
                            },
                        ),
                        dcc.Slider(
                            id=f"{self.component_id}-scrubber",
                            min=0,
                            max=1,
                            step=1,
                            value=0,
                            marks=None,
                            tooltip={"placement": "top", "always_visible": False},
                            updatemode="mouseup",
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # Speed slider (bidirectional)
                html.Div(
                    [
                        html.Label("Speed", style={"fontWeight": "500"}),
                        html.Span(
                            id=f"{self.component_id}-speed-readout",
                            style={"marginLeft": "10px", "fontFamily": "monospace"},
                        ),
                        dcc.Slider(
                            id=f"{self.component_id}-speed",
                            min=SPEED_MIN,
                            max=SPEED_MAX,
                            step=SPEED_STEP,
                            value=SPEED_DEFAULT,
                            marks=SPEED_MARKS,
                            tooltip={"placement": "top", "always_visible": False},
                            updatemode="mouseup",
                        ),
                        html.Small(
                            "Negative speeds play backward. 0 pauses. Range 0.1×–10×.",
                            style={"color": "var(--text-muted)"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # Range selector — restrict playback to a sub-window
                html.Div(
                    [
                        html.Label("Playback range", style={"fontWeight": "500"}),
                        html.Span(
                            id=f"{self.component_id}-range-readout",
                            style={"marginLeft": "10px", "fontFamily": "monospace"},
                        ),
                        dcc.RangeSlider(
                            id=f"{self.component_id}-range",
                            min=0,
                            max=1,
                            step=1,
                            value=[0, 1],
                            marks=None,
                            tooltip={"placement": "top", "always_visible": False},
                            updatemode="mouseup",
                        ),
                        html.Small(
                            "Restrict playback to a sub-window of the snapshot's history.",
                            style={"color": "var(--text-muted)"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Backend invocation
    # ------------------------------------------------------------------

    def _invoke_replay_control(
        self,
        snapshot_id: str,
        action: str,
        **params: Any,
    ) -> Dict[str, Any]:
        """POST /api/v1/snapshots/{id}/replay/control.

        Returns ``{"success": bool, "data"|"error": ...}`` mirroring
        the snapshot panel's handler conventions.
        """
        if not snapshot_id:
            return {"success": False, "error": "No active replay session"}
        if action not in ("play", "pause", "seek", "speed", "range", "stop"):
            return {"success": False, "error": f"Unknown action: {action!r}"}

        body: Dict[str, Any] = {"action": action}
        body.update({k: v for k, v in params.items() if v is not None})
        try:
            resp = requests.post(
                f"{self._api_base_url}/api/v1/snapshots/{snapshot_id}/replay/control",
                json=body,
                timeout=self.api_timeout + 5,
                headers=internal_api_headers(),
            )
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            if resp.status_code == 501:
                detail = resp.json().get("detail", "Replay requires a live cascor backend")
                return {"success": False, "error": detail}
            if resp.status_code == 409:
                detail = resp.json().get("detail", "Conflict")
                return {"success": False, "error": detail}
            detail = resp.json().get("detail", f"HTTP {resp.status_code}") if resp.text else f"HTTP {resp.status_code}"
            return {"success": False, "error": detail}
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Service unavailable"}
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _session_window(session: Optional[Dict[str, Any]]) -> tuple[int, int]:
        """Extract (start_epoch, end_epoch) from the session payload.

        Tolerates the unified response shape (``time_index.snapshot_window``)
        and the legacy/test shape (``length`` / ``window``).
        """
        if not session:
            return 0, 1
        ti = session.get("time_index") or {}
        window = ti.get("snapshot_window") or session.get("window") or {}
        start = int(window.get("start_epoch", 0))
        end = int(window.get("end_epoch", session.get("length", 1) - 1))
        if end < start:
            end = start
        return start, end

    @staticmethod
    def _session_current_index(session: Optional[Dict[str, Any]]) -> int:
        if not session:
            return 0
        ti = session.get("time_index") or {}
        cur = ti.get("current") if isinstance(ti, dict) else None
        if cur is None:
            cur = session.get("current_epoch", 0)
        try:
            return int(cur)
        except (TypeError, ValueError):
            return 0

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def register_callbacks(self, app):
        component_id = self.component_id

        @app.callback(
            Output(f"{component_id}-idle", "style"),
            Output(f"{component_id}-active", "style"),
            Output(f"{component_id}-snapshot-id", "children"),
            Output(f"{component_id}-fsm-badge", "children"),
            Output(f"{component_id}-scrubber", "min"),
            Output(f"{component_id}-scrubber", "max"),
            Output(f"{component_id}-scrubber", "value"),
            Output(f"{component_id}-range", "min"),
            Output(f"{component_id}-range", "max"),
            Output(f"{component_id}-range", "value"),
            Output(f"{component_id}-epoch-readout", "children"),
            Output(f"{component_id}-range-readout", "children"),
            Output(f"{component_id}-speed", "value"),
            Output(f"{component_id}-speed-readout", "children"),
            Output(f"{component_id}-weights-badge", "children"),
            Output(f"{component_id}-weights-badge", "style"),
            Input("replay-player-session", "data"),
        )
        def render_session(session):
            """Mirror the session Store into the player UI controls.

            CAN-015g (g-4): also surfaces a ``Weights ✓`` / ``V1 only``
            badge when the loaded snapshot's ``weights_available``
            field is set (added by g-2 to ``state_summary``).
            """
            if not session or not session.get("snapshot_id"):
                # Idle — show empty placeholder, hide active controls.
                return (
                    {"display": "block"},
                    {"display": "none"},
                    "",
                    "",
                    0,
                    1,
                    0,
                    0,
                    1,
                    [0, 1],
                    "",
                    "",
                    SPEED_DEFAULT,
                    f"{SPEED_DEFAULT}×",
                    "",
                    {"display": "none"},
                )

            start, end = self._session_window(session)
            cur = self._session_current_index(session)
            range_value = session.get("range") or [start, end]
            speed = float(session.get("speed", SPEED_DEFAULT))
            fsm = session.get("fsm_state") or "Replaying"
            weights_available = bool(session.get("weights_available"))
            badge_text = "V2 ✓ weights" if weights_available else "V1 (metrics only)"
            badge_style = {
                "marginLeft": "8px",
                "padding": "2px 8px",
                "borderRadius": "10px",
                "fontSize": "0.75rem",
                "display": "inline-block",
                "backgroundColor": "var(--bs-success-bg-subtle, #d1e7dd)" if weights_available else "var(--bs-secondary-bg-subtle, #e2e3e5)",
                "color": "var(--bs-success-text-emphasis, #0f5132)" if weights_available else "var(--bs-secondary-text-emphasis, #41464b)",
            }
            return (
                {"display": "none"},
                {"display": "block"},
                session["snapshot_id"],
                fsm,
                start,
                end,
                cur,
                start,
                end,
                range_value,
                f"{cur} / {end}",
                f"[{range_value[0]}, {range_value[1]}]",
                speed,
                f"{speed:g}×" if speed != 0 else "Paused (0×)",
                badge_text,
                badge_style,
            )

        # CAN-015g (g-4): periodic drain of the JS-side replay weight
        # ring buffer into the Dash Store. Clientside so the browser
        # doesn't pay a server round-trip per drain — at default
        # 500ms cadence with 100-entry buffer, the steady-state cost
        # is dominated by JSON serialization of one or two recent
        # weight events.
        app.clientside_callback(
            f"""
            function(n_intervals, current_buffer) {{
                if (!window._juniperWsDrain || typeof window._juniperWsDrain.drainReplayWeights !== "function") {{
                    return window.dash_clientside.no_update;
                }}
                var fresh = window._juniperWsDrain.drainReplayWeights();
                if (!fresh || fresh.length === 0) {{
                    return window.dash_clientside.no_update;
                }}
                var buf = (current_buffer || []).concat(fresh);
                // LRU cap: drop oldest when the ring exceeds the budget.
                if (buf.length > {REPLAY_WEIGHT_BUFFER_MAX}) {{
                    buf = buf.slice(buf.length - {REPLAY_WEIGHT_BUFFER_MAX});
                }}
                return buf;
            }}
            """,
            Output("replay-weight-buffer", "data"),
            Input(f"{component_id}-weight-drain", "n_intervals"),
            State("replay-weight-buffer", "data"),
        )

        # CAN-015g (g-4): last-sample readout reflects the most recent
        # weight payload received. Pure clientside — reads the buffer
        # tail and writes a short string, no Python round-trip.
        app.clientside_callback(
            """
            function(buffer) {
                if (!buffer || buffer.length === 0) {
                    return "";
                }
                var last = buffer[buffer.length - 1];
                if (!last || typeof last.epoch !== "number") {
                    return "";
                }
                return "last sample: epoch " + last.epoch + " (" + buffer.length + " buffered)";
            }
            """,
            Output(f"{component_id}-last-sample-readout", "children"),
            Input("replay-weight-buffer", "data"),
        )

        @app.callback(
            Output(f"{component_id}-control-trigger", "data"),
            Input(f"{component_id}-play-btn", "n_clicks"),
            Input(f"{component_id}-pause-btn", "n_clicks"),
            Input(f"{component_id}-stop-btn", "n_clicks"),
            Input(f"{component_id}-scrubber", "value"),
            Input(f"{component_id}-speed", "value"),
            Input(f"{component_id}-range", "value"),
            State("replay-player-session", "data"),
            prevent_initial_call=True,
        )
        def queue_control(play, pause, stop, scrub, speed, prange, session):
            """Translate UI control changes into a replay/control request.

            Writes ``{action, params}`` to ``-control-trigger`` Store; a
            sibling callback issues the HTTP POST.
            """
            ctx = dash.callback_context
            if not ctx.triggered or not session or not session.get("snapshot_id"):
                return dash.no_update
            triggered = ctx.triggered[0]
            prop_id = triggered.get("prop_id", "")
            value = triggered.get("value")

            if prop_id.endswith("-play-btn.n_clicks"):
                if not play:
                    return dash.no_update
                return {"action": "play", "ts": play}
            if prop_id.endswith("-pause-btn.n_clicks"):
                if not pause:
                    return dash.no_update
                return {"action": "pause", "ts": pause}
            if prop_id.endswith("-stop-btn.n_clicks"):
                if not stop:
                    return dash.no_update
                return {"action": "stop", "ts": stop}
            if prop_id.endswith("-scrubber.value"):
                if value is None:
                    return dash.no_update
                return {"action": "seek", "params": {"time_index": int(value)}}
            if prop_id.endswith("-speed.value"):
                if value is None:
                    return dash.no_update
                return {"action": "speed", "params": {"value": float(value)}}
            if prop_id.endswith("-range.value"):
                if not value or len(value) != 2:
                    return dash.no_update
                return {"action": "range", "params": {"start": int(value[0]), "end": int(value[1])}}
            return dash.no_update

        @app.callback(
            Output(f"{component_id}-status", "children"),
            Output("replay-player-session", "data", allow_duplicate=True),
            Input(f"{component_id}-control-trigger", "data"),
            State("replay-player-session", "data"),
            prevent_initial_call=True,
        )
        def dispatch_control(trigger, session):
            """POST to /replay/control and reflect the result in the Store."""
            if not trigger or not isinstance(trigger, dict):
                return dash.no_update, dash.no_update
            if not session or not session.get("snapshot_id"):
                return self._error_status("No active replay session"), dash.no_update

            action = trigger.get("action")
            params = trigger.get("params") or {}
            result = self._invoke_replay_control(session["snapshot_id"], action, **params)

            if not result["success"]:
                return self._error_status(result["error"]), dash.no_update

            new_session = self._merge_session(session, action, params, result.get("data"))
            return self._success_status(action), new_session

        # Expose for unit tests.
        self._cb_render_session = render_session
        self._cb_queue_control = queue_control
        self._cb_dispatch_control = dispatch_control
        self.logger.debug("Callbacks registered for %s", component_id)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _error_status(message: str):
        return html.Div(
            [html.Span("❌ ", style={"color": "var(--danger-color, #dc3545)"}), html.Span(message)],
            style={
                "color": "var(--danger-color, #dc3545)",
                "padding": "8px 12px",
                "backgroundColor": "var(--bs-danger-bg-subtle, #f8d7da)",
                "borderRadius": "4px",
                "fontSize": "0.85rem",
            },
        )

    @staticmethod
    def _success_status(action: str):
        verbs = {
            "play": "Playing",
            "pause": "Paused",
            "stop": "Stopped",
            "seek": "Seeked",
            "speed": "Speed updated",
            "range": "Range updated",
        }
        return html.Div(
            [html.Span("✓ ", style={"color": "#198754"}), html.Span(verbs.get(action, action))],
            style={"color": "#198754", "fontSize": "0.85rem", "padding": "4px 0"},
        )

    @staticmethod
    def _merge_session(
        session: Dict[str, Any],
        action: str,
        params: Dict[str, Any],
        data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Apply the control action to the session Store.

        Backend response is preferred when present; otherwise we apply
        the user's intended change locally so the UI stays responsive.
        """
        new = dict(session)
        if data:
            # Trust the backend's authoritative state — it includes the
            # post-action FSM state, time_index, and any auto-advanced
            # epoch from a play action.
            new.update(data)
            return new

        if action == "play":
            new["playing"] = True
        elif action == "pause":
            new["playing"] = False
        elif action == "stop":
            # Stop terminates the session; clearing the snapshot_id
            # flips the panel back to idle on the next render.
            return {"snapshot_id": None}
        elif action == "seek":
            ti = dict(new.get("time_index") or {})
            ti["current"] = int(params.get("time_index", 0))
            new["time_index"] = ti
        elif action == "speed":
            new["speed"] = float(params.get("value", SPEED_DEFAULT))
            new["playing"] = abs(new["speed"]) > 1e-9
        elif action == "range":
            new["range"] = [int(params.get("start", 0)), int(params.get("end", 0))]
        return new
