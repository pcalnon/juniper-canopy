# Testing Reference - Technical Documentation

**Last Updated:** January 29, 2026  
**Version:** v0.25.0

Complete technical reference for the Juniper Canopy testing infrastructure.

## Table of Contents

1. [Test Framework Architecture](#test-framework-architecture)
2. [Configuration Reference](#configuration-reference)
3. [Fixture Reference](#fixture-reference)
4. [Marker Reference](#marker-reference)
5. [Command Reference](#command-reference)
6. [Plugin Reference](#plugin-reference)
7. [Coverage Configuration](#coverage-configuration)
8. [API Testing Reference](#api-testing-reference)
9. [Performance Testing](#performance-testing)
10. [Advanced Topics](#advanced-topics)

## Test Framework Architecture

### Components

```bash
Testing Infrastructure
├── pytest                    # Core test framework
├── pytest-cov                # Coverage plugin
├── pytest-asyncio            # Async test support
├── pytest-html               # HTML test reports
├── pytest-json-report        # JSON test reports
├── pytest-mock               # Mocking utilities
└── coverage.py               # Coverage measurement
```

### Execution Flow

```bash
1. pytest collection
   ├── Discover test files (test_*.py)
   ├── Discover test functions (test_*)
   ├── Discover test classes (Test*)
   └── Apply markers and filters

2. pytest setup
   ├── Load conftest.py files
   ├── Register fixtures
   ├── Initialize plugins
   └── Configure coverage

3. pytest execution
   ├── Session setup (scope="session" fixtures)
   ├── Module setup (scope="module" fixtures)
   ├── Function setup (scope="function" fixtures)
   ├── Run test
   ├── Function teardown
   ├── Module teardown
   └── Session teardown

4. pytest reporting
   ├── Collect results
   ├── Generate coverage report
   ├── Generate HTML report
   ├── Generate JUnit XML
   └── Display summary
```

## Configuration Reference

### pytest.ini

```ini
[pytest]
# Test discovery paths
testpaths = src/tests

# File patterns
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Default options
addopts =
    --verbose                              # Verbose output
    --color=yes                            # Colored output
    --cov=src                              # Coverage source
    --cov-report=html:reports/coverage     # HTML coverage report
    --cov-report=term-missing              # Terminal with missing lines
    --junit-xml=reports/junit/results.xml  # JUnit XML report
    --html=reports/test_report.html        # HTML test report
    --self-contained-html                  # Standalone HTML report

# Async mode
asyncio_mode = auto

# Custom markers
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    regression: Regression tests
    end2end: End-to-end tests
    slow: Slow-running tests
    requires_redis: Tests requiring Redis connection
    requires_cascor: Tests requiring CasCor backend
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
minversion = "7.0"
testpaths = ["src/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

addopts = [
    "--verbose",
    "--color=yes",
    "--cov=src",
    "--cov-report=html:reports/coverage",
    "--cov-report=term-missing",
    "--junit-xml=reports/junit/results.xml",
    "--html=reports/test_report.html",
    "--self-contained-html",
]

markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "performance: Performance tests",
]

asyncio_mode = "auto"
```

### .coveragerc

```ini
[run]
# Source code directory
source = src

# Files to omit from coverage
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
    */site-packages/*
    */conftest.py
    */venv/*
    */.venv/*

# Enable branch coverage
branch = True

# Enable parallel coverage
parallel = True

[report]
# Display settings
show_missing = True        # Show missing lines
skip_covered = False       # Show covered files
skip_empty = True          # Skip empty files

# Coverage threshold
fail_under = 60            # Minimum 60% coverage

# Precision
precision = 2              # Two decimal places

# Lines to exclude from coverage
exclude_lines =
    pragma: no cover
    def __repr__
    def __str__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod

[html]
directory = reports/coverage
title = Juniper Canopy Coverage Report

[xml]
output = coverage.xml

[json]
output = coverage.json
pretty_print = True
```

## Fixture Reference

### Global Fixtures (src/tests/conftest.py)

#### Session Scope Fixtures

```python
@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for async tests.

    Scope: session
    Type: Generator
    Cleanup: Closes loop after all tests
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_test_data_directory():
    """
    Ensure test data directory exists.

    Scope: session
    Type: Auto-use (runs automatically)
    Returns: Path to test data directory
    """
    test_data_dir = Path(__file__).parent / "data"
    test_data_dir.mkdir(exist_ok=True)
    return test_data_dir
```

#### Function Scope Fixtures

```python
@pytest.fixture
def test_config() -> Dict[str, Any]:
    """
    Provide test configuration dictionary.

    Scope: function (default)
    Type: Factory
    Returns: Dictionary with test configuration
    """
    return {
        "application": {
            "name": "Juniper Canopy Test",
            "version": "1.0.0",
            "environment": "testing",
        },
        "server": {
            "host": "127.0.0.1",
            "port": 8050,
            "debug": False
        },
    }


@pytest.fixture
def sample_training_metrics() -> list:
    """
    Generate sample training metrics for testing.

    Scope: function
    Type: Factory
    Returns: List of metric dictionaries
    """
    return [
        {
            "epoch": i,
            "loss": 1.0 / (i + 1) + 0.1,
            "accuracy": (i / 10) * 0.9,
        }
        for i in range(10)
    ]


@pytest.fixture
def sample_network_topology() -> Dict[str, Any]:
    """
    Generate sample network topology.

    Scope: function
    Type: Factory
    Returns: Network topology dictionary
    """
    return {
        "input_units": 2,
        "hidden_units": 5,
        "output_units": 1,
        "connections": [
            {"from": "input_0", "to": "hidden_0", "weight": 0.5},
            {"from": "input_1", "to": "hidden_0", "weight": -0.3},
        ],
    }


@pytest.fixture
def sample_dataset() -> Dict[str, Any]:
    """
    Generate sample dataset for testing.

    Scope: function
    Type: Factory
    Returns: Dataset with inputs and targets
    Uses: numpy (for data generation)
    """
    import numpy as np
    np.random.seed(42)

    n_samples = 100
    X = np.random.randn(n_samples, 2)
    y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(int)

    return {
        "name": "test_dataset",
        "inputs": X.tolist(),
        "targets": y.tolist(),
        "n_samples": n_samples,
    }


@pytest.fixture
def temp_test_directory(tmp_path):
    """
    Create temporary directory structure for testing.

    Scope: function
    Type: Directory factory
    Args: tmp_path (pytest built-in)
    Returns: Path to temporary test directory
    Cleanup: Automatic (tmp_path handles cleanup)
    """
    test_dir = tmp_path / "cascor_test"
    test_dir.mkdir()
    (test_dir / "logs").mkdir()
    (test_dir / "data").mkdir()
    (test_dir / "images").mkdir()
    return test_dir


@pytest.fixture
def mock_config_file(tmp_path):
    """
    Create temporary configuration file for testing.

    Scope: function
    Type: File factory
    Args: tmp_path (pytest built-in)
    Returns: Path to temporary YAML config file
    """
    config_content = """
application:
    name: "Juniper Canopy Test"
    version: "1.0.0"

server:
    host: "127.0.0.1"
    port: 8050
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)
    return config_file
```

#### Auto-use Fixtures

```python
@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset singleton instances before each test for proper isolation.

    Scope: function
    Type: Auto-use (runs before every test)
    Purpose: Ensure test isolation for singleton patterns
    """
    with contextlib.suppress(ImportError):
        from config_manager import ConfigManager
        from demo_mode import DemoMode

        # Reset before test
        if hasattr(ConfigManager, "_instance"):
            ConfigManager._instance = None
        if hasattr(DemoMode, "_instance"):
            if DemoMode._instance is not None:
                DemoMode._instance.stop()
            DemoMode._instance = None

    yield  # Test runs here

    # Reset after test
    # ... cleanup code ...


@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """
    Clean up test environment after each test.

    Scope: function
    Type: Auto-use
    Purpose: Remove test-specific environment variables
    """
    yield  # Test runs here

    # Cleanup after test
    test_env_vars = [k for k in os.environ if k.startswith("CASCOR_TEST_")]
    for var in test_env_vars:
        del os.environ[var]
```

### Built-in Pytest Fixtures

```python
# Temporary directory (unique per test)
def test_with_tmp_path(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("content")


# Temporary directory (shared in module)
def test_with_tmpdir(tmpdir):
    p = tmpdir.mkdir("sub").join("test.txt")
    p.write("content")


# Capture output
def test_with_capsys(capsys):
    print("hello")
    captured = capsys.readouterr()
    assert captured.out == "hello\n"


# Monkeypatch (modify objects/environ)
def test_with_monkeypatch(monkeypatch):
    monkeypatch.setenv("KEY", "value")
    monkeypatch.setattr("module.attr", "new_value")


# Request object (fixture introspection)
def test_with_request(request):
    print(request.node.name)
    print(request.config.rootdir)
```

## Marker Reference

### Standard Markers

```python
import pytest

# Unit tests - isolated component tests
@pytest.mark.unit
def test_component_logic():
    pass

# Integration tests - component interactions
@pytest.mark.integration
def test_api_integration():
    pass

# Performance tests - speed/resource tests
@pytest.mark.performance
def test_processing_speed():
    pass

# Regression tests - bug fix verification
@pytest.mark.regression
def test_bug_123_fixed():
    pass

# Slow tests - long-running tests
@pytest.mark.slow
def test_long_operation():
    pass

# External dependencies
@pytest.mark.requires_cascor
def test_with_cascor_backend():
    pass

# Async tests
@pytest.mark.asyncio
async def test_async_operation():
    await async_function()
```

### Skip Markers

```python
# Skip test unconditionally
@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

# Skip test conditionally
@pytest.mark.skipif(sys.version_info < (3, 11), reason="Requires Python 3.11+")
def test_new_feature():
    pass

# Expected to fail
@pytest.mark.xfail(reason="Known bug #123")
def test_known_issue():
    pass

# Expected to fail conditionally
@pytest.mark.xfail(sys.platform == "win32", reason="Windows not supported")
def test_unix_feature():
    pass
```

### Parametrize Marker

```python
# Single parameter
@pytest.mark.parametrize("value", [1, 2, 3])
def test_values(value):
    assert value > 0

# Multiple parameters
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
])
def test_double(input, expected):
    assert double(input) == expected

# Named parameters
@pytest.mark.parametrize("test_input,expected", [
    pytest.param(1, 2, id="one"),
    pytest.param(2, 4, id="two"),
    pytest.param(3, 6, id="three"),
])
def test_named(test_input, expected):
    assert double(test_input) == expected
```

## Command Reference

### Basic Commands

```bash
# Run all tests
pytest

# Verbose output
pytest -v

# Extra verbose
pytest -vv

# Quiet mode (less output)
pytest -q

# Stop at first failure
pytest -x

# Stop after N failures
pytest --maxfail=3

# Run specific test
pytest path/to/test.py::test_function

# Run test class
pytest path/to/test.py::TestClass

# Run test method
pytest path/to/test.py::TestClass::test_method
```

### Selection Commands

```bash
# By marker
pytest -m unit
pytest -m "unit or integration"
pytest -m "not slow"

# By keyword
pytest -k "demo_mode"
pytest -k "not slow"
pytest -k "demo_mode and not advanced"

# By node ID
pytest src/tests/unit/test_demo_mode.py::test_initialization
```

### Output Commands

```bash
# Show local variables on failure
pytest -l

# Show print statements
pytest -s

# Capture method (no/sys/fd)
pytest --capture=no

# Show test durations
pytest --durations=10

# Show all durations
pytest --durations=0

# Verbose traceback
pytest --tb=long

# Short traceback
pytest --tb=short

# No traceback
pytest --tb=no

# Show warnings
pytest -W default

# Treat warnings as errors
pytest -W error
```

### Coverage Commands

```bash
# Basic coverage
pytest --cov=src

# Coverage with missing lines
pytest --cov=src --cov-report=term-missing

# HTML coverage report
pytest --cov=src --cov-report=html

# XML coverage report (for CI)
pytest --cov=src --cov-report=xml

# JSON coverage report
pytest --cov=src --cov-report=json

# Multiple report formats
pytest --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml

# Coverage for specific module
pytest --cov=src/demo_mode --cov-report=term-missing

# Append coverage data
pytest --cov-append
```

### Debugging Commands

```bash
# Drop into pdb on failure
pytest --pdb

# Drop into pdb at start of each test
pytest --trace

# Show local variables in traceback
pytest -l

# Verbose output with local vars
pytest -vl

# Run last failed tests
pytest --lf
pytest --last-failed

# Run failures first, then rest
pytest --ff
pytest --failed-first

# Show which tests would run (dry-run)
pytest --collect-only

# Show available fixtures
pytest --fixtures

# Show markers
pytest --markers
```

### Reporting Commands

```bash
# JUnit XML report
pytest --junit-xml=reports/junit.xml

# HTML report
pytest --html=reports/report.html

# Self-contained HTML
pytest --html=reports/report.html --self-contained-html

# JSON report
pytest --json-report --json-report-file=reports/report.json

# All reports
pytest \
    --junit-xml=reports/junit.xml \
    --html=reports/report.html \
    --json-report --json-report-file=reports/report.json \
    --cov=src --cov-report=html:reports/coverage
```

### Parallel Execution (requires pytest-xdist)

```bash
# Auto-detect CPU cores
pytest -n auto

# Use N workers
pytest -n 4

# Distribute by module
pytest -n auto --dist=loadscope

# Distribute by test
pytest -n auto --dist=loadfile
```

## Plugin Reference

### pytest-cov

```bash
# Installation
pip install pytest-cov

# Usage
pytest --cov=src --cov-report=html

# Options
--cov=<source>           # Source to measure
--cov-report=term        # Terminal report
--cov-report=html        # HTML report
--cov-report=xml         # XML report
--cov-report=json        # JSON report
--cov-append             # Append to existing coverage data
--cov-branch             # Enable branch coverage
--cov-fail-under=<min>   # Fail if coverage below threshold
```

### pytest-asyncio

```python
# Installation
pip install pytest-asyncio

# Configuration (pytest.ini or pyproject.toml)
asyncio_mode = auto  # auto, strict, legacy

# Usage
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result == expected

# Fixtures
@pytest.fixture
async def async_fixture():
    resource = await setup_resource()
    yield resource
    await cleanup_resource(resource)
```

### pytest-html

```bash
# Installation
pip install pytest-html

# Usage
pytest --html=reports/report.html

# Self-contained HTML
pytest --html=reports/report.html --self-contained-html

# Options
--html=<path>           # Path to HTML report
--self-contained-html   # Inline CSS and assets
```

### pytest-mock

```python
# Installation
pip install pytest-mock

# Usage
def test_with_mocker(mocker):
    # Mock object
    mock_obj = mocker.Mock()
    mock_obj.method.return_value = "result"

    # Patch
    mocker.patch('module.function', return_value="result")

    # Spy
    mocker.spy(object, 'method')
```

## Coverage Configuration

### Coverage Metrics

```python
# Statement coverage (default)
# Measures if each line of code is executed

# Branch coverage
# Measures if each branch (if/else) is taken
branch = True  # in .coveragerc

# Function coverage
# Measures if each function is called

# Missing coverage
# Shows which lines were not executed
show_missing = True  # in .coveragerc
```

### Coverage Thresholds

```ini
[report]
# Minimum coverage required
fail_under = 60  # Overall project

# Module-specific (in comments/documentation)
# Critical: 100%
# Core: 80%+
# Frontend: 60%+
```

### Excluding Code from Coverage

```python
# Pragma comment
def debug_function():  # pragma: no cover
    print("Debug")

# Via configuration (.coveragerc)
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
    @abstractmethod
```

## API Testing Reference

### Testing FastAPI Endpoints

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_endpoint():
    """Test REST API endpoint."""
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert "loss" in response.json()

def test_api_post():
    """Test POST endpoint."""
    response = client.post("/api/control", json={"command": "start"})
    assert response.status_code == 200
```

### Testing WebSocket Endpoints

```python
from fastapi.testclient import TestClient

def test_websocket():
    """Test WebSocket connection."""
    with client.websocket_connect("/ws/training") as websocket:
        websocket.send_json({"type": "subscribe"})
        data = websocket.receive_json()
        assert data["type"] == "metrics"
```

## Performance Testing

### Timing Tests

```python
import time
import pytest

def test_performance():
    """Test execution time."""
    start = time.time()

    # Operation to test
    result = expensive_operation()

    duration = time.time() - start
    assert duration < 1.0  # Must complete in under 1 second
```

### Memory Testing

```python
import tracemalloc

def test_memory_usage():
    """Test memory consumption."""
    tracemalloc.start()

    # Operation to test
    result = memory_intensive_operation()

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 10 * 1024 * 1024  # Less than 10 MB
```

### Benchmark Plugin (pytest-benchmark)

```python
# Installation
pip install pytest-benchmark

# Usage
def test_benchmark(benchmark):
    result = benchmark(function_to_test, arg1, arg2)
    assert result == expected
```

## Advanced Topics

### Custom Markers

```python
# Register in pytest.ini
[pytest]
markers =
    smoke: Smoke tests for basic functionality
    security: Security-related tests

# Use in tests
@pytest.mark.smoke
def test_basic_functionality():
    pass
```

### Custom Fixtures

```python
# In conftest.py
@pytest.fixture
def custom_fixture():
    # Setup
    resource = create_resource()

    yield resource

    # Teardown
    cleanup_resource(resource)
```

### Fixture Factories

```python
@pytest.fixture
def make_user():
    """Factory fixture for creating users."""
    created_users = []

    def _make_user(name, email):
        user = User(name=name, email=email)
        created_users.append(user)
        return user

    yield _make_user

    # Cleanup all created users
    for user in created_users:
        user.delete()

def test_with_factory(make_user):
    user1 = make_user("Alice", "alice@example.com")
    user2 = make_user("Bob", "bob@example.com")
    # Test with multiple users
```

### Parametrize from File

```python
import json
import pytest

def load_test_cases():
    with open('test_cases.json') as f:
        return json.load(f)

@pytest.mark.parametrize("test_case", load_test_cases())
def test_from_file(test_case):
    assert process(test_case['input']) == test_case['expected']
```

---

**For practical examples and usage, see [TESTING_MANUAL.md](TESTING_MANUAL.md).**
