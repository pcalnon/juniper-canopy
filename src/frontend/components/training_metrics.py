#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     training_metrics.py
# Author:        Paul Calnon
# Version:       1.0.0
#
# Date:          2025-10-11
# Last Modified: 2025-12-03
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    This module provides components for visualizing and managing training metrics
#    collected during the Cascade Correlation Neural Network training process.
#
#####################################################################################################################################################################################################
# Notes:
#
#     Training Metrics Component for CasCor Integration.
#         File: src/frontend/components/training_metrics.py
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
import plotly.graph_objects as go
from dash import html

from frontend.base_component import BaseComponent
from logger.logger import get_ui_logger


class TrainingMetricsComponent(BaseComponent):
    def __init__(self, config, component_id="training-metrics"):
        super().__init__(config, component_id)
        self.metrics_buffer = []
        self.logger = get_ui_logger()

    def get_layout(self):
        """Return empty layout - this is a legacy component."""
        layout = html.Div(id=f"{self.component_id}-container")
        layout.children = []  # Ensure children attribute exists
        return layout

    def register_callbacks(self, app):
        """No callbacks - legacy component."""
        pass

    def setup_callbacks(self, app):
        """Alias for register_callbacks to match test expectations."""
        return self.register_callbacks(app)

    def create_loss_plot(self, metrics_data):
        fig = go.Figure()

        # Handle both object attributes and dict formats
        epochs = [m.get("epoch", 0) if isinstance(m, dict) else m.epoch for m in metrics_data]
        losses = [m.get("metrics", {}).get("loss", 0) if isinstance(m, dict) else m.loss for m in metrics_data]

        fig.add_trace(go.Scatter(x=epochs, y=losses, mode="lines", name="Training Loss", line={"color": "#1f77b4", "width": 2}))

        fig.update_layout(title="Training Loss Over Time", xaxis_title="Epoch", yaxis_title="Loss")

        return fig
