#!/usr/bin/env python
"""F-CANOPY-042 complementary: execute the slider bounds-sync clientside callback.

PR #570 already pins the *label* half — wiring plus a node-executed rule compared
to ``_apply_hierarchy_filter``. Those tests never run the bounds-sync function
that the same fix split off (four Outputs → three). ``test_network_visualizer.py``
only greps ``currentValue`` / ``display: none``.

That JS is the other half of the control: it sets ``max``, preserves or snaps
``value``, and hides the container when there is nothing to filter. Registration
and the function body can drift independently — Dash will serve a three-Output
callback whose JS still returns a fourth element (the old label), or a body that
snaps the shipped ``value=0`` to ``nHidden`` and jumps the thumb the moment a
network loads. Neither failure is visible to the label-oracle suite.

WHY THESE TESTS ARE SHAPED THIS WAY.

Same layering as ``test_f042_depth_filter_label.py``, pointed at the *other*
callback:

1. **Wiring** against ``app._callback_list`` after a real ``register_callbacks``.
   Slider ``value`` must stay State (the constraint that forced the split): if it
   became an Input, Dash would reject the callback as circular because this
   function also *writes* ``-depth-slider.value``.
2. **The rule** by executing the registered JavaScript under node. Nothing here
   re-types the snap/preserve/hide logic — the cases name the product contract.
3. A **source-level backstop** so a node skip cannot leave the 4→3 arity change
   uncovered.

Falsified against parent ``ee2ec79``: the bounds-sync JS still returns four
elements and still computes ``var label``. Do not merge these into
``test_f042_depth_filter_label.py`` — that file owns the label writer.
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

SLIDER_MAX = f"{COMPONENT_ID}-depth-slider.max"
SLIDER_VALUE = (f"{COMPONENT_ID}-depth-slider", "value")
SLIDER_VALUE_OUTPUT = f"{COMPONENT_ID}-depth-slider.value"
CONTAINER_STYLE = f"{COMPONENT_ID}-depth-slider-container.style"
LABEL_OUTPUT = f"{COMPONENT_ID}-depth-label.children"
TOPOLOGY_STORE = (f"{COMPONENT_ID}-topology-store", "data")

NODE = shutil.which("node") or shutil.which("nodejs")


@pytest.fixture
def app():
    """A Dash app with the real callbacks registered."""
    visualizer = NetworkVisualizer({"show_weights": True, "layout": "hierarchical"}, component_id=COMPONENT_ID)
    dash_app = Dash(__name__)
    dash_app.layout = html.Div([dcc.Graph(id=f"{COMPONENT_ID}-graph")])
    visualizer.register_callbacks(dash_app)
    return dash_app


def _callback_list(app):
    entries = getattr(app, "_callback_list", None)
    assert entries, "dash.Dash no longer exposes _callback_list — these tests need re-pointing, not deleting"
    return entries


def _entry_for(app, output_key):
    return [c for c in _callback_list(app) if output_key in str(c.get("output", ""))]


def _pairs(entries_key):
    return [(e["id"], e["property"]) for e in entries_key or []]


def _bounds_entry(app):
    matches = _entry_for(app, SLIDER_MAX)
    assert len(matches) == 1, f"expected exactly one callback writing {SLIDER_MAX}, found {len(matches)}"
    return matches[0]


def _bounds_js(app):
    """The registered clientside function for bounds-sync, located by its hash."""
    fn = _bounds_entry(app).get("clientside_function")
    assert fn, "the bounds-sync callback is not clientside"
    name = fn["function_name"]
    scripts = getattr(app, "_inline_scripts", None)
    assert scripts, "dash.Dash no longer exposes _inline_scripts — re-point this helper"
    hits = [s for s in scripts if name in s]
    assert len(hits) == 1, f"expected one inline script registering {name}, found {len(hits)}"
    return name, hits[0]


def _args_in_registration_order(entry, topology, current_value):
    """Build the JS argument list from declared Inputs then State.

    Dash concatenates Input args then State args. The harness must read that
    order off the registration rather than assume ``(topology, currentValue)``.
    """
    by_key = {
        f"{COMPONENT_ID}-topology-store.data": topology,
        f"{COMPONENT_ID}-depth-slider.value": current_value,
    }
    args = []
    for spec in list(entry.get("inputs") or []) + list(entry.get("state") or []):
        key = f"{spec['id']}.{spec['property']}"
        assert key in by_key, f"the bounds-sync callback grew a dependency this harness cannot supply: {key}"
        args.append(by_key[key])
    return args


def _run_bounds(app, tmp_path, cases):
    """Execute the registered bounds-sync function once for each arg list."""
    entry = _bounds_entry(app)
    name, script = _bounds_js(app)
    payload = [_args_in_registration_order(entry, topology, value) for topology, value in cases]
    driver = tmp_path / "bounds_sync.js"
    driver.write_text(
        "globalThis.window = globalThis.window || {};\n"
        + script
        + "\n"
        + f'const fn = window.dash_clientside["_dashprivate_clientside_funcs"]["{name}"];\n'
        + "const cases = JSON.parse(process.argv[2]);\n"
        + "console.log(JSON.stringify(cases.map(function(args) { return fn.apply(null, args); })));\n",
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
    assert len(got) == len(cases)
    return got


@pytest.mark.unit
class TestF042BoundsSyncWiring:
    """The split is the fix. This callback writes the slider; it cannot also read it as Input."""

    def test_bounds_sync_writes_exactly_three_outputs(self, app):
        """Four Outputs was the wiring that owned the label. Three is the split."""
        entry = _bounds_entry(app)
        outputs = str(entry.get("output", ""))
        assert SLIDER_MAX in outputs
        assert SLIDER_VALUE_OUTPUT in outputs
        assert CONTAINER_STYLE in outputs
        assert LABEL_OUTPUT not in outputs
        # Dash records a multi-output as a list; pin the count so a silent
        # fourth Output (not the label id) still fails here.
        raw = entry.get("output")
        if isinstance(raw, list):
            assert len(raw) == 3, f"bounds-sync grew an extra Output: {raw}"

    def test_slider_value_is_state_not_input(self, app):
        """THE constraint that made the naive label fix impossible.

        This callback *writes* ``-depth-slider.value``. If that property were
        also an Input, Dash would reject the registration as circular — the
        same rejection that forced the label into its own callback.
        """
        entry = _bounds_entry(app)
        assert SLIDER_VALUE in _pairs(entry.get("state")), "bounds-sync must read the slider value as State so it can write it"
        assert SLIDER_VALUE not in _pairs(entry.get("inputs")), "bounds-sync has -depth-slider.value as Input — Dash rejects Input+Output on one property"

    def test_topology_store_is_the_trigger(self, app):
        """A cascade_add changes hidden_units; the slider max has to follow."""
        assert TOPOLOGY_STORE in _pairs(_bounds_entry(app)["inputs"])

    def test_bounds_sync_is_clientside(self, app):
        assert _bounds_entry(app).get("clientside_function"), f"{SLIDER_MAX} is served by the server, not clientside"


@pytest.mark.unit
class TestF042BoundsSyncSourceBackstop:
    """Runs everywhere, including without node."""

    def test_bounds_sync_no_longer_computes_a_label(self, app):
        """Parent ``ee2ec79`` still has ``var label = (v === nHidden) ? "all" ...``.

        That fourth return was Defect A's writer. The label callback owns the
        string now; if this body starts computing it again the two will drift.
        """
        _, script = _bounds_js(app)
        assert "var label" not in script, "bounds-sync still computes a label — that is the pre-split body"
        assert '"all"' not in script, "bounds-sync still returns the label string 'all'"


@pytest.mark.unit
class TestF042BoundsSyncRule:
    """Execute the registered JavaScript. The product contract, not a re-typed copy."""

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers the arity")
    def test_every_path_returns_exactly_three_elements(self, app, tmp_path):
        """Registration is three Outputs. The body must match on every path.

        Parent returns four (the label). A future edit that restores the fourth
        element would pass the wiring tests and fail only at Dash runtime.
        """
        cases = [
            (None, 0),
            ({"hidden_units": 0}, 0),
            ({"hidden_units": 40}, 0),
            ({"hidden_units": 40}, 20),
            ({"hidden_units": 40}, 40),
            ({"hidden_units": 40}, 99),
            ({"hidden_units": 40}, None),
        ]
        for result in _run_bounds(app, tmp_path, cases):
            assert isinstance(result, list), f"bounds-sync must return a list, got {type(result)}"
            assert len(result) == 3, f"bounds-sync must return 3 elements (max, value, style), got {len(result)}: {result}"

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers the hide paths")
    def test_missing_or_empty_topology_hides_the_slider(self, app, tmp_path):
        """No hidden units → no useful filter. The container must not stay visible."""
        results = _run_bounds(
            app,
            tmp_path,
            [
                (None, 7),
                ({}, 7),
                ({"hidden_units": 0}, 7),
            ],
        )
        for result in results:
            max_val, value, style = result
            assert max_val == 0
            assert value == 0
            assert style.get("display") == "none", f"empty topology must hide the slider, got {style}"

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers preserve-0")
    def test_shipped_zero_is_preserved_on_a_loaded_network(self, app, tmp_path):
        """The at-rest pairing: slider ships ``value=0``, topology arrives with 40.

        Snapping 0 → 40 would jump the thumb the moment the network loads. The
        filter and the label both read 0 as "all", so the value must stay 0.
        """
        result = _run_bounds(app, tmp_path, [({"hidden_units": 40}, 0)])[0]
        max_val, value, style = result
        assert max_val == 40
        assert value == 0, "snapping the shipped 0 to nHidden jumps the thumb on load (F-CANOPY-042 rest state)"
        assert style.get("display") == "block"

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers preserve")
    def test_in_range_value_survives_a_grow(self, app, tmp_path):
        """A focus on the first 20 units must not reset when cascade_add grows the max."""
        result = _run_bounds(app, tmp_path, [({"hidden_units": 41}, 20)])[0]
        max_val, value, style = result
        assert max_val == 41
        assert value == 20
        assert style.get("display") == "block"

    @pytest.mark.skipif(NODE is None, reason="node is not installed; source backstop above still covers snap")
    def test_out_of_range_and_unset_snap_to_max(self, app, tmp_path):
        """``v > nHidden`` or unset → snap to the new max (= show all)."""
        results = _run_bounds(
            app,
            tmp_path,
            [
                ({"hidden_units": 40}, 99),
                ({"hidden_units": 40}, None),
            ],
        )
        for result in results:
            max_val, value, style = result
            assert max_val == 40
            assert value == 40
            assert style.get("display") == "block"
