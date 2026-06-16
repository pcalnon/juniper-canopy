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
  * The *canonical* corrected native-setter (native prototype value
    setter + **bubbling** ``input``+``change`` + blur + 350 ms debounce
    wait — the documented React workaround in
    ``juniper-ml/papers/react-controlled-input-onchange.md``).
    Re-verified 2026-06-16: Apply pushed the **default** 0.01, not the
    set 0.0123, so ``dbc.Input``'s own value-tracking swallows the
    synthetic event just as it does ``el.value = x``.
  * Slow keystroke typing with 2 s post-typing settle
  * ``Locator.click(force=True)`` / ``dispatch_event('click')`` /
    ``evaluate('el.click()')``

Inputs that aren't touched by Playwright show their initial values in
the State block, so the bug is specifically "Playwright value-set
does not propagate to Dash's React-controlled ``dbc.Input(type=number)``
internal state". Manual browser sessions work end-to-end.

Resolution (L3 POC, 2026-06-16): the Playwright native-setter path
(POC #2) is a confirmed dead end for ``dbc.Input``. The working path is
``dash.testing``/``dash_duo`` (POC #1), which drives inputs via Selenium
``send_keys`` — real keystrokes that fire React's onChange natively — but
that needs ``selenium`` + ``multiprocess`` + ``chromedriver`` added to the
env plus its own ``make test-ui-dash`` job (deferred follow-up). The
Apply -> ``/api/set_params`` -> ``/api/state`` contract this test targets
is already proven deterministically by L2
(``test_control_manifest_behavioral`` ``apply-params-button`` row), so this
browser leg is a redundancy, not a coverage gap. This xfail documents the
harness wall.
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
    "Tried fill/type/React-setter/long-wait — none propagate. The corrected "
    "native-setter (bubbling input+change+blur+debounce; 2026-06-16) also fails: "
    "Apply pushes the default, not the set value. Manual browser sessions work. "
    "Un-xfail via dash[testing]/dash_duo (Selenium send_keys), which needs "
    "selenium+multiprocess+chromedriver added to the env (deferred follow-up).",
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
