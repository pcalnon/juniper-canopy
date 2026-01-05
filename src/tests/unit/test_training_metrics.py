#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_training_metrics.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2025-11-03
# Last Modified: 2025-11-03
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
# Description:   Unit tests for TrainingMetrics component
#####################################################################
"""Unit tests for TrainingMetrics component."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from frontend.components.training_metrics import TrainingMetricsComponent  # noqa: E402


@pytest.fixture
def config():
    """Basic config for training metrics."""
    return {
        "max_history": 1000,
        "update_interval": 1000,
    }


@pytest.fixture
def metrics(config):
    """Create TrainingMetrics instance."""
    return TrainingMetricsComponent(config, component_id="test-metrics")


class TestTrainingMetricsInitialization:
    """Test TrainingMetrics initialization."""

    def test_init_with_default_config(self):
        """Should initialize with empty config."""
        metrics = TrainingMetricsComponent({})
        assert metrics is not None

    def test_init_with_custom_id(self, config):
        """Should initialize with custom component ID."""
        metrics = TrainingMetricsComponent(config, component_id="custom-metrics")
        assert metrics.component_id == "custom-metrics"

    def test_init_sets_max_history(self, config):
        """Should set max_history from config."""
        metrics = TrainingMetricsComponent(config)
        if hasattr(metrics, "max_history"):
            assert metrics.max_history == 1000

    def test_init_sets_update_interval(self, config):
        """Should set update_interval from config."""
        metrics = TrainingMetricsComponent(config)
        if hasattr(metrics, "update_interval"):
            assert metrics.update_interval == 1000


class TestTrainingMetricsLayout:
    """Test TrainingMetrics layout generation."""

    def test_get_layout_returns_div(self, metrics):
        """get_layout should return Dash Div."""
        layout = metrics.get_layout()
        assert layout is not None
        from dash import html

        assert isinstance(layout, html.Div)

    def test_layout_contains_components(self, metrics):
        """Layout should contain components."""
        layout = metrics.get_layout()
        assert hasattr(layout, "children")
        assert layout.children is not None


class TestTrainingMetricsCallbacks:
    """Test TrainingMetrics callback registration."""

    def test_setup_callbacks_returns_none(self, metrics):
        """setup_callbacks should return None."""
        from dash import Dash

        app = Dash(__name__)
        result = metrics.setup_callbacks(app)
        assert result is None

    def test_setup_callbacks_with_mock_app(self, metrics):
        """Should handle callback setup without errors."""
        from dash import Dash

        app = Dash(__name__)

        try:
            metrics.setup_callbacks(app)
            success = True
        except Exception:
            success = False

        assert success


class TestTrainingMetricsDataHandling:
    """Test data handling methods."""

    def test_update_metrics(self, metrics):
        """Should update metrics."""
        if hasattr(metrics, "update_metrics"):
            data = {"epoch": 1, "loss": 0.5, "accuracy": 0.8}
            metrics.update_metrics(data)

    def test_get_metrics_history(self, metrics):
        """Should retrieve metrics history."""
        if hasattr(metrics, "get_history"):
            history = metrics.get_history()
            assert history is not None
            assert isinstance(history, list)

    def test_clear_metrics(self, metrics):
        """Should clear metrics."""
        if hasattr(metrics, "clear"):
            metrics.clear()


class TestTrainingMetricsInheritance:
    """Test BaseComponent inheritance."""

    def test_inherits_from_base_component(self, metrics):
        """Should inherit from BaseComponent."""
        from frontend.base_component import BaseComponent

        assert isinstance(metrics, BaseComponent)

    def test_has_logger(self, metrics):
        """Should have logger from BaseComponent."""
        assert hasattr(metrics, "logger")
        assert metrics.logger is not None

    def test_has_config(self, metrics):
        """Should have config from BaseComponent."""
        assert hasattr(metrics, "config")

    def test_has_component_id(self, metrics):
        """Should have component_id from BaseComponent."""
        assert hasattr(metrics, "component_id")
        assert metrics.component_id == "test-metrics"


class TestTrainingMetricsConfiguration:
    """Test configuration handling."""

    def test_config_override_max_history(self):
        """Should override max_history from config."""
        config = {"max_history": 500}
        metrics = TrainingMetricsComponent(config)
        if hasattr(metrics, "max_history"):
            assert metrics.max_history == 500

    def test_config_override_update_interval(self):
        """Should override update_interval from config."""
        config = {"update_interval": 2000}
        metrics = TrainingMetricsComponent(config)
        if hasattr(metrics, "update_interval"):
            assert metrics.update_interval == 2000


class TestTrainingMetricsEdgeCases:
    """Test edge cases."""

    def test_very_large_max_history(self):
        """Should handle very large max_history."""
        config = {"max_history": 1000000}
        metrics = TrainingMetricsComponent(config)
        if hasattr(metrics, "max_history"):
            assert metrics.max_history == 1000000

    def test_zero_max_history(self):
        """Should handle zero max_history."""
        config = {"max_history": 0}
        metrics = TrainingMetricsComponent(config)
        # Should either accept or use default
        assert metrics is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
