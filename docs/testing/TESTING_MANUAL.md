# Testing Manual - Comprehensive User Guide

**Last Updated:** January 29, 2026  
**Version:** v0.25.0

Complete guide to testing the Juniper Canopy application.

## Table of Contents

1. [Introduction](#introduction)
2. [Running Tests](#running-tests)
3. [Test Organization](#test-organization)
4. [Writing Tests](#writing-tests)
5. [Test Fixtures](#test-fixtures)
6. [Test Markers](#test-markers)
7. [Coverage Analysis](#coverage-analysis)
8. [Best Practices](#best-practices)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

## Introduction

### Overview

The Juniper Canopy uses **pytest** as the testing framework with:

- **272+ tests** across unit, integration, and performance categories
- **100% pass rate** (all tests passing)
- **73% code coverage** (target: 80%)
- **Automated CI/CD** via GitHub Actions

### Testing Philosophy

- **Test-Driven Development**: Write tests before or alongside code
- **Comprehensive Coverage**: Aim for 80%+ coverage, 100% for critical paths
- **Fast Feedback**: Unit tests run in seconds, full suite in minutes
- **Isolation**: Each test is independent and can run in any order
- **Realistic**: Integration tests use real components where possible

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with extra verbose output
pytest -vv

# Stop at first failure
pytest -x

# Show local variables on failure
pytest -l

# Run specific test file
pytest src/tests/unit/test_demo_mode.py

# Run specific test function
pytest src/tests/unit/test_demo_mode.py::test_demo_mode_initialization

# Run specific test class
pytest src/tests/unit/test_demo_mode.py::TestDemoMode
```

### Running by Category

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Performance tests only
pytest -m performance

# Skip slow tests
pytest -m "not slow"

# Skip tests requiring external services
pytest -m "not requires_cascor"
```

### Running by Pattern

```bash
# Run tests matching pattern
pytest -k "demo_mode"

# Run tests NOT matching pattern
pytest -k "not slow"

# Multiple patterns (OR)
pytest -k "demo_mode or config"

# Multiple patterns (AND)
pytest -k "demo_mode and advanced"
```

### Running with Coverage

```bash
# Basic coverage
pytest --cov=src

# Coverage with missing lines
pytest --cov=src --cov-report=term-missing

# HTML coverage report
pytest --cov=src --cov-report=html

# Multiple report formats
pytest --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml
```

### Advanced Options

```bash
# Run last failed tests
pytest --lf

# Run failures first, then rest
pytest --ff

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Show test durations
pytest --durations=10

# Show all durations
pytest --durations=0

# Capture output (default)
pytest -s

# Disable output capture
pytest --capture=no

# Show warnings
pytest -W default

# Treat warnings as errors
pytest -W error
```

## Test Organization

### Directory Structure

```bash
src/tests/
├── conftest.py              # Global fixtures and configuration
├── pytest.ini               # Pytest settings
│
├── unit/                    # Unit tests (73 tests)
│   ├── test_config_manager.py          # Configuration management
│   ├── test_config_manager_advanced.py # Advanced config tests
│   ├── test_demo_mode.py               # Demo mode core
│   ├── test_demo_mode_advanced.py      # Demo mode advanced
│   ├── test_metrics_panel.py           # Metrics panel (34 tests)
│   ├── test_network_visualizer.py      # Network viz (26 tests)
│   ├── test_decision_boundary.py       # Decision boundary (31 tests)
│   ├── test_dataset_plotter.py         # Dataset plotter (25 tests)
│   ├── test_dashboard_manager.py       # Dashboard (38 tests)
│   ├── test_training_metrics.py        # Training metrics
│   └── test_loggers.py                 # Logger tests
│
├── integration/             # Integration tests
│   ├── test_main_api_endpoints.py      # API endpoint tests
│   ├── test_websocket_control.py       # WebSocket control (10 tests)
│   ├── test_cascor_backend_integration.py
│   ├── test_mvp_functionality.py
│   ├── test_architectural_fixes.py
│   └── test_config.py
│
├── performance/             # Performance tests
│   └── (future performance tests)
│
├── fixtures/                # Shared test fixtures
│   └── conftest.py
│
├── helpers/                 # Test helper utilities
│   └── test_utils.py
│
└── mocks/                   # Mock objects
    └── mock_cascor.py
```

### Test Naming Conventions

```python
# Test files: test_<module_name>.py
test_demo_mode.py
test_config_manager.py

# Test functions: test_<what_is_tested>
def test_demo_mode_initialization():
    pass

def test_singleton_pattern():
    pass

# Test classes: Test<ClassName>
class TestDemoMode:
    def test_start_stop(self):
        pass

# Integration tests: test_<integration_scenario>
def test_websocket_control_integration():
    pass
```

## Writing Tests

### Basic Test Structure

```python
#!/usr/bin/env python
"""
Test module for <component>.

Tests cover:
- Core functionality
- Edge cases
- Error handling
"""

import pytest
from src.module import Component


def test_basic_functionality():
    """Test basic functionality of Component."""
    # Arrange
    component = Component()

    # Act
    result = component.do_something()

    # Assert
    assert result == expected_value


def test_edge_case():
    """Test edge case handling."""
    component = Component()

    with pytest.raises(ValueError):
        component.invalid_operation()
```

### Using Fixtures

```python
import pytest


@pytest.fixture
def demo_mode():
    """Create DemoMode instance for testing."""
    from demo_mode import DemoMode
    dm = DemoMode()
    yield dm
    # Cleanup
    if dm.is_running:
        dm.stop()


def test_demo_mode_start(demo_mode):
    """Test starting demo mode."""
    demo_mode.start()
    assert demo_mode.is_running
```

### Async Tests

```python
import pytest


@pytest.mark.asyncio
async def test_websocket_broadcast():
    """Test WebSocket broadcasting."""
    from communication.websocket_manager import WebSocketManager

    manager = WebSocketManager()

    # Test async operation
    await manager.broadcast({"type": "test"})

    assert manager.connection_count == 0
```

### Parameterized Tests

```python
import pytest


@pytest.mark.parametrize("input_value,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (0, 0),
])
def test_double(input_value, expected):
    """Test doubling function with multiple inputs."""
    assert double(input_value) == expected


@pytest.mark.parametrize("config,valid", [
    ({"port": 8050}, True),
    ({"port": "invalid"}, False),
    ({}, False),
])
def test_config_validation(config, valid):
    """Test config validation."""
    validator = ConfigValidator()
    assert validator.validate(config) == valid
```

### Testing Exceptions

```python
import pytest


def test_invalid_input_raises():
    """Test that invalid input raises ValueError."""
    component = Component()

    with pytest.raises(ValueError):
        component.process(None)


def test_exception_message():
    """Test exception message content."""
    component = Component()

    with pytest.raises(ValueError, match="Invalid input"):
        component.process("invalid")
```

### Mocking

```python
import pytest
from unittest.mock import Mock, patch, MagicMock


def test_with_mock():
    """Test using mock objects."""
    mock_backend = Mock()
    mock_backend.get_metrics.return_value = {"loss": 0.5}

    component = Component(backend=mock_backend)
    result = component.fetch_metrics()

    assert result["loss"] == 0.5
    mock_backend.get_metrics.assert_called_once()


@patch('module.external_api_call')
def test_with_patch(mock_api):
    """Test using patch decorator."""
    mock_api.return_value = {"status": "ok"}

    result = function_that_calls_api()

    assert result["status"] == "ok"
```

### Testing Thread Safety

```python
import pytest
import threading


def test_thread_safety():
    """Test concurrent access is thread-safe."""
    demo_mode = DemoMode()
    demo_mode.start()

    errors = []

    def read_state():
        try:
            for _ in range(100):
                demo_mode.get_current_state()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=read_state) for _ in range(10)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    demo_mode.stop()
```

## Test Fixtures

### Global Fixtures (conftest.py)

```python
# Located at src/tests/conftest.py

@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide test configuration dictionary."""
    return {
        "application": {"name": "Test", "version": "1.0.0"},
        "server": {"host": "127.0.0.1", "port": 8050},
    }


@pytest.fixture
def sample_training_metrics() -> list:
    """Generate sample training metrics."""
    return [
        {
            "epoch": i,
            "loss": 1.0 / (i + 1),
            "accuracy": (i / 10) * 0.9,
        }
        for i in range(10)
    ]


@pytest.fixture
def temp_test_directory(tmp_path):
    """Create temporary directory structure."""
    test_dir = tmp_path / "cascor_test"
    test_dir.mkdir()
    (test_dir / "logs").mkdir()
    return test_dir
```

### Fixture Scopes

```python
# Function scope (default) - created for each test
@pytest.fixture(scope="function")
def function_fixture():
    return "created per test"


# Class scope - created once per test class
@pytest.fixture(scope="class")
def class_fixture():
    return "created per class"


# Module scope - created once per module
@pytest.fixture(scope="module")
def module_fixture():
    return "created per module"


# Session scope - created once per test session
@pytest.fixture(scope="session")
def session_fixture():
    return "created once"
```

### Fixture Cleanup

```python
@pytest.fixture
def resource_fixture():
    """Fixture with cleanup."""
    # Setup
    resource = acquire_resource()

    yield resource

    # Cleanup (runs after test)
    release_resource(resource)
```

### Auto-use Fixtures

```python
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    # Runs automatically before each test
    ConfigManager._instance = None
    DemoMode._instance = None

    yield

    # Cleanup after test
    ConfigManager._instance = None
    DemoMode._instance = None
```

## Test Markers

### Using Markers

```python
import pytest


@pytest.mark.unit
def test_unit_functionality():
    """Unit test."""
    pass


@pytest.mark.integration
def test_integration_scenario():
    """Integration test."""
    pass


@pytest.mark.slow
def test_long_running_operation():
    """Slow test."""
    pass


@pytest.mark.requires_cascor
def test_with_cascor_backend():
    """Test requiring CasCor backend."""
    pass
```

### Available Markers

| Marker                         | Description       | Usage                       |
| ------------------------------ | ----------------- | --------------------------- |
| `@pytest.mark.unit`            | Unit tests        | Isolated component tests    |
| `@pytest.mark.integration`     | Integration tests | Component interaction tests |
| `@pytest.mark.performance`     | Performance tests | Speed/resource tests        |
| `@pytest.mark.regression`      | Regression tests  | Bug fix verification        |
| `@pytest.mark.slow`            | Slow tests        | Long-running tests          |
| `@pytest.mark.requires_cascor` | Requires backend  | External dependency         |
| `@pytest.mark.asyncio`         | Async tests       | Async/await tests           |

### Running by Marker

```bash
# Run unit tests
pytest -m unit

# Run integration tests
pytest -m integration

# Run non-slow tests
pytest -m "not slow"

# Run unit and integration
pytest -m "unit or integration"

# Run integration but not slow
pytest -m "integration and not slow"
```

### Custom Markers

```python
# Register in pytest.ini
[pytest]
markers =
    custom: Custom marker description

# Use in tests
@pytest.mark.custom
def test_with_custom_marker():
    pass
```

## Coverage Analysis

### Viewing Coverage

```bash
# Terminal output
pytest --cov=src --cov-report=term

# With missing lines
pytest --cov=src --cov-report=term-missing

# HTML report
pytest --cov=src --cov-report=html

# Open HTML report
xdg-open reports/coverage/index.html
```

### Coverage Targets

| Module Type      | Target Coverage |
| ---------------- | --------------- |
| Critical modules | 100%            |
| Core modules     | 80%+            |
| Frontend modules | 60%+            |
| Overall project  | 80%+            |

### Critical Modules (100% target)

- `config_manager.py` - Configuration management
- `demo_mode.py` - Demo mode core
- `websocket_manager.py` - WebSocket communication

### Excluding Lines from Coverage

```python
def debug_function():  # pragma: no cover
    """Debug function not covered."""
    print("Debug info")


if __name__ == "__main__":  # pragma: no cover
    main()


def not_implemented():
    raise NotImplementedError  # Excluded by default
```

## Best Practices

### 1. Test Independence

```python
# GOOD: Independent tests
def test_feature_a():
    component = Component()
    assert component.feature_a() == "A"

def test_feature_b():
    component = Component()
    assert component.feature_b() == "B"


# BAD: Dependent tests
component = Component()  # Shared state

def test_feature_a():
    assert component.feature_a() == "A"

def test_feature_b():
    assert component.feature_b() == "B"  # Depends on test_feature_a
```

### 2. Descriptive Names

```python
# GOOD: Descriptive test name
def test_demo_mode_starts_with_epoch_zero():
    pass

def test_config_manager_loads_yaml_successfully():
    pass


# BAD: Vague test name
def test_demo():
    pass

def test_config():
    pass
```

### 3. Single Responsibility

```python
# GOOD: Test one thing
def test_start_sets_running_flag():
    demo = DemoMode()
    demo.start()
    assert demo.is_running

def test_start_initializes_epoch():
    demo = DemoMode()
    demo.start()
    assert demo.epoch == 0


# BAD: Test multiple things
def test_start():
    demo = DemoMode()
    demo.start()
    assert demo.is_running
    assert demo.epoch == 0
    assert demo.metrics is not None
    # Too much in one test
```

### 4. Arrange-Act-Assert Pattern

```python
def test_feature():
    # Arrange - Setup test conditions
    component = Component()
    input_data = {"key": "value"}

    # Act - Execute the behavior
    result = component.process(input_data)

    # Assert - Verify the outcome
    assert result["status"] == "success"
```

### 5. Use Fixtures for Setup

```python
# GOOD: Use fixtures
@pytest.fixture
def configured_component():
    component = Component()
    component.configure({"setting": "value"})
    return component

def test_feature(configured_component):
    assert configured_component.setting == "value"


# BAD: Duplicate setup
def test_feature_a():
    component = Component()
    component.configure({"setting": "value"})
    # Test code

def test_feature_b():
    component = Component()
    component.configure({"setting": "value"})
    # Test code
```

### 6. Test Edge Cases

```python
def test_with_empty_input():
    component = Component()
    result = component.process([])
    assert result == []

def test_with_none_input():
    component = Component()
    with pytest.raises(ValueError):
        component.process(None)

def test_with_large_input():
    component = Component()
    large_input = list(range(10000))
    result = component.process(large_input)
    assert len(result) == 10000
```

### 7. Clean Up Resources

```python
def test_with_cleanup():
    # Setup
    resource = acquire_resource()

    try:
        # Test code
        result = use_resource(resource)
        assert result is not None
    finally:
        # Always cleanup
        release_resource(resource)


# Better: Use fixture
@pytest.fixture
def resource():
    r = acquire_resource()
    yield r
    release_resource(r)

def test_with_fixture(resource):
    result = use_resource(resource)
    assert result is not None
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r conf/requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files

# Configuration in .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
# Problem: ModuleNotFoundError
# Solution: Activate conda environment
conda activate JuniperPython
```

#### 2. Test Discovery Fails

```bash
# Problem: No tests collected
# Solution: Check pytest.ini and __init__.py files
pytest --collect-only -v
```

#### 3. Fixture Not Found

```bash
# Problem: fixture 'xxx' not found
# Solution: Check conftest.py location and imports
pytest --fixtures  # List all available fixtures
```

#### 4. Async Test Failures

```bash
# Problem: RuntimeWarning: coroutine was never awaited
# Solution: Add @pytest.mark.asyncio and install pytest-asyncio
pip install pytest-asyncio
```

#### 5. Coverage Not Working

```bash
# Problem: Coverage 0%
# Solution: Ensure source path is correct
pytest --cov=src --cov-report=term-missing
```

### Debug Tests

```bash
# Run with pdb on failure
pytest --pdb

# Run with verbose output
pytest -vv

# Show local variables on failure
pytest -l

# Show print statements
pytest -s

# Show warnings
pytest -W default
```

## Next Steps

- **Quick Reference**: See [TESTING_REFERENCE.md](TESTING_REFERENCE.md)
- **Coverage Reports**: See [TESTING_REPORTS_COVERAGE.md](TESTING_REPORTS_COVERAGE.md)
- **Quick Start**: See [TESTING_QUICK_START.md](TESTING_QUICK_START.md)
- **Environment Setup**: See [TESTING_ENVIRONMENT_SETUP.md](TESTING_ENVIRONMENT_SETUP.md)

---

**Happy Testing!**
