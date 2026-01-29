# Juniper Canopy API Reference

**Version:** 1.1.0  
**Last Updated:** January 29, 2026  
**Base URL:** `http://127.0.0.1:8050`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [REST API Endpoints](#rest-api-endpoints)
4. [Training Control Endpoints](#training-control-endpoints)
5. [Remote Worker Endpoints](#remote-worker-endpoints)
6. [WebSocket Channels](#websocket-channels)
7. [Data Models](#data-models)
8. [Error Handling](#error-handling)
9. [Rate Limiting](#rate-limiting)
10. [Code Examples](#code-examples)

---

## Overview

Juniper Canopy provides a RESTful HTTP API and WebSocket channels for real-time monitoring of Cascade Correlation neural network training.

### API Characteristics

- **Protocol:** HTTP/1.1, WebSocket (RFC 6455)
- **Data Format:** JSON
- **Encoding:** UTF-8
- **CORS:** Enabled for localhost origins
- **Rate Limiting:** None (currently)

### Base URL

**Local Development:**

```bash
http://127.0.0.1:8050
```

**Custom Port:**

```bash
export CASCOR_SERVER_PORT=8051
# Base URL: http://127.0.0.1:8051
```

### API Documentation (Interactive)

When server is running, visit:

```bash
http://127.0.0.1:8050/docs
```

This provides:

- Interactive API explorer (Swagger UI)
- Request/response schemas
- Try-it-out functionality

---

## Authentication

**Current Status:** No authentication required (MVP)

**Future Plans:** JWT-based authentication (optional)

```yaml
# conf/app_config.yaml (future)
security:
  authentication:
    enabled: true
    method: jwt
    token_expiry_hours: 24
```

---

## REST API Endpoints

### GET /

**Description:** Root endpoint, redirects to dashboard

**Response:**

- **Status:** 302 Found
- **Location:** `/dashboard/`

**Example:**

```bash
curl -I http://127.0.0.1:8050/
```

**Response Headers:**

```bash
HTTP/1.1 302 Found
Location: /dashboard/
```

---

### GET /api/health

**Description:** Health check endpoint for monitoring and load balancers

**Parameters:** None

**Response Schema:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "active_connections": 2,
  "training_active": true,
  "demo_mode": true
}
```

**Field Descriptions:**

- `status` (string) - Health status: `"healthy"` or `"unhealthy"`
- `version` (string) - Application version
- `active_connections` (integer) - Number of WebSocket connections
- `training_active` (boolean) - Whether training is in progress
- `demo_mode` (boolean) - Whether running in demo mode

**Status Codes:**

- `200 OK` - Service healthy
- `503 Service Unavailable` - Service unhealthy (future)

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/health
```

**Example Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "active_connections": 1,
  "training_active": true,
  "demo_mode": true
}
```

**Use Cases:**

- Docker health checks
- Load balancer health probes
- Monitoring dashboards (Prometheus, Grafana)

---

### GET /api/status

**Description:** Get current training status and network information

**Parameters:** None

**Response Schema (Demo Mode):**

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

**Response Schema (Production Mode):**

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
  "current_phase": "output_training"
}
```

**Field Descriptions:**

- `is_training` (boolean) - Training in progress
- `current_epoch` (integer) - Current epoch number
- `current_loss` (float) - Current training loss
- `current_accuracy` (float) - Current training accuracy
- `network_connected` (boolean) - Backend connection status
- `monitoring_active` (boolean) - Monitoring enabled
- `input_size` (integer) - Number of input nodes
- `output_size` (integer) - Number of output nodes
- `hidden_units` (integer) - Number of hidden cascade units
- `current_phase` (string) - Training phase: `"output_training"`, `"candidate_training"`, `"demo_mode"`, `"idle"`

**Status Codes:**

- `200 OK` - Status retrieved successfully

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/status
```

**Example Response:**

```json
{
  "is_training": true,
  "current_epoch": 15,
  "current_loss": 0.456,
  "current_accuracy": 0.789,
  "network_connected": true,
  "monitoring_active": true,
  "input_size": 2,
  "output_size": 1,
  "hidden_units": 2,
  "current_phase": "demo_mode"
}
```

---

### GET /api/metrics

**Description:** Get recent training metrics history

**Parameters:**

- `limit` (integer, optional) - Number of recent metrics to retrieve
  - Default: `100`
  - Range: `1` to `10000`

**Response Schema:**

```json
[
  {
    "epoch": 1,
    "metrics": {
      "loss": 0.987,
      "accuracy": 0.512,
      "val_loss": 1.023,
      "val_accuracy": 0.498
    },
    "network_topology": {
      "input_units": 2,
      "hidden_units": 0,
      "output_units": 1
    },
    "phase": "output",
    "timestamp": "2025-11-05T10:30:45.123456"
  },
  {
    "epoch": 2,
    "metrics": {
      "loss": 0.876,
      "accuracy": 0.567,
      "val_loss": 0.912,
      "val_accuracy": 0.534
    },
    "network_topology": {
      "input_units": 2,
      "hidden_units": 0,
      "output_units": 1
    },
    "phase": "candidate",
    "timestamp": "2025-11-05T10:30:46.234567"
  }
]
```

**Field Descriptions:**

- `epoch` (integer) - Epoch number
- `metrics` (object) - Metric values for this epoch
  - `loss` (float) - Training loss
  - `accuracy` (float) - Training accuracy (0.0 to 1.0)
  - `val_loss` (float) - Validation loss
  - `val_accuracy` (float) - Validation accuracy (0.0 to 1.0)
- `network_topology` (object) - Network structure at this epoch
  - `input_units` (integer) - Input node count
  - `hidden_units` (integer) - Hidden unit count
  - `output_units` (integer) - Output node count
- `phase` (string) - Training phase: `"output"`, `"candidate"`, `"demo_mode"`
- `timestamp` (string) - ISO 8601 timestamp

**Status Codes:**

- `200 OK` - Metrics retrieved successfully
- `400 Bad Request` - Invalid `limit` parameter

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/metrics?limit=5
```

**Example Response:**

```json
[
  {
    "epoch": 1,
    "metrics": {
      "loss": 0.987,
      "accuracy": 0.512,
      "val_loss": 1.023,
      "val_accuracy": 0.498
    },
    "network_topology": {
      "input_units": 2,
      "hidden_units": 0,
      "output_units": 1
    },
    "phase": "output",
    "timestamp": "2025-11-05T10:30:45.123456"
  }
]
```

**Notes:**

- Returns empty array `[]` if no metrics available
- Metrics ordered by epoch (oldest first)
- Use WebSocket `/ws/training` for real-time streaming

---

### GET /api/topology

**Description:** Get current network topology (nodes and connections)

**Parameters:** None

**Response Schema:**

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
    {"from": "hidden_0", "to": "output_0", "weight": 0.678},
    {"from": "hidden_1", "to": "output_0", "weight": -0.421},
    {"from": "hidden_2", "to": "output_0", "weight": 0.112}
  ],
  "total_connections": 5
}
```

**Field Descriptions:**

- `input_units` (integer) - Number of input nodes
- `hidden_units` (integer) - Number of hidden cascade units
- `output_units` (integer) - Number of output nodes
- `nodes` (array) - List of all network nodes
  - `id` (string) - Unique node identifier (e.g., `"input_0"`, `"hidden_1"`)
  - `type` (string) - Node type: `"input"`, `"hidden"`, `"output"`
  - `layer` (integer) - Layer number (0=input, 1=hidden, 2=output)
- `connections` (array) - List of all network connections
  - `from` (string) - Source node ID
  - `to` (string) - Target node ID
  - `weight` (float) - Connection weight value
- `total_connections` (integer) - Total number of connections

**Status Codes:**

- `200 OK` - Topology retrieved successfully
- `404 Not Found` - No topology available (network not initialized)

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/topology
```

**Example Response:**

```json
{
  "input_units": 2,
  "hidden_units": 2,
  "output_units": 1,
  "nodes": [
    {"id": "input_0", "type": "input", "layer": 0},
    {"id": "input_1", "type": "input", "layer": 0},
    {"id": "hidden_0", "type": "hidden", "layer": 1},
    {"id": "hidden_1", "type": "hidden", "layer": 1},
    {"id": "output_0", "type": "output", "layer": 2}
  ],
  "connections": [
    {"from": "input_0", "to": "output_0", "weight": 0.123},
    {"from": "input_1", "to": "output_0", "weight": -0.456},
    {"from": "hidden_0", "to": "output_0", "weight": 0.789},
    {"from": "hidden_1", "to": "output_0", "weight": -0.234}
  ],
  "total_connections": 4
}
```

**Notes:**

- Topology updates when cascade units are added
- Use WebSocket `/ws/training` (type: `topology_update`) for real-time updates

---

### GET /api/dataset

**Description:** Get dataset information and data points

**Parameters:** None

**Response Schema:**

```json
{
  "inputs": [
    [0.12, 0.34],
    [-0.56, 0.78],
    [0.91, -0.23]
  ],
  "targets": [0, 1, 0],
  "num_samples": 200,
  "num_features": 2,
  "num_classes": 2
}
```

**Field Descriptions:**

- `inputs` (array) - Input feature vectors (shape: `[num_samples, num_features]`)
- `targets` (array) - Target labels (shape: `[num_samples]`)
- `num_samples` (integer) - Total number of samples
- `num_features` (integer) - Number of input features
- `num_classes` (integer) - Number of output classes

**Status Codes:**

- `200 OK` - Dataset retrieved successfully
- `404 Not Found` - No dataset available

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/dataset
```

**Example Response:**

```json
{
  "inputs": [[0.12, 0.34], [-0.56, 0.78]],
  "targets": [0, 1],
  "num_samples": 200,
  "num_features": 2,
  "num_classes": 2
}
```

**Notes:**

- Demo mode uses spiral dataset (200 samples)
- Data returned as raw arrays (no pagination currently)
- Large datasets may cause slow response times

---

### GET /api/decision_boundary

**Description:** Get decision boundary data for visualization

**Parameters:** None

**Response Schema:**

```json
{
  "xx": [[...], [...], ...],
  "yy": [[...], [...], ...],
  "Z": [[...], [...], ...],
  "bounds": {
    "x_min": -1.2,
    "x_max": 1.2,
    "y_min": -1.2,
    "y_max": 1.2
  }
}
```

**Field Descriptions:**

- `xx` (array) - X-coordinate meshgrid (shape: `[resolution, resolution]`)
- `yy` (array) - Y-coordinate meshgrid (shape: `[resolution, resolution]`)
- `Z` (array) - Predicted class probabilities at each grid point (shape: `[resolution, resolution]`)
- `bounds` (object) - Data bounds used for grid generation
  - `x_min` (float) - Minimum X value
  - `x_max` (float) - Maximum X value
  - `y_min` (float) - Minimum Y value
  - `y_max` (float) - Maximum Y value

**Status Codes:**

- `200 OK` - Decision boundary computed successfully
- `404 Not Found` - No decision boundary available (network not trained)
- `500 Internal Server Error` - Computation failed

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/decision_boundary
```

**Example Response (truncated):**

```json
{
  "xx": [[−1.2, −1.18, ...], [−1.2, −1.18, ...]],
  "yy": [[−1.2, −1.2, ...], [−1.18, −1.18, ...]],
  "Z": [[0.12, 0.15, ...], [0.18, 0.21, ...]],
  "bounds": {
    "x_min": -1.2,
    "x_max": 1.2,
    "y_min": -1.2,
    "y_max": 1.2
  }
}
```

**Notes:**

- Computed on-demand (not cached)
- Resolution: 100x100 grid (configurable in `app_config.yaml`)
- Computationally expensive for large networks
- Only available for 2D input spaces

**Configuration:**

```yaml
frontend:
  decision_boundary:
    resolution: 100  # Grid resolution (higher = more detail, slower)
```

---

### GET /api/statistics

**Description:** Get WebSocket connection statistics

**Parameters:** None

**Response Schema:**

```json
{
  "active_connections": 2,
  "total_messages_broadcast": 1523,
  "connections_info": [
    {
      "client_id": "training-client-12345",
      "connected_at": "2025-11-05T10:30:00.123456",
      "messages_sent": 756,
      "last_message_at": "2025-11-05T10:45:23.987654"
    }
  ]
}
```

**Field Descriptions:**

- `active_connections` (integer) - Current active WebSocket connections
- `total_messages_broadcast` (integer) - Total messages broadcast since startup
- `connections_info` (array) - Detailed information per connection
  - `client_id` (string) - Client identifier
  - `connected_at` (string) - ISO 8601 connection timestamp
  - `messages_sent` (integer) - Messages sent to this client
  - `last_message_at` (string) - ISO 8601 timestamp of last message

**Status Codes:**

- `200 OK` - Statistics retrieved successfully

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/statistics
```

**Example Response:**

```json
{
  "active_connections": 1,
  "total_messages_broadcast": 42,
  "connections_info": [
    {
      "client_id": "training-client-123",
      "connected_at": "2025-11-05T10:30:00.000000",
      "messages_sent": 42,
      "last_message_at": "2025-11-05T10:30:42.000000"
    }
  ]
}
```

---

## Training Control Endpoints

### POST /api/train/start

**Description:** Start training (with optional reset)

**Parameters:**

- `reset` (boolean, query, optional) - Reset network before starting (default: `false`)

**Response Schema (Success):**

```json
{
  "status": "started",
  "is_running": true,
  "is_paused": false,
  "current_epoch": 0,
  "current_loss": 1.0,
  "current_accuracy": 0.5,
  "hidden_units": 0
}
```

**Status Codes:**

- `200 OK` - Training started successfully
- `400 Bad Request` - No network configured (cascor backend)
- `500 Internal Server Error` - Failed to start training
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST "http://127.0.0.1:8050/api/train/start?reset=true"
```

---

### POST /api/train/pause

**Description:** Pause training (preserves state)

> **Note:** Currently only works in demo mode. Cascor backend does not support pause.

**Parameters:** None

**Response Schema:**

```json
{
  "status": "paused"
}
```

**Status Codes:**

- `200 OK` - Training paused successfully
- `503 Service Unavailable` - No backend available (or pause not supported)

**Example Request:**

```bash
curl -X POST http://127.0.0.1:8050/api/train/pause
```

---

### POST /api/train/resume

**Description:** Resume paused training

> **Note:** Currently only works in demo mode. Cascor backend does not support resume.

**Parameters:** None

**Response Schema:**

```json
{
  "status": "running"
}
```

**Status Codes:**

- `200 OK` - Training resumed successfully
- `503 Service Unavailable` - No backend available (or resume not supported)

**Example Request:**

```bash
curl -X POST http://127.0.0.1:8050/api/train/resume
```

---

### POST /api/train/stop

**Description:** Stop training

**Parameters:** None

**Response Schema (Demo Mode):**

```json
{
  "status": "stopped"
}
```

**Response Schema (Cascor Backend):**

```json
{
  "status": "stop_requested",
  "message": "Training stop requested (best-effort)"
}
```

**Status Codes:**

- `200 OK` - Training stopped or stop requested
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST http://127.0.0.1:8050/api/train/stop
```

**Notes:**

- Demo mode: Immediate stop
- Cascor backend: Best-effort stop request (training may complete current epoch)

---

### POST /api/train/reset

**Description:** Reset training state

**Parameters:** None

**Response Schema:**

```json
{
  "status": "reset",
  "is_running": false,
  "is_paused": false,
  "current_epoch": 0,
  "current_loss": 1.0,
  "current_accuracy": 0.5,
  "hidden_units": 0
}
```

**Status Codes:**

- `200 OK` - Training reset successfully
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST http://127.0.0.1:8050/api/train/reset
```

---

### GET /api/train/status

**Description:** Get current training status (whether training is in progress)

**Parameters:** None

**Response Schema (Demo Mode):**

```json
{
  "backend": "demo",
  "is_running": true,
  "is_paused": false,
  "current_epoch": 42,
  "current_loss": 0.234,
  "current_accuracy": 0.876,
  "hidden_units": 3
}
```

**Response Schema (Cascor Backend):**

```json
{
  "backend": "cascor",
  "training_in_progress": true,
  "stop_requested": false,
  "current_epoch": 42,
  "current_loss": 0.234,
  "current_accuracy": 0.876,
  "hidden_units": 3
}
```

**Response Schema (No Backend):**

```json
{
  "backend": null,
  "status": "no_backend"
}
```

**Field Descriptions:**

- `backend` (string|null) - Active backend: `"demo"`, `"cascor"`, or `null`
- `training_in_progress` (boolean) - Whether training is currently running (cascor)
- `stop_requested` (boolean) - Whether a stop has been requested (cascor)
- `is_running` (boolean) - Training running state (demo)
- `is_paused` (boolean) - Training paused state (demo)
- `current_epoch` (integer) - Current epoch number
- `current_loss` (float) - Current training loss
- `current_accuracy` (float) - Current training accuracy
- `hidden_units` (integer) - Number of hidden cascade units

**Status Codes:**

- `200 OK` - Status retrieved successfully

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/train/status
```

---

## Remote Worker Endpoints

These endpoints manage distributed training via the RemoteWorkerClient.

> **Note:** Remote worker endpoints require the Cascor backend. They are not available in demo mode.

### GET /api/remote/status

**Description:** Get remote worker connection status

**Parameters:** None

**Response Schema (Connected):**

```json
{
  "available": true,
  "connected": true,
  "workers_active": true,
  "num_workers": 4,
  "address": "192.168.1.100:5000"
}
```

**Response Schema (Not Connected):**

```json
{
  "available": true,
  "connected": false,
  "workers_active": false
}
```

**Response Schema (No Backend):**

```json
{
  "available": false,
  "connected": false,
  "workers_active": false,
  "error": "No backend"
}
```

**Field Descriptions:**

- `available` (boolean) - Whether remote worker functionality is available
- `connected` (boolean) - Whether connected to a remote manager
- `workers_active` (boolean) - Whether workers are currently running
- `num_workers` (integer, optional) - Number of active workers
- `address` (string, optional) - Remote manager address
- `error` (string, optional) - Error message if unavailable

**Status Codes:**

- `200 OK` - Status retrieved successfully

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/remote/status
```

---

### POST /api/remote/connect

**Description:** Connect to a remote CandidateTrainingManager

**Parameters:**

- `host` (string, query, required) - Remote manager host address
- `port` (integer, query, required) - Remote manager port
- `authkey` (string, query, required) - Authentication key for secure connection

**Response Schema (Success):**

```json
{
  "status": "connected",
  "address": "192.168.1.100:5000"
}
```

**Status Codes:**

- `200 OK` - Connected successfully
- `500 Internal Server Error` - Connection failed
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST "http://127.0.0.1:8050/api/remote/connect?host=192.168.1.100&port=5000&authkey=secret123"
```

---

### POST /api/remote/start_workers

**Description:** Start remote worker processes

**Parameters:**

- `num_workers` (integer, query, optional) - Number of workers to start (default: `1`)

**Response Schema (Success):**

```json
{
  "status": "started",
  "num_workers": 4
}
```

**Status Codes:**

- `200 OK` - Workers started successfully
- `500 Internal Server Error` - Failed to start workers
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST "http://127.0.0.1:8050/api/remote/start_workers?num_workers=4"
```

---

### POST /api/remote/stop_workers

**Description:** Stop remote worker processes

**Parameters:**

- `timeout` (integer, query, optional) - Timeout for graceful shutdown in seconds (default: `10`)

**Response Schema (Success):**

```json
{
  "status": "stopped"
}
```

**Status Codes:**

- `200 OK` - Workers stopped successfully
- `500 Internal Server Error` - Failed to stop workers
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST "http://127.0.0.1:8050/api/remote/stop_workers?timeout=30"
```

---

### POST /api/remote/disconnect

**Description:** Disconnect from remote manager

**Parameters:** None

**Response Schema (Success):**

```json
{
  "status": "disconnected"
}
```

**Status Codes:**

- `200 OK` - Disconnected successfully
- `500 Internal Server Error` - Failed to disconnect
- `503 Service Unavailable` - No backend available

**Example Request:**

```bash
curl -X POST http://127.0.0.1:8050/api/remote/disconnect
```

---

## WebSocket Channels

### Connection URL Format

```bash
ws://127.0.0.1:8050/ws/<channel>
```

### Common Message Format

All WebSocket messages follow this structure:

```json
{
  "type": "message_type",
  "data": { ... },
  "timestamp": "2025-11-05T10:30:45.123456"
}
```

**Fields:**

- `type` (string) - Message type identifier
- `data` (object) - Message payload (varies by type)
- `timestamp` (string) - ISO 8601 timestamp (UTC)

---

### WS /ws/training

**Description:** Real-time training metrics and updates stream

**Connection:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');
```

**Message Types (Server → Client):**

#### 1. connection_established

**Description:** Sent immediately upon connection

**Payload:**

```json
{
  "type": "connection_established",
  "client_id": "training-client-12345",
  "server_time": "2025-11-05T10:30:00.123456",
  "timestamp": "2025-11-05T10:30:00.123456"
}
```

**Fields:**

- `client_id` (string) - Assigned client identifier
- `server_time` (string) - Server timestamp

---

#### 2. initial_status

**Description:** Current training status (sent after connection)

**Payload:**

```json
{
  "type": "initial_status",
  "data": {
    "is_running": true,
    "is_paused": false,
    "current_epoch": 15,
    "current_loss": 0.456,
    "current_accuracy": 0.789,
    "hidden_units": 2,
    "metrics_count": 15
  },
  "timestamp": "2025-11-05T10:30:00.234567"
}
```

**Fields:**

- `is_running` (boolean) - Training active
- `is_paused` (boolean) - Training paused
- `current_epoch` (integer) - Current epoch
- `current_loss` (float) - Latest loss value
- `current_accuracy` (float) - Latest accuracy
- `hidden_units` (integer) - Current hidden unit count
- `metrics_count` (integer) - Total metrics logged

---

#### 3. training_metrics

**Description:** Training metrics update (sent every epoch)

**Payload:**

```json
{
  "type": "training_metrics",
  "data": {
    "epoch": 42,
    "metrics": {
      "loss": 0.234,
      "accuracy": 0.876,
      "val_loss": 0.256,
      "val_accuracy": 0.854
    },
    "network_topology": {
      "input_units": 2,
      "hidden_units": 3,
      "output_units": 1
    },
    "phase": "output",
    "timestamp": "2025-11-05T10:30:42.123456"
  },
  "timestamp": "2025-11-05T10:30:42.123456"
}
```

**Fields:**

- `epoch` (integer) - Epoch number
- `metrics` (object) - Metric values
- `network_topology` (object) - Current network structure
- `phase` (string) - Training phase

**Frequency:** Every epoch (~1 second in demo mode)

---

#### 4. topology_update

**Description:** Network topology changed (new cascade unit added)

**Payload:**

```json
{
  "type": "topology_update",
  "data": {
    "input_units": 2,
    "hidden_units": 4,
    "output_units": 1,
    "nodes": [...],
    "connections": [...],
    "total_connections": 12
  },
  "timestamp": "2025-11-05T10:30:30.123456"
}
```

**Fields:** Same as `GET /api/topology`

**Frequency:** On cascade unit addition (~every 30 epochs in demo mode)

---

#### 5. cascade_add

**Description:** New cascade unit added to network

**Payload:**

```json
{
  "type": "cascade_add",
  "data": {
    "unit_index": 2,
    "total_hidden_units": 3,
    "epoch": 60
  },
  "timestamp": "2025-11-05T10:31:00.123456"
}
```

**Fields:**

- `unit_index` (integer) - Index of added unit
- `total_hidden_units` (integer) - Total hidden units after addition
- `epoch` (integer) - Epoch at which unit was added

---

#### 6. status

**Description:** Training status change (paused, resumed, stopped, reset)

**Payload:**

```json
{
  "type": "status",
  "data": {
    "status": "paused",
    "is_running": true,
    "is_paused": true,
    "current_epoch": 25,
    "current_loss": 0.345,
    "current_accuracy": 0.812
  },
  "timestamp": "2025-11-05T10:30:15.123456"
}
```

**Fields:**

- `status` (string) - Status change: `"running"`, `"paused"`, `"stopped"`, `"reset"`
- Other fields same as `initial_status`

---

#### 7. ping

**Description:** Heartbeat message (keep-alive)

**Payload:**

```json
{
  "type": "ping",
  "timestamp": "2025-11-05T10:30:00.123456"
}
```

**Response (Client → Server):**

```json
{
  "type": "pong",
  "timestamp": "2025-11-05T10:30:00.234567"
}
```

---

**Example JavaScript Client:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');

ws.onopen = () => {
  console.log('Connected to training stream');
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('Message type:', msg.type);

  switch (msg.type) {
    case 'connection_established':
      console.log('Client ID:', msg.client_id);
      break;
    case 'training_metrics':
      console.log('Epoch:', msg.data.epoch);
      console.log('Loss:', msg.data.metrics.loss);
      break;
    case 'cascade_add':
      console.log('New hidden unit added:', msg.data.unit_index);
      break;
    case 'ping':
      ws.send(JSON.stringify({ type: 'pong' }));
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from training stream');
};
```

---

### WS /ws/control

**Description:** Training control command channel (bidirectional)

**Connection:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/control');
```

**Message Types (Client → Server):**

#### 1. start

**Description:** Start training (with optional reset)

**Request:**

```json
{
  "command": "start",
  "reset": true
}
```

**Fields:**

- `command` (string) - Must be `"start"`
- `reset` (boolean, optional) - Reset state before starting (default: `true`)

**Response:**

```json
{
  "ok": true,
  "command": "start",
  "state": {
    "is_running": true,
    "is_paused": false,
    "current_epoch": 0,
    "current_loss": 1.0,
    "current_accuracy": 0.5,
    "hidden_units": 0,
    "metrics_count": 0
  }
}
```

---

#### 2. stop

**Description:** Stop training

**Request:**

```json
{
  "command": "stop"
}
```

**Response:**

```json
{
  "ok": true,
  "command": "stop",
  "state": {
    "is_running": false,
    "is_paused": false,
    "current_epoch": 42,
    "current_loss": 0.234,
    "current_accuracy": 0.876,
    "hidden_units": 3,
    "metrics_count": 42
  }
}
```

---

#### 3. pause

**Description:** Pause training (preserves state)

**Request:**

```json
{
  "command": "pause"
}
```

**Response:**

```json
{
  "ok": true,
  "command": "pause",
  "state": {
    "is_running": true,
    "is_paused": true,
    "current_epoch": 25,
    "current_loss": 0.345,
    "current_accuracy": 0.812,
    "hidden_units": 2,
    "metrics_count": 25
  }
}
```

---

#### 4. resume

**Description:** Resume paused training

**Request:**

```json
{
  "command": "resume"
}
```

**Response:**

```json
{
  "ok": true,
  "command": "resume",
  "state": {
    "is_running": true,
    "is_paused": false,
    "current_epoch": 25,
    "current_loss": 0.345,
    "current_accuracy": 0.812,
    "hidden_units": 2,
    "metrics_count": 25
  }
}
```

---

#### 5. reset

**Description:** Reset training state

**Request:**

```json
{
  "command": "reset"
}
```

**Response:**

```json
{
  "ok": true,
  "command": "reset",
  "state": {
    "is_running": false,
    "is_paused": false,
    "current_epoch": 0,
    "current_loss": 1.0,
    "current_accuracy": 0.5,
    "hidden_units": 0,
    "metrics_count": 0
  }
}
```

---

**Error Response:**

```json
{
  "ok": false,
  "error": "Unknown command: invalid_cmd"
}
```

---

**Example JavaScript Client:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/control');

ws.onopen = () => {
  console.log('Control channel connected');

  // Start training
  ws.send(JSON.stringify({
    command: 'start',
    reset: true
  }));
};

ws.onmessage = (event) => {
  const response = JSON.parse(event.data);

  if (response.ok) {
    console.log('Command succeeded:', response.command);
    console.log('State:', response.state);
  } else {
    console.error('Command failed:', response.error);
  }
};

// Send pause command
function pauseTraining() {
  ws.send(JSON.stringify({ command: 'pause' }));
}

// Send resume command
function resumeTraining() {
  ws.send(JSON.stringify({ command: 'resume' }));
}

// Send stop command
function stopTraining() {
  ws.send(JSON.stringify({ command: 'stop' }));
}

// Send reset command
function resetTraining() {
  ws.send(JSON.stringify({ command: 'reset' }));
}
```

---

## Data Models

### TrainingMetrics

```typescript
interface TrainingMetrics {
  epoch: number;
  metrics: {
    loss: number;
    accuracy: number;
    val_loss: number;
    val_accuracy: number;
  };
  network_topology: {
    input_units: number;
    hidden_units: number;
    output_units: number;
  };
  phase: "output" | "candidate" | "demo_mode";
  timestamp: string; // ISO 8601
}
```

---

### NetworkTopology

```typescript
interface NetworkTopology {
  input_units: number;
  hidden_units: number;
  output_units: number;
  nodes: Node[];
  connections: Connection[];
  total_connections: number;
}

interface Node {
  id: string; // e.g., "input_0", "hidden_1", "output_0"
  type: "input" | "hidden" | "output";
  layer: number; // 0=input, 1=hidden, 2=output
}

interface Connection {
  from: string; // Source node ID
  to: string;   // Target node ID
  weight: number;
}
```

---

### Dataset

```typescript
interface Dataset {
  inputs: number[][];  // Shape: [num_samples, num_features]
  targets: number[];   // Shape: [num_samples]
  num_samples: number;
  num_features: number;
  num_classes: number;
}
```

---

### DecisionBoundary

```typescript
interface DecisionBoundary {
  xx: number[][];  // X-coordinate meshgrid [resolution, resolution]
  yy: number[][];  // Y-coordinate meshgrid [resolution, resolution]
  Z: number[][];   // Predictions [resolution, resolution]
  bounds: {
    x_min: number;
    x_max: number;
    y_min: number;
    y_max: number;
  };
}
```

---

### TrainingState

```typescript
interface TrainingState {
  is_running: boolean;
  is_paused: boolean;
  current_epoch: number;
  current_loss: number;
  current_accuracy: number;
  hidden_units: number;
  metrics_count: number;
}
```

---

## Error Handling

### HTTP Error Codes

- `200 OK` - Request succeeded
- `302 Found` - Redirect (root endpoint)
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Resource not available
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service unhealthy

### Error Response Format

```json
{
  "error": "Error message description",
  "detail": "Additional error details (optional)",
  "status_code": 400
}
```

### WebSocket Error Handling

**Connection Errors:**

- Network disconnection → Client receives `onclose` event
- Server shutdown → `server_shutdown` message sent before close

**Command Errors:**

```json
{
  "ok": false,
  "error": "No backend available"
}
```

**Best Practices:**

- Implement exponential backoff for reconnection
- Handle `onclose` and `onerror` events
- Send `ping`/`pong` heartbeats every 30 seconds
- Gracefully degrade if WebSocket unavailable (fall back to REST polling)

---

## Rate Limiting

**Current Status:** No rate limiting (MVP)

**Future Plans:**

```yaml
security:
  rate_limiting:
    enabled: true
    requests_per_minute: 100
    burst_size: 10
```

**Response Headers (Future):**

```bash
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699200000
```

**429 Too Many Requests Response:**

```json
{
  "error": "Rate limit exceeded",
  "retry_after": 60
}
```

---

## Code Examples

### Python Client (REST API)

```python
import requests

BASE_URL = "http://127.0.0.1:8050"

# Health check
response = requests.get(f"{BASE_URL}/api/health")
health = response.json()
print(f"Status: {health['status']}")
print(f"Active connections: {health['active_connections']}")

# Get current status
response = requests.get(f"{BASE_URL}/api/status")
status = response.json()
print(f"Training: {status['is_training']}")
print(f"Epoch: {status['current_epoch']}")
print(f"Loss: {status['current_loss']:.4f}")

# Get recent metrics
response = requests.get(f"{BASE_URL}/api/metrics?limit=10")
metrics = response.json()
for m in metrics:
    print(f"Epoch {m['epoch']}: Loss={m['metrics']['loss']:.4f}")

# Get topology
response = requests.get(f"{BASE_URL}/api/topology")
topology = response.json()
print(f"Network: {topology['input_units']}-{topology['hidden_units']}-{topology['output_units']}")

# Get dataset
response = requests.get(f"{BASE_URL}/api/dataset")
dataset = response.json()
print(f"Dataset: {dataset['num_samples']} samples, {dataset['num_features']} features")
```

---

### Python Client (WebSocket)

```python
import asyncio
import json
import websockets

async def training_monitor():
    uri = "ws://127.0.0.1:8050/ws/training"

    async with websockets.connect(uri) as websocket:
        print("Connected to training stream")

        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'connection_established':
                print(f"Client ID: {data['client_id']}")

            elif msg_type == 'training_metrics':
                metrics = data['data']['metrics']
                epoch = data['data']['epoch']
                print(f"Epoch {epoch}: Loss={metrics['loss']:.4f}, Acc={metrics['accuracy']:.4f}")

            elif msg_type == 'cascade_add':
                unit_idx = data['data']['unit_index']
                print(f"New cascade unit added: #{unit_idx}")

# Run monitor
asyncio.run(training_monitor())
```

---

### Python Control Client

```python
import asyncio
import json
import websockets

async def training_controller():
    uri = "ws://127.0.0.1:8050/ws/control"

    async with websockets.connect(uri) as websocket:
        # Start training
        await websocket.send(json.dumps({
            'command': 'start',
            'reset': True
        }))

        response = await websocket.recv()
        data = json.loads(response)

        if data['ok']:
            print("Training started:", data['state'])
        else:
            print("Error:", data['error'])

        # Wait 10 seconds
        await asyncio.sleep(10)

        # Pause training
        await websocket.send(json.dumps({'command': 'pause'}))
        response = await websocket.recv()
        print("Paused:", json.loads(response))

        # Wait 5 seconds
        await asyncio.sleep(5)

        # Resume training
        await websocket.send(json.dumps({'command': 'resume'}))
        response = await websocket.recv()
        print("Resumed:", json.loads(response))

asyncio.run(training_controller())
```

---

### JavaScript Client (Browser)

```javascript
// Training monitor
const trainingWs = new WebSocket('ws://127.0.0.1:8050/ws/training');

trainingWs.onmessage = (event) => {
  const data = JSON.parse(event.data);

  switch (data.type) {
    case 'connection_established':
      console.log('Connected:', data.client_id);
      break;

    case 'training_metrics':
      const { epoch, metrics } = data.data;
      updateMetricsChart(epoch, metrics.loss, metrics.accuracy);
      break;

    case 'topology_update':
      updateTopologyGraph(data.data);
      break;

    case 'cascade_add':
      showNotification(`New unit added: #${data.data.unit_index}`);
      break;
  }
};

// Control client
const controlWs = new WebSocket('ws://127.0.0.1:8050/ws/control');

function startTraining() {
  controlWs.send(JSON.stringify({
    command: 'start',
    reset: true
  }));
}

function pauseTraining() {
  controlWs.send(JSON.stringify({ command: 'pause' }));
}

function resumeTraining() {
  controlWs.send(JSON.stringify({ command: 'resume' }));
}

function stopTraining() {
  controlWs.send(JSON.stringify({ command: 'stop' }));
}

controlWs.onmessage = (event) => {
  const response = JSON.parse(event.data);
  if (response.ok) {
    console.log(`Command '${response.command}' succeeded`);
    updateTrainingState(response.state);
  } else {
    console.error('Command failed:', response.error);
  }
};
```

---

### curl Examples

```bash
# Health check
curl http://127.0.0.1:8050/api/health

# Get status
curl http://127.0.0.1:8050/api/status

# Get metrics (last 10)
curl "http://127.0.0.1:8050/api/metrics?limit=10"

# Get topology
curl http://127.0.0.1:8050/api/topology

# Get dataset
curl http://127.0.0.1:8050/api/dataset

# Get decision boundary
curl http://127.0.0.1:8050/api/decision_boundary

# Get statistics
curl http://127.0.0.1:8050/api/statistics

# Pretty print JSON
curl -s http://127.0.0.1:8050/api/health | python -m json.tool
```

---

## Best Practices

### REST API

1. **Always check HTTP status codes**

   ```python
   response = requests.get(url)
   if response.status_code == 200:
       data = response.json()
   else:
       print(f"Error: {response.status_code}")
   ```

2. **Use appropriate timeouts**

   ```python
   response = requests.get(url, timeout=5)  # 5 second timeout
   ```

3. **Handle errors gracefully**

   ```python
   try:
       response = requests.get(url, timeout=5)
       response.raise_for_status()
       data = response.json()
   except requests.exceptions.RequestException as e:
       print(f"Request failed: {e}")
   ```

4. **Limit data retrieval**

   ```python
   # Don't retrieve all metrics
   response = requests.get(f"{BASE_URL}/api/metrics?limit=100")
   ```

---

### WebSocket

1. **Implement reconnection logic**

   ```javascript
   let reconnectDelay = 1000;
   const maxDelay = 30000;

   function connect() {
     const ws = new WebSocket(url);

     ws.onclose = () => {
       setTimeout(() => {
         reconnectDelay = Math.min(reconnectDelay * 2, maxDelay);
         connect();
       }, reconnectDelay);
     };

     ws.onopen = () => {
       reconnectDelay = 1000; // Reset on successful connection
     };
   }
   ```

2. **Send heartbeats**

   ```javascript
   setInterval(() => {
     if (ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify({ type: 'ping' }));
     }
   }, 30000); // Every 30 seconds
   ```

3. **Handle backpressure**

   ```javascript
   if (ws.bufferedAmount === 0) {
     ws.send(message);  // Safe to send
   } else {
     console.warn('Buffer full, skipping message');
   }
   ```

4. **Clean up on disconnect**

   ```javascript
   window.addEventListener('beforeunload', () => {
     ws.close(1000, 'Page unload');
   });
   ```

---

## Support and Contact

- **Documentation:** [docs/](.)
- **GitHub:** [Juniper Project](https://github.com/your-org/juniper)
- **Issues:** Report bugs via GitHub Issues
- **Email:** <support@example.com>

---

## End of API Reference
