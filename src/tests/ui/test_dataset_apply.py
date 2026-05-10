"""§5.6 (Issue #3, PR-10) — Apply Dataset → banner → Cancel flow.

PR-7 wired the Apply Dataset button + Cancel button + pending-dataset-
banner. This test drives the user-facing flow under Playwright:

  1. Click Apply Dataset (no input change needed — the dropdown
     defaults to ``spirals``, and the click is sufficient to stage).
  2. Assert the pending-dataset-banner becomes visible.
  3. Click Cancel pending change.
  4. Assert the banner closes.

Buttons don't have the React-controlled-input bug that blocks the
apply-params-button test (see ``test_apply_button_flow.py`` xfail);
button clicks DO fire Dash callbacks under headless Playwright.
"""

from __future__ import annotations

import pytest


@pytest.mark.ui
def test_apply_dataset_opens_banner_then_cancel_closes_it(dashboard_page) -> None:
    # The Apply Dataset button lives in the contextual Dataset section
    # of the sidebar — visible on tabs that include ``sidebar-nn-spiral-dataset``.
    # The default tab (``metrics``) doesn't show the dataset section, so
    # navigate to ``dataset`` first. Use the same label-based selector as
    # test_sidebar_width.py.
    dashboard_page.locator("#visualization-tabs >> a:has-text('Dataset View')").first.click()
    dashboard_page.wait_for_selector("#apply-dataset-button", state="visible", timeout=8_000)

    # 1 + 2: click Apply Dataset, banner becomes visible.
    dashboard_page.locator("#apply-dataset-button").click()
    dashboard_page.wait_for_function(
        """() => {
            const banner = document.getElementById('pending-dataset-banner');
            return banner && getComputedStyle(banner).display !== 'none';
        }""",
        timeout=8_000,
    )

    # 3 + 4: click Cancel, banner closes.
    dashboard_page.locator("#cancel-pending-dataset-button").click()
    dashboard_page.wait_for_function(
        """() => {
            const banner = document.getElementById('pending-dataset-banner');
            return !banner || getComputedStyle(banner).display === 'none';
        }""",
        timeout=8_000,
    )
