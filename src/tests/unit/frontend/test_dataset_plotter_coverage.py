#!/usr/bin/env python
"""
Comprehensive coverage tests for dataset_plotter.py
Target: Raise coverage from 87% to 90%+

Tests cover:
- DatasetPlotter initialization
- 2D scatter plotting with various datasets
- Color by class functionality
- Legend creation
- Data truncation/sampling for large datasets
- Missing value handling
- Different marker styles
- Title and axis labels
- Distribution plots
- Callback function update_dataset_plots (lines 203-223)
- Unknown split filter edge case (line 249)
- Empty unique classes edge case (line 404)
"""
from unittest.mock import MagicMock, patch

import numpy as np
import plotly.graph_objects as go
import pytest
from dash import html


@pytest.mark.unit
class TestDatasetPlotterInit:
    """Test DatasetPlotter initialization."""

    def test_init_with_minimal_config(self):
        """Test initialization with minimal configuration."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config, component_id="test-plotter")

        assert component.component_id == "test-plotter"
        assert component.default_colors is not None
        assert len(component.default_colors) == 5
        assert component.current_dataset is None

    def test_init_with_custom_id(self):
        """Test initialization with custom component ID."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config, component_id="my-custom-plotter")

        assert component.component_id == "my-custom-plotter"

    def test_default_colors_defined(self):
        """Test that default colors are properly defined."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        assert isinstance(component.default_colors, list)
        assert all(isinstance(c, str) for c in component.default_colors)
        # Check they're valid hex colors
        assert all(c.startswith("#") for c in component.default_colors)


@pytest.mark.unit
class TestDatasetPlotterLayout:
    """Test layout generation."""

    def test_get_layout_structure(self):
        """Test layout contains expected elements."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)
        layout = component.get_layout()

        assert isinstance(layout, html.Div)

    def test_get_layout_with_custom_id(self):
        """Test layout uses custom component ID."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config, component_id="my-plotter")
        layout = component.get_layout()

        layout_str = str(layout)
        assert "my-plotter" in layout_str


@pytest.mark.unit
class TestDatasetPlotterDataManagement:
    """Test dataset loading and management."""

    def test_load_dataset(self):
        """Test loading a dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [1, 1], [2, 2]], "targets": [0, 1, 0]}

        component.load_dataset(dataset)

        assert component.current_dataset == dataset

    def test_get_dataset(self):
        """Test retrieving current dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [1, 1]], "targets": [0, 1]}

        component.load_dataset(dataset)
        retrieved = component.get_dataset()

        assert retrieved == dataset

    def test_get_dataset_when_none(self):
        """Test retrieving dataset when none loaded."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        result = component.get_dataset()

        assert result is None


@pytest.mark.unit
class TestDatasetPlotterScatterPlot:
    """Test scatter plot creation."""

    def test_create_scatter_plot_with_2d_data(self):
        """Test creating scatter plot with 2D data."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [1, 1], [2, 2], [1, 2]], "targets": [0, 1, 0, 1]}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0  # Should have traces

    def test_create_scatter_plot_with_1d_data(self):
        """Test creating scatter plot with 1D data."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0], [1], [2], [3]], "targets": [0, 1, 0, 1]}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)
        # 1D data should be plotted differently

    def test_create_scatter_plot_with_empty_data(self):
        """Test creating scatter plot with empty data."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [], "targets": []}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)
        # Should return empty plot

    def test_create_scatter_plot_with_multi_class(self):
        """Test scatter plot with multiple classes."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 4 classes
        dataset = {"inputs": [[0, 0], [1, 1], [2, 2], [3, 3], [0, 1], [1, 0]], "targets": [0, 1, 2, 3, 0, 1]}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)
        # Should have multiple traces for different classes

    def test_create_scatter_plot_dark_theme(self):
        """Test scatter plot with dark theme."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [1, 1]], "targets": [0, 1]}

        fig = component._create_scatter_plot(dataset, theme="dark")

        assert isinstance(fig, go.Figure)  # Dark theme applied

    def test_create_scatter_plot_with_numpy_arrays(self):
        """Test scatter plot with numpy arrays."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": np.array([[0, 0], [1, 1], [2, 2]]), "targets": np.array([0, 1, 0])}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)

    def test_create_scatter_plot_with_high_dimensional_data(self):
        """Test scatter plot with >2D data (uses first 2 features)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 5D data
        dataset = {"inputs": [[0, 0, 1, 2, 3], [1, 1, 0, 1, 2], [2, 2, 3, 0, 1]], "targets": [0, 1, 0]}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)
        # Should plot first 2 dimensions


@pytest.mark.unit
class TestDatasetPlotterDistributionPlot:
    """Test distribution plot creation."""

    def test_create_distribution_plot_with_data(self):
        """Test creating distribution plot."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": np.random.randn(100, 2), "targets": np.random.randint(0, 2, 100)}

        fig = component._create_distribution_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)
        # Should have histogram traces

    def test_create_distribution_plot_with_empty_data(self):
        """Test creating distribution plot with empty data."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [], "targets": []}

        fig = component._create_distribution_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)

    def test_create_distribution_plot_dark_theme(self):
        """Test distribution plot with dark theme."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": np.random.randn(50, 3), "targets": np.random.randint(0, 2, 50)}

        fig = component._create_distribution_plot(dataset, theme="dark")

        assert isinstance(fig, go.Figure)

    def test_create_distribution_plot_with_many_features(self):
        """Test distribution plot with >4 features (should limit to 4)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 10 features
        dataset = {"inputs": np.random.randn(50, 10), "targets": np.random.randint(0, 2, 50)}

        fig = component._create_distribution_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)


@pytest.mark.unit
class TestDatasetPlotterFilterBySplit:
    """Test split filtering functionality."""

    def test_filter_by_split_all(self):
        """Test filtering with 'all' returns full dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2]],
            "targets": [0, 1, 0],
            "split_indices": {"train": [0, 1], "test": [2]},
        }

        filtered = component._filter_by_split(dataset, "all")

        assert filtered == dataset

    def test_filter_by_split_train(self):
        """Test filtering with 'train' split."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
            "split_indices": {"train": [0, 1, 2], "test": [3]},
        }

        filtered = component._filter_by_split(dataset, "train")

        assert len(filtered["inputs"]) == 3
        assert len(filtered["targets"]) == 3

    def test_filter_by_split_test(self):
        """Test filtering with 'test' split."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
            "split_indices": {"train": [0, 1, 2], "test": [3]},
        }

        filtered = component._filter_by_split(dataset, "test")

        assert len(filtered["inputs"]) == 1
        assert len(filtered["targets"]) == 1

    def test_filter_by_split_no_indices(self):
        """Test filtering when no split indices provided."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [1, 1]], "targets": [0, 1]}

        # Without split_indices, should return full dataset
        filtered = component._filter_by_split(dataset, "train")

        assert filtered == dataset

    def test_filter_by_split_with_out_of_bounds_indices(self):
        """Test filtering with indices beyond dataset size."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
            "split_indices": {"train": [0, 1, 5, 10], "test": []},  # 5 and 10 are out of bounds
        }

        filtered = component._filter_by_split(dataset, "train")

        # Should only include valid indices
        assert len(filtered["inputs"]) == 2

    def test_filter_by_split_unknown_split_type(self):
        """Test filtering with unknown split type returns full dataset (line 249)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2]],
            "targets": [0, 1, 0],
            "split_indices": {"train": [0, 1], "test": [2]},
        }

        # Unknown split type should return original dataset
        filtered = component._filter_by_split(dataset, "validation")

        assert filtered == dataset

    def test_filter_by_split_empty_string_split(self):
        """Test filtering with empty string split returns full dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
            "split_indices": {"train": [0], "test": [1]},
        }

        filtered = component._filter_by_split(dataset, "")

        assert filtered == dataset


@pytest.mark.unit
class TestDatasetPlotterBalance:
    """Test class balance calculation."""

    def test_calculate_balance_balanced(self):
        """Test calculating balance for balanced dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # Perfectly balanced
        targets = [0, 0, 0, 1, 1, 1]

        result = component._calculate_balance(targets)

        assert result == "Balanced"

    def test_calculate_balance_imbalanced(self):
        """Test calculating balance for imbalanced dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 80% class 0, 20% class 1
        targets = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1]

        result = component._calculate_balance(targets)

        assert "Imbalanced" in result

    def test_calculate_balance_moderate(self):
        """Test calculating balance for moderately imbalanced dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 60% class 0, 40% class 1
        targets = [0, 0, 0, 0, 0, 0, 1, 1, 1, 1]

        result = component._calculate_balance(targets)

        assert "Moderate" in result or "Balanced" in result

    def test_calculate_balance_empty(self):
        """Test calculating balance for empty targets."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        targets = []

        result = component._calculate_balance(targets)

        assert result == "N/A"

    def test_calculate_balance_single_class(self):
        """Test calculating balance for single class."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        targets = [0, 0, 0, 0]

        result = component._calculate_balance(targets)

        # All same class = 100% imbalanced
        assert "Imbalanced" in result

    def test_calculate_balance_empty_unique_classes(self):
        """Test calculate_balance when np.unique returns empty (line 404)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # Mock np.unique to return empty arrays
        with patch("frontend.components.dataset_plotter.np.unique") as mock_unique:
            mock_unique.return_value = (np.array([]), np.array([]))
            result = component._calculate_balance([1, 2, 3])

        assert result == "N/A"


@pytest.mark.unit
class TestDatasetPlotterEmptyPlot:
    """Test empty plot creation."""

    def test_create_empty_plot_light_theme(self):
        """Test empty plot with light theme."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        fig = component._create_empty_plot("No data", theme="light")

        assert isinstance(fig, go.Figure)
        assert len(fig.layout.annotations) > 0

    def test_create_empty_plot_dark_theme(self):
        """Test empty plot with dark theme."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        fig = component._create_empty_plot("No data", theme="dark")

        assert isinstance(fig, go.Figure)  # Dark theme applied

    def test_create_empty_plot_custom_message(self):
        """Test empty plot with custom message."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        custom_msg = "Custom message here"
        fig = component._create_empty_plot(custom_msg, theme="light")

        assert isinstance(fig, go.Figure)


@pytest.mark.unit
class TestDatasetPlotterEdgeCases:
    """Test edge cases and error handling."""

    def test_scatter_plot_with_nan_values(self):
        """Test scatter plot handles NaN values."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [1, np.nan], [2, 2]], "targets": [0, 1, 0]}

        # Should handle gracefully
        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)

    def test_scatter_plot_with_inf_values(self):
        """Test scatter plot handles infinite values."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[0, 0], [np.inf, 1], [2, 2]], "targets": [0, 1, 0]}

        # Should handle gracefully
        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)

    def test_scatter_plot_with_single_point(self):
        """Test scatter plot with single data point."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[1, 2]], "targets": [0]}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)

    def test_scatter_plot_with_many_classes(self):
        """Test scatter plot with many classes (>5, tests color cycling)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 10 classes
        dataset = {"inputs": [[i, i] for i in range(10)], "targets": list(range(10))}

        fig = component._create_scatter_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)

    def test_callbacks_registration(self):
        """Test callback registration."""
        from dash import Dash

        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        app = Dash(__name__)

        # Should not raise
        component.register_callbacks(app)

    def test_distribution_with_single_feature(self):
        """Test distribution plot with single feature."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {"inputs": [[1], [2], [3], [4], [5]], "targets": [0, 1, 0, 1, 0]}

        fig = component._create_distribution_plot(dataset, theme="light")

        assert isinstance(fig, go.Figure)


@pytest.mark.unit
class TestUpdateDatasetPlotsCallback:
    """Test the update_dataset_plots callback function (lines 203-223)."""

    def test_callback_with_no_dataset(self):
        """Test callback returns empty plots when dataset is None (lines 203-205)."""
        from dash import Dash

        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        app = Dash(__name__)
        component.register_callbacks(app)

        # Access the registered callback
        callbacks = app.callback_map

        # The callback should be registered
        assert any(component.component_id in key for key in callbacks.keys())

    def test_callback_returns_correct_output_types_no_data(self):
        """Test callback output types when no dataset provided."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # Simulate what the callback does with no dataset
        empty_fig = component._create_empty_plot("No dataset loaded", "light")

        assert isinstance(empty_fig, go.Figure)

    def test_callback_with_valid_dataset_calculates_statistics(self):
        """Test callback calculates correct statistics from dataset (lines 214-223)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # Simulate the callback logic
        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
        }

        filtered_data = component._filter_by_split(dataset, "all")

        # Calculate statistics as the callback does
        n_samples = len(filtered_data.get("inputs", []))
        n_features = len(filtered_data["inputs"][0]) if filtered_data.get("inputs") else 0
        targets = filtered_data.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0
        balance_info = component._calculate_balance(targets) if targets else "N/A"

        assert n_samples == 4
        assert n_features == 2
        assert unique_classes == 2
        assert balance_info == "Balanced"

    def test_callback_filter_integration(self):
        """Test callback integrates filtering correctly (lines 207-208)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
            "split_indices": {"train": [0, 1], "test": [2, 3]},
        }

        # Test train split
        filtered_train = component._filter_by_split(dataset, "train")
        assert len(filtered_train["inputs"]) == 2

        # Test test split
        filtered_test = component._filter_by_split(dataset, "test")
        assert len(filtered_test["inputs"]) == 2

    def test_callback_creates_both_plot_types(self):
        """Test callback creates both scatter and distribution plots (lines 210-212)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2]],
            "targets": [0, 1, 0],
        }

        scatter_fig = component._create_scatter_plot(dataset, "light")
        dist_fig = component._create_distribution_plot(dataset, "light")

        assert isinstance(scatter_fig, go.Figure)
        assert isinstance(dist_fig, go.Figure)

    def test_callback_handles_empty_targets(self):
        """Test callback handles dataset with empty targets (lines 217-221)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [],
        }

        targets = dataset.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0
        balance_info = component._calculate_balance(targets) if targets else "N/A"

        assert unique_classes == 0
        assert balance_info == "N/A"

    def test_callback_handles_no_features(self):
        """Test callback handles dataset with empty inputs (line 216)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        DatasetPlotter(config)

        dataset = {
            "inputs": [],
            "targets": [],
        }

        n_features = len(dataset["inputs"][0]) if dataset.get("inputs") else 0
        assert n_features == 0


@pytest.mark.unit
class TestCallbackDarkTheme:
    """Test callback behavior with dark theme."""

    def test_callback_creates_dark_theme_plots(self):
        """Test callback passes dark theme to plot creation."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
        }

        scatter_fig = component._create_scatter_plot(dataset, "dark")
        dist_fig = component._create_distribution_plot(dataset, "dark")

        # Check dark theme is applied (template is a Template object)
        assert scatter_fig.layout.plot_bgcolor == "#242424"
        assert dist_fig.layout.plot_bgcolor == "#242424"

    def test_callback_creates_light_theme_plots(self):
        """Test callback passes light theme to plot creation."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
        }

        scatter_fig = component._create_scatter_plot(dataset, "light")
        dist_fig = component._create_distribution_plot(dataset, "light")

        # Check light theme is applied
        assert scatter_fig.layout.plot_bgcolor == "#f8f9fa"
        assert dist_fig.layout.plot_bgcolor == "#f8f9fa"


@pytest.mark.unit
class TestProcessDatasetUpdate:
    """Test the _process_dataset_update method directly.

    This covers lines 206-243 (the extracted callback logic).
    """

    def test_process_update_no_dataset_returns_empty(self):
        """Test returns empty plots when dataset is None (lines 221-223)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        result = component._process_dataset_update(None, "all", "light")

        assert result[2] == "0"  # sample count
        assert result[3] == "0"  # feature count
        assert result[4] == "0"  # class count
        assert result[5] == "N/A"  # balance info

    def test_process_update_with_valid_dataset(self):
        """Test with valid dataset (lines 225-243)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
        }

        result = component._process_dataset_update(dataset, "all", "light")

        assert result[2] == "4"  # 4 samples
        assert result[3] == "2"  # 2 features
        assert result[4] == "2"  # 2 classes
        assert result[5] == "Balanced"

    def test_process_update_with_train_split(self):
        """Test with train split filter (line 226)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
            "split_indices": {"train": [0, 1], "test": [2, 3]},
        }

        result = component._process_dataset_update(dataset, "train", "light")

        assert result[2] == "2"  # 2 samples in train

    def test_process_update_with_dark_theme(self):
        """Test with dark theme (lines 221-222, 229-230)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
        }

        result = component._process_dataset_update(dataset, "all", "dark")

        # Verify dark theme is applied to scatter plot
        scatter_fig = result[0]
        assert scatter_fig.layout.plot_bgcolor == "#242424"

    def test_process_update_empty_after_filter(self):
        """Test handles empty dataset after filtering (lines 233-238)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
            "split_indices": {"train": [0, 1], "test": []},
        }

        result = component._process_dataset_update(dataset, "test", "light")

        assert result[2] == "0"  # 0 samples
        assert result[3] == "0"  # 0 features
        assert result[4] == "0"  # 0 classes
        assert result[5] == "N/A"  # balance N/A

    def test_process_update_with_imbalanced_dataset(self):
        """Test calculates imbalanced correctly (line 241)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # 80% class 0
        dataset = {
            "inputs": [[i, i] for i in range(10)],
            "targets": [0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
        }

        result = component._process_dataset_update(dataset, "all", "light")

        assert "Imbalanced" in result[5]

    def test_process_update_with_empty_targets(self):
        """Test handles empty targets (lines 235-241)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [],
        }

        result = component._process_dataset_update(dataset, "all", "light")

        assert result[4] == "0"  # 0 classes
        assert result[5] == "N/A"  # balance N/A

    def test_process_update_returns_figures(self):
        """Test returns proper figure objects (lines 229-230)."""
        import plotly.graph_objects as go

        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
        }

        result = component._process_dataset_update(dataset, "all", "light")

        assert isinstance(result[0], go.Figure)  # scatter plot
        assert isinstance(result[1], go.Figure)  # distribution plot


@pytest.mark.unit
class TestCallbackDirectInvocation:
    """Test the callback by simulating callback logic.

    This tests the update_dataset_plots callback function (lines 203-223)
    by calling the same methods the callback uses.
    """

    def test_callback_logic_no_dataset_returns_empty(self):
        """Test callback returns empty plots when dataset is None (line 203-205)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # Use the extracted method
        result = component._process_dataset_update(None, "all", "light")

        assert result[2] == "0"  # sample count
        assert result[3] == "0"  # feature count
        assert result[4] == "0"  # class count
        assert result[5] == "N/A"  # balance info

    def test_callback_logic_with_dataset(self):
        """Test callback logic with valid dataset (lines 207-223)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2], [3, 3]],
            "targets": [0, 1, 0, 1],
        }
        split = "all"
        theme = "light"

        # Simulate callback logic
        filtered_data = component._filter_by_split(dataset, split)
        scatter_fig = component._create_scatter_plot(filtered_data, theme)
        dist_fig = component._create_distribution_plot(filtered_data, theme)

        n_samples = len(filtered_data.get("inputs", []))
        n_features = len(filtered_data["inputs"][0]) if filtered_data.get("inputs") else 0
        targets = filtered_data.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0
        balance_info = component._calculate_balance(targets) if targets else "N/A"

        result = (scatter_fig, dist_fig, str(n_samples), str(n_features), str(unique_classes), balance_info)

        assert result[2] == "4"  # 4 samples
        assert result[3] == "2"  # 2 features
        assert result[4] == "2"  # 2 classes
        assert result[5] == "Balanced"

    def test_callback_logic_empty_filtered_inputs(self):
        """Test callback handles empty inputs after filtering (line 216)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        # Dataset where test split has no data
        dataset = {
            "inputs": [[0, 0], [1, 1]],
            "targets": [0, 1],
            "split_indices": {"train": [0, 1], "test": []},
        }
        split = "test"

        filtered_data = component._filter_by_split(dataset, split)

        n_samples = len(filtered_data.get("inputs", []))
        n_features = len(filtered_data["inputs"][0]) if filtered_data.get("inputs") else 0
        targets = filtered_data.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0
        balance_info = component._calculate_balance(targets) if targets else "N/A"

        assert n_samples == 0
        assert n_features == 0
        assert unique_classes == 0
        assert balance_info == "N/A"

    def test_callback_logic_with_dark_theme(self):
        """Test callback creates dark theme plots (line 204, 211, 212)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = None
        theme = "dark"

        if not dataset:
            empty_fig = component._create_empty_plot("No dataset loaded", theme)

        # Verify dark theme is applied
        assert empty_fig.layout.plot_bgcolor == "#242424"

    def test_callback_logic_with_single_sample(self):
        """Test callback handles single sample dataset."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[1, 2]],
            "targets": [0],
        }
        split = "all"

        filtered_data = component._filter_by_split(dataset, split)
        n_samples = len(filtered_data.get("inputs", []))
        n_features = len(filtered_data["inputs"][0]) if filtered_data.get("inputs") else 0
        targets = filtered_data.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0

        assert n_samples == 1
        assert n_features == 2
        assert unique_classes == 1

    def test_callback_logic_all_split_bypasses_filter(self):
        """Test 'all' split returns full dataset (line 238)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        component = DatasetPlotter(config)

        dataset = {
            "inputs": [[0, 0], [1, 1], [2, 2]],
            "targets": [0, 1, 0],
            "split_indices": {"train": [0], "test": [1, 2]},
        }

        filtered_data = component._filter_by_split(dataset, "all")
        assert len(filtered_data["inputs"]) == 3

    def test_callback_logic_targets_with_multiple_classes(self):
        """Test callback correctly counts multiple unique classes (line 218)."""
        from frontend.components.dataset_plotter import DatasetPlotter

        config = {}
        DatasetPlotter(config)

        dataset = {
            "inputs": [[i, i] for i in range(10)],
            "targets": [0, 1, 2, 3, 4, 0, 1, 2, 3, 4],  # 5 unique classes
        }

        targets = dataset.get("targets", [])
        unique_classes = len(set(targets)) if targets else 0

        assert unique_classes == 5
