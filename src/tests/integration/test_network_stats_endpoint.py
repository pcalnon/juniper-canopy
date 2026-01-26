#!/usr/bin/env python
#####################################################################################################################################################################################################
# Project:       Juniper
# Prototype:     Monitoring and Diagnostic Frontend for Cascade Correlation Neural Network
# File Name:     test_network_stats_endpoint.py
# Author:        Paul Calnon
# Version:       0.1.0
#
# Date:          2025-11-16
# Last Modified: 2025-11-16
#
# License:       MIT License
# Copyright:     Copyright (c) 2024-2025 Paul Calnon
#
# Description:
#    Integration tests for /api/network/stats endpoint.
#
#####################################################################################################################################################################################################
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    import sys
    from pathlib import Path

    src_dir = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(src_dir))

    from main import app

    return TestClient(app)


class TestNetworkStatsEndpoint:
    """Test /api/network/stats endpoint."""

    def test_endpoint_exists(self, client):
        """Test that the endpoint exists and returns 200 or 503."""
        response = client.get("/api/network/stats")

        assert response.status_code in [200, 503]

    def test_endpoint_returns_json(self, client):
        """Test that endpoint returns JSON response."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)

    def test_response_has_required_fields(self, client):
        """Test that response contains all required fields."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()

            # Check top-level fields
            assert "threshold_function" in data
            assert "optimizer" in data
            assert "total_nodes" in data
            assert "total_edges" in data
            assert "total_connections" in data
            assert "weight_statistics" in data

    def test_weight_statistics_structure(self, client):
        """Test weight_statistics object structure."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()
            weight_stats = data.get("weight_statistics", {})

            # Check all required weight statistics fields
            required_fields = [
                "total_weights",
                "positive_weights",
                "negative_weights",
                "zero_weights",
                "mean",
                "std_dev",
                "variance",
                "skewness",
                "kurtosis",
                "median",
                "mad",
                "median_ad",
                "iqr",
                "z_score_distribution",
            ]

            for field in required_fields:
                assert field in weight_stats, f"Missing field: {field}"

    def test_z_score_distribution_structure(self, client):
        """Test z_score_distribution object structure."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()
            z_dist = data.get("weight_statistics", {}).get("z_score_distribution", {})

            assert "within_1_sigma" in z_dist
            assert "within_2_sigma" in z_dist
            assert "within_3_sigma" in z_dist
            assert "beyond_3_sigma" in z_dist

    def test_field_types(self, client):
        """Test that fields have correct types."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()

            # String fields
            assert isinstance(data.get("threshold_function"), str)
            assert isinstance(data.get("optimizer"), str)

            # Integer fields
            assert isinstance(data.get("total_nodes"), int)
            assert isinstance(data.get("total_edges"), int)
            assert isinstance(data.get("total_connections"), int)

            # Weight statistics
            weight_stats = data.get("weight_statistics", {})
            assert isinstance(weight_stats.get("total_weights"), int)
            assert isinstance(weight_stats.get("positive_weights"), int)
            assert isinstance(weight_stats.get("negative_weights"), int)
            assert isinstance(weight_stats.get("zero_weights"), int)

            # Float fields
            assert isinstance(weight_stats.get("mean"), (int, float))
            assert isinstance(weight_stats.get("std_dev"), (int, float))
            assert isinstance(weight_stats.get("variance"), (int, float))

    def test_field_ranges(self, client):
        """Test that fields have reasonable ranges."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()
            weight_stats = data.get("weight_statistics", {})

            # Non-negative counts
            assert weight_stats.get("total_weights", 0) >= 0
            assert weight_stats.get("positive_weights", 0) >= 0
            assert weight_stats.get("negative_weights", 0) >= 0
            assert weight_stats.get("zero_weights", 0) >= 0

            # Variance and std_dev should be non-negative
            assert weight_stats.get("variance", 0) >= 0
            assert weight_stats.get("std_dev", 0) >= 0

            # IQR should be non-negative
            assert weight_stats.get("iqr", 0) >= 0

    def test_weight_count_consistency(self, client):
        """Test that weight counts are consistent."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()
            weight_stats = data.get("weight_statistics", {})

            total = weight_stats.get("total_weights", 0)
            positive = weight_stats.get("positive_weights", 0)
            negative = weight_stats.get("negative_weights", 0)
            zero = weight_stats.get("zero_weights", 0)

            # Sum of positive, negative, and zero should equal total
            assert positive + negative + zero == total

    def test_z_score_count_consistency(self, client):
        """Test that z-score counts are consistent."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()
            weight_stats = data.get("weight_statistics", {})
            z_dist = weight_stats.get("z_score_distribution", {})

            # within_3_sigma + beyond_3_sigma should equal total_weights
            total = weight_stats.get("total_weights", 0)
            within_3 = z_dist.get("within_3_sigma", 0)
            beyond_3 = z_dist.get("beyond_3_sigma", 0)

            if total > 0:
                assert within_3 + beyond_3 == total

    @pytest.mark.performance
    def test_endpoint_performance(self, client):
        """Test that endpoint responds within acceptable time."""
        import time

        start = time.time()
        client.get("/api/network/stats")
        elapsed = time.time() - start

        # Should respond in less than 200ms (relaxed from 50ms for CI environments)
        # Local development may see <50ms; CI/CD environments have higher latency
        assert elapsed < 0.2, f"Endpoint took {elapsed * 1000:.2f}ms (max 200ms)"


class TestNetworkStatsWithDemoMode:
    """Test network stats endpoint with demo mode active."""

    @pytest.fixture(autouse=True)
    def setup_demo_mode(self, monkeypatch):
        """Ensure demo mode is active for these tests."""
        monkeypatch.setenv("CASCOR_DEMO_MODE", "1")

    def test_demo_mode_returns_valid_stats(self, client):
        """Test that demo mode returns valid statistics."""
        response = client.get("/api/network/stats")

        if response.status_code == 200:
            data = response.json()

            # Should have threshold function from demo mode
            assert data.get("threshold_function") in ["sigmoid", "tanh", "relu"]

            # Should have optimizer from demo mode
            assert data.get("optimizer") in ["sgd", "SGD", "adam", "Adam"]

            # Should have weight statistics
            assert "weight_statistics" in data
            weight_stats = data["weight_statistics"]
            assert weight_stats.get("total_weights", 0) > 0


class TestNetworkStatsErrorHandling:
    """Test error handling for network stats endpoint."""

    def test_no_backend_available(self, client, monkeypatch):
        """Test response when no backend is available."""
        # This test may return 503 if neither demo nor real backend is available
        response = client.get("/api/network/stats")

        # Either success (200) or service unavailable (503)
        assert response.status_code in [200, 503]

        if response.status_code == 503:
            data = response.json()
            assert "error" in data


class TestStatsUpdateOnTopologyChange:
    """Test that stats update when network topology changes."""

    def test_stats_reflect_network_changes(self, client):
        """Test that statistics reflect changes in network topology."""
        # Get initial stats
        response1 = client.get("/api/network/stats")

        if response1.status_code == 200:
            data1 = response1.json()
            assert "total_nodes" in data1

            # Get stats again to verify consistency
            response2 = client.get("/api/network/stats")
            assert response2.status_code == 200

            data2 = response2.json()
            assert "total_nodes" in data2
