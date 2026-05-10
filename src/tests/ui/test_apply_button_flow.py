"""Issue #1 smoke: typed value reaches the backend on Apply.

Pre-fix this would silently drop newly-added params; the post-fix adapter
surfaces the value on ``GET /api/state``. We don't intercept the
server-side ``POST /api/set_params`` from the Dash callback because that
request is server-internal — instead we read back through ``/api/state``,
which is what the user actually observes.

Diagnostic note (PR-8): this test was xfail-pinned to PR-4/PR-5 (Issue #1
silent-drop). PR-5 closed the silent-drop and PR-8 closed the typing
debounce race, but a separate harness-level bug remains: clicking
``#apply-params-button`` in headless Playwright doesn't trigger the
apply callback's ``POST /api/set_params`` at all (network capture in
the PR-8 investigation showed only an unrelated ``metrics-panel-stats-
update-interval`` tick). Manual verification: filling the input then
clicking Apply in a real browser does fire the POST and the value
round-trips. Track-and-fix the harness gap separately; for now keep
the xfail with the corrected reason.
"""

import time

import pytest
import requests


@pytest.mark.ui
@pytest.mark.xfail(
    strict=True,
    reason="Harness-level: ``page.click('#apply-params-button')`` doesn't fire the " "Dash apply callback in headless chromium (no POST /api/set_params observed); " "manual browser sessions work. Separate from PR-8's debounce/blur fix. " "Investigate the Dash _dash-update-component dispatch for click-driven callbacks " "in Playwright; remove this xfail when fixed.",
)
def test_apply_pushes_typed_learning_rate_into_backend(dashboard_page, canopy_url):
    typed = 0.0123

    dashboard_page.wait_for_selector("#nn-learning-rate-input", timeout=15_000)
    dashboard_page.fill("#nn-learning-rate-input", str(typed))
    dashboard_page.locator("#nn-learning-rate-input").press("Tab")  # commit value
    # Give Dash's 350 ms debounce + callback chain time to propagate the
    # typed value into the applied-params-store before the Apply click
    # reads it. (PR-8 §2.5 C force-blur covers the click-without-tab case;
    # this wait protects the test from a fast-typist race.)
    dashboard_page.wait_for_timeout(500)

    dashboard_page.click("#apply-params-button")

    deadline = time.time() + 10
    last_value: float | None = None
    while time.time() < deadline:
        r = requests.get(f"{canopy_url}/api/state", timeout=2)
        r.raise_for_status()
        last_value = r.json().get("nn_learning_rate")
        if last_value == pytest.approx(typed):
            return
        time.sleep(0.25)

    pytest.fail(f"Apply did not push nn_learning_rate={typed} to backend within 10s; " f"last observed via /api/state: {last_value}")
