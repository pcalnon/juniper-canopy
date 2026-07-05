#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.dataset_plotter``.

Drives the sequence-control callback wrappers (via a stub app), the
``populate_dataset_selector`` generator-fetch callback (success + fallback),
and the empty/continue guard branches inside the sequence figure builders
(``_plot_normalized_series``, ``_create_windows_plot``, ``_create_target_plot``,
``_create_hist_plot``, ``_create_grid_plot``).
"""

from unittest.mock import MagicMock, patch

import plotly.graph_objects as go
import pytest
from dash import html

from frontend.components.dataset_plotter import DatasetPlotter


class _StubApp:
    def __init__(self):
        self.callbacks = []

    def callback(self, *outputs, **kwargs):
        def decorator(fn):
            self.callbacks.append((outputs, kwargs, fn))
            return fn

        return decorator


@pytest.fixture
def panel():
    return DatasetPlotter({}, component_id="dsp-gate")


@pytest.fixture
def callbacks(panel):
    app = _StubApp()
    panel.register_callbacks(app)
    return {fn.__name__: fn for _, _, fn in app.callbacks}


SEQ_DATASET = {
    "dataset_kind": "sequence",
    "n_windows": 2,
    "n_windows_stored": 2,
    "n_features": 2,
    "lookback": 3,
    "sequence": {
        "windows_X": [
            [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            [[1.1, 1.2], [1.3, 1.4], [1.5, 1.6]],
        ],
        "windows_dt": [[0.1, 0.1, 0.1], [0.2, 0.2, 0.2]],
        "windows_y": [[0.5, 0.6], [0.7, 0.8]],
        "feature_labels": ["sig0", "sig1"],
        "dt_hist": {"edges": [0.0, 0.1, 0.2], "counts": [3, 4]},
        "target_hist": {"edges": [0.0, 0.5, 1.0], "counts": [2, 5]},
    },
}

TABULAR_DATASET = {"inputs": [[0.1, 0.2], [0.3, 0.4], [-0.1, -0.2], [0.5, 0.6]], "targets": [0, 1, 0, 1]}
METADATA_ONLY = {"num_samples": 100, "num_features": 5, "num_classes": 3}


class TestUpdateDatasetPlotsCallback:
    def test_none_dataset_returns_empty_tuple(self, callbacks):
        out = callbacks["update_dataset_plots"](None, "all", "light", None, "small_multiples", "signals", 0, 0, None)
        assert out[2:] == ("0", "0", "0", "N/A")

    def test_tabular_dataset(self, callbacks):
        scatter, dist, n_samples, n_features, n_classes, balance = callbacks["update_dataset_plots"](TABULAR_DATASET, "all", "dark", None, "small_multiples", "signals", 0, 0, None)
        assert isinstance(scatter, go.Figure)
        assert n_samples == "4"
        assert n_features == "2"

    def test_metadata_only_dataset(self, callbacks):
        out = callbacks["update_dataset_plots"](METADATA_ONLY, "all", "light", None, "small_multiples", "signals", 0, 0, None)
        assert out[2] == "100"
        assert out[3] == "5"

    def test_sequence_signals_mode(self, callbacks):
        scatter, dist, n_windows, n_features, _c, _b = callbacks["update_dataset_plots"](SEQ_DATASET, "all", "light", [0, 1], "small_multiples", "signals", 0, None, None)
        assert isinstance(scatter, go.Figure)
        assert n_windows == "2"

    def test_sequence_windows_mode_overlay(self, callbacks):
        scatter, *_ = callbacks["update_dataset_plots"](SEQ_DATASET, "all", "dark", None, "overlay", "windows", 0, 0, [0, 1])
        assert isinstance(scatter, go.Figure)


class TestPopulateDatasetSelectorCallback:
    def test_success_defaults_to_spiral(self, callbacks):
        resp = MagicMock(ok=True)
        resp.json.return_value = {"generators": [{"name": "spiral", "display_name": "Spiral"}, {"name": "xor"}]}
        with patch("requests.get", return_value=resp):
            options, value = callbacks["populate_dataset_selector"](1)
        assert value == "spiral"
        assert {"label": "Spiral", "value": "spiral"} in options

    def test_success_without_spiral_uses_first_option(self, callbacks):
        resp = MagicMock(ok=True)
        resp.json.return_value = {"generators": [{"name": "xor"}, {"name": "moon"}]}
        with patch("requests.get", return_value=resp):
            options, value = callbacks["populate_dataset_selector"](1)
        assert value == "xor"
        assert options[0]["value"] == "xor"

    def test_exception_falls_back_to_static_list(self, callbacks):
        with patch("requests.get", side_effect=RuntimeError("no server")):
            options, value = callbacks["populate_dataset_selector"](1)
        assert value == "spiral"
        assert any(o["value"] == "circles" for o in options)


class TestSequenceControlCallbacks:
    def test_populate_sequence_controls_sequence(self, callbacks):
        out = callbacks["populate_sequence_controls"](SEQ_DATASET)
        assert len(out) == 8
        # signal-multi options + all-selected default.
        assert out[0] == [{"label": "sig0", "value": 0}, {"label": "sig1", "value": 1}]
        assert out[1] == [0, 1]

    def test_populate_sequence_controls_non_sequence_empty(self, callbacks):
        out = callbacks["populate_sequence_controls"](None)
        assert out == ([], None, [], None, [], None, [], None)

    def test_toggle_sequence_controls_visible_for_sequence(self, callbacks):
        style = callbacks["toggle_sequence_controls"](SEQ_DATASET)
        assert style["display"] == "flex"

    def test_toggle_sequence_controls_hidden_for_tabular(self, callbacks):
        style = callbacks["toggle_sequence_controls"](TABULAR_DATASET)
        assert style["display"] == "none"

    def test_toggle_mode_groups_windows(self, callbacks):
        signals_style, windows_style = callbacks["toggle_sequence_mode_groups"]("windows")
        assert signals_style == {"display": "none"}
        assert windows_style["display"] == "flex"

    def test_toggle_mode_groups_signals(self, callbacks):
        signals_style, windows_style = callbacks["toggle_sequence_mode_groups"]("signals")
        assert signals_style["display"] == "flex"
        assert windows_style == {"display": "none"}


class TestSequenceCompanionCallbacks:
    def test_update_sequence_target_toggled_on(self, callbacks):
        fig, style = callbacks["update_sequence_target"](SEQ_DATASET, ["on"], "signals", 0, None, "light")
        assert isinstance(fig, go.Figure)
        assert style["display"] == "block"

    def test_update_sequence_target_off(self, callbacks):
        fig, style = callbacks["update_sequence_target"](SEQ_DATASET, [], "signals", 0, None, "light")
        assert style["display"] == "none"

    def test_update_sequence_characterization(self, callbacks):
        dt_fig, tgt_fig, stats, style = callbacks["update_sequence_characterization"](SEQ_DATASET, "dark")
        assert isinstance(dt_fig, go.Figure)
        assert style["display"] == "block"

    def test_update_sequence_characterization_non_sequence(self, callbacks):
        _dt, _tgt, stats, style = callbacks["update_sequence_characterization"](None, "light")
        assert style == {"display": "none"}

    def test_toggle_characterization_collapse_open(self, callbacks):
        new_open, icon = callbacks["toggle_characterization_collapse"](1, False)
        assert new_open is True
        assert icon == "▾ "

    def test_toggle_characterization_collapse_close(self, callbacks):
        new_open, icon = callbacks["toggle_characterization_collapse"](1, True)
        assert new_open is False
        assert icon == "▸ "

    def test_update_sequence_grid_toggled_on(self, callbacks):
        fig, style = callbacks["update_sequence_grid"](SEQ_DATASET, ["on"], "light")
        assert isinstance(fig, go.Figure)
        assert style["display"] == "block"

    def test_update_sequence_grid_off(self, callbacks):
        fig, style = callbacks["update_sequence_grid"](None, [], "light")
        assert style == {"display": "none"}


class TestFigureBuilderGuardBranches:
    def test_plot_normalized_series_empty(self, panel):
        fig = panel._plot_normalized_series([], "light", "small_multiples", "Title")
        assert isinstance(fig, go.Figure)

    def test_create_windows_plot_no_data(self, panel):
        fig = panel._create_windows_plot({}, "light")
        assert isinstance(fig, go.Figure)

    def test_create_windows_plot_skips_bad_window(self, panel):
        seq = {
            "windows_X": [[[0.1, 0.2], [0.3, 0.4]], []],  # window 1 empty -> skipped
            "windows_dt": [[0.1, 0.1], []],
            "feature_labels": ["a", "b"],
        }
        fig = panel._create_windows_plot(seq, "light", signal=0, windows=[0, 1])
        assert isinstance(fig, go.Figure)

    def test_create_target_plot_no_target(self, panel):
        fig = panel._create_target_plot({}, "light", 0)
        assert isinstance(fig, go.Figure)

    def test_create_hist_plot_none(self, panel):
        fig = panel._create_hist_plot(None, "light", "title", "#000000")
        assert isinstance(fig, go.Figure)

    def test_create_hist_plot_empty_counts(self, panel):
        fig = panel._create_hist_plot({"edges": [], "counts": []}, "light", "title", "#000000")
        assert isinstance(fig, go.Figure)

    def test_create_grid_plot_no_windows(self, panel):
        fig = panel._create_grid_plot({}, "light")
        assert isinstance(fig, go.Figure)

    def test_create_grid_plot_first_window_invalid(self, panel):
        fig = panel._create_grid_plot({"windows_X": [[]]}, "light")
        assert isinstance(fig, go.Figure)

    def test_create_grid_plot_skips_bad_row(self, panel):
        seq = {
            "windows_X": [[[0.1, 0.2], [0.3, 0.4]], []],  # row 1 empty -> skipped
            "windows_dt": [[0.1, 0.1], []],
            "feature_labels": ["a", "b"],
        }
        fig = panel._create_grid_plot(seq, "light")
        assert isinstance(fig, go.Figure)
