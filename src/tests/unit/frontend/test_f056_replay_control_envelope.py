#!/usr/bin/env python
"""F-CANOPY-056: against cascor the replay player dropped every control's result.

Finding: juniper-ml ``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md``
(F-CANOPY-056, P1; masked by F-CANOPY-059 until canopy#694).

canopy's ``/replay/control`` proxy passes cascor's envelope through unchanged:
``{status, data: {snapshot_id, operation, action, result, fsm_state?}, meta}``, where ``result`` is
the session's ``state_summary()`` (``stop`` returns ``{status, snapshot_id}`` and adds
``fsm_state``). ``_merge_session`` overlaid that envelope onto the session whenever it was
non-empty. None of the keys ``render_session`` reads sits at its top level, so play, pause, seek,
speed and range never reached the session, and a Stop, whose empty-body branch was never reached,
kept the session and the weight drain alive.

These tests build each envelope the way cascor's route does (``replay_control_endpoint`` and
``TrainingLifecycleManager.replay_control`` / ``stop_replay`` on cascor ``main``), drive the
REGISTERED ``dispatch_control`` callback, and render its output with the registered
``render_session``. The session they start from is the payload the E2E ledger's Phase 1 measured
live, which is also the F-CANOPY-059 tests' fixture.

Verified against the parent commit: every test in ``TestF056ControlResultsReachTheSession`` fails
there.
"""

import copy
from unittest.mock import MagicMock, patch

import pytest

from frontend.components.replay_player_panel import ReplayPlayerPanel

# ``data.session`` exactly as Phase 1 measured it off the running service (ledger, segment 7).
MEASURED_SESSION = {
    "length": 12,
    "time_index": 0,
    "speed": 1.0,
    "paused": True,
    "range": {"start": 0, "end": 12},
    "weights_available": True,
    "weight_sampling": {"strategy": "adaptive", "num_samples": 3, "sample_epochs": [10000, 10, 11]},
}

# The ``data`` block ``confirm_snapshot_op`` stores as the session.
MEASURED_DATA_BLOCK = {
    "snapshot_id": "snap-measured",
    "fsm_state": "Replaying",
    "operation": "replay",
    "time_index": {"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
    "session": MEASURED_SESSION,
}

SNAP = MEASURED_DATA_BLOCK["snapshot_id"]


def _summary(**overrides):
    """cascor's post-action ``state_summary()``, starting from the measured one."""
    summary = dict(MEASURED_SESSION, snapshot_id=SNAP)
    summary.update(overrides)
    return summary


def _envelope(action, result, **extra):
    """The body canopy's proxy returns: cascor's ``success_response`` envelope, unchanged."""
    data = {"snapshot_id": SNAP, "operation": "replay_control", "action": action, "result": result}
    data.update(extra)
    return {"status": "success", "data": data, "meta": {"timestamp": "2026-10-03T00:00:00Z", "version": "0.6.0"}}


@pytest.fixture
def callbacks():
    """The registered callbacks, captured from a Dash-free stub app, plus the panel."""
    captured = {}
    app = MagicMock()
    app.clientside_callback = MagicMock()

    def callback(*_args, **_kwargs):
        def register(fn):
            captured[fn.__name__] = fn
            return fn

        return register

    app.callback = callback
    panel = ReplayPlayerPanel({"api_base_url": "http://localhost:8050"}, component_id="rp-f056")
    panel.register_callbacks(app)
    captured["panel"] = panel
    return captured


def _dispatch(callbacks, action, envelope, params=None, session=None):
    """Run the registered dispatch_control with the proxy returning ``envelope``."""
    panel = callbacks["panel"]
    session = copy.deepcopy(MEASURED_DATA_BLOCK) if session is None else session
    trigger = {"action": action, "params": params or {}}
    with patch.object(panel, "_invoke_replay_control", return_value={"success": True, "data": envelope}):
        _status, new_session = callbacks["dispatch_control"](trigger, session)
    return new_session


@pytest.mark.unit
class TestF056ControlResultsReachTheSession:
    def test_stop_clears_the_session(self, callbacks):
        envelope = _envelope("stop", {"status": "stopped", "snapshot_id": SNAP}, fsm_state="STOPPED")
        new = _dispatch(callbacks, "stop", envelope)
        assert new == {"snapshot_id": None}, "cascor echoes the id under data/result; it must not keep the session"
        out = callbacks["render_session"](new)
        assert out[0] == {"display": "block"} and out[1] == {"display": "none"}, "a Stop must return the panel to idle"

    def test_stop_on_an_already_ended_session_clears_it(self, callbacks):
        envelope = _envelope("stop", {"status": "not_active"})
        assert _dispatch(callbacks, "stop", envelope) == {"snapshot_id": None}

    def test_play_marks_the_session_playing(self, callbacks):
        new = _dispatch(callbacks, "play", _envelope("play", _summary(paused=False)))
        assert new["playing"] is True
        assert new["session"]["paused"] is False

    def test_pause_marks_the_session_paused(self, callbacks):
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        session["playing"] = True
        new = _dispatch(callbacks, "pause", _envelope("pause", _summary(paused=True)), session=session)
        assert new["playing"] is False

    def test_seek_moves_the_scrubber(self, callbacks):
        new = _dispatch(callbacks, "seek", _envelope("seek", _summary(time_index=7)), params={"time_index": 7})
        assert new["time_index"]["current"] == 7
        assert new["time_index"]["snapshot_window"] == {"start_epoch": 0, "end_epoch": 12}, "the window must survive"
        out = callbacks["render_session"](new)
        assert out[6] == 7, "scrubber value"
        assert out[10] == "7 / 11", "epoch readout: 12 frames are indexes 0..11"

    def test_seek_shows_cascors_clamped_index_not_the_request(self, callbacks):
        new = _dispatch(callbacks, "seek", _envelope("seek", _summary(time_index=11)), params={"time_index": 40})
        assert callbacks["render_session"](new)[6] == 11

    def test_speed_reaches_the_slider(self, callbacks):
        new = _dispatch(callbacks, "speed", _envelope("speed", _summary(speed=-5.0, paused=False)), params={"value": -5.0})
        out = callbacks["render_session"](new)
        assert out[12] == -5.0, "speed slider value"
        assert out[13] == "-5×", "speed readout"

    def test_range_reaches_the_slider(self, callbacks):
        new = _dispatch(callbacks, "range", _envelope("range", _summary(range={"start": 3, "end": 9})), params={"start": 3, "end": 9})
        out = callbacks["render_session"](new)
        assert out[9] == [3, 8], "range slider value (cascor's end is exclusive)"
        assert out[11] == "[3, 8]", "range readout"

    def test_no_envelope_key_lands_on_the_session(self, callbacks):
        new = _dispatch(callbacks, "play", _envelope("play", _summary(paused=False)))
        for key in ("status", "data", "meta", "result", "action"):
            assert key not in new, f"envelope key {key!r} overlaid onto the session"
        assert new["snapshot_id"] == SNAP
        assert new["operation"] == "replay", "the stored operation must not become 'replay_control'"


@pytest.mark.unit
class TestF056MergeSessionShapes:
    def test_the_stored_session_is_not_mutated(self):
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        before = copy.deepcopy(session)
        ReplayPlayerPanel._merge_session(session, "speed", {"value": 2.0}, _envelope("speed", _summary(speed=2.0)))
        ReplayPlayerPanel._merge_session(session, "range", {"start": 1, "end": 5}, None)
        assert session == before

    def test_an_envelope_without_a_result_applies_the_intended_change(self):
        envelope = {"status": "success", "data": {"snapshot_id": SNAP, "operation": "replay_control"}, "meta": {}}
        new = ReplayPlayerPanel._merge_session(copy.deepcopy(MEASURED_DATA_BLOCK), "speed", {"value": 3.0}, envelope)
        assert new["session"]["speed"] == 3.0
        assert "status" not in new and "meta" not in new

    @pytest.mark.parametrize("action,params,key,expected", [("speed", {"value": 2.0}, "speed", 2.0), ("range", {"start": 2, "end": 8}, "range", {"start": 2, "end": 8})])
    def test_the_local_fallback_writes_where_render_reads(self, action, params, key, expected):
        new = ReplayPlayerPanel._merge_session(copy.deepcopy(MEASURED_DATA_BLOCK), action, params, None)
        assert new["session"][key] == expected, "a nested session's summary is what render_session reads"
        assert key not in new

    def test_a_flat_session_takes_the_result_without_its_integer_time_index(self):
        flat = {"snapshot_id": SNAP, "time_index": {"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}}, "speed": 1.0}
        new = ReplayPlayerPanel._merge_session(flat, "seek", {"time_index": 4}, _envelope("seek", _summary(time_index=4, speed=2.0)))
        assert new["time_index"]["current"] == 4
        assert new["time_index"]["snapshot_window"] == {"start_epoch": 0, "end_epoch": 12}
        assert new["speed"] == 2.0

    def test_a_flat_legacy_body_is_still_trusted(self):
        new = ReplayPlayerPanel._merge_session(copy.deepcopy(MEASURED_DATA_BLOCK), "play", {}, {"fsm_state": "Playing"})
        assert new["fsm_state"] == "Playing"

    @pytest.mark.parametrize("body", [None, {}, [], "ok"])
    def test_an_empty_or_non_dict_body_uses_the_local_fallback(self, body):
        new = ReplayPlayerPanel._merge_session(copy.deepcopy(MEASURED_DATA_BLOCK), "play", {}, body)
        assert new["playing"] is True
