"""P2-6 (Issue #3) — Unit tests for Live Dataset Switch handler methods.

Direct-invocation tests for the seven ``_handler`` methods refactored
out of ``_setup_live_dataset_switch_callbacks`` in P2-6. The handlers
encode the Dash callback logic (gate, modal flow, POST + outcome,
cancel, status mirror) as pure Python so each branch is exercisable
without spinning up the Dash app.

Mirrors the established pattern from ``test_meta_parameters_handlers.py``:
``DashboardManager.__new__(DashboardManager)`` skips ``__init__`` so we
don't need to wire up the full app graph for unit tests; we just patch
the few attributes the handlers actually touch (``logger``,
``_api_base_url`` for ``_api_url()``).

The route-level contract (canopy → cascor proxy) is exercised separately
in ``tests/integration/test_live_dataset_swap_routes.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dash
import dash_bootstrap_components as dbc
import pytest
import requests

from frontend.dashboard_manager import DashboardManager


@pytest.fixture
def dm():
    """DashboardManager with the minimum surface the live-switch handlers need.

    ``_api_url`` resolves against a stable test host so URL assertions
    in the mock-call args are predictable. ``logger`` is a MagicMock so
    the handlers' ``self.logger.warning(...)`` / ``info(...)`` calls
    don't blow up.
    """
    manager = DashboardManager.__new__(DashboardManager)
    manager.logger = MagicMock()
    manager._api_base_url = "http://test.local"
    return manager


# ---------------------------------------------------------------------------
# 1. _update_training_status_store_handler
# ---------------------------------------------------------------------------


class TestUpdateTrainingStatusStoreHandler:
    """Mirrors ``/api/status`` payload into the ``training-status-store``
    so the gate callback has fresh data without re-polling."""

    def test_200_response_returns_is_running_and_phase(self, dm):
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"is_running": True, "phase": "training"}
            result = dm._update_training_status_store_handler(n_intervals=1)
        assert result == {"is_running": True, "phase": "training"}

    def test_200_response_with_missing_fields_falls_back_to_safe_defaults(self, dm):
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {}
            result = dm._update_training_status_store_handler(n_intervals=1)
        # Missing ``is_running`` → False (F2.5 safe default — gate stays
        # closed if we can't confirm training is running).
        assert result == {"is_running": False, "phase": "idle"}

    def test_non_200_response_returns_no_update(self, dm):
        """Backend hiccup must not blow away a previously-good store value.
        ``dash.no_update`` is the Dash idiom for "leave the current value
        alone"."""
        with patch("frontend.dashboard_manager.requests.get") as mock_get:
            mock_get.return_value.status_code = 503
            result = dm._update_training_status_store_handler(n_intervals=1)
        assert result is dash.no_update

    def test_request_exception_returns_no_update(self, dm):
        """Network failure same as non-200 — leave the prior store value."""
        with patch("frontend.dashboard_manager.requests.get", side_effect=requests.RequestException("connection refused")):
            result = dm._update_training_status_store_handler(n_intervals=1)
        assert result is dash.no_update


# ---------------------------------------------------------------------------
# 2. _gate_live_switch_button_handler
# ---------------------------------------------------------------------------


class TestGateLiveSwitchButtonHandler:
    """Disable Live Switch button unless BOTH stores agree:
    experimental_functions=True AND is_running=True (F2.3 + F2.5)."""

    def test_both_off_returns_disabled_true(self, dm):
        assert dm._gate_live_switch_button_handler(flags={"experimental_functions": False}, status={"is_running": False}) is True

    def test_flag_off_running_returns_disabled_true(self, dm):
        assert dm._gate_live_switch_button_handler(flags={"experimental_functions": False}, status={"is_running": True}) is True

    def test_flag_on_not_running_returns_disabled_true(self, dm):
        assert dm._gate_live_switch_button_handler(flags={"experimental_functions": True}, status={"is_running": False}) is True

    def test_both_on_returns_disabled_false(self, dm):
        """The one path that enables the button — both stores must agree."""
        assert dm._gate_live_switch_button_handler(flags={"experimental_functions": True}, status={"is_running": True}) is False

    def test_none_stores_return_disabled_true(self, dm):
        """Empty / missing store data must default to disabled. Avoids a
        brief enable-window during page mount before the stores populate."""
        assert dm._gate_live_switch_button_handler(flags=None, status=None) is True


# ---------------------------------------------------------------------------
# 3. _open_live_switch_modal_handler
# ---------------------------------------------------------------------------


class TestOpenLiveSwitchModalHandler:
    """Open the warning modal + populate the read-only summary from the
    sidebar State values (Q3 hybrid — "here's what we're about to swap to")."""

    def test_no_click_returns_no_update(self, dm):
        result = dm._open_live_switch_modal_handler(n_clicks=None)
        assert result == (dash.no_update, dash.no_update)

    def test_zero_clicks_returns_no_update(self, dm):
        """A zero click count is the initial-callback case (despite our
        prevent_initial_call=True the handler defends anyway)."""
        result = dm._open_live_switch_modal_handler(n_clicks=0)
        assert result == (dash.no_update, dash.no_update)

    def test_all_inputs_populated_renders_full_summary(self, dm):
        is_open, rows = dm._open_live_switch_modal_handler(
            n_clicks=1,
            dataset_type="moons",
            n_samples=200,
            noise=0.05,
            n_spirals=2,
            rotations=2.5,
        )
        assert is_open is True
        # 5 inputs populated → 5 rows.
        assert len(rows) == 5
        # Each row is a ListGroupItem with [Strong("Label: "), Span("value")].
        # Check the human-readable labels make it through verbatim.
        # The exact composition of dbc components is brittle to walk, so we
        # render to JSON and assert the strings are present in the right rows.
        labels = []
        values = []
        for row in rows:
            kids = row.children
            labels.append(kids[0].children)
            values.append(kids[1].children)
        assert labels == ["Dataset type: ", "Samples: ", "Noise: ", "Spirals: ", "Spiral rotations: "]
        assert values == ["moons", "200", "0.05", "2", "2.5"]

    def test_partial_inputs_skips_none_rows(self, dm):
        """Only populated values get a summary row. Sidebar inputs the user
        hasn't touched come through as ``None`` and must NOT pollute the
        modal with "None" rows."""
        is_open, rows = dm._open_live_switch_modal_handler(
            n_clicks=1,
            dataset_type="moons",
            n_samples=None,
            noise=0.05,
            n_spirals=None,
            rotations=None,
        )
        assert is_open is True
        assert len(rows) == 2
        labels = [row.children[0].children for row in rows]
        assert labels == ["Dataset type: ", "Noise: "]

    def test_all_none_inputs_shows_warning_placeholder(self, dm):
        """No sidebar inputs populated → modal still opens (so the user
        sees the warning) with a single warning-colored ListGroupItem
        explaining the missing config."""
        is_open, rows = dm._open_live_switch_modal_handler(n_clicks=1, dataset_type=None, n_samples=None, noise=None, n_spirals=None, rotations=None)
        assert is_open is True
        assert len(rows) == 1
        # The single row is a warning-colored ListGroupItem with Italic text.
        item = rows[0]
        assert item.color == "warning"

    def test_numeric_values_render_as_strings(self, dm):
        """Floats and ints both render via ``str(...)``. Pins the format
        in case the modal layout changes (e.g., switches to f-strings)."""
        _, rows = dm._open_live_switch_modal_handler(n_clicks=1, dataset_type="spirals", n_samples=200, noise=0.05, n_spirals=2, rotations=2.5)
        # Samples row's value is "200" (str of int), Noise is "0.05" (str of float).
        samples_value = rows[1].children[1].children
        noise_value = rows[2].children[1].children
        assert samples_value == "200"
        assert noise_value == "0.05"


# ---------------------------------------------------------------------------
# 4. _close_live_switch_modal_on_fallback_handler
# ---------------------------------------------------------------------------


class TestCloseLiveSwitchModalOnFallbackHandler:
    """ "Return to Stop & Restart" closes the modal — minimal Q2
    interpretation. Deferred active-interpretation items are captured in
    ``notes/PHASE_2_P2_5_FOLLOWUPS_2026-05-15.md``."""

    def test_click_returns_false(self, dm):
        assert dm._close_live_switch_modal_on_fallback_handler(n_clicks=1) is False

    def test_no_click_returns_no_update(self, dm):
        assert dm._close_live_switch_modal_on_fallback_handler(n_clicks=None) is dash.no_update


# ---------------------------------------------------------------------------
# 5. _accept_live_switch_handler
# ---------------------------------------------------------------------------


class TestAcceptLiveSwitchHandler:
    """The 4-output handler that POSTs to ``/api/live_dataset_swap`` and
    reconciles the UI to the response. Outputs: modal_open, progress_open,
    outcome_alert, in_flight_store_data."""

    def test_no_click_returns_no_update_quadruple(self, dm):
        result = dm._accept_live_switch_handler(n_clicks=None, dataset_type="moons")
        assert result == (dash.no_update, dash.no_update, dash.no_update, dash.no_update)

    def test_success_status_swapped_returns_success_alert(self, dm):
        """Cascor swap completed normally → success Alert naming the
        pre-swap snapshot id."""
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"data": {"status": "swapped", "pre_swap_snapshot_id": "snap_20260515T120000Z"}}
            modal_open, progress_open, outcome, in_flight = dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons", n_samples=200, noise=0.05, n_spirals=2, rotations=2.5)
        assert modal_open is False
        assert progress_open is False
        assert in_flight == {"in_flight": False}
        # Success outcome: green alert mentioning the snapshot id.
        assert isinstance(outcome, dbc.Alert)
        assert outcome.color == "success"
        # The snapshot id appears in the children (which is a list).
        flattened = " ".join(str(c.children) if hasattr(c, "children") else str(c) for c in outcome.children)
        assert "snap_20260515T120000Z" in flattened

    def test_success_status_cancelled_returns_info_alert(self, dm):
        """Cascor P2-1b cancel path: POST returns 200 with status=cancelled
        → info alert "swap cancelled"."""
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"data": {"status": "cancelled"}}
            _, _, outcome, _ = dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons")
        assert isinstance(outcome, dbc.Alert)
        assert outcome.color == "info"
        # Body text mentions "cancelled".
        assert "cancelled" in str(outcome.children).lower()

    def test_502_returns_danger_alert_with_verbatim_error(self, dm):
        """Spec §4.3: "failure shows the server error verbatim". The
        cascor error string is passed through into the alert body."""
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 502
            mock_post.return_value.text = "Backend rejected live swap: HTTP 409 — swap already in progress"
            _, _, outcome, _ = dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons")
        assert isinstance(outcome, dbc.Alert)
        assert outcome.color == "danger"
        assert "swap already in progress" in str(outcome.children)

    def test_500_returns_danger_alert(self, dm):
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = "Internal server error"
            _, _, outcome, _ = dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons")
        assert outcome.color == "danger"
        assert "Internal server error" in str(outcome.children)

    def test_request_exception_returns_backend_unreachable_alert(self, dm):
        with patch("frontend.dashboard_manager.requests.post", side_effect=requests.RequestException("connection refused")):
            _, _, outcome, in_flight = dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons")
        assert outcome.color == "danger"
        assert "Backend unreachable" in str(outcome.children)
        assert "connection refused" in str(outcome.children)
        # In-flight always clears on POST resolution (success OR failure).
        assert in_flight == {"in_flight": False}

    def test_drops_none_payload_fields(self, dm):
        """Sidebar inputs the user didn't touch come through as ``None``;
        the handler MUST filter them out so the POST body doesn't shadow
        cascor's current values with None."""
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"data": {"status": "swapped"}}
            dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons", n_samples=None, noise=None, n_spirals=None, rotations=None)
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"] == {"nn_dataset_type": "moons"}

    def test_success_without_snapshot_id_renders_na(self, dm):
        """Cascor's response shape always includes ``pre_swap_snapshot_id``
        (P2-3), but defensively handle the absence — fall back to 'n/a'
        in the success alert."""
        with patch("frontend.dashboard_manager.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"data": {"status": "swapped"}}
            _, _, outcome, _ = dm._accept_live_switch_handler(n_clicks=1, dataset_type="moons")
        assert outcome.color == "success"
        flattened = " ".join(str(c.children) if hasattr(c, "children") else str(c) for c in outcome.children)
        assert "n/a" in flattened


# ---------------------------------------------------------------------------
# 6. _open_progress_alert_on_accept_handler
# ---------------------------------------------------------------------------


class TestOpenProgressAlertOnAcceptHandler:
    """Open the progress alert + flip in_flight=True the moment Accept
    is clicked. Split from the Accept POST handler so the spinner shows
    before the POST returns (5–30s)."""

    def test_click_returns_open_and_in_flight(self, dm):
        assert dm._open_progress_alert_on_accept_handler(n_clicks=1) == (True, {"in_flight": True})

    def test_no_click_returns_no_update(self, dm):
        assert dm._open_progress_alert_on_accept_handler(n_clicks=None) == (dash.no_update, dash.no_update)


# ---------------------------------------------------------------------------
# 7. _cancel_live_switch_handler
# ---------------------------------------------------------------------------


class TestCancelLiveSwitchHandler:
    """DELETE ``/api/live_dataset_swap`` to cancel an in-flight swap.

    Success (200) returns ``no_update`` — the actual "swap cancelled"
    alert is rendered by ``_accept_live_switch_handler`` when its POST
    returns with ``status="cancelled"``. Avoiding double-rendering.
    """

    def test_no_click_returns_no_update(self, dm):
        assert dm._cancel_live_switch_handler(n_clicks=None) is dash.no_update

    def test_200_returns_no_update(self, dm):
        with patch("frontend.dashboard_manager.requests.delete") as mock_delete:
            mock_delete.return_value.status_code = 200
            result = dm._cancel_live_switch_handler(n_clicks=1)
        assert result is dash.no_update

    def test_502_returns_warning_alert(self, dm):
        with patch("frontend.dashboard_manager.requests.delete") as mock_delete:
            mock_delete.return_value.status_code = 502
            mock_delete.return_value.text = "Backend rejected cancel: HTTP 404 — no swap in progress"
            result = dm._cancel_live_switch_handler(n_clicks=1)
        assert isinstance(result, dbc.Alert)
        assert result.color == "warning"
        assert "no swap in progress" in str(result.children)

    def test_request_exception_returns_warning_alert(self, dm):
        with patch("frontend.dashboard_manager.requests.delete", side_effect=requests.RequestException("network down")):
            result = dm._cancel_live_switch_handler(n_clicks=1)
        assert result.color == "warning"
        assert "Cancel failed" in str(result.children)
        assert "network down" in str(result.children)
