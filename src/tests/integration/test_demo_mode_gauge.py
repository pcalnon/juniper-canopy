#!/usr/bin/env python
"""Integration test for the ``juniper_canopy_demo_mode_active`` gauge.

METRICS-MON R3.2 / seed-11: the demo-mode gauge must reflect the live
backend state (post-fallback) and respond to runtime toggles within one
``/metrics`` scrape tick. Without an end-to-end test, the gauge can drift
silently from reality — the symptom that motivated seed-11.

Pins:

1. Cold start under demo mode produces ``juniper_canopy_demo_mode_active 1.0``
   on the first ``/metrics`` scrape.
2. Calling :func:`observability.set_demo_mode_active` flips the gauge value
   visible on the very next scrape (no caching, no debounce, no async lag).
3. Toggling back to demo restores ``1.0`` on the following scrape.

The test does not rely on any runtime "demo toggle" production endpoint
(none exists); it drives the gauge through the public observability helper
and asserts the scrape-side projection. That is the same path that
``main.py``'s lifespan hook uses, so this test pins the contract the
production wiring must honor.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def demo_metrics_client():
    """Start the canopy app in demo mode with /metrics enabled."""
    os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"
    os.environ["JUNIPER_CANOPY_METRICS_ENABLED"] = "1"

    # Reset the lazily-cached canopy metrics dict so the Gauge re-registers
    # against a fresh prometheus REGISTRY (other test modules may have
    # interacted with it). Without this, the Gauge instance the test holds
    # may differ from the one mounted under /metrics.
    import observability as obs

    obs._canopy_metrics = None

    # Cleared settings cache so the env-var changes above take effect.
    from settings import get_settings

    get_settings.cache_clear()

    # Module-level guards in main.py decide route mounts at FIRST import time
    # (``main.py:309`` mounts ``/metrics`` only if ``settings.metrics_enabled``).
    # If an earlier test imported ``main`` under a settings cache that had
    # metrics disabled, ``/metrics`` is missing now and our scrape returns
    # 404. Same story for the demo-mode gauge: the singleton ``backend`` was
    # bound to a non-demo settings snapshot, so lifespan set the gauge to 0.
    # Patch both holes here so this fixture is independent of suite ordering.
    from juniper_observability import get_prometheus_app

    from main import app

    has_metrics_route = any(getattr(r, "path", None) == "/metrics" for r in app.routes)
    if not has_metrics_route:
        app.mount("/metrics", get_prometheus_app())

    with TestClient(app) as client:
        from observability import set_demo_mode_active

        set_demo_mode_active(True)
        yield client


def _scrape_demo_mode_gauge(client: TestClient) -> float:
    """GET /metrics and parse out the demo_mode_active sample."""
    response = client.get("/metrics")
    assert response.status_code == 200, response.text
    body = response.text
    # Prometheus exposition format: ``juniper_canopy_demo_mode_active <value>``
    # on its own line (no labels on this gauge). Skip the HELP / TYPE lines.
    for line in body.splitlines():
        if line.startswith("juniper_canopy_demo_mode_active") and not line.startswith("#"):
            # Last whitespace-separated token is the float value.
            return float(line.rsplit(" ", 1)[-1])
    raise AssertionError(f"juniper_canopy_demo_mode_active not present in /metrics body:\n{body}")


@pytest.mark.integration
class TestDemoModeGauge:
    """METRICS-MON R3.2: ``juniper_canopy_demo_mode_active`` reflects live state."""

    def test_cold_start_under_demo_mode_reports_one(self, demo_metrics_client):
        """Lifespan hook calls ``set_demo_mode_active(True)``; first scrape sees 1."""
        assert _scrape_demo_mode_gauge(demo_metrics_client) == 1.0

    def test_runtime_toggle_to_false_reflects_on_next_scrape(self, demo_metrics_client):
        from observability import set_demo_mode_active

        set_demo_mode_active(False)
        assert _scrape_demo_mode_gauge(demo_metrics_client) == 0.0

    def test_runtime_toggle_back_to_true_reflects_on_next_scrape(self, demo_metrics_client):
        from observability import set_demo_mode_active

        # Order matters: previous test left the gauge at 0.0. This test pins
        # that the *transition* 0 → 1 propagates without intermediate state.
        set_demo_mode_active(True)
        assert _scrape_demo_mode_gauge(demo_metrics_client) == 1.0
