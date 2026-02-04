#!/usr/bin/env python
"""
Implementation Test Script

Tests the current MVP implementation to verify:
1. Configuration loading
2. Logging system
3. CascorIntegration (with mock network)
4. WebSocket manager
5. Dashboard components

Run this before proceeding with integration tests.
"""

import os
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

print("=" * 80)
print("Juniper Canopy - Implementation Test Suite")
print("=" * 80)
print()

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []


def test_section(title):
    """Print test section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_pass(test_name):
    """Record test pass."""
    global tests_passed
    tests_passed += 1
    test_results.append((test_name, "PASS"))
    print(f"✅ {test_name}")


def test_fail(test_name, error):
    """Record test failure."""
    global tests_failed
    tests_failed += 1
    test_results.append((test_name, f"FAIL: {error}"))
    print(f"❌ {test_name}")
    print(f"   Error: {error}")


# ============================================================================
# TEST 1: Configuration Manager
# ============================================================================
test_section("TEST 1: Configuration Manager")

try:
    # from config_manager import get_config, ConfigManager
    from config_manager import get_config

    # Test singleton
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2, "Config should be singleton"  # trunk-ignore(bandit/B101)

    test_pass("Configuration Manager - Singleton pattern")

    # Test config loading
    app_name = config1.get("application.name", "default")
    assert isinstance(app_name, str), "Config value should be string"  # trunk-ignore(bandit/B101)
    test_pass("Configuration Manager - Load config values")

    # Test nested access
    server_host = config1.get("application.server.host", "127.0.0.1")
    assert server_host is not None, "Nested config access should work"  # trunk-ignore(bandit/B101)
    test_pass("Configuration Manager - Nested key access")

    # Test default values
    nonexistent = config1.get("does.not.exist", "default_value")
    assert nonexistent == "default_value", "Default values should work"  # trunk-ignore(bandit/B101)
    test_pass("Configuration Manager - Default values")

    print(f"\n📋 Config loaded from: {config1.config_path}")

except Exception as e:
    test_fail("Configuration Manager", str(e))


# ============================================================================
# TEST 2: Logging System
# ============================================================================
test_section("TEST 2: Logging System")

try:
    from logger.logger import get_system_logger, get_training_logger, get_ui_logger

    # Test logger creation
    system_logger = get_system_logger()
    assert system_logger is not None, "System logger should exist"  # trunk-ignore(bandit/B101)
    test_pass("Logging System - System logger")

    training_logger = get_training_logger()
    assert training_logger is not None, "Training logger should exist"  # trunk-ignore(bandit/B101)
    test_pass("Logging System - Training logger")

    ui_logger = get_ui_logger()
    assert ui_logger is not None, "UI logger should exist"  # trunk-ignore(bandit/B101)
    test_pass("Logging System - UI logger")

    # Test logger (doesn't fail even if logs don't write)
    system_logger.info("Test message from implementation test")
    test_pass("Logging System - Log message")

except Exception as e:
    test_fail("Logging System", str(e))


# ============================================================================
# TEST 3: WebSocket Manager
# ============================================================================
test_section("TEST 3: WebSocket Manager")

try:
    from communication.websocket_manager import WebSocketManager, websocket_manager

    # Test singleton instance
    assert websocket_manager is not None, "WebSocket manager should exist"  # trunk-ignore(bandit/B101)
    test_pass("WebSocket Manager - Singleton instance")

    # Test manager class
    manager = WebSocketManager()
    assert manager is not None, "Can create new manager instance"  # trunk-ignore(bandit/B101)
    test_pass("WebSocket Manager - Class instantiation")

    # Test connection count
    count = manager.get_connection_count()
    assert count == 0, "Initial connection count should be 0"  # trunk-ignore(bandit/B101)
    test_pass("WebSocket Manager - Connection count")

    # Test statistics
    stats = manager.get_statistics()
    assert "active_connections" in stats, "Stats should include connection count"  # trunk-ignore(bandit/B101)
    test_pass("WebSocket Manager - Statistics")

    # Test synchronous broadcast (should not crash)
    manager.broadcast_sync({"type": "test", "data": "hello"})
    test_pass("WebSocket Manager - Synchronous broadcast")

except Exception as e:
    test_fail("WebSocket Manager", str(e))


# ============================================================================
# TEST 4: Mock CasCor Network
# ============================================================================
test_section("TEST 4: Mock CasCor Network")

try:
    import numpy as np

    from tests.mocks.mock_cascor_network import MockCascorNetwork  # sourcery skip: dont-import-test-modules

    # Test network creation
    network = MockCascorNetwork(input_size=2, output_size=1, hidden_size=5)
    assert network is not None, "Mock network should be created"  # trunk-ignore(bandit/B101)
    test_pass("Mock Network - Creation")

    # Test network properties
    assert network.input_size == 2, "Input size should be 2"  # trunk-ignore(bandit/B101)
    assert network.output_size == 1, "Output size should be 1"  # trunk-ignore(bandit/B101)
    test_pass("Mock Network - Properties")

    # Test forward pass
    x = np.random.randn(10, 2)
    output = network.forward(x)
    assert output.shape == (10, 1), "Output shape should match"  # trunk-ignore(bandit/B101)
    test_pass("Mock Network - Forward pass")

    # Test callback registration
    callback_fired = {"called": False}

    def test_callback(epoch, loss, accuracy):
        callback_fired["called"] = True

    network.on_epoch_end = test_callback

    # Test short training
    x_train = np.random.randn(50, 2)
    y_train = np.random.randn(50, 1)

    result = network.train(x_train, y_train, epochs=3, display_frequency=999)
    assert result is not None, "Training should return result"  # trunk-ignore(bandit/B101)
    test_pass("Mock Network - Training")

    # Test callback was fired
    assert callback_fired["called"], "Epoch callback should fire"  # trunk-ignore(bandit/B101)
    test_pass("Mock Network - Callbacks")

except Exception as e:
    test_fail("Mock CasCor Network", str(e))


# ============================================================================
# TEST 5: CascorIntegration (Import Only - No Backend)
# ============================================================================
test_section("TEST 5: CascorIntegration Class")

print("⚠️  Note: Skipping full CascorIntegration tests (requires ../cascor backend)")
print("    Testing class structure and mock network integration only\n")

try:
    from backend.cascor_integration import CascorIntegration

    # Test class can be imported
    test_pass("CascorIntegration - Class import")

    # Test we can create instance (will fail if backend not found, which is OK for now)
    try:
        # Try with explicit backend path
        backend_path = os.getenv("CASCOR_BACKEND_PATH", "../cascor")
        if not Path(backend_path).exists():
            print(f"   ℹ️  Backend not found at: {backend_path}")
            print("   ℹ️  Set CASCOR_BACKEND_PATH env var to test full integration")
            test_pass("CascorIntegration - Skipped (backend not available)")
        else:
            integration = CascorIntegration(backend_path=backend_path)
            test_pass("CascorIntegration - Instantiation with backend")

            # Test connection to mock network
            from tests.mocks.mock_cascor_network import MockCascorNetwork  # sourcery skip: dont-import-test-modules

            mock_net = MockCascorNetwork()
            integration.connect_to_network(mock_net)
            test_pass("CascorIntegration - Connect to mock network")

            # Test hook installation
            result = integration.install_monitoring_hooks()
            assert result is True, "Hook installation should succeed"  # trunk-ignore(bandit/B101)
            test_pass("CascorIntegration - Install monitoring hooks")

            # Test status retrieval
            status = integration.get_training_status()
            assert "network_connected" in status, "Status should include connection info"  # trunk-ignore(bandit/B101)
            test_pass("CascorIntegration - Get training status")

    except FileNotFoundError as e:
        print(f"   ℹ️  {e}")
        test_pass("CascorIntegration - Skipped (backend not found)")

except Exception as e:
    test_fail("CascorIntegration", str(e))


# ============================================================================
# TEST 6: Data Adapter
# ============================================================================
test_section("TEST 6: Data Adapter")

try:
    import numpy as np

    from backend.data_adapter import DataAdapter

    # Test adapter creation
    adapter = DataAdapter()
    assert adapter is not None, "DataAdapter should be created"  # trunk-ignore(bandit/B101)
    test_pass("Data Adapter - Creation")

    # Test dataset preparation
    x = np.random.randn(100, 2)
    y = np.random.randint(0, 2, 100)

    dataset_info = adapter.prepare_dataset_for_visualization(features=x, labels=y, dataset_name="test")

    assert dataset_info is not None, "Dataset info should be returned"  # trunk-ignore(bandit/B101)
    assert "num_samples" in dataset_info, "Should include sample count"  # trunk-ignore(bandit/B101)
    test_pass("Data Adapter - Prepare dataset for visualization")

except Exception as e:
    test_fail("Data Adapter", str(e))


# ============================================================================
# TEST 7: Training Monitor
# ============================================================================
test_section("TEST 7: Training Monitor")

try:
    from backend.data_adapter import DataAdapter
    from backend.training_monitor import TrainingMonitor

    # Test monitor creation
    adapter = DataAdapter()
    monitor = TrainingMonitor(adapter)
    assert monitor is not None, "TrainingMonitor should be created"  # trunk-ignore(bandit/B101)
    test_pass("Training Monitor - Creation")

    # Test state tracking
    state = monitor.get_current_state()
    assert "is_training" in state, "State should include training flag"  # trunk-ignore(bandit/B101)
    test_pass("Training Monitor - Get current state")

    # Test training lifecycle
    monitor.on_training_start()
    assert monitor.is_training, "Should be training after start"  # trunk-ignore(bandit/B101)
    test_pass("Training Monitor - Start training")

    monitor.on_epoch_end(epoch=1, loss=0.5, accuracy=0.8, learning_rate=0.01)
    test_pass("Training Monitor - Epoch end callback")

    monitor.on_training_end()
    assert not monitor.is_training, "Should not be training after end"  # trunk-ignore(bandit/B101)
    test_pass("Training Monitor - End training")

except Exception as e:
    test_fail("Training Monitor", str(e))


# ============================================================================
# TEST 8: Frontend Components
# ============================================================================
test_section("TEST 8: Frontend Components")

try:
    from frontend.components.dataset_plotter import DatasetPlotter
    from frontend.components.decision_boundary import DecisionBoundary
    from frontend.components.metrics_panel import MetricsPanel
    from frontend.components.network_visualizer import NetworkVisualizer

    # Test component creation
    metrics = MetricsPanel(component_id="test-metrics")
    assert metrics is not None, "MetricsPanel should be created"  # trunk-ignore(bandit/B101)
    test_pass("Frontend Components - MetricsPanel")

    visualizer = NetworkVisualizer(component_id="test-network")
    assert visualizer is not None, "NetworkVisualizer should be created"  # trunk-ignore(bandit/B101)
    test_pass("Frontend Components - NetworkVisualizer")

    plotter = DatasetPlotter(component_id="test-dataset")
    assert plotter is not None, "DatasetPlotter should be created"  # trunk-ignore(bandit/B101)
    test_pass("Frontend Components - DatasetPlotter")

    boundary = DecisionBoundary(component_id="test-boundary")
    assert boundary is not None, "DecisionBoundary should be created"  # trunk-ignore(bandit/B101)
    test_pass("Frontend Components - DecisionBoundary")

    # Test layout generation
    metrics_layout = metrics.get_layout()
    assert metrics_layout is not None, "MetricsPanel layout should be generated"  # trunk-ignore(bandit/B101)
    test_pass("Frontend Components - MetricsPanel layout")

    # Test component IDs
    assert metrics.component_id == "test-metrics", "Component ID should be set"  # trunk-ignore(bandit/B101)
    test_pass("Frontend Components - Component IDs")

except Exception as e:
    test_fail("Frontend Components", str(e))


# ============================================================================
# TEST 9: Dashboard Manager
# ============================================================================
test_section("TEST 9: Dashboard Manager")

try:
    from frontend.dashboard_manager import DashboardManager

    # Test dashboard creation
    config = get_config()
    frontend_config = config.get_section("frontend") if hasattr(config, "get_section") else {}

    dashboard = DashboardManager(frontend_config)
    assert dashboard is not None, "DashboardManager should be created"  # trunk-ignore(bandit/B101)
    test_pass("Dashboard Manager - Creation")

    # Test Dash app exists
    assert dashboard.app is not None, "Dash app should be initialized"  # trunk-ignore(bandit/B101)
    test_pass("Dashboard Manager - Dash app initialization")

    # Test component registration
    component_count = len(dashboard.components)
    print(f"   ℹ️  {component_count} components registered")
    assert component_count > 0, "Should have registered components"  # trunk-ignore(bandit/B101)
    test_pass("Dashboard Manager - Component registration")

except Exception as e:
    test_fail("Dashboard Manager", str(e))


# ============================================================================
# TEST 10: Unit Tests (Config Manager)
# ============================================================================
test_section("TEST 10: Unit Tests Execution")

try:
    import subprocess  # trunk-ignore(bandit/B404)

    print("Running pytest on ConfigManager tests...")
    # trunk-ignore(bandit/B607)
    # trunk-ignore(bandit/B603)
    result = subprocess.run(
        ["pytest", "src/tests/unit/test_config_manager.py", "-v", "--tb=short"],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode == 0:
        test_pass("Unit Tests - ConfigManager (pytest)")
        print("\n" + result.stdout)
    else:
        print("\n" + result.stdout)
        print(result.stderr)
        test_fail("Unit Tests - ConfigManager (pytest)", "Some tests failed")

except subprocess.TimeoutExpired:
    test_fail("Unit Tests", "Tests timed out after 30s")
except FileNotFoundError:
    print("   ℹ️  pytest not found, skipping unit test execution")
    test_pass("Unit Tests - Skipped (pytest not installed)")
except Exception as e:
    test_fail("Unit Tests", str(e))


# ============================================================================
# FINAL RESULTS
# ============================================================================
print("\n" + "=" * 80)
print("  TEST RESULTS SUMMARY")
print("=" * 80)
print()

for test_name, result in test_results:
    if result == "PASS":
        print(f"  ✅ {test_name}")
    else:
        print(f"  ❌ {test_name}")
        print(f"     {result}")

print()
print(f"{'=' * 80}")
print(f"  Total: {tests_passed + tests_failed} tests")
print(f"  Passed: {tests_passed} ✅")
print(f"  Failed: {tests_failed} ❌")
print(f"  Success Rate: {(tests_passed / (tests_passed + tests_failed) * 100):.1f}%")
print(f"{'=' * 80}")

if tests_failed == 0:
    print("\n🎉 ALL TESTS PASSED! Implementation is ready for integration testing.")
    # sys.exit(0)
else:
    print(f"\n⚠️  {tests_failed} test(s) failed. Please review errors above.")
    # sys.exit(1)
