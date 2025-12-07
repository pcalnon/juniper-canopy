# CasCor Backend Integration Reference

## Technical reference for CasCor backend integration in Juniper Canopy

**Version:** 0.4.0  
**Status:** ✅ PARTIALLY IMPLEMENTED  
**Last Updated:** November 7, 2025

---

## Module: cascor_integration.py

**Location:** `src/backend/cascor_integration.py`

**Purpose:** Integration layer between Juniper Canopy frontend and CasCor neural network backend.

---

## Class: CascorIntegration

### Constructor

```python
CascorIntegration(backend_path: Optional[str] = None)
```

**Description:** Initialize CasCor backend integration.

**Parameters:**

- `backend_path` (str, optional): Path to CasCor backend directory. If None, resolves from environment/config.

**Raises:**

- `FileNotFoundError`: If backend path doesn't exist

**Attributes:**

- `logger`: Logger instance
- `backend_path`: Resolved backend path (Path object)
- `network`: Current network instance
- `monitoring_active`: Boolean monitoring state
- `data_adapter`: DataAdapter instance
- `training_monitor`: TrainingMonitor instance

**Example:**

```python
# Use default path from config
integration = CascorIntegration()

# Or specify path
integration = CascorIntegration(backend_path="/path/to/cascor")
```

---

### Methods

#### create_network

```python
create_network(config: Optional[Dict[str, Any]] = None) -> Any
```

**Description:** Create new CascadeCorrelationNetwork instance with configuration.

**Parameters:**

- `config` (Dict, optional): Network configuration
  - `input_size` (int): Number of input features
  - `output_size` (int): Number of output features
  - `learning_rate` (float): Learning rate (default: 0.01)
  - `output_epochs` (int): Epochs for output training (default: 100)
  - `candidate_epochs` (int): Epochs for candidate training (default: 100)
  - `max_hidden_units` (int): Maximum hidden units (default: 10)

**Returns:**

- CascadeCorrelationNetwork instance

**Example:**

```python
network = integration.create_network({
    'input_size': 2,
    'output_size': 1,
    'learning_rate': 0.01,
    'output_epochs': 100
})
```

---

#### connect_to_network

```python
connect_to_network(network: Any) -> bool
```

**Description:** Connect to existing CascadeCorrelationNetwork instance.

**Parameters:**

- `network`: Existing network instance

**Returns:**

- `bool`: True if connection successful

**Example:**

```python
network = CascadeCorrelationNetwork(...)
integration.connect_to_network(network)
```

---

#### install_monitoring_hooks

```python
install_monitoring_hooks() -> bool
```

**Description:** Install monitoring hooks on network training methods.

**Wraps:**

- `network.fit()` - Main training loop
- `network.train_output_layer()` - Output training
- `network.train_candidates()` - Candidate training

**Returns:**

- `bool`: True if hooks installed successfully

**Example:**

```python
integration.install_monitoring_hooks()
# Now network.fit() will be monitored automatically
```

---

#### start_monitoring_thread

```python
start_monitoring_thread(interval: float = 1.0)
```

**Description:** Start background thread for network state polling.

**Parameters:**

- `interval` (float): Polling interval in seconds (default: 1.0)

**Example:**

```python
# Poll every 0.5 seconds
integration.start_monitoring_thread(interval=0.5)
```

---

#### stop_monitoring

```python
stop_monitoring()
```

**Description:** Stop background monitoring thread (idempotent).

**Example:**

```python
integration.stop_monitoring()
```

---

#### get_network_topology

```python
get_network_topology() -> Optional[Dict]
```

**Description:** Extract current network topology for visualization (thread-safe).

**Returns:**

- `Dict`: Network structure
  - `input_size` (int)
  - `output_size` (int)
  - `hidden_units` (List[Dict])
  - `output_weights` (List)
  - `output_bias` (List)

**Example:**

```python
topology = integration.get_network_topology()
print(f"Hidden units: {len(topology['hidden_units'])}")
```

**Hidden Unit Structure:**

```python
{
    'id': 0,
    'weights': [0.1, 0.2, ...],
    'bias': 0.5,
    'activation': 'sigmoid'
}
```

---

#### get_dataset_info

```python
get_dataset_info(
    x: Optional[torch.Tensor] = None,
    y: Optional[torch.Tensor] = None
) -> Optional[Dict[str, Any]]
```

**Description:** Get dataset information for visualization.

**Parameters:**

- `x` (Tensor, optional): Feature tensor
- `y` (Tensor, optional): Label tensor

**Returns:**

- `Dict`: Dataset information
  - `features` (List): 2D array of features
  - `labels` (List): 1D array of labels
  - `num_samples` (int)
  - `num_features` (int)
  - `num_classes` (int)
  - `class_distribution` (Dict)

**Example:**

```python
dataset_info = integration.get_dataset_info(x_train, y_train)
print(f"Samples: {dataset_info['num_samples']}")
```

---

#### get_prediction_function

```python
get_prediction_function() -> Optional[Callable]
```

**Description:** Get prediction function for decision boundary visualization.

**Returns:**

- `Callable`: Function that takes input (numpy/torch) and returns predictions

**Example:**

```python
predict_fn = integration.get_prediction_function()
predictions = predict_fn(x_test)
```

---

#### get_training_status

```python
get_training_status() -> Dict[str, Any]
```

**Description:** Get current training status.

**Returns:**

- `Dict`: Training status
  - `network_connected` (bool)
  - `monitoring_active` (bool)
  - `is_training` (bool)
  - `current_epoch` (int)
  - `current_loss` (float)
  - `current_accuracy` (float)
  - `input_size` (int)
  - `output_size` (int)
  - `hidden_units` (int)

**Example:**

```python
status = integration.get_training_status()
if status['is_training']:
    print(f"Training epoch {status['current_epoch']}")
```

---

#### create_monitoring_callback

```python
create_monitoring_callback(event_type: str, callback: Callable)
```

**Description:** Register callback for monitoring events.

**Parameters:**

- `event_type` (str): Event type
  - `'epoch_end'`
  - `'training_start'`
  - `'training_end'`
- `callback` (Callable): Callback function

**Example:**

```python
def on_epoch(epoch, loss, accuracy):
    print(f"Epoch {epoch}: {loss:.4f}")

integration.create_monitoring_callback('epoch_end', on_epoch)
```

---

#### shutdown

```python
shutdown()
```

**Description:** Clean up integration resources (idempotent).

**Performs:**

- Stop monitoring thread
- Restore original methods
- End training monitoring

**Example:**

```python
integration.shutdown()
```

---

## Configuration Reference

### Configuration File

**Location:** `conf/app_config.yaml`

```yaml
backend:
  cascor_integration:
    enabled: boolean (default: true)
    monitoring_hooks: boolean (default: true)
    state_polling_interval_ms: integer (default: 500)
    backend_path: string (default: "~/Development/python/JuniperCanopy/cascor")
```

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CASCOR_BACKEND_PATH` | string | `../cascor` | Backend path |
| `CASCOR_BACKEND_ENABLED` | bool | `true` | Enable integration |
| `CASCOR_MONITORING_HOOKS` | bool | `true` | Enable hooks |
| `CASCOR_DEMO_MODE` | bool | `false` | Force demo mode |

---

## Path Resolution

### Resolution Order

1. **Explicit parameter:** `CascorIntegration(backend_path="/path")`
2. **Environment variable:** `CASCOR_BACKEND_PATH`
3. **Configuration file:** `backend.cascor_integration.backend_path`
4. **Default:** `../cascor`

### Path Expansion

**Supported formats:**

```python
# Tilde expansion
"~/Development/cascor"  # → "/home/user/Development/cascor"

# Environment variables
"$HOME/cascor"          # → "/home/user/cascor"
"${HOME}/cascor"        # → "/home/user/cascor"

# Relative paths
"../cascor"             # → "/abs/path/to/cascor"
"../../cascor"          # → "/abs/path/cascor"

# Absolute paths
"/absolute/path/cascor" # → "/absolute/path/cascor"
```

---

## Event Broadcast Format

### Message Structure

```python
{
    "type": str,         # Event type
    "timestamp": str,    # ISO 8601 timestamp
    "data": Dict         # Event-specific data
}
```

### Event Types

#### training_start

```python
{
    "type": "training_start",
    "timestamp": "2025-11-05T12:00:00",
    "input_size": 2,
    "output_size": 1
}
```

#### training_complete

```python
{
    "type": "training_complete",
    "timestamp": "2025-11-05T12:05:00",
    "history": {
        "train_loss": [0.5, 0.3, 0.1],
        "train_accuracy": [0.6, 0.8, 0.95]
    },
    "hidden_units_added": 3
}
```

#### metrics_update

```python
{
    "type": "metrics_update",
    "timestamp": "2025-11-05T12:00:30",
    "epoch": 5,
    "train_loss": 0.2,
    "train_accuracy": 0.95,
    "hidden_units": 2
}
```

---

## Thread Safety

### Protected Operations

**With locks:**

- `get_network_topology()` - Uses `self.topology_lock`
- Network state access during monitoring

**Thread-safe by design:**

- Monitoring thread start/stop
- WebSocket broadcasting
- Metrics extraction

### Lock Usage

```python
# Internal implementation
with self.topology_lock:
    topology = extract_topology()
```

---

## Error Handling

### Exceptions

| Exception | Cause | Recovery |
|-----------|-------|----------|
| `FileNotFoundError` | Backend path invalid | Set correct path |
| `ImportError` | Backend modules missing | Fix CasCor installation |
| `AttributeError` | Network method missing | Check CasCor version |

### Fallback Behavior

**Backend not found:**

- Logs warning
- Application continues in demo mode

**Import failure:**

- Raises ImportError
- Application startup fails

**Network creation failure:**

- Logs error
- Returns None or raises exception

---

## Performance Considerations

### Monitoring Thread

**Default interval:** 1.0 second

**Tuning:**

- Faster updates: `0.5s` (higher CPU)
- Slower updates: `2.0s` (lower CPU)

**Recommendation:** 0.5-1.0s for real-time dashboards

### Topology Extraction

**Cost:** ~1-5ms per call  
**Frequency:** Only when requested  
**Optimization:** Cached in frontend

### WebSocket Broadcasting

**Latency:** <100ms  
**Throttling:** None (uses monitoring interval)

---

## Testing Reference

### Unit Tests

**Location:** `src/tests/unit/test_cascor_integration.py`

**Coverage:**

- Path resolution
- Network creation
- Hook installation
- Method wrapping
- Thread safety

### Integration Tests

**Location:** `src/tests/integration/test_cascor_backend.py`

**Coverage:**

- Backend connection
- Training with monitoring
- Real-time metrics
- Topology extraction

---

## Dependencies

### Python Modules

- `torch` - PyTorch for tensors
- `numpy` - Numerical operations
- `logging` - Logging
- `threading` - Background monitoring
- `pathlib` - Path operations

### CasCor Backend

**Required modules:**

- `cascade_correlation.cascade_correlation.CascadeCorrelationNetwork`
- `cascade_correlation.cascade_correlation_config.CascadeCorrelationConfig`

**Optional:**

- `cascade_correlation.cascade_correlation.TrainingResults`

---

## Additional Resources

- **[CASCOR_BACKEND_QUICK_START.md](CASCOR_BACKEND_QUICK_START.md)** - Quick setup guide
- **[CASCOR_BACKEND_MANUAL.md](CASCOR_BACKEND_MANUAL.md)** - Complete usage guide
- **[CasCor Backend](../cascor/README.md)** - CasCor prototype documentation
- **[AGENTS.md](AGENTS.md)** - Development guide

---

**Last Updated:** November 7, 2025  
**Version:** 0.4.0  
**Status:** ✅ PARTIALLY IMPLEMENTED

**Complete technical reference for CasCor backend integration!**
