"""
Pytest Configuration and Fixtures

Global fixtures and configuration for the test suite.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Add src directory to Python path
# src_dir = Path(__file__).parent.parent
src_path = Path(__file__).parent.parent
# if str(src_dir) not in sys.path:
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
    # sys.path.insert(0, str(src_dir))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """
    Provide test configuration dictionary.

    Returns:
        Test configuration with safe defaults
    """
    return {
        "application": {"name": "Juniper Canopy Test", "version": "1.0.0", "environment": "testing"},
        "server": {"host": "127.0.0.1", "port": 8050, "debug": False},
        "logging": {"console": {"enabled": True, "level": "DEBUG"}, "file": {"enabled": False, "level": "INFO"}},
        "frontend": {"update_interval": 1000, "max_data_points": 1000},
        "backend": {
            "cascor_prototype_path": "../../JuniperCascor/juniper_cascor",
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
    # test_dir = tmp_path / "cascor_test"
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


# Cleanup
@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """Clean up test environment after each test."""
    yield
    # Cleanup code runs after test
    # Clear any test-specific environment variables
    # test_env_vars = [k for k in os.environ if k.startswith("CASCOR_TEST_")]
    test_env_vars = [k for k in os.environ if k.startswith("JUNIPER_CANOPY_TEST_")]
    for var in test_env_vars:
        del os.environ[var]
