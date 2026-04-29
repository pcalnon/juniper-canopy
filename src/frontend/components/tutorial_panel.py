"""Tutorial and help panel for Juniper Canopy dashboard."""

from typing import Any, Dict

import dash_bootstrap_components as dbc
from dash import html

from ..base_component import BaseComponent


class TutorialPanel(BaseComponent):
    """Interactive tutorial and reference guide for the CasCor dashboard.

    Provides:
    - CasCor algorithm overview
    - UI component guide
    - Typical workflow walkthrough
    - Parameter reference
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "tutorial-panel"):
        super().__init__(config, component_id)

    def get_layout(self) -> html.Div:
        return html.Div(
            [
                html.Div(
                    [
                        html.H3("Tutorial & Reference Guide", style={"display": "inline-block", "marginRight": "20px"}),
                        # CAN-019: launches the interactive walkthrough overlay.
                        # Sets ``walkthrough-state-store`` to ``{active: True,
                        # index: 0}``; a clientside callback in dashboard_manager
                        # picks that up and calls
                        # ``window._juniperWalkthrough.show(steps, 0)``.
                        dbc.Button(
                            "▶ Take a guided tour",
                            id="walkthrough-launch-btn",
                            color="primary",
                            outline=True,
                            size="sm",
                            style={"verticalAlign": "middle"},
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Accordion(
                    [
                        dbc.AccordionItem(
                            self._cascor_overview(),
                            title="What is Cascade Correlation?",
                            item_id="cascor-overview",
                        ),
                        dbc.AccordionItem(
                            self._workflow_guide(),
                            title="Getting Started — Typical Workflow",
                            item_id="workflow",
                        ),
                        dbc.AccordionItem(
                            self._ui_guide(),
                            title="Dashboard Components",
                            item_id="ui-guide",
                        ),
                        dbc.AccordionItem(
                            self._parameter_reference(),
                            title="Parameter Reference",
                            item_id="param-ref",
                        ),
                        dbc.AccordionItem(
                            self._keyboard_shortcuts(),
                            title="Tips & Shortcuts",
                            item_id="shortcuts",
                        ),
                    ],
                    id=f"{self.component_id}-accordion",
                    start_collapsed=True,
                    always_open=True,
                ),
            ],
            id=self.component_id,
        )

    def _cascor_overview(self) -> html.Div:
        return html.Div(
            [
                dbc.Alert(
                    "Cascade Correlation (CasCor) is a constructive neural network algorithm " "that grows the network architecture during training by adding hidden units one at a time.",
                    color="info",
                ),
                html.H5("How It Works"),
                html.Ol(
                    [
                        html.Li(
                            [
                                html.Strong("Output Training: "),
                                "Train output weights on the current network (initially input→output only). " "The network learns what it can with its current architecture.",
                            ]
                        ),
                        html.Li(
                            [
                                html.Strong("Candidate Training: "),
                                "If error is still high, create a pool of candidate hidden units. " "Each candidate is trained to maximize correlation with the residual error.",
                            ]
                        ),
                        html.Li(
                            [
                                html.Strong("Installation: "),
                                "The best candidate (highest correlation) is permanently installed. " "Its input weights are frozen — only output weights are retrained.",
                            ]
                        ),
                        html.Li(
                            [
                                html.Strong("Repeat: "),
                                "Return to step 1. The network now has one more hidden unit. " "Continue until convergence or the max hidden unit limit.",
                            ]
                        ),
                    ]
                ),
                html.H5("Key Concepts", className="mt-3"),
                dbc.ListGroup(
                    [
                        dbc.ListGroupItem([html.Strong("Grow Iteration: "), "One cycle of output training → candidate training → installation."]),
                        dbc.ListGroupItem([html.Strong("Candidate Pool: "), "Multiple candidates trained in parallel; best one wins."]),
                        dbc.ListGroupItem([html.Strong("Correlation: "), "Measure of how well a candidate's activation tracks the residual error."]),
                        dbc.ListGroupItem([html.Strong("Frozen Weights: "), "Once installed, a hidden unit's input weights never change."]),
                    ],
                    flush=True,
                ),
            ]
        )

    def _workflow_guide(self) -> html.Div:
        return html.Div(
            [
                html.H5("Step-by-Step Workflow"),
                dbc.ListGroup(
                    [
                        dbc.ListGroupItem(
                            [
                                html.Strong("1. Generate Dataset "),
                                html.Span("(Dataset View tab → Generate Dataset button)", className="text-muted"),
                                html.Br(),
                                "Create a spiral dataset with custom parameters (samples, rotations, noise).",
                            ]
                        ),
                        dbc.ListGroupItem(
                            [
                                html.Strong("2. Configure Parameters "),
                                html.Span("(Meta Parameters sidebar panel)", className="text-muted"),
                                html.Br(),
                                "Set learning rate, max iterations, candidate pool size, etc. Click Apply.",
                            ]
                        ),
                        dbc.ListGroupItem(
                            [
                                html.Strong("3. Start Training "),
                                html.Span("(Training Controls → Start)", className="text-muted"),
                                html.Br(),
                                "Watch output training on the Training Metrics tab. Loss should decrease.",
                            ]
                        ),
                        dbc.ListGroupItem(
                            [
                                html.Strong("4. Monitor Progress "),
                                html.Span("(Training Metrics + Network Topology tabs)", className="text-muted"),
                                html.Br(),
                                "Observe grow iterations adding hidden units. Watch the decision boundary evolve.",
                            ]
                        ),
                        dbc.ListGroupItem(
                            [
                                html.Strong("5. Save Snapshots "),
                                html.Span("(HDF5 Snapshots tab)", className="text-muted"),
                                html.Br(),
                                "Save network state at key points. Snapshots capture weights and parameters.",
                            ]
                        ),
                    ],
                    flush=True,
                ),
            ]
        )

    def _ui_guide(self) -> html.Div:
        return html.Div(
            [
                html.H5("Dashboard Tabs"),
                dbc.Table(
                    [
                        html.Thead(html.Tr([html.Th("Tab"), html.Th("Purpose")])),
                        html.Tbody(
                            [
                                html.Tr([html.Td("Training Metrics"), html.Td("Loss/accuracy charts, progress bars, candidate pool status")]),
                                html.Tr([html.Td("Network Topology"), html.Td("Interactive graph of network architecture (inputs, hidden, output)")]),
                                html.Tr([html.Td("Decision Boundaries"), html.Td("2D visualization of classification regions — updates during training")]),
                                html.Tr([html.Td("Dataset View"), html.Td("Scatter plot of training/test data with class distributions")]),
                                html.Tr([html.Td("HDF5 Snapshots"), html.Td("Save/load network state checkpoints")]),
                                html.Tr([html.Td("Parameters"), html.Td("Read-only summary of current applied training parameters")]),
                                html.Tr([html.Td("Tutorial"), html.Td("This guide — algorithm reference and workflow help")]),
                            ]
                        ),
                    ],
                    bordered=True,
                    hover=True,
                    size="sm",
                ),
                html.H5("Sidebar Controls", className="mt-3"),
                html.P("The left sidebar contains training controls (Start/Stop/Pause/Resume/Reset) " "and meta parameter inputs organized into Neural Network and Candidate Node sections. " "Hover over any input for a tooltip description."),
            ]
        )

    def _parameter_reference(self) -> html.Div:
        params = [
            ("Max Iterations", "Maximum grow iterations (cascade additions)", "10"),
            ("Max Total Epochs", "Total output training epochs across all iterations", "1,000,000"),
            ("Learning Rate", "Step size for output weight gradient descent", "0.01"),
            ("Max Hidden Units", "Maximum cascade layers to add", "40"),
            ("Pool Size", "Candidates trained per grow iteration", "8"),
            ("Correlation Threshold", "Minimum correlation to install a candidate", "0.01"),
            ("Candidate Epochs", "Training epochs per candidate node", "200"),
            ("Candidate Convergence", "Stop candidate training below this improvement", "0.0001"),
        ]
        return html.Div(
            [
                html.H5("Key Parameters"),
                dbc.Table(
                    [
                        html.Thead(html.Tr([html.Th("Parameter"), html.Th("Description"), html.Th("Default")])),
                        html.Tbody([html.Tr([html.Td(p[0]), html.Td(p[1]), html.Td(p[2])]) for p in params]),
                    ],
                    bordered=True,
                    hover=True,
                    size="sm",
                ),
            ]
        )

    def _keyboard_shortcuts(self) -> html.Div:
        return html.Div(
            [
                html.H5("Tips"),
                dbc.ListGroup(
                    [
                        dbc.ListGroupItem("Hover over any parameter input in the sidebar for a tooltip description."),
                        dbc.ListGroupItem("The active tab is saved automatically — it persists across page reloads."),
                        dbc.ListGroupItem("Use the sliding window control on Training Metrics to zoom into recent epochs."),
                        dbc.ListGroupItem("Decision boundaries update every 1 second when the boundaries tab is active."),
                        dbc.ListGroupItem("Snapshots capture both network weights and parameter values — restore brings back both."),
                        dbc.ListGroupItem("Generate Dataset stops any running training and resets metrics history."),
                    ],
                    flush=True,
                ),
            ]
        )

    def register_callbacks(self, app):
        pass
