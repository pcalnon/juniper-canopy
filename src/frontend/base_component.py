#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     base_component.py
# Author:        Paul Calnon
# Version:       0.1.4 (0.7.3)
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This module provides abstract base classes for frontend components.
#
#####################################################################################################################################################################################################
# Notes:
#
#     Base Component Classes
#     Provides abstract base classes for frontend components following a common interface.
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
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

import plotly.graph_objects as go

from frontend.theme_constants import get_theme_bg


def create_empty_plot(message: str = "No data available", theme: str = "light") -> go.Figure:
    """Create an empty placeholder plot with a centered message.

    Shared utility for all dashboard components.

    Args:
        message: Message to display in the empty plot.
        theme: Current theme ("light" or "dark").

    Returns:
        Empty Plotly figure with centered annotation.
    """
    fig = go.Figure()
    bg = get_theme_bg(theme)

    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 16, "color": bg["text_color"]},
    )

    fig.update_layout(
        xaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        yaxis={"showgrid": False, "showticklabels": False, "zeroline": False},
        template="plotly_dark" if theme == "dark" else "plotly",
        plot_bgcolor=bg["plot_bgcolor"],
        paper_bgcolor=bg["paper_bgcolor"],
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )

    return fig


class BaseComponent(ABC):
    """
    Abstract base class for all dashboard components.
    Provides common interface and functionality for all visualization components.
    """

    def __init__(self, config: Dict[str, Any], component_id: str):
        """
        Initialize base component.
        Args:
            config: Component configuration dictionary
            component_id: Unique identifier for this component
        """
        self.config = config
        self.component_id = component_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.is_initialized = False

    @abstractmethod
    def get_layout(self) -> Any:
        """
        Get Dash layout for this component.

        Returns:
            Dash component layout
        """
        pass

    @abstractmethod
    def register_callbacks(self, app):
        """
        Register Dash callbacks for this component.

        Args:
            app: Dash application instance
        """
        pass

    def initialize(self):
        """Initialize component (called once)."""
        if not self.is_initialized:
            self.logger.info(f"Initializing component: {self.component_id}")
            self.is_initialized = True

    def cleanup(self):
        """Clean up component resources."""
        self.logger.info(f"Cleaning up component: {self.component_id}")

    def get_component_id(self) -> str:
        """Get component identifier."""
        return self.component_id

    def update_config(self, config: Dict[str, Any]):
        """
        Update component configuration.

        Args:
            config: New configuration dictionary
        """
        self.config.update(config)
        self.logger.debug(f"Configuration updated for {self.component_id}")
