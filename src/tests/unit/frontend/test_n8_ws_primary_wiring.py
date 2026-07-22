"""N8 (training-runtime defects plan §4 I-1, posture O3+O1 / Q6): WS-primary
tiles/state with a liveness-gated poll fallback.

N1 un-gated the metrics/topology polls to defeat the sticky-flag starvation (a tab
that once saw a WS frame stopped polling forever). N8 takes the target step, split
across TWO callbacks per store to satisfy Dash's execution model:

- **O1 — liveness-gated REST poll** (``_update_metrics_store_handler`` /
  ``_fetch_training_state_handler``): fires on every interval tick (the interval is
  the SOLE trigger, so it can never be starved); reads the liveness signal as State;
  returns ``no_update`` while the stream is fresh, and re-engages the REST poll the
  instant it goes stale.
- **O3 — WS-primary append** (``_append_ws_metrics_store_handler`` /
  ``_append_ws_training_state_handler``): triggered ONLY by a WS-buffer change (a real
  frame arrived), so it is the sole writer of WS data and can never starve the store
  when the stream is quiet.

The load-bearing property is that the gate is a LIVE freshness signal, never a sticky
flag: fresh ⇒ poll skips REST; stale ⇒ poll resumes on the next tick; an empty/soured
path never wipes a populated store; history-analysis modes stay on REST.

Handler-level unit pins plus structural pins over the JS bridge and the dashboard
wiring (the assets/ JS and the layout are otherwise un-unit-covered — the same gate
class as ``test_phase_b_bridge.py``). The end-to-end browser behavior is pinned by
``tests/ui/test_ws_silent_poll_liveness.py``.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import dash
import pytest

_SRC_DIR = Path(__file__).resolve().parents[3]


def _dm():
    from frontend.dashboard_manager import DashboardManager

    dm = DashboardManager.__new__(DashboardManager)
    dm.logger = __import__("logging").getLogger("test")
    dm._api_base_url = "http://127.0.0.1:8050"
    return dm


# ─────────────────────────────────────────────────────────────────────────────
# Metrics store — O1 liveness-gated REST poll
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.unit
class TestMetricsStorePollLivenessGate:
    """``_update_metrics_store_handler`` — fires every tick; demoted while WS live,
    REST fallback while stale. The WS buffer is NOT one of its inputs (that would
    starve it — see the callback's Dash-model note); it only sees ``ws_live``."""

    def test_ws_live_window_mode_skips_rest(self):
        """Demoted: WS fresh in the window view → no_update, NO REST call (the append
        callback owns the store)."""
        dm = _dm()
        with patch("frontend.dashboard_manager.requests") as mock_requests:
            result = dm._update_metrics_store_handler(
                n=1,
                display_mode_state={"mode": "window", "window_size": 100},
                current_metrics=[{"epoch": 5}],
                trigger="fast-update-interval.n_intervals",
                ws_live=True,
            )
        assert result is dash.no_update
        mock_requests.get.assert_not_called()

    def test_ws_stale_falls_back_to_rest(self):
        """WS stale → the REST poll runs (the O1 fallback)."""
        dm = _dm()
        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 9, "error": 0.1}]
            result = dm._update_metrics_store_handler(
                n=1,
                display_mode_state={"mode": "window", "window_size": 100},
                current_metrics=[{"epoch": 5}],
                trigger="fast-update-interval.n_intervals",
                ws_live=False,
            )
        assert result == [{"epoch": 9, "error": 0.1}]
        mock_requests.get.assert_called_once()

    def test_full_mode_ignores_ws_live_and_polls(self):
        """History-analysis (``full``) mode is NOT demoted by a fresh WS stream: on a
        modulus tick it fetches the complete history via REST (Q6)."""
        from canopy_constants import DashboardConstants

        dm = _dm()
        tick = DashboardConstants.FULL_HISTORY_POLL_TICK_MODULUS
        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": [{"epoch": 1}]}
            result = dm._update_metrics_store_handler(
                n=tick,
                display_mode_state={"mode": "full"},
                trigger="fast-update-interval.n_intervals",
                ws_live=True,
            )
        assert result == [{"epoch": 1}]
        mock_requests.get.assert_called_once()
        assert "limit=0" in mock_requests.get.call_args[0][0]

    def test_gate_not_sticky_resumes_rest_when_stale(self):
        """ANTI-STICKY (the load-bearing pin): a live tick skips REST; the very next
        tick with the stream stale MUST poll REST. The N1-era sticky flag latched off
        forever — this gate resets on every tick from the live freshness signal."""
        dm = _dm()
        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 42, "error": 0.1}]

            r1 = dm._update_metrics_store_handler(
                display_mode_state={"mode": "window", "window_size": 100},
                current_metrics=[{"epoch": 5}],
                trigger="fast-update-interval.n_intervals",
                ws_live=True,
            )
            assert r1 is dash.no_update
            assert mock_requests.get.call_count == 0

            r2 = dm._update_metrics_store_handler(
                display_mode_state={"mode": "window", "window_size": 100},
                current_metrics=[{"epoch": 5}],
                trigger="fast-update-interval.n_intervals",
                ws_live=False,
            )
            assert r2 == [{"epoch": 42, "error": 0.1}]
            assert mock_requests.get.call_count == 1

    def test_empty_guard_preserved_on_stale_path(self):
        """The N1 empty-guard survives: a stale-path empty fetch with a populated
        store returns no_update (never wipes a completed run's charts)."""
        dm = _dm()
        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = {"history": []}
            result = dm._update_metrics_store_handler(n=1, current_metrics=[{"epoch": 7}], ws_live=False)
        assert result is dash.no_update

    def test_default_call_preserves_n1_rest_behavior(self):
        """Backward-compat: with no ws_live (every legacy caller), the handler is the
        N1 REST poll unchanged — the fallback is intact by default, not opt-in."""
        dm = _dm()
        with patch("frontend.dashboard_manager.requests") as mock_requests:
            mock_resp = mock_requests.get.return_value
            mock_resp.ok = True
            mock_resp.json.return_value = [{"epoch": 1, "error": 0.5}]
            result = dm._update_metrics_store_handler(n=1, display_mode_state={"mode": "window", "window_size": 100}, trigger="fast-update-interval.n_intervals")
        assert result == [{"epoch": 1, "error": 0.5}]
        mock_requests.get.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Metrics store — O3 WS-primary append
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.unit
class TestAppendWsMetricsStore:
    """``_append_ws_metrics_store_handler`` — accumulates drained WS metrics; runs
    only on a WS push, so it can never starve the store."""

    def test_appends_events_onto_store(self):
        dm = _dm()
        result = dm._append_ws_metrics_store_handler(
            ws_metrics_buffer={"events": [{"epoch": 6}, {"epoch": 7}]},
            display_mode_state={"mode": "window", "window_size": 100},
            current_metrics=[{"epoch": 5}],
        )
        assert result == [{"epoch": 5}, {"epoch": 6}, {"epoch": 7}]

    def test_accumulation_bounded_to_window(self):
        dm = _dm()
        events = [{"epoch": i} for i in range(10)]
        result = dm._append_ws_metrics_store_handler(
            ws_metrics_buffer={"events": events},
            display_mode_state={"mode": "window", "window_size": 3},
            current_metrics=[{"epoch": -1}],
        )
        assert result == [{"epoch": 7}, {"epoch": 8}, {"epoch": 9}]
        assert len(result) == 3

    def test_no_events_returns_no_update(self):
        dm = _dm()
        result = dm._append_ws_metrics_store_handler(ws_metrics_buffer={"events": []}, display_mode_state={"mode": "window"}, current_metrics=[{"epoch": 5}])
        assert result is dash.no_update

    def test_none_buffer_returns_no_update(self):
        dm = _dm()
        assert dm._append_ws_metrics_store_handler(ws_metrics_buffer=None, display_mode_state={"mode": "window"}, current_metrics=[]) is dash.no_update

    def test_full_mode_opts_out(self):
        """History-analysis mode ignores WS pushes (keeps the complete REST history)."""
        dm = _dm()
        result = dm._append_ws_metrics_store_handler(
            ws_metrics_buffer={"events": [{"epoch": 6}]},
            display_mode_state={"mode": "full"},
            current_metrics=[{"epoch": 5}],
        )
        assert result is dash.no_update

    def test_appends_onto_empty_store(self):
        dm = _dm()
        result = dm._append_ws_metrics_store_handler(
            ws_metrics_buffer={"events": [{"epoch": 1}]},
            display_mode_state={"mode": "window", "window_size": 100},
            current_metrics=None,
        )
        assert result == [{"epoch": 1}]


# ─────────────────────────────────────────────────────────────────────────────
# Training-state store — O1 liveness-gated REST poll + empty-guard
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.unit
class TestTrainingStatePollLivenessGate:
    """``_fetch_training_state_handler`` — fires every stats tick; demoted while WS
    live, REST fallback + empty-guard while stale."""

    def _panel(self):
        from frontend.components.metrics_panel import MetricsPanel

        return MetricsPanel({"max_data_points": 100}, component_id="test-panel")

    def test_ws_live_skips_rest(self):
        mp = self._panel()
        with patch("requests.get") as mock_get:
            result = mp._fetch_training_state_handler(ws_live=True, current_state={"status": "OLD"})
        assert result is dash.no_update
        mock_get.assert_not_called()

    def test_ws_stale_falls_back_to_rest(self):
        mp = self._panel()
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "RUNNING"}
            mock_get.return_value = mock_response
            result = mp._fetch_training_state_handler(ws_live=False, current_state={"status": "OLD"})
        assert result == {"status": "RUNNING"}
        mock_get.assert_called_once()

    def test_rest_empty_guard_on_exception_with_populated_store(self):
        mp = self._panel()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("boom")
            result = mp._fetch_training_state_handler(ws_live=False, current_state={"status": "OLD"})
        assert result is dash.no_update

    def test_rest_non_200_with_populated_store_preserved(self):
        mp = self._panel()
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_get.return_value = mock_response
            result = mp._fetch_training_state_handler(ws_live=False, current_state={"status": "OLD"})
        assert result is dash.no_update

    def test_rest_empty_store_returns_empty_dict(self):
        mp = self._panel()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("boom")
            result = mp._fetch_training_state_handler(ws_live=False, current_state=None)
        assert result == {}

    def test_gate_not_sticky_resumes_rest_when_stale(self):
        mp = self._panel()
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "FROM_REST"}
            mock_get.return_value = mock_response

            r1 = mp._fetch_training_state_handler(ws_live=True, current_state={"status": "OLD"})
            assert r1 is dash.no_update
            assert mock_get.call_count == 0

            r2 = mp._fetch_training_state_handler(ws_live=False, current_state={"status": "OLD"})
            assert r2 == {"status": "FROM_REST"}
            assert mock_get.call_count == 1

    def test_default_call_preserves_pre_n8_rest_behavior(self):
        from frontend.internal_api import internal_api_headers

        mp = self._panel()
        with patch("requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "RUNNING", "epoch": 25}
            mock_get.return_value = mock_response
            result = mp._fetch_training_state_handler()
        assert result == {"status": "RUNNING", "epoch": 25}
        mock_get.assert_called_once_with("http://127.0.0.1:8050/api/state", timeout=2, headers=internal_api_headers())


# ─────────────────────────────────────────────────────────────────────────────
# Training-state store — O3 WS-primary append + the unwrap helper
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.unit
class TestAppendWsTrainingState:
    """``_append_ws_training_state_handler`` — latest-only WS state; runs only on a
    WS push."""

    def _panel(self):
        from frontend.components.metrics_panel import MetricsPanel

        return MetricsPanel({"max_data_points": 100}, component_id="test-panel")

    def test_flat_state_returned(self):
        mp = self._panel()
        assert mp._append_ws_training_state_handler(ws_state_buffer={"status": "RUNNING", "current_epoch": 12}) == {"status": "RUNNING", "current_epoch": 12}

    def test_unwraps_nested_training_state(self):
        mp = self._panel()
        assert mp._append_ws_training_state_handler(ws_state_buffer={"action": "snapshot_restored", "training_state": {"status": "STOPPED"}}) == {"status": "STOPPED"}

    def test_bare_wrapper_returns_no_update(self):
        mp = self._panel()
        assert mp._append_ws_training_state_handler(ws_state_buffer={"action": "x", "snapshot_id": "s1"}) is dash.no_update

    def test_none_returns_no_update(self):
        mp = self._panel()
        assert mp._append_ws_training_state_handler(ws_state_buffer=None) is dash.no_update

    @pytest.mark.parametrize(
        "buf,expected",
        [
            ({"status": "RUNNING"}, {"status": "RUNNING"}),
            ({"phase": "output", "current_epoch": 3}, {"phase": "output", "current_epoch": 3}),
            ({"training_state": {"status": "X"}}, {"status": "X"}),
            ({"training_state": {}, "action": "y"}, None),
            ({"action": "y", "snapshot_id": "s"}, None),
            ({}, None),
            (None, None),
            ("not-a-dict", None),
        ],
    )
    def test_extract_ws_training_state(self, buf, expected):
        from frontend.components.metrics_panel import MetricsPanel

        assert MetricsPanel._extract_ws_training_state(buf) == expected


# ─────────────────────────────────────────────────────────────────────────────
# Structural pins: the JS bridge + the dashboard wiring (otherwise un-covered)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.unit
class TestBridgeJsWiring:
    """Structural gate over ws_dash_bridge.js — the frame-arrival clocks, the fixed
    ``state`` handler, and peekLiveness."""

    @pytest.fixture
    def bridge_js(self):
        return (_SRC_DIR / "frontend" / "assets" / "ws_dash_bridge.js").read_text(encoding="utf-8")

    def test_state_handler_uses_real_wire_type(self, bridge_js):
        """The server broadcasts training state as type ``state`` (never emitted the
        old ``state_change`` the dead handler listened on)."""
        assert 'window.cascorWS.on("state"' in bridge_js
        assert 'on("state_change"' not in bridge_js

    def test_metrics_frame_clock_stamped(self, bridge_js):
        assert "_lastMetricsFrameMs = Date.now()" in bridge_js

    def test_state_frame_clock_stamped(self, bridge_js):
        assert "_lastStateFrameMs = Date.now()" in bridge_js

    def test_peek_liveness_is_age_based_not_sticky(self, bridge_js):
        """peekLiveness reports an AGE (now − last-arrival) — an aging signal that can
        never latch live, the opposite of the retired sticky metricsReceived flag."""
        assert "peekLiveness" in bridge_js
        assert "now - this._lastMetricsFrameMs" in bridge_js
        assert "now - this._lastStateFrameMs" in bridge_js

    def test_raf_coalescer_invariant_preserved(self, bridge_js):
        """N8 must not disturb the GAP-WS-15 rAF invariant (only candidate_progress
        coalesces)."""
        assert bridge_js.count("window._juniperRafCoalescerEnabled === true") == 1


@pytest.mark.unit
class TestDashboardManagerWiring:
    """Structural gate over dashboard_manager.py — the re-created ws-state-buffer
    drain, the liveness store/callback, and the two-callback metrics split."""

    @pytest.fixture
    def dm_src(self):
        return (_SRC_DIR / "frontend" / "dashboard_manager.py").read_text(encoding="utf-8")

    def test_ws_state_buffer_store_recreated(self, dm_src):
        assert 'dcc.Store(id="ws-state-buffer"' in dm_src

    def test_ws_liveness_store_added(self, dm_src):
        assert 'dcc.Store(id="ws-liveness-store"' in dm_src

    def test_drain_state_callback_recreated(self, dm_src):
        assert "drainState()" in dm_src
        assert 'Output("ws-state-buffer", "data")' in dm_src

    def test_liveness_callback_wired(self, dm_src):
        assert "peekLiveness()" in dm_src
        assert 'Output("ws-liveness-store", "data")' in dm_src
        assert "WS_LIVENESS_WINDOW_MS" in dm_src

    def test_metrics_split_wiring(self, dm_src):
        """The append callback consumes ws-metrics-buffer via ``allow_duplicate`` and
        the poll reads liveness as State — the WS buffer must NOT be a poll Input
        (that re-creates the I-1 starvation)."""
        assert 'Output("metrics-panel-metrics-store", "data", allow_duplicate=True)' in dm_src
        assert 'Input("ws-metrics-buffer", "data")' in dm_src
        assert 'State("ws-liveness-store", "data")' in dm_src


@pytest.mark.unit
class TestMetricsPanelWiring:
    """Structural gate over metrics_panel.py — the training-state two-callback split."""

    @pytest.fixture
    def mp_src(self):
        return (_SRC_DIR / "frontend" / "components" / "metrics_panel.py").read_text(encoding="utf-8")

    def test_state_split_wiring(self, mp_src):
        assert "allow_duplicate=True" in mp_src
        assert 'Input("ws-state-buffer", "data")' in mp_src
        assert 'State("ws-liveness-store", "data")' in mp_src


@pytest.mark.unit
class TestLivenessWindowConstant:
    def test_window_is_positive_int(self):
        from canopy_constants import DashboardConstants

        assert isinstance(DashboardConstants.WS_LIVENESS_WINDOW_MS, int)
        assert DashboardConstants.WS_LIVENESS_WINDOW_MS > 0
