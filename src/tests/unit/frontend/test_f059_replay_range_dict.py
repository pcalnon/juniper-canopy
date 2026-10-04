#!/usr/bin/env python
"""F-CANOPY-059: against cascor the replay player never showed a session.

Finding: juniper-ml ``notes/JUNIPER_2026-08-09_JUNIPER-CANOPY_E2E-VALIDATION-EVIDENCE.md``
(F-CANOPY-059, P0, a regression from canopy#532).

cascor's ``/replay`` route nests ``state_summary()`` at ``data.session``. That summary has served
``range`` as a dict, ``{"start": …, "end": …}``, since cascor#178. canopy#532 (F-CANOPY-015) read
``range`` one level deeper but kept indexing it as a list, so ``render_session`` raised
``KeyError: 0`` on every session cascor served. Dash applies none of a raising callback's outputs, so
the Replay tab stayed at "No active replay session" with no control reachable, and cascor stayed in
REPLAYING.

canopy#532's own test passed because its fixture, labelled "the exact shape measured off the running
service", typed the range as a list. These tests use the payload Phase 1 measured live (the ledger's
Phase 1 segment 7, "F-CANOPY-015 measured against the payload"), and they execute the REGISTERED
callback, not a helper, because the helper alone cannot show that the callback no longer raises.

Verified against the parent commit: ``test_render_session_on_the_measured_payload`` raises
``KeyError: 0`` there.
"""

from unittest.mock import MagicMock

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

# The ``data`` block ``confirm_snapshot_op`` stores as the session: the replay block carries
# ``snapshot_id``, ``fsm_state`` and the ``time_index`` window, and nests the summary at ``session``.
MEASURED_DATA_BLOCK = {
    "snapshot_id": "snap-measured",
    "fsm_state": "Replaying",
    "operation": "replay",
    "time_index": {"current": 0, "snapshot_window": {"start_epoch": 0, "end_epoch": 12}},
    "session": MEASURED_SESSION,
}


@pytest.fixture
def render_session():
    """The registered ``render_session`` callback, captured from a Dash-free stub app."""
    captured = {}
    app = MagicMock()
    app.clientside_callback = MagicMock()

    def callback(*_args, **_kwargs):
        def register(fn):
            captured[fn.__name__] = fn
            return fn

        return register

    app.callback = callback
    ReplayPlayerPanel({"api_base_url": "http://localhost:8050"}, component_id="rp-f059").register_callbacks(app)
    return captured["render_session"]


@pytest.mark.unit
class TestF059RangeDictFromCascor:
    def test_render_session_on_the_measured_payload(self, render_session):
        out = render_session(MEASURED_DATA_BLOCK)
        idle_style, active_style = out[0], out[1]
        assert idle_style == {"display": "none"}, "the idle placeholder still shows for a live cascor session"
        assert active_style == {"display": "block"}, "the player's controls never render for a cascor session"
        # cascor's range end is exclusive and its window end is a count: 12 frames are indexes 0..11.
        assert out[9] == [0, 11], "the range slider value must be an inclusive [lo, hi] list"
        assert out[11] == "[0, 11]", "the range readout"
        assert out[14] == "V2 ✓ weights", "weights_available is true in the measured payload"

    def test_a_narrowed_dict_range_is_shown(self, render_session):
        block = dict(MEASURED_DATA_BLOCK, session=dict(MEASURED_SESSION, range={"start": 3, "end": 9}))
        out = render_session(block)
        assert out[9] == [3, 8], "cascor's end 9 is exclusive: the last frame played is 8"
        assert out[11] == "[3, 8]"

    def test_the_legacy_list_shape_still_renders(self, render_session):
        block = dict(MEASURED_DATA_BLOCK, session=dict(MEASURED_SESSION, range=[2, 7]))
        out = render_session(block)
        assert out[9] == [2, 7]

    @pytest.mark.parametrize("raw", [None, {}, {"start": 1}, [], [1], "0-12", {"start": "a", "end": "b"}, [None, 4]])
    def test_missing_or_malformed_range_falls_back_to_the_window(self, render_session, raw):
        block = dict(MEASURED_DATA_BLOCK, session=dict(MEASURED_SESSION, range=raw))
        out = render_session(block)
        assert out[1] == {"display": "block"}, f"render_session must not fail on range={raw!r}"
        assert out[9] == [0, 11]


@pytest.mark.unit
class TestF059SessionRangeHelper:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ({"start": 0, "end": 13}, [0, 12]),  # cascor's end is exclusive
            ({"start": 4, "end": 8}, [4, 7]),
            ([4, 8], [4, 8]),
            ((4, 8), [4, 8]),
            ({"start": -5, "end": 99}, [0, 12]),  # clamped to the window
            ({"start": 9, "end": 3}, [9, 9]),  # never inverted
            (None, [0, 12]),
        ],
    )
    def test_normalises_to_a_clamped_pair(self, raw, expected):
        assert ReplayPlayerPanel._session_range(raw, 0, 12) == expected
