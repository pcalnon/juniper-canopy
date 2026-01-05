#!/usr/bin/env python
"""End-to-end dashboard smoke tests."""
import os

os.environ["CASCOR_DEMO_MODE"] = "1"

import time  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create test client with demo mode."""
    with TestClient(app) as client:
        yield client


class TestDashboardE2E:
    """End-to-end dashboard tests."""

    def test_dashboard_loads_without_errors(self, client):
        """Dashboard page should load successfully."""
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert "Dashboard" in response.text or "dash" in response.text.lower()

    def test_dashboard_metrics_panel_gets_data(self, client):
        """Metrics panel should receive data from API."""
        # Wait for demo mode to generate some metrics
        time.sleep(2)

        # Fetch metrics that dashboard would use
        response = client.get("/api/metrics/history?limit=10")
        assert response.status_code == 200
        data = response.json()

        # Verify format is correct for dashboard consumption
        assert isinstance(data, dict)
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_dashboard_api_endpoints_respond(self, client):
        """All dashboard API endpoints should respond."""
        endpoints = [
            "/api/health",
            "/api/status",
            "/api/metrics",
            "/api/metrics/history",
            "/api/topology",
            "/api/dataset",
            "/api/decision_boundary",
            "/api/statistics",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in (200, 503), f"{endpoint} failed"

            # If 200, should be valid JSON
            if response.status_code == 200:
                data = response.json()
                assert data is not None

    def test_training_controls_work(self, client):
        """Training control endpoints should work."""
        response = self._test_training_controls_result(client, "/api/train/pause", "paused")
        response = self._test_training_controls_result(client, "/api/train/resume", "running")

    def _test_training_controls_result(self, client, arg1, arg2):
        # Pause
        result = client.post(arg1)
        assert result.status_code == 200
        assert result.json()["status"] == arg2

        return result
