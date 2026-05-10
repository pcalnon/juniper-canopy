"""Issue #1 smoke: typed value reaches the backend on Apply.

Pre-fix this would silently drop newly-added params; the post-fix adapter
surfaces the value on ``GET /api/state``. We don't intercept the
server-side ``POST /api/set_params`` from the Dash callback because that
request is server-internal (Dash callback runs in the canopy process and
``requests.post`` to ``/api/set_params`` from there never crosses the
browser network) — instead we read back through ``/api/state``, which
is what the user actually observes.

PR-10 root-cause note. The xfail below pins a real harness-level
incompatibility, not a Dash callback bug:

  * The Apply click DOES fire the Dash apply callback (verified via
    ``_dash-update-component`` request capture).
  * BUT the State payload sent to the callback contains
    ``"nn-learning-rate-input": null`` even when the DOM input element
    shows ``"0.0123"`` after Playwright's ``fill()``.

Tried fixes (none worked):

  * ``page.fill()`` + Tab
  * ``page.type()`` with per-keystroke delay + Tab
  * React-friendly ``HTMLInputElement.prototype.value`` setter +
    ``input``/``change`` event dispatch
  * Slow keystroke typing with 2 s post-typing settle
  * ``Locator.click(force=True)`` / ``dispatch_event('click')`` /
    ``evaluate('el.click()')``

Inputs that aren't touched by Playwright show their initial values in
the State block, so the bug is specifically "Playwright value-set
does not propagate to Dash's React-controlled ``dbc.Input(type=number)``
internal state". Manual browser sessions work end-to-end.

Track-and-fix separately (likely needs Dash component-level work or a
``pytest-dash`` style harness that drives Dash's own clientside
callbacks). For now this xfail documents the harness gap.
"""

import time

import pytest
import requests


@pytest.mark.ui
@pytest.mark.xfail(
    strict=True,
    reason="Harness-level: Playwright fills DOM but Dash dbc.Input(type=number) never "
    "sees the React onChange — apply callback receives State value=null. PR-10 "
    "investigation confirmed: Apply click DOES fire the callback (visible in "
    "_dash-update-component requests); the State payload itself is wrong. "
    "Tried fill/type/React-setter/long-wait — none propagate. Manual browser "
    "sessions work. Remove xfail when the harness can drive React-controlled "
    "Dash inputs (likely via dash[testing] / pytest-dash).",
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
