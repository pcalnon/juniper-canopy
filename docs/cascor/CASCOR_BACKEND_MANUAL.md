# CasCor Backend Integration Manual

## Complete guide for CasCor backend integration in Juniper Canopy

**Version:** 0.25.0  
**Status:** ✅ PARTIALLY IMPLEMENTED  
**Last Updated:** January 29, 2026

---

## Overview

The CasCor backend integration (`src/backend/cascor_integration.py`) provides a seamless connection between the Juniper Canopy frontend and the CasCor (Cascade Correlation) neural network prototype.

### Features

**Implemented:**

- ✅ Dynamic import of CasCor backend modules
- ✅ Network instantiation with configuration mapping
- ✅ Method wrapping for monitoring hooks
- ✅ Real-time metrics extraction and broadcasting
- ✅ Network topology extraction (thread-safe)
- ✅ Dataset information retrieval
- ✅ Prediction function access
- ✅ Background monitoring thread
- ✅ Automatic fallback to demo mode
- ✅ Async training support (`fit_async`, `start_training_background`)
- ✅ Remote worker integration for distributed training

**Planned:**

- ⏳ Checkpoint/resume support
- ⏳ Advanced metric aggregation
- ⏳ Multi-network management
- ⏳ Enhanced error recovery

---

## Table of Contents

- [Architecture](#architecture)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Advanced Features](#advanced-features)
- [Async Training](#async-training)
- [Remote Worker Integration](#remote-worker-integration)
- [Monitoring Hooks](#monitoring-hooks)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Architecture

### Component Overview

```bash
┌───────────────────────────────────────────────────────────┐
│                  CascorIntegration                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Path Resolution & Import                           │  │
│  │  - Resolves backend path (~/path, $VAR, etc.)       │  │
│  │  - Adds backend/src to Python path                  │  │
│  │  - Imports CascadeCorrelationNetwork                │  │
│  │  - Imports CascadeCorrelationConfig                 │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Network Management                                 │  │
│  │  - create_network(config)                           │  │
│  │  - connect_to_network(network)                      │  │
│  │  - Configuration mapping                            │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Monitoring Hooks                                   │  │
│  │  - Wrap fit()                                       │  │
│  │  - Wrap train_output_layer()                        │  │
│  │  - Wrap train_candidates()                          │  │
│  │  - Inject callbacks                                 │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Data Extraction                                    │  │
│  │  - get_network_topology() [thread-safe]             │  │
│  │  - get_dataset_info()                               │  │
│  │  - get_prediction_function()                        │  │
│  │  - get_training_status()                            │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Background Monitoring                              │  │
│  │  - Polling loop (configurable interval)             │  │
│  │  - Metrics extraction                               │  │
│  │  - WebSocket broadcasting                           │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  CasCor Backend         │
              │  (../cascor)            │
              │                         │
              │  CascadeCorrelation     │
              │  Network                │
              └─────────────────────────┘
```

### Data Flow

**1. Initialization:**

```bash
CascorIntegration.__init__()
  └→ _resolve_backend_path()
     └→ _add_backend_to_path()
        └→ _import_backend_modules()
```

**2. Network Creation:**

```bash
create_network(config)
  └→ Map config parameters
     └→ Create CascadeCorrelationConfig
        └→ Create CascadeCorrelationNetwork
           └→ Return network instance
```

**3. Training with Monitoring:**

```bash
install_monitoring_hooks()
  └→ Wrap network.fit()
     └→ Wrap network.train_output_layer()
        └→ Wrap network.train_candidates()

network.fit(x, y)
  └→ monitored_fit()
     └→ _on_training_start()
     └→ original_fit(x, y)
     └→ _on_training_complete(result)
```

**4. Real-Time Monitoring:**

```bash
start_monitoring_thread(interval=1.0)
  └→ _monitoring_loop()
     └→ while monitoring_active:
        └→ _extract_current_metrics()
           └→ _broadcast_message(metrics)
           └→ sleep(interval)
```

---

## Installation

### Prerequisites

1. **CasCor backend installed:**

   ```bash
   cd ~/Development/python/Juniper/juniper-canopy
   ls cascor/src/cascade_correlation/cascade_correlation.py
   ```

2. **Dependencies installed:**

   ```bash
   conda activate JuniperPython
   pip install torch numpy
   ```

3. **Juniper Canopy running:**

   ```bash
   cd juniper_canopy
   ./demo  # Test demo mode first
   ```

### Configuration

**In `conf/app_config.yaml`:**

```yaml
backend:
  cascor_integration:
    enabled: true
    monitoring_hooks: true
    state_polling_interval_ms: 500
    backend_path: ~/Development/python/Juniper/juniper-cascor
```

**Environment variables:**

```bash
export CASCOR_BACKEND_PATH=/path/to/cascor
export CASCOR_DEMO_MODE=0  # Disable demo mode
```

---

## Basic Usage

### Example 1: Simple Network Training

```python
#!/usr/bin/env python
from backend.cascor_integration import CascorIntegration
import torch

# Create integration
integration = CascorIntegration()

# Create network
config = {
    'input_size': 2,
    'output_size': 1,
    'learning_rate': 0.01,
    'output_epochs': 100,
    'candidate_epochs': 100,
    'max_hidden_units': 5
}
network = integration.create_network(config)

# Install monitoring
integration.install_monitoring_hooks()

# Prepare data (XOR problem)
x = torch.tensor([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=torch.float32)
y = torch.tensor([[0], [1], [1], [0]], dtype=torch.float32)

# Train (automatically monitored)
history = network.fit(x, y)

print(f"Final loss: {history['train_loss'][-1]:.4f}")
print(f"Hidden units: {len(network.hidden_units)}")

# Cleanup
integration.shutdown()
```

### Example 2: Using Existing Network

```python
from backend.cascor_integration import CascorIntegration
from cascade_correlation.cascade_correlation import CascadeCorrelationNetwork

# Create network directly
network = CascadeCorrelationNetwork(...)

# Connect integration to existing network
integration = CascorIntegration()
integration.connect_to_network(network)

# Install monitoring
integration.install_monitoring_hooks()

# Now train as usual
history = network.fit(x, y)
```

### Example 3: Background Monitoring

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()
network = integration.create_network(config)
integration.install_monitoring_hooks()

# Start background monitoring (polls every 0.5 seconds)
integration.start_monitoring_thread(interval=0.5)

# Train (monitoring runs in background)
history = network.fit(x, y)

# Stop monitoring
integration.stop_monitoring()
integration.shutdown()
```

---

## Advanced Features

### Custom Monitoring Callbacks

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()
network = integration.create_network(config)

# Define callbacks
def on_epoch(epoch, loss, accuracy):
    print(f"Epoch {epoch}: loss={loss:.4f}, acc={accuracy:.4f}")

def on_training_start():
    print("Training started!")

def on_training_end():
    print("Training completed!")

# Register callbacks
integration.create_monitoring_callback('epoch_end', on_epoch)
integration.create_monitoring_callback('training_start', on_training_start)
integration.create_monitoring_callback('training_end', on_training_end)

# Install hooks
integration.install_monitoring_hooks()

# Train
network.fit(x, y)
```

### Topology Extraction

```python
# Get current network topology
topology = integration.get_network_topology()

print(f"Input size: {topology['input_size']}")
print(f"Output size: {topology['output_size']}")
print(f"Hidden units: {len(topology['hidden_units'])}")

# Hidden unit details
for i, unit in enumerate(topology['hidden_units']):
    print(f"Unit {i}:")
    print(f"  Bias: {unit['bias']:.4f}")
    print(f"  Weights shape: {len(unit['weights'])}")
    print(f"  Activation: {unit['activation']}")
```

### Dataset Information

```python
# Get dataset info for visualization
dataset_info = integration.get_dataset_info(x_train, y_train)

print(f"Samples: {dataset_info['num_samples']}")
print(f"Features: {dataset_info['num_features']}")
print(f"Classes: {dataset_info['num_classes']}")
print(f"Distribution: {dataset_info['class_distribution']}")
```

### Prediction Function

```python
# Get prediction function for decision boundary
predict_fn = integration.get_prediction_function()

# Use for predictions
import numpy as np
grid_x = np.linspace(-2, 2, 100)
grid_y = np.linspace(-2, 2, 100)
xx, yy = np.meshgrid(grid_x, grid_y)
grid_points = np.c_[xx.ravel(), yy.ravel()]

# Get predictions
predictions = predict_fn(grid_points)
print(f"Predictions shape: {predictions.shape}")
```

### Training Status

```python
# Get current training status
status = integration.get_training_status()

print(f"Network connected: {status['network_connected']}")
print(f"Monitoring active: {status['monitoring_active']}")
print(f"Is training: {status['is_training']}")
print(f"Current epoch: {status['current_epoch']}")
print(f"Input size: {status['input_size']}")
print(f"Output size: {status['output_size']}")
print(f"Hidden units: {status['hidden_units']}")
```

---

## Async Training

The CasCor integration supports asynchronous training to keep the UI responsive during long training sessions.

### Using fit_async

The `fit_async` method runs training in a background thread and returns an awaitable:

```python
import asyncio
from backend.cascor_integration import CascorIntegration

async def train_network():
    integration = CascorIntegration()
    network = integration.create_network({
        'input_size': 2,
        'output_size': 1,
        'max_hidden_units': 5
    })

    # Prepare data
    x = torch.tensor([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=torch.float32)
    y = torch.tensor([[0], [1], [1], [0]], dtype=torch.float32)

    # Async training - UI remains responsive
    history = await integration.fit_async(x, y, {'learning_rate': 0.01})

    print(f"Training complete: {history['train_loss'][-1]:.4f}")

asyncio.run(train_network())
```

### Using start_training_background

For fire-and-forget training, use `start_training_background`:

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()
network = integration.create_network(config)

# Start training in background (returns immediately)
integration.start_training_background(x, y, {'learning_rate': 0.01})

# Check training status
while integration.is_training_in_progress():
    status = integration.get_training_status()
    print(f"Epoch: {status['current_epoch']}")
    time.sleep(1.0)

print("Training complete!")
```

### Stopping Training

Request graceful training stop:

```python
# Request stop (training completes current epoch)
integration.request_training_stop()

# Check if still running
if not integration.is_training_in_progress():
    print("Training stopped")
```

---

## Remote Worker Integration

The CasCor integration supports distributed training via remote workers for improved performance on large datasets.

### Connecting to Remote Workers

```python
from backend.cascor_integration import CascorIntegration

integration = CascorIntegration()

# Connect to existing remote worker manager
integration.connect_remote_workers(
    address=('192.168.1.100', 5000),
    authkey=b'secret_key'
)

# Verify connection
status = integration.get_remote_worker_status()
print(f"Connected workers: {status['connected_workers']}")
print(f"Worker status: {status['status']}")
```

### Starting Local Workers

Start worker processes on the local machine:

```python
# Start 4 local worker processes
integration.start_remote_workers(num_workers=4)

# Check worker status
status = integration.get_remote_worker_status()
print(f"Active workers: {status['active_workers']}")
print(f"Pending tasks: {status['pending_tasks']}")
```

### Stopping Workers

```python
# Stop workers with timeout
integration.stop_remote_workers(timeout=5.0)

# Or disconnect without stopping
integration.disconnect_remote_workers()
```

### Worker Status

```python
status = integration.get_remote_worker_status()

# Status dictionary structure:
# {
#     'connected': True,
#     'active_workers': 4,
#     'connected_workers': 4,
#     'pending_tasks': 0,
#     'completed_tasks': 127,
#     'status': 'running',
#     'address': ('192.168.1.100', 5000)
# }
```

---

## Monitoring Hooks

### Hook Architecture

The integration wraps three key methods:

1. **fit()** - Main training loop
2. **train_output_layer()** - Output training phase
3. **train_candidates()** - Candidate training phase

### Hook Lifecycle

```bash
network.fit(x, y)
  ↓
monitored_fit(x, y)
  ↓
  _on_training_start()
    - Broadcast training_start event
    - Initialize training monitor
  ↓
  original_fit(x, y)
    ↓
    train_output_layer()
      ↓
      monitored_train_output()
        ↓
        _on_output_phase_start()
        ↓
        original_train_output()
        ↓
        _on_output_phase_end(result)
    ↓
    train_candidates()
      ↓
      monitored_train_candidates()
        ↓
        _on_candidate_phase_start()
        ↓
        original_train_candidates()
        ↓
        _on_candidate_phase_end(result)
  ↓
  _on_training_complete(history)
    - Broadcast training_complete event
    - Finalize training monitor
```

### Hook Events

**training_start:**

```json
{
  "type": "training_start",
  "timestamp": "2025-11-05T12:00:00",
  "input_size": 2,
  "output_size": 1
}
```

**training_complete:**

```json
{
  "type": "training_complete",
  "timestamp": "2025-11-05T12:05:00",
  "history": {...},
  "hidden_units_added": 3
}
```

---

## API Reference

See [CASCOR_BACKEND_REFERENCE.md](CASCOR_BACKEND_REFERENCE.md) for complete API documentation.

**Key Methods:**

- `CascorIntegration(backend_path=None)` - Constructor
- `create_network(config)` - Create new network
- `connect_to_network(network)` - Connect to existing network
- `install_monitoring_hooks()` - Install monitoring
- `start_monitoring_thread(interval)` - Start background monitoring
- `stop_monitoring()` - Stop background monitoring
- `get_network_topology()` - Extract topology
- `get_dataset_info(x, y)` - Get dataset information
- `get_prediction_function()` - Get prediction function
- `get_training_status()` - Get training status
- `fit_async(data, params)` - Async training
- `start_training_background(data, params)` - Background training
- `is_training_in_progress()` - Check training status
- `request_training_stop()` - Request training stop
- `connect_remote_workers(address, authkey)` - Connect to workers
- `start_remote_workers(num_workers)` - Start local workers
- `stop_remote_workers(timeout)` - Stop workers
- `disconnect_remote_workers()` - Disconnect from workers
- `get_remote_worker_status()` - Get worker status
- `shutdown()` - Cleanup resources

---

## Testing

### Unit Tests

```bash
cd src
pytest tests/unit/test_cascor_integration.py -v
```

### Integration Tests

```bash
cd src
pytest tests/integration/test_cascor_backend.py -v
```

### Manual Testing

```bash
# Test backend connection
cd src
python -c "from backend.cascor_integration import CascorIntegration; CascorIntegration()"

# Test network creation
python test_integration.py

# Test with training
python test_training.py
```

---

## Troubleshooting

See [CASCOR_BACKEND_QUICK_START.md](CASCOR_BACKEND_QUICK_START.md#common-issues) for common issues.

### Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

integration = CascorIntegration()
# Will see detailed logs
```

### Thread Safety Issues

All topology extraction is protected by locks:

```python
# Thread-safe topology access
topology = integration.get_network_topology()  # Uses self.topology_lock
```

### Memory Management

The integration ensures proper cleanup:

```python
# Always call shutdown
integration.shutdown()

# Or use context manager (when implemented)
with CascorIntegration() as integration:
    network = integration.create_network(config)
    # ... use network ...
# Automatic cleanup
```

---

## Additional Resources

- **[CASCOR_BACKEND_QUICK_START.md](CASCOR_BACKEND_QUICK_START.md)** - Quick setup guide
- **[CASCOR_BACKEND_REFERENCE.md](CASCOR_BACKEND_REFERENCE.md)** - Technical reference
- **[CasCor Backend README](../cascor/README.md)** - CasCor prototype docs
- **[AGENTS.md](AGENTS.md)** - Development guide

---

**Last Updated:** January 29, 2026  
**Version:** 0.25.0  
**Status:** ✅ PARTIALLY IMPLEMENTED

**Explore advanced features and integrate with your workflow!**
