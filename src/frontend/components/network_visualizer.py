#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     network_visualizer.py
# Author:        Paul Calnon
# Version:       1.4.0
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This file contains the code to Visualize the current Cascade Correlation Neural Network prototype
#       including training, state, and architecture with the Juniper prototype Frontend for monitoring and diagnostics.
#
#####################################################################################################################################################################################################
# Notes:
#
# Network Visualizer Component
#
# Interactive visualization of the Cascade Correlation network topology,
# showing input, hidden, and output units with weighted connections.
# Color-coded by layer and connection strength.
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
import hashlib
import json
from typing import Any, Dict, List, Tuple

import networkx as nx
import plotly.graph_objects as go
from dash import dcc, html
from dash.dependencies import Input, Output, State

from constants import DashboardConstants

from ..base_component import BaseComponent

# import numpy as np


class NetworkVisualizer(BaseComponent):
    """
    Network topology visualization component.

    Displays an interactive graph showing:
    - Input units
    - Hidden units (added dynamically during training)
    - Output units
    - Weighted connections between units
    - Color-coded by layer and connection strength
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "network-visualizer"):
        """
        Initialize network visualizer component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        # Configuration
        self.show_weights = config.get("show_weights", True)
        self.layout_type = config.get("layout", "hierarchical")  # hierarchical or spring

        # Current network state
        self.current_topology: Dict[str, Any] = {
            "input_units": 0,
            "hidden_units": 0,
            "output_units": 0,
            "connections": [],
        }

        self.logger.info(f"NetworkVisualizer initialized with layout={self.layout_type}")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for network visualizer.

        Returns:
            Dash Div containing the network visualization
        """
        return html.Div(
            [
                # Header with controls
                html.Div(
                    [
                        html.H3("Network Topology", style={"display": "inline-block"}),
                        html.Div(
                            [
                                html.Label("Layout:", style={"marginRight": "10px"}),
                                dcc.Dropdown(
                                    id=f"{self.component_id}-layout-selector",
                                    options=[
                                        {"label": "Hierarchical", "value": "hierarchical"},
                                        {"label": "Staggered", "value": "staggered"},
                                        {"label": "Spring", "value": "spring"},
                                        {"label": "Circular", "value": "circular"},
                                    ],
                                    value=self.layout_type,
                                    style={"width": "150px", "display": "inline-block"},
                                ),
                                html.Label("Show Weights:", style={"marginLeft": "20px", "marginRight": "10px"}),
                                dcc.Checklist(
                                    id=f"{self.component_id}-show-weights",
                                    options=[{"label": "", "value": "show"}],
                                    value=["show"] if self.show_weights else [],
                                    style={"display": "inline-block"},
                                ),
                            ],
                            style={"display": "inline-block", "float": "right"},
                        ),
                    ],
                    style={"marginBottom": "10px"},
                ),
                # Network statistics
                html.Div(
                    id=f"{self.component_id}-stats-bar",
                    children=[
                        html.Div(
                            [
                                html.Strong("Input Units: "),
                                html.Span(id=f"{self.component_id}-input-count", children="0"),
                            ],
                            style={"display": "inline-block", "marginRight": "20px"},
                        ),
                        html.Div(
                            [
                                html.Strong("Hidden Units: "),
                                html.Span(id=f"{self.component_id}-hidden-count", children="0"),
                            ],
                            style={"display": "inline-block", "marginRight": "20px"},
                        ),
                        html.Div(
                            [
                                html.Strong("Output Units: "),
                                html.Span(id=f"{self.component_id}-output-count", children="0"),
                            ],
                            style={"display": "inline-block", "marginRight": "20px"},
                        ),
                        html.Div(
                            [
                                html.Strong("Total Connections: "),
                                html.Span(id=f"{self.component_id}-connection-count", children="0"),
                            ],
                            style={"display": "inline-block"},
                        ),
                    ],
                    style={
                        "marginBottom": "15px",
                        "padding": "10px",
                        "backgroundColor": "#f8f9fa",
                        "borderRadius": "3px",
                    },
                ),
                # Selected node info panel
                html.Div(
                    id=f"{self.component_id}-selection-info",
                    children=[],
                    style={
                        "marginBottom": "10px",
                        "padding": "10px",
                        "backgroundColor": "#e3f2fd",
                        "borderRadius": "4px",
                        "display": "none",
                    },
                ),
                # Network graph
                dcc.Graph(
                    id=f"{self.component_id}-graph",
                    config={
                        "displayModeBar": True,
                        "displaylogo": False,
                        "modeBarButtonsToAdd": ["select2d", "lasso2d"],
                    },
                    style={"height": "600px"},
                ),
                # Topology data store
                dcc.Store(id=f"{self.component_id}-topology-store", data=self.current_topology),
                # View state store for preserving zoom, pan, and tool selection
                dcc.Store(
                    id=f"{self.component_id}-view-state",
                    data={
                        "xaxis_range": None,
                        "yaxis_range": None,
                        "dragmode": "pan",
                    },
                ),
                # Previous topology hash to detect changes
                dcc.Store(id=f"{self.component_id}-topology-hash", data=None),
                # Selected nodes store
                dcc.Store(id=f"{self.component_id}-selected-nodes", data=[]),
            ],
            style={"padding": "20px"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for network visualizer.

        Args:
            app: Dash application instance
        """

        @app.callback(
            Output(f"{self.component_id}-view-state", "data"),
            Input(f"{self.component_id}-graph", "relayoutData"),
            State(f"{self.component_id}-view-state", "data"),
            prevent_initial_call=True,
        )
        def capture_view_state(relayout_data, current_state):
            """Capture user's view state (zoom, pan, tool selection)."""
            if not relayout_data or not current_state:
                return current_state or {"xaxis_range": None, "yaxis_range": None, "dragmode": "pan"}

            new_state = current_state.copy()

            # Capture axis ranges (zoom/pan)
            if "xaxis.range[0]" in relayout_data:
                new_state["xaxis_range"] = [
                    relayout_data["xaxis.range[0]"],
                    relayout_data["xaxis.range[1]"],
                ]
            if "yaxis.range[0]" in relayout_data:
                new_state["yaxis_range"] = [
                    relayout_data["yaxis.range[0]"],
                    relayout_data["yaxis.range[1]"],
                ]

            # Capture tool selection
            if "dragmode" in relayout_data:
                new_state["dragmode"] = relayout_data["dragmode"]

            # Handle autorange/reset
            if relayout_data.get("xaxis.autorange"):
                new_state["xaxis_range"] = None
            if relayout_data.get("yaxis.autorange"):
                new_state["yaxis_range"] = None

            return new_state

        @app.callback(
            [
                Output(f"{self.component_id}-graph", "figure"),
                Output(f"{self.component_id}-input-count", "children"),
                Output(f"{self.component_id}-hidden-count", "children"),
                Output(f"{self.component_id}-output-count", "children"),
                Output(f"{self.component_id}-connection-count", "children"),
                Output(f"{self.component_id}-topology-hash", "data"),
            ],
            [
                Input(f"{self.component_id}-topology-store", "data"),
                Input(f"{self.component_id}-layout-selector", "value"),
                Input(f"{self.component_id}-show-weights", "value"),
                Input("metrics-panel-metrics-store", "data"),
                Input("theme-state", "data"),
                Input(f"{self.component_id}-selected-nodes", "data"),
            ],
            [
                State(f"{self.component_id}-view-state", "data"),
                State(f"{self.component_id}-topology-hash", "data"),
            ],
        )
        def update_network_graph(
            topology_data: Dict[str, Any],
            layout_type: str,
            show_weights: List[str],
            metrics_data: List[Dict[str, Any]],
            theme: str,
            selected_nodes: List[str],
            view_state: Dict[str, Any],
            prev_hash: str,
        ):
            """
            Update network visualization based on topology data.

            Args:
                topology_data: Network topology dictionary
                layout_type: Layout algorithm to use
                show_weights: List containing 'show' if weights should be displayed
                metrics_data: Historical metrics data for detecting new units
                theme: Current theme
                selected_nodes: List of selected node IDs
                view_state: Stored view state (zoom, pan, dragmode)
                prev_hash: Previous topology hash

            Returns:
                Tuple of updated components
            """

            def compute_hash(topo):
                key = {
                    "input": topo.get("input_units", 0),
                    "hidden": topo.get("hidden_units", 0),
                    "output": topo.get("output_units", 0),
                    "connections": len(topo.get("connections", [])),
                }
                return hashlib.md5(json.dumps(key, sort_keys=True).encode(), usedforsecurity=False).hexdigest()

            if not topology_data or topology_data.get("input_units", 0) == 0:
                empty_fig = self._create_empty_graph(theme)
                return empty_fig, "0", "0", "0", "0", None

            current_hash = compute_hash(topology_data)

            # Detect newly added hidden unit
            newly_added_unit = None
            if metrics_data and len(metrics_data) >= 2:
                prev_hidden = metrics_data[-2].get("network_topology", {}).get("hidden_units", 0)
                curr_hidden = metrics_data[-1].get("network_topology", {}).get("hidden_units", 0)
                if curr_hidden > prev_hidden:
                    newly_added_unit = curr_hidden - 1  # Index of new unit

            # Create network graph
            show_weight_labels = bool(show_weights) and ("show" in show_weights)
            fig = self._create_network_graph(
                topology_data, layout_type, show_weight_labels, newly_added_unit, theme, selected_nodes
            )

            # Apply stored view state
            if view_state:
                if view_state.get("xaxis_range"):
                    fig.update_layout(xaxis_range=view_state["xaxis_range"])
                if view_state.get("yaxis_range"):
                    fig.update_layout(yaxis_range=view_state["yaxis_range"])
                if view_state.get("dragmode"):
                    fig.update_layout(dragmode=view_state["dragmode"])

            # Extract counts
            input_count = str(topology_data.get("input_units", 0))
            hidden_count = str(topology_data.get("hidden_units", 0))
            output_count = str(topology_data.get("output_units", 0))
            connection_count = str(len(topology_data.get("connections", [])))

            return fig, input_count, hidden_count, output_count, connection_count, current_hash

        @app.callback(
            Output(f"{self.component_id}-stats-bar", "style"),
            Input("theme-state", "data"),
        )
        def update_stats_bar_theme(theme):
            """Update stats bar background for dark mode."""
            is_dark = theme == "dark"
            return {
                "marginBottom": "15px",
                "padding": "10px",
                "backgroundColor": "#343a40" if is_dark else "#f8f9fa",
                "color": "#f8f9fa" if is_dark else "#212529",
                "borderRadius": "3px",
            }

        @app.callback(
            [
                Output(f"{self.component_id}-selected-nodes", "data"),
                Output(f"{self.component_id}-selection-info", "children"),
                Output(f"{self.component_id}-selection-info", "style"),
            ],
            [
                Input(f"{self.component_id}-graph", "clickData"),
                Input(f"{self.component_id}-graph", "selectedData"),
            ],
            State(f"{self.component_id}-selected-nodes", "data"),
            prevent_initial_call=True,
        )
        def handle_node_selection(click_data, selected_data, current_selection):
            """Handle node selection via click or box/lasso select."""
            import dash

            ctx = dash.callback_context
            trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

            base_style = {
                "marginBottom": "10px",
                "padding": "10px",
                "backgroundColor": "#e3f2fd",
                "borderRadius": "4px",
                "border": "1px solid #90caf9",
            }
            hidden_style = {**base_style, "display": "none"}
            visible_style = {**base_style, "display": "block"}

            # Handle box/lasso selection
            if "selectedData" in trigger and selected_data:
                points = selected_data.get("points", [])
                if points:
                    selected_nodes = []
                    for point in points:
                        text = point.get("text", "")
                        if text:
                            node_id = text.lower().replace(" ", "_")
                            selected_nodes.append(node_id)

                    if selected_nodes:
                        info = html.Div(
                            [
                                html.Strong(f"Selected: {len(selected_nodes)} node(s)"),
                                html.Ul([html.Li(n.replace("_", " ").title()) for n in selected_nodes[:5]]),
                                html.Span(
                                    "(Click elsewhere to deselect)",
                                    style={"fontSize": "11px", "color": "#666"},
                                ),
                            ]
                        )
                        return selected_nodes, info, visible_style

            # Handle single click selection
            if "clickData" in trigger and click_data:
                points = click_data.get("points", [])
                if points:
                    point = points[0]
                    text = point.get("text", "")
                    if text:
                        node_id = text.lower().replace(" ", "_")

                        # Toggle selection: if already selected, deselect
                        if current_selection and node_id in current_selection:
                            return [], [], hidden_style

                        # Get node info
                        curve_number = point.get("curveNumber", 0)
                        layer_names = ["", "", "Input", "Hidden", "Output"]
                        layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"

                        info = html.Div(
                            [
                                html.Strong(f"Selected: {text}"),
                                html.Br(),
                                html.Span(f"Layer: {layer}", style={"color": "#666"}),
                                html.Br(),
                                html.Span(
                                    "(Click again or elsewhere to deselect)",
                                    style={"fontSize": "11px", "color": "#888"},
                                ),
                            ]
                        )
                        return [node_id], info, visible_style

            # No valid selection, clear
            return [], [], hidden_style

        self.logger.debug(f"Callbacks registered for {self.component_id}")

    def _create_network_graph(
        self,
        topology: Dict[str, Any],
        layout_type: str,
        show_weights: bool,
        newly_added_unit: int = None,
        theme: str = "light",
        selected_nodes: List[str] = None,
    ) -> go.Figure:
        """
        Create network graph visualization.

        Args:
            topology: Network topology dictionary
            layout_type: Layout algorithm ('hierarchical', 'spring', 'circular')
            show_weights: Whether to display weight values on edges
            newly_added_unit: Index of newly added hidden unit (for highlighting)
            theme: Current theme ("light" or "dark")
            selected_nodes: List of selected node IDs for highlighting

        Returns:
            Plotly figure object
        """
        # Create NetworkX graph
        G = nx.DiGraph()

        # Add nodes
        n_input = topology.get("input_units", 0)
        n_hidden = topology.get("hidden_units", 0)
        n_output = topology.get("output_units", 0)

        # Add input nodes
        for i in range(n_input):
            G.add_node(f"input_{i}", layer="input", index=i)

        # Add hidden nodes
        for i in range(n_hidden):
            G.add_node(f"hidden_{i}", layer="hidden", index=i)

        # Add output nodes
        for i in range(n_output):
            G.add_node(f"output_{i}", layer="output", index=i)

        # Add edges with weights
        connections = topology.get("connections", [])
        for conn in connections:
            from_node = conn.get("from")
            to_node = conn.get("to")
            weight = conn.get("weight", 0.0)

            if from_node and to_node:
                G.add_edge(from_node, to_node, weight=weight)

        # Calculate layout positions
        pos = self._calculate_layout(G, layout_type, n_input, n_hidden, n_output)

        # Create edge traces
        edge_traces = self._create_edge_traces(G, pos, show_weights)

        # Create node traces
        node_traces = self._create_node_traces(G, pos)

        # Combine traces
        fig = go.Figure(data=edge_traces + node_traces)

        # Highlight newly added hidden unit
        if newly_added_unit is not None and newly_added_unit < n_hidden:
            hidden_node = f"hidden_{newly_added_unit}"
            if hidden_node in pos:
                x, y = pos[hidden_node]
                # Add pulse effect for newly added hidden unit
                fig.add_trace(
                    go.Scatter(
                        x=[x],
                        y=[y],
                        mode="markers",
                        marker={
                            "size": 28,  # Larger than normal
                            "color": "#17a2b8",  # Cyan highlight
                            "line": {"width": 4, "color": "#fff"},
                            "opacity": 0.9,
                        },
                        name="New Unit",
                        showlegend=False,
                        hoverinfo="skip",
                    )
                )

        # Add selection highlights if any nodes are selected
        if selected_nodes:
            selection_traces = self._create_selection_highlight(pos, selected_nodes)
            for trace in selection_traces:
                fig.add_trace(trace)

        # Update layout
        is_dark = theme == "dark"
        fig.update_layout(
            title="Cascade Correlation Network Architecture",
            showlegend=True,
            hovermode="closest",
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            font={"color": "#e9ecef" if is_dark else "#212529"},
            legend={"x": 0.7, "y": 0.95},
            transition={"duration": 500, "easing": "cubic-in-out"},
            dragmode="pan",
        )

        return fig

    def _calculate_layout(
        self,
        G: nx.DiGraph,
        layout_type: str,
        n_input: int,
        n_hidden: int,
        n_output: int,
        scale: float = DashboardConstants.DEFAULT_SCALE,
    ) -> Dict[str, Tuple[float, float]]:
        """
        Calculate node positions based on layout algorithm.

        Args:
            G: NetworkX graph
            layout_type: Layout algorithm to use
            n_input: Number of input units
            n_hidden: Number of hidden units
            n_output: Number of output units

        Returns:
            Dictionary mapping node IDs to (x, y) positions
        """
        if layout_type == "circular":
            return self._layout_type_circular(G=G, scale=scale)
        elif layout_type == "hierarchical":  # Hierarchical layout with layers
            return self._layout_type_hierarchical(G=G, n_input=n_input, n_hidden=n_hidden, n_output=n_output)
        elif layout_type == "spring":  # Spring layout with constraints
            return self._layout_type_sprint(
                G=G, k=2, iterations=50, seed=42
            )  # TODO: Convert these magic numbers into constants
        elif layout_type == "staggered":
            return self._layout_type_staggered(G=G, n_input=n_input, n_hidden=n_hidden, n_output=n_output)
        else:  # Default to hierarchical
            return self._calculate_layout(
                G=G, layout_type="hierarchical", n_input=n_input, n_hidden=n_hidden, n_output=n_output
            )

    def _layout_type_circular(self, G: nx.DiGraph, scale: float = None):
        return nx.circular_layout(G, scale=scale)

    def _layout_type_hierarchical(self, G: nx.DiGraph, n_input: int, n_hidden: int, n_output: int):
        pos = {}
        # Input layer (left)
        for i in range(n_input):
            y = (i - n_input / 2) * 1.5
            pos[f"input_{i}"] = (0, y)
        # Hidden layer (middle) - staggered layout for better edge visibility
        if n_hidden > 0:
            self._calculate_hidden_node_position_offsets(n_hidden, pos)
        # Output layer (right)
        for i in range(n_output):
            y = (i - n_output / 2) * 1.5
            pos[f"output_{i}"] = (10, y)
        return pos

    def _layout_type_sprint(self, G: nx.DiGraph, k: float, iterations: int, seed: int):
        pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
        # Scale positions
        for node in pos:
            pos[node] = (pos[node][0] * 10, pos[node][1] * 10)
        return pos

    def _layout_type_staggered(self, G: nx.DiGraph, n_input: int, n_hidden: int, n_output: int):
        # Staggered hierarchical layout (same as hierarchical but more explicit)
        pos = {}
        # Input layer (left)
        for i in range(n_input):
            y = (i - n_input / 2) * 1.5
            pos[f"input_{i}"] = (0, y)
        # Hidden layer (middle) - staggered layout
        if n_hidden > 0:
            base_x = 5.0
            spread = min(3.0, max(1.5, n_hidden * 0.5))
            for i in range(n_hidden):
                y = (i - n_hidden / 2) * 1.5
                # Zigzag pattern
                if n_hidden == 1:
                    x = base_x
                else:
                    # Distribute across spread range
                    position_ratio = i / max(1, n_hidden - 1)
                    x = base_x - spread / 2 + position_ratio * spread
                    # Add small offset for zigzag effect
                    x += 0.3 if i % 2 == 0 else -0.3
                pos[f"hidden_{i}"] = (x, y)
        # Output layer (right)
        for i in range(n_output):
            y = (i - n_output / 2) * 1.5
            pos[f"output_{i}"] = (10, y)
        return pos

    def _calculate_hidden_node_position_offsets(self, n_hidden, pos):
        # Base x position (midpoint between input and output)
        base_x = 5.0
        # Stagger offset (horizontal spread)
        stagger_offset = 1.2

        # Calculate positions with alternating offsets
        hidden_x_positions = []
        for i in range(n_hidden):
            # Alternate left/right: even indices go right, odd go left
            offset = stagger_offset / 2 if i % 2 == 0 else -stagger_offset / 2
            hidden_x_positions.append(base_x + offset)

        # If more than 2 nodes, use a more spread-out stagger pattern
        if n_hidden > 2:
            # Distribute nodes across a wider horizontal range
            spread = min(3.0, n_hidden * 0.4)
            for i in range(n_hidden):
                # Create a wave pattern: first node at center, then alternating outward
                if i == 0:
                    hidden_x_positions[i] = base_x
                else:
                    # Alternate left and right with increasing offset
                    direction = 1 if i % 2 == 1 else -1
                    offset_level = (i + 1) // 2
                    hidden_x_positions[i] = base_x + direction * (offset_level * spread / max(1, (n_hidden // 2)))

        # Apply positions
        for i in range(n_hidden):
            y = (i - n_hidden / 2) * 1.5
            pos[f"hidden_{i}"] = (hidden_x_positions[i], y)

    def _create_edge_traces(
        self, G: nx.DiGraph, pos: Dict[str, Tuple[float, float]], show_weights: bool
    ) -> List[go.Scatter]:
        """
        Create edge traces for the graph.

        Args:
            G: NetworkX graph
            pos: Node positions
            show_weights: Whether to show weight labels

        Returns:
            List of Scatter traces for edges
        """
        edge_traces = []

        # Group edges by weight magnitude for coloring
        for edge in G.edges(data=True):
            from_node, to_node, data = edge
            weight = data.get("weight", 0.0)

            x0, y0 = pos[from_node]
            x1, y1 = pos[to_node]

            # Color based on weight (red for negative, blue for positive)
            color = "#3498db" if weight >= 0 else "#e74c3c"

            # Line width based on weight magnitude
            width = min(5, max(0.5, abs(weight) * 3))

            edge_trace = go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line={"width": width, "color": color},
                hoverinfo="text",
                hovertext=f"Weight: {weight:.3f}",
                showlegend=False,
            )
            edge_traces.append(edge_trace)

            # Add weight label if requested
            if show_weights:
                mid_x = (x0 + x1) / 2
                mid_y = (y0 + y1) / 2

                label_trace = go.Scatter(
                    x=[mid_x],
                    y=[mid_y],
                    mode="text",
                    text=[f"{weight:.2f}"],
                    textfont={"size": 8, "color": "#7f8c8d"},
                    hoverinfo="skip",
                    showlegend=False,
                )
                edge_traces.append(label_trace)

        return edge_traces

    def _create_node_traces(self, G: nx.DiGraph, pos: Dict[str, Tuple[float, float]]) -> List[go.Scatter]:
        """
        Create node traces for the graph.

        Args:
            G: NetworkX graph
            pos: Node positions

        Returns:
            List of Scatter traces for nodes
        """
        # Separate nodes by layer
        input_nodes = [n for n in G.nodes() if G.nodes[n].get("layer") == "input"]
        hidden_nodes = [n for n in G.nodes() if G.nodes[n].get("layer") == "hidden"]
        output_nodes = [n for n in G.nodes() if G.nodes[n].get("layer") == "output"]

        node_traces = []

        # Input nodes (green)
        if input_nodes:
            node_trace = self._create_node_trace(input_nodes, pos, "#2ecc71", "Input Units")
            node_traces.append(node_trace)

        # Hidden nodes (blue)
        if hidden_nodes:
            node_trace = self._create_node_trace(hidden_nodes, pos, "#3498db", "Hidden Units")
            node_traces.append(node_trace)

        # Output nodes (red)
        if output_nodes:
            node_trace = self._create_node_trace(output_nodes, pos, "#e74c3c", "Output Units")
            node_traces.append(node_trace)

        return node_traces

    def _create_node_trace(
        self, nodes: List[str], pos: Dict[str, Tuple[float, float]], color: str, name: str
    ) -> go.Scatter:
        """
        Create a scatter trace for a group of nodes.

        Args:
            nodes: List of node IDs
            pos: Node positions
            color: Node color
            name: Trace name for legend

        Returns:
            Scatter trace object
        """
        x_coords = [pos[node][0] for node in nodes]
        y_coords = [pos[node][1] for node in nodes]
        labels = [node.replace("_", " ").title() for node in nodes]

        return go.Scatter(
            x=x_coords,
            y=y_coords,
            mode="markers+text",
            marker={"size": 20, "color": color, "line": {"width": 2, "color": "white"}},
            text=labels,
            textposition="middle center",
            textfont={"size": 10, "color": "white", "family": "Arial Black"},
            hoverinfo="text",
            hovertext=labels,
            name=name,
        )

    def _create_selection_highlight(
        self, pos: Dict[str, Tuple[float, float]], selected_nodes: List[str]
    ) -> List[go.Scatter]:
        """
        Create highlight traces for selected nodes.

        Args:
            pos: Node positions
            selected_nodes: List of selected node IDs

        Returns:
            List of Scatter traces for selection highlights
        """
        if not selected_nodes:
            return []

        highlight_traces = []
        for node_id in selected_nodes:
            if node_id in pos:
                x, y = pos[node_id]
                highlight_traces.extend(
                    (
                        go.Scatter(
                            x=[x],
                            y=[y],
                            mode="markers",
                            marker={
                                "size": 35,
                                "color": "rgba(255, 193, 7, 0.5)",  # Yellow glow
                                "line": {"width": 3, "color": "#ffc107"},
                            },
                            name="Selected",
                            showlegend=False,
                            hoverinfo="skip",
                        ),
                        go.Scatter(
                            x=[x],
                            y=[y],
                            mode="markers",
                            marker={
                                "size": 28,
                                "color": "rgba(0, 0, 0, 0)",
                                "line": {"width": 3, "color": "#ff9800"},
                            },
                            name="Selected Ring",
                            showlegend=False,
                            hoverinfo="skip",
                        ),
                    )
                )
        return highlight_traces

    def _create_empty_graph(self, theme: str = "light") -> go.Figure:
        """
        Create empty placeholder graph.

        Args:
            theme: Current theme ("light" or "dark")

        Returns:
            Empty Plotly figure
        """
        fig = go.Figure()

        is_dark = theme == "dark"
        text_color = "#adb5bd" if is_dark else "#6c757d"

        fig.add_annotation(
            text="No network topology available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": text_color},
        )

        fig.update_layout(
            xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
            yaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
            template="plotly_dark" if is_dark else "plotly",
            plot_bgcolor="#242424" if is_dark else "#f8f9fa",
            paper_bgcolor="#242424" if is_dark else "#ffffff",
            margin={"l": 20, "r": 20, "t": 20, "b": 20},
        )

        return fig

    def update_topology(self, topology: Dict[str, Any]):
        """
        Update the network topology.

        Args:
            topology: New topology dictionary
        """
        self.current_topology = topology
        self.logger.debug(f"Topology updated: {topology.get('hidden_units', 0)} hidden units")

    def get_topology(self) -> Dict[str, Any]:
        """
        Get current network topology.

        Returns:
            Topology dictionary
        """
        return self.current_topology.copy()
