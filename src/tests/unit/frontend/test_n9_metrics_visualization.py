#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_n9_metrics_visualization.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-07-22
# Last Modified: 2026-07-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   N9 metrics-visualization overhaul regression tests
#####################################################################
"""Regression tests for N9 — the metrics-visualization overhaul.

Covers the juniper-ml training-runtime defects plan §4-U (U-2/U-3 presentation
+ U-4 display half) roadmap unit N9:

- the C7 scalar classification metrics (F1/precision/recall/ROC-AUC) rendered
  as bounded-[0,1] series on the classification (accuracy) plot, with honest
  null gaps (never zeros), sparse-legible markers, and the ``eval_metrics``
  metadata surfaced (average/split in the legend, undefined reasons annotated)
  without guessing;
- the U-2/U-3 presentation overhaul (percentage y-axis + bounds, palette);
- the **trace-index contract** between the Plotly figure builders and the WS
  bridge's ``extendTraces`` clientside callback — pinned on both sides because
  a name/index mismatch would silently corrupt WS appends;
- the C7 fields threaded through the adapter metric normalizers (REST path) and
  the demo emission (default demo surface).
"""

import pytest

from backend.cascor_service_adapter import CascorServiceAdapter
from frontend.components.metrics_panel import MetricsPanel

# Row keys / display names the C7 contract defines (cascor
# classification_metrics.METRIC_KEYS + the "Accuracy" trace 0).
SCALAR_KEYS = ("f1", "precision", "recall", "roc_auc")
SCALAR_NAMES = ("F1", "Precision", "Recall", "ROC-AUC")


def _row(epoch, phase, hidden_units, *, accuracy=None, val_accuracy=None, scalars=None, loss=0.4, eval_metrics=None):
    """Build a canopy-shaped metric row (nested ``metrics`` dict)."""
    metrics = {"loss": loss, "accuracy": accuracy, "val_accuracy": val_accuracy}
    if scalars:
        metrics.update(scalars)
    row = {"epoch": epoch, "phase": phase, "network_topology": {"hidden_units": hidden_units}, "metrics": metrics}
    if eval_metrics is not None:
        row["eval_metrics"] = eval_metrics
    return row


def _rows_with_scalars():
    return [
        _row(
            1,
            "output_training",
            0,
            accuracy=0.70,
            val_accuracy=0.68,
            scalars={"f1": 0.66, "precision": 0.71, "recall": 0.62, "roc_auc": 0.80},
            eval_metrics={"enabled": True, "average": "macro", "split": "validation", "n_samples": 200, "n_classes": 3, "undefined": {}},
        ),
        # Candidate-phase row: accuracy and every scalar are None → gaps.
        _row(2, "candidate_training", 1, accuracy=None, scalars={"f1": None, "precision": None, "recall": None, "roc_auc": None}),
        _row(
            3,
            "output_training",
            1,
            accuracy=0.82,
            val_accuracy=0.80,
            scalars={"f1": 0.79, "precision": 0.83, "recall": 0.76, "roc_auc": 0.88},
            eval_metrics={"enabled": True, "average": "macro", "split": "validation", "n_samples": 200, "n_classes": 3, "undefined": {}},
        ),
    ]


@pytest.fixture
def panel():
    return MetricsPanel({}, component_id="metrics-panel")


@pytest.mark.unit
class TestClassificationPlotSeries:
    """The classification (accuracy) plot renders accuracy + the C7 scalars."""

    def test_trace0_is_accuracy(self, panel):
        """Trace 0 MUST be Accuracy — the WS bridge extends it by index."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        assert fig.data[0].name == MetricsPanel.ACCURACY_TRACE_NAME == "Accuracy"

    def test_scalar_series_present_in_order(self, panel):
        """F1/Precision/Recall/ROC-AUC render after Accuracy, in spec order."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        names = [t.name for t in fig.data]
        assert names[:5] == ["Accuracy", "F1", "Precision", "Recall", "ROC-AUC"]
        assert "Validation Accuracy" in names

    def test_scalar_series_absent_when_all_null(self, panel):
        """A metric with no real value must NOT add a cluttering empty trace."""
        rows = [_row(1, "output", 0, accuracy=0.7, scalars={"f1": None, "precision": None, "recall": None, "roc_auc": None})]
        fig = panel._create_accuracy_plot(rows, "light")
        names = [t.name for t in fig.data]
        assert names == ["Accuracy"]
        for scalar_name in SCALAR_NAMES:
            assert scalar_name not in names

    def test_scalar_series_absent_when_field_missing(self, panel):
        """Pre-C7 rows (no scalar keys at all) render only Accuracy."""
        rows = [_row(1, "output", 0, accuracy=0.7)]
        fig = panel._create_accuracy_plot(rows, "light")
        assert [t.name for t in fig.data] == ["Accuracy"]

    def test_null_scalar_is_gap_not_zero(self, panel):
        """A None value becomes a gap (None y + connectgaps False), never 0.0."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        f1 = next(t for t in fig.data if t.name == "F1")
        assert list(f1.y) == [0.66, None, 0.79]
        assert f1.connectgaps is False
        # The candidate-phase gap must be a real None, not a zero.
        assert f1.y[1] is None

    def test_scalar_series_sparse_markers(self, panel):
        """lines+markers so sparse (every-25th-epoch) points stay legible."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        for scalar_name in SCALAR_NAMES:
            trace = next(t for t in fig.data if t.name == scalar_name)
            assert trace.mode == "lines+markers"

    def test_scalar_series_palette_matches_spec(self, panel):
        """Each series uses its SCALAR_SERIES color (coherent palette)."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        by_name = {t.name: t for t in fig.data}
        for _key, name, color in MetricsPanel.SCALAR_SERIES:
            assert by_name[name].line.color == color, f"{name} palette drift"
        assert by_name["Accuracy"].line.color == MetricsPanel.ACCURACY_COLOR

    def test_accuracy_gaps_through_candidate_phase(self, panel):
        """Accuracy itself keeps its candidate-phase gap (None), not a zero."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        accuracy = fig.data[0]
        assert list(accuracy.y) == [0.70, None, 0.82]
        assert accuracy.connectgaps is False


@pytest.mark.unit
class TestClassificationPlotPresentation:
    """U-2/U-3: axis bounds, percentage formatting, readability."""

    def test_yaxis_bounded_zero_to_one(self, panel):
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        assert tuple(fig.layout.yaxis.range) == (0, 1.0)

    def test_yaxis_percentage_tickformat(self, panel):
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        assert fig.layout.yaxis.tickformat == ".0%"

    def test_gridlines_enabled(self, panel):
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        assert fig.layout.yaxis.showgrid is True
        assert fig.layout.xaxis.showgrid is True

    def test_dark_theme_builds(self, panel):
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "dark")
        assert fig.layout.template is not None
        assert fig.layout.paper_bgcolor == "#242424"

    def test_title_reflects_classification_metrics(self, panel):
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        assert fig.layout.title.text == "Classification Metrics"

    def test_empty_data_still_builds(self, panel):
        """No rows → a valid figure (accuracy trace with empty arrays)."""
        fig = panel._create_accuracy_plot([], "light")
        assert fig.data[0].name == "Accuracy"


@pytest.mark.unit
class TestEvalMetricsMetadata:
    """The C7 eval_metrics block is surfaced, never guessed."""

    def test_average_split_in_legend_title(self, panel):
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        assert fig.layout.legend.title.text == "Metrics · macro · validation"

    def test_no_legend_title_when_eval_metrics_absent(self, panel):
        """No eval_metrics anywhere → the legend stays untitled (no guess)."""
        rows = [_row(1, "output", 0, accuracy=0.7, scalars={"f1": 0.6, "precision": 0.6, "recall": 0.6, "roc_auc": 0.7})]
        fig = panel._create_accuracy_plot(rows, "light")
        assert fig.layout.legend.title.text is None

    def test_undefined_reasons_annotated(self, panel):
        """A latest eval with undefined metrics gets an unobtrusive annotation."""
        rows = [
            _row(
                1,
                "output",
                0,
                accuracy=0.7,
                scalars={"f1": 0.6, "precision": 0.6, "recall": 0.6, "roc_auc": None},
                eval_metrics={"enabled": True, "average": "binary", "split": "training", "n_samples": 50, "n_classes": 2, "undefined": {"roc_auc": "single_class"}},
            )
        ]
        fig = panel._create_accuracy_plot(rows, "light")
        texts = [a.text for a in fig.layout.annotations]
        assert any("roc_auc: single_class" in t for t in texts)

    def test_latest_clean_eval_suppresses_stale_undefined(self, panel):
        """The annotation reflects the NEWEST eval block, not an older one."""
        rows = [
            _row(1, "output", 0, accuracy=0.7, scalars={"f1": 0.6, "precision": 0.6, "recall": 0.6, "roc_auc": None}, eval_metrics={"average": "binary", "split": "training", "undefined": {"roc_auc": "single_class"}}),
            _row(3, "output", 0, accuracy=0.8, scalars={"f1": 0.7, "precision": 0.7, "recall": 0.7, "roc_auc": 0.85}, eval_metrics={"average": "binary", "split": "training", "undefined": {}}),
        ]
        fig = panel._create_accuracy_plot(rows, "light")
        texts = [a.text for a in fig.layout.annotations]
        assert not any("undefined" in t for t in texts)

    def test_latest_eval_metrics_scans_newest_first(self):
        rows = [
            {"eval_metrics": {"average": "macro", "split": "training"}},
            {"eval_metrics": {}},  # empty — skipped
            {"eval_metrics": {"average": "binary", "split": "validation"}},
        ]
        assert MetricsPanel._latest_eval_metrics(rows)["split"] == "validation"

    def test_latest_eval_metrics_none_when_absent(self):
        assert MetricsPanel._latest_eval_metrics([{"metrics": {}}, {"epoch": 1}]) is None


@pytest.mark.unit
class TestLossPlotContract:
    """The loss plot keeps its own unbounded axis and trace-0 contract."""

    def test_loss_trace0_is_output_training(self, panel):
        fig = panel._create_loss_plot(_rows_with_scalars(), "light")
        assert fig.data[0].name == MetricsPanel.OUTPUT_TRACE_NAME == "Output Training"

    def test_loss_hovermode_allowed(self, panel):
        fig = panel._create_loss_plot(_rows_with_scalars(), "light")
        assert fig.layout.hovermode in ("closest", "x", "y", "x unified", "y unified")

    def test_loss_has_no_percentage_axis(self, panel):
        """Loss must NOT be clamped to [0, 1] — it is unbounded."""
        fig = panel._create_loss_plot(_rows_with_scalars(), "light")
        assert fig.layout.yaxis.tickformat != ".0%"


@pytest.mark.unit
class TestTraceIndexContract:
    """Pin the figure-builder trace names to the WS bridge extendTraces JS.

    A mismatch between the Plotly trace names and the ``findTraceIndex`` lookups
    silently mis-appends WS points to the wrong trace (or drops them). These
    tests bind BOTH sides to ``MetricsPanel.SCALAR_SERIES``.
    """

    @pytest.fixture
    def source(self):
        from pathlib import Path

        path = Path(__file__).resolve().parents[3] / "frontend" / "components" / "metrics_panel.py"
        return path.read_text(encoding="utf-8")

    def test_figure_names_are_the_spec_names(self, panel):
        """The figure builder emits exactly the SCALAR_SERIES display names."""
        fig = panel._create_accuracy_plot(_rows_with_scalars(), "light")
        names = [t.name for t in fig.data]
        for _key, name, _color in MetricsPanel.SCALAR_SERIES:
            assert name in names

    def test_bridge_reads_each_scalar_flat(self, source):
        """The WS clientside callback reads each scalar flat off the frame."""
        for key in SCALAR_KEYS:
            assert f"e.{key}" in source, f"WS bridge must read e.{key}"

    def test_bridge_looks_up_each_scalar_by_name(self, source):
        """Each SCALAR_SERIES display name is an extendTraces lookup target."""
        for _key, name, _color in MetricsPanel.SCALAR_SERIES:
            assert f'"{name}"' in source, f"WS bridge must reference trace name {name!r}"

    def test_bridge_scalar_series_share_epochs_axis(self, source):
        """Scalar extends share [epochs] with accuracy trace 0 (stay aligned)."""
        assert "{x: [epochs], y: [n9Series[s].v]}" in source
        assert "findTraceIndex(accEl, n9Series[s].n)" in source

    def test_bridge_accuracy_trace0_extended_by_index(self, source):
        """Accuracy trace 0 is still extended positionally ([0], 5000)."""
        assert "Plotly.extendTraces(accEl, {x: [epochs], y: [accuracies]}, [0], 5000)" in source

    def test_bridge_validation_overlays_preserved(self, source):
        """GAP-WS-14 validation overlays must survive the N9 changes."""
        assert '"Validation Loss"' in source
        assert '"Validation Accuracy"' in source
        assert "findTraceIndex" in source

    def test_bridge_scalar_reads_under_loss_gate(self, source):
        """Scalars are collected inside the loss push-gate (no length skew)."""
        # The scalar pushes sit between the accuracy push and the close of the
        # `if (loss !== undefined ...)` block.
        anchor = source.index("accuracies.push(acc")
        gate_close = source.index("}", anchor)
        gate_body = source[anchor:gate_close]
        for key in SCALAR_KEYS:
            assert f"{_js_array(key)}.push(" in gate_body, f"{key} push must be inside the loss gate"


def _js_array(key):
    return {"f1": "f1s", "precision": "precisions", "recall": "recalls", "roc_auc": "rocAucs"}[key]


@pytest.mark.unit
class TestAdapterNormalizerScalars:
    """The C7 scalars + eval_metrics thread through the metric normalizers."""

    def test_normalize_metric_carries_nested_scalars(self):
        entry = {"epoch": 5, "loss": 0.3, "accuracy": 0.8, "f1": 0.75, "precision": 0.79, "recall": 0.72, "roc_auc": 0.9, "eval_metrics": {"enabled": True, "average": "macro", "split": "validation", "undefined": {}}}
        out = CascorServiceAdapter._normalize_metric(entry)
        for key in SCALAR_KEYS:
            assert out["metrics"][key] == entry[key]
        assert out["eval_metrics"] == entry["eval_metrics"]

    def test_to_dashboard_metric_end_to_end(self):
        """The full REST funnel (_to_dashboard_metric ∘ _normalize_metric)."""
        entry = {"epoch": 5, "loss": 0.3, "accuracy": 0.8, "f1": 0.75, "precision": 0.79, "recall": 0.72, "roc_auc": 0.9, "eval_metrics": {"average": "binary", "split": "training", "undefined": {"roc_auc": "single_class"}}}
        out = CascorServiceAdapter._to_dashboard_metric(CascorServiceAdapter._normalize_metric(entry))
        assert out["metrics"]["f1"] == 0.75
        assert out["metrics"]["roc_auc"] == 0.9
        assert out["eval_metrics"]["undefined"] == {"roc_auc": "single_class"}

    def test_scalars_nullable_when_absent(self):
        """Pre-C7 cascor (no scalar fields) → None, never KeyError."""
        out = CascorServiceAdapter._to_dashboard_metric(CascorServiceAdapter._normalize_metric({"epoch": 1, "loss": 0.5, "accuracy": 0.6}))
        for key in SCALAR_KEYS:
            assert out["metrics"][key] is None
        assert out["eval_metrics"] is None

    def test_normalized_rows_render_through_figure_builder(self, panel):
        """End-to-end: adapter-normalized rows drive the classification plot."""
        entries = [
            {"epoch": 1, "loss": 0.4, "accuracy": 0.7, "phase": "output_training", "f1": 0.66, "precision": 0.7, "recall": 0.62, "roc_auc": 0.8, "hidden_units": 0},
            {"epoch": 2, "loss": 0.3, "accuracy": 0.82, "phase": "output_training", "f1": 0.79, "precision": 0.83, "recall": 0.76, "roc_auc": 0.88, "hidden_units": 1},
        ]
        rows = [CascorServiceAdapter._to_dashboard_metric(CascorServiceAdapter._normalize_metric(e)) for e in entries]
        fig = panel._create_accuracy_plot(rows, "light")
        names = [t.name for t in fig.data]
        assert names[:5] == ["Accuracy", "F1", "Precision", "Recall", "ROC-AUC"]


@pytest.mark.unit
class TestDemoEmission:
    """The default demo surface emits the C7 scalars + eval_metrics."""

    import collections

    # class _FakePhase(collections.namedtuple("Phase", ["name"])):
    class _FakePhase(collections.namedtuple):  # noqa: B903
        def __init__(self, name):
            self.name = name

    def _demo(self):
        from demo_mode import DemoMode

        return DemoMode()

    def test_demo_row_carries_scalar_keys_and_eval_metrics(self):
        demo = self._demo()
        demo._emit_training_metrics()
        row = demo.metrics_history[-1]
        for key in SCALAR_KEYS:
            assert key in row["metrics"]
        assert isinstance(row["eval_metrics"], dict)
        for meta_key in ("enabled", "average", "split", "n_samples", "n_classes", "undefined"):
            assert meta_key in row["eval_metrics"]

    def test_demo_output_phase_emits_numeric_scalars(self):
        demo = self._demo()
        demo.state_machine.get_phase = lambda: self._FakePhase("OUTPUT")
        demo._emit_training_metrics()
        metrics = demo.metrics_history[-1]["metrics"]
        for key in SCALAR_KEYS:
            assert isinstance(metrics[key], float)
            assert 0.0 <= metrics[key] <= 1.0

    def test_demo_candidate_phase_emits_gaps(self):
        demo = self._demo()
        demo.state_machine.get_phase = lambda: self._FakePhase("CANDIDATE")
        demo._emit_training_metrics()
        metrics = demo.metrics_history[-1]["metrics"]
        for key in SCALAR_KEYS:
            assert metrics[key] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
