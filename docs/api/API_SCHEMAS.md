# API Response Schemas

**Last Updated:** March 26, 2026  
**Version:** 1.2.0  
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

**Response (Demo Backend):**

```json
{
  "is_training": true,
  "is_running": true,
  "is_paused": false,
  "completed": false,
  "failed": false,
  "fsm_status": "STARTED",
  "phase": "output",
  "current_epoch": 42,
  "current_loss": 0.234,
  "current_accuracy": 0.876,
  "network_connected": true,
  "monitoring_active": true,
  "input_size": 2,
  "output_size": 1,
  "hidden_units": 3
}
```

**Response (Service Backend, normalized):**

```json
{
  "is_training": true,
  "is_running": true,
  "is_paused": false,
  "completed": false,
  "failed": false,
  "fsm_status": "STARTED",
  "phase": "output",
  "current_epoch": 42,
  "hidden_units": 3,
  "network_connected": true,
  "monitoring_active": true,
  "input_size": 2,
  "output_size": 3,
  "learning_rate": 0.01,
  "max_hidden_units": 10,
  "max_epochs": 500
}
```

**Response Fields:**

- `is_training` (boolean): Whether training is active
- `is_running` (boolean): Whether training is running
- `is_paused` (boolean): Whether training is paused
- `completed` (boolean): Whether training reached completion
- `failed` (boolean): Whether training failed
- `fsm_status` (string): Backend FSM status
- `phase` (string): Current phase (`idle`, `output`, `candidate`, ...)
- `current_epoch` (integer): Current training epoch
- `hidden_units` (integer): Number of hidden units
- `network_connected` (boolean): Whether backend/network is connected
- `monitoring_active` (boolean): Whether monitoring is active
- `input_size` (integer): Number of input features
- `output_size` (integer): Number of output units
- `learning_rate` (number, service mode): Active learning rate
- `max_hidden_units` (integer, service mode): Max hidden units parameter
- `max_epochs` (integer, service mode): Max epochs parameter

**Status Codes:**

- `200`: Success

### GET /api/metrics

Get current training metrics snapshot.

**Response (Demo Backend):**

```json
{
  "is_running": true,
  "is_paused": false,
  "current_epoch": 10,
  "current_loss": 0.45,
  "current_accuracy": 0.85,
  "hidden_units": 2,
  "metrics_count": 100
}
```

**Response (Service Backend, normalized):**

```json
{
  "epoch": 10,
  "train_loss": 0.45,
  "train_accuracy": 0.85,
  "val_loss": 0.48,
  "val_accuracy": 0.83,
  "hidden_units": 2,
  "phase": "output",
  "timestamp": 1711459200.123
}
```

**Status Codes:**

- `200`: Success

### GET /api/metrics/history

Get historical training metrics.

**Query Parameters:**

- `limit` (integer, optional): Maximum number of metrics to return (`0` means all available)

**Response:**

```json
{
  "history": [
    {
      "epoch": 1,
      "metrics": {
        "loss": 0.95,
        "accuracy": 0.38,
        "val_loss": 0.99,
        "val_accuracy": 0.35
      },
      "network_topology": {
        "input_units": 2,
        "hidden_units": 0,
        "output_units": 3
      },
      "phase": "output",
      "timestamp": "2026-03-26T18:30:00"
    },
    {
      "epoch": 2,
      "train_loss": 0.82,
      "train_accuracy": 0.51,
      "val_loss": 0.84,
      "val_accuracy": 0.49,
      "hidden_units": 0,
      "phase": "output",
      "timestamp": 1711459201.123
    }
  ]
}
```

**Notes:**

- Demo history entries use nested `metrics` and `network_topology` objects.
- Service history entries are normalized flat metric objects.

**Status Codes:**

- `200`: Success
- `422`: Invalid query parameter type

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
    {"id": "hidden_0", "type": "hidden", "label": "H0"},
    {"id": "output_0", "type": "output", "layer": 2}
  ],
  "connections": [
    {"from": "input_0", "to": "hidden_0", "weight": 0.45},
    {"from": "hidden_0", "to": "output_0", "weight": 0.89}
  ]
}
```

**Status Codes:**

- `200`: Success
- `503`: No topology available

### GET /api/dataset

Get dataset information.

**Response (Demo Backend):**

```json
{
  "inputs": [[0.5, 0.3], [0.2, 0.8], [-0.3, 0.1]],
  "targets": [[0], [1], [0]],
  "num_samples": 300,
  "num_features": 2,
  "num_classes": 2
}
```

**Response (Service Backend, normalized):**

```json
{
  "num_samples": 1000,
  "num_features": 2,
  "num_classes": 3,
  "loaded": true,
  "train_samples": 800,
  "test_samples": 200
}
```

**Status Codes:**

- `200`: Success
- `503`: No dataset available

### GET /api/decision_boundary

Get decision boundary data for visualization.

**Query Parameters:**

- `resolution` (integer, optional): Grid resolution per axis (`5..200`, clamped)

**Response:**

```json
{
  "xx": [[0.0, 0.1, 0.2], [0.0, 0.1, 0.2]],
  "yy": [[0.0, 0.0, 0.0], [0.1, 0.1, 0.1]],
  "Z": [[0, 0, 1], [0, 1, 1]],
  "x_min": -1.5,
  "x_max": 1.5,
  "y_min": -1.5,
  "y_max": 1.5,
  "resolution": 100
}
```

**Status Codes:**

- `200`: Success
- `503`: No decision boundary data available

### GET /api/statistics

Get WebSocket connection statistics.

**Response:**

```json
{
  "active_connections": 3,
  "total_messages_broadcast": 1523,
  "connections_info": [
    {
      "client_id": "training-client-12345",
      "connected_at": "2026-03-26T18:30:00",
      "messages_sent": 756,
      "last_message_at": "2026-03-26T18:45:00"
    }
  ]
}
```

**Response Fields:**

- `active_connections` (integer): Number of active WebSocket connections
- `total_messages_broadcast` (integer): Total messages broadcast
- `connections_info` (array): Per-connection metadata (`client_id`, `connected_at`, `messages_sent`, `last_message_at`)

**Status Codes:**

- `200`: Success

---

## Training Control Endpoints

### POST /api/train/start

Start training simulation.

**Query Parameters:**

- `reset` (boolean, optional): Whether to reset network before starting (default: false)

**Response (Demo Backend):**

```json
{
  "status": "started",
  "is_running": true,
  "is_paused": false,
  "current_epoch": 0,
  "current_loss": 1.0,
  "current_accuracy": 0.5,
  "hidden_units": 0,
  "metrics_count": 0
}
```

**Response (Service Backend):**

```json
{
  "status": "started",
  "ok": true,
  "is_training": true
}
```

**Status Codes:**

- `200`: Success

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

**Notes:**

- Response is an acknowledgement; check `GET /api/status` for authoritative backend state.

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

**Notes:**

- Response is an acknowledgement; check `GET /api/status` for authoritative backend state.

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

### POST /api/train/reset

Reset training to initial state.

**Response (Demo Backend):**

```json
{
  "status": "reset",
  "is_running": false,
  "is_paused": false,
  "current_epoch": 0,
  "current_loss": 1.0,
  "current_accuracy": 0.5,
  "hidden_units": 0,
  "metrics_count": 0
}
```

**Response (Service Backend):**

```json
{
  "status": "reset",
  "ok": true,
  "data": {
    "message": "reset requested"
  }
}
```

**Status Codes:**

- `200`: Success

### GET /api/train/status

Get current training status flags.

**Response:**

```json
{
  "backend": "service",
  "is_training": true,
  "is_running": true,
  "is_paused": false,
  "completed": false,
  "failed": false,
  "fsm_status": "STARTED",
  "phase": "output",
  "current_epoch": 42,
  "hidden_units": 3
}
```

**Response Fields:**

- `backend` (string): Active backend (`demo` or `service`)
- Remaining fields mirror `GET /api/status`

**Status Codes:**

- `200`: Success

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

**Initial Messages (Server -> Client):**

```json
{
  "type": "initial_status",
  "data": {
    "is_training": true,
    "is_running": true,
    "phase": "output",
    "current_epoch": 42
  }
}
```

```json
{
  "type": "state",
  "timestamp": 1711459200.123,
  "data": {
    "status": "Started",
    "phase": "Output",
    "current_epoch": 42
  }
}
```

**Metrics Update (Server -> Client):**

```json
{
  "type": "metrics",
  "timestamp": 1711459201.123,
  "data": {
    "epoch": 43,
    "metrics": {
      "loss": 0.221,
      "accuracy": 0.885,
      "val_loss": 0.245,
      "val_accuracy": 0.87
    }
  }
}
```

**Topology Update (Server -> Client):**

```json
{
  "type": "topology",
  "timestamp": 1711459201.456,
  "data": {
    "input_units": 2,
    "hidden_units": 3,
    "output_units": 1,
    "nodes": [],
    "connections": []
  }
}
```

**Event Update (Server -> Client):**

```json
{
  "type": "event",
  "timestamp": 1711459202.123,
  "data": {
    "event": "training_complete"
  }
}
```

**Ping/Pong (Client <-> Server):**

```json
{"type": "ping"}
```

```json
{"type": "pong"}
```

### WS /ws/control

Training control WebSocket endpoint.

**Connection:**

```javascript
const ws = new WebSocket('ws://localhost:8050/ws/control');
```

**Connection Confirmation (Server -> Client):**

```json
{
  "type": "connection_confirmed",
  "client_id": "control-client-12345"
}
```

**Command (Client -> Server):**

```json
{
  "command": "start",
  "reset": true
}
```

**Response (Server -> Client):**

```json
{
  "ok": true,
  "command": "start",
  "state": {
    "is_running": true,
    "current_epoch": 0
  }
}
```

**Error Response (Server -> Client):**

```json
{
  "ok": false,
  "error": "Unknown command: invalid_cmd"
}
```

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

History payloads support two valid metric shapes:

- Demo history shape: `metrics.loss`, `metrics.accuracy`, `metrics.val_loss`, `metrics.val_accuracy`
- Service history shape: `train_loss`, `train_accuracy`, `val_loss`, `val_accuracy`

Canopy normalizes service-side external CasCor fields (`loss`, `accuracy`, `validation_loss`, `validation_accuracy`) before returning service history/current metric snapshots.

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
