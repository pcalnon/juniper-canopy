# Selective Test Enablement Guide

**Last Updated:** 2025-11-18  
**Version:** 1.0.0

## Overview

The juniper_canopy project uses a selective test enablement system to manage tests with different requirements. This allows you to run only the tests appropriate for your environment, improving test speed and reducing false failures.

## Test Categories

Tests are organized using pytest markers:

| Marker | Description | Enabled By Default |
|--------|-------------|-------------------|
| `unit` | Fast unit tests, no external dependencies | ✓ Yes |
| `integration` | Integration tests (may use files, DB) | ✓ Yes |
| `e2e` | End-to-end tests (full system required) | ✓ Yes |
| `slow` | Tests taking >1 second | ✗ No |
| `requires_cascor` | Requires CasCor backend installation | ✗ No |
| `requires_server` | Requires live server running | ✗ No |
| `requires_display` | Requires display for visualization | ✗ No |
| `requires_redis` | Requires Redis connection | ✗ No |

## Environment Variables

Control which tests run using environment variables:

```bash
# Enable CasCor backend tests
export CASCOR_BACKEND_AVAILABLE=1

# Enable live server tests
export RUN_SERVER_TESTS=1

# Enable display/visualization tests
export RUN_DISPLAY_TESTS=1

# Enable slow tests
export ENABLE_SLOW_TESTS=1
```

## Running Tests

### 1. Run All Default Tests

```bash
cd src
pytest tests/
```

This runs all tests **except**:

- Tests requiring CasCor backend
- Tests requiring live server
- Display tests (in headless environments)
- Slow tests

### 2. Run Only Unit Tests

```bash
cd src
pytest tests/ -m unit
```

### 3. Run Integration Tests

```bash
cd src
pytest tests/ -m integration
```

### 4. Run Tests Excluding Specific Categories

```bash
# Exclude slow and server tests
cd src
pytest tests/ -m "not slow and not requires_server"

# Exclude all external dependency tests
cd src
pytest tests/ -m "not requires_cascor and not requires_server and not requires_redis"
```

### 5. Run Only CasCor Backend Tests

First, ensure CasCor backend is available:

```bash
export CASCOR_BACKEND_PATH=/path/to/cascor
export CASCOR_BACKEND_AVAILABLE=1
cd src
pytest tests/ -m requires_cascor
```

### 6. Run Live Server Tests

Start the server in one terminal:

```bash
./demo
```

In another terminal:

```bash
export RUN_SERVER_TESTS=1
cd src
pytest tests/ -m requires_server
```

### 7. Run Display Tests

```bash
# On systems with display
cd src
pytest tests/ -m requires_display

# On headless systems, force enable
export RUN_DISPLAY_TESTS=1
cd src
pytest tests/ -m requires_display
```

### 8. Run All Tests (Including Optional)

```bash
export CASCOR_BACKEND_AVAILABLE=1
export RUN_SERVER_TESTS=1
export RUN_DISPLAY_TESTS=1
export ENABLE_SLOW_TESTS=1
cd src
pytest tests/
```

## Test Environment Configuration

At test startup, you'll see the current configuration:

```bash
=== Test Environment Configuration ===
CasCor Backend Tests: DISABLED (set CASCOR_BACKEND_AVAILABLE=1)
Live Server Tests: DISABLED (set RUN_SERVER_TESTS=1)
Display Tests: DISABLED (set RUN_DISPLAY_TESTS=1)
Slow Tests: DISABLED (set ENABLE_SLOW_TESTS=1)
========================================
```

## CI/CD Integration

### GitHub Actions

The CI pipeline automatically configures test environments:

```yaml
# Standard PR/commit tests (fast tests only)
env:
  RUN_SERVER_TESTS: 0
  CASCOR_BACKEND_AVAILABLE: 0
  ENABLE_SLOW_TESTS: 0

# Run most tests, exclude CasCor and server
jobs:
  test:
    steps:
      - name: Run Tests
        run: |
          cd src
          pytest tests/ -m "not requires_cascor and not requires_server"
```

### Nightly Builds

For comprehensive testing in nightly builds:

```yaml
# Nightly comprehensive tests
env:
  CASCOR_BACKEND_AVAILABLE: 1  # Install CasCor in setup
  RUN_SERVER_TESTS: 1          # Start server in background
  ENABLE_SLOW_TESTS: 1         # Run all tests
```

## Troubleshooting

### Tests Are Skipped Unexpectedly

**Problem:** Tests marked with `requires_cascor` are skipped even though backend is available.

**Solution:** Verify environment variable is set:

```bash
echo $CASCOR_BACKEND_AVAILABLE
# Should print: 1

# If not set:
export CASCOR_BACKEND_AVAILABLE=1
```

### Display Tests Fail in Headless Environment

**Problem:** Tests requiring display fail with "no display" errors.

**Solution:** Either run on system with display, or force enable:

```bash
export RUN_DISPLAY_TESTS=1  # Force run even without display
```

### Server Tests Timeout

**Problem:** Tests marked `requires_server` timeout or fail.

**Solution:** Ensure server is running before tests:

```bash
# Terminal 1: Start server
./demo

# Terminal 2: Wait for startup, then run tests
sleep 5
export RUN_SERVER_TESTS=1
cd src
pytest tests/ -m requires_server
```

### All Tests Run (Including Skipped Ones)

**Problem:** Tests that should be skipped are running.

**Solution:** Check if environment variables were accidentally set:

```bash
# Unset all test control variables
unset CASCOR_BACKEND_AVAILABLE
unset RUN_SERVER_TESTS
unset RUN_DISPLAY_TESTS
unset ENABLE_SLOW_TESTS

# Verify
env | grep -E "(CASCOR|RUN_|ENABLE_)"
# Should show nothing
```

## Adding New Tests

### 1. Mark Tests with Appropriate Markers

```python
import pytest

@pytest.mark.unit
def test_simple_unit():
    """Fast unit test with no dependencies."""
    assert True

@pytest.mark.integration
def test_file_integration():
    """Integration test that uses files."""
    assert Path("data/test.json").exists()

@pytest.mark.requires_cascor
@pytest.mark.integration
def test_cascor_backend():
    """Test requiring CasCor backend."""
    from backend.cascor_integration import CascorIntegration
    integration = CascorIntegration()
    assert integration.backend_available

@pytest.mark.slow
@pytest.mark.integration
def test_long_running():
    """Test that takes several seconds."""
    time.sleep(5)
    assert True
```

### 2. Combine Multiple Markers

```python
@pytest.mark.requires_server
@pytest.mark.slow
@pytest.mark.e2e
class TestFullSystemWorkflow:
    """End-to-end tests requiring server and taking time."""

    def test_complete_workflow(self):
        # ... full system test
        pass
```

### 3. Document Test Requirements

Add docstring explaining what the test requires:

```python
@pytest.mark.requires_cascor
@pytest.mark.requires_display
def test_network_visualization():
    """
    Test network visualization rendering.

    Requirements:
        - CasCor backend must be installed (CASCOR_BACKEND_AVAILABLE=1)
        - Display required for rendering (RUN_DISPLAY_TESTS=1 on headless)
    """
    # ... test code
```

## Best Practices

1. **Mark All Tests**: Every test should have at least one marker (`unit`, `integration`, `e2e`)

2. **Minimize External Dependencies**: Keep `requires_*` markers to minimum necessary

3. **Document Requirements**: Use docstrings to explain what tests need

4. **Test Locally First**: Run with environment variables locally before CI:

   ```bash
   # Simulate CI environment
   unset CASCOR_BACKEND_AVAILABLE
   unset RUN_SERVER_TESTS
   cd src
   pytest tests/ -m "not requires_cascor and not requires_server"
   ```

5. **Fast Tests First**: Optimize for fast feedback loop. Slow/external tests run in nightly builds.

6. **Clear Skip Messages**: Provide helpful skip reasons:

   ```python
   if not backend_available:
       pytest.skip("CasCor backend not available (set CASCOR_BACKEND_AVAILABLE=1)")
   ```

## Summary

The selective test enablement system provides:

- ✓ Fast local development (skip slow/external tests)
- ✓ Comprehensive CI testing (enable all tests in nightly)
- ✓ Clear test requirements (markers document dependencies)
- ✓ Flexible execution (environment variables control behavior)
- ✓ Better test organization (categorize by speed and requirements)

For questions or issues, see [TESTING_MANUAL.md](TESTING_MANUAL.md) or [TESTING_REFERENCE.md](TESTING_REFERENCE.md).
