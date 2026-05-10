"""Issue #5 end-to-end: Stop → Reset → Start does not auto-pause.

Drives the dashboard buttons against the demo backend. Pre-fix in cascor
this would synthesise a pause after one iteration; demo mode has its own
state machine, so this test doubles as a smoke check that the harness can
exercise the control row.
"""

import time

import pytest
import requests


def _status(canopy_url: str) -> dict:
    r = requests.get(f"{canopy_url}/api/status", timeout=2)
    r.raise_for_status()
    return r.json()


def _wait_status(canopy_url: str, predicate, *, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = _status(canopy_url)
        if predicate(last):
            return last
        time.sleep(0.2)
    raise AssertionError(f"status predicate not satisfied within {timeout}s; last={last}")


@pytest.mark.ui
def test_stop_reset_start_does_not_auto_pause(dashboard_page, canopy_url):
    """Demo and real backends use different status casing; rely on the two
    booleans (`is_running`, `is_paused`) which are stable across both."""
    dashboard_page.wait_for_selector("#start-button", timeout=15_000)

    dashboard_page.click("#start-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is True)

    dashboard_page.click("#stop-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is False)

    dashboard_page.click("#reset-button")
    # Reset is idempotent on a stopped backend; just give it a tick.
    time.sleep(0.5)

    dashboard_page.click("#start-button")
    _wait_status(canopy_url, lambda s: s.get("is_running") is True)

    # Observe for 2s — must not auto-flip to paused (BUG-CC-#5 symptom).
    end = time.time() + 2.0
    while time.time() < end:
        s = _status(canopy_url)
        assert s.get("is_paused") is not True, f"auto-paused after restart: {s}"
        assert s.get("is_running") is True, f"training stopped on its own: {s}"
        time.sleep(0.25)
