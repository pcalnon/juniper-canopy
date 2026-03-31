# Canopy → CasCor Dashboard Data Flow Analysis

**Date**: 2026-03-26
**Status**: Investigation Complete — Fixes Required
**Symptom**: Canopy connects to external cascor successfully, but the dashboard displays no training data

---

## Executive Summary

The canopy dashboard shows no training data from an externally running cascor instance due to **response shape mismatches** between what the dashboard frontend expects and what the service backend returns. The dashboard was built against the demo backend's response formats. The service backend returns cascor's native API response structures, which have different key names, nesting, and envelope wrapping.

Three critical mismatches were identified:

1. `/api/status` returns a nested cascor structure instead of the flat dict the dashboard reads
2. `/api/metrics/history` extracts with the wrong envelope key (`"history"` vs `"data"`)
3. `/api/metrics` returns the raw cascor envelope without unwrapping

---

## Investigation Method

### Data Flow Traced

The full pipeline was traced from cascor → canopy backend → REST API → dashboard frontend:

```text
juniper-cascor (port 8201)
  └── /v1/training/status, /v1/metrics/*, /v1/network/*, /v1/dataset
        │
        ▼
juniper-cascor-client (JuniperCascorClient)
  └── client._get("/training/status") → returns raw JSON envelope
        │
        ▼
CascorServiceAdapter (canopy/src/backend/cascor_service_adapter.py)
  └── get_training_status() → _unwrap_response(client.get_training_status())
        │
        ▼
ServiceBackend (canopy/src/backend/service_backend.py)
  └── get_status() → adapter.get_training_status()
        │
        ▼
main.py REST endpoints (/api/status, /api/metrics/history, etc.)
  └── return backend.get_status()
        │
        ▼
dashboard_manager.py (Dash callbacks)
  └── _update_unified_status_bar_handler() ← polls /api/status via dcc.Interval
  └── _update_metrics_store_handler()      ← polls /api/metrics/history
  └── _update_topology_store_handler()     ← polls /api/topology
  └── _update_dataset_store_handler()      ← polls /api/dataset
```

### Files Examined

| File | Purpose |
|------|---------|
| `canopy/src/main.py` lines 620-743 | REST API endpoint definitions |
| `canopy/src/backend/service_backend.py` lines 100-124 | ServiceBackend method implementations |
| `canopy/src/backend/demo_backend.py` lines 87-199 | DemoBackend reference implementations |
| `canopy/src/backend/cascor_service_adapter.py` lines 47-80, 397-424 | _ServiceTrainingMonitor and adapter methods |
| `canopy/src/frontend/dashboard_manager.py` lines 1455-1590, 1681-1764 | Dashboard polling callbacks and status bar builder |
| `canopy/src/frontend/assets/websocket_client.js` | Browser WebSocket client (training + control) |
| `cascor/src/api/routes/metrics.py` | Cascor metrics endpoints |
| `cascor/src/api/routes/training.py` lines 109-113 | Cascor training status endpoint |
| `cascor/src/api/lifecycle/manager.py` lines 450-510 | Cascor status/metrics implementations |
| `cascor/src/api/models/common.py` lines 50-52 | `success_response()` envelope wrapper |
| `cascor-client/juniper_cascor_client/client.py` lines 172-211 | Client HTTP methods |

---

## Issue 1: `/api/status` — Completely Wrong Shape (CRITICAL)

### What the dashboard expects

`dashboard_manager.py` line 1525-1532 — `_update_unified_status_bar_handler()` reads:

```python
is_running = status_data.get("is_running", False)
is_paused = status_data.get("is_paused", False)
is_completed = status_data.get("completed", False)
is_failed = status_data.get("failed", False)
raw_phase = status_data.get("phase", "idle")
epoch = status_data.get("current_epoch", 0)
hidden_units = status_data.get("hidden_units", 0)
```

### What demo backend returns (reference)

`demo_backend.py` line 87-113 — `DemoBackend.get_status()` builds a flat dict:

```python
{
    "is_training": True,
    "is_running": True,          # ← dashboard reads this
    "is_paused": False,          # ← dashboard reads this
    "completed": False,          # ← dashboard reads this
    "failed": False,             # ← dashboard reads this
    "fsm_status": "STARTED",
    "phase": "output",           # ← dashboard reads this
    "current_epoch": 25,         # ← dashboard reads this
    "hidden_units": 3,           # ← dashboard reads this
    "network_connected": True,
    "monitoring_active": True,
    "input_size": 2,
    "output_size": 1,
    ...
}
```

### What service backend actually returns

`service_backend.py` line 100-101:

```python
def get_status(self) -> Dict[str, Any]:
    return self._adapter.get_training_status()
```

Which calls `_unwrap_response(self._client.get_training_status())`.

The cascor `/v1/training/status` endpoint returns (via `success_response()`):

```json
{
    "status": "success",
    "data": {
        "state_machine": {"status": "STARTED", "phase": "output", ...},
        "monitor": {"epoch": 25, "metrics_count": 100, ...},
        "training_state": {"learning_rate": 0.01, ...},
        "network_loaded": true,
        "training_active": true
    }
}
```

After `_unwrap_response`, the `"status"/"data"` envelope is stripped, but the result is still:

```json
{
    "state_machine": {"status": "STARTED", "phase": "output", ...},
    "monitor": {"epoch": 25, ...},
    "training_state": {...},
    "network_loaded": true,
    "training_active": true
}
```

### Evidence of failure

The dashboard reads `status_data.get("is_running", False)` → `False` (key doesn't exist).
Every field defaults: status → "Stopped", phase → "Idle", epoch → 0, hidden_units → 0.

### Location of fix

`service_backend.py` `get_status()` — must extract values from the nested cascor structure and build a flat dict matching the demo backend's format.

### Supporting references

- Cascor status structure: `cascor/src/api/lifecycle/manager.py` lines 450-462
- Dashboard consumption: `canopy/src/frontend/dashboard_manager.py` lines 1525-1532
- Demo backend reference: `canopy/src/backend/demo_backend.py` lines 87-113

---

## Issue 2: `/api/metrics/history` — Wrong Envelope Key (CRITICAL)

### What happens

`main.py` line 640-650:

```python
@app.get("/api/metrics/history")
async def get_metrics_history(limit: int = 100):
    count = limit if limit > 0 else 10000
    return {"history": backend.get_metrics_history(count)}
```

This calls `ServiceBackend.get_metrics_history(count)` → `self._adapter.training_monitor.get_recent_metrics(count)`.

`_ServiceTrainingMonitor.get_recent_metrics()` at line 74-79:

```python
def get_recent_metrics(self, count: int = 100) -> list:
    try:
        result = self._client.get_metrics_history(count=count)
        return result.get("history", []) if isinstance(result, dict) else result
    except JuniperCascorClientError:
        return []
```

### The bug

The cascor client's `get_metrics_history()` returns the raw cascor API response:

```json
{"status": "success", "data": [... list of metrics ...]}
```

The monitor extracts with `result.get("history", [])` — but the key is `"data"`, not `"history"`. This **always returns `[]`**.

The dashboard's `_update_metrics_store_handler()` at line 1694-1701 then receives `{"history": []}` and displays nothing.

### Evidence

- Cascor endpoint wraps with `success_response()`: `cascor/src/api/routes/metrics.py` line 33
- `success_response()` uses `{"status": "success", "data": ...}`: `cascor/src/api/models/common.py` line 50-52
- Client returns raw JSON: `cascor-client/client.py` line 270 (`return response.json()`)
- Monitor looks for wrong key: `cascor_service_adapter.py` line 77

### Location of fix

`_ServiceTrainingMonitor.get_recent_metrics()` line 77 — change `result.get("history", [])` to `result.get("data", [])`.

---

## Issue 3: `/api/metrics` — Unwrapped Envelope (MODERATE)

### What happens

`_ServiceTrainingMonitor.get_current_metrics()` at line 68-72:

```python
def get_current_metrics(self) -> Dict[str, Any]:
    try:
        return self._client.get_metrics()
    except JuniperCascorClientError:
        return {}
```

The cascor client returns:

```json
{"status": "success", "data": {"epoch": 5, "train_loss": 0.3, "train_accuracy": 0.85, ...}}
```

The metrics data is wrapped in the envelope. Downstream consumers that expect the inner dict (epoch, train_loss, etc.) at the top level will fail or get empty data.

### Location of fix

`_ServiceTrainingMonitor.get_current_metrics()` — unwrap the response: `return self._unwrap_response(self._client.get_metrics())` or extract `result.get("data", {})`.

---

## Issue 4: Dataset Format Differences (MODERATE)

### What demo backend returns

`demo_backend.py` line 187-199 — returns:

```python
{
    "num_samples": 200,
    "num_features": 2,
    "num_classes": 2,
    "inputs": [[0.1, 0.2], ...],   # 2D list
    "targets": [0, 1, ...]          # 1D list
}
```

### What cascor API returns

`cascor/src/api/lifecycle/manager.py` line 499-509 — returns:

```python
{
    "loaded": True,
    "train_samples": 200,
    "test_samples": 50,
    "input_features": 2,
    "output_features": 1
}
```

After `_unwrap_response`, the service backend returns the cascor format. The key names differ (`num_samples` vs `train_samples`, `num_features` vs `input_features`), and crucially the cascor endpoint does **not** return the actual data arrays (`inputs`, `targets`).

### Impact

The dataset visualization tab will either show no data or display incorrect metadata. The dataset plotter component likely expects `inputs` and `targets` arrays for scatter plots, which cascor's metadata-only endpoint does not provide.

### Investigation needed

- Check if cascor has a separate endpoint that returns actual dataset arrays
- Check what the dataset plotter component requires vs what it receives
- May need a dedicated cascor endpoint for full dataset retrieval, or the service adapter needs to call multiple cascor endpoints and assemble the response

---

## Endpoints Not Affected

### `/api/topology` — Likely OK

`CascorServiceAdapter.extract_network_topology()` uses `_unwrap_response(self._client.get_topology())`. The cascor topology endpoint returns nodes and connections in a format that should match what the network visualizer expects. Needs verification but structurally sound.

### `/api/decision_boundary` — Confirmed Working

`CascorServiceAdapter.get_decision_boundary()` explicitly maps cascor's `grid_x`/`grid_y` keys to the frontend's `xx`/`yy`/`Z` format. This transformation was implemented and tested with boundary test coverage.

---

## Dashboard Update Mechanism

The dashboard uses **two parallel update mechanisms**:

### 1. dcc.Interval Polling (Primary — drives all data display)

```text
fast-update-interval (DashboardConstants.FAST_UPDATE_INTERVAL_MS)
  ├── update_unified_status_bar  → GET /api/status
  └── update_metrics_store       → GET /api/metrics/history

slow-update-interval (DashboardConstants.SLOW_UPDATE_INTERVAL_MS)
  ├── update_network_info        → GET /api/status
  ├── update_topology_store      → GET /api/topology
  ├── update_dataset_store       → GET /api/dataset
  └── update_boundary_store      → GET /api/decision_boundary
```

This is the mechanism that drives all visible dashboard content. **All data display depends on correct REST API responses.**

### 2. WebSocket Push (Secondary — real-time overlay)

```text
websocket_client.js → CascorWebSocket → ws://host:8050/ws/training
  └── Buffers messages in messageBuffer[]
  └── Dispatches to registered type handlers
```

The WebSocket client receives pushed messages and buffers them. However, there is **no evidence** that any Dash callback consumes `window.cascorWS.getBufferedMessages()`. The WebSocket appears to be infrastructure for future real-time push integration but is not currently wired into the Dash callback graph for data display.

**Implication**: Even if the relay loop correctly pushes cascor messages to canopy's WebSocket, the dashboard won't display them until a Dash callback is wired to consume the buffer. The polling callbacks are the sole data path.

---

## Next Steps — Prioritized

### Priority 1: Fix `/api/status` Response Shape (CRITICAL)

**File**: `canopy/src/backend/service_backend.py`
**Method**: `get_status()`
**Action**: Extract values from cascor's nested response and build a flat dict matching `DemoBackend.get_status()` format. Map:

| Cascor Path | Canopy Key |
|-------------|------------|
| `state_machine.status == "STARTED"` | `is_running: True` |
| `state_machine.status == "PAUSED"` | `is_paused: True` |
| `state_machine.status == "COMPLETED"` | `completed: True` |
| `state_machine.status == "FAILED"` | `failed: True` |
| `state_machine.phase` | `phase` |
| `monitor.epoch` or `training_state.current_epoch` | `current_epoch` |
| `monitor.hidden_units` | `hidden_units` |
| `training_active` | `is_training` |

**Estimated effort**: 30 min
**Impact**: Unlocks status bar, phase display, epoch counter, hidden unit counter

### Priority 2: Fix Metrics History Envelope Key (CRITICAL)

**File**: `canopy/src/backend/cascor_service_adapter.py`
**Method**: `_ServiceTrainingMonitor.get_recent_metrics()` line 77
**Action**: Change `result.get("history", [])` to `result.get("data", [])`
**Estimated effort**: 5 min
**Impact**: Unlocks metrics charts (loss plot, accuracy plot)

### Priority 3: Fix Current Metrics Envelope (MODERATE)

**File**: `canopy/src/backend/cascor_service_adapter.py`
**Method**: `_ServiceTrainingMonitor.get_current_metrics()` line 70
**Action**: Unwrap the response envelope: `return CascorServiceAdapter._unwrap_response(self._client.get_metrics())`
**Estimated effort**: 5 min
**Impact**: Fixes current metrics snapshot for any consumer

### Priority 4: Investigate Dataset Format Gap (MODERATE)

**File**: `canopy/src/backend/service_backend.py` and `cascor_service_adapter.py`
**Action**: Determine whether cascor has an endpoint returning actual dataset arrays (not just metadata). If not, evaluate adding one to cascor or using the juniper-data-client to fetch data directly. Map cascor metadata keys to canopy's expected format.
**Estimated effort**: 1-2 hours (investigation + potential cascor endpoint addition)
**Impact**: Unlocks dataset visualization tab

### Priority 5: Verify Topology Format Compatibility (LOW)

**Action**: Compare cascor's `/v1/network/topology` response shape against what `network_visualizer.py` expects (nodes, connections, layers). May need key mapping similar to decision boundary.
**Estimated effort**: 30 min
**Impact**: Ensures network topology visualization works

---

## Test Verification Plan

After fixes are applied:

1. **Unit tests**: Mock cascor client responses with real cascor envelope format, verify service backend returns dashboard-compatible shapes
2. **Integration tests**: Start cascor on 8201, canopy on 8050 with `CASCOR_SERVICE_URL=http://localhost:8201`, verify each `/api/*` endpoint returns correct format
3. **Visual verification**: Open dashboard in browser, confirm:
   - Status bar shows Running/Paused/Stopped correctly
   - Epoch counter increments
   - Hidden units count updates on cascade events
   - Loss/accuracy charts plot live data
   - Network topology renders with correct structure
   - Dataset scatter plot displays (if data available)
   - Decision boundary contour renders

---

## Architectural Observation

The root cause is that `ServiceBackend` was implemented as a thin passthrough to `CascorServiceAdapter`, which in turn passes through the cascor-client's raw responses. The `DemoBackend`, by contrast, carefully constructs response dicts matching the dashboard's expected format.

The `BackendProtocol` (defined in `backend/protocol.py`) specifies the interface but not the response shapes. A robust fix should define the expected response schemas explicitly in the protocol or in a shared contract, ensuring both demo and service backends produce identical shapes for the same method calls. This would prevent similar mismatches if a third backend implementation is ever added.
