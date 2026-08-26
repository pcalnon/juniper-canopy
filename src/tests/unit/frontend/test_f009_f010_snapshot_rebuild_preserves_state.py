"""F-CANOPY-009 / F-CANOPY-010 regression: the snapshots table's 10 s rebuild
must not destroy panel state.

Both were found live in the canopy E2E arc (juniper-ml evidence note):

* F-CANOPY-009 -- the detail panel self-destructed within one refresh tick of
  every ``View Details`` click. The rebuilt button was constructed without
  ``n_clicks=0`` (unlike its four op-item siblings), so the pattern-matching
  Input re-fired ``select_snapshot`` with ``[None]``; its guard then returned
  ``None``, which wiped the selected-id store, and the detail panel followed.
* F-CANOPY-010 -- the snapshot-operation CONFIRMATION modal closed itself
  ~3.6 s after opening: the same rebuild reconstructed the dropdown items,
  re-fired ``open_snapshot_op_modal`` with ``n_clicks == 0``, and its early-out
  returned ``(False, "", None)`` -- slamming the dialog shut, blanking its body
  and discarding the pending operation.

Every early-out in both callbacks means "nothing meaningful triggered me"; the
correct return is ``dash.no_update``. These tests drive the registered
callbacks directly (the ``registered_panel`` idiom of test_hdf5_callbacks.py).
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

src_dir = Path(__file__).parents[3]
sys.path.insert(0, str(src_dir))

import pytest
from dash import no_update
from dash.development.base_component import Component

import frontend.components.hdf5_snapshots_panel as panel_module
from frontend.components.hdf5_snapshots_panel import HDF5SnapshotsPanel

CID = "test-hdf5-snapshots"
VIEW_IDS = [{"type": f"{CID}-view-btn", "index": "snap_1"}, {"type": f"{CID}-view-btn", "index": "snap_2"}]
VIEW_CLICK = json.dumps({"index": "snap_2", "type": f"{CID}-view-btn"}, separators=(",", ":")) + ".n_clicks"
OP_CLICK = json.dumps({"index": "snap_1", "op": "restore", "type": f"{CID}-snapshot-op-btn"}, separators=(",", ":")) + ".n_clicks"
OP_BOGUS = json.dumps({"index": "snap_1", "op": "bogus", "type": f"{CID}-snapshot-op-btn"}, separators=(",", ":")) + ".n_clicks"


class _DummyApp:
    def callback(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


class _Ctx:
    def __init__(self, prop_id="", value=1):
        self.triggered = [{"prop_id": prop_id, "value": value}]


def _no_trigger():
    ctx = MagicMock()
    ctx.triggered = []
    return ctx


def _walk(node):
    """Yield every Dash component in a rendered tree."""
    if isinstance(node, (list, tuple)):
        for child in node:
            yield from _walk(child)
    elif isinstance(node, Component):
        yield node
        yield from _walk(getattr(node, "children", None))


def _pattern_buttons(rows, id_type):
    return [n for n in _walk(rows) if isinstance(getattr(n, "id", None), dict) and n.id.get("type") == id_type]


@pytest.fixture
def panel():
    p = HDF5SnapshotsPanel({}, component_id=CID)
    p.register_callbacks(_DummyApp())
    return p


@pytest.mark.unit
class TestF009DetailSelectionSurvivesRebuild:
    def test_view_details_button_carries_n_clicks_zero_like_its_siblings(self, panel):
        data = {
            "snapshots": [
                {"id": "snap_1", "timestamp": "", "size_bytes": 0},
                {"id": "snap_2", "timestamp": "", "size_bytes": 0},
            ],
            "message": None,
        }
        with patch.object(panel, "_fetch_snapshots_handler", return_value=data):
            rows, _, _, _ = panel._cb_update_snapshots_table(1, 0, 0, {"events": []})

        view = _pattern_buttons(rows, f"{CID}-view-btn")
        ops = _pattern_buttons(rows, f"{CID}-snapshot-op-btn")
        assert len(view) == 2 and len(ops) == 8
        # The four op items always carried n_clicks=0; the rebuilt View Details
        # button must match them instead of reporting None.
        assert {getattr(b, "n_clicks", None) for b in ops} == {0}
        assert [getattr(b, "n_clicks", None) for b in view] == [0, 0]

    @pytest.mark.parametrize(
        "rebuilt",
        [[None], [None, None], [0, 0], []],
        ids=["legacy-none", "legacy-none-x2", "zeros", "empty"],
    )
    def test_rebuild_refire_leaves_selection_alone(self, panel, rebuilt):
        ids = VIEW_IDS[: len(rebuilt)]
        assert panel._cb_select_snapshot(rebuilt, ids) is no_update

    def test_selection_then_rebuild_keeps_selected_id(self, panel):
        with patch.object(panel_module, "callback_context", _Ctx(VIEW_CLICK, 1)):
            assert panel._cb_select_snapshot([0, 1], VIEW_IDS) == "snap_2"
        # The 10 s rebuild: fresh buttons with falsy counters, and a trigger that
        # names the rebuilt input without a value. Neither may clear the store.
        with patch.object(panel_module, "callback_context", _Ctx(VIEW_CLICK, None)):
            assert panel._cb_select_snapshot([0, 0], VIEW_IDS) is no_update
        with patch.object(panel_module, "callback_context", _Ctx(VIEW_CLICK, None)):
            assert panel._cb_select_snapshot([1, 1], VIEW_IDS) is no_update

    def test_no_trigger_and_empty_prop_id_leave_selection_alone(self, panel):
        with patch.object(panel_module, "callback_context", _no_trigger()):
            assert panel._cb_select_snapshot([1, 0], VIEW_IDS) is no_update
        with patch.object(panel_module, "callback_context", _Ctx("", 1)):
            assert panel._cb_select_snapshot([1, 0], VIEW_IDS) is no_update


@pytest.mark.unit
class TestF010ConfirmModalSurvivesRebuild:
    def test_real_click_still_opens_the_modal(self, panel):
        with patch.object(panel_module, "callback_context", _Ctx(OP_CLICK, 1)):
            is_open, body, pending = panel._cb_open_snapshot_op_modal([1, 0, 0, 0], None, False)
        assert is_open is True
        assert "snap_1" in str(body)
        assert pending == {"id": "snap_1", "operation": "restore"}

    @pytest.mark.parametrize(
        "make_ctx",
        [
            lambda: _Ctx(OP_CLICK, 0),
            lambda: _Ctx(OP_CLICK, None),
            lambda: _no_trigger(),
            lambda: _Ctx("", 1),
            lambda: _Ctx(OP_BOGUS, 1),
        ],
        ids=["rebuilt-items-refire-zero", "refire-none", "no-trigger", "empty-prop-id", "unknown-op"],
    )
    def test_rebuild_refire_leaves_the_open_modal_alone(self, panel, make_ctx):
        # ``_is_open=True``: the operator is reading the confirmation dialog when
        # the rebuild lands. The live signature was body blanked at +4.8 s and
        # the modal gone at +5.9 s with no user action.
        with patch.object(panel_module, "callback_context", make_ctx()):
            result = panel._cb_open_snapshot_op_modal([0, 0, 0, 0], None, True)
        assert len(result) == 3
        assert all(r is no_update for r in result)

    def test_context_menu_reset_does_not_close_the_modal(self, panel):
        # The context-menu Store is a second Input; a falsy rewrite of it (its
        # reset after an operation) must be as inert as the rebuilt items.
        with patch.object(panel_module, "callback_context", _Ctx(f"{CID}-context-menu-trigger.data", None)):
            result = panel._cb_open_snapshot_op_modal([0, 0, 0, 0], None, True)
        assert all(r is no_update for r in result)
