# Quick Start Guide

## Get Juniper Canopy running in 5 minutes

**Version:** 0.25.4
**Status:** ✅ Production Ready
**Last Updated:** October 8, 2026
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
# Activate the live JuniperCanopy environment
conda activate JuniperCanopy1
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
2. Sets `JUNIPER_CANOPY_DEMO_MODE=1` environment variable
3. Starts FastAPI + Dash server
4. Demo mode generates simulated training data

#### Expected output

```bash
Starting Juniper Canopy in demo mode...
Activating conda environment: JuniperCanopy1
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8050 (Press CTRL+C to quit)
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
# Set CasCor backend path (default: ../juniper-cascor)
export JUNIPER_CANOPY_BACKEND_PATH=/path/to/juniper-cascor

# Or use default (../cascor)
# No export needed if using default
```

### Step 2: Disable Demo Mode

```bash
# Ensure demo mode is NOT forced
unset JUNIPER_CANOPY_DEMO_MODE

# Or explicitly set to 0
export JUNIPER_CANOPY_DEMO_MODE=0
```

### Step 3: Launch Production Mode

#### Option A: Using try script (recommended)

```bash
./try
```

#### Option B: Manual launch

```bash
cd src
/opt/miniforge3/envs/JuniperCanopy1/bin/python main.py
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
JUNIPER_CANOPY_SERVER__HOST=127.0.0.1
JUNIPER_CANOPY_SERVER__PORT=8050

# Demo mode (0=production, 1=demo)
JUNIPER_CANOPY_DEMO_MODE=1

# Debug logging (0=off, 1=on)
JUNIPER_CANOPY_LOG_LEVEL=INFO

# Backend path (default: ../juniper-cascor)
JUNIPER_CANOPY_BACKEND_PATH=../juniper-cascor

# Update interval (seconds)
JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL=1.0
```

#### Load environment variables

```bash
# Linux/macOS
source .env

# Or use export manually
export JUNIPER_CANOPY_SERVER__PORT=8050
export JUNIPER_CANOPY_DEMO_MODE=1
```

### Configuration File

#### Edit `conf/app_config.yaml`

```yaml
server:
  host: "127.0.0.1"
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
conda activate JuniperCanopy1

# Or use explicit Python path
/opt/miniforge3/envs/JuniperCanopy1/bin/python src/main.py
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
export JUNIPER_CANOPY_SERVER__PORT=8051
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
export JUNIPER_CANOPY_DEMO_MODE=1
./demo
```

---

### Issue 4: Startup Refuses `0.0.0.0`

**Error:**

```bash
NonLoopbackBindError: REFUSING TO START: canopy is configured to bind a non-loopback interface
```

**Cause:** Canopy now fail-closes when `JUNIPER_CANOPY_SERVER__HOST` is non-loopback
unless a perimeter attestation is set (`JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED` or
`JUNIPER_CANOPY_AUTH_PROXY_ATTESTED`).

**Solution:**

```bash
# Local development and demo mode
export JUNIPER_CANOPY_SERVER__HOST=127.0.0.1
./demo

# Containerized behind a loopback-only host publish (the deploy default)
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
export JUNIPER_CANOPY_LOOPBACK_PUBLISH_ATTESTED=true

# Or behind a fronting authenticating reverse proxy (Phase 4)
export JUNIPER_CANOPY_SERVER__HOST=0.0.0.0
export JUNIPER_CANOPY_AUTH_PROXY_ATTESTED=true
```

---

### Issue 5: WebSocket Connection Failed

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

### Issue 6: Import Errors in Tests

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

### Issue 7: Conda Environment Not Found

**Error:**

```bash
CondaEnvironmentError: environment 'JuniperCanopy1' not found
```

**Solution:**

```bash
# Create conda environment
conda env create -f conf/conda_environment.yaml

# Or manually
conda create -n JuniperCanopy1 python=3.12
conda activate JuniperCanopy1
pip install -r conf/requirements.txt
```

**See:** [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for complete setup.

---

### Issue 8: Dashboard Frozen / `/v1/health/live` Hangs When CasCor Is Down

**Symptom:** Canopy stops answering HTTP — health probes included — whenever cascor is
stopped or hung. Pre-fix measurements: 3.0 s with cascor stopped, **123.12 s** with
cascor hung.

**Cause:** Synchronous `requests` I/O inside `async def` on a single-worker uvicorn (X7).

**Check:**

```bash
# Liveness must stay fast even when cascor is unreachable
curl -s -o /dev/null -w "%{http_code} %{time_total}\n" http://127.0.0.1:8050/v1/health/live

# Client budget (slice 1b, on main)
cd src && pytest tests/regression/test_x7_client_budget.py -v
```

**See:** [AGENTS_REFERENCE.md — Event-loop I/O discipline](AGENTS_REFERENCE.md#event-loop-io-discipline-x7)

---

### Issue 8: Modebar Camera Does Nothing

**Symptom:** The Topology camera button is present. Clicking it never offers a PNG. The browser console reports a Content-Security-Policy `img-src` violation for a `blob:` URL.

**Cause:** Plotly's PNG export loads the figure through a `blob:` URL. The shipped CSP is `img-src 'self' data: blob:` (`SecurityConstants.DEFAULT_CSP_POLICY`). Without `blob:`, the promise rejects with `[object Event]` and no file is offered. SVG export from the same menu still works.

**Solution:** Do not replace `data:` with `blob:` (Bootstrap icons need `data:`). Do not add `blob:` to `script-src`. Confirm both pins still hold:

cd src
pytest tests/regression/test_csp_plotly_image_export.py \
       tests/regression/test_csp_bootstrap_cdn.py -v

**See:** [AGENTS_REFERENCE.md § Plotly PNG Export](AGENTS_REFERENCE.md#plotly-png-export-f-canopy-047)

### Issue 9: Status Bar Says "Stopped" While CasCor Is Down

**Symptom:** Service-mode dashboard shows **Stopped** (or a healthy idle) when cascor is
unreachable, hung, or returning a 200 that is not a cascor status. An operator cannot
tell that from a backend that is genuinely idle.

**Cause:** `/api/status` handed the UI a raw payload. A half-dead 200 has no `error`
key, so the PR `#340` branch never fires (X7 slice 1c). The cache must publish
`status_class`; the status bar must render the class (`Unreachable` / `Unknown`).

```bash
curl -s http://127.0.0.1:8050/api/status | python -m json.tool
# Expect status_class + stale + age_seconds in service mode (landed with #578)

cd src && pytest tests/regression/test_x7_status_cache.py -v
```

**See:** [AGENTS_REFERENCE.md — Cascor status cache](AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c)

---

### Issue 10: Replay Range Skips the Last Frame, or a Control Re-fires

**Symptom:** A time range on the Replay tab never plays its last epoch. The scrubber's last position does nothing. After a control, or after the session simply repaints, the same action is sent again.

**Cause:** The build predates canopy#697. Cascor's range end is exclusive (`[start, end)`) and `snapshot_window.end_epoch` is the history length. The sliders are inclusive. `render_session` writes the scrubber, speed, and range, and those values are Inputs of `queue_control`. Since canopy#697 the player shows `end - 1`, sends `hi + 1`, stops the scrubber at `end_epoch - 1`, and returns `dash.no_update` when the painted value already matches the session.

**Check:**

```bash
cd src && pytest tests/unit/frontend/test_replay_range_end_and_echo.py -v
```

**See:** [AGENTS_REFERENCE.md § Replay index contract](AGENTS_REFERENCE.md#replay-index-contract)

---

### Issue 11: Recurrence Fit Shows a Status Code and No Reason

**Symptom:** A Recurrence (LMU) fit fails. The status bar reads `Failed — recurrence service error <code> on POST /v1/train`, with nothing after the path.

**Cause:** The service answered with a 5xx, or with a 4xx whose body had no usable `detail`. A 5xx `detail` is never appended, because that text can quote the recurrence service's own upstream header value. A 4xx `detail` is appended after the path, as in `recurrence service error 422 on POST /v1/train: invalid dataset: X_train has non-finite values (NaN/Inf)`. canopy 0.8.1 and earlier append no `detail` at all, and their status bar shows a bare `Failed`.

**Check:**

```bash
curl -s http://127.0.0.1:8050/api/status | python -m json.tool
```

`completion_reason` holds the whole message. A 4xx `detail` is flattened and cut at 300 characters. A validation list becomes `loc -> msg` pairs and omits each item's `input`. When the status-bar label cuts a long reason at 120 characters, hover the bar: the tooltip holds the rest, up to 480 characters. For a 5xx, read the recurrence service's own log.

The regression card is titled `Recurrence (LMU) — in-sample (train split) regression metrics`, with the caption `Computed on the training split the fit saw; not a held-out score.` Its numbers are the training split `POST /v1/train` scored.

**See:** [AGENTS_REFERENCE.md § Recurrence fit refusal and in-sample scores](AGENTS_REFERENCE.md#recurrence-fit-refusal-and-in-sample-scores)

---

### Issue 12: Recurrence Fit Names the Key, or Says Retry After

**Symptom:** A recurrence fit fails and the status bar names `JUNIPER_CANOPY_RECURRENCE_API_KEY` and `JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE`, or it says `retry after 30 s`. The visible line cuts at 120 characters and ends in `…`. canopy 0.8.1 and earlier word the key refusal as `check recurrence_api_key`.

**Cause:** 401 / 403 means the outbound `X-API-Key` is missing or wrong. 429 means the recurrence service rate-limited the call and sent `Retry-After`. The dashboard polls canopy, so a 429 usually means another client shares that key or address.

**Check:**

```bash
# Prefixed pair wins. The shared JUNIPER_RECURRENCE_API_KEY pair applies when this pair is unset.
# The _FILE form is read before the direct variable. Restart canopy after changing either.
export JUNIPER_CANOPY_RECURRENCE_API_KEY_FILE=/run/secrets/recurrence_api_key
```

Hover the status text for the rest of the reason (up to 480 characters). A restored snapshot counts as a model (`model_present`); it does not mean the fit you just started succeeded. The recurrence model version is read from the service, and no screen shows it yet.

**See:** [AGENTS_REFERENCE.md § Recurrence key, restored model, and service version](AGENTS_REFERENCE.md#recurrence-key-restored-model-and-service-version)

---

### Issue 13: Start Refuses a Wider Dataset

**Symptom:** Start fails. The alert says the staged dataset is wider than the current network. The charts still show the previous run, and the pending-dataset banner is still up.

**Cause:** A plain Start continues the current network. It cannot add features or outputs. Cascor refuses before loading anything and opens the message with `[start_fresh_required]` (juniper-cascor#687; canopy#681 recognises it). `equities` (15 features) and `mnist` (784 features) are the cases the unit test drives.

**What to do:** Click **Stop & Restart with new dataset**. Turn **Start fresh** on. Confirm. That rebuilds an untrained network from the staged dataset. Applied parameters (including edits in the modal) and on-disk snapshots are kept; the current model and its retained metrics and history are discarded. The toggle defaults to off, which would continue the network that is too narrow. Edits in the modal are applied before the restart. The alert stays up until you dismiss it or a later command succeeds.

A cascor that does not send the marker will not show this alert. It used to consume the staged dataset before refusing, so the banner this alert names is already gone. Do not invent a second wording for that case.

```bash
cd src && pytest tests/unit/frontend/test_start_fresh_refusal_and_modal_text.py -v
```

**See:** [AGENTS_REFERENCE.md § Start-fresh refusal](AGENTS_REFERENCE.md#start-fresh-refusal-f1-f2)

---

### Issue 14: Sidebar Says "backend status unknown"

**Symptom:** Under **Model:** the sidebar reads `Selected: CasCor (Cascade-Correlation) · backend status unknown` at first paint, or it stays there after the page loads.

**Cause:** **Active** is only used after a round-trip includes a `backend` that serves the selection. The layout seed has no `backend`. The same sentence is written when `GET /api/selection` fails (connection error, non-OK status, or a 200 with no `nn_model`). It is not the **NOT ACTIVE** sentence, which names the backend that is running and disables Start. Unknown does not disable Start by itself. A missing dataset still does.

**Check:** Reload. A healthy body includes `backend` (`service`, `demo`, or `recurrence`) and the line becomes **Active** or **NOT ACTIVE**. A stuck unknown line means the mount read failed. The log says `Selection hydration read failed`.

```bash
curl -s http://127.0.0.1:8050/api/selection | python -m json.tool

cd src && pytest tests/regression/test_selection_reachability_guardrails.py -k X11 -v
```

**See:** [AGENTS_REFERENCE.md § Sidebar model summary](AGENTS_REFERENCE.md#sidebar-model-summary-x11)

## Next Steps

### Learn More

- **[README.md](../README.md)** - Complete project overview and features
- **[ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md)** - Detailed environment configuration
- **[AGENTS.md](../AGENTS.md)** - Development guide and conventions
- **[Event-loop I/O discipline (X7)](AGENTS_REFERENCE.md#event-loop-io-discipline-x7)** - Keep `/v1/health/live` answerable when cascor is down
- **[Cascor status cache (X7 slice 1c)](AGENTS_REFERENCE.md#cascor-status-cache-x7-slice-1c)** - Why `/api/status` publishes a class, not a raw payload
- **[Replay index contract](AGENTS_REFERENCE.md#replay-index-contract)** - Exclusive range end, window length, and why a replay paint must not queue a control
- **[Recurrence fit refusal and in-sample scores](AGENTS_REFERENCE.md#recurrence-fit-refusal-and-in-sample-scores)** - Where a 4xx `detail` goes, and why the regression card is a training-split score
- **[Recurrence key, restored model, and service version](AGENTS_REFERENCE.md#recurrence-key-restored-model-and-service-version)** - What a 401, a 429, a restored snapshot, and a blank model version mean
- **[Start-fresh refusal (F1, F2)](AGENTS_REFERENCE.md#start-fresh-refusal-f1-f2)** - What to do when Start says the staged dataset is wider than the network
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
2. Set `JUNIPER_CANOPY_BACKEND_PATH`
3. Disable demo mode: `unset JUNIPER_CANOPY_DEMO_MODE`
4. Run: `./try`

**See production mode setup above.**

---

## Performance Tips

### Faster Dashboard Updates

```bash
# Reduce update interval (default: 1.0s)
export JUNIPER_CANOPY_DEMO_UPDATE_INTERVAL=0.5
./demo
```

### Reduce Log Verbosity

```bash
# Set logging level to WARNING
export JUNIPER_CANOPY_LOG_LEVEL=WARNING
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

- [ ] Conda environment activated? (`conda activate JuniperCanopy1`)
- [ ] Python version 3.11+? (`python --version`)
- [ ] Dependencies installed? (`pip install -r conf/requirements.txt`)
- [ ] Port 8050 available? (`lsof -i :8050`)
- [ ] Demo mode enabled? (`export JUNIPER_CANOPY_DEMO_MODE=1`)
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

**Last Updated:** October 8, 2026  
**Version:** 0.25.4  
**Status:** ✅ Production Ready

**Last Updated:** 2026-10-08
