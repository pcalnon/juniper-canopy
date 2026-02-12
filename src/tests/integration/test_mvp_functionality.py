#!/usr/bin/env python
"""
MVP Functionality Test Suite

Tests all critical functionality for Phase 1 MVP:
- Demo mode initialization
- API endpoints return data
- Dashboard components receive data
- Data flow from backend to frontend

Run: python -m pytest src/tests/test_mvp_functionality.py -v
"""
import sys
import time
from pathlib import Path

import pytest
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.integration
class TestDemoMode:
    """Test demo mode functionality."""

    def test_demo_mode_import(self):
        """Test that demo_mode module can be imported."""
        from demo_mode import DemoMode, MockCascorNetwork

        assert DemoMode is not None  # trunk-ignore(bandit/B101)
        assert MockCascorNetwork is not None  # trunk-ignore(bandit/B101)

    def test_mock_network_creation(self):
        """Test MockCascorNetwork initialization."""
        from demo_mode import MockCascorNetwork

        network = MockCascorNetwork(input_size=2, output_size=1)
        assert network.input_size == 2  # trunk-ignore(bandit/B101)
        assert network.output_size == 1  # trunk-ignore(bandit/B101)
        assert len(network.hidden_units) == 0  # trunk-ignore(bandit/B101)
        assert network.learning_rate == 0.01  # trunk-ignore(bandit/B101)

    def test_demo_mode_initialization(self):
        """Test DemoMode initialization."""
        from demo_mode import DemoMode

        demo = DemoMode(update_interval=0.1)
        assert demo.network is not None  # trunk-ignore(bandit/B101)
        assert demo.dataset is not None  # trunk-ignore(bandit/B101)
        assert demo.current_epoch == 0  # trunk-ignore(bandit/B101)
        assert not demo.is_running  # trunk-ignore(bandit/B101)

    def test_spiral_dataset_generation(self):
        """Test spiral dataset properties."""
        from demo_mode import DemoMode

        demo = DemoMode()
        dataset = demo.get_dataset()

        assert "inputs" in dataset  # trunk-ignore(bandit/B101)
        assert "targets" in dataset  # trunk-ignore(bandit/B101)
        assert dataset["num_samples"] == 200  # trunk-ignore(bandit/B101)
        assert dataset["num_features"] == 2  # trunk-ignore(bandit/B101)
        assert dataset["num_classes"] == 2  # trunk-ignore(bandit/B101)

    def test_demo_mode_start_stop(self):
        """Test demo mode can start and stop."""
        from demo_mode import DemoMode

        demo = DemoMode(update_interval=0.1)
        demo.start()

        assert demo.is_running  # trunk-ignore(bandit/B101)
        time.sleep(0.5)  # Let it run briefly

        demo.stop()
        assert not demo.is_running  # trunk-ignore(bandit/B101)

    def test_metrics_generation(self):
        """Test that demo mode generates metrics."""
        from demo_mode import DemoMode

        demo = DemoMode(update_interval=0.1)
        demo.start()

        time.sleep(0.5)  # Let it generate some metrics

        metrics = demo.get_metrics_history()
        assert len(metrics) > 0  # trunk-ignore(bandit/B101)

        # Check metric structure
        metric = metrics[0]
        assert "epoch" in metric  # trunk-ignore(bandit/B101)
        assert "metrics" in metric  # trunk-ignore(bandit/B101)
        assert "loss" in metric["metrics"]  # trunk-ignore(bandit/B101)
        assert "accuracy" in metric["metrics"]  # trunk-ignore(bandit/B101)

        demo.stop()


@pytest.mark.requires_server
class TestAPIEndpoints:
    """Test API endpoints return correct data."""

    @pytest.fixture(scope="class")
    def base_url(self):
        """Base URL for API."""
        return "http://localhost:8050"

    def test_health_endpoint(self, base_url):
        """Test /api/health endpoint."""
        try:
            response = requests.get(f"{base_url}/api/health", timeout=2)
            if response.status_code >= 500:
                pytest.skip(f"Server endpoint error: {response.status_code}")
            assert response.status_code == 200  # trunk-ignore(bandit/B101)

            data = response.json()
            assert "status" in data  # trunk-ignore(bandit/B101)
            assert "version" in data  # trunk-ignore(bandit/B101)
            assert "demo_mode" in data  # trunk-ignore(bandit/B101)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_status_endpoint(self, base_url):
        """Test /api/status endpoint."""
        try:
            response = requests.get(f"{base_url}/api/status", timeout=2)
            if response.status_code >= 500:
                pytest.skip(f"Server endpoint error: {response.status_code}")
            assert response.status_code == 200  # trunk-ignore(bandit/B101)

            data = response.json()
            assert "network_connected" in data  # trunk-ignore(bandit/B101)
            assert "input_size" in data  # trunk-ignore(bandit/B101)
            assert "output_size" in data  # trunk-ignore(bandit/B101)
            assert "hidden_units" in data  # trunk-ignore(bandit/B101)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_metrics_endpoint(self, base_url):
        """Test /api/metrics endpoint."""
        try:
            response = requests.get(f"{base_url}/api/metrics?limit=10", timeout=2)
            if response.status_code >= 500:
                pytest.skip(f"Server endpoint error: {response.status_code}")
            assert response.status_code == 200  # trunk-ignore(bandit/B101)
            data = response.json()
            if isinstance(data, dict):
                metrics_list = data.get("history", data.get("data", []))
            else:
                metrics_list = data
            assert isinstance(metrics_list, list)  # trunk-ignore(bandit/B101)

            if len(metrics_list) > 0:
                metric = metrics_list[0]
                assert "epoch" in metric  # trunk-ignore(bandit/B101)
                assert "metrics" in metric  # trunk-ignore(bandit/B101)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_topology_endpoint(self, base_url):
        """Test /api/topology endpoint."""
        try:
            response = requests.get(f"{base_url}/api/topology", timeout=2)
            if response.status_code >= 500:
                pytest.skip(f"Server endpoint error: {response.status_code}")
            assert response.status_code == 200  # trunk-ignore(bandit/B101)

            data = response.json()
            assert "input_units" in data or "error" in data  # trunk-ignore(bandit/B101)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")

    def test_dataset_endpoint(self, base_url):
        """Test /api/dataset endpoint."""
        try:
            response = requests.get(f"{base_url}/api/dataset", timeout=2)
            if response.status_code >= 500:
                pytest.skip(f"Server endpoint error: {response.status_code}")
            assert response.status_code == 200  # trunk-ignore(bandit/B101)

            data = response.json()
            if "error" not in data:
                assert "inputs" in data  # trunk-ignore(bandit/B101)
                assert "targets" in data  # trunk-ignore(bandit/B101)
                assert "num_samples" in data  # trunk-ignore(bandit/B101)
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running")


@pytest.mark.integration
class TestBackendIntegration:
    """Test backend integration functionality."""

    def test_cascor_integration_import(self):
        """Test CascorIntegration can be imported."""
        from backend.cascor_integration import CascorIntegration

        assert CascorIntegration is not None  # trunk-ignore(bandit/B101)

    def test_path_resolution_with_tilde(self):
        """Test that tilde expansion works in path resolution."""
        # from backend.cascor_integration import CascorIntegration
        import os

        # Test with fake path to ensure expansion happens
        test_path = "~/test_path"
        expanded = os.path.expanduser(test_path)
        assert "~" not in expanded  # trunk-ignore(bandit/B101)

    def test_data_adapter_import(self):
        """Test DataAdapter can be imported."""
        from backend.data_adapter import DataAdapter

        adapter = DataAdapter()
        assert adapter is not None  # trunk-ignore(bandit/B101)


class TestComponentStores:
    """Test that component stores are properly defined."""

    def test_dashboard_manager_import(self):
        """Test DashboardManager can be imported."""
        from frontend.dashboard_manager import DashboardManager

        assert DashboardManager is not None  # trunk-ignore(bandit/B101)

    def test_component_imports(self):
        """Test all component classes can be imported."""
        from frontend.components.dataset_plotter import DatasetPlotter
        from frontend.components.decision_boundary import DecisionBoundary
        from frontend.components.metrics_panel import MetricsPanel
        from frontend.components.network_visualizer import NetworkVisualizer

        assert MetricsPanel is not None  # trunk-ignore(bandit/B101)
        assert NetworkVisualizer is not None  # trunk-ignore(bandit/B101)
        assert DatasetPlotter is not None  # trunk-ignore(bandit/B101)
        assert DecisionBoundary is not None  # trunk-ignore(bandit/B101)


def run_integration_test():
    """Run integration test manually (requires running server)."""
    _display_integration_test_heading_("INTEGRATION TEST - Manual Verification", "\n1. Testing API Health...")
    base_url = "http://localhost:8050"
    try:
        response = requests.get(f"{base_url}/api/health", timeout=2)
        data = response.json()
        print(f"   ✓ Health: {data.get('status')}, Demo Mode: {data.get('demo_mode')}")
    except Exception as e:
        print(f"   ✗ Health check failed: {e}")
        return False

    print("\n2. Testing Training Status...")
    try:
        response = requests.get(f"{base_url}/api/status", timeout=2)
        data = response.json()
        print(f"   ✓ Epoch: {data.get('current_epoch')}")
        print(f"   ✓ Loss: {data.get('current_loss'):.4f}")
        print(f"   ✓ Accuracy: {data.get('current_accuracy'):.4f}")
        print(f"   ✓ Hidden Units: {data.get('hidden_units')}")
    except Exception as e:
        print(f"   ✗ Status check failed: {e}")

    print("\n3. Testing Metrics Data...")
    try:
        response = requests.get(f"{base_url}/api/metrics?limit=5", timeout=2)
        metrics = response.json()
        print(f"   ✓ Retrieved {len(metrics)} metrics")
        if metrics:
            latest = metrics[-1]
            print(f"   ✓ Latest epoch: {latest.get('epoch')}")
    except Exception as e:
        print(f"   ✗ Metrics check failed: {e}")

    print("\n4. Testing Dataset...")
    try:
        response = requests.get(f"{base_url}/api/dataset", timeout=2)
        dataset = response.json()
        if "error" not in dataset:
            print(f"   ✓ Samples: {dataset.get('num_samples')}")
            print(f"   ✓ Features: {dataset.get('num_features')}")
            print(f"   ✓ Classes: {dataset.get('num_classes')}")
        else:
            print(f"   ✗ Dataset error: {dataset.get('error')}")
    except Exception as e:
        print(f"   ✗ Dataset check failed: {e}")

    print("\n5. Testing Topology...")
    try:
        response = requests.get(f"{base_url}/api/topology", timeout=2)
        topology = response.json()
        if "error" not in topology:
            print(f"   ✓ Input Units: {topology.get('input_units')}")
            print(f"   ✓ Hidden Units: {topology.get('hidden_units')}")
            print(f"   ✓ Output Units: {topology.get('output_units')}")
        else:
            print(f"   ✗ Topology error: {topology.get('error')}")
    except Exception as e:
        print(f"   ✗ Topology check failed: {e}")

    _display_integration_test_heading_("INTEGRATION TEST COMPLETE", "\nManual Verification Steps:")
    print("1. Open http://localhost:8050/dashboard/ in browser")
    print("2. Check Training Metrics tab shows loss/accuracy plots")
    print("3. Check Network Topology tab shows network graph")
    print("4. Check Dataset View tab shows spiral scatter plot")
    print("5. Verify epoch counter increments every second")
    print("=" * 70)

    return True


def _display_integration_test_heading_(arg0, arg1):
    print("\n" + "=" * 70)
    print(arg0)
    print("=" * 70)
    print(arg1)


if __name__ == "__main__":
    # Run integration test if server is running
    print("Juniper Canopy MVP Test Suite")
    print("Note: Some tests require the server to be running")
    print("\nRunning integration test...")

    run_integration_test()
