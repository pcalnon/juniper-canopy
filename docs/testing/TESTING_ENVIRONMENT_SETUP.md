# Testing Environment Setup

**Last Updated:** January 29, 2026  
**Version:** v0.25.0

Complete guide to setting up the testing environment for Juniper Canopy.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Installing Test Dependencies](#installing-test-dependencies)
4. [IDE Configuration](#ide-configuration)
5. [Directory Structure](#directory-structure)
6. [Configuration Files](#configuration-files)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python**: 3.11, 3.12, or 3.13
- **Conda/Miniforge**: For environment management
- **Git**: For version control

### Conda Environment

The project uses the `JuniperPython` conda environment:

```bash
# Location
/opt/miniforge3/envs/JuniperPython

# Activate
conda activate JuniperPython

# Verify activation
which python
# Should output: /opt/miniforge3/envs/JuniperPython/bin/python
```

## Environment Configuration

### 1. Clone Repository

```bash
cd ~/Development/python/Juniper/juniper-canopy
git clone <repository-url> juniper_canopy
cd juniper_canopy
```

### 2. Activate Environment

```bash
conda activate JuniperPython
```

### 3. Set Environment Variables (Optional)

```bash
# Enable debug mode
export CASCOR_DEBUG=1

# Enable demo mode
export CASCOR_DEMO_MODE=1

# Custom configuration path
export CASCOR_CONFIG_PATH=/path/to/config.yaml

# Test-specific variables
export CASCOR_TEST_MODE=1
export CASCOR_TEST_DB_PATH=/tmp/test_db
```

## Installing Test Dependencies

### Core Dependencies

```bash
# Install from requirements file
pip install -r conf/requirements.txt
```

### Test-Specific Dependencies

```bash
# Core testing
pip install pytest>=7.0
pip install pytest-cov>=4.0
pip install pytest-asyncio>=0.21
pip install pytest-mock>=3.10

# Test reporting
pip install pytest-html>=3.1
pip install pytest-json-report>=1.5

# Code quality
pip install black>=23.0
pip install isort>=5.12
pip install flake8>=6.0
pip install mypy>=1.0
pip install bandit>=1.7

# Pre-commit hooks
pip install pre-commit>=3.0
```

### Verify Installation

```bash
# Check pytest
pytest --version

# Check coverage
pytest-cov --version

# List installed packages
pip list | grep pytest
```

## IDE Configuration

### VS Code

1. **Install Python Extension**
   - Install "Python" extension by Microsoft

2. **Configure Python Interpreter**

   ```json
   // .vscode/settings.json
   {
     "python.defaultInterpreterPath": "/opt/miniforge3/envs/JuniperPython/bin/python",
     "python.testing.pytestEnabled": true,
     "python.testing.pytestArgs": [
       "src/tests",
       "-v"
     ],
     "python.testing.unittestEnabled": false,
     "python.testing.cwd": "${workspaceFolder}",
     "python.linting.enabled": true,
     "python.linting.flake8Enabled": true,
     "python.formatting.provider": "black",
     "python.formatting.blackArgs": [
       "--line-length=120"
     ]
   }
   ```

3. **Launch Configuration**

   ```json
   // .vscode/launch.json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "Python: Current Test File",
         "type": "python",
         "request": "launch",
         "module": "pytest",
         "args": [
           "${file}",
           "-v"
         ],
         "console": "integratedTerminal",
         "justMyCode": false
       },
       {
         "name": "Python: All Tests",
         "type": "python",
         "request": "launch",
         "module": "pytest",
         "args": [
           "src/tests",
           "-v",
           "--cov=src"
         ],
         "console": "integratedTerminal"
       }
     ]
   }
   ```

### PyCharm

1. **Configure Project Interpreter**
   - File → Settings → Project → Python Interpreter
   - Add → Conda Environment → Existing
   - Select: `/opt/miniforge3/envs/JuniperPython/bin/python`

2. **Configure Pytest**
   - File → Settings → Tools → Python Integrated Tools
   - Default test runner: pytest
   - Working directory: `$PROJECT_DIR$`

3. **Run Configuration**
   - Run → Edit Configurations → Add New → Python tests → pytest
   - Target: `src/tests`
   - Additional arguments: `-v --cov=src`

## Directory Structure

### Create Required Directories

```bash
# From project root
mkdir -p reports/coverage
mkdir -p reports/junit
mkdir -p logs
mkdir -p data
mkdir -p images
```

### Test Directory Structure

```bash
src/tests/
├── __init__.py
├── conftest.py              # Global fixtures
├── pytest.ini               # Pytest configuration
├── unit/                    # Unit tests
│   ├── __init__.py
│   ├── test_config_manager.py
│   ├── test_demo_mode.py
│   └── ...
├── integration/             # Integration tests
│   ├── __init__.py
│   ├── test_main_api_endpoints.py
│   ├── test_websocket_control.py
│   └── ...
├── performance/             # Performance tests
│   ├── __init__.py
│   └── ...
├── fixtures/                # Test fixtures
│   ├── __init__.py
│   └── conftest.py
├── helpers/                 # Test helpers
│   ├── __init__.py
│   └── test_utils.py
└── mocks/                   # Mock objects
    ├── __init__.py
    └── mock_cascor.py
```

## Configuration Files

### pytest.ini

Located at `src/tests/pytest.ini`:

```ini
[pytest]
testpaths = src/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --color=yes
    --cov=src
    --cov-report=html:reports/coverage
    --cov-report=term-missing
    --junit-xml=reports/junit/results.xml
    --html=reports/test_report.html
    --self-contained-html
asyncio_mode = auto
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

### .coveragerc

Located at project root:

```ini
[run]
source = src
omit =
    */tests/*
    */test_*.py
    */__pycache__/*
    */site-packages/*
    */conftest.py
    */venv/*
    */.venv/*
branch = True
parallel = True

[report]
show_missing = True
skip_covered = False
skip_empty = True
fail_under = 60
precision = 2

[html]
directory = reports/coverage
title = Juniper Canopy Coverage Report
```

### pyproject.toml

Test configuration section:

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
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "performance: Performance tests",
]
asyncio_mode = "auto"
```

### Pre-commit Configuration

Located at `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        args: [--line-length=120]

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort
        args: [--profile=black, --line-length=120]

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=120]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports]
```

Install hooks:

```bash
pre-commit install
pre-commit run --all-files
```

## Verification

### 1. Verify Python Environment

```bash
# Check Python version
python --version
# Should be: Python 3.11.x, 3.12.x, or 3.13.x

# Check Python path
which python
# Should be: /opt/miniforge3/envs/JuniperPython/bin/python

# Check conda environment
conda info --envs | grep JuniperPython
```

### 2. Verify Test Dependencies

```bash
# Check pytest
pytest --version
# Should be: pytest 7.0+

# Check pytest-cov
pytest --version --cov
# Should show coverage plugin loaded

# List all pytest plugins
pytest --version --verbose
```

### 3. Run Test Discovery

```bash
# Collect tests without running
pytest --collect-only

# Should show:
# collected XXX items
# <Module unit/test_*.py>
# <Module integration/test_*.py>
```

### 4. Run Sample Tests

```bash
# Run a single simple test
pytest src/tests/unit/test_config_manager.py::test_singleton -v

# Should pass with green output
```

### 5. Verify Coverage

```bash
# Generate coverage report
pytest --cov=src --cov-report=term

# Should show coverage percentage (target: 60%+)
```

### 6. Verify Reports Directory

```bash
# Check reports are generated
ls -la reports/coverage/
ls -la reports/junit/

# Should contain:
# - index.html (coverage)
# - results.xml (junit)
```

## Troubleshooting

### Issue: pytest not found

```bash
# Solution: Install pytest
pip install pytest

# Or reinstall all dependencies
pip install -r conf/requirements.txt
```

### Issue: Module not found errors

```bash
# Solution: Verify PYTHONPATH
echo $PYTHONPATH

# Add src directory to path
export PYTHONPATH="${PYTHONPATH}:/home/pcalnon/Development/python/Juniper/juniper-canopy/src"

# Or activate conda environment
conda activate JuniperPython
```

### Issue: Test discovery fails

```bash
# Solution: Check directory structure
find src/tests -name "test_*.py"

# Ensure __init__.py exists in all test directories
find src/tests -type d -exec sh -c 'touch {}/__init__.py' \;
```

### Issue: Coverage reports not generated

```bash
# Solution: Create reports directory
mkdir -p reports/coverage
mkdir -p reports/junit

# Run with explicit paths
pytest --cov=src --cov-report=html:reports/coverage
```

### Issue: Import errors in tests

```bash
# Solution: Check conftest.py has correct path setup
grep "sys.path" src/tests/conftest.py

# Should contain:
# src_dir = project_root / "src"
# sys.path.insert(0, str(src_dir))
```

### Issue: Async test failures

```bash
# Solution: Install pytest-asyncio
pip install pytest-asyncio

# Verify asyncio_mode in pytest.ini
grep "asyncio_mode" src/tests/pytest.ini
# Should show: asyncio_mode = auto
```

### Issue: Permission denied on reports

```bash
# Solution: Fix permissions
chmod -R 755 reports/
```

### Issue: Stale .pyc files

```bash
# Solution: Clean cache
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

## Environment Variables Reference

| Variable             | Default                | Description          |
| -------------------- | ---------------------- | -------------------- |
| `CASCOR_DEBUG`       | `0`                    | Enable debug logging |
| `CASCOR_DEMO_MODE`   | `0`                    | Run in demo mode     |
| `CASCOR_CONFIG_PATH` | `conf/app_config.yaml` | Config file path     |
| `CASCOR_TEST_MODE`   | `0`                    | Enable test mode     |
| `CASCOR_LOG_LEVEL`   | `INFO`                 | Logging level        |
| `CASCOR_SERVER_PORT` | `8050`                 | Server port          |

## Next Steps

1. **Run Quick Tests**: See [TESTING_QUICK_START.md](TESTING_QUICK_START.md)
2. **Learn Testing**: See [TESTING_MANUAL.md](TESTING_MANUAL.md)
3. **Technical Details**: See [TESTING_REFERENCE.md](TESTING_REFERENCE.md)
4. **Coverage Reports**: See [TESTING_REPORTS_COVERAGE.md](TESTING_REPORTS_COVERAGE.md)

---

**Environment setup complete! You're ready to run tests.**
