#!/usr/bin/env python
"""Test dashboard title displays correctly."""
import os

os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create test client with demo mode."""
    with TestClient(app) as client:
        yield client


class TestDashboardTitle:
    """Test that dashboard title is correct."""

    def test_browser_tab_title(self, client):
        """Browser tab should show 'Juniper Canopy Dashboard'."""
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert "Juniper Canopy Dashboard" in response.text

    def test_dashboard_header_title(self, client):
        """Dashboard header should display 'Juniper Canopy Dashboard'."""
        response = client.get("/dashboard/")
        assert response.status_code == 200
        # Check for H1 header with exact title
        assert "Juniper Canopy Dashboard" in response.text
        # Ensure old title is not present
        assert "Juniper Canopy Monitor" not in response.text
