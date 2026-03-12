#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_metrics_layouts_api.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-09
# Last Modified: 2026-01-09
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Integration tests for metrics layouts API endpoints (P3-4)
#####################################################################
"""Integration tests for metrics layouts API endpoints."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))


@pytest.fixture
def temp_layouts_dir(tmp_path):
    """Create temporary layouts directory."""
    layouts_dir = tmp_path / "layouts"
    layouts_dir.mkdir()
    return layouts_dir


@pytest.fixture
def client(temp_layouts_dir):
    """Create test client with mocked layouts directory."""
    os.environ["JUNIPER_CANOPY_DEMO_MODE"] = "1"

    with patch("main._layouts_dir", str(temp_layouts_dir)):
        from main import app

        yield TestClient(app)


@pytest.mark.integration
class TestListMetricsLayouts:
    """Tests for GET /api/v1/metrics/layouts endpoint."""

    def test_list_layouts_empty(self, client, temp_layouts_dir):
        """Should return empty list when no layouts exist."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.get("/api/v1/metrics/layouts")

        assert response.status_code == 200
        data = response.json()
        assert data["layouts"] == []
        assert data["total"] == 0

    def test_list_layouts_with_data(self, client, temp_layouts_dir):
        """Should return list of layouts when they exist."""
        layouts_file = temp_layouts_dir / "metrics_layouts.json"
        layouts_file.write_text(
            json.dumps(
                {
                    "test1": {
                        "name": "test1",
                        "created": "2026-01-09T10:00:00Z",
                        "description": "Test layout 1",
                    },
                    "test2": {
                        "name": "test2",
                        "created": "2026-01-09T11:00:00Z",
                        "description": "Test layout 2",
                    },
                }
            )
        )

        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.get("/api/v1/metrics/layouts")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        names = [layout["name"] for layout in data["layouts"]]
        assert "test1" in names
        assert "test2" in names


@pytest.mark.integration
class TestGetMetricsLayout:
    """Tests for GET /api/v1/metrics/layouts/{name} endpoint."""

    def test_get_layout_not_found(self, client, temp_layouts_dir):
        """Should return 404 when layout doesn't exist."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.get("/api/v1/metrics/layouts/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_layout_success(self, client, temp_layouts_dir):
        """Should return layout when it exists."""
        layouts_file = temp_layouts_dir / "metrics_layouts.json"
        layouts_file.write_text(
            json.dumps(
                {
                    "mytest": {
                        "name": "mytest",
                        "created": "2026-01-09T10:00:00Z",
                        "selected_metrics": ["loss", "accuracy"],
                        "zoom_ranges": {"xaxis": [0, 100]},
                    }
                }
            )
        )

        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.get("/api/v1/metrics/layouts/mytest")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "mytest"
        assert data["selected_metrics"] == ["loss", "accuracy"]
        assert data["zoom_ranges"] == {"xaxis": [0, 100]}


@pytest.mark.integration
class TestSaveMetricsLayout:
    """Tests for POST /api/v1/metrics/layouts endpoint."""

    def test_save_layout_success(self, client, temp_layouts_dir):
        """Should save layout successfully."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.post(
                "/api/v1/metrics/layouts",
                params={"name": "newlayout", "description": "A new layout"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "newlayout"
        assert "saved" in data["message"].lower()
        assert "created" in data

    def test_save_layout_with_all_params(self, client, temp_layouts_dir):
        """Should save layout with all parameters."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.post(
                "/api/v1/metrics/layouts",
                params={
                    "name": "full_layout",
                    "description": "Full test",
                    "smoothing_window": 20,
                },
            )

        assert response.status_code == 201

        with patch("main._layouts_dir", str(temp_layouts_dir)):
            get_response = client.get("/api/v1/metrics/layouts/full_layout")

        assert get_response.status_code == 200
        data = get_response.json()
        assert data["name"] == "full_layout"
        assert data["smoothing_window"] == 20

    def test_save_layout_empty_name(self, client, temp_layouts_dir):
        """Should reject empty layout name."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.post(
                "/api/v1/metrics/layouts",
                params={"name": ""},
            )

        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower()

    def test_save_layout_whitespace_name(self, client, temp_layouts_dir):
        """Should reject whitespace-only name."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.post(
                "/api/v1/metrics/layouts",
                params={"name": "   "},
            )

        assert response.status_code == 400

    def test_save_layout_overwrites_existing(self, client, temp_layouts_dir):
        """Should overwrite existing layout with same name."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            client.post("/api/v1/metrics/layouts", params={"name": "dupe", "description": "first"})
            client.post("/api/v1/metrics/layouts", params={"name": "dupe", "description": "second"})

            response = client.get("/api/v1/metrics/layouts/dupe")

        assert response.status_code == 200
        assert response.json()["description"] == "second"


@pytest.mark.integration
class TestDeleteMetricsLayout:
    """Tests for DELETE /api/v1/metrics/layouts/{name} endpoint."""

    def test_delete_layout_not_found(self, client, temp_layouts_dir):
        """Should return 404 when layout doesn't exist."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            response = client.delete("/api/v1/metrics/layouts/nonexistent")

        assert response.status_code == 404

    def test_delete_layout_success(self, client, temp_layouts_dir):
        """Should delete layout successfully."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            client.post("/api/v1/metrics/layouts", params={"name": "todelete"})
            response = client.delete("/api/v1/metrics/layouts/todelete")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "todelete"
        assert "deleted" in data["message"].lower()

        with patch("main._layouts_dir", str(temp_layouts_dir)):
            get_response = client.get("/api/v1/metrics/layouts/todelete")
        assert get_response.status_code == 404


@pytest.mark.integration
class TestLayoutPersistence:
    """Tests for layout persistence across requests."""

    def test_layouts_persist_in_file(self, client, temp_layouts_dir):
        """Should persist layouts to JSON file."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            client.post("/api/v1/metrics/layouts", params={"name": "persist_test"})

        layouts_file = temp_layouts_dir / "metrics_layouts.json"
        assert layouts_file.exists()

        with open(layouts_file) as f:
            data = json.load(f)
        assert "persist_test" in data

    def test_deleted_layouts_removed_from_file(self, client, temp_layouts_dir):
        """Should remove deleted layouts from JSON file."""
        with patch("main._layouts_dir", str(temp_layouts_dir)):
            client.post("/api/v1/metrics/layouts", params={"name": "delete_test"})
            client.delete("/api/v1/metrics/layouts/delete_test")

        layouts_file = temp_layouts_dir / "metrics_layouts.json"
        with open(layouts_file) as f:
            data = json.load(f)
        assert "delete_test" not in data
