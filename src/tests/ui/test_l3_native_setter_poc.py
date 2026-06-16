"""L3 POC #2 — committed reproducible proof that the corrected Playwright
native-value-setter does NOT drive Dash's React-controlled ``dbc.Input(type=number)``.

This is the reproducible artifact behind the audit doc's §5.3 / §6 claim
(`juniper-ml/notes/JUNIPER_CANOPY_AUDIT_REGRESSIONS_AND_MODEL_SELECTION_2026-06-15.md`).
It is a **strict xfail**: the assertion that the set value reaches the backend
is expected to FAIL (Apply pushes the *default*, not the set value), proving the
POC #2 wall empirically and continuously. If a future Dash/dbc release fixes the
synthetic-event path, this flips to XPASS and the strict marker fails the suite —
a canary telling us the un-xfail (and dropping the dash_duo follow-up) is now
possible.

Mechanism under test (papers/react-controlled-input-onchange.md): native
``HTMLInputElement.prototype.value`` setter (bypassing React's value-tracker) +
**bubbling** ``input``+``change`` dispatch + blur + 350 ms debounce wait — the
canonical React workaround. It works for plain React inputs but ``dbc.Input``
(dash-bootstrap-components) has its own value-tracking that swallows the
synthetic event, so the Dash callback ``State`` never updates.

Companion to ``test_apply_button_flow.py`` (which proves the same wall via
``page.fill()``); this file pins the *corrected native-setter* specifically.
"""

import time

import pytest
import requests


def _set_dash_number(page, selector, value):
    """Native-prototype-setter + bubbling events: the canonical React workaround."""
    page.eval_on_selector(
        selector,
        """(el, value) => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, value);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        str(value),
    )


@pytest.mark.ui
@pytest.mark.xfail(
    strict=True,
    reason="L3 POC #2: the corrected native-value-setter (native prototype setter " "+ bubbling input+change+blur+debounce) does not propagate into dbc.Input's " "React State — Apply pushes the default, not the set value. dbc.Input's own " "value-tracking swallows the synthetic event. Un-xfail path is dash_duo " "(Selenium send_keys); see the audit doc §5.3. XPASS here = Dash fixed it.",
)
def test_native_setter_does_not_reach_backend(dashboard_page, canopy_url):
    typed = 0.0123

    dashboard_page.wait_for_selector("#nn-learning-rate-input", timeout=15_000)
    _set_dash_number(dashboard_page, "#nn-learning-rate-input", typed)
    dashboard_page.locator("#nn-learning-rate-input").press("Tab")
    dashboard_page.wait_for_timeout(700)  # > 350 ms debounce + callback chain

    dashboard_page.click("#apply-params-button")

    deadline = time.time() + 8
    last = None
    while time.time() < deadline:
        r = requests.get(f"{canopy_url}/api/state", timeout=2)
        r.raise_for_status()
        last = r.json().get("nn_learning_rate")
        if last == pytest.approx(typed):
            return  # would mean the wall is gone -> strict xfail flips to XPASS
        time.sleep(0.25)

    # Expected outcome (xfail): the native-setter value never reached the Dash
    # State, so Apply pushed the default and /api/state never shows `typed`.
    assert last == pytest.approx(typed), f"native-setter did not propagate; /api/state nn_learning_rate={last} (expected the set {typed})"
