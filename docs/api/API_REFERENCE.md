# Juniper Canopy API Reference

**Version:** 1.3.0
**Last Updated:** March 30, 2026
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

### External CasCor Normalization (Service Mode)

When `backend_type` is `service`, Canopy normalizes external CasCor `ResponseEnvelope` payloads before returning API responses.
This preserves dashboard contracts across demo and service backends for:

- status/state fields (`training_active`/`state_machine` -> flat status flags)
- metric naming (`loss`/`accuracy`/`validation_*` -> canonical keys where needed)
- dataset metadata (`input_features`/`train_samples` -> `num_*` keys)
- decision boundary key mapping (`grid_x`/`grid_y`/`predictions` -> `xx`/`yy`/`Z`)

Primary codepaths: `src/backend/cascor_service_adapter.py`, `src/backend/service_backend.py`, `src/backend/state_sync.py`.

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
  "timestamp": 1711459200.123,
  "version": "0.3.0",
  "active_connections": 2,
  "training_active": true,
  "demo_mode": false,
  "juniper_data_available": true
}
```

**Field Descriptions:**

- `status` (string) - Health status, currently always `"healthy"`
- `timestamp` (number) - Unix timestamp in seconds
- `version` (string) - Application version
- `active_connections` (integer) - Number of active WebSocket connections
- `training_active` (boolean) - Whether training is in progress
- `demo_mode` (boolean) - Whether running in demo mode
- `juniper_data_available` (boolean) - JuniperData dependency status

**Status Codes:**

- `200 OK` - Service healthy

**Example Request:**

```bash
curl http://127.0.0.1:8050/api/health
```

**Use Cases:**

- Docker health checks
- Load balancer probes
- Deployment diagnostics

### GET /api/status

**Description:** Get normalized training status and network information

**Parameters:** None

**Response Schema (Demo Backend):**

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
  "hidden_units": 3,
  "network_connected": true,
  "monitoring_active": true,
  "input_size": 2,
  "output_size": 1
}
```

**Response Schema (Service Backend, normalized):**

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

**Field Descriptions:**

- `is_training` (boolean) - Training active flag
- `is_running` (boolean) - Running state derived from backend FSM
- `is_paused` (boolean) - Paused state derived from backend FSM
- `completed` (boolean) - Completion state
- `failed` (boolean) - Failure state
- `fsm_status` (string) - Backend FSM status string
- `phase` (string) - Normalized phase (`idle`, `output`, `candidate`, `inference`, etc.)
- `current_epoch` (integer) - Current epoch
- `hidden_units` (integer) - Current hidden unit count
- `network_connected` (boolean) - Whether a network is loaded/connected
- `monitoring_active` (boolean) - Whether training monitoring is active
- `input_size` (integer) - Input dimension
- `output_size` (integer) - Output dimension
- `learning_rate` (number, service mode) - Active learning rate
- `max_hidden_units` (integer, service mode) - Max hidden units setting
- `max_epochs` (integer, service mode) - Max epochs setting

**Status Codes:**

- `200 OK` - Status retrieved successfully

**Notes:**

- Use `phase` (not `current_phase`) as the canonical phase key.
- In service mode, this endpoint returns normalized fields from nested CasCor status payloads.

### GET /api/state

**Description:** Get the full training state used by dashboard UI handlers.

**Parameters:** None

**Response Schema (abridged):**

```json
{
  "status": "Started",
  "phase": "Output",
  "learning_rate": 0.01,
  "max_hidden_units": 10,
  "current_epoch": 42,
  "grow_iteration": 3,
  "grow_max": 10,
  "phase_started_at": "2026-03-30T12:00:00+00:00",
  "candidate_epoch": 120,
  "candidate_total_epochs": 500
}
```

**Field Groups:**

- Core runtime: `status`, `phase`, `current_epoch`, `current_step`, `timestamp`
- Hyperparameters: `learning_rate`, `max_hidden_units`, `max_epochs`
- Candidate pool state: `candidate_pool_*`, `pool_metrics`, `top_candidate_*`
- Progress detail: `phase_detail`, `grow_iteration`, `grow_max`, `best_correlation`, `candidates_*`, `phase_started_at`, `candidate_epoch`, `candidate_total_epochs`
- Service/dashboard compatibility keys: `nn_*`, `cn_*` fields may also be present depending on backend mode

**Status Codes:**

- `200 OK` - State retrieved successfully

**Notes:**

- This endpoint is the source for metrics-panel state cards and progress bars.
- `phase_started_at` is ISO-8601 and used to compute elapsed phase duration in the dashboard.

### GET /api/metrics

**Description:** Get current training metrics snapshot

**Parameters:** None

**Response Schema (Demo Backend):**

```json
{
  "is_running": true,
  "is_paused": false,
  "current_epoch": 42,
  "current_loss": 0.234,
  "current_accuracy": 0.876,
  "hidden_units": 3,
  "metrics_count": 420
}
```

**Response Schema (Service Backend, normalized):**

```json
{
  "epoch": 42,
  "train_loss": 0.234,
  "train_accuracy": 0.876,
  "val_loss": 0.251,
  "val_accuracy": 0.861,
  "hidden_units": 3,
  "phase": "output",
  "timestamp": 1711459200.123
}
```

**Status Codes:**

- `200 OK` - Metrics retrieved successfully

**Notes:**

- `/api/metrics` is a point-in-time snapshot.
- For time-series plotting, use `/api/metrics/history`.

---

### GET /api/metrics/history

**Description:** Get historical training metrics

**Query Parameters:**

- `limit` (integer, optional): Maximum history entries to return. `0` means "all available" (internally capped).

**Response Schema:**

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

**History Entry Shapes:**

- Demo entries use nested `metrics` + `network_topology` blocks.
- Service entries are normalized flat metric objects (`train_loss`, `train_accuracy`, `val_loss`, `val_accuracy`, etc.).

**Status Codes:**

- `200 OK` - History retrieved successfully
- `422 Unprocessable Entity` - Invalid `limit` value type

**Example Request:**

```bash
curl "http://127.0.0.1:8050/api/metrics/history?limit=100"
```

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
    {"id": "hidden_0", "type": "hidden", "label": "H0"},
    {"id": "output_0", "type": "output", "layer": 2}
  ],
  "connections": [
    {"from": "input_0", "to": "hidden_0", "weight": 0.12},
    {"from": "hidden_0", "to": "output_0", "weight": 0.56}
  ]
}
```

**Field Descriptions:**

- `input_units` (integer) - Input node count
- `hidden_units` (integer) - Hidden node count
- `output_units` (integer) - Output node count
- `nodes` (array) - Topology node list
- `connections` (array) - Weighted edges

**Status Codes:**

- `200 OK` - Topology retrieved successfully
- `503 Service Unavailable` - No topology available

**Notes:**

- Node attributes may vary by backend (`layer` in demo mode, `label` in service mode).
- Consumers should rely on `id` + `type` + `connections` as primary contract.
- Service-mode topology normalization emits a strict 3-layer scheme:
  - `input` nodes use `layer: 0`
  - all `hidden_*` nodes use `layer: 1`
  - all `output_*` nodes use `layer: 2`
- In service mode, output connection rows are derived by transposing CasCor `output_weights` from `(input+hidden, output)` to output-oriented rows.

### GET /api/dataset

**Description:** Get dataset information

**Parameters:** None

**Response Schema (Demo Backend):**

```json
{
  "inputs": [[0.12, 0.34], [-0.56, 0.78]],
  "targets": [0, 1],
  "num_samples": 200,
  "num_features": 2,
  "num_classes": 2
}
```

**Response Schema (Service Backend, normalized):**

```json
{
  "num_samples": 1000,
  "num_features": 2,
  "num_classes": 3,
  "loaded": true,
  "train_samples": 800,
  "test_samples": 200,
  "inputs": [[0.1, 0.2], [0.3, 0.4]],
  "targets": [0, 1]
}
```

**Status Codes:**

- `200 OK` - Dataset retrieved successfully
- `503 Service Unavailable` - No dataset available

**Notes:**

- Demo mode returns full sample arrays.
- Service mode always returns normalized metadata (`num_samples`, `num_features`, `num_classes`), and may additionally include `inputs`/`targets` when available.
- If service metadata is returned without arrays, Canopy attempts a secondary dataset fetch through the service data endpoint before returning.
- When arrays are still unavailable, frontend dataset visualizations should treat the payload as metadata-only and avoid assuming `inputs`/`targets` exist.

### GET /api/decision_boundary

**Description:** Get decision boundary data for visualization

**Query Parameters:**

- `resolution` (integer, optional): Grid resolution per axis. Values are clamped to `[5, 200]`.

**Response Schema:**

```json
{
  "xx": [[-1.2, -1.0, -0.8], [-1.2, -1.0, -0.8]],
  "yy": [[-1.2, -1.2, -1.2], [-1.0, -1.0, -1.0]],
  "Z": [[0, 0, 1], [0, 1, 1]],
  "x_min": -1.2,
  "x_max": 1.2,
  "y_min": -1.2,
  "y_max": 1.2,
  "resolution": 100
}
```

**Field Descriptions:**

- `xx` (array) - X meshgrid (`resolution x resolution`)
- `yy` (array) - Y meshgrid (`resolution x resolution`)
- `Z` (array) - Predicted class grid (`resolution x resolution`)
- `x_min`, `x_max`, `y_min`, `y_max` (number) - Plot bounds
- `resolution` (integer) - Applied resolution

**Status Codes:**

- `200 OK` - Decision boundary computed
- `503 Service Unavailable` - No decision boundary data available

**Notes:**

- Service mode maps external CasCor `grid_x`/`grid_y`/`predictions` to `xx`/`yy`/`Z`.
- Returned `Z` is class grid data for contour rendering.

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

**Description:** Start training (optionally with reset)

**Parameters:**

- `reset` (boolean, query, optional) - Reset network before starting (default: `false`)

**Response Schema (Demo Backend):**

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

**Response Schema (Service Backend):**

```json
{
  "status": "started",
  "ok": true,
  "is_training": true
}
```

**Status Codes:**

- `200 OK` - Request accepted

### POST /api/train/pause

**Description:** Request training pause

**Parameters:** None

**Response Schema:**

```json
{
  "status": "paused"
}
```

**Status Codes:**

- `200 OK` - Request accepted

**Notes:**

- Endpoint response is an acknowledgement payload.
- For authoritative backend state, follow with `GET /api/status` or WebSocket control responses.

### POST /api/train/resume

**Description:** Request training resume

**Parameters:** None

**Response Schema:**

```json
{
  "status": "running"
}
```

**Status Codes:**

- `200 OK` - Request accepted

**Notes:**

- Endpoint response is an acknowledgement payload.
- For authoritative backend state, follow with `GET /api/status` or WebSocket control responses.

### POST /api/train/stop

**Description:** Request training stop

**Parameters:** None

**Response Schema:**

```json
{
  "status": "stopped"
}
```

**Status Codes:**

- `200 OK` - Request accepted

### POST /api/train/reset

**Description:** Reset training state

**Parameters:** None

**Response Schema (Demo Backend):**

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

**Response Schema (Service Backend):**

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

- `200 OK` - Request accepted

### GET /api/train/status

**Description:** Get backend-tagged training status

**Parameters:** None

**Response Schema:**

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

**Status Codes:**

- `200 OK` - Status retrieved successfully

**Notes:**

- `backend` is `"demo"` or `"service"`.
- Remaining fields mirror `GET /api/status` for the active backend.

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

**Request Body (JSON):**

- `address` (string, required) - Remote manager address in `host:port` format
- `authkey` (string, optional) - Authentication key for secure connection

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

Most WebSocket messages use this shape:

```json
{
  "type": "state | metrics | topology | event | control_ack",
  "timestamp": 1711459200.123,
  "data": { }
}
```

**Notes:**

- `/ws/training` sends an initial `initial_status` message before steady-state messages.
- Some control-channel messages may omit `timestamp`.
- Runtime dashboard updates consume `metrics`, `state`, `topology`, and `event` message types.

### WS /ws/training

**Description:** Stream training state/metrics/topology/event updates.

**Connection URL:**

```bash
ws://127.0.0.1:8050/ws/training
```

**Initial Status Message:**

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

**State Message:**

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

**Metrics Message:**

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

**Topology Message:**

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

**Event Message:**

```json
{
  "type": "event",
  "timestamp": 1711459202.123,
  "data": {
    "event": "training_complete"
  }
}
```

**Ping/Pong:**

```json
{"type": "ping"}
```

```json
{"type": "pong"}
```

**Example JavaScript Client:**

```javascript
const ws = new WebSocket('ws://127.0.0.1:8050/ws/training');

ws.onopen = () => {
  console.log('Connected to training stream');
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch (msg.type) {
    case 'initial_status':
      console.log('Initial status:', msg.data);
      break;
    case 'state':
      console.log('State:', msg.data);
      break;
    case 'metrics':
      console.log('Epoch:', msg.data.epoch);
      console.log('Loss:', msg.data.metrics?.loss);
      break;
    case 'event':
      console.log('Event:', msg.data);
      break;
    case 'pong':
      console.log('Pong received');
      break;
  }
};
```

### WS /ws/control

**Description:** Send training-control commands and receive command acknowledgements.

**Connection URL:**

```bash
ws://127.0.0.1:8050/ws/control
```

**Connection Confirmation:**

```json
{
  "type": "connection_confirmed",
  "client_id": "control-client-12345"
}
```

**Command Request:**

```json
{
  "command": "start",
  "reset": true
}
```

**Command Success Response:**

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

**Command Error Response:**

```json
{
  "ok": false,
  "error": "Unknown command: invalid_cmd"
}
```

**Supported Commands:** `start`, `stop`, `pause`, `resume`, `reset`

## Data Models

### TrainingMetrics

```typescript
interface DemoHistoryMetric {
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
  phase: string;
  timestamp: string; // ISO 8601 in demo mode
}

interface ServiceHistoryMetric {
  epoch: number;
  train_loss?: number;
  train_accuracy?: number;
  val_loss?: number;
  val_accuracy?: number;
  hidden_units?: number;
  phase?: string;
  timestamp?: number | string;
}
```

### NetworkTopology

```typescript
interface NetworkTopology {
  input_units: number;
  hidden_units: number;
  output_units: number;
  nodes: Node[];
  connections: Connection[];
}

interface Node {
  id: string; // e.g., "input_0", "hidden_1", "output_0"
  type: "input" | "hidden" | "output";
  layer?: number; // demo mode
  label?: string; // service mode
}

interface Connection {
  from: string;
  to: string;
  weight: number;
}
```

### Dataset

```typescript
interface DemoDataset {
  inputs: number[][];
  targets: number[] | number[][];
  num_samples: number;
  num_features: number;
  num_classes: number;
}

interface ServiceDataset {
  num_samples: number;
  num_features: number;
  num_classes: number;
  loaded?: boolean;
  train_samples?: number;
  test_samples?: number;
}
```

### DecisionBoundary

```typescript
interface DecisionBoundary {
  xx: number[][];  // X meshgrid [resolution, resolution]
  yy: number[][];  // Y meshgrid [resolution, resolution]
  Z: number[][];   // Class grid [resolution, resolution]
  x_min: number;
  x_max: number;
  y_min: number;
  y_max: number;
  resolution: number;
}
```

### TrainingState

```typescript
interface TrainingState {
  is_training?: boolean;
  is_running: boolean;
  is_paused: boolean;
  completed?: boolean;
  failed?: boolean;
  fsm_status?: string;
  phase?: string;
  current_epoch: number;
  current_loss?: number;
  current_accuracy?: number;
  hidden_units: number;
  metrics_count?: number;
}
```

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
print(f"Loss: {status.get('current_loss', status.get('train_loss'))}")

# Get recent metrics
response = requests.get(f"{BASE_URL}/api/metrics/history?limit=10")
metrics_payload = response.json()
for m in metrics_payload.get("history", []):
    epoch = m.get("epoch", 0)
    if "metrics" in m:
        loss = m["metrics"].get("loss")
    else:
        loss = m.get("train_loss")
    print(f"Epoch {epoch}: Loss={loss}")

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

            if msg_type == 'initial_status':
                print('Initial status received')

            elif msg_type == 'state':
                print('State update:', data['data'])

            elif msg_type == 'metrics':
                metrics = data['data'].get('metrics', {})
                epoch = data['data'].get('epoch')
                print(f"Epoch {epoch}: Loss={metrics.get('loss')} Acc={metrics.get('accuracy')}")

            elif msg_type == 'event':
                print('Event:', data['data'])

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
    case 'initial_status':
      console.log('Initial status:', data.data);
      break;

    case 'state':
      updateStatusBanner(data.data);
      break;

    case 'metrics':
      const { epoch, metrics } = data.data;
      updateMetricsChart(epoch, metrics.loss, metrics.accuracy);
      break;

    case 'topology':
      updateTopologyGraph(data.data);
      break;

    case 'event':
      console.log('Training event:', data.data);
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
curl "http://127.0.0.1:8050/api/metrics/history?limit=10"

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
   response = requests.get(f"{BASE_URL}/api/metrics/history?limit=100")
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
- **GitHub:** [Juniper Canopy](https://github.com/pcalnon/juniper-canopy)
- **Issues:** Report bugs via GitHub Issues
- **Email:** <support@example.com>

---

## End of API Reference
