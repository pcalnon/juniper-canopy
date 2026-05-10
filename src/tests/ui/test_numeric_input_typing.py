"""Issue #2 smoke: typed values are visible in the DOM after blur.

This is the weak version of the Issue #2 contract — it only verifies that
``page.fill()`` + Tab leaves the typed value in the input. The real Issue
#2 bug is about typing **vs** spinner clicks racing the debounce; PR-2
will add the type-and-spinner-share-payload test that actually exercises
the bug class.
"""

import pytest


@pytest.mark.ui
def test_typed_learning_rate_survives_blur(dashboard_page):
    dashboard_page.wait_for_selector("#nn-learning-rate-input", timeout=15_000)
    dashboard_page.fill("#nn-learning-rate-input", "0.05")
    dashboard_page.locator("#nn-learning-rate-input").press("Tab")

    value = dashboard_page.input_value("#nn-learning-rate-input")
    assert float(value) == pytest.approx(0.05), f"input value after blur: {value!r}"
