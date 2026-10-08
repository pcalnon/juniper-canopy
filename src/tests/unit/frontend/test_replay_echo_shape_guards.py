#!/usr/bin/env python
"""Echo and index-space guards the measured-session suite cannot see.

``test_replay_range_end_and_echo.py`` drives the registered callbacks on the payload Phase 1
measured: a nested summary, speed 1.0 (which equals the slider default), an in-window dict range,
and a window that starts at epoch 0. Those fixtures stay green for four mistakes:

1. **Speed 0 is falsy.** The slider's 0 mark is pause. A truthiness check in the echo guard
   (``if not value``) swallows a move to 0 while the session is playing at any other speed.
   The measured speed is 1.0, and the "new speed" test sends 4.0, so 0 is never the value.
2. **A stale top-level summary.** F-CANOPY-015: ``speed`` and ``range`` live under
   ``data.session``. The measured block has no top-level speed, so a shallow
   ``session.get("speed", nested)`` falls through and the echo still matches. A stale top-level
   speed of 1.0, or a stale top-level range, disagrees with the nested summary. The nested
   integer ``time_index`` likewise disagrees with ``time_index.current``; ``_apply_control_result``
   keeps those two in lockstep, so the seek round-trip never separates them.
3. **A range cascor would clamp.** An exclusive ``end`` past the window is clamped before it is
   shown. In-window ranges make that clamp a no-op, so an equality check that compares the raw
   exclusive end restarts the control loop only for an out-of-window range.
4. **The legacy shapes.** A list ``range`` is already inclusive, and ``window.end_epoch`` is
   already the last index. The dict echo tests never feed a list back into ``queue_control``.
   The legacy window test calls the helper and never renders the scrubber. A window whose
   ``start_epoch`` is not 0 is untested: every fixture starts at 0, and the inverted-window test
   only asserts ``end == start``, which ``(0, 0)`` also satisfies.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest

from frontend.components.replay_player_panel import ReplayPlayerPanel

CID = "rp-guard"


class _Ctx:
    __slots__ = ("triggered",)

    def __init__(self, triggered):
        self.triggered = triggered


@pytest.fixture
def cb():
    """The registered callbacks, captured from a Dash-free stub app."""
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
    """Run queue_control with ``triggered`` as ``[(prop, value), ...]`` (first one wins)."""
    values = {"scrubber": 0, "speed": 1.0, "range": [0, 1]}
    for prop, value in triggered:
        values[prop] = value
    ctx = _Ctx([{"prop_id": f"{CID}-{prop}.value", "value": value} for prop, value in triggered])
    with patch("dash.callback_context", ctx):
        return cb["queue_control"](0, 0, 0, values["scrubber"], values["speed"], values["range"], session)


def _block(**overrides):
    """A cascor data block: 12 frames, indexes 0..11, nested summary."""
    session = {
        "length": 12,
        "time_index": 0,
        "speed": 1.0,
        "paused": True,
        "range": {"start": 0, "end": 12},
        "weights_available": True,
    }
    block = {
        "snapshot_id": "snap-guard",
        "fsm_state": "Replaying",
        "operation": "replay",
        "time_index": {"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
        "session": session,
    }
    block.update(overrides)
    return block


@pytest.mark.unit
class TestZeroSpeedIsARealChange:
    def test_moving_the_slider_to_zero_pauses(self, cb):
        session = _block()
        session["session"] = dict(session["session"], speed=4.0)
        assert _queue(cb, session, ("speed", 0)) == {"action": "speed", "params": {"value": 0.0}}

    def test_a_session_already_at_zero_echoes_nothing(self, cb):
        session = _block()
        session["session"] = dict(session["session"], speed=0.0, paused=True)
        out = cb["render_session"](session)
        assert out[12] == 0.0
        assert out[13] == "Paused (0×)"
        assert _queue(cb, session, ("speed", out[12])) is dash.no_update


@pytest.mark.unit
class TestStaleTopLevelDoesNotWin:
    def _session(self):
        """Nested summary disagrees with every stale top-level fallback."""
        return _block(
            speed=1.0,
            range=[0, 11],
            time_index={"current": 4, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
            session={
                "length": 12,
                "time_index": 0,
                "speed": -2.0,
                "paused": False,
                "range": {"start": 2, "end": 10},
                "weights_available": True,
            },
        )

    def test_the_render_follows_the_nested_summary_and_the_outer_index(self, cb):
        out = cb["render_session"](self._session())
        assert out[6] == 4, "scrubber reads time_index.current, not the nested integer 0"
        assert out[9] == [2, 9], "cascor's end 10 is exclusive; the stale top-level list is [0, 11]"
        assert out[12] == -2.0, "speed is the nested -2, not the stale top-level 1.0"

    def test_echoing_what_was_rendered_queues_nothing(self, cb):
        session = self._session()
        out = cb["render_session"](session)
        # One trigger each: queue_control reads only triggered[0], so a scrubber echo
        # must not hide a speed or range echo that compared the stale top-level value.
        assert _queue(cb, session, ("scrubber", out[6])) is dash.no_update
        assert _queue(cb, session, ("speed", out[12])) is dash.no_update
        assert _queue(cb, session, ("range", out[9])) is dash.no_update

    def test_the_stale_top_level_values_are_real_changes(self, cb):
        session = self._session()
        assert _queue(cb, session, ("speed", 1.0)) == {"action": "speed", "params": {"value": 1.0}}
        assert _queue(cb, session, ("range", [0, 11])) == {"action": "range", "params": {"start": 0, "end": 12}}
        assert _queue(cb, session, ("scrubber", 0)) == {"action": "seek", "params": {"time_index": 0}}


@pytest.mark.unit
class TestOutOfWindowRangeEchoesTheClamp:
    def test_the_clamped_slider_queues_nothing_and_the_raw_end_does_not(self, cb):
        session = _block()
        session["session"] = dict(session["session"], range={"start": 0, "end": 100})
        out = cb["render_session"](session)
        assert out[9] == [0, 11], "end 100 is past the 12-frame window, so the slider stops at 11"
        assert _queue(cb, session, ("range", out[9])) is dash.no_update
        # The unclamped inclusive reading of that exclusive end is a different slider value.
        assert _queue(cb, session, ("range", [0, 99])) == {"action": "range", "params": {"start": 0, "end": 100}}


@pytest.mark.unit
class TestLegacyShapesStayInclusive:
    def _flat(self):
        """No nested summary. ``window.end_epoch`` is the last index; ``range`` is an inclusive list."""
        return {
            "snapshot_id": "snap-flat",
            "fsm_state": "Replaying",
            "length": 50,
            "window": {"start_epoch": 0, "end_epoch": 49},
            "time_index": {"current": 20},
            "speed": -2.0,
            "range": [4, 20],
        }

    def test_the_rendered_values_echo_and_a_change_sends_an_exclusive_end(self, cb):
        session = self._flat()
        out = cb["render_session"](session)
        assert (out[4], out[5]) == (0, 49), "a legacy window end is already the last index"
        assert out[6] == 20
        assert out[9] == [4, 20], "a list range is inclusive; it must not lose its last frame"
        assert out[12] == -2.0
        assert _queue(cb, session, ("scrubber", out[6])) is dash.no_update
        assert _queue(cb, session, ("speed", out[12])) is dash.no_update
        assert _queue(cb, session, ("range", out[9])) is dash.no_update
        assert _queue(cb, session, ("range", [4, 21])) == {"action": "range", "params": {"start": 4, "end": 22}}


@pytest.mark.unit
class TestWindowStartIsKept:
    def test_a_window_that_does_not_start_at_zero(self, cb):
        session = _block(
            time_index={"current": 5, "snapshot_window": {"start_epoch": 5, "end_epoch": 12}},
            session={
                "length": 12,
                "time_index": 5,
                "speed": 1.0,
                "paused": True,
                "range": {"start": 5, "end": 12},
                "weights_available": False,
            },
        )
        out = cb["render_session"](session)
        assert (out[4], out[5]) == (5, 11), "start_epoch is the first index; end_epoch is still a count"
        assert out[9] == [5, 11]
        assert _queue(cb, session, ("scrubber", out[6])) is dash.no_update
        assert _queue(cb, session, ("range", out[9])) is dash.no_update
