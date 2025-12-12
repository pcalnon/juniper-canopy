"""
Pytest Configuration and Fixtures

Global fixtures and configuration for the test suite.

Environment Variables for Test Control:
    CASCOR_BACKEND_AVAILABLE: Set to "1" to enable CasCor backend tests
    RUN_SERVER_TESTS: Set to "1" to enable live server tests
    RUN_DISPLAY_TESTS: Set to "1" to enable display/visualization tests
    ENABLE_SLOW_TESTS: Set to "1" to run slow tests (>1s execution)
"""

import asyncio
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# CRITICAL: Set demo mode BEFORE any imports of main.py
os.environ["CASCOR_DEMO_MODE"] = "1"

# Add src directory to Python path IMMEDIATELY (before pytest rewrites imports)
# This MUST happen at module load time, not in fixtures
# Go up 3 levels: conftest.py → tests/ → src/ → project_root/
project_root = Path(__file__).resolve().parent.parent.parent
src_dir = project_root / "src"

print("[src/tests/conftest.py] Initializing...")
print(f"[src/tests/conftest.py] project_root={project_root}")
print(f"[src/tests/conftest.py] src_dir={src_dir}")
print(f"[src/tests/conftest.py] src_dir.exists()={src_dir.exists()}")

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
    os.environ["PYTHONPATH"] = f"{src_dir}:{os.environ.get('PYTHONPATH', '')}"
    print(f"[src/tests/conftest.py] Added {src_dir} to sys.path")
else:
    print(f"[src/tests/conftest.py] {src_dir} already in sys.path")


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (may use DB, files, etc.)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (require full system)")
    config.addinivalue_line("markers", "slow: Slow tests (>1 second)")
    config.addinivalue_line("markers", "requires_cascor: Requires CasCor backend installation")
    config.addinivalue_line("markers", "requires_server: Requires live server running")
    config.addinivalue_line("markers", "requires_display: Requires display for visualization tests")
    config.addinivalue_line("markers", "requires_redis: Tests requiring Redis connection")

    # Display test environment configuration
    print("\n=== Test Environment Configuration ===")
    print(
        f"CasCor Backend Tests: "
        f"{'ENABLED' if os.getenv('CASCOR_BACKEND_AVAILABLE') else 'DISABLED (set CASCOR_BACKEND_AVAILABLE=1)'}"
    )
    print(f"Live Server Tests: {'ENABLED' if os.getenv('RUN_SERVER_TESTS') else 'DISABLED (set RUN_SERVER_TESTS=1)'}")

    enabled = os.getenv("RUN_DISPLAY_TESTS") or os.getenv("DISPLAY")
    print(f"Display Tests: {'ENABLED' if enabled else 'DISABLED (set RUN_DISPLAY_TESTS=1)'}")
    print(f"Slow Tests: {'ENABLED' if os.getenv('ENABLE_SLOW_TESTS') else 'DISABLED (set ENABLE_SLOW_TESTS=1)'}")
    print("=" * 40 + "\n")


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection based on environment variables.

    This function automatically skips tests based on markers and environment settings:
    - CasCor backend tests skipped unless CASCOR_BACKEND_AVAILABLE=1
    - Server tests skipped unless RUN_SERVER_TESTS=1
    - Display tests skipped in headless environments unless RUN_DISPLAY_TESTS=1
    - Slow tests skipped unless ENABLE_SLOW_TESTS=1
    """

    # Skip CasCor tests unless explicitly enabled
    if not os.getenv("CASCOR_BACKEND_AVAILABLE"):
        skip_cascor = pytest.mark.skip(reason="CasCor backend not available (set CASCOR_BACKEND_AVAILABLE=1)")
        for item in items:
            if "requires_cascor" in item.keywords:
                item.add_marker(skip_cascor)

    # Skip server tests unless explicitly enabled
    if not os.getenv("RUN_SERVER_TESTS"):
        skip_server = pytest.mark.skip(reason="Server tests disabled (set RUN_SERVER_TESTS=1)")
        for item in items:
            if "requires_server" in item.keywords:
                item.add_marker(skip_server)

    # Skip display tests in headless environments
    if os.getenv("DISPLAY") is None and not os.getenv("RUN_DISPLAY_TESTS"):
        skip_display = pytest.mark.skip(reason="No display available (set RUN_DISPLAY_TESTS=1)")
        for item in items:
            if "requires_display" in item.keywords:
                item.add_marker(skip_display)

    # Skip slow tests unless explicitly enabled
    if not os.getenv("ENABLE_SLOW_TESTS"):
        skip_slow = pytest.mark.skip(reason="Slow tests disabled (set ENABLE_SLOW_TESTS=1)")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def client():
    """
    FastAPI test client with demo mode enabled.
    Module-scoped to ensure demo_mode_instance initializes properly.
    """
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """
    Provide test configuration dictionary.

    Returns:
        Test configuration with safe defaults
    """
    return {
        "application": {
            "name": "Juniper Canopy Test",
            "version": "1.0.0",
            "environment": "testing",
        },
        "server": {"host": "127.0.0.1", "port": 8050, "debug": False},
        "logging": {
            "console": {"enabled": True, "level": "DEBUG"},
            "file": {"enabled": False, "level": "INFO"},
        },
        "frontend": {"update_interval": 1000, "max_data_points": 1000},
        "backend": {
            "cascor_prototype_path": "../cascor",
            "cache": {"enabled": False, "type": "memory"},
        },
        "communication": {"websocket": {"max_connections": 10, "heartbeat_interval": 30}},
    }


@pytest.fixture
def sample_training_metrics() -> list:
    """
    Generate sample training metrics for testing.

    Returns:
        List of training metric dictionaries
    """
    metrics = []
    metrics.extend(
        {
            "run_id": "test_run_001",
            "timestamp": f"2025-10-14T12:00:{epoch:02d}",
            "epoch": epoch,
            "phase": ("output_training" if epoch % 2 == 0 else "candidate_training"),
            "metrics": {
                "loss": 1.0 / (epoch + 1) + 0.1,
                "accuracy": (epoch / 10) * 0.9,
                "hidden_units": epoch // 2,
                "learning_rate": 0.01,
            },
            "network_topology": {
                "input_units": 2,
                "hidden_units": epoch // 2,
                "output_units": 1,
            },
        }
        for epoch in range(10)
    )
    return metrics


@pytest.fixture
def sample_network_topology() -> Dict[str, Any]:
    """
    Generate sample network topology for testing.

    Returns:
        Network topology dictionary
    """
    return {
        "input_units": 2,
        "hidden_units": 5,
        "output_units": 1,
        "connections": [
            {"from": "input_0", "to": "hidden_0", "weight": 0.5},
            {"from": "input_1", "to": "hidden_0", "weight": -0.3},
            {"from": "input_0", "to": "hidden_1", "weight": 0.7},
            {"from": "input_1", "to": "hidden_1", "weight": 0.2},
            {"from": "hidden_0", "to": "output_0", "weight": 0.8},
            {"from": "hidden_1", "to": "output_0", "weight": -0.4},
        ],
    }


@pytest.fixture
def sample_dataset() -> Dict[str, Any]:
    """
    Generate sample dataset for testing.

    Returns:
        Dataset with inputs and targets
    """
    import numpy as np

    np.random.seed(42)
    n_samples = 100

    # Generate XOR-like dataset
    X = np.random.randn(n_samples, 2)
    y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(int)

    return {
        "name": "test_dataset",
        "inputs": X.tolist(),
        "targets": y.tolist(),
        "n_samples": n_samples,
        "n_features": 2,
        "n_classes": 2,
    }


@pytest.fixture
def temp_test_directory(tmp_path):
    # sourcery skip: inline-immediately-returned-variable
    """
    Create temporary directory structure for testing.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to temporary test directory
    """
    test_dir = tmp_path / "juniper_canopy_test"
    # test_dir.mkdir(exist_ok=True)

    # Create subdirectories
    # (test_dir / "logs").mkdir(exist_ok=True)
    # (test_dir / "data").mkdir(exist_ok=True)
    # (test_dir / "images").mkdir(exist_ok=True)

    return test_dir


@pytest.fixture
def mock_config_file(tmp_path):
    """
    Create temporary configuration file for testing.

    Args:
        tmp_path: Pytest temporary path fixture

    Returns:
        Path to temporary config file
    """
    config_content = """
application:
    name: "Juniper Canopy Test"
    version: "1.0.0"
    environment: "testing"

server:
    host: "127.0.0.1"
    port: 8050

logging:
    console:
        enabled: true
        level: "DEBUG"
    file:
        enabled: false
"""

    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)

    return config_file


# Test data directory management
@pytest.fixture(scope="session", autouse=True)
def ensure_test_data_directory():
    """Ensure test data directory exists."""
    test_data_dir = Path(__file__).parent / "data"
    # test_data_dir.mkdir(exist_ok=True)

    # Create sample data files if they don't exist
    sample_metrics_file = test_data_dir / "sample_metrics.json"
    if not sample_metrics_file.exists():
        sample_data = {
            "metrics": [{"epoch": i, "loss": 1.0 / (i + 1), "accuracy": (i / 100) * 0.9} for i in range(100)]
        }
        with open(sample_metrics_file, "w") as f:
            json.dump(sample_data, f, indent=2)

    return test_data_dir


# Singleton reset for test isolation
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test for proper isolation."""
    # Import here to avoid circular imports
    with contextlib.suppress(ImportError):
        from config_manager import ConfigManager
        from demo_mode import DemoMode

        # Reset ConfigManager singleton
        if hasattr(ConfigManager, "_instance"):
            ConfigManager._instance = None
        if hasattr(ConfigManager, "_instances"):
            ConfigManager._instances.clear()

        # Reset DemoMode singleton
        if hasattr(DemoMode, "_instance"):
            # Stop any running demo mode
            if DemoMode._instance is not None and hasattr(DemoMode._instance, "stop"):
                with contextlib.suppress(Exception):
                    DemoMode._instance.stop()
            DemoMode._instance = None
        if hasattr(DemoMode, "_instances"):
            for instance in DemoMode._instances.values():
                if hasattr(instance, "stop"):
                    with contextlib.suppress(Exception):
                        instance.stop()
            DemoMode._instances.clear()

    # Reset callback context adapter
    with contextlib.suppress(ImportError):
        from frontend.callback_context import CallbackContextAdapter

        CallbackContextAdapter.reset_instance()
    yield

    # Clean up after test
    with contextlib.suppress(ImportError):
        from config_manager import ConfigManager
        from demo_mode import DemoMode

        # Reset again after test
        if hasattr(ConfigManager, "_instance"):
            ConfigManager._instance = None
        if hasattr(ConfigManager, "_instances"):
            ConfigManager._instances.clear()

        if hasattr(DemoMode, "_instance"):
            if DemoMode._instance is not None and hasattr(DemoMode._instance, "stop"):
                with contextlib.suppress(Exception):
                    DemoMode._instance.stop()
            DemoMode._instance = None
        if hasattr(DemoMode, "_instances"):
            for instance in DemoMode._instances.values():
                if hasattr(instance, "stop"):
                    with contextlib.suppress(Exception):
                        instance.stop()
            DemoMode._instances.clear()


# Fake backend root fixture for testing CasCor integration
@pytest.fixture
def fake_backend_root(tmp_path):
    """
    Create a fake CasCor backend directory structure for testing.

    This fixture supports testing against different backend versions and
    configurations without requiring a real CasCor installation.

    Returns:
        Path to the fake backend root directory
    """
    backend_root = tmp_path / "cascor"
    src_dir = backend_root / "src"
    # src_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal cascade_correlation module structure
    cc_module = src_dir / "cascade_correlation"
    # cc_module.mkdir(exist_ok=True)

    # Create __init__.py files
    (cc_module / "__init__.py").write_text("# Fake cascade_correlation module\n")

    # Create fake cascade_correlation.py
    cc_py = cc_module / "cascade_correlation.py"
    cc_py.write_text(
        """
class CascadeCorrelationNetwork:
    '''Fake CasCor network for testing'''
    def __init__(self, config=None):
        self.config = config
        self.hidden_units = []

class TrainingResults:
    '''Fake training results for testing'''
    def __init__(self):
        self.metrics = []
"""
    )

    # Create fake config module
    config_module = cc_module / "cascade_correlation_config"
    # config_module.mkdir(exist_ok=True)
    (config_module / "__init__.py").write_text("# Fake config module\n")
    (config_module / "cascade_correlation_config.py").write_text(
        """
class CascadeCorrelationConfig:
    '''Fake CasCor config for testing'''
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
"""
    )

    return backend_root


# Cleanup
@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """Clean up test environment after each test."""
    yield
    # Cleanup code runs after test
    # Clear any test-specific environment variables
    test_env_vars = [k for k in os.environ if k.startswith("CASCOR_TEST_")]
    for var in test_env_vars:
        del os.environ[var]
