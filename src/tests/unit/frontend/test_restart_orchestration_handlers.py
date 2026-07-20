"""N3 (canopy training-runtime defects plan, I-6) — restart-orchestration handlers.

Direct-invocation tests for the ``_*_handler`` methods extracted from
``_setup_restart_orchestration_callbacks`` — the cold-swap confirm modal (Q3/Q4)
and the ``POST /api/train/restart`` outcome rendering. Mirrors the P2-6 live-switch
handler test pattern: ``DashboardManager.__new__`` skips ``__init__`` so we exercise
the branch logic without the full Dash app; ``requests`` is patched at the module.

The route-level orchestration contract lives in
``tests/integration/test_restart_orchestration_route.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dash
import pytest
import requests

from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


def _text(component):
    """Flatten a Dash/dbc component tree to its concatenated text."""
    if component is None:
        return ""
    if isinstance(component, str):
        return component
    if isinstance(component, (list, tuple)):
        return "".join(_text(c) for c in component)
    return _text(getattr(component, "children", None))


# ---------------------------------------------------------------------------
# _open_restart_confirm_modal_handler
# ---------------------------------------------------------------------------


class TestOpenRestartConfirmModalHandler:
    def test_no_clicks_is_all_no_update(self, dm):
        result = dm._open_restart_confirm_modal_handler(n_clicks=None)
        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_opens_with_summary_and_defaults_off(self, dm):
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"current_epoch": 12, "learning_rate": 0.01, "max_hidden_units": 100}
            is_open, summary, granular, toggle_value, collapse_open = dm._open_restart_confirm_modal_handler(n_clicks=1, dataset_type="xor", n_samples=300, noise=0.1, rotations=None, n_spirals=None)
        assert is_open is True
        # Q4: the start-fresh toggle resets to its default OFF and the granular
        # verify section is collapsed on every open.
        assert toggle_value is False
        assert collapse_open is False
        assert "xor" in _text(summary)
        assert "300" in _text(summary)
        # Q3 verify body carries the current engine params (best-effort read).
        assert "12" in _text(granular)
        assert "continue the current model" in _text(granular)

    def test_verify_body_degrades_when_status_unreachable(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("boom")):
            is_open, summary, granular, _, _ = dm._open_restart_confirm_modal_handler(n_clicks=1, dataset_type="moons")
        assert is_open is True
        # Still opens; the verify section notes the params are unavailable.
        assert "unavailable" in _text(granular).lower()

    def test_empty_dataset_selection_still_opens(self, dm):
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("boom")):
            is_open, summary, _, _, _ = dm._open_restart_confirm_modal_handler(n_clicks=1)
        assert is_open is True
        assert "staged change will be applied" in _text(summary)


# ---------------------------------------------------------------------------
# _execute_restart_handler
# ---------------------------------------------------------------------------


class TestExecuteRestartHandler:
    def test_no_clicks_is_all_no_update(self, dm):
        result = dm._execute_restart_handler(n_clicks=None, start_fresh=False)
        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_success_closes_modal_and_banner(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True, "was_active": True, "start_fresh": False, "steps": [{"step": "start", "ok": True}]}
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert modal is False
        assert progress is False
        assert banner is False  # closed on success
        assert outcome.color == "success"
        assert "Restart succeeded" in _text(outcome)

    def test_forwards_start_fresh_true(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True, "was_active": False, "start_fresh": True, "steps": []}
            dm._execute_restart_handler(n_clicks=1, start_fresh=True)
        args, kwargs = mock_post.call_args
        assert args[0].endswith("/api/train/restart")
        assert kwargs["json"] == {"start_fresh": True, "reset": True}

    def test_failure_keeps_banner_open_and_surfaces_detail(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 409
            mock_post.return_value.json.return_value = {"success": False, "message": "Training already in progress"}
            mock_post.return_value.text = "Training already in progress"
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert modal is False
        assert progress is False
        assert banner is dash.no_update  # banner stays open on failure
        assert outcome.color == "danger"
        assert "Training already in progress" in _text(outcome)

    def test_timeout_504_marks_retriable(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 504
            mock_post.return_value.json.return_value = {"success": False, "message": "Timed out waiting for the current run to stop", "retriable": True}
            mock_post.return_value.text = ""
            _, _, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert banner is dash.no_update
        assert outcome.color == "danger"
        assert "retry" in _text(outcome).lower()

    def test_request_exception_surfaces_unreachable(self, dm):
        with patch("frontend.dashboard_manager.requests.post", side_effect=requests.RequestException("connection refused")):
            modal, progress, outcome, banner = dm._execute_restart_handler(n_clicks=1, start_fresh=False)
        assert modal is False
        assert banner is dash.no_update
        assert outcome.color == "danger"
        assert "unreachable" in _text(outcome).lower()


# ---------------------------------------------------------------------------
# _render_restart_outcome
# ---------------------------------------------------------------------------


class TestRenderRestartOutcome:
    def test_success_continue_mentions_continued_model(self):
        alert = DashboardManager._render_restart_outcome({"success": True, "was_active": True, "start_fresh": False}, ok=True)
        assert alert.color == "success"
        text = _text(alert)
        assert "Stopped the running model" in text
        assert "continued the current model" in text

    def test_success_start_fresh_mentions_fresh_model(self):
        alert = DashboardManager._render_restart_outcome({"success": True, "was_active": False, "start_fresh": True}, ok=True)
        assert alert.color == "success"
        assert "fresh model" in _text(alert)

    def test_success_instant_complete_is_truthful(self):
        # Folded finding 2 — an epoch-0 run must read as "converged immediately",
        # not as a frozen dashboard.
        alert = DashboardManager._render_restart_outcome({"success": True, "was_active": False, "start_fresh": True, "instant_complete": True}, ok=True)
        assert "converged immediately" in _text(alert)

    def test_failure_carries_message(self):
        alert = DashboardManager._render_restart_outcome({"message": "boom"}, ok=False)
        assert alert.color == "danger"
        assert "boom" in _text(alert)

    def test_failure_retriable_notes_staged_change(self):
        alert = DashboardManager._render_restart_outcome({"message": "timed out", "retriable": True}, ok=False)
        assert "still staged" in _text(alert)
