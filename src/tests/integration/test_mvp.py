#!/usr/bin/env python
"""
Test Juniper Canopy MVP

Tests the critical fixes for dashboard display issue.
"""

import os
import sys
from pathlib import Path

import pytest

# Set demo mode BEFORE importing
os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

# Add src to path
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def client():
    """Create test client with demo mode."""
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as client:
        yield client


def test_api_health(client):
    """Test API health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_api_status(client):
    """Test API status endpoint."""
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "network_connected" in data


def test_api_dataset(client):
    """Test API dataset endpoint."""
    response = client.get("/api/dataset")
    assert response.status_code == 200
    data = response.json()
    # Either has data or error
    assert ("num_samples" in data) or ("error" in data)


def test_root_redirect(client):
    """Test root redirect to dashboard."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {301, 302, 307, 308}


def test_dashboard_accessible(client):
    """Test dashboard accessibility."""
    response = client.get("/dashboard/")
    assert response.status_code == 200

    # Check if it's HTML
    content_type = response.headers.get("content-type", "")
    assert "html" in content_type.lower()

    # Check for key elements (dashboard title or tab names)
    html = response.text
    assert "Juniper Canopy" in html or "Training Metrics" in html
