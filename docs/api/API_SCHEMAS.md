# API Response Schemas

**Last Updated:** January 29, 2026  
**Version:** 1.1.0  
**Status:** Current

## Table of Contents

- [API Response Schemas](#api-response-schemas)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [REST API Endpoints](#rest-api-endpoints)
    - [GET /api/health](#get-apihealth)
    - [GET /api/status](#get-apistatus)
    - [GET /api/metrics](#get-apimetrics)
    - [GET /api/metrics/history](#get-apimetricshistory)
    - [GET /api/topology](#get-apitopology)
    - [GET /api/dataset](#get-apidataset)
    - [GET /api/decision\_boundary](#get-apidecision_boundary)
    - [GET /api/statistics](#get-apistatistics)
  - [Training Control Endpoints](#training-control-endpoints)
    - [POST /api/train/start](#post-apitrainstart)
    - [POST /api/train/pause](#post-apitrainpause)
    - [POST /api/train/resume](#post-apitrainresume)
    - [POST /api/train/stop](#post-apitrainstop)
    - [POST /api/train/reset](#post-apitrainreset)
    - [GET /api/train/status](#get-apitrainstatus)
  - [Remote Worker Endpoints](#remote-worker-endpoints)
    - [GET /api/remote/status](#get-apiremotestatus)
    - [POST /api/remote/connect](#post-apiremoteconnect)
    - [POST /api/remote/start\_workers](#post-apiremotestart_workers)
    - [POST /api/remote/stop\_workers](#post-apiremotestop_workers)
  - [WebSocket Endpoints](#websocket-endpoints)
    - [WS /ws/training](#ws-wstraining)
    - [WS /ws/control](#ws-wscontrol)
  - [Error Responses](#error-responses)
  - [Data Types](#data-types)
    - [Metric Naming Convention](#metric-naming-convention)
    - [Timestamp Format](#timestamp-format)
    - [Node ID Format](#node-id-format)
    - [Connection Format](#connection-format)
  - [Notes](#notes)

---

## Overview

This document provides complete request/response schema documentation for all Juniper Canopy API endpoints. All endpoints return JSON responses unless otherwise specified.

**Base URL:** `http://localhost:8050`  
**API Prefix:** `/api`  
**WebSocket Prefix:** `/ws`

---

## REST API Endpoints

### GET /api/health

Health check endpoint for monitoring application status.

**Response:**

```json
{
  "status": "healthy",
  "timestamp": 1699876543.123,
  "version": "1.6.0",
  "active_connections": 2,
  "training_active": true,
  "demo_mode": true
}
```

**Response Fields:**

- `status` (string): Always "healthy" if application is running
- `timestamp` (float): Unix timestamp in seconds
- `version` (string): Application version
- `active_connections` (integer): Number of active WebSocket connections
- `training_active` (boolean): Whether training is currently active
- `demo_mode` (boolean): Whether demo mode is active

**Status Codes:**

- `200`: Success

---

### GET /api/status

Get detailed training status and network information.

**Response (Demo Mode):**

```json
{
  "is_training": true,
  "current_epoch": 42,
  "current_loss": 0.234,
  "current_accuracy": 0.876,
  "network_connected": true,
  "monitoring_active": true,
  "input_size": 2,
  "output_size": 1,
  "hidden_units": 3,
  "current_phase": "demo_mode"
}
```

**Response (CasCor Backend):**

```json
{
  "is_training": true,
  "current_epoch": 100,
  "current_phase": "output_training",
  "network_connected": true,
  "monitoring_active": true,
  "hidden_units": 5
}
```

**Response (No Backend):**

```json
{
  "is_training": false,
  "network_connected": false,
  "monitoring_active": false
}
```

**Response Fields:**

- `is_training` (boolean): Whether training is active
- `current_epoch` (integer): Current training epoch
- `current_loss` (float): Most recent loss value
- `current_accuracy` (float): Most recent accuracy value
- `network_connected` (boolean): Whether backend is connected
- `monitoring_active` (boolean): Whether monitoring is active
- `input_size` (integer): Number of input features
- `output_size` (integer): Number of output units
- `hidden_units` (integer): Number of hidden units
- `current_phase` (string): Training phase identifier

**Status Codes:**

- `200`: Success

---

### GET /api/metrics

Get current training metrics snapshot.

**Response:**

```json
{
  "is_running": true,
  "is_paused": false,
  "current_epoch": 10,
  "current_loss": 0.45,
  "current_accuracy": 0.85,
  "val_loss": 0.48,
  "val_accuracy": 0.83,
  "hidden_units": 2,
  "metrics_count": 100,
  "phase": "output_training"
}
```

**Response Fields:**

- `is_running` (boolean): Whether training is running
- `is_paused` (boolean): Whether training is paused
- `current_epoch` (integer): Current epoch number
- `current_loss` (float): Current training loss
- `current_accuracy` (float): Current training accuracy
- `val_loss` (float): Current validation loss
- `val_accuracy` (float): Current validation accuracy
- `hidden_units` (integer): Number of hidden units
- `metrics_count` (integer): Total metrics collected
- `phase` (string): Current training phase

**Status Codes:**

- `200`: Success
- `503`: No backend available (returns empty object `{}`)

---

### GET /api/metrics/history

Get historical training metrics.

**Query Parameters:**

- `limit` (integer, optional): Maximum number of metrics to return (default: all)

**Response:**

```json
{
  "history": [
    {
      "epoch": 1,
      "metrics": {
        "loss": 0.9,
        "accuracy": 0.5,
        "val_loss": 0.95,
        "val_accuracy": 0.45
      },
      "network_topology": {
        "input_units": 2,
        "hidden_units": 0,
        "output_units": 1
      },
      "phase": "output_training",
      "timestamp": "2025-11-12T10:30:00"
    },
    {
      "epoch": 2,
      "metrics": {
        "loss": 0.8,
        "accuracy": 0.6,
        "val_loss": 0.85,
        "val_accuracy": 0.55
      },
      "network_topology": {
        "input_units": 2,
        "hidden_units": 0,
        "output_units": 1
      },
      "phase": "output_training",
      "timestamp": "2025-11-12T10:30:01"
    }
  ]
}
```

**Response Fields:**

- `history` (array): List of historical metric snapshots
  - `epoch` (integer): Epoch number
  - `metrics` (object): Training metrics
    - `loss` (float): Training loss
    - `accuracy` (float): Training accuracy
    - `val_loss` (float): Validation loss
    - `val_accuracy` (float): Validation accuracy
  - `network_topology` (object): Network structure
    - `input_units` (integer): Number of inputs
    - `hidden_units` (integer): Number of hidden units
    - `output_units` (integer): Number of outputs
  - `phase` (string): Training phase
  - `timestamp` (string): ISO 8601 timestamp

**Status Codes:**

- `200`: Success
- `503`: No backend available

**Error Response:**

```json
{
  "error": "No backend available"
}
```

---

### GET /api/topology

Get current network topology with nodes and connections.

**Response:**

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
    {"from": "input_0", "to": "output_0", "weight": 0.45},
    {"from": "input_1", "to": "output_0", "weight": -0.32},
    {"from": "input_0", "to": "hidden_0", "weight": 0.67},
    {"from": "input_1", "to": "hidden_0", "weight": 0.23},
    {"from": "hidden_0", "to": "output_0", "weight": 0.89},
    {"from": "hidden_0", "to": "hidden_1", "weight": 0.12},
    {"from": "hidden_1", "to": "output_0", "weight": -0.54}
  ],
  "total_connections": 7
}
```

**Response Fields:**

- `input_units` (integer): Number of input nodes
- `hidden_units` (integer): Number of hidden nodes
- `output_units` (integer): Number of output nodes
- `nodes` (array): List of network nodes
  - `id` (string): Unique node identifier (e.g., "input_0", "hidden_1", "output_0")
  - `type` (string): Node type ("input", "hidden", "output")
  - `layer` (integer): Layer index (0=input, 1=hidden, 2=output)
- `connections` (array): List of weighted connections
  - `from` (string): Source node ID
  - `to` (string): Target node ID
  - `weight` (float): Connection weight
- `total_connections` (integer): Total number of connections

**Status Codes:**

- `200`: Success

**Error Response:**

```json
{
  "error": "No topology available"
}
```

---

### GET /api/dataset

Get dataset information and samples.

**Response:**

```json
{
  "inputs": [[0.5, 0.3], [0.2, 0.8], [-0.3, 0.1]],
  "targets": [[0], [1], [0]],
  "num_samples": 300,
  "num_features": 2,
  "num_classes": 2
}
```

**Response Fields:**

- `inputs` (array): 2D array of input samples [num_samples × num_features]
- `targets` (array): 2D array of target labels [num_samples × num_outputs]
- `num_samples` (integer): Total number of samples
- `num_features` (integer): Number of input features
- `num_classes` (integer): Number of output classes

**Status Codes:**

- `200`: Success

**Error Response:**

```json
{
  "error": "No dataset available"
}
```

---

### GET /api/decision_boundary

Get decision boundary data for visualization.

**Response:**

```json
{
  "xx": [[0.0, 0.1, 0.2], [0.0, 0.1, 0.2]],
  "yy": [[0.0, 0.0, 0.0], [0.1, 0.1, 0.1]],
  "Z": [[0.2, 0.3, 0.5], [0.4, 0.6, 0.7]],
  "bounds": {
    "x_min": -1.5,
    "x_max": 1.5,
    "y_min": -1.5,
    "y_max": 1.5
  }
}
```

**Response Fields:**

- `xx` (array): 2D meshgrid x-coordinates [100 × 100]
- `yy` (array): 2D meshgrid y-coordinates [100 × 100]
- `Z` (array): 2D prediction values [100 × 100]
- `bounds` (object): Data bounds
  - `x_min` (float): Minimum x value
  - `x_max` (float): Maximum x value
  - `y_min` (float): Minimum y value
  - `y_max` (float): Maximum y value

**Status Codes:**

- `200`: Success

**Error Response:**

```json
{
  "error": "No decision boundary data available"
}
```

---

### GET /api/statistics

Get WebSocket connection statistics.

**Response:**

```json
{
  "active_connections": 3,
  "total_messages_sent": 1523,
  "total_messages_received": 87,
  "uptime_seconds": 3456.78
}
```

**Response Fields:**

- `active_connections` (integer): Number of active WebSocket connections
- `total_messages_sent` (integer): Total messages broadcast
- `total_messages_received` (integer): Total messages received from clients
- `uptime_seconds` (float): WebSocket manager uptime in seconds

**Status Codes:**

- `200`: Success

---

## Training Control Endpoints

### POST /api/train/start

Start training simulation.

**Query Parameters:**

- `reset` (boolean, optional): Whether to reset network before starting (default: false)

**Request Example:**

```http
POST /api/train/start?reset=true
```

**Response:**

```json
{
  "status": "started",
  "is_running": true,
  "is_paused": false,
  "current_epoch": 0,
  "current_loss": 0.0,
  "current_accuracy": 0.0,
  "hidden_units": 0
}
```

**Response Fields:**

- `status` (string): Operation status ("started")
- `is_running` (boolean): Training is now running
- `is_paused` (boolean): Training pause state
- `current_epoch` (integer): Current epoch (0 if reset)
- `current_loss` (float): Current loss
- `current_accuracy` (float): Current accuracy
- `hidden_units` (integer): Number of hidden units

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

### POST /api/train/pause

Pause training without losing state.

**Response:**

```json
{
  "status": "paused"
}
```

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

### POST /api/train/resume

Resume paused training.

**Response:**

```json
{
  "status": "running"
}
```

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

### POST /api/train/stop

Stop training completely.

**Response:**

```json
{
  "status": "stopped"
}
```

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

### POST /api/train/reset

Reset training to initial state.

**Response:**

```json
{
  "status": "reset",
  "is_running": false,
  "is_paused": false,
  "current_epoch": 0,
  "current_loss": 0.0,
  "current_accuracy": 0.0,
  "hidden_units": 0
}
```

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

### GET /api/train/status

Get current training status flags.

**Response:**

```json
{
  "is_training_in_progress": true,
  "stop_requested": false
}
```

**Response Fields:**

- `is_training_in_progress` (boolean): Whether training is currently running
- `stop_requested` (boolean): Whether a stop has been requested but not yet completed

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

## Remote Worker Endpoints

### GET /api/remote/status

Get remote worker connection status.

**Response:**

```json
{
  "connected": true,
  "address": "localhost:5000",
  "workers_active": 4
}
```

**Response (Not Connected):**

```json
{
  "connected": false,
  "address": null,
  "workers_active": 0
}
```

**Response Fields:**

- `connected` (boolean): Whether connected to remote worker manager
- `address` (string | null): Address of connected remote manager, or null if not connected
- `workers_active` (integer): Number of currently active workers

**Status Codes:**

- `200`: Success
- `503`: No backend available

---

### POST /api/remote/connect

Connect to a remote worker manager.

**Request:**

```json
{
  "address": "localhost:5000",
  "authkey": "optional-auth-key"
}
```

**Request Fields:**

- `address` (string, required): Address of the remote worker manager (host:port)
- `authkey` (string, optional): Authentication key for secure connection

**Response:**

```json
{
  "status": "connected",
  "address": "localhost:5000"
}
```

**Response Fields:**

- `status` (string): Connection status ("connected")
- `address` (string): Address of connected remote manager

**Status Codes:**

- `200`: Success
- `400`: Invalid address format
- `503`: No backend available or connection failed

---

### POST /api/remote/start_workers

Start remote worker processes.

**Request:**

```json
{
  "num_workers": 4
}
```

**Request Fields:**

- `num_workers` (integer, required): Number of worker processes to start

**Response:**

```json
{
  "status": "started",
  "workers_active": 4
}
```

**Response Fields:**

- `status` (string): Operation status ("started")
- `workers_active` (integer): Number of workers now active

**Status Codes:**

- `200`: Success
- `400`: Invalid number of workers
- `503`: No backend available or not connected to remote manager

---

### POST /api/remote/stop_workers

Stop remote worker processes.

**Request:**

```json
{
  "timeout": 30
}
```

**Request Fields:**

- `timeout` (integer, optional): Timeout in seconds for graceful shutdown (default: 30)

**Response:**

```json
{
  "status": "stopped",
  "workers_active": 0
}
```

**Response Fields:**

- `status` (string): Operation status ("stopped")
- `workers_active` (integer): Number of workers still active (should be 0)

**Status Codes:**

- `200`: Success
- `503`: No backend available or not connected to remote manager

---

## WebSocket Endpoints

### WS /ws/training

Real-time training metrics WebSocket endpoint.

**Connection:**

```javascript
const ws = new WebSocket('ws://localhost:8050/ws/training');
```

**Initial Message (Server → Client):**

```json
{
  "type": "initial_status",
  "data": {
    "is_running": true,
    "current_epoch": 42,
    "current_loss": 0.234,
    "current_accuracy": 0.876
  }
}
```

**Training Metrics Update (Server → Client):**

```json
{
  "type": "training_metrics",
  "data": {
    "epoch": 43,
    "loss": 0.221,
    "accuracy": 0.885,
    "val_loss": 0.245,
    "val_accuracy": 0.870
  }
}
```

**Topology Update (Server → Client):**

```json
{
  "type": "topology_update",
  "data": {
    "input_units": 2,
    "hidden_units": 3,
    "output_units": 1,
    "nodes": [...],
    "connections": [...]
  }
}
```

**Cascade Add Event (Server → Client):**

```json
{
  "type": "cascade_add",
  "data": {
    "hidden_unit_index": 3,
    "epoch": 50,
    "correlation": 0.678
  }
}
```

**Ping/Pong (Client → Server → Client):**

```json
// Client sends
{"type": "ping"}

// Server responds
{"type": "pong"}
```

---

### WS /ws/control

Training control WebSocket endpoint.

**Connection:**

```javascript
const ws = new WebSocket('ws://localhost:8050/ws/control');
```

**Connection Confirmation (Server → Client):**

Sent automatically upon connection.

```json
{
  "type": "connection_confirmed",
  "client_id": "control-client-12345"
}
```

**Start Command (Client → Server):**

```json
{
  "command": "start",
  "reset": true
}
```

**Start Response (Server → Client):**

```json
{
  "ok": true,
  "command": "start",
  "state": {
    "is_running": true,
    "current_epoch": 0,
    "current_loss": 0.0
  }
}
```

**Pause Command (Client → Server):**

```json
{
  "command": "pause"
}
```

**Pause Response (Server → Client):**

```json
{
  "ok": true,
  "command": "pause",
  "state": {
    "is_running": false,
    "is_paused": true,
    "current_epoch": 25
  }
}
```

**Resume Command (Client → Server):**

```json
{
  "command": "resume"
}
```

**Resume Response (Server → Client):**

```json
{
  "ok": true,
  "command": "resume",
  "state": {
    "is_running": true,
    "is_paused": false,
    "current_epoch": 25
  }
}
```

**Stop Command (Client → Server):**

```json
{
  "command": "stop"
}
```

**Stop Response (Server → Client):**

```json
{
  "ok": true,
  "command": "stop",
  "state": {
    "is_running": false,
    "current_epoch": 42
  }
}
```

**Reset Command (Client → Server):**

```json
{
  "command": "reset"
}
```

**Reset Response (Server → Client):**

```json
{
  "ok": true,
  "command": "reset",
  "state": {
    "is_running": false,
    "is_paused": false,
    "current_epoch": 0
  }
}
```

**Error Response (Server → Client):**

```json
{
  "ok": false,
  "error": "Unknown command: invalid_cmd"
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error message describing what went wrong"
}
```

Common HTTP status codes:

- `200`: Success
- `400`: Bad request (invalid parameters)
- `404`: Endpoint not found
- `500`: Internal server error
- `503`: Service unavailable (no backend available)

---

## Data Types

### Metric Naming Convention

All metrics follow snake_case naming:

- Training metrics: `loss`, `accuracy`
- Validation metrics: `val_loss`, `val_accuracy`
- Learning rate: `learning_rate`
- Epoch counter: `epoch`

### Timestamp Format

All timestamps use one of these formats:

- **Unix timestamp**: Float representing seconds since epoch (e.g., `1699876543.123`)
- **ISO 8601**: String in format `YYYY-MM-DDTHH:MM:SS` (e.g., `"2025-11-12T10:30:00"`)

### Node ID Format

Network node identifiers follow this pattern:

- Input nodes: `input_{index}` (e.g., `"input_0"`, `"input_1"`)
- Hidden nodes: `hidden_{index}` (e.g., `"hidden_0"`, `"hidden_1"`)
- Output nodes: `output_{index}` (e.g., `"output_0"`)

### Connection Format

Network connections are represented as:

```json
{
  "from": "source_node_id",
  "to": "target_node_id",
  "weight": 0.456
}
```

---

## Notes

- All numeric values (loss, accuracy, weights) are IEEE 754 floating-point numbers
- Arrays can be empty (`[]`) if no data is available
- Boolean fields are always `true` or `false` (never null)
- Missing optional fields may be omitted from responses
- WebSocket messages are always JSON-encoded strings
- Connection IDs are automatically generated and should not be relied upon for persistence

---

**See Also:**

- [API Reference](API_REFERENCE.md) - Complete API documentation
- [WebSocket Manager](../src/communication/websocket_manager.py) - WebSocket implementation
- [Demo Mode](../src/demo_mode.py) - Demo mode implementation
- [Main Application](../src/main.py) - Endpoint definitions
