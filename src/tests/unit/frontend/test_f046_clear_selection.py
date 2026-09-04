#!/usr/bin/env python
"""F-CANOPY-046: clearing the selection, pinned against the REAL callback.

WHAT WAS BROKEN.

The selection panel promised a gesture that does not exist. After a click it read
**"(Click again or elsewhere to deselect)"**; after a box/lasso select,
**"(Click elsewhere to deselect)"**. Clicking elsewhere does nothing, and never
did.

The mechanism, measured rather than argued: ``handle_node_selection``'s only click
Input is ``-graph.clickData``, and **plotly emits ``plotly_click`` only when a
POINT is hit**. A click on empty canvas produces no event at all — so ``clickData``
never changes, the callback (``prevent_initial_call=True``) never runs, and the
selection stands. Seven clicks on empty canvas produced zero events on the live
2/40/2/944 fixture. This is not a callback that fires and decides wrongly; it is a
callback that is never asked.

Half the click hint was true: clicking the *selected node* again does deselect it,
via the toggle branch. So that half stays and "or elsewhere" goes. The box branch
has no true half at all — clicking a selected node inside a box selection toggles
only that one node — so its hint is removed entirely rather than reworded into
something accurate but unusable ("click each selected node again to clear").

THE FIX, AND WHY NOT A LISTENER.

A clientside listener on the graph's own ``plotly_click`` / container-level
``mousedown`` would literally satisfy the old sentence, and it was rejected: it
races plotly's event path, and this callback family is the one this arc has
repeatedly starved (F-CANOPY-037 / -039 / -043). An explicit button is a control
the user can see, it cannot fire when nothing is selected because it is hidden
then, and it is drivable by a test. Options B1-B5 are recorded in juniper-ml's
``notes/JUNIPER_2026-09-04_JUNIPER-CANOPY_F042-F046-FIX-DECISION-BRIEF.md``.

THE THIRD DEFECT, WHICH NO OPTION INCLUDED.

The clear path wrote ``[]`` **unconditionally**. ``-selected-nodes`` is a real
Input of ``update_network_graph`` and Dash fires every consumer of a store on any
write, identical or not — the property canopy#542 had to suppress for the topology
store. So *failing* to clear an already-empty selection cost a full 1.5-31 s
rebuild. Both clear paths now return ``dash.no_update`` when there is nothing to
clear, and that is asserted below on identity, not on equality: ``[] == []`` would
pass against the broken behaviour.
"""

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import dash
import pytest
from dash import Dash, dcc, html

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402

COMPONENT_ID = "network-visualizer"

CLEAR_BUTTON = f"{COMPONENT_ID}-clear-selection"
SELECTED_STORE = f"{COMPONENT_ID}-selected-nodes"


@pytest.fixture
def visualizer():
    return NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)


@pytest.fixture
def app(visualizer):
    dash_app = Dash(__name__)
    dash_app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(dash_app)
    return dash_app


@pytest.fixture
def selection_callback(app):
    """The REAL registered ``handle_node_selection``, unwrapped.

    Single explicit return rather than ``return`` inside the loop plus a trailing
    ``pytest.fail``: CodeQL reads the latter as an implicit fall-through return
    (it cannot know ``pytest.fail`` raises) and files "Explicit returns mixed with
    implicit (fall through) returns", which lands as an unresolved review thread
    that blocks the merge while every check still reads SUCCESS. That happened on
    canopy#564, in this arc, in a fixture just like this one.
    """
    found = None
    for entry in app.callback_map.values():
        cb = entry.get("callback")
        if cb is None:
            continue
        raw = getattr(cb, "__wrapped__", cb)
        if getattr(raw, "__name__", None) == "handle_node_selection":
            found = raw
            break
    assert found is not None, "handle_node_selection is not registered"
    return found


class _MissingOutput(dict):
    """Stands in for an Output the build under test does not return.

    Behaves as an empty style dict, so ``.get("display")`` is ``None`` and the
    assertion that wanted a value fails with its own message rather than with an
    ``AttributeError`` about ``NoneType``.
    """

    def __repr__(self):  # pragma: no cover - diagnostic only
        return "<Output not present on this build>"


_MISSING = _MissingOutput()


def _call(callback, *, click_data=None, selected_data=None, clear_clicks=0, current_selection=None, theme=None, trigger=None):
    """Invoke the real callback with a stubbed dash callback context.

    ``trigger`` is the full ``prop_id`` so a test can drive the clear button as
    the trigger, which is the whole point of the new Input.

    The argument list is built from the callback's ACTUAL signature and the
    return is padded to four, deliberately. Without that, running this file
    against the parent commit collapses thirteen of its tests into one
    ``TypeError`` about positional arity — which proves only that the signature
    changed, and says nothing about the hint text or the unconditional write.
    With it, each test fails against parent for its own reason and the
    falsification is worth reading.

    This tolerance is NOT a substitute for pinning the shape: the Input's
    existence is asserted on its own by
    ``test_button_is_an_input_of_the_selection_callback``, so removing the
    button still fails loudly there.
    """
    ctx = MagicMock()
    ctx.triggered = [{"prop_id": trigger or f"{COMPONENT_ID}-graph.clickData"}]
    n_params = len(inspect.signature(callback).parameters)
    if n_params == 4:
        args = [click_data, selected_data, current_selection, theme]
    else:
        args = [click_data, selected_data, clear_clicks, current_selection, theme]
    with patch("dash.callback_context", ctx):
        out = list(callback(*args))
    while len(out) < 4:
        out.append(_MISSING)
    return out


def _text_of(children):
    """Flatten a Dash component tree to a string, for asserting on rendered text."""
    if children is None:
        return ""
    if isinstance(children, str):
        return children
    if isinstance(children, (list, tuple)):
        return " ".join(_text_of(c) for c in children)
    return _text_of(getattr(children, "children", None))


def _find(node, node_id):
    """Depth-first search of a rendered layout for a component by id."""
    if getattr(node, "id", None) == node_id:
        return node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            hit = _find(child, node_id)
            if hit is not None:
                return hit
    elif children is not None and not isinstance(children, str):
        return _find(children, node_id)
    return None


def _selection_entry(app):
    """The registration that writes ``-selected-nodes``, found by its Output.

    Located by scanning rather than by a composed ``callback_map`` key: that key
    is a concatenation of every Output, so adding one silently invalidates a
    hard-coded lookup and the test would fail for the wrong reason.
    """
    matches = [e for e in app._callback_list if f"{SELECTED_STORE}.data" in str(e.get("output", ""))]
    assert len(matches) == 1, f"expected one callback writing {SELECTED_STORE}, found {len(matches)}"
    return matches[0]


# Assert a POSITIVE display value, never `!= "none"`: an Output the build does
# not return reads as None here, and `None != "none"` is true — the assertion
# would pass against a build with no button at all.
_VISIBLE = ("inline-block", "block", "inline")

CLICK_ON_HIDDEN_0 = {"points": [{"text": "Hidden 0", "curveNumber": 1888}]}
BOX_OVER_TWO = {"points": [{"text": "Input 0"}, {"text": "Hidden 0"}]}


@pytest.mark.unit
class TestF046ClearControlExists:
    """B2: there is a control, it is wired as a trigger, and it is visible only
    when it applies."""

    def test_button_is_in_the_layout(self, visualizer):
        button = _find(visualizer.get_layout(), CLEAR_BUTTON)
        assert button is not None, "no clear-selection control in the layout — the panel promises a gesture with nothing behind it"
        assert "clear" in _text_of(button).lower()

    def test_button_ships_hidden(self, visualizer):
        """Nothing is selected at mount, so there is nothing to clear."""
        button = _find(visualizer.get_layout(), CLEAR_BUTTON)
        assert button is not None, "no clear-selection control in the layout"
        assert (button.style or {}).get("display") == "none"

    def test_button_is_an_input_of_the_selection_callback(self, app):
        """An Input, not State. The click on it IS the trigger — as State it
        would be read only when something else fired, which is the same wiring
        error F-CANOPY-042 recorded on the depth label."""
        entry = _selection_entry(app)
        inputs = [(i["id"], i["property"]) for i in entry["inputs"]]
        states = [(st["id"], st["property"]) for st in entry.get("state") or []]
        assert (CLEAR_BUTTON, "n_clicks") in inputs, "the clear button does not trigger the selection callback"
        assert (CLEAR_BUTTON, "n_clicks") not in states

    def test_button_style_is_an_output(self, app):
        """Its visibility is state-derived, not static."""
        outputs = [str(e.get("output", "")) for e in app._callback_list]
        assert any(f"{CLEAR_BUTTON}.style" in o for o in outputs), "nothing writes the button's style — it can never appear"


@pytest.mark.unit
class TestF046ClearActuallyClears:
    """The button does the thing the old hint claimed a click would do."""

    def test_clear_empties_the_selection(self, selection_callback):
        nodes, info, style, clear_style = _call(
            selection_callback,
            clear_clicks=1,
            current_selection=["hidden_0"],
            trigger=f"{CLEAR_BUTTON}.n_clicks",
        )
        assert nodes == []
        assert style.get("display") == "none", "the selection panel must close when the selection is cleared"
        assert clear_style.get("display") == "none", "the button must hide once there is nothing left to clear"

    def test_clear_works_on_a_box_selection_too(self, selection_callback):
        """The branch with no true click gesture at all is the one that most
        needed a control."""
        nodes, _, style, clear_style = _call(
            selection_callback,
            clear_clicks=1,
            current_selection=["input_0", "hidden_0"],
            trigger=f"{CLEAR_BUTTON}.n_clicks",
        )
        assert nodes == []
        assert style.get("display") == "none"
        assert clear_style.get("display") == "none"

    def test_button_is_revealed_when_a_click_selects(self, selection_callback):
        _, _, style, clear_style = _call(selection_callback, click_data=CLICK_ON_HIDDEN_0, current_selection=[])
        assert style.get("display") == "block"
        assert clear_style.get("display") in _VISIBLE, f"a selection exists and no way to clear it is offered (display={clear_style.get('display')!r})"

    def test_button_is_revealed_when_a_box_select_selects(self, selection_callback):
        _, _, style, clear_style = _call(
            selection_callback,
            selected_data=BOX_OVER_TWO,
            current_selection=[],
            trigger=f"{COMPONENT_ID}-graph.selectedData",
        )
        assert style.get("display") == "block"
        assert clear_style.get("display") in _VISIBLE, f"a box selection exists and no way to clear it is offered (display={clear_style.get('display')!r})"

    def test_button_hides_again_when_a_click_toggles_the_selection_off(self, selection_callback):
        """The one click gesture that DOES clear must leave the same end state as
        the button, or the two controls disagree about what "cleared" means."""
        nodes, _, style, clear_style = _call(selection_callback, click_data=CLICK_ON_HIDDEN_0, current_selection=["hidden_0"])
        assert nodes == []
        assert style.get("display") == "none"
        assert clear_style.get("display") == "none"


@pytest.mark.unit
class TestF046HintsAreTrue:
    """B1: the panel must not describe a gesture that does not exist."""

    def test_click_hint_no_longer_promises_elsewhere(self, selection_callback):
        _, info, _, _ = _call(selection_callback, click_data=CLICK_ON_HIDDEN_0, current_selection=[])
        text = _text_of(info)
        assert "elsewhere" not in text.lower(), f"the panel still promises a click-elsewhere gesture that emits no event: {text!r}"

    def test_click_hint_keeps_the_half_that_is_true(self, selection_callback):
        """Clicking the selected node again really does deselect it, so that
        instruction stays — dropping it would lose a working gesture."""
        _, info, _, _ = _call(selection_callback, click_data=CLICK_ON_HIDDEN_0, current_selection=[])
        assert "Click again to deselect" in _text_of(info)

    def test_box_select_panel_has_no_deselect_hint(self, selection_callback):
        """No click gesture clears a box selection, so there is no true sentence
        to write. The visible button carries the affordance instead."""
        _, info, _, _ = _call(
            selection_callback,
            selected_data=BOX_OVER_TWO,
            current_selection=[],
            trigger=f"{COMPONENT_ID}-graph.selectedData",
        )
        text = _text_of(info).lower()
        assert "deselect" not in text and "elsewhere" not in text, f"box-select panel still describes a clearing gesture: {text!r}"

    def test_box_select_panel_still_reports_what_is_selected(self, selection_callback):
        """Removing the hint must not remove the content."""
        _, info, _, _ = _call(
            selection_callback,
            selected_data=BOX_OVER_TWO,
            current_selection=[],
            trigger=f"{COMPONENT_ID}-graph.selectedData",
        )
        text = _text_of(info)
        assert "Selected: 2 node(s)" in text
        assert "Hidden 0" in text


@pytest.mark.unit
class TestF046NoOpCostsNothing:
    """The third defect: an unconditional ``[]`` write triggers a 1.5-31 s rebuild
    for no change.

    Asserted with ``is dash.no_update`` — ``== []`` would pass against the broken
    behaviour, which is precisely why this cost went unnoticed.
    """

    def test_clear_on_an_empty_selection_writes_nothing(self, selection_callback):
        out = _call(selection_callback, clear_clicks=1, current_selection=[], trigger=f"{CLEAR_BUTTON}.n_clicks")
        assert all(v is dash.no_update for v in out), "clearing an already-empty selection still writes the store, forcing a rebuild"

    def test_clear_on_a_null_selection_writes_nothing(self, selection_callback):
        """The store's value before anything is written can be ``None``, not
        ``[]`` — the guard has to cover both."""
        out = _call(selection_callback, clear_clicks=1, current_selection=None, trigger=f"{CLEAR_BUTTON}.n_clicks")
        assert all(v is dash.no_update for v in out)

    def test_a_click_that_resolves_to_nothing_writes_nothing_when_empty(self, selection_callback):
        """The fall-through path. A click on an edge with no label used to write
        ``[]`` unconditionally — a rebuild bought by a click that selected
        nothing while nothing was selected."""
        out = _call(selection_callback, click_data={"points": [{"curveNumber": 12}]}, current_selection=[])
        assert all(v is dash.no_update for v in out)

    def test_a_click_that_resolves_to_nothing_still_clears_a_real_selection(self, selection_callback):
        """The guard must not turn into a refusal to clear. Clicking away from a
        selected node onto an unlabelled point still drops the selection."""
        nodes, _, style, clear_style = _call(
            selection_callback,
            click_data={"points": [{"curveNumber": 12}]},
            current_selection=["hidden_0"],
        )
        assert nodes == []
        assert style.get("display") == "none"
        assert clear_style.get("display") == "none"
