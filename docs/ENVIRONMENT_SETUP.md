# Environment Setup Guide

## Complete Environment Configuration for Juniper Canopy

**Version:** 0.25.0  
**Status:** ✅ Production Ready  
**Last Updated:** January 29, 2026  
**Project:** Juniper - Cascade Correlation Neural Network Monitoring

---

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Conda Environment Setup](#conda-environment-setup)
- [Python Dependencies](#python-dependencies)
- [Configuration Files](#configuration-files)
- [Environment Variables](#environment-variables)
- [Path Configuration](#path-configuration)
- [Verification Steps](#verification-steps)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## Overview

This guide covers complete environment setup for Juniper Canopy development and deployment.

**What you'll set up:**

- Conda environment (JuniperPython)
- Python dependencies
- Configuration files
- Environment variables
- Path resolution
- Logging configuration

**Time required:** 15-30 minutes (first-time setup)

---

## System Requirements

### Operating System

**Supported:**

- ✅ **Linux** (Ubuntu 20.04+, Debian 10+, CentOS 8+)
- ✅ **macOS** (11.0+)
- ✅ **Windows** (WSL2 recommended, native support limited)

**Recommended:** Linux or macOS for best compatibility

### Software Requirements

| Software        | Minimum Version | Recommended  | Purpose                     |
| --------------- | --------------- | ------------ | --------------------------- |
| **Python**      | 3.11            | 3.11 or 3.12 | Runtime                     |
| **Conda/Mamba** | 4.12+           | Latest       | Environment management      |
| **Git**         | 2.20+           | Latest       | Version control             |
| **Make**        | Any             | Latest       | Build automation (optional) |
| **curl**        | Any             | Latest       | API testing                 |

### Hardware Requirements

**Minimum:**

- 2 CPU cores
- 4 GB RAM
- 2 GB disk space

**Recommended:**

- 4+ CPU cores
- 8+ GB RAM
- 10+ GB disk space (includes logs, test artifacts)

---

## Conda Environment Setup

### Install Conda/Mamba

#### Option A: Install Miniforge3 (recommended)

```bash
# Download installer
curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"

# Run installer
bash Miniforge3-$(uname)-$(uname -m).sh

# Follow prompts, accept defaults
# Restart shell when complete
```

#### Option B: Use existing Conda/Mamba

If you already have Conda/Miniconda/Anaconda installed, you can use it.

### Create JuniperPython Environment

#### Method 1: From conda_environment.yaml (recommended)

```bash
# Navigate to project
cd /path/to/juniper_canopy

# Create environment from file
conda env create -f conf/conda_environment.yaml

# Activate environment
conda activate JuniperPython
```

#### Method 2: Manual creation

```bash
# Create environment with Python 3.11
conda create -n JuniperPython python=3.11 -y

# Activate environment
conda activate JuniperPython

# Install dependencies
pip install -r conf/requirements.txt
```

### Verify Conda Environment

```bash
# Check environment exists
conda env list | grep JuniperPython

# Expected output:
# JuniperPython         /opt/miniforge3/envs/JuniperPython

# Check Python version
python --version

# Expected: Python 3.11.x or 3.12.x

# Check Python path
which python

# Expected: /opt/miniforge3/envs/JuniperPython/bin/python
```

### Environment Location

#### Default location

```bash
/opt/miniforge3/envs/JuniperPython
```

#### Custom location

```bash
# Create in specific location
conda create -p /custom/path/JuniperPython python=3.11

# Activate by path
conda activate /custom/path/JuniperPython
```

---

## Python Dependencies

### Core Dependencies

**Framework:**

- **fastapi** (0.104.0+) - Web framework
- **uvicorn** (0.24.0+) - ASGI server
- **dash** (2.14.0+) - Dashboard framework
- **plotly** (5.17.0+) - Visualization library

**Data Processing:**

- **numpy** (1.24.0+) - Numerical operations
- **pandas** (2.1.0+) - Data manipulation

**Communication:**

- **websockets** (12.0+) - WebSocket support
- **python-multipart** (0.0.6+) - Form data parsing

**Configuration:**

- **pyyaml** (6.0+) - YAML parsing
- **python-dotenv** (1.0.0+) - Environment variable loading

### Development Dependencies

**Testing:**

- **pytest** (7.4.0+) - Testing framework
- **pytest-cov** (4.1.0+) - Coverage plugin
- **pytest-asyncio** (0.21.0+) - Async test support
- **pytest-mock** (3.12.0+) - Mocking support

**Code Quality:**

- **black** (23.10.0+) - Code formatter
- **isort** (5.12.0+) - Import sorter
- **flake8** (6.1.0+) - Linter
- **mypy** (1.6.0+) - Type checker
- **bandit** (1.7.5+) - Security scanner

**Pre-commit:**

- **pre-commit** (3.5.0+) - Git hook framework

### Install Dependencies

**From requirements.txt:**

```bash
# Activate environment first
conda activate JuniperPython

# Install all dependencies
pip install -r conf/requirements.txt

# Install with specific versions
pip install -r conf/requirements.txt --no-cache-dir
```

**Verify installations:**

```bash
# Core dependencies
python -c "import fastapi; print(f'FastAPI: {fastapi.__version__}')"
python -c "import uvicorn; print(f'Uvicorn: {uvicorn.__version__}')"
python -c "import dash; print(f'Dash: {dash.__version__}')"

# Testing dependencies
python -c "import pytest; print(f'pytest: {pytest.__version__}')"
python -c "import black; print(f'Black: {black.__version__}')"

# All should print version numbers, no errors
```

### Dependency Management

**Update dependencies:**

```bash
# Update all packages
pip install --upgrade -r conf/requirements.txt

# Update specific package
pip install --upgrade fastapi

# Freeze current versions
pip freeze > conf/requirements-frozen.txt
```

**Check for outdated packages:**

```bash
pip list --outdated
```

---

## Configuration Files

### Application Configuration (app_config.yaml)

**Location:** `conf/app_config.yaml`

**Structure:**

```yaml
# Server configuration
server:
  host: "0.0.0.0"              # Bind address
  port: 8050                    # Server port
  reload: false                 # Auto-reload on code changes
  workers: 1                    # Number of worker processes

# Demo mode configuration
demo:
  enabled: true                 # Enable demo mode
  update_interval: 1.0          # Update interval (seconds)
  max_epochs: 100               # Maximum epochs to simulate
  dataset_type: "spiral"        # Dataset type (spiral, circles, xor)
  num_samples: 300              # Number of data points

# Logging configuration
logging:
  level: "INFO"                 # Log level (DEBUG, INFO, WARNING, ERROR)
  format: "detailed"            # Log format (simple, detailed, json)
  file_rotation: true           # Enable log rotation
  max_bytes: 10485760          # Max log file size (10MB)
  backup_count: 5               # Number of backup files

# Backend integration
backend:
  path: "../cascor"             # CasCor backend path
  timeout: 30                   # Connection timeout (seconds)
  retry_attempts: 3             # Number of retry attempts
  retry_delay: 5                # Delay between retries (seconds)

# WebSocket configuration
websocket:
  ping_interval: 30             # WebSocket ping interval (seconds)
  ping_timeout: 10              # WebSocket ping timeout (seconds)
  max_message_size: 1048576    # Max message size (1MB)

# Dashboard configuration
dashboard:
  update_interval: 1000         # Update interval (milliseconds)
  max_history_points: 1000      # Max points in history plots
  default_tab: "metrics"        # Default tab on load
```

**Edit configuration:**

```bash
# Open in editor
nano conf/app_config.yaml
# or
vim conf/app_config.yaml
# or
code conf/app_config.yaml  # VS Code
```

### Requirements File (requirements.txt)

**Location:** `conf/requirements.txt`

**Format:**

```txt
# Web framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Dashboard
dash>=2.14.0
plotly>=5.17.0

# ... more dependencies
```

**Pinned versions (production):**

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0.post1
dash==2.14.2
```

### Conda Environment File (conda_environment.yaml)

**Location:** `conf/conda_environment.yaml`

**Structure:**

```yaml
name: JuniperPython
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - pip
  - pip:
    - -r file:requirements.txt
```

---

## Environment Variables

### Standard Variables

**Format:** `CASCOR_<SECTION>_<KEY>`

**Example:** `app_config.yaml` key `server.port` → `CASCOR_SERVER_PORT`

### Core Variables

```bash
# Server configuration
export CASCOR_SERVER_PORT=8050        # Server port
export CASCOR_SERVER_HOST="0.0.0.0"   # Bind address

# Demo mode
export CASCOR_DEMO_MODE=1             # Force demo mode (1=on, 0=off)
export CASCOR_DEMO_UPDATE_INTERVAL=1.0
export CASCOR_DEMO_MAX_EPOCHS=100

# Logging
export CASCOR_DEBUG=1                 # Enable debug logging
export CASCOR_LOGGING_LEVEL="DEBUG"   # Log level

# Backend
export CASCOR_BACKEND_PATH="../cascor"

# Paths
export CASCOR_DATA_DIR="./data"
export CASCOR_LOGS_DIR="./logs"
export CASCOR_REPORTS_DIR="./reports"
```

### Setting Environment Variables

#### Method 1: Export in shell

```bash
export CASCOR_SERVER_PORT=8051
export CASCOR_DEBUG=1
```

#### Method 2: .env file (recommended)

Create `.env` in project root:

```bash
# .env file
CASCOR_SERVER_PORT=8050
CASCOR_DEBUG=1
CASCOR_DEMO_MODE=1
CASCOR_BACKEND_PATH=../cascor
```

Load with:

```bash
# Load .env file
set -a
source .env
set +a

# Or use python-dotenv (automatically loaded by app)
```

#### Method 3: Shell script

```bash
#!/bin/bash
# setup_env.bash

export CASCOR_SERVER_PORT=8050
export CASCOR_DEBUG=0
export CASCOR_DEMO_MODE=1
export CASCOR_BACKEND_PATH=../cascor
```

Source with:

```bash
source setup_env.bash
```

### Environment Variable Expansion

#### Supports

- `${VAR}` - Bash-style expansion
- `$VAR` - Simple expansion

**Example in app_config.yaml:**

```yaml
backend:
  path: "${CASCOR_BACKEND_PATH}"  # Expands to env var value

logging:
  level: "$LOG_LEVEL"             # Expands to env var value
```

### Override Priority

**Precedence (highest to lowest):**

1. Environment variables (`CASCOR_*`)
2. Configuration file (`conf/app_config.yaml`)
3. Default values (in code)

**Example:**

```yaml
# app_config.yaml
server:
  port: 8050  # Default from file
```

```bash
# Environment variable override
export CASCOR_SERVER_PORT=8051  # Overrides file value

# Result: Server runs on port 8051
```

---`

## Path Configuration

### Project Paths

**Standard paths (relative to project root):**

```bash
juniper_canopy/
├── conf/          # Configuration files
├── data/          # Datasets
├── docs/          # Documentation
├── logs/          # Log files
├── reports/       # Coverage/test reports
├── src/           # Source code
└── util/          # Utility scripts
```

### Absolute vs. Relative Paths

**❌ NEVER use hardcoded absolute paths:**

```python
# BAD - hardcoded absolute path
data_dir = "/home/user/juniper_canopy/data"
```

**✅ ALWAYS use pathlib and relative resolution:**

```python
# GOOD - relative path resolution
from pathlib import Path

# Project root (from src/ file)
ROOT = Path(__file__).resolve().parents[1]

# Resolve data directory
data_dir = (ROOT / "data").resolve()
logs_dir = (ROOT / "logs").resolve()
conf_dir = (ROOT / "conf").resolve()
```

### Conda Environment Path

**Environment location:**

```bash
# Check environment path
conda env list | grep JuniperPython

# Output:
# JuniperPython    /opt/miniforge3/envs/JuniperPython
```

**Python interpreter path:**

```bash
# Full path to Python
/opt/miniforge3/envs/JuniperPython/bin/python

# Use in scripts
#!/opt/miniforge3/envs/JuniperPython/bin/python
```

**Or use conda activation:**

```bash
#!/bin/bash
conda activate JuniperPython
python script.py
```

### Backend Integration Path

**Default:** `../cascor` (relative to juniper_canopy)

**Override with environment variable:**

```bash
export CASCOR_BACKEND_PATH=/absolute/path/to/cascor
```

**Or in app_config.yaml:**

```yaml
backend:
  path: "/absolute/path/to/cascor"
```

---

## Verification Steps

### Step 1: Verify Conda Environment

```bash
# Activate environment
conda activate JuniperPython

# Check activation
echo $CONDA_DEFAULT_ENV
# Expected: JuniperPython

# Check Python version
python --version
# Expected: Python 3.11.x or 3.12.x

# Check Python path
which python
# Expected: /opt/miniforge3/envs/JuniperPython/bin/python
```

### Step 2: Verify Dependencies

```bash
# Check all dependencies installed
pip check

# Expected: "No broken requirements found."

# List installed packages
pip list | grep -E "(fastapi|dash|pytest)"

# Should show:
# fastapi      0.104.x
# dash         2.14.x
# pytest       7.4.x
```

### Step 3: Verify Configuration

```bash
# Check config file exists
ls -l conf/app_config.yaml

# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('conf/app_config.yaml'))"

# No output = valid YAML
```

### Step 4: Verify Environment Variables

```bash
# Check environment variables
env | grep CASCOR

# Should show your configured variables
```

### Step 5: Verify Paths

```bash
# Check directory structure
ls -la
# Should see: conf/, docs/, src/, logs/, data/, etc.

# Check logs directory
ls -la logs/
# Should exist (created on first run if missing)

# Check data directory
ls -la data/
# Should exist
```

### Step 6: Verify Application Startup

```bash
# Start demo mode
./demo

# Check for errors in output
# Should see: "Uvicorn running on http://0.0.0.0:8050"

# In another terminal, test API
curl http://localhost:8050/health

# Expected: {"status":"healthy"}
```

### Step 7: Verify Tests

```bash
# Run test suite
cd src
pytest tests/ -v

# All tests should pass
# Expected: "XXX passed in Y.YYs"
```

**✅ If all verification steps pass:** Environment setup complete!

---

## Troubleshooting

### Issue: Conda Command Not Found

**Symptoms:**

```bash
bash: conda: command not found
```

**Solutions:**

```bash
# Add conda to PATH
export PATH="/opt/miniforge3/bin:$PATH"

# Or reinitialize shell
source ~/.bashrc  # Linux
source ~/.zshrc   # macOS

# Or reinstall Miniforge3
```

---

### Issue: Python Version Mismatch

**Symptoms:**

```bash
Python 3.9.x found, but 3.11+ required
```

**Solutions:**

```bash
# Recreate environment with correct Python
conda deactivate
conda remove -n JuniperPython --all -y
conda create -n JuniperPython python=3.11 -y
conda activate JuniperPython
pip install -r conf/requirements.txt
```

---

### Issue: Dependency Installation Fails

**Symptoms:**

```bash
ERROR: Could not find a version that satisfies the requirement...
```

**Solutions:**

```bash
# Update pip
pip install --upgrade pip setuptools wheel

# Clear pip cache
pip cache purge

# Reinstall dependencies
pip install -r conf/requirements.txt --no-cache-dir

# If specific package fails, install separately
pip install problematic-package --verbose
```

---

### Issue: Import Errors

**Symptoms:**

```bash
ModuleNotFoundError: No module named 'fastapi'
```

**Solutions:**

```bash
# Verify conda environment activated
conda activate JuniperPython

# Verify package installed
pip list | grep fastapi

# Reinstall if missing
pip install fastapi

# Check Python path
which python
# Should be: /opt/miniforge3/envs/JuniperPython/bin/python
```

---

### Issue: Configuration Not Loading

**Symptoms:**

- App ignores app_config.yaml
- Environment variables not recognized

**Solutions:**

```bash
# Verify config file exists
ls -l conf/app_config.yaml

# Validate YAML syntax
python -c "import yaml; print(yaml.safe_load(open('conf/app_config.yaml')))"

# Check environment variables
env | grep CASCOR

# Export variables correctly
export CASCOR_SERVER_PORT=8051  # Not: export CASCOR_SERVER_PORT 8051
```

---

### Issue: Path Resolution Errors

**Symptoms:**

```bash
FileNotFoundError: [Errno 2] No such file or directory: '/home/user/data'
```

**Solutions:**

```bash
# Verify working directory
pwd
# Should be: /path/to/juniper_canopy

# Create missing directories
mkdir -p data logs reports

# Check relative paths in code
# Use pathlib: ROOT / "data" instead of hardcoded paths
```

---

### Issue: Port Already in Use

**Symptoms:**

```bash
OSError: [Errno 48] Address already in use
```

**Solutions:**

```bash
# Find process using port
lsof -i :8050

# Kill process
kill -9 <PID>

# Or use different port
export CASCOR_SERVER_PORT=8051
./demo
```

---

## Advanced Configuration

### Multi-Environment Setup

**Development environment:**

```yaml
# conf/app_config.dev.yaml
server:
  reload: true
  workers: 1

logging:
  level: "DEBUG"

demo:
  enabled: true
```

**Production environment:**

```yaml
# conf/app_config.prod.yaml
server:
  reload: false
  workers: 4

logging:
  level: "WARNING"

demo:
  enabled: false
```

**Load specific config:**

```bash
export CASCOR_CONFIG_FILE=conf/app_config.prod.yaml
./try
```

---

### Custom Logging Configuration

**Create custom logging config:**

```yaml
# conf/logging_config.yaml
version: 1
disable_existing_loggers: false

formatters:
  detailed:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  simple:
    format: '%(levelname)s - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: DEBUG
    formatter: simple
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: detailed
    filename: logs/system.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

root:
  level: INFO
  handlers: [console, file]
```

---

### Docker Environment

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies
COPY conf/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY conf/ ./conf/

# Create directories
RUN mkdir -p logs data reports

# Set environment variables
ENV CASCOR_DEMO_MODE=1
ENV CASCOR_SERVER_HOST=0.0.0.0
ENV CASCOR_SERVER_PORT=8050

# Expose port
EXPOSE 8050

# Run application
CMD ["python", "src/main.py"]
```

**Build and run:**

```bash
docker build -t juniper_canopy .
docker run -p 8050:8050 juniper_canopy
```

---

### Pre-commit Configuration

**Install pre-commit hooks:**

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

**Configuration:** `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.10.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]

  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: ["--max-line-length=120"]
```

**See:** [CI/CD Quick Start](ci_cd/CICD_QUICK_START.md) for details.

---

## Environment Maintenance

### Update Environment

```bash
# Update conda
conda update conda

# Update environment
conda env update -f conf/conda_environment.yaml

# Update pip packages
pip install --upgrade -r conf/requirements.txt
```

### Recreate Environment

```bash
# Remove existing environment
conda deactivate
conda remove -n JuniperPython --all -y

# Recreate from scratch
conda env create -f conf/conda_environment.yaml
conda activate JuniperPython

# Verify
pytest tests/ -v
```

### Export Environment

```bash
# Export conda environment
conda env export > environment-export.yaml

# Export pip requirements
pip freeze > requirements-frozen.txt
```

---

## Checklist: Environment Setup Complete

**Verify these items are complete:**

- [ ] Conda/Mamba installed
- [ ] JuniperPython environment created
- [ ] Python 3.11+ installed in environment
- [ ] All dependencies installed (`pip check` passes)
- [ ] Configuration files present (app_config.yaml, requirements.txt)
- [ ] Environment variables set (optional but recommended)
- [ ] Paths configured (data/, logs/, reports/ directories exist)
- [ ] Application starts without errors (`./demo` works)
- [ ] API endpoints respond (`curl http://localhost:8050/health`)
- [ ] Tests pass (`cd src && pytest tests/ -v`)
- [ ] Pre-commit hooks installed (optional)

**✅ All items checked:** Environment setup complete!

---

## Next Steps

- **[QUICK_START.md](QUICK_START.md)** - Run the application
- **[AGENTS.md](../AGENTS.md)** - Development guide
- **[CI/CD Quick Start](ci_cd/CICD_QUICK_START.md)** - Testing and CI/CD
- **[CI/CD Manual](ci_cd/CICD_MANUAL.md)** - Complete CI/CD guide

---

**Last Updated:** January 29, 2026  
**Version:** 0.25.0  
**Maintainer:** Paul Calnon
