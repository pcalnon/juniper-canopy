"""Issue #1 smoke: typed value reaches the backend on Apply.

Pre-fix this would silently drop newly-added params; the post-fix adapter
surfaces the value on ``GET /api/state``. We don't intercept the
server-side ``POST /api/set_params`` from the Dash callback because that
request is server-internal — instead we read back through ``/api/state``,
which is what the user actually observes.
"""

import time

import pytest
import requests


@pytest.mark.ui
@pytest.mark.xfail(
    strict=True,
    reason="Pinned by PR-4/PR-5 (Issue #1 — adapter silently drops nn_learning_rate). " "Will start passing when those PRs land; remove this xfail in the same PR.",
)
def test_apply_pushes_typed_learning_rate_into_backend(dashboard_page, canopy_url):
    typed = 0.0123

    dashboard_page.wait_for_selector("#nn-learning-rate-input", timeout=15_000)
    dashboard_page.fill("#nn-learning-rate-input", str(typed))
    dashboard_page.locator("#nn-learning-rate-input").press("Tab")  # commit value

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
