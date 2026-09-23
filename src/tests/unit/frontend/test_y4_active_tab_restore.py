#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     test_y4_active_tab_restore.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Y4 — the active-tab restore must never leave the
#                dashboard on a tab the one-shot suppression removed.
#                Executes the REGISTERED clientside function under node.
#####################################################################
"""Y4: a model swap must not strand ``visualization-tabs.active_tab`` on a deleted tab.

``suppress_cascade_tabs`` rebuilds the tab bar without the five cascade-only tabs when a one-shot
model is active. The restore callback used to guard only "no saved tab" and "saved == shown", so:

* **runtime** — on Network Topology, a swap to a one-shot model removed the tab and nothing moved
  the selection off it;
* **reload** — a persisted cascade tab was restored at mount (full tab list), and then the one-shot
  rebuild removed it underneath.

Measured in headless chromium against the unmodified tree, both ended with **no tab highlighted and
zero visible panes** — dbc 2.0.4 renders nothing for an ``active_tab`` that names no child.

WHY THESE TESTS ARE SHAPED THIS WAY (the ``test_f042_depth_slider_bounds.py`` layering):

1. **Wiring** against ``app._callback_list`` after a real ``DashboardManager`` build. The rendered
   tabs must be an Input; as State the check would run once at mount, before the rebuild.
2. **The rule**, by executing the registered JavaScript under node against the tab lists exactly as
   Dash serialises them to the browser (``to_json_plotly`` of ``_visible_tabs``). Nothing here
   re-types the rule; the cases name the product contract.
3. The source-level backstop lives with the existing coverage of this callback,
   ``tests/unit/test_dashboard_manager.py::TestLayoutStatePersistence``, so a node skip cannot leave
   the fix uncovered.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from plotly.io.json import to_json_plotly

_SRC = Path(__file__).resolve().parents[3]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from frontend.dashboard_manager import _CASCADE_ONLY_TAB_IDS, DashboardManager  # noqa: E402

NODE = shutil.which("node") or shutil.which("nodejs")
NO_UPDATE = "__dash_no_update__"

ACTIVE_TAB = "visualization-tabs.active_tab"
STORE = "layout-state-store.data"
TABS = "visualization-tabs.children"
DEFAULT_TAB = "metrics"


@pytest.fixture(scope="module")
def manager():
    return DashboardManager({})


@pytest.fixture(scope="module")
def tab_lists(manager):
    """Both tab bars exactly as Dash serialises them to the browser."""
    return {model_class: json.loads(to_json_plotly(manager._visible_tabs(model_class))) for model_class in ("live", "one_shot")}


@pytest.fixture(scope="module")
def rendered_ids(tab_lists):
    return {model_class: [tab["props"]["tab_id"] for tab in tabs] for model_class, tabs in tab_lists.items()}


def _keys(specs):
    return [f"{spec['id']}.{spec['property']}" for spec in specs or []]


def _restore_entry(manager):
    entries = getattr(manager.app, "_callback_list", None)
    assert entries, "dash.Dash no longer exposes _callback_list — these tests need re-pointing, not deleting"
    matches = [entry for entry in entries if ACTIVE_TAB in str(entry.get("output", "")) and STORE in _keys(entry.get("inputs"))]
    assert len(matches) == 1, f"expected exactly one restore callback writing {ACTIVE_TAB}, found {len(matches)}"
    return matches[0]


def _run_restore(manager, tab_lists, tmp_path, cases):
    """Execute the registered restore function once per ``(saved_state, tab_list_key, shown_tab)``.

    ``tab_list_key`` is ``"live"``, ``"one_shot"`` or ``None`` (no readable tab list). The tab lists
    travel once, in a file — each is ~100 KB, near the 128 KB per-argument limit.
    """
    entry = _restore_entry(manager)
    function = entry.get("clientside_function")
    assert function, "the restore callback is not clientside"
    name = function["function_name"]
    scripts = [script for script in getattr(manager.app, "_inline_scripts", None) or [] if name in script]
    assert len(scripts) == 1, f"expected one inline script registering {name}, found {len(scripts)}"
    # Dash passes Input values then State values; read that order off the registration rather than
    # assuming (state, tabs, currentTab).
    order = _keys(entry.get("inputs")) + _keys(entry.get("state"))
    assert sorted(order) == sorted([STORE, TABS, ACTIVE_TAB]), f"the restore callback grew a dependency this harness cannot supply: {order}"
    payload = tmp_path / "cases.json"
    payload.write_text(json.dumps({"order": order, "tabs": tab_lists, "cases": cases}), encoding="utf-8")
    driver = tmp_path / "restore.js"
    driver.write_text(
        f"globalThis.window = {{dash_clientside: {{no_update: {json.dumps(NO_UPDATE)}}}}};\n"
        + scripts[0]
        + "\n"
        + f'const fn = window.dash_clientside["_dashprivate_clientside_funcs"]["{name}"];\n'
        + "const data = JSON.parse(require('fs').readFileSync(process.argv[2], 'utf8'));\n"
        + "const results = data.cases.map(function(c) {\n"
        + f"  const byKey = {{{json.dumps(STORE)}: c[0], {json.dumps(TABS)}: c[1] === null ? null : data.tabs[c[1]], {json.dumps(ACTIVE_TAB)}: c[2]}};\n"
        + "  return fn.apply(null, data.order.map(function(k) { return byKey[k]; }));\n"
        + "});\n"
        + "console.log(JSON.stringify(results));\n",
        encoding="utf-8",
    )
    proc = subprocess.run(  # nosec B603 - fixed interpreter, test-authored script
        [NODE, str(driver), str(payload)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"node failed: {proc.stderr}"
    results = json.loads(proc.stdout)
    assert len(results) == len(cases)
    return results


@pytest.mark.unit
class TestY4RestoreWiring:
    """The rendered tab list reaches the restore as an Input, and the writer count stays at two."""

    def test_the_rendered_tabs_are_an_input_not_state(self, manager):
        entry = _restore_entry(manager)
        assert TABS in _keys(entry.get("inputs")), "the restore must re-run when the tab bar is rebuilt"
        assert TABS not in _keys(entry.get("state")), "as State the check runs once, before the one-shot rebuild"

    def test_the_shown_tab_stays_state(self, manager):
        # An Input on the property this callback writes is a self-edge: the #1 tab-toggle loop.
        entry = _restore_entry(manager)
        assert ACTIVE_TAB in _keys(entry.get("state"))
        assert ACTIVE_TAB not in _keys(entry.get("inputs"))

    def test_the_reset_adds_no_active_tab_writer(self, manager):
        """The fix lives in the Store-restore writer so that the reset adds no writer.

        Census of the BUILT app, identified by trigger. It is three, not the two that
        ``test_single_mount_time_active_tab_restore`` counts: that test reads
        ``dashboard_manager.py`` only, and ``hdf5_snapshots_panel``'s replay hand-off (CAN-015f)
        writes ``active_tab`` too. Counting one file's source is how the third went unseen.
        """
        writers = [entry for entry in manager.app._callback_list if ACTIVE_TAB in str(entry.get("output", ""))]
        triggers = sorted(tuple(sorted(_keys(entry.get("inputs")))) for entry in writers)
        assert triggers == sorted(
            [
                ("context-menu-tutorial-trigger.data",),
                ("hdf5-snapshots-panel-restore-confirm.n_clicks",),
                tuple(sorted([STORE, TABS])),
            ]
        ), triggers
        # In particular the one-shot rebuild does not write the tab itself.
        assert not any("model-class-store.data" in _keys(entry.get("inputs")) for entry in writers)

    def test_the_restore_is_clientside(self, manager):
        assert _restore_entry(manager).get("clientside_function")


@pytest.mark.unit
@pytest.mark.skipif(NODE is None, reason="node is not installed; TestLayoutStatePersistence still pins the source shape")
class TestY4RestoreRule:
    """Execute the registered JavaScript. The product contract, not a re-typed copy."""

    def test_fixture_premise_metrics_leads_both_tab_bars(self, rendered_ids):
        # The fallback is "first rendered tab"; the contract below is that this is Training Metrics.
        assert rendered_ids["live"][0] == DEFAULT_TAB
        assert rendered_ids["one_shot"][0] == DEFAULT_TAB
        assert _CASCADE_ONLY_TAB_IDS <= set(rendered_ids["live"])
        assert not _CASCADE_ONLY_TAB_IDS & set(rendered_ids["one_shot"])

    def test_runtime_swap_off_a_cascade_tab_lands_on_metrics(self, manager, tab_lists, tmp_path):
        """The runtime strand: the store and the shown tab both name the tab the rebuild removed."""
        cases = [[{"active_tab": tab}, "one_shot", tab] for tab in sorted(_CASCADE_ONLY_TAB_IDS)]
        assert _run_restore(manager, tab_lists, tmp_path, cases) == [DEFAULT_TAB] * len(cases)

    def test_a_saved_tab_that_is_not_rendered_is_never_restored(self, manager, tab_lists, tmp_path):
        """The reload strand's other half: a stale cascade tab must not be pushed over a good one."""
        results = _run_restore(manager, tab_lists, tmp_path, [[{"active_tab": "topology"}, "one_shot", "parameters"], [{"active_tab": "workers"}, "one_shot", DEFAULT_TAB]])
        assert results == [NO_UPDATE, NO_UPDATE]

    def test_an_unknown_saved_tab_keeps_the_shown_tab(self, manager, tab_lists, tmp_path):
        assert _run_restore(manager, tab_lists, tmp_path, [[{"active_tab": "no-such-tab"}, "live", "parameters"]]) == [NO_UPDATE]

    def test_an_empty_store_still_rescues_a_stranded_tab(self, manager, tab_lists, tmp_path):
        results = _run_restore(manager, tab_lists, tmp_path, [[None, "one_shot", "topology"], [{}, "one_shot", "boundaries"], [None, "live", DEFAULT_TAB]])
        assert results == [DEFAULT_TAB, DEFAULT_TAB, NO_UPDATE]

    def test_cascade_tabs_still_restore_for_a_live_model(self, manager, tab_lists, tmp_path):
        """CAN-016a is unchanged where the tab exists: no over-correction for a live model."""
        cases = [[{"active_tab": tab}, "live", DEFAULT_TAB] for tab in sorted(_CASCADE_ONLY_TAB_IDS)]
        assert _run_restore(manager, tab_lists, tmp_path, cases) == sorted(_CASCADE_ONLY_TAB_IDS)

    def test_a_rendered_saved_tab_restores_under_one_shot(self, manager, tab_lists, tmp_path):
        assert _run_restore(manager, tab_lists, tmp_path, [[{"active_tab": "parameters"}, "one_shot", DEFAULT_TAB]]) == ["parameters"]

    def test_the_equality_guard_survives(self, manager, tab_lists, tmp_path):
        """#1 tab-feedback-loop: a store echo of the shown tab must not re-assert active_tab."""
        results = _run_restore(manager, tab_lists, tmp_path, [[{"active_tab": DEFAULT_TAB}, "live", DEFAULT_TAB], [{"active_tab": "dataset"}, "one_shot", "dataset"]])
        assert results == [NO_UPDATE, NO_UPDATE]

    def test_an_unreadable_tab_list_keeps_the_pre_y4_rule(self, manager, tab_lists, tmp_path):
        """If the tab list cannot be read, behave exactly as before Y4 — never worse than it."""
        results = _run_restore(manager, tab_lists, tmp_path, [[{"active_tab": "topology"}, None, DEFAULT_TAB], [{"active_tab": DEFAULT_TAB}, None, DEFAULT_TAB], [None, None, "topology"]])
        assert results == ["topology", NO_UPDATE, NO_UPDATE]

    def test_the_shown_tab_is_always_rendered_afterwards(self, manager, tab_lists, rendered_ids, tmp_path):
        """THE invariant, over every saved × shown × tab-bar combination.

        Whatever the store and the screen say, after this callback the shown tab is one the bar
        actually renders; a rendered saved tab that differs from the shown one is restored; and
        nothing is written when nothing needs to change.
        """
        all_ids = rendered_ids["live"]
        saved_values = [None, *all_ids, "no-such-tab"]
        cases = [[None if saved is None else {"active_tab": saved}, bar, shown] for bar in ("live", "one_shot") for saved in saved_values for shown in all_ids]
        results = _run_restore(manager, tab_lists, tmp_path, cases)
        for (state, bar, shown), result in zip(cases, results):
            rendered = rendered_ids[bar]
            saved = state["active_tab"] if state else None
            after = shown if result == NO_UPDATE else result
            assert after in rendered, (state, bar, shown, result)
            if saved in rendered and saved != shown:
                assert result == saved, (state, bar, shown, result)
            if shown in rendered and (saved == shown or saved not in rendered):
                assert result == NO_UPDATE, (state, bar, shown, result)
