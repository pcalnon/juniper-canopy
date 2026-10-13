"""Skeleton smoke: the dashboard page loads and exposes the canonical controls.

This test is the green-on-skeleton anchor. The other ``test_*.py`` files in
this directory are expected to fail until their corresponding fix PRs land
(see each file's ``xfail`` marker). This one always asserts that the
Playwright + canopy harness can boot end-to-end.
"""

import pytest


@pytest.mark.ui
def test_dashboard_renders_control_row_and_apply_button(dashboard_page):
    for selector in ("#start-button", "#stop-button", "#reset-button", "#apply-params-button"):
        dashboard_page.wait_for_selector(selector, timeout=15_000)
