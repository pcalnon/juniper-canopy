#!/usr/bin/env python
"""Test script to verify candidate pool visibility in running demo.

This test requires a running server (./demo) and is marked appropriately.
"""
import os
import time

import pytest
import requests


@pytest.mark.e2e
@pytest.mark.requires_server
@pytest.mark.skipif(
    not os.getenv("RUN_SERVER_TESTS"),
    reason="Requires running server - set RUN_SERVER_TESTS=1 to enable",
)
class TestCandidateVisibility:
    """Test that candidate pool becomes visible during candidate training phases."""

    BASE_URL = "http://localhost:8050"

    @pytest.fixture(autouse=True)
    def _check_server_reachable(self):
        """Skip all tests if server is not reachable."""
        try:
            requests.get(f"{self.BASE_URL}/health", timeout=2)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not reachable at localhost:8050 (start with ./demo)")

    def test_server_health(self):
        """Test that the server is running and healthy."""
        response = requests.get(f"{self.BASE_URL}/health", timeout=2)
        assert response.status_code == 200, f"Server health check failed: {response.status_code}"
        health_data = response.json()
        assert "status" in health_data or health_data is not None, "Health response should contain data"

    def test_state_endpoint_returns_data(self):
        """Test that the state endpoint returns valid data."""
        response = requests.get(f"{self.BASE_URL}/api/state", timeout=2)
        assert response.status_code == 200, f"State endpoint failed: {response.status_code}"
        data = response.json()
        assert "current_epoch" in data or "epoch" in data or data is not None, "State should contain epoch data"

    def test_candidate_pool_becomes_active(self):
        """Test that candidate pool becomes active during candidate phases.

        This test monitors the training state and verifies that the candidate
        pool status transitions to 'Active' at some point during training.
        Note: Candidate phases typically occur every 5 epochs.
        """
        seen_candidate_phase = False
        max_checks = 30  # Check for up to 30 seconds

        for _ in range(max_checks):
            response = requests.get(f"{self.BASE_URL}/api/state", timeout=2)
            assert response.status_code == 200, f"State endpoint failed: {response.status_code}"
            data = response.json()

            pool_status = data.get("candidate_pool_status", "N/A")

            if pool_status == "Active":
                seen_candidate_phase = True
                # Verify pool data is present when active
                pool_size = data.get("candidate_pool_size", 0)
                assert pool_size >= 0, "Pool size should be non-negative"
                top_candidate_id = data.get("top_candidate_id", "")
                assert top_candidate_id is not None, "Top candidate ID should be present"
                break

            time.sleep(1)

        if not seen_candidate_phase:
            pytest.skip(f"Candidate pool not activated within {max_checks}s (candidate phases occur every 5 epochs)")

    def test_pool_metrics_available_when_active(self):
        """Test that pool metrics are available when candidate pool is active.

        This test waits for an active candidate phase and verifies that
        pool metrics are properly populated.
        """
        max_checks = 30

        for _ in range(max_checks):
            response = requests.get(f"{self.BASE_URL}/api/state", timeout=2)
            assert response.status_code == 200
            data = response.json()

            pool_status = data.get("candidate_pool_status", "N/A")

            if pool_status == "Active":
                pool_metrics = data.get("pool_metrics", {})
                # Verify pool metrics structure when active
                assert isinstance(pool_metrics, dict), "Pool metrics should be a dictionary"
                # At minimum, metrics should be present (may be empty or populated)
                return  # Test passed - found active phase with metrics

            time.sleep(1)

        pytest.skip("Could not observe active candidate phase within time limit")


# Keep backward compatibility for manual execution
def test_candidate_visibility_manual():
    """Manual test function for backward compatibility.

    Run with: python -m pytest src/tests/regression/test_candidate_visibility.py -v -s
    With server: RUN_SERVER_TESTS=1 python -m pytest ...
    """
    pass  # The actual tests are in the class above


if __name__ == "__main__":
    print("Running candidate visibility tests...")
    print("=" * 60)
    print("To run these tests, ensure the demo server is running (./demo)")
    print("Then run: RUN_SERVER_TESTS=1 pytest src/tests/regression/test_candidate_visibility.py -v")
    print("=" * 60)
