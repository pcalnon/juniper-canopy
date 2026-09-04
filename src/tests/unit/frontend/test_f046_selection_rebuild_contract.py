#!/usr/bin/env python
"""F-CANOPY-046 complementary contract: why ``no_update`` is load-bearing.

``test_f046_clear_selection.py`` (17 tests, ships with canopy#573) already pins
the control, the hint text, and the click-path ``no_update`` guard against the
REAL ``handle_node_selection``. This file covers the three facts that suite
cannot see:

1. **The rebuild consumer.** ``-selected-nodes`` is a real Input of
   ``update_network_graph``. Dash fires every consumer of a store on ANY write,
   identical or not — the 1.5–31 s figure rebuild that made the unconditional
   ``[]`` write expensive. F046 asserts ``is dash.no_update`` on the *writer*
   and never looks at the reader. F037's "real topology triggers" list names
   ``-topology-store`` and ``ws-cascade-add-buffer`` and omits this store, so a
   demotion to State (copying the F-CANOPY-037 / -039 pattern) would leave the
   selection highlight unpainted and every F046 test still green.

2. **The selectedData fall-through.** Plotly's box/lasso path emits
   ``selectedData`` as ``{points: []}`` or ``None`` when the rubber-band is
   dismissed. Those used to write ``[]`` unconditionally, same as the click
   fall-through. F046 only drives the clickData miss. The leftover
   ``_simulate_handle_node_selection`` in ``test_network_visualizer_callbacks.py``
   still encodes the old ``[]`` write, so that class stays green on a revert.

3. **The layout ↔ callback style contract.** The button is revealed by replacing
   its whole ``style`` dict. If the callback's ``clear_base`` drifts from the
   layout keys, the control jumps (padding / font / cursor) the moment it
   appears. F046 asserts only ``display``.

Do not restack ``test_f046_clear_selection.py``.
"""

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
GRAPH_ID = f"{COMPONENT_ID}-graph"

_STYLE_KEYS_THAT_MUST_NOT_JUMP = ("marginBottom", "padding", "fontSize", "cursor")


@pytest.fixture
def visualizer():
    return NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)


@pytest.fixture
def app(visualizer):
    dash_app = Dash(__name__)
    dash_app.layout = html.Div([dcc.Graph(id=GRAPH_ID)])
    visualizer.register_callbacks(dash_app)
    return dash_app


@pytest.fixture
def selection_callback(app):
    """The REAL registered ``handle_node_selection``, unwrapped.

    Single explicit return: CodeQL treats ``return``-in-loop plus a trailing
    ``pytest.fail`` as mixed explicit/implicit returns (canopy#564).
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


@pytest.fixture
def rebuild_entry(app):
    """The registered ``update_network_graph`` callback_map entry."""
    found = None
    for key, entry in app.callback_map.items():
        if f"{GRAPH_ID}.figure" in key:
            found = entry
            break
    assert found is not None, "update_network_graph is not registered"
    return found


def _call(callback, *, click_data=None, selected_data=None, clear_clicks=0, current_selection=None, theme=None, trigger=None):
    """Invoke the real callback. No arity padding — this file is stacked on F046."""
    ctx = MagicMock()
    ctx.triggered = [{"prop_id": trigger or f"{GRAPH_ID}.clickData"}]
    with patch("dash.callback_context", ctx):
        return list(callback(click_data, selected_data, clear_clicks, current_selection, theme))


def _find(node, node_id):
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


def _dep_pairs(entry, kind):
    return [(dep.get("id"), dep.get("property")) for dep in entry.get(kind, []) if isinstance(dep, dict)]


@pytest.mark.unit
class TestRebuildConsumerMakesNoUpdateLoadBearing:
    """F046's ``is dash.no_update`` assertions are empty if nothing listens."""

    def test_selected_nodes_is_an_input_of_the_rebuild(self, rebuild_entry):
        """A write to the store — even ``[]`` over ``[]`` — fires the 1.5–31 s rebuild.

        Demoting this to State (the F-CANOPY-037 / -039 move) would leave every
        F046 test green and the selection highlight unpainted: State is read
        when something else fires, and a selection change is not a topology
        change.
        """
        inputs = _dep_pairs(rebuild_entry, "inputs")
        assert (SELECTED_STORE, "data") in inputs, (
            f"{SELECTED_STORE} is not an Input of update_network_graph — "
            "writing the store no longer rebuilds the figure, so the highlight "
            "and the no_update guard both lose their consumer"
        )

    def test_selected_nodes_is_not_demoted_to_state(self, rebuild_entry):
        """Input, not State. The same demotion that fixed the poll tick would
        silently starve the highlight here."""
        assert (SELECTED_STORE, "data") not in _dep_pairs(rebuild_entry, "state")


@pytest.mark.unit
class TestSelectedDataFallthroughAlsoGuardsTheStore:
    """The box/lasso dismiss path used to write ``[]`` too.

    F046 covers the clickData miss and the clear button. Plotly's selectedData
    dismiss (empty points, or ``None``) is a third writer of the same store
    and is exercised here against the real callback — not the leftover
    simulator that still returns ``[]``.
    """

    def test_empty_box_points_write_nothing_when_empty(self, selection_callback):
        out = _call(
            selection_callback,
            selected_data={"points": []},
            current_selection=[],
            trigger=f"{GRAPH_ID}.selectedData",
        )
        assert all(v is dash.no_update for v in out), (
            "an empty box-select still writes the store, forcing a rebuild"
        )

    def test_null_box_selection_writes_nothing_when_empty(self, selection_callback):
        """Plotly sends ``selectedData=None`` when the rubber-band is dismissed."""
        out = _call(
            selection_callback,
            selected_data=None,
            current_selection=[],
            trigger=f"{GRAPH_ID}.selectedData",
        )
        assert all(v is dash.no_update for v in out)

    def test_box_points_without_text_write_nothing_when_empty(self, selection_callback):
        """Edge vertices carry no ``text``; filtering them all out is a no-op."""
        out = _call(
            selection_callback,
            selected_data={"points": [{"curveNumber": 0}, {"curveNumber": 12}]},
            current_selection=[],
            trigger=f"{GRAPH_ID}.selectedData",
        )
        assert all(v is dash.no_update for v in out)

    def test_empty_box_points_still_clear_a_real_selection(self, selection_callback):
        """The guard must not turn into a refusal to honour a box-select dismiss."""
        nodes, _, style, clear_style = _call(
            selection_callback,
            selected_data={"points": []},
            current_selection=["hidden_0"],
            trigger=f"{GRAPH_ID}.selectedData",
        )
        assert nodes == []
        assert style.get("display") == "none"
        assert clear_style.get("display") == "none"

    def test_null_box_selection_still_clears_a_real_selection(self, selection_callback):
        nodes, _, style, clear_style = _call(
            selection_callback,
            selected_data=None,
            current_selection=["input_0", "hidden_0"],
            trigger=f"{GRAPH_ID}.selectedData",
        )
        assert nodes == []
        assert style.get("display") == "none"
        assert clear_style.get("display") == "none"


@pytest.mark.unit
class TestClearButtonStyleDoesNotJumpOnReveal:
    """Replacing the whole style dict must not restyle the control."""

    def test_revealed_button_keeps_the_layout_non_display_keys(self, visualizer, selection_callback):
        button = _find(visualizer.get_layout(), CLEAR_BUTTON)
        assert button is not None, "no clear-selection control in the layout"
        shipped = button.style or {}
        for key in _STYLE_KEYS_THAT_MUST_NOT_JUMP:
            assert key in shipped, f"layout button is missing style key {key!r}"

        _, _, _, clear_style = _call(
            selection_callback,
            click_data={"points": [{"text": "Hidden 0", "curveNumber": 1888}]},
            current_selection=[],
        )
        for key in _STYLE_KEYS_THAT_MUST_NOT_JUMP:
            assert clear_style.get(key) == shipped.get(key), (
                f"revealing the button changed {key!r}: "
                f"layout={shipped.get(key)!r} callback={clear_style.get(key)!r}"
            )
        assert clear_style.get("display") in ("inline-block", "block", "inline")

    def test_hidden_after_clear_keeps_the_same_non_display_keys(self, visualizer, selection_callback):
        shipped = (_find(visualizer.get_layout(), CLEAR_BUTTON).style or {})
        _, _, _, clear_style = _call(
            selection_callback,
            clear_clicks=1,
            current_selection=["hidden_0"],
            trigger=f"{CLEAR_BUTTON}.n_clicks",
        )
        for key in _STYLE_KEYS_THAT_MUST_NOT_JUMP:
            assert clear_style.get(key) == shipped.get(key)
        assert clear_style.get("display") == "none"

    def test_button_style_is_theme_independent(self, selection_callback):
        """The panel is themed; the button is not. A theme leak on only one
        path would make the control jump when the theme flips under a selection."""
        click = {"points": [{"text": "Hidden 0", "curveNumber": 1888}]}
        _, _, _, light = _call(selection_callback, click_data=click, current_selection=[], theme="light")
        _, _, _, dark = _call(selection_callback, click_data=click, current_selection=[], theme="dark")
        assert light == dark, f"clear-button style changed with theme: light={light!r} dark={dark!r}"
