# Testing Quick Start Guide

Get up and running with tests in **5 minutes**.

## Prerequisites

```bash
# Activate conda environment
conda activate JuniperPython

# Verify pytest is installed
pytest --version
```

## Run All Tests

```bash
# From project root
cd /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing
```

## Common Test Commands

```bash
# Run unit tests only
pytest -m unit -v

# Run integration tests only
pytest -m integration -v

# Run specific test file
pytest src/tests/unit/test_demo_mode.py -v

# Run specific test function
pytest src/tests/unit/test_demo_mode.py::test_demo_mode_initialization -v

# Run tests matching pattern
pytest -k "demo_mode" -v

# Run with verbose output
pytest -vv

# Run and stop at first failure
pytest -x
```

## View Coverage Reports

```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open report in browser (Linux)
xdg-open reports/coverage/index.html

# Open report in browser (macOS)
open reports/coverage/index.html
```

## Quick Test Status

```bash
# See what tests exist
find src/tests -name "test_*.py" | wc -l

# Count tests
pytest --collect-only | grep "test session starts" -A 1

# Run tests with summary
pytest --tb=short -v
```

## Common Issues

### Import Errors

```bash
# Ensure conda environment is active
conda activate JuniperPython

# Verify Python path
which python
# Should be: /opt/miniforge3/envs/JuniperPython/bin/python
```

### Test Discovery Failures

```bash
# Run from project root
cd /home/pcalnon/Development/python/JuniperCanopy/juniper_canopy

# Check pytest configuration
cat src/tests/pytest.ini
```

### Coverage Not Working

```bash
# Install pytest-cov if missing
pip install pytest-cov

# Use explicit coverage command
pytest --cov=src --cov-report=html:reports/coverage
```

## Next Steps

- **Environment Setup**: See [TESTING_ENVIRONMENT_SETUP.md](TESTING_ENVIRONMENT_SETUP.md)
- **Comprehensive Guide**: See [TESTING_MANUAL.md](TESTING_MANUAL.md)
- **Coverage Details**: See [TESTING_REPORTS_COVERAGE.md](TESTING_REPORTS_COVERAGE.md)
- **Technical Reference**: See [TESTING_REFERENCE.md](TESTING_REFERENCE.md)

## Test Structure Overview

```bash
src/tests/
├── unit/              # Unit tests (isolated components)
├── integration/       # Integration tests (component interactions)
├── performance/       # Performance tests
├── conftest.py        # Global fixtures
└── pytest.ini         # Pytest configuration
```

## Current Test Statistics

- **Total Tests**: 272+
- **Pass Rate**: 100%
- **Coverage**: 73% (target: 80%)
- **Test Directories**: unit/, integration/, performance/

## Quick Reference

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -m unit` | Run unit tests |
| `pytest -m integration` | Run integration tests |
| `pytest -k "name"` | Run tests matching name |
| `pytest -x` | Stop at first failure |
| `pytest -v` | Verbose output |
| `pytest --cov=src` | Run with coverage |
| `pytest --lf` | Run last failed tests |
| `pytest --ff` | Run failures first |

---

**For detailed testing information, see the complete testing documentation suite.**
