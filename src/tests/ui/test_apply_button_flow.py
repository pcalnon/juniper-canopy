"""Issue #1 smoke: typed value reaches the backend on Apply.

Pre-fix this would silently drop newly-added params; the post-fix adapter
surfaces the value on ``GET /api/state``. We don't intercept the
server-side ``POST /api/set_params`` from the Dash callback because that
request is server-internal (Dash callback runs in the canopy process and
``requests.post`` to ``/api/set_params`` from there never crosses the
browser network) — instead we read back through ``/api/state``, which
is what the user actually observes.

RESOLVED 2026-08-14 — this was a PRODUCT bug, not a harness wall.

This test carried a ``strict`` xfail for months, attributed to Playwright
being unable to drive Dash's React-controlled ``dbc.Input(type=number)``.
That diagnosis was wrong, and the evidence that looked like a harness
limitation was the product defect reporting itself:

  * The Apply click DOES fire the callback, and the State payload really
    did contain ``"nn-learning-rate-input": null`` — both true.
  * But the null did not come from a swallowed React event. The widget
    declared ``min=0.0001, step=0.001``, and **HTML5 evaluates ``step``
    validity relative to ``min``**, so the only admissible values were
    ``0.0001 + n*0.001``. The probe ``0.0123`` is off that grid
    (``n = 12.2``) — ``el.validity.stepMismatch`` was true, an invalid
    number input reports no usable value, and Dash therefore received
    ``null``.
  * ``_apply_parameters_handler`` then substituted
    ``TrainingConstants.DEFAULT_LEARNING_RATE``. That is precisely the
    "Apply pushed the **default** 0.01, not the set 0.0123" observation
    recorded here on 2026-06-16 — the handler doing exactly what it was
    written to do, with a null it should never have been given.

Two details that made the misattribution so convincing, both explained by
the same cause:

  * "Inputs that aren't touched by Playwright show their initial values" —
    Dash seeds those through props, which bypasses the browser's
    validity-gated input path, so an untouched widget keeps a real value
    however off-grid it is.
  * "Manual browser sessions work end-to-end" — the spinner arrows snap to
    the step grid, so a human clicking them can only ever produce a valid
    value. Typing an arbitrary one by hand would have failed identically.

No harness change was needed. ``selenium``/``dash_duo`` would not have
fixed it either: real keystrokes hit the same grid. The fix (F-CANOPY-017)
gives float params ``step="any"`` and makes a ``None`` numeric State refuse
the apply instead of silently defaulting, so ``page.fill()`` propagates and
this test passes on its original code path.

We still don't intercept the server-side ``POST /api/set_params`` from the
Dash callback — that request is server-internal (the callback runs in the
canopy process and ``requests.post`` never crosses the browser network) —
so the assertion reads back through ``/api/state``, which is what the user
actually observes.
"""

import time

import pytest
import requests


@pytest.mark.ui
def test_apply_pushes_typed_learning_rate_into_backend(dashboard_page, canopy_url):
    # 0.0123 is deliberately kept from the xfail era: it is the exact probe
    # that used to arrive as the 0.01 default, and it is off the old
    # min=0.0001/step=0.001 grid. With step="any" it must now survive
    # verbatim, so this value is the regression guard for F-CANOPY-017.
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
