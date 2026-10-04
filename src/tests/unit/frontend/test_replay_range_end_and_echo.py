#!/usr/bin/env python
"""The replay player's index space against cascor: the range end, the window end, and render echoes.

Follow-ups to F-CANOPY-059 and F-CANOPY-056, from juniper-ml
``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md``.

1. **The range end.** cascor's ``set_range`` restricts playback to ``[start, end)``, and
   ``state_summary()`` serves that exclusive ``end``. The range slider is inclusive. canopy sent
   the slider's upper value as ``end`` and showed cascor's ``end`` as the upper value, so a chosen
   range never played its last frame.
2. **The window end.** cascor's ``snapshot_window.end_epoch`` is the history LENGTH
   (``_compute_snapshot_window``), while replay indexes run ``0 .. length - 1``. canopy used it as
   the last index, so the scrubber and the range slider each offered one position cascor clamps
   away.
3. **Render echoes.** ``render_session`` writes the scrubber, speed and range values on every
   session change, and those values are ``queue_control``'s Inputs. Each write therefore queued a
   control request whose result wrote the session again: the ``can015-replay-player-control-loop``
   exemption in ``test_f048_replay_cycle.py``, unreachable until F-059 and F-056 were fixed.
   ``queue_control`` now ignores a value equal to what the session already shows.

Verified against the parent commit (``3cc4fdb2``): 9 of these 13 fail there. Four pass there by
design: ``test_the_round_trip_shows_what_the_user_chose`` (the parent was wrong in both directions,
so its round trip agreed with itself; the two tests beside it pin each direction against cascor),
``test_a_snapshot_with_no_history_does_not_invert``, and ``TestUserChangesStillQueue``, which
guards that the echo check does not swallow a real change.
"""

import copy
from unittest.mock import MagicMock, patch

import dash
import pytest

from frontend.components.replay_player_panel import ReplayPlayerPanel

# ``data.session`` exactly as Phase 1 measured it off the running service (ledger, segment 7):
# 12 frames, indexes 0..11, full range {0, 12} with the end exclusive.
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
    "time_index": {"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
    "session": MEASURED_SESSION,
}

CID = "rp-echo"


class _Ctx:
    def __init__(self, triggered):
        self.triggered = triggered


@pytest.fixture
def cb():
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
    panel = ReplayPlayerPanel({"api_base_url": "http://localhost:8050"}, component_id=CID)
    panel.register_callbacks(app)
    captured["panel"] = panel
    return captured


def _queue(cb, session, *triggered):
    """Run the registered queue_control with ``triggered`` as ``[(prop, value), ...]``."""
    values = {"scrubber": 0, "speed": 1.0, "range": [0, 1]}
    for prop, value in triggered:
        values[prop] = value
    ctx = _Ctx([{"prop_id": f"{CID}-{prop}.value", "value": value} for prop, value in triggered])
    with patch("dash.callback_context", ctx):
        return cb["queue_control"](0, 0, 0, values["scrubber"], values["speed"], values["range"], session)


def _envelope(action, result):
    data = {"snapshot_id": "snap-measured", "operation": "replay_control", "action": action, "result": result}
    return {"status": "success", "data": data, "meta": {}}


def _dispatch(cb, trigger, session, result):
    with patch.object(cb["panel"], "_invoke_replay_control", return_value={"success": True, "data": _envelope(trigger["action"], result)}):
        return cb["dispatch_control"](trigger, session)[1]


@pytest.mark.unit
class TestRangeEndIsExclusive:
    def test_a_chosen_range_is_sent_with_an_exclusive_end(self, cb):
        trigger = _queue(cb, copy.deepcopy(MEASURED_DATA_BLOCK), ("range", [3, 8]))
        assert trigger == {"action": "range", "params": {"start": 3, "end": 9}}, "frame 8 must be inside cascor's [start, end)"

    def test_cascors_range_is_shown_inclusive(self, cb):
        block = dict(MEASURED_DATA_BLOCK, session=dict(MEASURED_SESSION, range={"start": 3, "end": 9}))
        out = cb["render_session"](block)
        assert out[9] == [3, 8]
        assert out[11] == "[3, 8]"

    def test_the_round_trip_shows_what_the_user_chose(self, cb):
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        trigger = _queue(cb, session, ("range", [3, 8]))
        # cascor's set_range stores the request as-is (within [0, length]) and echoes it in the summary.
        result = dict(MEASURED_SESSION, snapshot_id="snap-measured", range={"start": trigger["params"]["start"], "end": trigger["params"]["end"]})
        out = cb["render_session"](_dispatch(cb, trigger, session, result))
        assert out[9] == [3, 8]

    def test_the_last_frame_can_be_selected(self, cb):
        session = dict(MEASURED_DATA_BLOCK, session=dict(MEASURED_SESSION, range={"start": 3, "end": 9}))
        trigger = _queue(cb, session, ("range", [3, 11]))
        assert trigger["params"]["end"] == 12, "the full tail is end == length, which cascor accepts"


@pytest.mark.unit
class TestWindowEndIsALength:
    def test_the_sliders_stop_at_the_last_frame(self, cb):
        out = cb["render_session"](copy.deepcopy(MEASURED_DATA_BLOCK))
        assert (out[4], out[5]) == (0, 11), "scrubber min/max: 12 frames are indexes 0..11"
        assert (out[7], out[8]) == (0, 11), "range slider min/max"
        assert out[9] == [0, 11], "the full range"

    def test_a_snapshot_with_no_history_does_not_invert(self, cb):
        block = dict(MEASURED_DATA_BLOCK, time_index={"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 0}})
        assert cb["panel"]._session_window(block) == (0, 0)


@pytest.mark.unit
class TestRenderEchoesQueueNothing:
    @pytest.mark.parametrize("prop,index", [("scrubber", 6), ("speed", 12), ("range", 9)])
    def test_a_rendered_value_fed_back_queues_nothing(self, cb, prop, index):
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        out = cb["render_session"](session)
        assert _queue(cb, session, (prop, out[index])) is dash.no_update, f"render_session's {prop} write must not queue a control"

    def test_a_render_writing_all_three_queues_nothing(self, cb):
        session = dict(MEASURED_DATA_BLOCK, time_index={"current": 4, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}}, session=dict(MEASURED_SESSION, speed=-2.0, range={"start": 2, "end": 10}))
        out = cb["render_session"](session)
        assert _queue(cb, session, ("scrubber", out[6]), ("speed", out[12]), ("range", out[9])) is dash.no_update

    def test_the_loop_stops_after_one_control(self, cb):
        """A user seek, its result, the render, and the render's echo: the chain ends there."""
        session = copy.deepcopy(MEASURED_DATA_BLOCK)
        trigger = _queue(cb, session, ("scrubber", 5))
        assert trigger == {"action": "seek", "params": {"time_index": 5}}
        new = _dispatch(cb, trigger, session, dict(MEASURED_SESSION, snapshot_id="snap-measured", time_index=5))
        out = cb["render_session"](new)
        assert _queue(cb, new, ("scrubber", out[6]), ("speed", out[12]), ("range", out[9])) is dash.no_update


@pytest.mark.unit
class TestUserChangesStillQueue:
    def test_a_new_scrubber_value_seeks(self, cb):
        assert _queue(cb, copy.deepcopy(MEASURED_DATA_BLOCK), ("scrubber", 3)) == {"action": "seek", "params": {"time_index": 3}}

    def test_a_new_speed_is_sent(self, cb):
        assert _queue(cb, copy.deepcopy(MEASURED_DATA_BLOCK), ("speed", 4.0)) == {"action": "speed", "params": {"value": 4.0}}
