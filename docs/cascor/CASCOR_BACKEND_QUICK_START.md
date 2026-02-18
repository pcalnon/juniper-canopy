# CasCor Backend Integration Quick Start

## Connect to real CasCor backend in 5 minutes

**Version:** 0.25.0  
**Status:** ✅ ASYNC TRAINING READY  
**Last Updated:** January 29, 2026

---

## Overview

**CasCor backend integration provides:**

- ✅ Dynamic import of CasCor backend modules
- ✅ Network instantiation and configuration
- ✅ Method wrapping for monitoring hooks
- ✅ Real-time metrics extraction
- ✅ Network topology visualization
- ✅ Automatic fallback to Demo Mode if backend unavailable
- ✅ Async training support (non-blocking fit)
- ✅ Background training start capability
- ✅ Training status and stop request support
- ✅ Remote worker integration for distributed training

**Current Status:** Async training ready in `src/backend/cascor_integration.py`

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Setup](#quick-setup)
- [Configuration](#configuration)
- [Verification](#verification)
- [Common Issues](#common-issues)
- [Next Steps](#next-steps)

---

## Prerequisites

**Before connecting to CasCor backend:**

- [ ] **CasCor backend** installed at `../cascor` (or custom path)
- [ ] **Juniper Canopy** running successfully in demo mode
- [ ] **Python 3.11+** with JuniperPython conda environment
- [ ] **CasCor backend tested** independently

**Check CasCor backend:**

```bash
# Navigate to cascor directory
cd ../cascor

# Run CasCor tests
cd src
pytest

# Verify CasCor works
python -c "from cascade_correlation.cascade_correlation import CascadeCorrelationNetwork; print('OK')"
```

---

## Quick Setup

### Step 1: Verify CasCor Backend Location

**Default location:** `../cascor` (relative to juniper_canopy)

**Directory structure:**

```bash
JuniperCanopy/
├── juniper_canopy/          # Frontend (this project)
│   ├── src/
│   │   ├── backend/
│   │   │   └── cascor_integration.py
│   │   └── main.py
│   └── conf/
│       └── app_config.yaml
│
└── cascor/                  # Backend (CasCor prototype)
    └── src/
        └── cascade_correlation/
            ├── cascade_correlation.py
            └── cascade_correlation_config/
```

**Verify path:**

```bash
cd ~/Development/python/JuniperCanopy/juniper_canopy
ls ../cascor/src/cascade_correlation/cascade_correlation.py
# Should exist
```

---

### Step 2: Configure Backend Path

#### Option A: Use default path (recommended)

Default path in `conf/app_config.yaml`:

```yaml
backend:
  cascor_integration:
    enabled: true
    backend_path: ~/Development/python/JuniperCanopy/cascor
```

No configuration needed if CasCor is at default location.

---

#### Option B: Set custom path

**Via environment variable:**

```bash
export CASCOR_BACKEND_PATH=/path/to/cascor
```

**Or edit `conf/app_config.yaml`:**

```yaml
backend:
  cascor_integration:
    backend_path: /custom/path/to/cascor
```

---

### Step 3: Disable Demo Mode

#### Disable demo mode to use real backend

```bash
# Unset demo mode
unset CASCOR_DEMO_MODE

# Or explicitly set to 0
export CASCOR_DEMO_MODE=0
```

---

### Step 4: Launch Application

```bash
# Using try script (recommended)
./try

# Or manually
cd src
/opt/miniforge3/envs/JuniperPython/bin/python main.py
```

**Expected output:**

```bash
INFO: CasCor backend path: /home/user/.../cascor
INFO: Added to Python path: /home/user/.../cascor/src
INFO: Imported CascadeCorrelationNetwork
INFO: Imported CascadeCorrelationConfig
INFO: CascorIntegration initialized successfully
INFO: CasCor backend integration enabled
INFO: Uvicorn running on http://0.0.0.0:8050
```

---

### Step 5: Verify Connection

**Check logs:**

```bash
tail -f logs/system.log | grep -i cascor
```

**Expected:**

```bash
INFO: CasCor backend found at: /path/to/cascor
INFO: CascorIntegration initialized successfully
```

**Not expected:**

```bash
WARNING: CasCor backend not found, falling back to demo mode
```

---

## Configuration

### Configuration File

**In `conf/app_config.yaml`:**

```yaml
backend:
  # CasCor network integration
  cascor_integration:
    # Enable CasCor backend integration
    enabled: true

    # Enable monitoring hooks
    monitoring_hooks: true

    # State polling interval (milliseconds)
    state_polling_interval_ms: 500

    # Backend path (supports ~, $HOME, environment variables)
    backend_path: ~/Development/python/JuniperCanopy/cascor
```

### Environment Variables

**Override configuration:**

```bash
# Enable/disable integration
export CASCOR_BACKEND_ENABLED=1  # 1=enabled, 0=disabled

# Set backend path
export CASCOR_BACKEND_PATH=/path/to/cascor

# Disable demo mode
export CASCOR_DEMO_MODE=0

# Enable monitoring hooks
export CASCOR_MONITORING_HOOKS=1
```

### Path Resolution Priority

**CascorIntegration resolves path in this order:**

1. **Explicit parameter:** `CascorIntegration(backend_path="/explicit/path")`
2. **Environment variable:** `CASCOR_BACKEND_PATH`
3. **Configuration file:** `backend.cascor_integration.backend_path`
4. **Default:** `../cascor`

**Path expansion support:**

- Tilde expansion: `~/path` → `/home/user/path`
- Environment variables: `$HOME/cascor` or `${HOME}/cascor`
- Relative paths: `../cascor`, `../../cascor`
- Absolute paths: `/absolute/path/to/cascor`

---

## Verification

### Check Backend Connection

**In logs:**

```bash
tail -f logs/system.log | grep "CasCor backend"
```

**Expected output:**

```bash
INFO: CasCor backend found at: /path/to/cascor
INFO: Added to Python path: /path/to/cascor/src
INFO: Imported CascadeCorrelationNetwork
```

### Test Integration Programmatically

**Create test script `test_integration.py`:**

```python
#!/usr/bin/env python
from backend.cascor_integration import CascorIntegration

# Create integration
integration = CascorIntegration()

# Create network
network = integration.create_network(config={
    'input_size': 2,
    'output_size': 1,
    'learning_rate': 0.01,
    'output_epochs': 100
})

print(f"Network created: {network}")
print(f"Input size: {network.input_size}")
print(f"Output size: {network.output_size}")

# Install hooks
integration.install_monitoring_hooks()
print("Monitoring hooks installed")

# Get status
status = integration.get_training_status()
print(f"Training status: {status}")

# Cleanup
integration.shutdown()
print("Integration shutdown complete")
```

**Run test:**

```bash
cd src
python test_integration.py
```

### Test with Training

**Create training test `test_training.py`:**

```python
#!/usr/bin/env python
import torch
from backend.cascor_integration import CascorIntegration

# Create integration
integration = CascorIntegration()

# Create network
network = integration.create_network(config={
    'input_size': 2,
    'output_size': 1,
    'learning_rate': 0.01,
    'output_epochs': 50,
    'candidate_epochs': 50,
    'max_hidden_units': 5
})

# Install monitoring
integration.install_monitoring_hooks()

# Generate simple XOR dataset
x = torch.tensor([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=torch.float32)
y = torch.tensor([[0], [1], [1], [0]], dtype=torch.float32)

# Train network
print("Starting training...")
history = network.fit(x, y)

print(f"Training complete!")
print(f"Final loss: {history['train_loss'][-1]:.4f}")
print(f"Hidden units added: {len(network.hidden_units)}")

# Get topology
topology = integration.get_network_topology()
print(f"Network topology: {topology}")

# Cleanup
integration.shutdown()
```

**Run training test:**

```bash
cd src
python test_training.py
```

**Expected output:**

```bash
INFO: CascorIntegration initialized successfully
INFO: Network created: input_size=2, output_size=1
INFO: Monitoring hooks installed successfully
Starting training...
INFO: Training started
INFO: Training completed
Training complete!
Final loss: 0.0123
Hidden units added: 3
Network topology: {...}
INFO: CasCor integration shutdown complete
```

---

## Common Issues

### Issue 1: Backend Not Found

**Error:**

```bash
FileNotFoundError: CasCor backend not found at: /path/to/cascor
```

**Cause:** Backend path incorrect or backend not installed

**Solution:**

```bash
# Check if cascor exists
ls ../cascor/src/cascade_correlation/cascade_correlation.py

# If not, verify path in config
cat conf/app_config.yaml | grep backend_path

# Set correct path
export CASCOR_BACKEND_PATH=/correct/path/to/cascor

# Or update conf/app_config.yaml
```

---

### Issue 2: Import Failed

**Error:**

```bash
ImportError: Failed to import CasCor backend modules: ...
```

**Cause:** CasCor backend structure changed or incomplete

**Solution:**

```bash
# Verify CasCor structure
ls ../cascor/src/cascade_correlation/

# Should contain:
# - cascade_correlation.py
# - cascade_correlation_config/

# Test import manually
cd ../cascor/src
python -c "from cascade_correlation.cascade_correlation import CascadeCorrelationNetwork"

# If fails, CasCor backend needs fixing
```

---

### Issue 3: Falls Back to Demo Mode

**Symptom:** Application runs but uses demo data instead of real backend

**Cause:** Backend not found or disabled

**Solution:**

```bash
# Check logs
tail -f logs/system.log | grep -E "(CasCor|demo)"

# Look for:
# "CasCor backend not found, falling back to demo mode"

# Verify demo mode is disabled
echo $CASCOR_DEMO_MODE  # Should be empty or 0

# Verify backend path is correct
echo $CASCOR_BACKEND_PATH

# Restart application
./try
```

---

### Issue 4: Network Creation Fails

**Error:**

```bash
TypeError: CascadeCorrelationConfig() got unexpected keyword argument ...
```

**Cause:** Configuration parameter mismatch

**Solution:**

```bash
# Check CascadeCorrelationConfig parameters
cd ../cascor/src
python -c "from cascade_correlation.cascade_correlation_config.cascade_correlation_config import CascadeCorrelationConfig; help(CascadeCorrelationConfig.__init__)"

# Update integration code with correct parameter names
# Or use parameter mapping in cascor_integration.py
```

---

### Issue 5: Monitoring Hooks Not Working

**Symptom:** Training runs but no metrics appear in dashboard

**Solution:**

```bash
# Verify hooks are enabled in config
grep "monitoring_hooks" conf/app_config.yaml
# Should be: monitoring_hooks: true

# Check if hooks were installed
tail -f logs/system.log | grep "Monitoring hooks"
# Should see: "Monitoring hooks installed successfully"

# Verify WebSocket connection
# In browser console:
# ws://localhost:8050/ws/training should be connected
```

---

## Async Training (v0.25.0)

**v0.25.0 adds non-blocking training support** via `fit_async()` and `start_training_background()` methods.

### Start Training in Background

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()
network = integration.create_network(...)

# Start training without blocking
integration.start_training_background(x_train, y_train, epochs=100)

# Check if training is in progress
if integration.is_training_in_progress():
    print("Training running...")

# Request training to stop gracefully
integration.request_training_stop()
```

### Using fit_async()

```python
import asyncio

async def main():
    # Non-blocking fit (awaitable coroutine)
    training_task = asyncio.create_task(
        integration.fit_async(x_train, y_train, epochs=100)
    )

    # Do other work while training runs...

    # Wait for completion when needed
    result = await training_task

asyncio.run(main())
```

**Note:** Background training runs in a `ThreadPoolExecutor`, allowing the UI to remain responsive during training.

---

## Remote Workers (v0.25.0)

**v0.25.0 adds distributed training support** via `RemoteWorkerClient` integration.

### Connect to Remote Workers

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()

# Connect to remote workers
integration.connect_remote_workers(host="192.168.1.100", port=5000)

# Start distributed training
integration.start_remote_workers(x_train, y_train, worker_count=4)

# Monitor remote worker status
status = integration.get_remote_worker_status()
print(f"Workers active: {status['active_workers']}")
```

**See [CASCOR_BACKEND_MANUAL.md](CASCOR_BACKEND_MANUAL.md) for complete remote worker configuration and advanced distributed training options.**

---

## Next Steps

### Explore Integration Features

**1. Get network topology:**

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()
network = integration.create_network(...)
topology = integration.get_network_topology()
print(topology)
```

**2. Get dataset info:**

```python
dataset_info = integration.get_dataset_info(x_train, y_train)
print(f"Samples: {dataset_info['num_samples']}")
print(f"Features: {dataset_info['num_features']}")
```

**3. Get prediction function:**

```python
predict_fn = integration.get_prediction_function()
predictions = predict_fn(x_test)
```

**4. Monitor training status:**

```python
status = integration.get_training_status()
print(f"Training: {status['is_training']}")
print(f"Epoch: {status['current_epoch']}")
```

### Advanced Configuration

**Start monitoring thread:**

```python
# Start background monitoring (polls every 0.5s)
integration.start_monitoring_thread(interval=0.5)

# Stop monitoring
integration.stop_monitoring()
```

**Register custom callbacks:**

```python
def on_epoch_end(epoch, loss, accuracy):
    print(f"Epoch {epoch}: loss={loss:.4f}, acc={accuracy:.4f}")

integration.create_monitoring_callback('epoch_end', on_epoch_end)
```

### Integration with Dashboard

**The integration automatically provides:**

1. **Real-time metrics** via monitoring hooks
2. **Network topology** for visualization
3. **Training status** for controls
4. **Prediction function** for decision boundaries

**No additional code needed - dashboard uses integration automatically!**

---

## Architecture

```bash
┌────────────────────────────────────────────────────────┐
│          Juniper Canopy Frontend                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │              FastAPI Backend                     │  │
│  │  ┌────────────────────────────────────────────┐  │  │
│  │  │       CascorIntegration                    │  │  │
│  │  │  - Dynamic import                          │  │  │
│  │  │  - Method wrapping                         │  │  │
│  │  │  - Monitoring hooks                        │  │  │
│  │  └────────────┬───────────────────────────────┘  │  │
│  └───────────────┼──────────────────────────────────┘  │
└──────────────────┼─────────────────────────────────────┘
                   │
                   ▼
     ┌──────────────────────────────┐
     │    CasCor Backend            │
     │  (Prototype at ../cascor)    │
     │  ┌────────────────────────┐  │
     │  │ CascadeCorrelation     │  │
     │  │ Network                │  │
     │  │                        │  │
     │  │ - fit()                │  │
     │  │ - train_output_layer() │  │
     │  │ - train_candidates()   │  │
     │  │ - forward()            │  │
     │  └────────────────────────┘  │
     └──────────────────────────────┘
```

---

## Additional Resources

- **[CASCOR_BACKEND_MANUAL.md](CASCOR_BACKEND_MANUAL.md)** - Complete integration guide
- **[CASCOR_BACKEND_REFERENCE.md](CASCOR_BACKEND_REFERENCE.md)** - Technical reference
- **[CasCor Backend](../cascor/README.md)** - CasCor prototype documentation
- **[AGENTS.md](AGENTS.md)** - Development guide

---

## Summary

**What Works:** ✅

- Dynamic backend import
- Network creation and configuration
- Monitoring hook installation
- Topology extraction
- Dataset info retrieval
- Prediction function access

**What's Tested:** ✅

- Basic integration tests
- Method wrapping
- Thread safety
- Error handling

**Next Level:**

- Add more comprehensive integration tests
- Implement advanced monitoring features
- Add checkpoint/resume support
- Integrate with Redis/Cassandra (when implemented)

---

**Last Updated:** January 29, 2026  
**Version:** 0.25.0  
**Status:** ✅ ASYNC TRAINING READY

**Ready to use! See [CASCOR_BACKEND_MANUAL.md](CASCOR_BACKEND_MANUAL.md) for advanced features!**
