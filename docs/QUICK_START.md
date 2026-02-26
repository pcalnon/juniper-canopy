# Quick Start Guide

## Get Juniper Canopy running in 5 minutes

**Version:** 0.25.0  
**Status:** ✅ Production Ready  
**Last Updated:** January 29, 2026  
**Project:** Juniper - Cascade Correlation Neural Network Monitoring  

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Demo Mode)](#quick-start-demo-mode)
- [Verify Installation](#verify-installation)
- [Production Mode Setup](#production-mode-setup)
- [First-Time Configuration](#first-time-configuration)
- [Common Issues](#common-issues)
- [Next Steps](#next-steps)

---

## Prerequisites

**Before you begin, ensure you have:**

- [ ] **Python 3.11 or higher** installed
- [ ] **Conda/Mamba** (Miniforge3 or Miniconda)
- [ ] **Git** for cloning the repository
- [ ] **Terminal/Shell** access
- [ ] **5 minutes** of your time

**Check your versions:**

```bash
# Python version
python --version  # Should be 3.11+

# Conda version
conda --version

# Git version
git --version
```

**Don't have these?** See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for installation instructions.

---

## Quick Start (Demo Mode)

**Demo mode runs without the CasCor backend, simulating training data for development and testing.**

### Step 1: Clone Repository

```bash
# Navigate to your workspace
cd ~/Development/python/Juniper/juniper-canopy

# Repository should already be cloned
# If not, clone from your repository
```

### Step 2: Navigate to Project

```bash
cd juniper_canopy
```

### Step 3: Activate Environment

#### Option A: Using conda (recommended)

```bash
# Activate JuniperPython environment
conda activate JuniperPython
```

#### Option B: Let the demo script handle it

The `./demo` script automatically activates the conda environment.

### Step 4: Run Demo Mode

```bash
# Launch demo mode
./demo
```

#### What happens

1. Script activates conda environment
2. Sets `CASCOR_DEMO_MODE=1` environment variable
3. Starts FastAPI + Dash server
4. Demo mode generates simulated training data

#### Expected output

```bash
Starting Juniper Canopy in demo mode...
Activating conda environment: JuniperPython
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8050 (Press CTRL+C to quit)
Dash is running on http://127.0.0.1:8050/

 * Serving Flask app 'demo_mode'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment.
```

### Step 5: Open Dashboard

#### In your browser, navigate to

```bash
http://localhost:8050/dashboard/
```

**You should see:**

- ✅ **Training Metrics** tab with live loss/accuracy plots
- ✅ **Network Topology** tab with network visualization
- ✅ **Decision Boundary** tab with boundary plot
- ✅ **Dataset** tab with data points

**Congratulations! 🎉 You're running Juniper Canopy!**

---

## Verify Installation

### Check API Endpoints

**Open a new terminal and test the API:**

```bash
# Health check
curl http://localhost:8050/health

# Expected: {"status": "healthy"}

# Get current metrics
curl http://localhost:8050/api/metrics

# Expected: JSON with epoch, loss, accuracy, etc.

# Get network topology
curl http://localhost:8050/api/topology

# Expected: JSON with network structure
```

### Check WebSocket Connection

**In browser console (F12 → Console tab):**

```javascript
// Connect to training WebSocket
const ws = new WebSocket('ws://localhost:8050/ws/training');

ws.onopen = () => console.log('Connected!');
ws.onmessage = (event) => console.log('Received:', JSON.parse(event.data));

// You should see real-time metric updates
```

### Check Logs

```bash
# View system logs
tail -f logs/system.log

# View training logs
tail -f logs/training.log

# View UI logs
tail -f logs/ui.log
```

**If everything works:** ✅ Installation verified!

**If something fails:** See [Common Issues](#common-issues) below.

---

## Production Mode Setup

**Production mode connects to the real CasCor backend for actual neural network training.**

### Prerequisites, Production Mode

- [ ] CasCor backend installed at `../cascor/` (or custom path)
- [ ] CasCor backend tested and working
- [ ] Environment variables configured

### Step 1: Set Backend Path

```bash
# Set CasCor backend path (default: ../cascor)
export CASCOR_BACKEND_PATH=/path/to/cascor

# Or use default (../cascor)
# No export needed if using default
```

### Step 2: Disable Demo Mode

```bash
# Ensure demo mode is NOT forced
unset CASCOR_DEMO_MODE

# Or explicitly set to 0
export CASCOR_DEMO_MODE=0
```

### Step 3: Launch Production Mode

#### Option A: Using try script (recommended)

```bash
./try
```

#### Option B: Manual launch

```bash
cd src
/opt/miniforge3/envs/JuniperPython/bin/python main.py
```

### Step 4: Verify Backend Connection

#### Check logs for backend integration

```bash
tail -f logs/system.log | grep -i "cascor"
```

#### Expected

```bash
INFO: CasCor backend found at: /path/to/cascor
INFO: CasCor integration initialized successfully
INFO: Connected to CasCor backend
```

#### If backend not found

```bash
WARNING: CasCor backend not found, falling back to demo mode
```

---

## First-Time Configuration

### Environment Variables

#### Create `.env` file in project root

```bash
# Server configuration
CASCOR_SERVER_PORT=8050
CASCOR_SERVER_HOST=0.0.0.0

# Demo mode (0=production, 1=demo)
CASCOR_DEMO_MODE=1

# Debug logging (0=off, 1=on)
CASCOR_DEBUG=0

# Backend path (default: ../cascor)
CASCOR_BACKEND_PATH=../cascor

# Update interval (seconds)
CASCOR_DEMO_UPDATE_INTERVAL=1.0
CASCOR_DEMO_MAX_EPOCHS=100
```

#### Load environment variables

```bash
# Linux/macOS
source .env

# Or use export manually
export CASCOR_SERVER_PORT=8050
export CASCOR_DEMO_MODE=1
```

### Configuration File

#### Edit `conf/app_config.yaml`

```yaml
server:
  host: "0.0.0.0"
  port: 8050
  reload: false

demo:
  enabled: true
  update_interval: 1.0
  max_epochs: 100

logging:
  level: "INFO"
  format: "detailed"

backend:
  path: "../cascor"
  timeout: 30
```

#### Environment variables override config file values

**See:** [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for complete configuration guide.

---

## Common Issues

### Issue 1: ModuleNotFoundError

#### Error

```bash
ModuleNotFoundError: No module named 'uvicorn'
```

**Cause:** Not using conda environment's Python

**Solution:**

```bash
# Activate conda environment
conda activate JuniperPython

# Or use explicit Python path
/opt/miniforge3/envs/JuniperPython/bin/python src/main.py
```

---

### Issue 2: Port Already in Use

**Error:**

```bash
OSError: [Errno 48] Address already in use
```

**Cause:** Port 8050 already occupied

**Solution:**

```bash
# Check what's using port 8050
lsof -i :8050

# Kill the process
kill -9 <PID>

# Or use different port
export CASCOR_SERVER_PORT=8051
./demo
```

---

### Issue 3: Dashboard Shows "No Data Available"

**Symptoms:** Dashboard loads but all tabs show "No data available"

**Causes:**

1. Demo mode not activated
2. API endpoints not responding
3. CORS issues

**Solutions:**

```bash
# 1. Verify demo mode is running
curl http://localhost:8050/api/metrics

# Should return JSON, not 404

# 2. Check logs
tail -f logs/system.log

# Look for errors or warnings

# 3. Restart with explicit demo mode
export CASCOR_DEMO_MODE=1
./demo
```

---

### Issue 4: WebSocket Connection Failed

**Error in browser console:**

```bash
WebSocket connection to 'ws://localhost:8050/ws/training' failed
```

**Solutions:**

```bash
# 1. Verify server is running
curl http://localhost:8050/health

# 2. Check WebSocket endpoint
wscat -c ws://localhost:8050/ws/training
# Install wscat: npm install -g wscat

# 3. Check firewall/CORS settings
# Ensure localhost connections allowed
```

---

### Issue 5: Import Errors in Tests

**Error:**

```bash
ImportError: cannot import name 'get_system_logger' from 'logger'
```

**Cause:** Running tests from wrong directory

**Solution:**

```bash
# CORRECT: Run from src/ directory
cd src
pytest tests/ -v

# WRONG: Running from project root
pytest src/tests/ -v  # This will fail
```

---

### Issue 6: Conda Environment Not Found

**Error:**

```bash
CondaEnvironmentError: environment 'JuniperPython' not found
```

**Solution:**

```bash
# Create conda environment
conda env create -f conf/conda_environment.yaml

# Or manually
conda create -n JuniperPython python=3.11
conda activate JuniperPython
pip install -r conf/requirements.txt
```

**See:** [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for complete setup.

---

## Next Steps

### Learn More

- **[README.md](../README.md)** - Complete project overview and features
- **[ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)** - Detailed environment configuration
- **[AGENTS.md](../AGENTS.md)** - Development guide and conventions
- **[CI/CD Guide](ci_cd/CICD_QUICK_START.md)** - Testing and CI/CD workflows

### Start Developing

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run tests
cd src
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=. --cov-report=html

# View coverage
open reports/coverage/index.html  # macOS
xdg-open reports/coverage/index.html  # Linux
```

### Explore the Dashboard

1. **Training Metrics Tab**
   - Watch loss and accuracy update in real-time
   - Observe convergence behavior

2. **Network Topology Tab**
   - See hidden units added dynamically
   - Explore connection weights

3. **Decision Boundary Tab**
   - Visualize learned decision boundaries
   - See class separation

4. **Dataset Tab**
   - View training data distribution
   - Understand data characteristics

### Customize Demo Mode

**Edit `src/demo_mode.py` to:**

- Change dataset (spiral, circles, XOR, etc.)
- Adjust update interval
- Modify max epochs
- Customize metric generation

**Example:**

```python
# In demo_mode.py
def __init__(self):
    # ...
    self.update_interval = 0.5  # Faster updates
    self.max_epochs = 200       # More epochs
    # ...
```

### Connect to Real CasCor Backend

**When ready for production:**

1. Install CasCor backend
2. Set `CASCOR_BACKEND_PATH`
3. Disable demo mode: `unset CASCOR_DEMO_MODE`
4. Run: `./try`

**See production mode setup above.**

---

## Performance Tips

### Faster Dashboard Updates

```bash
# Reduce update interval (default: 1.0s)
export CASCOR_DEMO_UPDATE_INTERVAL=0.5
./demo
```

### Reduce Log Verbosity

```bash
# Set logging level to WARNING
export CASCOR_LOGGING_LEVEL=WARNING
./demo
```

### Optimize for Production

```yaml
# In conf/app_config.yaml
server:
  reload: false  # Disable auto-reload
  workers: 4     # Multiple workers

logging:
  level: "WARNING"  # Reduce log volume
```

---

## Command Reference

### Essential Commands

```bash
# Run demo mode
./demo

# Run production mode
./try

# Run tests
cd src && pytest tests/ -v

# Run tests with coverage
cd src && pytest tests/ --cov=.

# Pre-commit checks
pre-commit run --all-files

# Check syntax
python -m py_compile src/**/*.py

# Format code
black src/ && isort src/
```

### API Endpoints

```bash
# Health check
curl http://localhost:8050/health

# Current metrics
curl http://localhost:8050/api/metrics

# Metrics history
curl http://localhost:8050/api/metrics/history

# Network topology
curl http://localhost:8050/api/network/topology

# Decision boundary
curl http://localhost:8050/api/decision_boundary

# Dataset
curl http://localhost:8050/api/dataset
```

### WebSocket Channels

```javascript
// Training metrics stream
ws://localhost:8050/ws/training

// Control commands
ws://localhost:8050/ws/control
```

---

## Troubleshooting Checklist

**If something doesn't work:**

- [ ] Conda environment activated? (`conda activate JuniperPython`)
- [ ] Python version 3.11+? (`python --version`)
- [ ] Dependencies installed? (`pip install -r conf/requirements.txt`)
- [ ] Port 8050 available? (`lsof -i :8050`)
- [ ] Demo mode enabled? (`export CASCOR_DEMO_MODE=1`)
- [ ] Running from correct directory? (`pwd` should end with juniper_canopy)
- [ ] Logs showing errors? (`tail -f logs/system.log`)

**Still stuck?** See [AGENTS.md](../AGENTS.md) Common Issues section.

---

## Getting Help

### Documentation

- **[DOCUMENTATION_OVERVIEW.md](DOCUMENTATION_OVERVIEW.md)** - Complete doc navigation
- **[AGENTS.md](../AGENTS.md)** - Development guide with troubleshooting
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and known issues

### Check Logs for Issues

```bash
# System log (startup, configuration)
tail -f logs/system.log

# Training log (metrics, demo mode)
tail -f logs/training.log

# UI log (dashboard events)
tail -f logs/ui.log

# All logs
tail -f logs/*.log
```

### Verify Configuration

```bash
# Check environment variables
env | grep CASCOR

# Check config file
cat conf/app_config.yaml

# Check conda environment
conda list | grep -E "(fastapi|dash|uvicorn)"
```

---

## Success Criteria

### You've successfully completed quick start when

- ✅ Demo mode launches without errors
- ✅ Dashboard accessible at <http://localhost:8050/dashboard/>
- ✅ All 4 tabs display data (not "No data available")
- ✅ Training metrics update in real-time
- ✅ API endpoints respond correctly
- ✅ Logs show no errors

### Congratulations! You're ready to use Juniper Canopy! 🎉

---

## What's Next?

### For Developers

1. Read [AGENTS.md](../AGENTS.md) development guide
2. Set up [pre-commit hooks](ci_cd/CICD_QUICK_START.md)
3. Run [test suite](ci_cd/CICD_QUICK_START.md)
4. Review [code style guidelines](../AGENTS.md#code-style-guidelines)

### For Users

1. Explore all dashboard tabs
2. Experiment with demo mode parameters
3. Try connecting to real CasCor backend
4. Review [feature documentation](../README.md#active-research-components)

### For Contributors

1. Read [contributing guidelines](../AGENTS.md#contributing)
2. Review [definition of done](../AGENTS.md#definition-of-done)
3. Check [development roadmap](../notes/) for open tasks
4. Set up [CI/CD locally](ci_cd/CICD_QUICK_START.md)

---

**Last Updated:** January 29, 2026  
**Version:** 0.25.0  
**Status:** ✅ Production Ready

```markdown
**Happy coding! 🚀**
```
