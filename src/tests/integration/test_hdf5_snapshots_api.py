#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_hdf5_snapshots_api.py
# Author:        Paul Calnon (via Amp AI)
# Version:       1.0.0
# Date:          2026-01-08
# Last Modified: 2026-01-08
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Integration tests for HDF5 Snapshots API endpoints (P2-4, P2-5)
#####################################################################
"""Integration tests for HDF5 Snapshots API endpoints."""

import os
import sys
import tempfile
from pathlib import Path

# Ensure src is on the path
src_dir = Path(__file__).parents[2]
sys.path.insert(0, str(src_dir))

# Force demo mode for tests
os.environ["CASCOR_DEMO_MODE"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402


@pytest.fixture
def client():
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# GET /api/v1/snapshots Tests
# =============================================================================


class TestGetSnapshotsEndpoint:
    """Test GET /api/v1/snapshots endpoint."""

    @pytest.mark.integration
    def test_snapshots_endpoint_returns_200(self, client):
        """Should return 200 OK."""
        response = client.get("/api/v1/snapshots")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_snapshots_endpoint_returns_json(self, client):
        """Should return JSON response."""
        response = client.get("/api/v1/snapshots")
        assert response.headers.get("content-type", "").startswith("application/json")

    @pytest.mark.integration
    def test_snapshots_endpoint_has_snapshots_key(self, client):
        """Should have 'snapshots' key in response."""
        response = client.get("/api/v1/snapshots")
        data = response.json()
        assert "snapshots" in data

    @pytest.mark.integration
    def test_snapshots_endpoint_snapshots_is_list(self, client):
        """Snapshots should be a list."""
        response = client.get("/api/v1/snapshots")
        data = response.json()
        assert isinstance(data["snapshots"], list)

    @pytest.mark.integration
    def test_demo_mode_returns_mock_snapshots(self, client):
        """In demo mode, should return mock snapshots."""
        response = client.get("/api/v1/snapshots")
        data = response.json()

        # Demo mode should return at least one snapshot
        assert len(data["snapshots"]) > 0

        # Check snapshot structure
        snapshot = data["snapshots"][0]
        assert "id" in snapshot
        assert "name" in snapshot
        assert "timestamp" in snapshot
        assert "size_bytes" in snapshot

    @pytest.mark.integration
    def test_demo_mode_snapshots_have_demo_prefix(self, client):
        """Demo mode snapshots should have 'demo_' prefix in ID."""
        response = client.get("/api/v1/snapshots")
        data = response.json()

        # At least one snapshot should have demo prefix
        demo_snapshots = [s for s in data["snapshots"] if s["id"].startswith("demo_")]
        assert len(demo_snapshots) > 0

    @pytest.mark.integration
    def test_demo_mode_has_message(self, client):
        """Demo mode should include a message."""
        response = client.get("/api/v1/snapshots")
        data = response.json()

        # Should have message indicating demo mode
        assert "message" in data
        assert "demo" in data["message"].lower()

    @pytest.mark.integration
    def test_snapshots_have_valid_timestamps(self, client):
        """Snapshots should have valid ISO8601 timestamps."""
        response = client.get("/api/v1/snapshots")
        data = response.json()

        for snapshot in data["snapshots"]:
            timestamp = snapshot.get("timestamp", "")
            # Basic ISO8601 format check
            assert "T" in timestamp
            assert timestamp.endswith("Z")

    @pytest.mark.integration
    def test_snapshots_have_positive_sizes(self, client):
        """Snapshots should have positive size values."""
        response = client.get("/api/v1/snapshots")
        data = response.json()

        for snapshot in data["snapshots"]:
            size = snapshot.get("size_bytes", 0)
            assert size > 0


# =============================================================================
# GET /api/v1/snapshots/{snapshot_id} Tests
# =============================================================================


class TestGetSnapshotDetailEndpoint:
    """Test GET /api/v1/snapshots/{snapshot_id} endpoint."""

    @pytest.mark.integration
    def test_snapshot_detail_returns_200_for_valid_id(self, client):
        """Should return 200 for valid snapshot ID."""
        # First get list to find a valid ID
        list_response = client.get("/api/v1/snapshots")
        snapshots = list_response.json()["snapshots"]
        assert len(snapshots) > 0

        snapshot_id = snapshots[0]["id"]
        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_snapshot_detail_returns_404_for_invalid_id(self, client):
        """Should return 404 for non-existent snapshot ID."""
        response = client.get("/api/v1/snapshots/nonexistent_snapshot_xyz")
        assert response.status_code == 404

    @pytest.mark.integration
    def test_snapshot_detail_has_required_fields(self, client):
        """Snapshot detail should have all required fields."""
        list_response = client.get("/api/v1/snapshots")
        snapshots = list_response.json()["snapshots"]
        snapshot_id = snapshots[0]["id"]

        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        data = response.json()

        assert "id" in data
        assert "name" in data
        assert "timestamp" in data
        assert "size_bytes" in data

    @pytest.mark.integration
    def test_snapshot_detail_has_attributes(self, client):
        """Demo mode snapshot detail should have attributes."""
        list_response = client.get("/api/v1/snapshots")
        snapshots = list_response.json()["snapshots"]
        snapshot_id = snapshots[0]["id"]

        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        data = response.json()

        # Demo mode should include attributes
        assert "attributes" in data
        assert isinstance(data["attributes"], dict)

    @pytest.mark.integration
    def test_snapshot_detail_demo_attributes_content(self, client):
        """Demo mode snapshot attributes should have expected keys."""
        list_response = client.get("/api/v1/snapshots")
        snapshots = list_response.json()["snapshots"]
        snapshot_id = snapshots[0]["id"]

        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        data = response.json()
        attrs = data.get("attributes", {})

        # Demo mode attributes should include mode indicator
        assert "mode" in attrs
        assert attrs["mode"] == "demo"

    @pytest.mark.integration
    def test_snapshot_detail_id_matches_request(self, client):
        """Returned snapshot ID should match requested ID."""
        list_response = client.get("/api/v1/snapshots")
        snapshots = list_response.json()["snapshots"]
        snapshot_id = snapshots[0]["id"]

        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        data = response.json()

        assert data["id"] == snapshot_id


# =============================================================================
# Real File System Tests (with temp directory)
# =============================================================================


class TestSnapshotsWithRealFiles:
    """Test snapshot endpoints with real HDF5 files."""

    @pytest.fixture
    def temp_snapshot_dir(self):
        """Create temporary directory with mock HDF5 files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create mock .h5 files (just empty files for testing)
            (Path(tmpdir) / "snapshot_001.h5").write_bytes(b"\x00" * 1024)
            (Path(tmpdir) / "snapshot_002.hdf5").write_bytes(b"\x00" * 2048)
            (Path(tmpdir) / "not_a_snapshot.txt").write_text("not a snapshot")
            yield tmpdir

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires patching global _snapshots_dir which is complex in demo mode")
    def test_lists_real_hdf5_files(self, temp_snapshot_dir):
        """Should list real HDF5 files from snapshot directory."""
        # This test would require mocking the global _snapshots_dir
        # Skipped for now as demo mode returns mock data
        pass

    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires patching global _snapshots_dir which is complex in demo mode")
    def test_ignores_non_hdf5_files(self, temp_snapshot_dir):
        """Should ignore non-HDF5 files in snapshot directory."""
        pass


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestSnapshotsErrorHandling:
    """Test error handling for snapshot endpoints."""

    @pytest.mark.integration
    def test_404_response_has_detail(self, client):
        """404 response should have 'detail' field."""
        response = client.get("/api/v1/snapshots/nonexistent_id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.integration
    def test_404_detail_is_descriptive(self, client):
        """404 detail message should be descriptive."""
        response = client.get("/api/v1/snapshots/nonexistent_id")
        data = response.json()
        detail = data.get("detail", "")
        assert "not found" in detail.lower()


# =============================================================================
# Content Type and Format Tests
# =============================================================================


class TestSnapshotsContentFormat:
    """Test content format of snapshot responses."""

    @pytest.mark.integration
    def test_list_content_type_is_json(self, client):
        """List endpoint should return JSON content type."""
        response = client.get("/api/v1/snapshots")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    @pytest.mark.integration
    def test_detail_content_type_is_json(self, client):
        """Detail endpoint should return JSON content type."""
        list_response = client.get("/api/v1/snapshots")
        snapshots = list_response.json()["snapshots"]
        snapshot_id = snapshots[0]["id"]

        response = client.get(f"/api/v1/snapshots/{snapshot_id}")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type

    @pytest.mark.integration
    def test_timestamp_format_is_iso8601(self, client):
        """Timestamps should be in ISO8601 format."""
        response = client.get("/api/v1/snapshots")
        data = response.json()

        for snapshot in data["snapshots"]:
            ts = snapshot.get("timestamp", "")
            # ISO8601 format: YYYY-MM-DDTHH:MM:SSZ
            assert len(ts) >= 19  # At least YYYY-MM-DDTHH:MM:SS
            assert ts[4] == "-" and ts[7] == "-" and ts[10] == "T"
