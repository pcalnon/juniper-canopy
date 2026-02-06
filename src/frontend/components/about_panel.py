#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     about_panel.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2026-01-07
# Last Modified: 2026-01-07
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
#
# Description:
#    About panel component displaying application information, credits, and support resources.
#
#####################################################################################################################################################################################################
# Notes:
#
# About Panel Component
#
# Static informational panel displaying version, license, credits, documentation links,
# and contact information for Juniper Canopy.
#
#####################################################################################################################################################################################################
# References:
#
#####################################################################################################################################################################################################
# TODO :
#
#####################################################################################################################################################################################################
# COMPLETED:
#   - Initial implementation for Phase 2 (P2-3)
#
#####################################################################################################################################################################################################
from typing import Any, Dict

import dash_bootstrap_components as dbc
from dash import html

from ..base_component import BaseComponent

# Version information - should match pyproject.toml
APP_VERSION = "2.2.0"
APP_NAME = "Juniper Canopy"
COPYRIGHT_YEAR = "2024-2026"


class AboutPanel(BaseComponent):
    """
    About panel component displaying application information.

    Shows:
    - Application version
    - License information
    - Credits and acknowledgments
    - Links to documentation and support resources
    - Contact information for support
    """

    def __init__(self, config: Dict[str, Any], component_id: str = "about-panel"):
        """
        Initialize about panel component.

        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        super().__init__(config, component_id)

        # Allow version override from config
        self.version = config.get("version", APP_VERSION)
        self.app_name = config.get("app_name", APP_NAME)

        self.logger.info(f"AboutPanel initialized: {self.app_name} v{self.version}")

    def get_layout(self) -> html.Div:
        """
        Get Dash layout for about panel.

        Returns:
            Dash Div containing the about information
        """
        return html.Div(
            [
                # Application Title and Version
                html.Div(
                    [
                        html.H3(
                            f"About {self.app_name}",
                            style={"color": "#2c3e50", "marginBottom": "20px"},
                        ),
                        dbc.Badge(
                            f"Version {self.version}",
                            color="primary",
                            className="mb-3",
                            style={"fontSize": "14px"},
                        ),
                    ],
                    style={"marginBottom": "20px"},
                ),
                # Description
                html.Div(
                    [
                        html.P(
                            "Juniper Canopy is a real-time monitoring and diagnostic frontend for the " "Cascade Correlation Neural Network (CasCor) prototype.",
                            style={"fontSize": "15px", "lineHeight": "1.6"},
                        ),
                        html.P(
                            "It provides interactive visualization of network training, topology, " "decision boundaries, and dataset analysis.",
                            style={"fontSize": "15px", "lineHeight": "1.6", "marginBottom": "20px"},
                        ),
                    ]
                ),
                html.Hr(),
                # License Information
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("License Information", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            [
                                html.P(
                                    [
                                        html.Strong("License: "),
                                        "MIT License",
                                    ]
                                ),
                                html.P(
                                    f"Copyright © {COPYRIGHT_YEAR} Paul Calnon",
                                    style={"color": "#6c757d"},
                                ),
                                html.P(
                                    "Permission is hereby granted, free of charge, to any person obtaining a copy " "of this software and associated documentation files, to deal in the Software " "without restriction, including without limitation the rights to use, copy, " "modify, merge, publish, distribute, sublicense, and/or sell copies of the " "Software.",
                                    style={"fontSize": "12px", "color": "#6c757d", "fontStyle": "italic"},
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # Credits and Acknowledgments
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Credits and Acknowledgments", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            [
                                html.Ul(
                                    [
                                        html.Li(
                                            [
                                                html.Strong("Primary Author: "),
                                                "Paul Calnon",
                                            ]
                                        ),
                                        html.Li(
                                            [
                                                html.Strong("CasCor Algorithm: "),
                                                "Based on the Cascade-Correlation learning architecture " "by Scott E. Fahlman and Christian Lebiere (1990)",
                                            ]
                                        ),
                                        html.Li(
                                            [
                                                html.Strong("Built With: "),
                                                "Python, FastAPI, Dash, Plotly, NetworkX, NumPy",
                                            ]
                                        ),
                                        html.Li(
                                            [
                                                html.Strong("UI Framework: "),
                                                "Dash Bootstrap Components",
                                            ]
                                        ),
                                    ],
                                    style={"listStyleType": "disc", "paddingLeft": "20px"},
                                )
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # Documentation and Support
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Documentation and Support", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            [
                                html.Ul(
                                    [
                                        html.Li(
                                            html.A(
                                                "📖 User Manual",
                                                href="/docs/USER_MANUAL.md",
                                                target="_blank",
                                                style={"textDecoration": "none"},
                                            )
                                        ),
                                        html.Li(
                                            html.A(
                                                "🚀 Quick Start Guide",
                                                href="/docs/QUICK_START.md",
                                                target="_blank",
                                                style={"textDecoration": "none"},
                                            )
                                        ),
                                        html.Li(
                                            html.A(
                                                "📚 API Documentation",
                                                href="/docs/api/",
                                                target="_blank",
                                                style={"textDecoration": "none"},
                                            )
                                        ),
                                        html.Li(
                                            html.A(
                                                "⚙️ Environment Setup",
                                                href="/docs/ENVIRONMENT_SETUP.md",
                                                target="_blank",
                                                style={"textDecoration": "none"},
                                            )
                                        ),
                                        html.Li(
                                            html.A(
                                                "🐛 Issue Tracker (GitHub)",
                                                href="https://github.com/pcalnon/Juniper/issues",
                                                target="_blank",
                                                style={"textDecoration": "none"},
                                            )
                                        ),
                                    ],
                                    style={"listStyleType": "none", "paddingLeft": "10px"},
                                )
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # Contact Information
                dbc.Card(
                    [
                        dbc.CardHeader(
                            html.H5("Contact", className="mb-0"),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.CardBody(
                            [
                                html.P(
                                    [
                                        html.Strong("Repository: "),
                                        html.A(
                                            "github.com/pcalnon/Juniper",
                                            href="https://github.com/pcalnon/Juniper",
                                            target="_blank",
                                        ),
                                    ]
                                ),
                                html.P(
                                    [
                                        html.Strong("For Support: "),
                                        "Please open an issue on GitHub or refer to the documentation.",
                                    ]
                                ),
                            ]
                        ),
                    ],
                    className="mb-3",
                ),
                # System Information (collapsible)
                dbc.Card(
                    [
                        dbc.CardHeader(
                            dbc.Button(
                                "System Information",
                                id=f"{self.component_id}-system-info-toggle",
                                color="link",
                                className="text-decoration-none p-0",
                            ),
                            style={"backgroundColor": "#f8f9fa"},
                        ),
                        dbc.Collapse(
                            dbc.CardBody(
                                [
                                    html.Div(id=f"{self.component_id}-system-info-content"),
                                ]
                            ),
                            id=f"{self.component_id}-system-info-collapse",
                            is_open=False,
                        ),
                    ],
                    className="mb-3",
                ),
            ],
            id=self.component_id,
            style={"padding": "20px", "maxWidth": "800px", "margin": "0 auto"},
        )

    def register_callbacks(self, app):
        """
        Register Dash callbacks for about panel.

        Args:
            app: Dash application instance
        """
        from dash.dependencies import Input, Output, State

        @app.callback(
            Output(f"{self.component_id}-system-info-collapse", "is_open"),
            Input(f"{self.component_id}-system-info-toggle", "n_clicks"),
            State(f"{self.component_id}-system-info-collapse", "is_open"),
            prevent_initial_call=True,
        )
        def toggle_system_info(n_clicks, is_open):
            """Toggle system information section."""
            return not is_open if n_clicks else is_open

        @app.callback(
            Output(f"{self.component_id}-system-info-content", "children"),
            Input(f"{self.component_id}-system-info-collapse", "is_open"),
        )
        def update_system_info(is_open):
            """Update system information content when opened."""
            if not is_open:
                return []

            import platform
            import sys

            return html.Ul(
                [
                    html.Li(f"Python Version: {sys.version.split()[0]}"),
                    html.Li(f"Platform: {platform.system()} {platform.release()}"),
                    html.Li(f"Architecture: {platform.machine()}"),
                    html.Li(f"App Version: {self.version}"),
                ],
                style={"listStyleType": "disc", "paddingLeft": "20px", "fontSize": "13px"},
            )

        # Expose callback functions for unit testing
        self._cb_toggle_system_info = toggle_system_info
        self._cb_update_system_info = update_system_info

        self.logger.debug(f"Callbacks registered for {self.component_id}")
