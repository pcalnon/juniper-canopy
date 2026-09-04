#!/usr/bin/env python
"""F-CANOPY-042: the depth-filter label, pinned against the REAL registered callbacks.

WHAT WAS BROKEN — two defects, not one.

**Defect A — the label was wired to the wrong thing.** ``-depth-label.children``
was the fourth Output of the *clientside slider-bounds sync*, whose only Input is
``-topology-store.data``; the slider's value rode there as **State**, and a State
is read when something *else* fires. So the label recomputed when the topology
changed and never when the user moved the slider. Since canopy#542
identity-suppressed the topology store, at idle it never changed at all — the
label was frozen at whatever the last topology write produced. Measured live on a
2/40/2/944 fixture: dragging to 20 re-rendered the figure (1891 -> 551 traces) and
moved the stats bar (``hidden`` ``40`` -> ``20 of 40``) while the label sat at
``"0 of 40"``.

The obvious repair is **structurally unavailable**: adding
``Input(-depth-slider, "value")`` to that callback would make one
component-property both an Input and an Output of a single callback, which Dash
rejects at registration as a circular dependency. Hence the split.

**Defect B — ``0`` meant two different things, and was wrong at rest.** The
server filter reads ``depth <= 0`` as "no filter" and labels it ``"all"``; the
clientside rule was ``(v === nHidden) ? "all" : v + " of " + nHidden``, which at
the slider's shipped ``value=0`` renders ``"0 of 40"``. On a freshly loaded
40-unit network the control therefore read **"0 of 40" while all 40 units were on
screen** — wrong before anyone touched anything, and *not* fixed by repairing the
wiring alone.

WHY THESE TESTS ARE SHAPED THIS WAY.

Both halves of the fix live in JavaScript, which no Python assertion can execute.
The temptation is to assert on source substrings and call it covered — the same
move that let F-CANOPY-041b and F-CANOPY-045 ship green (see
``test_f044_node_click_selection.py``'s header for that history). So the coverage
here is layered:

1. **Wiring** is checked against ``app._callback_list`` after a real
   ``register_callbacks`` — the actual registration Dash would serve, not a
   description of it. These carry the load and always run.
2. **The rule** is checked by *executing the registered JavaScript under node*
   and comparing it, case for case, against ``_apply_hierarchy_filter`` — the
   server function that decides what is actually filtered. The Python side is the
   oracle; the test asserts the two agree rather than asserting the JS matches a
   second copy of the rule typed into this file.
3. A **source-level backstop** for the rule runs even where node is absent, so
   the node skip cannot leave Defect B uncovered.

Both wiring and rule tests fail against the parent commit (``ee2ec79``): there is
no callback outputting ``-depth-label.children`` on its own there, and the rule
lacks the ``depth <= 0`` arm entirely.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dash import Dash, dcc, html

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.components.network_visualizer import NetworkVisualizer  # noqa: E402

COMPONENT_ID = "network-visualizer"

LABEL_OUTPUT = f"{COMPONENT_ID}-depth-label.children"
SLIDER_VALUE = (f"{COMPONENT_ID}-depth-slider", "value")
TOPOLOGY_STORE = (f"{COMPONENT_ID}-topology-store", "data")

NODE = shutil.which("node") or shutil.which("nodejs")


@pytest.fixture
def app():
    """A Dash app with the real callbacks registered.

    ``register_callbacks`` is what the dashboard calls; if any of this file's
    wiring were a circular dependency, Dash would raise here rather than at
    assert time — which is itself part of what these tests protect.
    """
    visualizer = NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)
    dash_app = Dash(__name__)
    dash_app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(dash_app)
    return dash_app


def _callback_list(app):
    """Dash's registration list, with a legible failure if the internal moves.

    ``_callback_list`` is private, but it is the only place the clientside
    function *name* is recorded — ``callback_map`` drops it. A Dash upgrade that
    renames this should fail loudly here rather than silently skipping every
    test below.
    """
    entries = getattr(app, "_callback_list", None)
    assert entries, "dash.Dash no longer exposes _callback_list — these tests need re-pointing, not deleting"
    return entries


def _entry_for(app, output_key):
    matches = [c for c in _callback_list(app) if output_key in str(c.get("output", ""))]
    return matches


def _pairs(entries_key):
    return [(e["id"], e["property"]) for e in entries_key or []]


def _label_entry(app):
    matches = _entry_for(app, LABEL_OUTPUT)
    assert len(matches) == 1, f"expected exactly one callback writing {LABEL_OUTPUT}, found {len(matches)}"
    return matches[0]


@pytest.mark.unit
class TestF042LabelWiring:
    """Defect A. The label must recompute when the slider moves."""

    def test_label_has_exactly_one_writer(self, app):
        """One writer, not two.

        Option A3 from the fix brief — a clientside callback for instant
        feedback *plus* the server's authoritative value — was rejected because
        two writers to one Output need ``allow_duplicate`` and produce
        last-writer-wins flicker on a callback whose paint is 1.5-31 s.
        """
        assert len(_entry_for(app, LABEL_OUTPUT)) == 1

    def test_slider_value_is_an_input_not_state(self, app):
        """THE finding. A State is read when something else fires; the slider
        moving must itself be the trigger."""
        entry = _label_entry(app)
        assert SLIDER_VALUE in _pairs(entry["inputs"]), f"{LABEL_OUTPUT} does not take the depth slider as an Input — " "moving the slider cannot update the label (F-CANOPY-042 defect A)"
        assert SLIDER_VALUE not in _pairs(entry.get("state")), "the slider's value must be an Input, not State"

    def test_topology_store_is_also_an_input(self, app):
        """The label is a function of both operands of the filter. A cascade_add
        changes the denominator with no user action at all, so the store has to
        trigger it too."""
        assert TOPOLOGY_STORE in _pairs(_label_entry(app)["inputs"])

    def test_bounds_sync_no_longer_writes_the_label(self, app):
        """The split is the fix. While the label shared a callback with
        ``-depth-slider.value``, no Input on the slider could be added."""
        bounds = _entry_for(app, f"{COMPONENT_ID}-depth-slider.max")
        assert len(bounds) == 1, "the slider bounds-sync callback is missing"
        assert LABEL_OUTPUT not in str(bounds[0]["output"]), "the bounds-sync callback still owns the label — that is the wiring that made " "the label follow the topology instead of the slider"

    def test_no_callback_both_reads_and_writes_the_slider_value(self, app):
        """The constraint that made the naive fix impossible, pinned so a future
        'simplification' that merges these two callbacks back together fails
        here instead of at Dash registration in production."""
        for entry in _callback_list(app):
            outputs = str(entry.get("output", ""))
            if f"{COMPONENT_ID}-depth-slider.value" in outputs:
                assert SLIDER_VALUE not in _pairs(entry["inputs"]), "a callback has -depth-slider.value as both Input and Output — " "Dash rejects this as a circular dependency"

    def test_label_is_clientside(self, app):
        """Option A2 — routing the label out of the rebuild, which already
        computes it — was rejected because it puts a text readout behind that
        callback's measured 1.5-31 s paint (F-CANOPY-037 / -039 / -043). The
        number under the user's thumb would update seconds after the drag."""
        assert _label_entry(app).get("clientside_function"), f"{LABEL_OUTPUT} is served by the server, not clientside"

    def test_label_is_not_an_output_of_the_graph_rebuild(self, app):
        """Same rejection, checked from the other side."""
        rebuilds = _entry_for(app, f"{COMPONENT_ID}-graph.figure")
        assert rebuilds, "the graph rebuild callback is missing"
        for entry in rebuilds:
            assert LABEL_OUTPUT not in str(entry["output"]), "the label must not ride on the starvation-prone rebuild"


def _label_js(app):
    """The registered clientside function for the label, located by its own hash.

    Matched through ``clientside_function["function_name"]`` rather than by
    grepping the inline scripts for a signature, so the lookup stays correct if
    another clientside callback is added.
    """
    fn = _label_entry(app).get("clientside_function")
    assert fn, "the label callback is not clientside"
    name = fn["function_name"]
    scripts = getattr(app, "_inline_scripts", None)
    assert scripts, "dash.Dash no longer exposes _inline_scripts — re-point this helper"
    hits = [s for s in scripts if name in s]
    assert len(hits) == 1, f"expected one inline script registering {name}, found {len(hits)}"
    return name, hits[0]


# (depth, hidden_units) — the grid deliberately straddles every boundary in the
# server guard: below zero, at zero, inside the range, at the top, and past it.
_CASES = [(depth, n) for n in (0, 1, 5, 40) for depth in (None, -1, 0, 1, 3, 4, 5, 20, 39, 40, 41, 99)]


def _oracle(depth, n_hidden):
    """The label the server filter would produce for the same operands."""
    topology = {"input_units": 2, "hidden_units": n_hidden, "output_units": 1, "connections": []}
    _, label = NetworkVisualizer._apply_hierarchy_filter(topology, depth, n_hidden)
    return label


def _args_in_registration_order(entry, depth, n_hidden):
    """Build the JS argument list from the callback's declared Inputs.

    Dash passes clientside arguments in Input order, so the harness must read
    that order off the registration rather than assume the signature. Without
    this, reordering the two Inputs would make every case here evaluate with
    swapped operands and fail for a reason that has nothing to do with the rule.
    """
    by_key = {
        f"{COMPONENT_ID}-depth-slider.value": depth,
        f"{COMPONENT_ID}-topology-store.data": {"hidden_units": n_hidden},
    }
    args = []
    for spec in entry["inputs"]:
        key = f"{spec['id']}.{spec['property']}"
        assert key in by_key, f"the label callback grew an Input this harness cannot supply: {key}"
        args.append(by_key[key])
    return args


@pytest.mark.unit
class TestF042ZeroSemantics:
    """Defect B. The label must never claim a filter the server is not applying."""

    def test_source_guard_transliterates_the_server_guard(self, app):
        """Backstop that runs everywhere, including without node.

        ``_apply_hierarchy_filter`` returns "all" when
        ``depth is None or depth <= 0 or depth >= n_hidden_total or n_hidden_total == 0``.
        All four arms must be present clientside. The ``depth <= 0`` arm is the
        one the old rule lacked, and its absence is exactly what rendered
        ``"0 of 40"`` on an unfiltered 40-unit network.
        """
        _, script = _label_js(app)
        for arm in ("depth === null", "depth === undefined", "depth <= 0", "depth >= nHidden", "nHidden === 0"):
            assert arm in script, f"the clientside label guard is missing the `{arm}` arm of the server's rule"
        assert 'return "all"' in script

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers the rule")
    def test_clientside_label_agrees_with_the_server_filter(self, app, tmp_path):
        """Execute the registered JavaScript and compare it to the Python filter.

        This is the test the whole file exists for: the two implementations of
        one rule, driven over the same grid, asserted equal. Nothing here
        re-types the rule — the Python side is the oracle.
        """
        entry = _label_entry(app)
        name, script = _label_js(app)
        payload = [_args_in_registration_order(entry, depth, n) for depth, n in _CASES]
        driver = tmp_path / "label_rule.js"
        driver.write_text(
            "globalThis.window = globalThis.window || {};\n" + script + "\n" + f'const fn = window.dash_clientside["_dashprivate_clientside_funcs"]["{name}"];\n' + "const cases = JSON.parse(process.argv[2]);\n" + "console.log(JSON.stringify(cases.map(function(args) { return fn.apply(null, args); })));\n",
            encoding="utf-8",
        )
        proc = subprocess.run(  # nosec B603 - fixed interpreter, test-authored script
            [NODE, str(driver), json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, f"node failed: {proc.stderr}"
        got = json.loads(proc.stdout)
        assert len(got) == len(_CASES)

        mismatches = [(depth, n, actual, _oracle(depth, n)) for (depth, n), actual in zip(_CASES, got, strict=True) if actual != _oracle(depth, n)]
        assert not mismatches, "label disagrees with the server filter at: " + "; ".join(f"depth={d!r} hidden={n} label={a!r} filter={e!r}" for d, n, a, e in mismatches)

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers the rule")
    def test_zero_reads_all_on_a_loaded_network(self, app, tmp_path):
        """The at-rest defect, named on its own because it needs no gesture to
        see: the slider ships ``value=0``, so this is what the control says the
        moment a 40-unit network finishes loading."""
        entry = _label_entry(app)
        name, script = _label_js(app)
        args = _args_in_registration_order(entry, 0, 40)
        driver = tmp_path / "label_zero.js"
        driver.write_text(
            "globalThis.window = globalThis.window || {};\n" + script + "\n" + f'const fn = window.dash_clientside["_dashprivate_clientside_funcs"]["{name}"];\n' + f"console.log(JSON.stringify(fn.apply(null, {json.dumps(args)})));\n",
            encoding="utf-8",
        )
        proc = subprocess.run(  # nosec B603 - fixed interpreter, test-authored script
            [NODE, str(driver)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, f"node failed: {proc.stderr}"
        assert json.loads(proc.stdout) == "all", "a 40-unit network at slider 0 shows all 40 units; the label must say so"
        assert _oracle(0, 40) == "all", "the server filter's own answer, for comparison"


@pytest.mark.unit
class TestF042StaticDefaultsAgree:
    """The label's mount-time value and the slider's shipped value must not
    contradict each other before either callback has ever run."""

    def test_layout_default_label_matches_the_shipped_slider_value(self):
        """``children="all"`` beside ``value=0`` is only coherent under the
        decision that ``0`` means "all" — which is also what the filter does. If
        someone changes the slider's ``min`` to 1, this pairing needs revisiting.
        """
        visualizer = NetworkVisualizer({"show_weights": True}, component_id=COMPONENT_ID)
        layout = visualizer.get_layout()

        found = {}

        def walk(node):
            node_id = getattr(node, "id", None)
            if node_id == f"{COMPONENT_ID}-depth-label":
                found["label"] = getattr(node, "children", None)
            if node_id == f"{COMPONENT_ID}-depth-slider":
                found["min"] = getattr(node, "min", None)
                found["value"] = getattr(node, "value", None)
            children = getattr(node, "children", None)
            if isinstance(children, (list, tuple)):
                for child in children:
                    walk(child)
            elif children is not None and not isinstance(children, str):
                walk(children)

        walk(layout)
        assert found.get("label") == "all", "the label's static default must be the same 'all' the filter produces"
        assert found.get("min") == 0 and found.get("value") == 0, "the slider still ships min=0/value=0, so 0 must mean 'all' — " "if that changed, the static label default has to change with it"
        assert _oracle(found["value"], 40) == "all"
