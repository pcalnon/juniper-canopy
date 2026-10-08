#!/usr/bin/env python
"""Guards on cascor's replay-control result that the F-CANOPY-056 suite cannot see.

``test_f056_replay_control_envelope.py`` drives the measured session, whose
``state_summary()`` always carries ``paused`` and an integer ``time_index``,
and whose ``snapshot_id`` matches the session already stored. Its only failed
control is a play. Those fixtures stay green if:

* a Stop that cascor refused still clears the player (the clear moved ahead of
  the success check);
* a boolean ``time_index`` is stored as ``1`` (``bool`` is an ``int``);
* a numeric string index is coerced, or a float is rounded instead of truncated;
* a result that omits ``paused`` starts playback;
* a falsy ``fsm_state`` blanks the badge, or a truthy one is dropped;
* a flat session adopts the result's different ``snapshot_id``;
* an empty or non-dict ``result`` is treated as authoritative and the user's
  change is dropped.

Production behavior is unchanged. These tests call the registered
``dispatch_control`` for the failed Stop and ``_merge_session`` for the
mapping guards.
"""

import copy
from unittest.mock import MagicMock, patch

import dash
import pytest

from frontend.components.replay_player_panel import ReplayPlayerPanel

MEASURED_SESSION = {
    "length": 12,
    "time_index": 0,
    "speed": 1.0,
    "paused": True,
    "range": {"start": 0, "end": 12},
    "weights_available": True,
    "weight_sampling": {"strategy": "adaptive", "num_samples": 3, "sample_epochs": [10000, 10, 11]},
}

MEASURED_DATA_BLOCK = {
    "snapshot_id": "snap-measured",
    "fsm_state": "Replaying",
    "operation": "replay",
    "time_index": {"current": 5, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
    "session": MEASURED_SESSION,
}

SNAP = MEASURED_DATA_BLOCK["snapshot_id"]
WINDOW = {"start_epoch": 0, "end_epoch": 12}


def _summary(**overrides):
    summary = dict(MEASURED_SESSION, snapshot_id=SNAP)
    summary.update(overrides)
    return summary


def _envelope(action, result, **extra):
    data = {"snapshot_id": SNAP, "operation": "replay_control", "action": action, "result": result}
    data.update(extra)
    return {"status": "success", "data": data, "meta": {"timestamp": "2026-10-03T00:00:00Z", "version": "0.6.0"}}


def _flat_session():
    return {
        "snapshot_id": SNAP,
        "fsm_state": "Replaying",
        "time_index": {"current": 5, "snapshot_window": dict(WINDOW)},
        "speed": 1.0,
        "playing": False,
    }


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
    panel = ReplayPlayerPanel({"api_base_url": "http://localhost:8050"}, component_id="rp-result-guards")
    panel.register_callbacks(app)
    captured["panel"] = panel
    return captured


def _merge(action, params, body, session=None):
    stored = copy.deepcopy(MEASURED_DATA_BLOCK if session is None else session)
    before = copy.deepcopy(stored)
    new = ReplayPlayerPanel._merge_session(stored, action, params, body)
    assert stored == before, "the caller's session store must not be mutated"
    return new


@pytest.mark.unit
class TestFailedStopKeepsTheSession:
    def test_a_refused_stop_leaves_the_session_and_says_why(self, callbacks):
        """A 200 is what clears the player. A refusal, even one whose body says stopped, must not."""
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        envelope = _envelope("stop", {"status": "stopped", "snapshot_id": SNAP}, fsm_state="STOPPED")
        refused = {"success": False, "error": "cascor still replaying", "data": envelope}
        with patch.object(callbacks["panel"], "_invoke_replay_control", return_value=refused):
            status, new_session = callbacks["dispatch_control"]({"action": "stop", "params": {}}, session)
        assert new_session is dash.no_update
        assert session["snapshot_id"] == SNAP
        assert session["fsm_state"] == "Replaying"
        assert session["time_index"]["current"] == 5
        assert "cascor still replaying" in str(status)


@pytest.mark.unit
class TestControlResultMapping:
    @pytest.mark.parametrize("raw", [True, False])
    def test_a_bool_time_index_is_not_an_index(self, callbacks, raw):
        body = _envelope("seek", _summary(time_index=raw))
        new = _merge("seek", {"time_index": 4}, body)
        assert new["time_index"]["current"] == 5, "True is an int, and it must not become the scrubber index 1"
        assert new["time_index"]["snapshot_window"] == WINDOW
        assert callbacks["render_session"](new)[6] == 5

    def test_a_numeric_string_time_index_is_not_an_index(self, callbacks):
        body = _envelope("seek", _summary(time_index="7"))
        new = _merge("seek", {"time_index": 4}, body)
        assert new["time_index"]["current"] == 5
        assert callbacks["render_session"](new)[6] == 5

    def test_a_float_time_index_is_truncated(self, callbacks):
        body = _envelope("seek", _summary(time_index=7.9))
        new = _merge("seek", {"time_index": 4}, body)
        assert new["time_index"]["current"] == 7
        assert new["time_index"]["snapshot_window"] == WINDOW
        assert callbacks["render_session"](new)[6] == 7

    def test_a_result_that_omits_paused_does_not_start_playback(self):
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        session["playing"] = False
        result = _summary(speed=3.0)
        del result["paused"]
        new = _merge("speed", {"value": 3.0}, _envelope("speed", result), session=session)
        assert new["playing"] is False
        assert new["session"]["speed"] == 3.0

    @pytest.mark.parametrize("fsm", ["", 0, False, None])
    def test_a_falsy_fsm_state_does_not_blank_the_badge(self, fsm):
        new = _merge("play", {}, _envelope("play", _summary(paused=False), fsm_state=fsm))
        assert new["fsm_state"] == "Replaying"

    def test_a_truthy_fsm_state_is_written(self):
        new = _merge("play", {}, _envelope("play", _summary(paused=False), fsm_state="Playing"))
        assert new["fsm_state"] == "Playing"
        assert new["playing"] is True

    def test_a_flat_session_keeps_its_snapshot_id(self):
        result = _summary(speed=2.0, time_index=6)
        result["snapshot_id"] = "snap-other"
        new = _merge("speed", {"value": 2.0}, _envelope("speed", result), session=_flat_session())
        assert new["snapshot_id"] == SNAP
        assert new["speed"] == 2.0
        assert new["time_index"] == {"current": 6, "snapshot_window": WINDOW}

    def test_an_empty_result_still_applies_the_local_change(self):
        new = _merge("speed", {"value": 4.0}, _envelope("speed", {}))
        assert new["session"]["speed"] == 4.0
        for key in ("status", "data", "meta", "result", "action"):
            assert key not in new

    @pytest.mark.parametrize("result", [[1, 2], "ok"])
    def test_a_non_dict_result_still_applies_the_local_change(self, result):
        new = _merge("speed", {"value": 4.0}, _envelope("speed", result))
        assert new["session"]["speed"] == 4.0
        assert new["playing"] is True
        for key in ("status", "data", "meta", "result"):
            assert key not in new
