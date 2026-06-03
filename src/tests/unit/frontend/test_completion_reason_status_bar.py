#!/usr/bin/env python
"""Unit tests for the canopy status-bar ``completion_reason`` consumer (Issue #3 follow-up).

cascor #320 surfaces a ``grow_network`` ``completion_reason`` on ``/api/status``;
``service_backend`` carries it through and ``_build_unified_status_bar_content``
appends it to a *completed* run's status ("Completed — converged" vs
"Completed — stalled (0 new units)"). These pin the label mapping and the
augmentation (only when completed, only when the reason is present/known).
"""

from unittest.mock import Mock

import pytest

from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dashboard_manager():
    """Minimal DashboardManager for direct handler calls."""
    config = {"metrics_panel": {}, "network_visualizer": {}, "dataset_plotter": {}, "decision_boundary": {}}
    return DashboardManager(config)


def _status_response(**overrides):
    """A minimal completed-run /api/status payload, with overrides applied."""
    data = {
        "is_running": False,
        "is_paused": False,
        "completed": True,
        "failed": False,
        "phase": "idle",
        "current_epoch": 12,
        "hidden_units": 3,
        "max_hidden_units": 10,
    }
    data.update(overrides)
    resp = Mock()
    resp.json.return_value = data
    return resp


@pytest.mark.unit
class TestCompletionReasonLabel:
    """The static reason → operator-label mapping."""

    @pytest.mark.parametrize(
        "reason,label",
        [
            ("residual_collapsed", "converged"),
            ("below_threshold", "converged"),
            ("no_candidate", "stalled (0 new units)"),
            ("early_stopped", "early stopped"),
            ("max_iterations", "max iterations"),
        ],
    )
    def test_known_reasons(self, reason, label):
        assert DashboardManager._completion_reason_label(reason) == label

    @pytest.mark.parametrize("reason", [None, "", "something_new", "unknown"])
    def test_unknown_or_missing_returns_none(self, reason):
        assert DashboardManager._completion_reason_label(reason) is None


@pytest.mark.unit
class TestStatusBarCompletionReason:
    """_build_unified_status_bar_content appends the reason on a completed run only."""

    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("residual_collapsed", "Completed — converged"),
            ("below_threshold", "Completed — converged"),
            ("no_candidate", "Completed — stalled (0 new units)"),
            ("early_stopped", "Completed — early stopped"),
            ("max_iterations", "Completed — max iterations"),
        ],
    )
    def test_completed_appends_reason(self, dashboard_manager, reason, expected):
        result = dashboard_manager._build_unified_status_bar_content(_status_response(completion_reason=reason), latency_ms=50)
        assert result[3] == expected

    def test_completed_without_reason_stays_bare(self, dashboard_manager):
        """No completion_reason (e.g. cascor predates the field) → plain "Completed"."""
        result = dashboard_manager._build_unified_status_bar_content(_status_response(), latency_ms=50)
        assert result[3] == "Completed"

    def test_unknown_reason_stays_bare(self, dashboard_manager):
        """An unrecognized reason is not surfaced (forward-compatible)."""
        result = dashboard_manager._build_unified_status_bar_content(_status_response(completion_reason="brand_new_reason"), latency_ms=50)
        assert result[3] == "Completed"

    def test_non_completed_ignores_reason(self, dashboard_manager):
        """A stale completion_reason must not decorate a non-completed status."""
        result = dashboard_manager._build_unified_status_bar_content(
            _status_response(completed=False, is_running=True, completion_reason="no_candidate"),
            latency_ms=50,
        )
        assert result[3] == "Running"
