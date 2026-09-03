#!/usr/bin/env python
"""F-CANOPY-044 / F-CANOPY-045: node click selection, pinned against the REAL callback.

**Why this file exists at all, which is the durable part.**

``test_network_visualizer_callbacks.py`` already has a
``TestHandleNodeSelectionCallback`` class with eleven tests, and every one of them
either drives ``_simulate_handle_node_selection`` -- a *re-implementation* of the
handler living in the test file -- or, worse, re-types the production expression
inline and asserts against its own copy::

    def test_layer_detection_input(self, visualizer):
        layer_names = ["", "", "Input", "Hidden", "Output"]
        curve_number = 2
        layer = layer_names[min(curve_number, 4)] if curve_number >= 2 else "Unknown"
        assert layer == "Input"

That test imports nothing from ``network_visualizer`` and calls nothing in it. It
cannot fail for any implementation -- the same class as canopy#558's
``assert min(a, b) <= b``, which is how F-CANOPY-041b shipped. Four
``test_layer_detection_*`` tests "covered" the layer logic while the product
labelled **every** node ``Output``.

So the rule for this file: **every test here reaches the real registered callback
or the real trace builder.** None of them re-states the logic under test.

THE TWO DEFECTS.

* **F-CANOPY-044** -- the figure carries one ``mode="lines"`` trace per connection
  (1888 of them on a 40-unit network) plus 3 node traces, and each edge is drawn
  TO the node centres. A click aimed at a node therefore resolves to an EDGE, whose
  points have no ``text``, and the handler's ``if text:`` guard dropped it. Measured
  live: **0 of 7** clicks across all three node traces landed on a node trace, and
  ``-selection-info`` never left ``display:none``.
* **F-CANOPY-045** -- ``layer_names[min(curve_number, 4)]`` is correct only if the
  node traces are curves 2-4. They are ~1888-1890, so ``min(...)`` is 4 for all
  three and every node reported ``Layer: Output``. Fully MASKED by -044 until -044
  was lifted experimentally, at which point all three node types showed it.

Fix directions were chosen by measurement, not argument
(``util/ad-hoc/2026-09-02_f044_fix_experiment.py`` in juniper-ml): reordering so the
node traces come first does NOT work (with them moved to curves 0/1/2 a node click
still resolved to edge curve 251, so data order does not break plotly's tie), while
``customdata`` on the edges DOES survive onto ``clickData``.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from dash import Dash, dcc, html

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402

COMPONENT_ID = "network-visualizer"


@pytest.fixture
def visualizer():
    return NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)


@pytest.fixture
def selection_callback(visualizer):
    """The REAL registered ``handle_node_selection``, unwrapped.

    Single explicit return rather than ``return`` inside the loop plus a trailing
    ``pytest.fail``: CodeQL reads the latter as an implicit fall-through return
    (it cannot know ``pytest.fail`` raises) and files
    "Explicit returns mixed with implicit (fall through) returns", which lands as
    an unresolved review thread that blocks the merge while every check still
    reads SUCCESS.
    """
    app = Dash(__name__)
    app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(app)
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


def _call(callback, *, click_data=None, selected_data=None, current_selection=None, theme=None, trigger="clickData"):
    """Invoke the real callback with a stubbed dash callback context."""
    ctx = MagicMock()
    ctx.triggered = [{"prop_id": f"{COMPONENT_ID}-graph.{trigger}"}]
    with patch("dash.callback_context", ctx):
        return callback(click_data, selected_data, current_selection, theme)


def _text_of(children):
    """Flatten a Dash component tree to a string, for asserting on rendered text."""
    if children is None:
        return ""
    if isinstance(children, str):
        return children
    if isinstance(children, (list, tuple)):
        return " ".join(_text_of(c) for c in children)
    return _text_of(getattr(children, "children", None))


def _graph_with_edges():
    """A tiny directed graph whose node ids match the production naming."""
    g = nx.DiGraph()
    for n in ("input_0", "hidden_0", "output_0"):
        g.add_node(n)
    g.add_edge("input_0", "hidden_0", weight=0.5)
    g.add_edge("hidden_0", "output_0", weight=-0.25)
    return g


@pytest.mark.unit
class TestF044EdgesCarryTheirEndpointLabels:
    """The edge traces must say which node sits at each vertex."""

    def test_every_edge_trace_has_customdata(self, visualizer):
        g = _graph_with_edges()
        pos = {"input_0": (0.0, 0.0), "hidden_0": (1.0, 1.0), "output_0": (2.0, 0.0)}
        traces = visualizer._create_edge_traces(g, pos, show_weights=False)
        edge_traces = [t for t in traces if getattr(t, "mode", None) == "lines"]
        assert edge_traces, "no edge traces built"
        for t in edge_traces:
            assert t.customdata is not None, "an edge trace carries no customdata — a click on it cannot identify a node (F-CANOPY-044)"

    def test_customdata_uses_the_same_label_form_as_node_traces(self, visualizer):
        """``hidden_0`` -> ``Hidden 0``, matching ``_create_node_trace``'s labels.

        If these two ever diverge, the handler's ``node_id`` derivation would
        produce a different id for a click on an edge than for a click on a node,
        and the toggle-to-deselect behaviour would silently break.
        """
        g = _graph_with_edges()
        pos = {"input_0": (0.0, 0.0), "hidden_0": (1.0, 1.0), "output_0": (2.0, 0.0)}
        traces = visualizer._create_edge_traces(g, pos, show_weights=False)
        edge_traces = [t for t in traces if getattr(t, "mode", None) == "lines"]
        seen = {cd for t in edge_traces for cd in (t.customdata or []) if cd}
        assert "Input 0" in seen
        assert "Hidden 0" in seen
        assert "Output 0" in seen

    def test_customdata_is_positional_with_the_vertices(self, visualizer):
        """[from, to, None] — the third entry pairs with the ``None`` separator.

        plotly hands back ``customdata`` for the point index it resolved, so the
        alignment IS the mechanism: index 0 is the source vertex, index 1 the target.
        """
        g = nx.DiGraph()
        g.add_edge("input_0", "hidden_0", weight=0.5)
        pos = {"input_0": (0.0, 0.0), "hidden_0": (1.0, 1.0)}
        t = [x for x in visualizer._create_edge_traces(g, pos, show_weights=False) if getattr(x, "mode", None) == "lines"][0]
        assert list(t.customdata) == ["Input 0", "Hidden 0", None]
        assert len(t.customdata) == len(t.x), "customdata must be per-point, aligned with x"

    def test_the_weight_tooltip_is_preserved(self, visualizer):
        """The reason ``hoverinfo='skip'`` was rejected — it would kill this."""
        g = nx.DiGraph()
        g.add_edge("input_0", "hidden_0", weight=-0.42)
        pos = {"input_0": (0.0, 0.0), "hidden_0": (1.0, 1.0)}
        t = [x for x in visualizer._create_edge_traces(g, pos, show_weights=False) if getattr(x, "mode", None) == "lines"][0]
        assert t.hoverinfo == "text"
        assert "Weight: -0.420" in str(t.hovertext)


@pytest.mark.unit
class TestF044ClickOnAnEdgeStillSelectsTheNode:
    """The live failure: a click aimed at a node resolves to an edge."""

    def test_edge_resolved_click_selects_the_node(self, selection_callback):
        """FAILS ON THE PARENT — this is the whole finding.

        Shape taken from the real measurement: curve 248 (an edge), ``text`` absent,
        ``customdata`` naming the node at the clicked vertex.
        """
        click = {"points": [{"curveNumber": 248, "pointNumber": 0, "customdata": "Hidden 0"}]}
        nodes, info, style = _call(selection_callback, click_data=click, current_selection=[])
        assert nodes == ["hidden_0"], "an edge-resolved click selected nothing — node selection is unreachable (F-CANOPY-044)"
        assert style["display"] == "block"
        assert "Hidden 0" in _text_of(info)

    def test_node_resolved_click_still_selects(self, selection_callback):
        """The pre-existing path must not regress."""
        click = {"points": [{"curveNumber": 1889, "pointNumber": 0, "text": "Hidden 3"}]}
        nodes, _, style = _call(selection_callback, click_data=click, current_selection=[])
        assert nodes == ["hidden_3"]
        assert style["display"] == "block"

    def test_text_wins_over_customdata(self, selection_callback):
        """A node-trace click carries both; ``text`` is the node's own label."""
        click = {"points": [{"curveNumber": 1889, "pointNumber": 0, "text": "Hidden 3", "customdata": "Input 0"}]}
        nodes, _, _ = _call(selection_callback, click_data=click, current_selection=[])
        assert nodes == ["hidden_3"]

    def test_clicking_the_same_node_again_deselects(self, selection_callback):
        """M-TOPOLOGY-10's second half, now reachable through an edge-resolved click."""
        click = {"points": [{"curveNumber": 248, "pointNumber": 0, "customdata": "Hidden 0"}]}
        nodes, _, style = _call(selection_callback, click_data=click, current_selection=["hidden_0"])
        assert nodes == []
        assert style["display"] == "none"

    def test_a_point_with_neither_text_nor_customdata_clears(self, selection_callback):
        """Empty space stays empty space (M-TOPOLOGY-12)."""
        click = {"points": [{"curveNumber": 7, "pointNumber": 0}]}
        nodes, _, style = _call(selection_callback, click_data=click, current_selection=["hidden_0"])
        assert nodes == []
        assert style["display"] == "none"


@pytest.mark.unit
class TestF045LayerComesFromTheLabelNotTheCurveNumber:
    """Every node reported ``Output`` because the table was indexed by curveNumber."""

    @pytest.mark.parametrize(
        ("label", "expected"),
        [("Input 0", "Input"), ("Hidden 0", "Hidden"), ("Output 1", "Output")],
    )
    def test_layer_is_derived_from_the_label(self, selection_callback, label, expected):
        """FAILS ON THE PARENT for Input and Hidden — both reported ``Output``.

        The curveNumber here is a realistic ~1889, which is exactly the value that
        made ``layer_names[min(curve_number, 4)]`` collapse to ``Output``.
        """
        click = {"points": [{"curveNumber": 1889, "pointNumber": 0, "text": label}]}
        _, info, _ = _call(selection_callback, click_data=click, current_selection=[])
        assert f"Layer: {expected}" in _text_of(info)

    def test_layer_is_correct_for_an_edge_resolved_click_too(self, selection_callback):
        """The two fixes have to compose: an edge curve number must not leak in."""
        click = {"points": [{"curveNumber": 248, "pointNumber": 0, "customdata": "Input 0"}]}
        _, info, _ = _call(selection_callback, click_data=click, current_selection=[])
        assert "Layer: Input" in _text_of(info)

    def test_an_unrecognised_label_reads_unknown(self, selection_callback):
        click = {"points": [{"curveNumber": 1889, "pointNumber": 0, "text": "Candidate 2"}]}
        _, info, _ = _call(selection_callback, click_data=click, current_selection=[])
        assert "Layer: Unknown" in _text_of(info)


@pytest.mark.unit
class TestBoxSelectDoesNotOverSelect:
    """The customdata fallback must NOT leak into the box/lasso branch.

    ``selectedData`` returns every point inside the region across ALL traces. If the
    edge fallback applied there, a box drawn over a few nodes would also pick up both
    endpoints of every edge crossing the region — silently selecting nodes the user
    never enclosed. The click branch wants the fallback; this one does not.
    """

    def test_edge_points_are_ignored_by_box_select(self, selection_callback):
        selected = {
            "points": [
                {"text": "Input 0"},
                {"curveNumber": 248, "customdata": "Hidden 39"},
                {"text": "Hidden 0"},
            ]
        }
        nodes, _, style = _call(selection_callback, selected_data=selected, current_selection=[], trigger="selectedData")
        assert nodes == ["input_0", "hidden_0"], "box select picked up an edge endpoint the user did not enclose"
        assert style["display"] == "block"
