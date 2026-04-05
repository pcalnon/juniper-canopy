# Testing Environment Setup

**Last Updated:** April 5, 2026
**Version:** v0.26.0

Operational setup guide for running the Juniper Canopy test suite with the same assumptions used by CI and `src/tests/conftest.py`.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Configuration](#environment-configuration)
3. [Installing Test Dependencies](#installing-test-dependencies)
4. [IDE Configuration](#ide-configuration)
5. [Directory Structure](#directory-structure)
6. [Verification](#verification)
7. [Test Selection Controls](#test-selection-controls)
8. [Run Commands](#run-commands)
9. [Verification Checklist](#verification-checklist)
10. [Troubleshooting](#troubleshooting)
11. [References](#references)

## Prerequisites

### Required Software

- **Python**: 3.11 or newer (CI parity targets 3.12, 3.13, and 3.14)
- **Conda/Miniforge**: For environment management
- **Git**: For version control

### Conda Environment

The project uses the `JuniperCanopy` conda environment:

```bash
# Location
/opt/miniforge3/envs/JuniperCanopy

# Activate
conda activate JuniperCanopy

# Verify activation
which python
# Should output: /opt/miniforge3/envs/JuniperCanopy/bin/python
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
conda activate JuniperCanopy
```

### 3. Set Environment Variables (Optional)

```bash
# Enable debug mode
export JUNIPER_CANOPY_LOG_LEVEL=DEBUG

# Enable demo mode
export JUNIPER_CANOPY_DEMO_MODE=1

# Custom configuration path
export JUNIPER_CANOPY_SERVER__PORT=8051

# Test-specific variables
export CASCOR_BACKEND_AVAILABLE=0
export RUN_SERVER_TESTS=0
export ENABLE_SLOW_TESTS=0
```

## Installing Test Dependencies

### Core Dependencies

```bash
# Install CI-aligned requirements
pip install -r conf/requirements_ci.txt
pip install -e .
```

- Python `3.12+` (CI validates on `3.12`, `3.13`, `3.14`)
- `pip` available
- Repository checked out at project root

```bash
python --version
pip --version
```

---

## IDE Configuration

### VS Code

1. **Install Python Extension**
   - Install "Python" extension by Microsoft

2. **Configure Python Interpreter**

   ```json
   // .vscode/settings.json
   {
     "python.defaultInterpreterPath": "/opt/miniforge3/envs/JuniperCanopy/bin/python",
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
   - Select: `/opt/miniforge3/envs/JuniperCanopy/bin/python`

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
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r conf/requirements_ci.txt
pip install -e .
```

Optional local tooling:

```bash
pip install pre-commit
pre-commit install
```

## Verification

### 1. Verify Python Environment

```bash
# Check Python version
python --version
# Should be: Python 3.11+ (CI parity: 3.12/3.13/3.14)

# Check Python path
which python
# Should be: /opt/miniforge3/envs/JuniperCanopy/bin/python

# Check conda environment
conda info --envs | grep JuniperCanopy
```

## Default Test Runtime Behavior

`src/tests/conftest.py` enforces and configures critical defaults before tests run:

- Forces demo mode: `JUNIPER_CANOPY_DEMO_MODE=1`
- Sets JuniperData URL for test paths: `JUNIPER_DATA_URL=http://localhost:8100`
- Disables rate limiting in tests: `CANOPY_RATE_LIMIT_ENABLED=false`
- Adds `src/` to import path at runtime
- Injects stubs for `juniper_data_client` and `juniper_cascor_client` if missing, allowing collection and most unit/integration tests to execute without external services

Implication:

- Most tests should run offline in demo mode without a live backend stack.

---

## Test Selection Controls

Environment variables used for selective enablement:

| Variable | Effect | Default in CI |
| --- | --- | --- |
| `CASCOR_BACKEND_AVAILABLE=1` | Enables tests marked `requires_cascor` | `0` |
| `RUN_SERVER_TESTS=1` | Enables tests marked `requires_server` | `0` |
| `RUN_DISPLAY_TESTS=1` | Enables tests marked `requires_display` in headless environments | `0` |
| `ENABLE_SLOW_TESTS=1` | Enables tests marked `slow` | `0` |

Library-dependent markers:

- `requires_cassandra`: skipped if Cassandra driver is not installed
- `requires_redis`: skipped if Redis library is not installed

---

## Run Commands

Fast unit/regression pass (matches CI gate intent):

```bash
python -m pytest \
  -m "not requires_cascor and not requires_server and not slow" \
  src/tests/unit/ src/tests/regression/ \
  --verbose
```

Integration pass without external dependencies:

```bash
# Solution: Install pytest
pip install pytest

# Or reinstall all dependencies
pip install -r conf/requirements_ci.txt
pip install -e .
```

Coverage gate equivalent:

```bash
# Solution: Verify PYTHONPATH
echo $PYTHONPATH

# Add src directory to path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or activate conda environment
conda activate JuniperCanopy
```

Opt-in full suite including gated tests:

```bash
export CASCOR_BACKEND_AVAILABLE=1
export RUN_SERVER_TESTS=1
export ENABLE_SLOW_TESTS=1
python -m pytest src/tests --verbose
```

---

## Verification Checklist

- `python -m pytest --collect-only` succeeds
- Fast unit/regression run completes without collection errors
- Coverage command generates:
  - `reports/coverage.xml`
  - `reports/htmlcov/index.html`
- Marker gating behaves as expected when toggling environment variables

---

## Troubleshooting

`ModuleNotFoundError` for project modules:

- Ensure `pip install -e .` has been run in the active environment.

Unexpected skips:

- Run with `-ra` to display skip reasons.
- Check whether marker-enabling env vars are set.

Backend-dependent tests not running:

- Set `CASCOR_BACKEND_AVAILABLE=1` (and ensure backend dependencies are installed/running if required by test path).

Server-dependent tests not running:

- Set `RUN_SERVER_TESTS=1` and provide the expected running server context for those tests.

| Variable                              | Default     | Description                           |
| ------------------------------------- | ----------- | ------------------------------------- |
| `JUNIPER_CANOPY_DEMO_MODE`            | `0`         | Run in demo mode                      |
| `JUNIPER_CANOPY_LOG_LEVEL`            | `INFO`      | Application log level                 |
| `JUNIPER_CANOPY_SERVER__PORT`         | `8050`      | Server port                           |
| `CASCOR_BACKEND_AVAILABLE`            | unset/`0`   | Enable tests requiring real backend   |
| `RUN_SERVER_TESTS`                    | unset/`0`   | Enable tests requiring running server |
| `ENABLE_SLOW_TESTS`                   | unset/`0`   | Enable tests marked `slow`            |

- Re-run coverage command above and inspect `reports/htmlcov/index.html` for module-level gaps.

---

## References

- [Testing Quick Start](TESTING_QUICK_START.md)
- [Testing Manual](TESTING_MANUAL.md)
- [Testing Reference](TESTING_REFERENCE.md)
- [Selective Test Guide](SELECTIVE_TEST_GUIDE.md)
