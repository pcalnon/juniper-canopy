"""Network Evolution — small-multiples view of cascade-grow timeline.

Renders a grid of mini-schematics, one per recorded cascade-grow event,
so the user can see the architectural progression of training at a glance.

Distinct from the live Network Topology tab (which shows the current
network) and from CAN-021's deferred "population view" (parallel
networks). This is a *temporal* timeline of one network's growth.

Data source: ``evolution-snapshots-store``, populated client-side from
``ws-cascade-add-buffer`` events. Each snapshot is a tiny dict —
``{timestamp, epoch, input_units, hidden_units, output_units}`` — we
deliberately don't store the full ``connections`` list because:
- Per-snapshot footprint stays under a few hundred bytes
- Mini-schematics communicate "how many cascade layers exist" better
  than dense arrow webs at thumbnail size
- Full topology details remain one click away on the Network Topology tab

Bound: 20 snapshots, oldest-evicted. Cleared by the explicit Clear
button or by a training-reset signal.
"""

from typing import Any, Dict, List, Optional

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html

from ..base_component import BaseComponent

MAX_SNAPSHOTS = 20  # ring-buffer cap surfaced to the clientside callback


class NetworkEvolution(BaseComponent):
    """Timeline of cascade-grow snapshots, displayed as a small-multiples grid.

    Each card in the grid is a simplified Plotly schematic of the network
    at the moment that snapshot was captured. Snapshots are recorded
    client-side on every ``cascade_add`` WebSocket event and live in the
    ``evolution-snapshots-store`` Dash Store.

    Component IDs (all prefixed with ``self.component_id``):
    - ``-grid-container``: outer div hosting the grid
    - ``-empty-state``: placeholder when no snapshots exist
    - ``-stats``: header strip ("Snapshots: K of N max")
    - ``-clear-btn``: explicit clear button
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "network-evolution"):
        super().__init__(config, component_id)
        self.logger.info("NetworkEvolution initialized")

    def get_layout(self) -> html.Div:
        return html.Div(
            [
                html.Div(
                    [
                        html.H3("Network Evolution", style={"display": "inline-block", "marginRight": "20px"}),
                        html.Span(
                            "Cascade growth timeline — one snapshot per grow event.",
                            style={"color": "#6c757d", "fontSize": "0.9em", "marginRight": "20px"},
                        ),
                        dbc.Button(
                            "Clear snapshots",
                            id=f"{self.component_id}-clear-btn",
                            color="secondary",
                            outline=True,
                            size="sm",
                            style={"verticalAlign": "middle"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                html.Div(
                    id=f"{self.component_id}-stats",
                    children="No snapshots yet",
                    style={"color": "#6c757d", "fontSize": "0.85em", "marginBottom": "15px"},
                ),
                html.Div(
                    id=f"{self.component_id}-grid-container",
                    children=self._empty_state(),
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fill, minmax(220px, 1fr))",
                        "gap": "12px",
                        "padding": "8px",
                    },
                ),
            ],
            id=self.component_id,
            style={"padding": "20px"},
        )

    def _empty_state(self) -> html.Div:
        return html.Div(
            [
                html.Div(
                    "🌱",
                    style={"fontSize": "2em", "textAlign": "center", "marginBottom": "8px"},
                ),
                html.Div(
                    "No snapshots yet — start training to record cascade growth.",
                    style={"textAlign": "center", "color": "#6c757d"},
                ),
            ],
            id=f"{self.component_id}-empty-state",
            style={"gridColumn": "1 / -1", "padding": "40px"},
        )

    def register_callbacks(self, app):
        """Wire grid rendering. The capture-and-clear callbacks live in
        ``dashboard_manager.py`` because they cross-reference stores
        (``ws-cascade-add-buffer``, ``network-visualizer-topology-store``)
        owned by other components."""

        @app.callback(
            [
                Output(f"{self.component_id}-grid-container", "children"),
                Output(f"{self.component_id}-stats", "children"),
            ],
            Input("evolution-snapshots-store", "data"),
            State("theme-state", "data"),
            prevent_initial_call=False,
        )
        def render_grid(snapshots: Optional[List[Dict[str, Any]]], theme: Optional[str]):
            return self._render_grid(snapshots or [], theme or "light")

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _render_grid(self, snapshots: List[Dict[str, Any]], theme: str):
        if not snapshots:
            return self._empty_state(), "No snapshots yet"

        # Snapshots arrive newest-first from the capture callback (so the
        # most recent grow shows at top-left). Compute deltas vs. the
        # immediately-prior snapshot in *time order* — i.e. iterating
        # reverse-chronological we look at the next index for the prior.
        cards = []
        for i, snap in enumerate(snapshots):
            prior = snapshots[i + 1] if i + 1 < len(snapshots) else None
            cards.append(self._render_snapshot_card(snap, prior, i, theme))

        stats = f"Snapshots: {len(snapshots)} of {MAX_SNAPSHOTS} max"
        return cards, stats

    def _render_snapshot_card(
        self,
        snap: Dict[str, Any],
        prior: Optional[Dict[str, Any]],
        index: int,
        theme: str,
    ) -> html.Div:
        is_dark = theme == "dark"
        bg = "#2d2d2d" if is_dark else "#ffffff"
        fg = "#f8f9fa" if is_dark else "#212529"
        border = "#404040" if is_dark else "#dee2e6"
        delta = self._compute_delta(snap, prior)
        epoch_label = self._format_epoch_label(snap)

        return html.Div(
            [
                html.Div(
                    [
                        html.Span(epoch_label, style={"fontSize": "0.85em", "color": fg}),
                        html.Span(
                            delta,
                            style={
                                "fontSize": "0.75em",
                                "color": "#1976d2" if delta and "+" in delta else "#6c757d",
                                "float": "right",
                            },
                        ),
                    ],
                    style={"marginBottom": "4px"},
                ),
                dcc.Graph(
                    figure=self._build_mini_diagram(snap, theme),
                    config={"displayModeBar": False, "staticPlot": True},
                    style={"height": "120px"},
                ),
                html.Div(
                    [
                        html.Span("Hidden: ", style={"color": "#6c757d", "fontSize": "0.8em"}),
                        html.Strong(str(snap.get("hidden_units", 0)), style={"color": fg, "fontSize": "0.85em"}),
                    ],
                    style={"textAlign": "center", "marginTop": "4px"},
                ),
            ],
            style={
                "background": bg,
                "border": f"1px solid {border}",
                "borderRadius": "6px",
                "padding": "10px",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.06)",
            },
            **{"data-snapshot-index": str(index)},  # for tests + future click-to-expand
        )

    @staticmethod
    def _compute_delta(snap: Dict[str, Any], prior: Optional[Dict[str, Any]]) -> str:
        """Return ``"+N"`` if hidden_units grew vs. prior, else empty string.

        Static so tests can call it directly without a NetworkEvolution
        instance.
        """
        if not prior:
            return ""
        try:
            current = int(snap.get("hidden_units", 0))
            previous = int(prior.get("hidden_units", 0))
        except (TypeError, ValueError):
            return ""
        diff = current - previous
        if diff > 0:
            return f"+{diff} units"
        if diff < 0:
            return f"{diff} units"
        return ""

    @staticmethod
    def _format_epoch_label(snap: Dict[str, Any]) -> str:
        """Render the snapshot's epoch (or fall back to a relative-time hint).

        Static so tests can drive it without an instance.
        """
        epoch = snap.get("epoch")
        if isinstance(epoch, (int, float)) and epoch >= 0:
            return f"Epoch {int(epoch)}"
        ts = snap.get("timestamp")
        if isinstance(ts, (int, float)) and ts > 0:
            return "Captured"
        return "—"

    @staticmethod
    def _build_mini_diagram(snap: Dict[str, Any], theme: str) -> go.Figure:
        """Build a small layered schematic: input dots, cascade column, output dots.

        Static so tests can build figures without a component instance.
        Designed to read clearly at ~220x120 px — no labels, no axes,
        just colored dots and connecting lines.
        """
        is_dark = theme == "dark"
        input_color = "#3498db"
        hidden_color = "#1976d2"
        output_color = "#2ecc71"
        line_color = "#bbbbbb" if not is_dark else "#555555"
        bg = "#2d2d2d" if is_dark else "#ffffff"

        n_input = max(1, int(snap.get("input_units", 0) or 0))
        n_hidden = int(snap.get("hidden_units", 0) or 0)
        n_output = max(1, int(snap.get("output_units", 0) or 0))

        # Cap dot counts to keep the schematic readable. The exact value
        # isn't load-bearing — the count is shown as text on the card.
        n_input_d = min(n_input, 8)
        n_output_d = min(n_output, 8)

        input_x = [0.05] * n_input_d
        input_y = [(i + 1) / (n_input_d + 1) for i in range(n_input_d)]
        output_x = [0.95] * n_output_d
        output_y = [(i + 1) / (n_output_d + 1) for i in range(n_output_d)]

        # Hidden units laid out as a vertical column at x=0.5; if there are
        # too many to fit we squash them but still visibly show the cascade.
        n_hidden_d = min(n_hidden, 12)
        hidden_x = [0.5 + 0.02 * (i % 2) for i in range(n_hidden_d)]  # tiny zigzag for readability
        hidden_y = [(i + 1) / (n_hidden_d + 1) if n_hidden_d > 0 else 0.5 for i in range(n_hidden_d)]

        traces: List[go.Scatter] = []

        # Light skip-layer connection lines (input → output).
        for ix, iy in zip(input_x, input_y, strict=True):
            for ox, oy in zip(output_x, output_y, strict=True):
                traces.append(
                    go.Scatter(
                        x=[ix, ox],
                        y=[iy, oy],
                        mode="lines",
                        line={"color": line_color, "width": 0.5},
                        hoverinfo="skip",
                        showlegend=False,
                    )
                )

        # Input → hidden, hidden → output (only when hidden units exist).
        if n_hidden_d > 0:
            for hx, hy in zip(hidden_x, hidden_y, strict=True):
                for ix, iy in zip(input_x, input_y, strict=True):
                    traces.append(
                        go.Scatter(
                            x=[ix, hx],
                            y=[iy, hy],
                            mode="lines",
                            line={"color": line_color, "width": 0.5},
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )
                for ox, oy in zip(output_x, output_y, strict=True):
                    traces.append(
                        go.Scatter(
                            x=[hx, ox],
                            y=[hy, oy],
                            mode="lines",
                            line={"color": line_color, "width": 0.5},
                            hoverinfo="skip",
                            showlegend=False,
                        )
                    )

        traces.append(
            go.Scatter(
                x=input_x,
                y=input_y,
                mode="markers",
                marker={"color": input_color, "size": 8},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        if n_hidden_d > 0:
            traces.append(
                go.Scatter(
                    x=hidden_x,
                    y=hidden_y,
                    mode="markers",
                    marker={"color": hidden_color, "size": 7},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
        traces.append(
            go.Scatter(
                x=output_x,
                y=output_y,
                mode="markers",
                marker={"color": output_color, "size": 8},
                hoverinfo="skip",
                showlegend=False,
            )
        )

        fig = go.Figure(data=traces)
        fig.update_layout(
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            paper_bgcolor=bg,
            plot_bgcolor=bg,
            xaxis={"visible": False, "range": [-0.05, 1.05], "fixedrange": True},
            yaxis={"visible": False, "range": [-0.05, 1.05], "fixedrange": True},
            showlegend=False,
            hovermode=False,
        )
        return fig
