# Testing Manual - Comprehensive User Guide

**Last Updated:** 2026-09-05  
**Version:** v0.26.2

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

- A large multi-suite test corpus across unit, integration, regression, performance, and API categories
- Marker-gated infrastructure tests (`requires_server`, `requires_cascor`, `requires_redis`, `requires_cassandra`, `requires_display`)
- Coverage enforcement in CI (`fail_under = 80`)
- Automated execution through GitHub Actions

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
pytest -m "not requires_cascor and not requires_server and not requires_redis and not requires_cassandra and not requires_display"
```

### X7 event-loop suite

```bash
# Slice 1b client budget (on main)
pytest src/tests/regression/test_x7_client_budget.py -v

# Slice 1a gate + responsiveness (land with #567). Not marked slow on purpose.
pytest src/tests/regression/test_x7_off_loop_discipline.py \
  src/tests/regression/test_x7_loop_responsiveness.py -v
```

The structural gate reads `main.py` only. After adapter edits run
`python util/ad-hoc/2026-09-04_async_blocking_callgraph.py` (needs sibling
`juniper-cascor-client`). See [AGENTS_REFERENCE.md § Event-loop I/O discipline](../AGENTS_REFERENCE.md#event-loop-io-discipline-x7).

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

# X7 slice 1c — classifier, status-bar class routing, breaker isolation, staleness
# Landed with #578.
pytest src/tests/regression/test_x7_status_cache.py -v
```

See [TESTING_REFERENCE.md — X7 Status Cache](TESTING_REFERENCE.md#x7-status-cache-slice-1c)
and [AGENTS_REFERENCE.md — Cascor status cache](../AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c).

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

### Optional Testing Extras for Service-Mode Suites

Some backend/service tests rely on testing helpers from optional client extras.

Install when needed:

```bash
pip install "juniper-cascor-client[testing]" "juniper-data-client[testing]"
```

Why this matters:

- Service-mode tests now gate on `pytest.importorskip("juniper_cascor_client.testing", ...)`.
- Dataset versioning tests using `FakeDataClient` gate on `juniper_data_client.testing`.
- Without these extras, tests are skipped by design instead of failing collection.

### High-Signal Regression Commands

```bash
# Service normalization contract tests
cd src
pytest tests/unit/test_response_normalization.py -k "Fix1 or Fix2 or Fix3 or Fix4 or Fix13 or DashboardMetricsContract or TopologyTransformation or DatasetTargetConversion" -v

# ServiceBackend status/dataset normalization tests
pytest tests/unit/test_service_backend.py -k "get_status or get_dataset" -v

# Metrics panel handler edge-case tests (replay/progress/validation overlays)
pytest tests/unit/frontend/test_metrics_panel_handlers.py -k "validation_overlay or replay or progress_detail or training_progress or hidden_units" -v

# Documentation link checker regression tests
pytest tests/unit/test_doc_link_checker.py -v

# F-CANOPY-047: plotly PNG export vs Bootstrap CSP pair
pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v
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

| Marker                            | Description                        | Usage                                 |
| --------------------------------- | ---------------------------------- | ------------------------------------- |
| `@pytest.mark.unit`               | Unit tests                         | Isolated component tests              |
| `@pytest.mark.integration`        | Integration tests                  | Component interaction tests           |
| `@pytest.mark.performance`        | Performance tests                  | Speed/resource tests                  |
| `@pytest.mark.regression`         | Regression tests                   | Bug fix verification                  |
| `@pytest.mark.e2e`                | End-to-end tests                   | Full-system scenarios                 |
| `@pytest.mark.slow`               | Slow tests                         | Long-running tests                    |
| `@pytest.mark.requires_cascor`    | Requires CasCor backend            | External dependency                   |
| `@pytest.mark.requires_server`    | Requires running server            | Live endpoint/WebSocket validation    |
| `@pytest.mark.requires_redis`     | Requires Redis                     | Redis integration tests               |
| `@pytest.mark.requires_cassandra` | Requires Cassandra                 | Cassandra integration tests           |
| `@pytest.mark.requires_display`   | Requires display                   | GUI/visual tests                      |
| `@pytest.mark.api`                | API endpoint tests                 | HTTP contract testing                 |
| `@pytest.mark.generators`         | Generator/data tests               | Data generation and helper coverage   |
| `@pytest.mark.asyncio`            | Async tests                        | Async/await tests                     |

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

### Known Coverage Gap Watchlist (Release Readiness)

The release-readiness review identified these modules as historically under-covered and worth tracking in regression suites:

- `discovery.py` - service discovery probing behavior
- `observability.py` - metrics labeling and Sentry/telemetry setup
- `secrets_util.py` - secret-loading and decryption utility paths

Quick verification commands:

```bash
cd src
pytest tests/unit/test_cascor_discovery.py -v
pytest tests/unit/test_observability.py -v
pytest tests/unit/test_secrets_util.py -v
```

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

The active CI pipeline is split across multiple jobs in `.github/workflows/ci.yml`.
For testing-relevant behavior, CI currently uses:

- Python matrix `3.12`, `3.13`, `3.14` for `pre-commit` and `unit-tests`
- Python `3.14` for non-matrix jobs (integration/security/build/docs/lockfile)
- `conf/requirements_ci.txt` plus editable install (`pip install -e .`)
- Unit/regression fast subset:
  `-m "not requires_cascor and not requires_server and not slow"`
- Integration fast subset:
  `-m "integration and not requires_cascor and not requires_server and not slow"`

Reference commands (mirrors CI):

```bash
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .

cd src
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  tests/unit/ tests/regression/ \
  --verbose --timeout=60 --maxfail=5 \
  --cov=. --cov-report=term-missing --cov-fail-under=80

python -m pytest \
  -m "integration and not requires_cascor and not requires_server and not slow" \
  tests/integration \
  --verbose --timeout=120 --maxfail=3
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files

# CI uses pre-commit as its own matrix job
# See .github/workflows/ci.yml job: pre-commit
```

## Troubleshooting

### Common Issues

#### 1. Import Errors

```bash
# Problem: ModuleNotFoundError
# Solution: Activate conda environment
conda activate JuniperCanopy1
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

#### 5. Optional Testing Extras Missing (Collection or Import Skips)

```bash
# Symptom: ModuleNotFoundError for juniper_*_client.testing or skipped tests
# Fix: install testing extras used by service-integration unit tests
pip install "juniper-data-client[testing]" "juniper-cascor-client[testing]"
```

Collection-safe patterns used in the suite:

- `pytest.importorskip("juniper_cascor_client.testing", reason="requires juniper-cascor-client[testing]")`
- `@pytest.mark.skipif(not _has_jdc_testing, reason="requires juniper-data-client[testing]")`

Use `pytest --collect-only -q` after dependency changes to catch import-time failures early.

#### 6. Coverage Not Working

```bash
# Problem: Coverage 0%
# Solution: Ensure source path is correct
pytest --cov=src --cov-report=term-missing
```

#### 6. `requires_server` Tests Are Skipped in CI

```bash
# Problem: tests marked requires_server are skipped in default CI profile
# Solution: run with an active app server and opt-in variable
export RUN_SERVER_TESTS=1
cd src
pytest tests/ -m requires_server -v
```

#### 7. Service Metrics Shape Mismatch in Dashboard Tests

```bash
# Symptom: metrics panel tests fail with missing nested keys
# Check: metrics payload must include nested metrics/network_topology
pytest tests/unit/frontend/test_metrics_panel_handlers.py -k "metrics_display" -v
```

Expected per-entry shape:

- `entry["metrics"]["loss"]` / `entry["metrics"]["accuracy"]`
- `entry["metrics"]["val_loss"]` / `entry["metrics"]["val_accuracy"]`
- `entry["network_topology"]["hidden_units"]`

If only flat keys (`train_loss`, `train_accuracy`) are present at top-level, normalize through service adapter helpers before UI consumption.

#### 8. Zero Values Dropped During Status/Metrics Assertions

```bash
# Symptom: epoch=0 or hidden_units=0 treated as missing
# Check dedicated normalization coverage
pytest tests/unit/test_response_normalization.py -k "epoch_zero_preserved or hidden_units_zero_preserved or ZeroMetricPreservation" -v
```

Avoid `or` fallbacks when zero is valid. Prefer explicit `None` checks or first-defined helper logic.

#### 8. Documentation Link Validation Fails in CI

```bash
# Symptom: "FAILED: Documentation link validation"
# Reproduce CI docs job locally from repo root
python scripts/check_doc_links.py \
  --exclude templates --exclude history \
  --exclude pull_requests --exclude releases \
  --exclude analysis --exclude fixes --exclude development \
  --exclude CHANGELOG.md \
  --cross-repo skip
```

If checker behavior appears to regress, run the dedicated test module:

```bash
cd src
pytest tests/unit/test_doc_link_checker.py -v
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
