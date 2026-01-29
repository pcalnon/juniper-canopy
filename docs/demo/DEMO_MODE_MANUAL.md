# Demo Mode Manual

Complete user guide for the Juniper Canopy demo mode.

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Dashboard Interface](#dashboard-interface)
4. [Training Controls](#training-controls)
5. [Simulated Training Behavior](#simulated-training-behavior)
6. [WebSocket API](#websocket-api)
7. [Extending Demo Mode](#extending-demo-mode)
8. [Troubleshooting](#troubleshooting)

## Overview

### What is Demo Mode?

Demo mode simulates a complete CasCor neural network training session without requiring the actual CasCor C++ backend. It enables:

- **UI development** without backend dependency
- **Feature testing** with realistic data flows
- **Demonstrations** of network training behavior
- **Integration testing** of frontend components

### Demo vs Production

| Feature         | Demo Mode                     | Production Mode                |
| --------------- | ----------------------------- | ------------------------------ |
| **Backend**     | Simulated (Python)            | Real CasCor (C++/Python)       |
| **Dataset**     | Fixed spiral (200 samples)    | Configurable datasets          |
| **Training**    | Deterministic curves          | Real network training          |
| **Network**     | Simulated cascade growth      | Actual cascade correlation     |
| **Performance** | Fixed timing (~100ms updates) | Variable based on computation  |
| **Purpose**     | Development, testing, demos   | Real neural network training   |
| **Launch**      | `./demo`                      | `cd src && python main.py`     |
| **Config**      | `CASCOR_DEMO_MODE=1`          | `CASCOR_DEMO_MODE=0` (default) |

### When to Use Demo Mode

**Use demo mode for:**

- UI development and iteration
- Frontend testing without backend setup
- Demonstrations and presentations
- CI/CD testing pipelines
- Learning the CasCor visualization interface

**Use production mode for:**

- Actual neural network training
- Real dataset experimentation
- Performance benchmarking
- Research and analysis

## Getting Started

### Quick Launch

```bash
# From project root
./demo
```

The demo script:

1. Activates JuniperPython conda environment
2. Sets `CASCOR_DEMO_MODE=1`
3. Launches FastAPI server on port 8050
4. Starts Dash dashboard
5. Initializes demo training simulation

### Manual Launch

```bash
# Activate conda environment
conda activate JuniperPython

# Set demo mode
export CASCOR_DEMO_MODE=1

# Launch application
cd src
python main.py
```

### Verify Demo Mode Active

Check terminal output for:

```bash
2025-11-03 10:00:00 [INFO] Demo mode enabled
2025-11-03 10:00:00 [INFO] Initializing demo training simulation...
2025-11-03 10:00:00 [INFO] Demo mode started: Spiral dataset (200 samples, 2 features)
```

### Access Dashboard

Open browser to: `http://localhost:8050`

## Dashboard Interface

### Tab 1: Training Metrics

Real-time visualization of training progress:

**Loss Plot:**

- Training loss (blue) - Exponential decay from ~0.7 to ~0.05
- Validation loss (orange) - Similar curve with slight offset
- Updates every 100ms via WebSocket

**Accuracy Plot:**

- Training accuracy (green) - Rises from ~50% to ~98%
- Validation accuracy (red) - Tracks training with small gap
- Realistic learning curves with plateaus

**Key Metrics Display:**

- Current epoch
- Training/validation loss
- Training/validation accuracy
- Learning rate
- Number of hidden units

### Tab 2: Network Topology

Dynamic visualization of cascade network structure:

**Initial State (Epoch 0-29):**

- 2 input nodes (spiral features)
- No hidden units
- 2 output nodes (class 0, class 1)

**After Cascade Events (Every 30 Epochs):**

- New hidden unit added
- Connections from inputs → new hidden unit
- Connections from new hidden unit → outputs
- Maximum 8 hidden units (240 epochs)

**Graph Layout:**

- Input layer (left)
- Hidden layer (middle, grows vertically)
- Output layer (right)
- Edge thickness represents connection strength (simulated)

### Tab 3: Decision Boundary

2D visualization of network learning on spiral dataset:

**Dataset Points:**

- 200 samples total
- 2 features (x, y coordinates)
- 2 classes (inner spiral, outer spiral)
- Color-coded by true class

**Decision Boundary:**

- Background heatmap showing predicted class probabilities
- Updates as network learns
- Progressively separates spiral classes
- Demonstrates cascade correlation learning

**Evolution Over Time:**

- Epoch 0-30: Simple linear separation (poor)
- Epoch 30-60: First hidden unit improves separation
- Epoch 60-180: Additional units refine boundary
- Epoch 180+: Complex spiral boundary captured

### Tab 4: Dataset View

Static visualization of training data:

**Spiral Dataset Properties:**

- 200 points (100 per class)
- 2D features (x, y)
- Non-linearly separable
- Standard CasCor benchmark dataset

**Display:**

- Scatter plot with class colors
- Dataset statistics
- Feature ranges
- Class distribution

## Training Controls

### Control Interface

Located at top of dashboard:

```bash
[Start] [Pause] [Resume] [Reset] [Stop]
Status: [Running/Paused/Stopped]
Epoch: [Current Epoch] / 300 (max)
```

### Start/Restart

**Button:** Start (or automatic on launch)

**Effect:**

- Begins training simulation from epoch 0
- Resets all metrics
- Starts WebSocket broadcasting
- Enables other controls

**WebSocket Command:**

```json
{"command": "start"}
```

### Pause

**Button:** Pause

**Effect:**

- Halts training loop (thread-safe Event)
- Maintains current state (epoch, metrics, network)
- WebSocket broadcasting paused
- Dashboard shows "Paused" status

**WebSocket Command:**

```json
{"command": "pause"}
```

**Use cases:**

- Examine current state in detail
- Prepare for demonstration
- Debugging network behavior

### Resume

**Button:** Resume

**Effect:**

- Continues training from paused epoch
- Restores WebSocket broadcasting
- Dashboard shows "Running" status

**WebSocket Command:**

```json
{"command": "resume"}
```

### Reset

**Button:** Reset

**Effect:**

- Resets to epoch 0
- Clears all metrics history
- Removes all cascade units
- Resets loss/accuracy to initial values
- Training automatically resumes

**WebSocket Command:**

```json
{"command": "reset"}
```

**Use cases:**

- Start fresh demonstration
- Test UI reset behavior
- Compare training runs

### Stop

**Button:** Stop (or Ctrl+C in terminal)

**Effect:**

- Gracefully stops demo mode thread
- Closes WebSocket connections
- Saves final state (if configured)
- Shuts down FastAPI server

**WebSocket Command:**

```json
{"command": "stop"}
```

## Simulated Training Behavior

### Training Loop

Demo mode runs a background thread simulating training:

```python
while not self._stop.is_set():
    # Increment epoch
    epoch += 1

    # Calculate metrics (exponential decay)
    train_loss = calculate_loss(epoch)
    train_accuracy = calculate_accuracy(epoch)

    # Add cascade unit every 30 epochs
    if epoch % 30 == 0 and hidden_units < 8:
        hidden_units += 1

    # Broadcast metrics via WebSocket
    broadcast_metrics(epoch, train_loss, train_accuracy, hidden_units)

    # Wait epoch duration (50ms)
    time.sleep(0.05)
```

### Metric Curves

**Training Loss:**

```python
train_loss = 0.7 * np.exp(-epoch / 100) + 0.05
```

- Starts at 0.7
- Exponentially decays to 0.05
- Realistic training behavior

**Validation Loss:**

```python
val_loss = train_loss * 1.1 + 0.02
```

- Slightly higher than training (overfitting simulation)
- Offset by 0.02

**Training Accuracy:**

```python
train_accuracy = 0.98 * (1 - np.exp(-epoch / 80)) + 0.50
```

- Starts at 50% (random guess)
- Rises to 98%
- S-curve learning pattern

**Validation Accuracy:**

```python
val_accuracy = train_accuracy * 0.95
```

- Slightly lower than training (generalization gap)

### Cascade Events

**Trigger:** Every 30 epochs

**Effect:**

```python
if epoch % 30 == 0 and hidden_units < max_hidden_units:
    hidden_units += 1
    broadcast_topology_update()
```

**Maximum:** 8 hidden units (240 epochs)

**Simulation:**

- New node added to network graph
- Connections created (inputs → hidden, hidden → outputs)
- Decision boundary complexity increases

### Dataset Simulation

**Spiral Dataset Generation:**

```python
n_samples = 200
n_features = 2
n_classes = 2

# Generate spiral points
theta = np.linspace(0, 4*np.pi, n_samples//2)
r = np.linspace(0, 1, n_samples//2)

# Class 0: inner spiral
x0 = r * np.cos(theta)
y0 = r * np.sin(theta)

# Class 1: outer spiral (phase shifted)
x1 = r * np.cos(theta + np.pi)
y1 = r * np.sin(theta + np.pi)
```

**Properties:**

- 100 samples per class
- Deterministic (same every run)
- Non-linearly separable
- Standard benchmark dataset

## WebSocket API

### Connection Endpoints

**Training Metrics Channel:**

```bash
ws://localhost:8050/ws/training
```

**Control Channel:**

```bash
ws://localhost:8050/ws/control
```

### Message Format

All WebSocket messages use JSON:

```json
{
    "type": "metrics" | "state" | "topology" | "event",
    "timestamp": 1699000000.123,
    "data": { ... }
}
```

### Message Types

#### Type: metrics

```json
{
    "type": "metrics",
    "timestamp": 1699000000.123,
    "data": {
        "epoch": 45,
        "train_loss": 0.234,
        "val_loss": 0.256,
        "train_accuracy": 0.876,
        "val_accuracy": 0.845,
        "learning_rate": 0.01,
        "hidden_units": 1
    }
}
```

#### Type: state

```json
{
    "type": "state",
    "timestamp": 1699000000.123,
    "data": {
        "status": "running" | "paused" | "stopped",
        "epoch": 45,
        "total_epochs": 300
    }
}
```

#### Type: topology

```json
{
    "type": "topology",
    "timestamp": 1699000000.123,
    "data": {
        "nodes": [
            {"id": "input_0", "layer": "input"},
            {"id": "hidden_0", "layer": "hidden"},
            {"id": "output_0", "layer": "output"}
        ],
        "edges": [
            {"source": "input_0", "target": "hidden_0", "weight": 0.45},
            {"source": "hidden_0", "target": "output_0", "weight": 0.78}
        ]
    }
}
```

#### Type: event

```json
{
    "type": "event",
    "timestamp": 1699000000.123,
    "data": {
        "event": "cascade_add",
        "message": "Added hidden unit 2 at epoch 60"
    }
}
```

### Client Implementation

JavaScript client example (included in dashboard):

```javascript
// Connect to training metrics
const ws = new WebSocket('ws://localhost:8050/ws/training');

ws.onopen = () => {
    console.log('Connected to training WebSocket');
};

ws.onmessage = (event) => {
    const message = JSON.parse(event.data);

    switch(message.type) {
        case 'metrics':
            updateMetricsPlot(message.data);
            break;
        case 'topology':
            updateNetworkGraph(message.data);
            break;
        case 'event':
            showNotification(message.data.message);
            break;
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};

ws.onclose = () => {
    console.log('WebSocket closed, attempting reconnect...');
    setTimeout(connect, 5000);  // Reconnect after 5s
};
```

### Sending Control Commands

```javascript
// Connect to control channel
const controlWs = new WebSocket('ws://localhost:8050/ws/control');

// Send pause command
controlWs.send(JSON.stringify({command: 'pause'}));

// Send reset command
controlWs.send(JSON.stringify({command: 'reset'}));
```

## Extending Demo Mode

### Custom Dataset

Modify `src/demo_mode.py` to use custom dataset:

```python
class DemoMode:
    def __init__(self):
        # ... existing code ...

        # Load custom dataset
        self.__dataset = self._load_custom_dataset()

    def _load_custom_dataset(self):
        """Load custom dataset instead of spiral."""
        # Option 1: Load from file
        data = np.load('data/my_dataset.npy')

        # Option 2: Generate synthetic
        from sklearn.datasets import make_moons
        X, y = make_moons(n_samples=200, noise=0.1)

        return {'X': X, 'y': y}
```

### Custom Metric Curves

Modify metric calculation for different behavior:

```python
def _calculate_metrics(self, epoch):
    """Calculate metrics with custom curves."""

    # Custom loss curve (polynomial decay)
    train_loss = max(0.01, 0.8 * (1 / (1 + epoch/50)))

    # Custom accuracy curve (logistic growth)
    train_accuracy = 0.95 / (1 + np.exp(-(epoch-50)/20))

    # Add noise for realism
    train_loss += np.random.normal(0, 0.01)
    train_accuracy += np.random.normal(0, 0.005)

    return train_loss, train_accuracy
```

### Custom Cascade Behavior

Modify cascade unit addition logic:

```python
def _should_add_cascade_unit(self, epoch):
    """Custom cascade unit addition logic."""

    # Option 1: Adaptive (based on loss plateau)
    if epoch > 10 and self._loss_plateau_detected():
        return True

    # Option 2: Random intervals
    if np.random.random() < 0.05:  # 5% chance per epoch
        return True

    # Option 3: Fibonacci sequence
    if epoch in [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]:
        return True

    return False
```

### Additional Metrics

Add custom metrics to broadcast:

```python
def _get_current_state(self):
    """Get current state with custom metrics."""
    with self._lock:
        state = {
            # Standard metrics
            'epoch': self.__current_epoch,
            'train_loss': self.__train_loss,

            # Custom metrics
            'gradient_norm': self._calculate_gradient_norm(),
            'weight_sparsity': self._calculate_weight_sparsity(),
            'layer_activations': self._get_layer_activations()
        }
    return state
```

## Troubleshooting

### Issue: Demo Mode Won't Start

**Symptom:** Application launches but no training visible

**Diagnosis:**

```bash
# Check logs
tail -f logs/system.log

# Look for:
# [ERROR] Demo mode failed to start
# [DEBUG] Demo mode enabled: False
```

**Solutions:**

1. Verify `CASCOR_DEMO_MODE=1` is set
2. Check `conf/app_config.yaml` has `demo.enabled: true`
3. Ensure conda environment activated
4. Check no port conflicts

### Issue: Training Stops Unexpectedly

**Symptom:** Metrics stop updating mid-training

**Diagnosis:**

```python
# Check demo mode status
demo = get_demo_mode()
print(f"Running: {demo.is_running}")
print(f"Stopped: {demo._stop.is_set()}")
```

**Solutions:**

1. Check for exceptions in `logs/system.log`
2. Verify WebSocket connections active
3. Reset demo mode: Send `{command: 'reset'}`
4. Restart application

### Issue: WebSocket Disconnects

**Symptom:** Dashboard shows "Connecting..." or stale data

**Diagnosis:**

```javascript
// Browser console
console.log('WebSocket state:', ws.readyState);
// 0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED
```

**Solutions:**

1. Check network connectivity
2. Verify server running on correct port
3. Check browser console for errors
4. Refresh browser page
5. Clear browser cache

### Issue: Memory Usage Grows

**Symptom:** Application memory increases over time

**Diagnosis:**

```python
# Check buffer sizes
demo = get_demo_mode()
print(f"History size: {len(demo.__metrics_history)}")
```

**Solutions:**

1. Verify `deque(maxlen=1000)` is set for history buffers
2. Reset demo mode periodically
3. Check for unbounded collections in custom code

### Issue: Metrics Look Unrealistic

**Symptom:** Loss doesn't decrease, accuracy doesn't increase

**Diagnosis:**
Check metric calculation in `demo_mode.py`:

```python
print(f"Epoch {epoch}: loss={loss}, accuracy={accuracy}")
```

**Solutions:**

1. Verify exponential decay coefficients correct
2. Check no division by zero
3. Ensure random seed set for reproducibility
4. Review custom metric modifications

### Issue: Cascade Units Not Appearing

**Symptom:** Network topology doesn't update

**Diagnosis:**

```python
# Check cascade event trigger
if epoch % 30 == 0:
    print(f"Cascade event at epoch {epoch}")
```

**Solutions:**

1. Verify `cascade_interval` configuration (default 30)
2. Check `max_hidden_units` not exceeded (default 8)
3. Ensure topology messages broadcast via WebSocket
4. Check dashboard topology tab for errors

## Next Steps

- **[Technical Reference](DEMO_MODE_REFERENCE.md)** - Implementation details
- **[Environment Setup](DEMO_MODE_ENVIRONMENT_SETUP.md)** - Configuration guide
- **[Quick Start](DEMO_MODE_QUICK_START.md)** - Launch in 60 seconds

---

**Last Updated:** January 29, 2026
**Version:** v0.25.0

**See Also:**

- [AGENTS.md](../../AGENTS.md) - Development guide
- [README.md](../../README.md) - Project overview
- [DEVELOPMENT_ROADMAP.md](../../notes/DEVELOPMENT_ROADMAP.md) - Planned features
