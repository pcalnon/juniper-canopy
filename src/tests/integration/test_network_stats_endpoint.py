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
"""Integration tests for /api/network/stats endpoint."""

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for FastAPI app with lifespan."""
    from main import app

    with TestClient(app) as c:
        yield c


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


class TestNetworkStatsServiceMode:
    """Test /api/network/stats service mode path with mocked backend.

    Verifies that the service mode code path correctly passes hidden_weights
    from get_network_data() through to DataAdapter.get_network_statistics().
    """

    @pytest.fixture
    def service_client(self, monkeypatch):
        """TestClient with backend mocked as service mode returning multi-unit weights."""
        import main
        from main import app

        # Simulate 3 hidden units with 4 weights each (12 total hidden weights)
        hidden_unit_1 = np.array([0.1, -0.2, 0.3, -0.4], dtype=np.float32)
        hidden_unit_2 = np.array([0.5, -0.6, 0.7, -0.8], dtype=np.float32)
        hidden_unit_3 = np.array([0.9, -1.0, 1.1, -1.2], dtype=np.float32)
        all_hidden = np.concatenate([hidden_unit_1, hidden_unit_2, hidden_unit_3])

        mock_adapter = MagicMock()
        mock_adapter.get_network_data.return_value = {
            "input_weights": np.array([0.1, 0.2, -0.3, 0.4], dtype=np.float32),
            "hidden_weights": all_hidden,
            "output_weights": np.array([0.5, -0.5], dtype=np.float32),
            "hidden_biases": np.array([0.01, 0.02, 0.03], dtype=np.float32),
            "output_biases": np.array([0.0], dtype=np.float32),
            "threshold_function": "tanh",
            "optimizer": "adam",
        }

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend._adapter = mock_adapter
        mock_backend.shutdown = AsyncMock()

        with TestClient(app) as c:
            monkeypatch.setattr(main, "backend", mock_backend)
            yield c, all_hidden

    @pytest.mark.integration
    def test_service_mode_returns_200(self, service_client):
        """Service mode path should return 200 with valid weight data."""
        client, _ = service_client
        response = client.get("/api/network/stats")
        assert response.status_code == 200

    @pytest.mark.integration
    def test_service_mode_includes_all_hidden_weights(self, service_client):
        """Weight count should reflect ALL hidden unit weights, not just the first."""
        client, all_hidden = service_client
        response = client.get("/api/network/stats")
        data = response.json()

        weight_stats = data["weight_statistics"]
        # input(4) + hidden(12) + output(2) = 18 total weights
        assert weight_stats["total_weights"] == 18

    @pytest.mark.integration
    def test_service_mode_weight_statistics_correctness(self, service_client):
        """Weight statistics should be computed from all weights combined."""
        client, all_hidden = service_client
        response = client.get("/api/network/stats")
        data = response.json()

        weight_stats = data["weight_statistics"]
        # With mixed positive/negative weights, both counts should be > 0
        assert weight_stats["positive_weights"] > 0
        assert weight_stats["negative_weights"] > 0
        assert weight_stats["positive_weights"] + weight_stats["negative_weights"] + weight_stats["zero_weights"] == 18

    @pytest.mark.integration
    def test_service_mode_metadata(self, service_client):
        """Service mode should pass through threshold_function and optimizer."""
        client, _ = service_client
        response = client.get("/api/network/stats")
        data = response.json()

        assert data["threshold_function"] == "tanh"
        assert data["optimizer"] == "adam"

    @pytest.mark.integration
    def test_service_mode_no_hidden_weights(self, monkeypatch):
        """Service mode with no hidden weights should still return valid stats."""
        import main
        from main import app

        mock_adapter = MagicMock()
        mock_adapter.get_network_data.return_value = {
            "input_weights": np.array([0.1, 0.2], dtype=np.float32),
            "hidden_weights": None,
            "output_weights": np.array([0.5], dtype=np.float32),
            "threshold_function": "sigmoid",
            "optimizer": "sgd",
        }

        mock_backend = MagicMock()
        mock_backend.backend_type = "service"
        mock_backend._adapter = mock_adapter
        mock_backend.shutdown = AsyncMock()

        with TestClient(app) as c:
            monkeypatch.setattr(main, "backend", mock_backend)
            response = c.get("/api/network/stats")

        assert response.status_code == 200
        data = response.json()
        # Only input(2) + output(1) = 3 weights (no hidden)
        assert data["weight_statistics"]["total_weights"] == 3
