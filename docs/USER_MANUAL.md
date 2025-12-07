# Juniper Canopy User Manual

**Version:** 0.4.0  
**Status:** ✅ Production Ready  
**Last Updated:** November 11, 2025  
**Project:** Juniper - Cascade Correlation Neural Network Monitoring

---

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [Training Controls](#training-controls)
5. [Visualization Tabs](#visualization-tabs)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Features](#advanced-features)

---

## Introduction

### What is Juniper Canopy?

Juniper Canopy is a real-time monitoring and diagnostic frontend for Cascade Correlation (CasCor) Neural Networks. It provides:

- **Real-time Training Visualization** - Monitor loss, accuracy, and training progress
- **Network Topology Viewer** - Visualize network structure as it evolves
- **Decision Boundary Plotting** - See how the network classifies data
- **Dataset Explorer** - View and analyze training data
- **Training Controls** - Start, pause, resume, and reset training sessions

### Key Features

✅ **Zero Configuration** - Works out of the box with sensible defaults  
✅ **Demo Mode** - Test and explore without a CasCor backend  
✅ **Real-time Updates** - WebSocket-based push updates (<100ms latency)  
✅ **Responsive UI** - Modern Bootstrap-based interface  
✅ **Production Ready** - Comprehensive testing and CI/CD pipeline

---

## Getting Started

### Installation

1. **Clone the repository:**

   ```bash
   cd ~/Development/python/JuniperCanopy/juniper_canopy
   ```

2. **Activate the conda environment:**

   ```bash
   conda activate JuniperPython
   ```

3. **Verify dependencies:**

   ```bash
   pip install -r conf/requirements.txt
   ```

### Running the Application

#### Demo Mode (Recommended for First-Time Users)

Demo mode runs a simulated training session without requiring a CasCor backend:

```bash
./demo
```

This will:

- Start the FastAPI server at <http://127.0.0.1:8050>
- Initialize demo mode with spiral dataset
- Begin simulated training automatically
- Open the dashboard at <http://127.0.0.1:8050/dashboard/>

#### Production Mode (With Real CasCor Backend)

To connect to a real CasCor training session:

```bash
# Set backend path (if different from default)
export CASCOR_BACKEND_PATH=/path/to/cascor

# Run application
cd src
/opt/miniforge3/envs/JuniperPython/bin/python main.py
```

### Accessing the Dashboard

Once running, open your browser to:

```bash
http://127.0.0.1:8050/dashboard/
```

You should see:

- **Status Indicator** (Green ● Active / Blue ● Training)
- **WebSocket Connection Status**
- **Training Controls Panel** (left sidebar)
- **Network Information Panel** (left sidebar)
- **Visualization Tabs** (main area)

---

## Dashboard Overview

### Layout Structure

```bash
┌─────────────────────────────────────────────────────────┐
│              Juniper Canopy Monitor                    │
│    Real-time monitoring for Cascade Correlation NNs     │
├──────────────┬──────────────────────────────────────────┤
│ Status: ●    │ WebSocket: 1 connection(s)               │
├──────────────┴──────────────────────────────────────────┤
│ Training     │ ┌─────────────────────────────────────┐  │
│ Controls     │ │  [Training Metrics Tab]             │  │
│ ┌─────────┐  │ │                                     │  │
│ │ Start   │  │ │  Loss and Accuracy plots            │  │
│ │ Pause   │  │ │                                     │  │
│ │ Stop    │  │ └─────────────────────────────────────┘  │
│ └─────────┘  │                                          │
│              │                                          │
│ Network      │                                          │
│ Info         │                                          │
│ ┌─────────┐  │                                          │
│ │Input: 2 │  │                                          │
│ │Hidden:3 │  │                                          │
│ │Output:1 │  │                                          │
│ └─────────┘  │                                          │
└──────────────┴──────────────────────────────────────────┘
```

### Status Indicators

#### System Status (Top Left)

- 🟢 **Green ● Active** - Server running, idle
- 🔵 **Blue ● Training** - Training in progress
- 🟠 **Orange ● Standby** - Server connected, not healthy
- 🔴 **Red ● Error** - Connection or server error

#### WebSocket Status (Top Right)

- **`N connection(s)`** (Green) - Active WebSocket connections
- **Disconnected** (Gray) - No WebSocket connection

### Update Intervals

- **Fast Updates** (1 second): Status indicators, training metrics
- **Slow Updates** (5 seconds): Network topology, decision boundaries, dataset

---

## Training Controls

The **Training Controls Panel** (left sidebar) provides real-time control over training:

### Control Buttons

#### Start Training

```bash
┌─────────────────┐
│  Start Training │  (Green)
└─────────────────┘
```

- **Action:** Starts or restarts training from beginning
- **Demo Mode:** Begins simulated training with automatic epoch progression
- **Production Mode:** Initiates training on real CasCor backend
- **Note:** Automatically resets state on start

#### Pause Training

```bash
┌─────────────────┐
│  Pause Training │  (Yellow/Warning)
└─────────────────┘
```

- **Action:** Pauses training without losing state
- **Demo Mode:** Freezes epoch progression while maintaining current state
- **Production Mode:** Sends pause command to CasCor backend
- **Resume:** Click again to resume (button text changes)

#### Stop Training

```bash
┌─────────────────┐
│  Stop Training  │  (Red/Danger)
└─────────────────┘
```

- **Action:** Stops training completely
- **Demo Mode:** Halts simulation thread cleanly
- **Production Mode:** Sends stop command to CasCor backend
- **Warning:** State is preserved but training cannot be resumed (use Start to restart)

### Configuration Parameters

#### Learning Rate

- **Type:** Decimal number (step: 0.001)
- **Default:** 0.01
- **Range:** 0.001 - 1.0
- **Effect:** Controls training speed and convergence

#### Max Hidden Units

- **Type:** Integer (step: 1)
- **Default:** 10
- **Range:** 1 - 100
- **Effect:** Limits maximum cascade units added during training

> **Note:** In current version (MVP), these parameters are UI-only placeholders.  
> Full integration with training control is in development roadmap (Phase 3).

---

## Visualization Tabs

### Tab 1: Training Metrics

**Purpose:** Monitor real-time training progress with loss and accuracy curves

**Plots Displayed:**

1. **Training & Validation Loss** (Blue/Red lines)
2. **Training & Validation Accuracy** (Green/Orange lines)

**Features:**

- **Auto-scaling Y-axis** - Adjusts to data range
- **Real-time Updates** - Every 1 second via WebSocket
- **Smoothing** - 10-point rolling average (configurable)
- **Hover Information** - Epoch, exact metric values
- **Legend Toggle** - Click legend items to show/hide series

**Interpreting the Plots:**

✅ **Good Training:**

- Loss decreases smoothly
- Accuracy increases steadily
- Validation metrics track training metrics closely
- No sudden spikes or divergence

⚠️ **Warning Signs:**

- Validation loss increases while training loss decreases (overfitting)
- Erratic fluctuations (learning rate too high)
- Flat curves (learning rate too low, or convergence)

**Data Source:**

- API: `GET /api/metrics?limit=100`
- WebSocket: `/ws/training` (type: `training_metrics`)

---

### Tab 2: Network Topology

**Purpose:** Visualize network architecture and connection weights

**Display Elements:**

1. **Input Nodes** (Green circles, left)
   - One node per input feature
   - Default: 2 nodes for (x, y) coordinates

2. **Hidden Nodes** (Blue circles, middle)
   - Cascade units added during training
   - Count increases as training progresses
   - Maximum: 8 in demo mode (configurable)

3. **Output Nodes** (Orange circles, right)
   - One node per output class
   - Default: 1 node for binary classification

4. **Connection Lines**
   - **Color Intensity** - Represents weight magnitude
   - **Red** - Negative weights
   - **Blue** - Positive weights
   - **Thickness** - Proportional to |weight| value

**Layout Algorithm:**

- **Spring Layout** - Nodes positioned by force-directed graph
- **Layered** - Input (layer 0) → Hidden (layer 1) → Output (layer 2)

**Interactive Features:**

- **Zoom** - Scroll to zoom in/out
- **Pan** - Click and drag to pan view
- **Hover** - Show node ID and connection details

**Data Source:**

- API: `GET /api/topology`
- WebSocket: `/ws/training` (type: `topology_update`)

**Example Topology Response:**

```json
{
  "input_units": 2,
  "hidden_units": 3,
  "output_units": 1,
  "nodes": [
    {"id": "input_0", "type": "input", "layer": 0},
    {"id": "input_1", "type": "input", "layer": 0},
    {"id": "hidden_0", "type": "hidden", "layer": 1},
    {"id": "hidden_1", "type": "hidden", "layer": 1},
    {"id": "hidden_2", "type": "hidden", "layer": 1},
    {"id": "output_0", "type": "output", "layer": 2}
  ],
  "connections": [
    {"from": "input_0", "to": "output_0", "weight": 0.234},
    {"from": "input_1", "to": "output_0", "weight": -0.156},
    {"from": "hidden_0", "to": "output_0", "weight": 0.678}
  ],
  "total_connections": 9
}
```

---

### Tab 3: Decision Boundaries

**Purpose:** Visualize how the network classifies the input space

**Display Components:**

1. **Contour Plot** (Background)
   - **Color Gradient** - Represents classification confidence
   - **Viridis Colorscale** - Purple (class 0) → Yellow (class 1)
   - **Resolution** - 100x100 grid (configurable)

2. **Data Points** (Scatter overlay)
   - **Color** - Actual class label
   - **Size** - Fixed (5 pixels)
   - **Opacity** - 70% for background visibility

**Interpreting the Visualization:**

✅ **Good Classification:**

- Clear separation between color regions
- Data points clustered in correct color regions
- Smooth decision boundaries

⚠️ **Poor Classification:**

- Mixed colors in data point regions
- Erratic, noisy boundaries
- Points in wrong color regions (misclassifications)

**Configuration Options** (app_config.yaml):

```yaml
frontend:
  decision_boundary:
    resolution: 100        # Grid resolution
    opacity: 0.7           # Contour opacity
    contour_levels: 20     # Number of contour lines
    color_scale: Viridis   # Colmar
    show_data_points: true
    show_misclassified: true
```

**Data Source:**

- API: `GET /api/decision_boundary`
- Computed on-demand from network forward pass

**Example Response:**

```json
{
  "xx": [[...], [...], ...],    // X-coordinate meshgrid
  "yy": [[...], [...], ...],    // Y-coordinate meshgrid
  "Z": [[...], [...], ...],     // Predictions (100x100)
  "bounds": {
    "x_min": -1.2,
    "x_max": 1.2,
    "y_min": -1.2,
    "y_max": 1.2
  }
}
```

---

### Tab 4: Dataset View

**Purpose:** Explore the training dataset structure and distribution

**Display Elements:**

1. **Scatter Plot** (2D data points)
   - **X-axis** - Feature 1 (e.g., x-coordinate)
   - **Y-axis** - Feature 2 (e.g., y-coordinate)
   - **Color** - Class label
   - **Marker Size** - 5 pixels

2. **Statistics Panel** (if enabled)
   - Sample count
   - Feature count
   - Class distribution

**Default Dataset (Demo Mode):**

- **Name:** Two-Class Spiral
- **Samples:** 200 (100 per class)
- **Features:** 2 (x, y coordinates)
- **Classes:** 2 (binary)
- **Noise:** Gaussian (σ=0.1)

**Supported Dataset Formats:**

- CSV (with header)
- JSON (array of objects)
- NumPy (.npy)
- HDF5 (.h5)

**Data Source:**

- API: `GET /api/dataset`

**Example Response:**

```json
{
  "inputs": [[0.12, 0.34], [-0.56, 0.78], ...],
  "targets": [0, 1, 0, 1, ...],
  "num_samples": 200,
  "num_features": 2,
  "num_classes": 2
}
```

---

## Configuration

### Configuration Files

**Primary Config:** `conf/app_config.yaml`

### Environment Variables

Override config values using `CASCOR_<SECTION>_<KEY>` format:

```bash
# Server configuration
export CASCOR_SERVER_PORT=8051
export CASCOR_SERVER_HOST=0.0.0.0

# Demo mode
export CASCOR_DEMO_MODE=1

# Backend path
export CASCOR_BACKEND_PATH=/custom/path/to/cascor

# Debug mode
export CASCOR_DEBUG=1
```

### Key Configuration Sections

#### Application Settings

```yaml
application:
  server:
    host: 127.0.0.1      # Server host (use 0.0.0.0 for external access)
    port: 8050           # Server port
    debug: true          # Debug mode (verbose logging)
```

#### Frontend Settings

```yaml
frontend:
  dashboard:
    update_interval_ms: 1000  # Fast update interval
    max_data_points: 10000    # Max points to display
    theme: plotly_dark        # Plot theme

  training_metrics:
    smoothing_window: 10      # Rolling average window
    buffer_size: 5000         # Metrics buffer size
```

#### Logging Settings

```yaml
logging:
  console:
    level: DEBUG         # Console log level (DEBUG, INFO, WARNING, ERROR)
    colored: true        # Colored output

  file:
    level: DEBUG         # File log level
    json_format: false   # JSON structured logs
```

### Applying Configuration Changes

1. **Edit config file:**

   ```bash
   nano conf/app_config.yaml
   ```

2. **Restart application:**

   ```bash
   ./demo  # or production command
   ```

3. **Verify changes:**
   - Check logs in `logs/system.log`
   - Observe dashboard behavior

---

## Troubleshooting

### Common Issues

#### 1. "No data available" in Dashboard Tabs

**Symptoms:**

- All tabs show "No data available"
- Metrics, topology, dataset views are empty

**Causes:**

- Demo mode not started
- WebSocket not connected
- API endpoint errors

**Solutions:**

✅ **Check demo mode is running:**

```bash
# In logs/system.log, look for:
"Demo mode started with simulated training"
"Demo training simulation started"
```

✅ **Verify WebSocket connection:**

- Check "WebSocket: 1 connection(s)" in dashboard header
- If "Disconnected", refresh browser page

✅ **Check API endpoints:**

```bash
curl http://127.0.0.1:8050/api/health
curl http://127.0.0.1:8050/api/metrics?limit=10
```

✅ **Review logs for errors:**

```bash
tail -f logs/system.log | grep -i error
```

---

#### 2. ModuleNotFoundError: No module named 'uvicorn'

**Symptoms:**

```bash
ModuleNotFoundError: No module named 'uvicorn'
```

**Cause:**

- Using system Python instead of conda environment

**Solutions:**

✅ **Use conda environment Python explicitly:**

```bash
/opt/miniforge3/envs/JuniperPython/bin/python main.py
```

✅ **Or activate environment first:**

```bash
conda activate JuniperPython
python main.py
```

✅ **Use demo script (automatically activates):**

```bash
./demo
```

---

#### 3. Port Already in Use

**Symptoms:**

```bash
Error: Address already in use: 127.0.0.1:8050
```

**Cause:**

- Another instance running on same port
- Previous instance didn't shut down cleanly

**Solutions:**

✅ **Find and kill existing process:**

```bash
# Find process using port 8050
lsof -i :8050

# Kill process
kill -9 <PID>
```

✅ **Use different port:**

```bash
export CASCOR_SERVER_PORT=8051
./demo
```

---

#### 4. Demo Mode Won't Stop

**Symptoms:**

- Ctrl+C doesn't stop application
- Training continues after stop button

**Cause:**

- Background thread not stopping cleanly

**Solutions:**

✅ **Force kill:**

```bash
# Find Python process
ps aux | grep python | grep main.py

# Kill
kill -9 <PID>
```

✅ **Check Event-based stopping:**

```python
# In demo_mode.py, verify:
while not self._stop.is_set():
    # ... work
```

---

#### 5. WebSocket Connection Failures

**Symptoms:**

- "WebSocket: Disconnected" in dashboard
- No real-time updates
- Browser console shows WebSocket errors

**Causes:**

- FastAPI event loop not set
- Network/firewall issues
- CORS configuration

**Solutions:**

✅ **Verify event loop setup (in logs):**

```text
"Event loop captured for thread-safe broadcasting"
```

✅ **Check browser console:**

```javascript
// Should see:
WebSocket connection to 'ws://127.0.0.1:8050/ws/training' opened
```

✅ **Test WebSocket manually:**

```javascript
// In browser console:
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');
ws.onopen = () => console.log('Connected');
ws.onmessage = (e) => console.log('Message:', e.data);
```

---

### Diagnostic Commands

**Check server health:**

```bash
curl http://127.0.0.1:8050/api/health
```

**Get current status:**

```bash
curl http://127.0.0.1:8050/api/status
```

**Get metrics:**

```bash
curl http://127.0.0.1:8050/api/metrics?limit=5
```

**View logs:**

```bash
# System logs
tail -f logs/system.log

# Training logs
tail -f logs/training.log

# UI logs
tail -f logs/ui.log
```

**Check processes:**

```bash
ps aux | grep -i cascor
ps aux | grep -i python.*main.py
```

---

## Advanced Features

### WebSocket Real-Time Updates

Juniper Canopy uses WebSocket push updates for real-time data streaming:

**Connection:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('Type:', msg.type, 'Data:', msg.data);
};
```

**Message Types:**

- `connection_established` - Initial connection confirmation
- `training_metrics` - Epoch metrics (loss, accuracy)
- `topology_update` - Network structure changes
- `cascade_add` - New hidden unit added
- `status` - Training status changes (paused, running, stopped)

**Latency:** <100ms for metric updates

---

### Custom Datasets

To use your own dataset in demo mode:

1. **Prepare data format:**

   ```python
   dataset = {
       "inputs": np.array([[x1, x2], [x1, x2], ...]),  # Shape: (N, 2)
       "targets": np.array([0, 1, 0, 1, ...]),         # Shape: (N,)
       "num_samples": N,
       "num_features": 2,
       "num_classes": 2
   }
   ```

2. **Modify demo_mode.py:**

   ```python
   def _generate_custom_dataset(self):
       # Load your data
       inputs = np.loadtxt('data/my_dataset.csv', delimiter=',')
       targets = np.loadtxt('data/my_labels.csv')

       return {
           "inputs": inputs,
           "targets": targets,
           # ... etc
       }
   ```

3. **Update initialization:**

   ```python
   self.dataset = self._generate_custom_dataset()
   ```

---

### Performance Tuning

**Reduce Update Frequency:**

```yaml
frontend:
  dashboard:
    update_interval_ms: 2000  # Slower updates (less CPU)
```

**Limit Data Points:**

```yaml
frontend:
  training_metrics:
    buffer_size: 1000  # Smaller buffer (less memory)
```

**Disable Features:**

```yaml
frontend:
  decision_boundary:
    enabled: false  # Skip boundary computation
```

---

### Export and Logging

**Training Logs:**

```bash
logs/training.log  # All training metrics
```

**System Logs:**

```bash
logs/system.log    # Application events
```

**UI Interaction Logs:**

```bash
logs/ui.log        # User interactions
```

**Log Rotation:**

- Daily rotation at midnight
- 30-day retention
- Automatic compression

---

## Getting Help

### Documentation

- [README.md](../README.md) - Quick start guide
- [API_REFERENCE.md](API_REFERENCE.md) - Complete API documentation
- [DEVELOPMENT_ROADMAP.md](../notes/DEVELOPMENT_ROADMAP.md) - Planned features
- [CHANGELOG.md](../CHANGELOG.md) - Release history

### Support

- **Issues:** Report bugs via GitHub Issues
- **Questions:** Check AGENTS.md for developer guidelines
- **Email:** <paul.calnon@example.com> (replace with actual contact)

### Version Information

**Current Version:** 1.0.0 (MVP)  
**Release Date:** October 2025  
**Python:** 3.11+  
**License:** MIT

---

## Appendix

### Keyboard Shortcuts

```markdown
*(Future feature - currently not implemented)*
```

### Glossary

- **CasCor** - Cascade Correlation neural network architecture
- **Epoch** - One complete pass through the training dataset
- **Cascade Unit** - Hidden unit added dynamically during training
- **Decision Boundary** - Regions where network changes classification
- **WebSocket** - Bidirectional real-time communication protocol
- **FastAPI** - Modern Python web framework for APIs
- **Dash** - Python framework for interactive web dashboards

### System Requirements

**Minimum:**

- Python 3.11+
- 2GB RAM
- Modern web browser (Chrome, Firefox, Safari, Edge)

**Recommended:**

- Python 3.12+
- 4GB RAM
- 2+ CPU cores
- Fast network connection (for remote access)

---

## End of User Manual
