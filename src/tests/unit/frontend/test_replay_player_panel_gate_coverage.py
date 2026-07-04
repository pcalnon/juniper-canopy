#!/usr/bin/env python
"""Per-file coverage-gate tests for ``frontend.components.replay_player_panel``.

Exercises the callback closures the baseline suite leaves uncovered:
``queue_control`` (control-to-request translation, driven with a faked
``dash.callback_context``), ``dispatch_control`` (backend dispatch +
Store reflection), the swap-events callback wrapper, plus the
``_invoke_replay_control`` generic-error branch and the status helpers.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest
from dash import html

from frontend.components.replay_player_panel import SPEED_DEFAULT, ReplayPlayerPanel


class _FakeCtx:
    __slots__ = ("triggered",)

    def __init__(self, triggered):
        self.triggered = triggered


@pytest.fixture
def panel():
    return ReplayPlayerPanel({"api_base_url": "http://localhost:8050"}, component_id="rp-gate")


@pytest.fixture
def registered(panel):
    """Register callbacks against a Dash-free stub app (clientside supported)."""
    app = MagicMock()
    app.clientside_callback = MagicMock()
    app.callback = lambda *a, **kw: (lambda fn: fn)
    panel.register_callbacks(app)
    return panel


def _session():
    return {"snapshot_id": "snap_001", "fsm_state": "Replaying", "speed": 1.0}


def _trigger(prop_id, value):
    return _FakeCtx([{"prop_id": prop_id, "value": value}])


class TestInvokeReplayControlGenericError:
    def test_unhandled_status_uses_detail(self, panel):
        resp = MagicMock(status_code=500, text="err")
        resp.json.return_value = {"detail": "internal blow-up"}
        with patch("requests.post", return_value=resp):
            result = panel._invoke_replay_control("snap_001", "play")
        assert result["success"] is False
        assert "internal blow-up" in result["error"]

    def test_unhandled_status_empty_text_falls_back_to_code(self, panel):
        resp = MagicMock(status_code=500, text="")
        with patch("requests.post", return_value=resp):
            result = panel._invoke_replay_control("snap_001", "play")
        assert result["success"] is False
        assert "500" in result["error"]


class TestSessionCurrentIndexNone:
    def test_none_session_returns_zero(self, panel):
        assert panel._session_current_index(None) == 0


class TestQueueControl:
    def test_no_trigger_no_update(self, registered):
        with patch("dash.callback_context", _FakeCtx([])):
            result = registered._cb_queue_control(1, 0, 0, 0, 1.0, [0, 1], _session())
        assert result is dash.no_update

    def test_no_session_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-play-btn.n_clicks", 1)):
            result = registered._cb_queue_control(1, 0, 0, 0, 1.0, [0, 1], None)
        assert result is dash.no_update

    def test_play_action(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-play-btn.n_clicks", 1)):
            result = registered._cb_queue_control(1, 0, 0, 0, 1.0, [0, 1], _session())
        assert result == {"action": "play", "ts": 1}

    def test_play_zero_clicks_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-play-btn.n_clicks", 0)):
            result = registered._cb_queue_control(0, 0, 0, 0, 1.0, [0, 1], _session())
        assert result is dash.no_update

    def test_pause_action(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-pause-btn.n_clicks", 2)):
            result = registered._cb_queue_control(0, 2, 0, 0, 1.0, [0, 1], _session())
        assert result == {"action": "pause", "ts": 2}

    def test_pause_zero_clicks_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-pause-btn.n_clicks", 0)):
            result = registered._cb_queue_control(0, 0, 0, 0, 1.0, [0, 1], _session())
        assert result is dash.no_update

    def test_stop_action(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-stop-btn.n_clicks", 3)):
            result = registered._cb_queue_control(0, 0, 3, 0, 1.0, [0, 1], _session())
        assert result == {"action": "stop", "ts": 3}

    def test_stop_zero_clicks_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-stop-btn.n_clicks", 0)):
            result = registered._cb_queue_control(0, 0, 0, 0, 1.0, [0, 1], _session())
        assert result is dash.no_update

    def test_scrubber_seek(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-scrubber.value", 7)):
            result = registered._cb_queue_control(0, 0, 0, 7, 1.0, [0, 1], _session())
        assert result == {"action": "seek", "params": {"time_index": 7}}

    def test_scrubber_none_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-scrubber.value", None)):
            result = registered._cb_queue_control(0, 0, 0, None, 1.0, [0, 1], _session())
        assert result is dash.no_update

    def test_speed_change(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-speed.value", -2.5)):
            result = registered._cb_queue_control(0, 0, 0, 0, -2.5, [0, 1], _session())
        assert result == {"action": "speed", "params": {"value": -2.5}}

    def test_speed_none_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-speed.value", None)):
            result = registered._cb_queue_control(0, 0, 0, 0, None, [0, 1], _session())
        assert result is dash.no_update

    def test_range_change(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-range.value", [2, 8])):
            result = registered._cb_queue_control(0, 0, 0, 0, 1.0, [2, 8], _session())
        assert result == {"action": "range", "params": {"start": 2, "end": 8}}

    def test_range_bad_length_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-range.value", [2])):
            result = registered._cb_queue_control(0, 0, 0, 0, 1.0, [2], _session())
        assert result is dash.no_update

    def test_unknown_prop_no_update(self, registered):
        with patch("dash.callback_context", _trigger("rp-gate-mystery.value", 1)):
            result = registered._cb_queue_control(0, 0, 0, 0, 1.0, [0, 1], _session())
        assert result is dash.no_update


class TestDispatchControl:
    def test_empty_trigger_no_update(self, registered):
        status, session = registered._cb_dispatch_control(None, _session())
        assert status is dash.no_update
        assert session is dash.no_update

    def test_no_session_error(self, registered):
        status, session = registered._cb_dispatch_control({"action": "play"}, None)
        assert isinstance(status, html.Div)
        assert session is dash.no_update

    def test_backend_failure_surfaced(self, registered, panel):
        with patch.object(panel, "_invoke_replay_control", return_value={"success": False, "error": "no live cascor"}):
            status, session = registered._cb_dispatch_control({"action": "play"}, _session())
        assert isinstance(status, html.Div)
        assert "no live cascor" in str(status)
        assert session is dash.no_update

    def test_success_merges_session(self, registered, panel):
        with patch.object(panel, "_invoke_replay_control", return_value={"success": True, "data": {"fsm_state": "Playing"}}):
            status, session = registered._cb_dispatch_control({"action": "play", "params": {}}, _session())
        assert isinstance(status, html.Div)
        assert session["fsm_state"] == "Playing"


class TestSwapEventsCallback:
    def test_callback_delegates_to_handler(self, registered):
        figure, count = registered._cb_render_swap_events_graph(None, None)
        assert count == "0 events"
        assert "data" in figure

    def test_callback_with_live_events(self, registered):
        live = {"events": [{"timestamp": "2026-01-01", "before_cfg": {"dataset_type": "a"}, "after_cfg": {"dataset_type": "b"}}]}
        figure, count = registered._cb_render_swap_events_graph(live, None)
        assert "1" in count
        assert figure["data"]


class TestStatusHelpers:
    def test_error_status_builds_div(self, panel):
        result = panel._error_status("something failed")
        assert isinstance(result, html.Div)
        assert "something failed" in str(result)

    def test_success_status_known_action(self, panel):
        result = panel._success_status("play")
        assert isinstance(result, html.Div)
        assert "Playing" in str(result)

    def test_success_status_unknown_action_uses_raw(self, panel):
        result = panel._success_status("weird")
        assert "weird" in str(result)
