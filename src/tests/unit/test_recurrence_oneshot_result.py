#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_recurrence_oneshot_result.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-06-23
# Last Modified: 2026-06-23
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   A1-iii-b2 tests: the MetricsPanel one-shot regression result
#                view — _render_model_class_metrics (surface toggle) and
#                _build_oneshot_result (regression metrics card / spinner).
#####################################################################
"""A1-iii-b2 unit tests (juniper-canopy #368).

For a one-shot (recurrence / LMU) model the metrics panel hides the classification surface
(accuracy cards + per-epoch plots) and shows a regression result card (R² / RMSE / MSE / MAE
/ Loss) — never an accuracy/percentage readout. While the fit runs (no metrics yet) a spinner
placeholder is shown.
"""

import pytest


@pytest.mark.unit
class TestOneShotResultView:
    @pytest.fixture(scope="class")
    def mp(self):
        from frontend.dashboard_manager import DashboardManager

        return DashboardManager({}).metrics_panel

    # --- surface toggle ---

    def test_live_shows_classification_hides_result(self, mp):
        result_children, result_style, cards_style, loss_style, acc_style = mp._render_model_class_metrics("live", [])
        assert result_style == {"display": "none"}  # result card hidden
        assert cards_style.get("display") == "flex"  # classification cards visible
        assert loss_style.get("display") != "none" and acc_style.get("display") != "none"
        assert result_children == []

    def test_one_shot_hides_classification_shows_result(self, mp):
        result_children, result_style, cards_style, loss_style, acc_style = mp._render_model_class_metrics("one_shot", [{"r2": 0.9, "loss": 0.01}])
        assert result_style.get("display") == "block"  # result card shown
        assert cards_style.get("display") == "none"  # classification cards hidden
        assert loss_style.get("display") == "none" and acc_style.get("display") == "none"
        assert result_children is not None and result_children != []

    # --- result card builder ---

    def test_empty_metrics_shows_spinner_placeholder(self, mp):
        text = str(mp._build_oneshot_result([]))
        assert "Awaiting" in text  # spinner + "Awaiting … fit result"
        assert "Spinner" in text

    def test_renders_regression_metrics(self, mp):
        text = str(mp._build_oneshot_result([{"r2": 0.9612, "mse": 0.02, "rmse": 0.1414, "mae": 0.1, "loss": 0.02}]))
        assert "R²" in text  # regression label, not "Accuracy"
        assert "0.9612" in text  # r2 as a plain float
        assert "96.12%" not in text  # NOT a percentage (regression-generic)
        assert "RMSE" in text and "0.1414" in text

    def test_missing_metric_renders_dashes(self, mp):
        text = str(mp._build_oneshot_result([{"r2": 0.9}]))  # mse/rmse/mae/loss absent
        assert "0.9000" in text  # r2 formatted
        assert "--" in text  # absent metrics fall back to '--'

    def test_uses_last_point(self, mp):
        # one-shot history is a single point, but be robust if more arrive — use the latest.
        text = str(mp._build_oneshot_result([{"r2": 0.10}, {"r2": 0.95}]))
        assert "0.9500" in text and "0.1000" not in text
