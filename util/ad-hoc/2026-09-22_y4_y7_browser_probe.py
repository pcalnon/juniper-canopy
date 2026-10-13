#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     2026-09-22_y4_y7_browser_probe.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-09-22
# Last Modified: 2026-09-22
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Y4 / Y7 -- observe, in a real browser, what the unit
#                tests can only infer: where the active tab lands after
#                a one-shot rebuild, and what the model table's Select
#                buttons expose to the accessibility tree.
#####################################################################
"""Real-browser probe for Y4 (stranded active tab) and Y7 (Select-button description).

Project: juniper-canopy
Sub-Project: ad-hoc tooling
Author: Paul Calnon
Created: 2026-09-22
Status: ad-hoc -- investigation
Retire when: the Y4 / Y7 / Y8 PR has merged and a live E2E pass has re-observed both
Related: selection-reachability arc, handoff items 16 and 21; design §4.3 (Y7)

Boots canopy in demo mode from ``<repo>/src`` on a free port, drives the dashboard in headless
chromium, prints one JSON line per observation, and always terminates the server. Run it against
two checkouts (before / after) and diff the lines.

* **Y4** -- click Network Topology, flip ``model-class-store`` to ``one_shot`` (demo mode has no
  recurrence service, so the flip is driven with ``dash_clientside.set_props``), and read the
  highlighted tab, the number of visible panes and the persisted ``layout-state-store``. Then the
  reload path: persist ``topology``, reload, flip again.
* **Y7** -- open the model-selection modal at ``spirals`` and at ``⊥``, and read each Select
  button's DOM plus its accessible name / description from ``Accessibility.getFullAXTree``. At
  ``⊥`` it also clicks an enabled Select, proving the button still drives the pattern-matching
  selection callback.

Traps this probe had to route around (see the juniper-ml memory index): a mount-time
``hydrate_model_class`` can retire a ``set_props`` rebuild, so the flip waits for the mount to
settle and retries once; canopy's DOM is never "stable", so clicks are ``force=True``.

Usage (the env must not see rust_mudgeon's libtorch)::

    LIBTORCH= LD_LIBRARY_PATH= python util/ad-hoc/2026-09-22_y4_y7_browser_probe.py [<repo-root>]
"""

from __future__ import annotations

import json
import os
import socket
import subprocess  # nosec B404 -- starts this repo's own server for the probe
import sys
import tempfile
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
SRC = REPO / "src"

SELECT_BUTTONS_JS = """() => Array.from(document.querySelectorAll('#model-selection-table-container button')).map(b => {
    const ref = b.getAttribute('aria-describedby');
    const target = ref ? document.getElementById(ref) : null;
    return {
        outer: b.outerHTML,
        describedby: ref,
        describedbyTargetText: target ? target.textContent : null,
        describedbyTargetInSameTable: target ? b.closest('table') === target.closest('table') : null,
        title: b.getAttribute('title'),
        disabled: b.disabled,
        pointerEvents: getComputedStyle(b).pointerEvents,
        className: b.className,
    };
})"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def report(label, value) -> None:
    print(json.dumps({"probe": label, "value": value}, ensure_ascii=False), flush=True)


def active_tab_label(page):
    return page.evaluate("() => { const a = document.querySelector('#visualization-tabs .nav-link.active'); return a ? a.textContent : null; }")


def tab_labels(page):
    return page.evaluate("() => Array.from(document.querySelectorAll('#visualization-tabs .nav-link')).map(a => a.textContent)")


def visible_pane_count(page):
    return page.evaluate("() => document.querySelectorAll('.tab-content > .tab-pane.active').length")


def stored_layout_state(page):
    return page.evaluate("() => localStorage.getItem('layout-state-store')")


def wait_until(page, predicate_js, timeout_ms=60000) -> None:
    page.wait_for_function(predicate_js, timeout=timeout_ms)


def wait_for_mount_settled(page) -> None:
    """Mirror src/tests/ui/conftest.py: params-init-interval has fired and its writes settled."""
    page.wait_for_timeout(1500)
    page.wait_for_function(
        """() => {
            const el = document.getElementById('nn-learning-rate-input');
            if (!el) return false;
            const now = Date.now();
            if (window.__probeLastValue !== el.value) { window.__probeLastValue = el.value; window.__probeLastChangeAt = now; return false; }
            return now - window.__probeLastChangeAt > 300;
        }""",
        timeout=60000,
    )
    page.wait_for_timeout(3000)


def flip_model_class(page, value: str, expected_tabs: int) -> int:
    """``set_props`` the model class; retry once if a mount-time hydrate retired the rebuild."""
    for attempt in range(2):
        page.evaluate(f"() => window.dash_clientside.set_props('model-class-store', {{data: '{value}'}})")
        try:
            wait_until(page, f"() => document.querySelectorAll('#visualization-tabs .nav-link').length === {expected_tabs}", timeout_ms=45000)
            return attempt
        except Exception:  # noqa: BLE001 -- a timeout here is the retry signal
            report(f"flip_model_class.{value}.attempt{attempt}.timeout", len(tab_labels(page)))
    raise RuntimeError(f"model class {value} never produced {expected_tabs} tabs")


def ax_select_buttons(cdp, tag: str) -> None:
    for node in cdp.send("Accessibility.getFullAXTree").get("nodes", []):
        role = (node.get("role") or {}).get("value")
        name = (node.get("name") or {}).get("value")
        if role == "button" and name in ("Select", "Selected"):
            description = (node.get("description") or {}).get("value")
            props = {p.get("name"): (p.get("value") or {}).get("value") for p in node.get("properties", [])}
            report(f"{tag}.ax.button", {"name": name, "description": description, "disabled": props.get("disabled")})


def probe(page, context) -> None:
    wait_until(page, "() => document.querySelectorAll('#visualization-tabs .nav-link').length >= 15")
    wait_for_mount_settled(page)
    report("mount.tabs", len(tab_labels(page)))
    report("mount.active", active_tab_label(page))

    # ---- Y4, runtime path: on a cascade-only tab, the model class flips to one_shot.
    page.get_by_role("tab", name="Network Topology", exact=True).click(force=True)
    page.wait_for_timeout(1500)
    report("y4.before_swap.active", active_tab_label(page))
    report("y4.before_swap.store", stored_layout_state(page))
    flip_model_class(page, "one_shot", 10)
    page.wait_for_timeout(2500)
    report("y4.after_swap.tabs", tab_labels(page))
    report("y4.after_swap.active", active_tab_label(page))
    report("y4.after_swap.visible_panes", visible_pane_count(page))
    report("y4.after_swap.store", stored_layout_state(page))

    flip_model_class(page, "live", 15)
    page.wait_for_timeout(2500)
    report("y4.back_to_live.active", active_tab_label(page))
    report("y4.back_to_live.store", stored_layout_state(page))

    # ---- Y4, reload path: a persisted cascade tab, then the one_shot rebuild.
    page.evaluate("() => localStorage.setItem('layout-state-store', JSON.stringify({active_tab: 'topology'}))")
    page.reload()
    wait_until(page, "() => document.querySelectorAll('#visualization-tabs .nav-link').length >= 15")
    wait_for_mount_settled(page)
    report("y4.reload.active_before_one_shot", active_tab_label(page))
    flip_model_class(page, "one_shot", 10)
    page.wait_for_timeout(2500)
    report("y4.reload.after_one_shot.active", active_tab_label(page))
    report("y4.reload.after_one_shot.visible_panes", visible_pane_count(page))
    report("y4.reload.after_one_shot.store", stored_layout_state(page))

    # ---- Y7 at the default dataset (spirals): recurrence is incompatible, so its Select is greyed.
    page.locator("#nn-model-change-button").click(force=True)
    wait_until(page, "() => document.querySelectorAll('#model-selection-table-container button').length >= 2")
    page.wait_for_timeout(500)
    for index, info in enumerate(page.evaluate(SELECT_BUTTONS_JS)):
        report(f"y7.spirals.button[{index}]", info)
    cdp = context.new_cdp_session(page)
    ax_select_buttons(cdp, "y7.spirals")
    page.locator("#model-selection-modal-close").click(force=True)
    page.wait_for_timeout(1000)

    # ---- Y7 at ⊥: every Select is enabled; click one to prove it still drives selection.
    page.evaluate("() => window.dash_clientside.set_props('nn-dataset-type-dropdown', {value: null})")
    page.wait_for_timeout(1500)
    page.locator("#nn-model-change-button").click(force=True)
    wait_until(page, "() => document.querySelectorAll('#model-selection-table-container button').length >= 2")
    page.wait_for_timeout(800)
    for index, info in enumerate(page.evaluate(SELECT_BUTTONS_JS)):
        report(f"y7.bottom.button[{index}]", info)
    ax_select_buttons(cdp, "y7.bottom")
    report("y7.bottom.summary_before", page.evaluate("() => { const e = document.getElementById('nn-model-summary'); return e ? e.textContent : null; }"))
    page.locator("#model-selection-table-container button:not([disabled])", has_text="Select").filter(has_not_text="Selected").first.click(force=True)
    wait_until(page, "() => { const m = document.getElementById('model-selection-modal'); return !m || !m.classList.contains('show'); }", timeout_ms=30000)
    page.wait_for_timeout(1500)
    report("y7.bottom.summary_after_select", page.evaluate("() => { const e = document.getElementById('nn-model-summary'); return e ? e.textContent : null; }"))


def main() -> int:
    port = free_port()
    env = {
        **os.environ,
        "JUNIPER_CANOPY_DEMO_MODE": "1",
        "JUNIPER_CANOPY_SERVER__HOST": "127.0.0.1",
        "JUNIPER_CANOPY_SERVER__PORT": str(port),
        "PYTHONPATH": f"{SRC}{os.pathsep}{os.environ.get('PYTHONPATH', '')}",
    }
    base = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, str(SRC / "main.py")], env=env, stdout=log, stderr=subprocess.STDOUT, cwd=str(REPO))  # nosec B603 -- fixed argv, this repo
        try:
            deadline = time.time() + 60
            while time.time() < deadline:
                if proc.poll() is not None:
                    log.seek(0)
                    print(log.read()[-4000:], file=sys.stderr)
                    raise RuntimeError(f"canopy exited early: {proc.returncode}")
                try:
                    if requests.get(f"{base}/v1/health/ready", timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    pass  # not listening yet; keep polling until the 60 s deadline below
                time.sleep(0.25)
            else:
                raise RuntimeError("canopy not ready in 60s")
            report("repo", str(REPO))
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                context = browser.new_context()
                page = context.new_page()
                page.add_init_script("localStorage.setItem('juniper_canopy_welcomed', '1');")
                page.goto(f"{base}/dashboard/")
                probe(page, context)
                browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
