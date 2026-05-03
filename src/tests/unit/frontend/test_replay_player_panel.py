#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# File Name:     test_replay_player_panel.py
# Author:        Paul Calnon
# Date:          2026-05-02
# License:       MIT License
# Description:   Unit tests for ReplayPlayerPanel (CAN-015f, Phase 6E B-6).
#####################################################################
"""Unit tests for the replay player UI panel."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

from frontend.components.replay_player_panel import (  # noqa: E402
    SPEED_DEFAULT,
    SPEED_MAX,
    SPEED_MIN,
    ReplayPlayerPanel,
)


@pytest.fixture
def panel():
    return ReplayPlayerPanel({"api_base_url": "http://localhost:8050"}, component_id="rp-test")


@pytest.fixture
def session():
    return {
        "snapshot_id": "snap_001",
        "operation": "replay",
        "fsm_state": "Replaying",
        "time_index": {
            "default": "start",
            "snapshot_window": {"start_epoch": 0, "end_epoch": 100},
            "current": 25,
        },
        "speed": 1.0,
        "playing": False,
    }


# =============================================================================
# Layout
# =============================================================================


class TestLayout:
    def test_layout_renders(self, panel):
        layout = panel.get_layout()
        layout_str = str(layout)
        assert "Replay Player" in layout_str
        assert "rp-test-play-btn" in layout_str
        assert "rp-test-pause-btn" in layout_str
        assert "rp-test-stop-btn" in layout_str
        assert "rp-test-scrubber" in layout_str
        assert "rp-test-speed" in layout_str
        assert "rp-test-range" in layout_str

    def test_layout_has_session_store(self, panel):
        layout_str = str(panel.get_layout())
        assert "replay-player-session" in layout_str

    def test_layout_has_idle_state(self, panel):
        layout_str = str(panel.get_layout())
        assert "No active replay session" in layout_str


# =============================================================================
# Window helpers
# =============================================================================


class TestSessionHelpers:
    def test_session_window_unified_shape(self, panel, session):
        start, end = panel._session_window(session)
        assert (start, end) == (0, 100)

    def test_session_window_legacy_shape(self, panel):
        legacy = {"length": 50, "window": {"start_epoch": 0, "end_epoch": 49}}
        assert panel._session_window(legacy) == (0, 49)

    def test_session_window_none(self, panel):
        assert panel._session_window(None) == (0, 1)

    def test_session_window_clamps_negative(self, panel):
        bad = {"time_index": {"snapshot_window": {"start_epoch": 10, "end_epoch": 5}}}
        start, end = panel._session_window(bad)
        assert end == start

    def test_current_index_from_unified(self, panel, session):
        assert panel._session_current_index(session) == 25

    def test_current_index_default(self, panel):
        assert panel._session_current_index({"snapshot_id": "x"}) == 0

    def test_current_index_handles_garbage(self, panel):
        assert panel._session_current_index({"time_index": {"current": "foo"}}) == 0


# =============================================================================
# Backend invocation
# =============================================================================


class TestInvokeReplayControl:
    def test_no_session_id_rejected(self, panel):
        result = panel._invoke_replay_control("", "play")
        assert result["success"] is False
        assert "no active" in result["error"].lower()

    def test_unknown_action_rejected(self, panel):
        result = panel._invoke_replay_control("snap_001", "delete")
        assert result["success"] is False
        assert "delete" in result["error"]

    def test_play_action_posts_correct_body(self, panel):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"action": "play", "fsm_state": "Replaying"}
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            result = panel._invoke_replay_control("snap_001", "play")

        assert result["success"] is True
        assert captured["url"].endswith("/api/v1/snapshots/snap_001/replay/control")
        assert captured["json"] == {"action": "play"}

    def test_seek_passes_time_index(self, panel):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            panel._invoke_replay_control("snap_001", "seek", time_index=42)

        assert captured["json"] == {"action": "seek", "time_index": 42}

    def test_speed_passes_value(self, panel):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            panel._invoke_replay_control("snap_001", "speed", value=-2.5)

        assert captured["json"] == {"action": "speed", "value": -2.5}

    def test_range_passes_start_end(self, panel):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            panel._invoke_replay_control("snap_001", "range", start=10, end=80)

        assert captured["json"] == {"action": "range", "start": 10, "end": 80}

    def test_drops_none_params(self, panel):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["json"] = json
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {}
            return mock_resp

        with patch("requests.post", side_effect=fake_post):
            panel._invoke_replay_control("snap_001", "play", time_index=None)

        assert captured["json"] == {"action": "play"}

    def test_501_demo_mode(self, panel):
        mock_resp = MagicMock()
        mock_resp.status_code = 501
        mock_resp.json.return_value = {"detail": "live cascor required"}
        with patch("requests.post", return_value=mock_resp):
            result = panel._invoke_replay_control("snap_001", "play")
        assert result["success"] is False
        assert "cascor" in result["error"].lower()

    def test_409_conflict(self, panel):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "no replay active"}
        with patch("requests.post", return_value=mock_resp):
            result = panel._invoke_replay_control("snap_001", "stop")
        assert result["success"] is False
        assert "replay" in result["error"].lower()

    def test_timeout_handled(self, panel):
        import requests

        with patch("requests.post", side_effect=requests.exceptions.Timeout):
            result = panel._invoke_replay_control("snap_001", "play")
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_connection_error_handled(self, panel):
        import requests

        with patch("requests.post", side_effect=requests.exceptions.ConnectionError):
            result = panel._invoke_replay_control("snap_001", "play")
        assert result["success"] is False
        assert "unavailable" in result["error"].lower()


# =============================================================================
# Session merge
# =============================================================================


class TestMergeSession:
    def test_play_marks_playing(self, panel, session):
        new = panel._merge_session(session, "play", {}, None)
        assert new["playing"] is True

    def test_pause_marks_not_playing(self, panel, session):
        new = panel._merge_session(session, "pause", {}, None)
        assert new["playing"] is False

    def test_stop_clears_session(self, panel, session):
        new = panel._merge_session(session, "stop", {}, None)
        assert new["snapshot_id"] is None

    def test_seek_updates_time_index(self, panel, session):
        new = panel._merge_session(session, "seek", {"time_index": 80}, None)
        assert new["time_index"]["current"] == 80

    def test_speed_zero_pauses(self, panel, session):
        new = panel._merge_session(session, "speed", {"value": 0}, None)
        assert new["speed"] == 0
        assert new["playing"] is False

    def test_speed_negative_keeps_playing(self, panel, session):
        new = panel._merge_session(session, "speed", {"value": -2.0}, None)
        assert new["speed"] == -2.0
        assert new["playing"] is True

    def test_range_updates_window(self, panel, session):
        new = panel._merge_session(session, "range", {"start": 20, "end": 70}, None)
        assert new["range"] == [20, 70]

    def test_backend_response_overrides(self, panel, session):
        backend_data = {"fsm_state": "Stopped", "time_index": {"current": 999}}
        new = panel._merge_session(session, "play", {}, backend_data)
        assert new["fsm_state"] == "Stopped"
        assert new["time_index"]["current"] == 999


# =============================================================================
# Speed slider config sanity
# =============================================================================


class TestSpeedConfig:
    def test_speed_range_bidirectional(self):
        assert SPEED_MIN < 0 < SPEED_MAX

    def test_speed_default_forward(self):
        assert SPEED_DEFAULT > 0

    def test_speed_min_max_symmetry(self):
        # Bidirectional design — magnitude should match.
        assert abs(SPEED_MIN) == SPEED_MAX


# =============================================================================
# CAN-015g (g-4): replay weight buffer + V2 indicator wiring
# =============================================================================


class TestReplayWeightBufferLayout:
    """Layout-level assertions for the new weight-buffer Store + indicators."""

    def test_layout_has_replay_weight_buffer_store(self, panel):
        layout_str = str(panel.get_layout())
        assert "replay-weight-buffer" in layout_str

    def test_layout_has_weight_drain_interval(self, panel):
        layout_str = str(panel.get_layout())
        assert "weight-drain" in layout_str

    def test_layout_has_weights_badge(self, panel):
        layout_str = str(panel.get_layout())
        assert "weights-badge" in layout_str

    def test_layout_has_last_sample_readout(self, panel):
        layout_str = str(panel.get_layout())
        assert "last-sample-readout" in layout_str

    def test_replay_weight_buffer_max_is_documented(self):
        from frontend.components.replay_player_panel import REPLAY_WEIGHT_BUFFER_MAX

        # Cap exists and is non-trivial. Plan claimed 1000 but g-4
        # tuned down — assert anything in the [10, 500] sanity band.
        assert 10 <= REPLAY_WEIGHT_BUFFER_MAX <= 500


class TestRenderSessionWeightsBadge:
    """``render_session`` callback should drive the V2 weights-available badge."""

    @pytest.fixture
    def registered_panel(self, panel):
        from unittest.mock import MagicMock

        app = MagicMock()
        # Capture clientside_callback wiring without spinning up Dash.
        app.clientside_callback = MagicMock()
        app.callback = lambda *a, **kw: (lambda fn: fn)
        panel.register_callbacks(app)
        return panel

    def test_idle_session_hides_badge(self, registered_panel):
        result = registered_panel._cb_render_session(None)
        # Badge text and style are the last two outputs (g-4 added).
        badge_style = result[-1]
        assert badge_style == {"display": "none"}

    def test_v2_session_shows_v2_badge(self, registered_panel):
        session = {
            "snapshot_id": "snap_001",
            "fsm_state": "Replaying",
            "weights_available": True,
            "time_index": {"snapshot_window": {"start_epoch": 0, "end_epoch": 100}},
        }
        result = registered_panel._cb_render_session(session)
        badge_text = result[-2]
        badge_style = result[-1]
        assert "V2" in badge_text
        assert "weights" in badge_text.lower()
        assert badge_style.get("display") == "inline-block"

    def test_v1_session_shows_v1_badge(self, registered_panel):
        session = {
            "snapshot_id": "snap_001",
            "fsm_state": "Replaying",
            "weights_available": False,
            "time_index": {"snapshot_window": {"start_epoch": 0, "end_epoch": 100}},
        }
        result = registered_panel._cb_render_session(session)
        badge_text = result[-2]
        badge_style = result[-1]
        assert "V1" in badge_text or "metrics" in badge_text.lower()
        assert badge_style.get("display") == "inline-block"

    def test_clientside_callbacks_registered(self, panel):
        # The drain callback + last-sample readout are clientside.
        # Verify register_callbacks invoked clientside_callback at
        # least twice (drain + readout).
        from unittest.mock import MagicMock

        app = MagicMock()
        app.clientside_callback = MagicMock()
        app.callback = lambda *a, **kw: (lambda fn: fn)
        panel.register_callbacks(app)
        assert app.clientside_callback.call_count >= 2
