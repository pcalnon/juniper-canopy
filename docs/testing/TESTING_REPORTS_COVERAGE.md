# Testing Reports and Coverage Guide

**Last Updated:** January 29, 2026  
**Version:** v0.25.0

Complete guide to generating, reading, and analyzing test reports and coverage metrics.

## Table of Contents

1. [Coverage Reports](#coverage-reports)
2. [Test Reports](#test-reports)
3. [CI/CD Reports](#cicd-reports)
4. [Reading Coverage Reports](#reading-coverage-reports)
5. [Coverage Improvement](#coverage-improvement)
6. [Report Automation](#report-automation)
7. [Best Practices](#best-practices)

## Coverage Reports

### Generating Coverage Reports

#### Terminal Coverage Report

```bash
# Basic terminal output
pytest --cov=src

# Output:
# ---------- coverage: platform linux, python 3.11.0 ----------
# Name                                 Stmts   Miss  Cover
# --------------------------------------------------------
# src/config_manager.py                  150     12    92%
# src/demo_mode.py                       200     34    83%
# src/communication/websocket_manager.py  120      8    93%
# --------------------------------------------------------
# TOTAL                                 2500    450    73%


# With missing line numbers
pytest --cov=src --cov-report=term-missing

# Output:
# Name                     Stmts   Miss  Cover   Missing
# ------------------------------------------------------
# src/config_manager.py      150     12    92%   45-48, 67, 89-95
# src/demo_mode.py           200     34    83%   123-145, 200-215, 267


# With branch coverage
pytest --cov=src --cov-report=term --cov-branch

# Show only files with missing coverage
pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

#### HTML Coverage Report

```bash
# Generate HTML report
pytest --cov=src --cov-report=html

# Report location: reports/coverage/index.html

# Custom output directory
pytest --cov=src --cov-report=html:reports/coverage

# Open report (Linux)
xdg-open reports/coverage/index.html

# Open report (macOS)
open reports/coverage/index.html

# Open report (Windows)
start reports/coverage/index.html
```

#### XML Coverage Report (for CI/CD)

```bash
# Generate XML report
pytest --cov=src --cov-report=xml

# Output: coverage.xml (root directory)

# Custom location
pytest --cov=src --cov-report=xml:reports/coverage.xml

# For Codecov/Coveralls
pytest --cov=src --cov-report=xml
codecov --file coverage.xml

# For Jenkins/GitLab CI
pytest --cov=src --cov-report=xml:reports/coverage.xml
```

#### JSON Coverage Report

```bash
# Generate JSON report
pytest --cov=src --cov-report=json

# Output: coverage.json

# Custom location
pytest --cov=src --cov-report=json:reports/coverage.json

# Pretty printed JSON
# (Configured in .coveragerc: pretty_print = True)
```

#### Multiple Report Formats

```bash
# Generate all formats
pytest --cov=src \
    --cov-report=html:reports/coverage \
    --cov-report=xml:coverage.xml \
    --cov-report=json:coverage.json \
    --cov-report=term-missing

# Use configuration file
# (Configured in pytest.ini or .coveragerc)
pytest
```

### Coverage Report Structure

#### HTML Report Components

```bash
reports/coverage/
├── index.html           # Main coverage overview
├── status.json          # Coverage status data
├── coverage_html.js     # Interactive features
├── style.css            # Styling
│
# Source file reports
├── src_config_manager_py.html
├── src_demo_mode_py.html
├── src_communication_websocket_manager_py.html
└── ...

# Each file report shows:
# - Coverage percentage
# - Line-by-line coverage
# - Missing lines highlighted
# - Branch coverage (if enabled)
```

#### Coverage Index Page

The `index.html` shows:

1. **Overall Coverage**: Total statements and coverage percentage
2. **Module List**: All source files with individual coverage
3. **Color Coding**:
   - 🟢 Green: High coverage (80-100%)
   - 🟡 Yellow: Medium coverage (60-79%)
   - 🔴 Red: Low coverage (0-59%)
4. **Sortable Columns**: Click to sort by coverage, name, etc.

#### Individual File Reports

Each source file report shows:

#### Example: src_demo_mode_py.html

```html
Coverage: 83% (200 statements, 34 missing)

| Line | Coverage | Source Code                         |
| ---- | -------- | ----------------------------------- |
| 1    | ✓        | #!/usr/bin/env python               |
| 2    | ✓        | """Demo mode for Juniper Canopy.""" |
...
| 123  | ✗        | def _advanced_feature(self):        |
| 124  | ✗        | return "not tested"                 |
...

# Legend:
# ✓ (green) = Line executed
# ✗ (red) = Line not executed
# ! (yellow) = Partial branch coverage
```

### Coverage Configuration

#### .coveragerc Configuration

```ini
[run]
source = src                # Source directory to measure
branch = True               # Enable branch coverage
parallel = True             # Support parallel test execution
omit =                      # Files to exclude
    */tests/*
    */test_*.py
    */__pycache__/*

[report]
show_missing = True         # Show missing line numbers
skip_empty = True           # Skip empty files
fail_under = 60             # Minimum coverage threshold
precision = 2               # Decimal places

exclude_lines =             # Lines to exclude
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:

[html]
directory = reports/coverage
title = Juniper Canopy Coverage Report

[xml]
output = coverage.xml

[json]
output = coverage.json
pretty_print = True
```

#### pyproject.toml Configuration

```toml
[tool.coverage.run]
source = ["src"]
branch = true
parallel = true

[tool.coverage.report]
show_missing = true
fail_under = 60
precision = 2

[tool.coverage.html]
directory = "reports/coverage"
title = "Juniper Canopy Coverage Report"
```

## Test Reports

### HTML Test Report

```bash
# Generate HTML test report
pytest --html=reports/test_report.html

# Self-contained HTML (includes CSS/JS inline)
pytest --html=reports/test_report.html --self-contained-html

# Output includes:
# - Test summary (passed, failed, skipped)
# - Test duration
# - Test details with full output
# - Environment info
```

### JUnit XML Report

```bash
# Generate JUnit XML (for CI/CD)
pytest --junit-xml=reports/junit/results.xml

# Used by:
# - Jenkins
# - GitLab CI
# - GitHub Actions
# - Azure Pipelines
# - CircleCI
```

### JSON Report

```bash
# Install plugin
pip install pytest-json-report

# Generate JSON report
pytest --json-report --json-report-file=reports/report.json

# Report includes:
# - Test results
# - Test durations
# - Test metadata
# - Environment info
```

### Terminal Output

```bash
# Short summary
pytest

# Verbose summary
pytest -v

# Extra verbose (show test names and docstrings)
pytest -vv

# Quiet (minimal output)
pytest -q

# Show test durations
pytest --durations=10

# Show only failures
pytest --tb=short

# Example output:
# ======================== test session starts =========================
# platform linux -- Python 3.11.0, pytest-7.4.0, pluggy-1.3.0
# rootdir: /home/user/project
# plugins: cov-4.1.0, asyncio-0.21.0
# collected 272 items
#
# tests/unit/test_demo_mode.py ................              [  5%]
# tests/unit/test_config_manager.py ................         [ 11%]
# tests/integration/test_websocket.py ..........             [ 15%]
# ...
#
# ========================= 272 passed in 12.34s =======================
```

## CI/CD Reports

### GitHub Actions Integration

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run tests with coverage
        run: |
          pytest --cov=src \
            --cov-report=xml \
            --cov-report=html \
            --junit-xml=reports/junit/results.xml

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

      - name: Upload test results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: reports/

      - name: Publish test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: reports/junit/results.xml
```

### Codecov Integration

```yaml
# .codecov.yml
coverage:
  status:
    project:
      default:
        target: 80%
        threshold: 1%
    patch:
      default:
        target: 80%

comment:
  layout: "header, diff, files"
  behavior: default

ignore:
  - "tests/"
  - "**/__pycache__/"
```

### Coverage Badge

```markdown
# In README.md

[![codecov](https://codecov.io/gh/username/repo/branch/main/graph/badge.svg)](https://codecov.io/gh/username/repo)

# Or

![Coverage](https://img.shields.io/codecov/c/github/username/repo)
```

## Reading Coverage Reports

### Understanding Coverage Metrics

#### Statement Coverage

```python
# Coverage: 100% (3/3 statements executed)
def add(a, b):
    result = a + b    # ✓ Executed
    return result     # ✓ Executed

# Test
assert add(1, 2) == 3  # ✓ Executed
```

#### Branch Coverage

```python
# Statement coverage: 100% (4/4 statements)
# Branch coverage: 50% (1/2 branches)
def abs_value(x):
    if x < 0:         # ✓ Condition evaluated
        return -x     # ✗ Branch not taken
    return x          # ✓ Branch taken

# Test (only positive values)
assert abs_value(5) == 5  # Only tests x >= 0 branch

# To achieve 100% branch coverage, add:
assert abs_value(-5) == 5  # Tests x < 0 branch
```

#### Function Coverage

```python
# Function coverage: 50% (1/2 functions called)
def used_function():      # ✓ Called
    return "used"

def unused_function():    # ✗ Never called
    return "unused"

# Test
assert used_function() == "used"
```

### Coverage Percentage Interpretation

| Coverage | Status        | Action Required               |
| -------- | ------------- | ----------------------------- |
| 0-59%    | 🔴 Critical   | Urgent: Add tests immediately |
| 60-79%   | 🟡 Low        | Important: Improve coverage   |
| 80-89%   | 🟢 Good       | Optional: Fill remaining gaps |
| 90-99%   | 🟢 Excellent  | Maintain current level        |
| 100%     | 🟢 Perfect    | Review if practical/necessary |

### Module-Specific Targets

```python
# Critical modules (100% target)
src/config_manager.py          # 92% → Add 8% more tests
src/communication/websocket_manager.py  # 93% → Add 7% more tests

# Core modules (80%+ target)
src/demo_mode.py               # 83% → ✓ Meets target
src/backend/                   # 75% → Add 5% more tests

# Frontend modules (60%+ target)
src/frontend/dashboard_manager.py  # 84% → ✓ Exceeds target
src/frontend/components/       # 71% → ✓ Exceeds target
```

### Identifying Missing Coverage

```bash
# View missing lines
pytest --cov=src --cov-report=term-missing

# Output:
# Name                     Stmts   Miss  Cover   Missing
# ------------------------------------------------------
# src/demo_mode.py           200     34    83%   123-145, 200-215, 267
#                                                 ^^^^^^^^^^^^^^^^
#                                                 Lines not tested

# Open HTML report to see code
xdg-open reports/coverage/index.html

# Navigate to src_demo_mode_py.html
# Red lines = not executed
# Yellow lines = partial branch coverage
```

## Coverage Improvement

### Step-by-Step Coverage Improvement

#### 1. Generate Current Coverage

```bash
# Generate HTML report
pytest --cov=src --cov-report=html --cov-report=term-missing

# Note current coverage: 73%
# Target: 80%
# Gap: 7% (needs ~175 more statements covered)
```

#### 2. Identify Low-Coverage Modules

```bash
# Terminal output shows:
# src/config_manager.py      92%  ← Close to target
# src/demo_mode.py           83%  ← Close to target
# src/backend/api.py         65%  ← Needs improvement
# src/frontend/controls.py   58%  ← Priority target
```

#### 3. Focus on Priority Files

```bash
# Generate coverage for specific module
pytest --cov=src/frontend/controls.py --cov-report=html

# Open HTML report
xdg-open reports/coverage/src_frontend_controls_py.html

# Identify missing lines (red highlighting)
# Lines 45-67: Error handling not tested
# Lines 89-102: Edge case not tested
```

#### 4. Write Tests for Missing Lines

```python
# test_controls.py

def test_error_handling():
    """Test error handling (lines 45-67)."""
    controls = Controls()

    with pytest.raises(ValueError):
        controls.invalid_operation()

def test_edge_case():
    """Test edge case (lines 89-102)."""
    controls = Controls()
    result = controls.edge_case_operation(None)
    assert result is None
```

#### 5. Verify Coverage Improvement

```bash
# Run tests again
pytest --cov=src --cov-report=html --cov-report=term-missing

# New coverage:
# src/frontend/controls.py   75%  ← Improved from 58%

# Overall: 75% → Target: 80% (5% gap remaining)
```

#### 6. Iterate Until Target Reached

```bash
# Repeat steps 3-5 for next priority file
# Continue until overall coverage ≥ 80%
```

### Coverage Improvement Strategies

#### 1. Test Edge Cases

```python
# Missing: Edge case handling
def process_data(data):
    if not data:
        return []
    return [x * 2 for x in data]

# Add tests for edge cases
def test_process_empty_data():
    assert process_data([]) == []

def test_process_none_data():
    assert process_data(None) == []

def test_process_single_item():
    assert process_data([5]) == [10]
```

#### 2. Test Error Paths

```python
# Missing: Error handling
def divide(a, b):
    if b == 0:
        raise ValueError("Division by zero")
    return a / b

# Add error path tests
def test_divide_by_zero():
    with pytest.raises(ValueError, match="Division by zero"):
        divide(10, 0)
```

#### 3. Test All Branches

```python
# Missing: Else branch
def categorize(value):
    if value > 100:
        return "high"
    else:
        return "low"

# Test both branches
def test_categorize_high():
    assert categorize(150) == "high"

def test_categorize_low():
    assert categorize(50) == "low"
```

#### 4. Test Private Methods

```python
# Missing: Private method coverage
class Component:
    def public_method(self):
        return self._private_method()

    def _private_method(self):
        return "private"

# Test through public interface
def test_public_method_calls_private():
    component = Component()
    result = component.public_method()
    assert result == "private"
```

#### 5. Test Initialization and Cleanup

```python
# Missing: __init__ and cleanup
class Resource:
    def __init__(self, config):
        self.config = config
        self._setup()

    def cleanup(self):
        self._teardown()

# Test initialization
def test_resource_initialization():
    resource = Resource({"key": "value"})
    assert resource.config == {"key": "value"}

# Test cleanup
def test_resource_cleanup():
    resource = Resource({})
    resource.cleanup()
    # Verify cleanup occurred
```

### Coverage Anti-Patterns

#### ❌ Don't: Write Tests Just for Coverage

```python
# BAD: Test that adds coverage but no value
def test_useless():
    component = Component()
    component.method()  # Call method but don't assert anything
    # This increases coverage but doesn't test anything
```

#### ✅ Do: Write Meaningful Tests

```python
# GOOD: Test that verifies behavior
def test_method_behavior():
    component = Component()
    result = component.method()
    assert result == expected_value
    assert component.state == expected_state
```

#### ❌ Don't: Exclude Important Code

```python
# BAD: Exclude code to inflate coverage
def important_function():  # pragma: no cover
    # This code should be tested!
    return critical_operation()
```

#### ✅ Do: Only Exclude Debug/Unreachable Code

```python
# GOOD: Exclude only debug/unreachable code
def debug_print():  # pragma: no cover
    if DEBUG:
        print("Debug info")

if __name__ == "__main__":  # pragma: no cover
    main()
```

## Report Automation

### Automated Report Generation

```bash
#!/bin/bash
# scripts/generate_reports.sh

# Generate all reports
pytest \
    --cov=src \
    --cov-report=html:reports/coverage \
    --cov-report=xml:coverage.xml \
    --cov-report=json:coverage.json \
    --cov-report=term-missing \
    --junit-xml=reports/junit/results.xml \
    --html=reports/test_report.html \
    --self-contained-html

# Open HTML reports
xdg-open reports/coverage/index.html
xdg-open reports/test_report.html

echo "Reports generated in reports/ directory"
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-coverage
        name: pytest with coverage
        entry: pytest --cov=src --cov-fail-under=60
        language: system
        pass_filenames: false
        always_run: true
```

### Make Targets

```makefile
# Makefile
.PHONY: test coverage reports

test:
 pytest -v

coverage:
 pytest --cov=src --cov-report=html --cov-report=term-missing

reports:
 pytest \
  --cov=src \
  --cov-report=html:reports/coverage \
  --junit-xml=reports/junit/results.xml \
  --html=reports/test_report.html

coverage-open:
 xdg-open reports/coverage/index.html
```

## Best Practices

### 1. Regular Coverage Monitoring

```bash
# Daily development
pytest --cov=src --cov-report=term-missing

# Before commit
pytest --cov=src --cov-fail-under=60

# Before PR
pytest --cov=src --cov-report=html
# Review HTML report for gaps
```

### 2. Coverage Thresholds

```ini
# .coveragerc
[report]
fail_under = 60  # Overall minimum

# Module-specific in CI/CD
pytest --cov=src/config_manager.py --cov-fail-under=90
pytest --cov=src/frontend/ --cov-fail-under=60
```

### 3. Coverage in Code Review

```markdown
# PR Review Checklist

- [ ] Coverage maintained or improved
- [ ] Critical paths have 100% coverage
- [ ] New code has corresponding tests
- [ ] Coverage report reviewed
- [ ] No coverage regressions
```

### 4. Coverage Trends

```bash
# Track coverage over time
echo "$(date),$(pytest --cov=src --cov-report=term | grep TOTAL | awk '{print $NF}')" >> coverage_history.csv

# Visualize trends (Python script)
python scripts/plot_coverage_trends.py
```

### 5. Documentation

```markdown
# Document coverage targets in AGENTS.md

## Coverage Targets

- Overall: 80%
- Critical modules: 100%
- Core modules: 80%+
- Frontend modules: 60%+

## Current Status

- Overall: 73% (target: 80%)
- config_manager.py: 92% ✓
- demo_mode.py: 83% ✓
- backend/: 75% (needs improvement)
```

---

**For more testing information:**

- [TESTING_QUICK_START.md](TESTING_QUICK_START.md) - Quick start guide
- [TESTING_MANUAL.md](TESTING_MANUAL.md) - Comprehensive testing guide
- [TESTING_REFERENCE.md](TESTING_REFERENCE.md) - Technical reference
- [TESTING_ENVIRONMENT_SETUP.md](TESTING_ENVIRONMENT_SETUP.md) - Environment setup

**Reports are stored in:**

- `reports/coverage/index.html` - Coverage report
- `reports/test_report.html` - Test report
- `reports/junit/results.xml` - JUnit XML
- `coverage.xml` - Coverage XML (for CI/CD)
