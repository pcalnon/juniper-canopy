#!/usr/bin/env python
"""Window and range shapes the measured-session replay tests never build.

``test_replay_range_end_and_echo.py`` uses a 12-frame window that starts at 0 and
always carries ``end_epoch``, and a dict ``time_index``. Four shapes fall outside
that, and outside the echo-guard tests that disagree a nested summary with a stale
top-level one:

* ``end_epoch`` of 1 is a one-frame history. Subtracting 1 only when the count is
  large, or only when it would not go negative, still leaves the scrubber an
  unplayable index. The empty-history case (``end_epoch`` 0) and the 12-frame case
  both stay green for that.
* A truthy integer ``time_index`` is cascor's ``state_summary`` shape. Asking it
  for ``snapshot_window`` raises ``AttributeError`` and the player does not render.
  ``0`` never reaches that line, because ``time_index or {}`` replaces it.
* An empty ``snapshot_window`` is falsy, so a legacy ``window`` beside it keeps
  its inclusive end. A check on key presence would enter the count path and
  collapse that window.
* A ``snapshot_window`` that names ``start_epoch`` and omits ``end_epoch`` is one
  index at that start. ``length`` does not fill the count in. The previous default
  was ``length - 1``.
* A dict range with no ``end`` renders as the whole window. Echoing that slider
  must not raise, and must not queue a control.
"""

from unittest.mock import MagicMock, patch

import dash
import pytest

from frontend.components.replay_player_panel import ReplayPlayerPanel

CID = "rp-echo-edges"


class _Ctx:
    __slots__ = ("triggered",)

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


def _block(**overrides):
    session = {
        "length": 12,
        "time_index": 0,
        "speed": 1.0,
        "paused": True,
        "range": {"start": 0, "end": 12},
        "weights_available": True,
    }
    block = {
        "snapshot_id": "snap-edges",
        "fsm_state": "Replaying",
        "operation": "replay",
        "time_index": {"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
        "session": session,
    }
    block.update(overrides)
    return block


@pytest.mark.unit
class TestOneFrameHistory:
    def test_end_epoch_one_is_index_zero_and_echoes(self, cb):
        session = _block(
            time_index={"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 1}},
            session={
                "length": 1,
                "time_index": 0,
                "speed": 1.0,
                "paused": True,
                "range": {"start": 0, "end": 1},
                "weights_available": False,
            },
        )
        out = cb["render_session"](session)
        assert (out[4], out[5]) == (0, 0), "one frame is index 0; end_epoch 1 is a count"
        assert out[9] == [0, 0]
        assert out[10] == "0 / 0"
        assert _queue(cb, session, ("range", out[9])) is dash.no_update
        assert _queue(cb, session, ("scrubber", out[6])) is dash.no_update


@pytest.mark.unit
class TestTimeIndexShapes:
    def test_a_truthy_integer_time_index_uses_length(self, cb):
        session = {
            "snapshot_id": "snap-edges",
            "fsm_state": "Replaying",
            "time_index": 4,
            "length": 12,
            "speed": 1.0,
            "range": {"start": 0, "end": 12},
            "weights_available": False,
        }
        out = cb["render_session"](session)
        assert out[1] == {"display": "block"}
        assert (out[4], out[5]) == (0, 11), "an int time_index has no snapshot_window; the last index is length - 1"
        assert out[9] == [0, 11]


@pytest.mark.unit
class TestPartialWindows:
    def test_an_empty_snapshot_window_keeps_the_legacy_window(self, cb):
        session = {
            "snapshot_id": "snap-edges",
            "fsm_state": "Replaying",
            "time_index": {"current": 10, "snapshot_window": {}},
            "window": {"start_epoch": 4, "end_epoch": 40},
            "length": 50,
            "speed": 1.0,
        }
        out = cb["render_session"](session)
        assert (out[4], out[5]) == (4, 40), "an empty snapshot_window is absent; the legacy end stays inclusive"
        assert out[6] == 10

    def test_a_missing_end_epoch_is_one_index_and_ignores_length(self, cb):
        session = _block(
            length=12,
            time_index={"current": 3, "snapshot_window": {"start_epoch": 3}},
        )
        out = cb["render_session"](session)
        assert (out[4], out[5]) == (3, 3), "no end_epoch: the window is that start, not length - 1"


@pytest.mark.unit
class TestMalformedRangeEcho:
    def test_a_dict_range_without_end_echoes_the_window(self, cb):
        session = _block()
        session["session"] = dict(session["session"], range={"start": 1})
        out = cb["render_session"](session)
        assert out[9] == [0, 11], "a dict with no end falls back to the window"
        assert _queue(cb, session, ("range", out[9])) is dash.no_update
        assert _queue(cb, session, ("range", [2, 4])) == {"action": "range", "params": {"start": 2, "end": 5}}
