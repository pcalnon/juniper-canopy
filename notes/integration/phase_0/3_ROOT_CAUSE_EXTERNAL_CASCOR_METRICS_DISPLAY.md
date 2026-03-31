# Root Cause Analysis: External CasCor Training Not Displayed in Canopy

**Version**: 1.0.0
**Date**: 2026-03-26
**Author**: Claude (AI Agent)
**Status**: Root Causes Identified — Ready for Fix Implementation
**Related**: `INVESTIGATION_PLAN_EXTERNAL_CASCOR_METRICS_DISPLAY.md`,
`CANOPY_EXTERNAL_CASCOR_PLAN.md`

---

## Executive Summary

The canopy dashboard displays no training metrics when connected to an
external cascor process. The investigation traced both data paths (HTTP
polling and WebSocket relay) end-to-end across three codebases and identified
**5 root causes**, all stemming from a single systemic issue:

> **The `_ServiceTrainingMonitor` and `CascorStateSync` classes read
> response fields at the wrong nesting level because they were developed
> against `FakeCascorClient`, whose response format diverges from the real
> cascor server's `ResponseEnvelope`.**

The **primary cause** (RC-1) is that the HTTP polling path — which is the
Dash dashboard's sole mechanism for populating metrics plots — always returns
an empty list due to an incorrect key lookup on the response envelope.

---

## Root Causes

### RC-1: `_ServiceTrainingMonitor.get_recent_metrics()` Always Returns `[]` (CRITICAL)

**File**: `canopy/src/backend/cascor_service_adapter.py:74-77`
**Impact**: Dashboard metrics panels are permanently empty — no loss curves,
no accuracy plots, no epoch counters.

#### Code

```python
def get_recent_metrics(self, count: int = 100) -> list:
    try:
        result = self._client.get_metrics_history(count=count)
        return result.get("history", []) if isinstance(result, dict) else result
    except JuniperCascorClientError:
        return []
```

#### Evidence

**Real cascor server** wraps all responses in `ResponseEnvelope`:

```bash
GET /v1/metrics/history?count=100
```

The cascor route handler (`metrics.py:27-33`):

```python
return success_response(lifecycle.get_metrics_history(count=count))
```

Where `lifecycle.get_metrics_history(count)` returns a **list** of metric
dicts, and `success_response()` wraps it in `ResponseEnvelope`:

```json
{
    "status": "success",
    "data": [
        {"epoch": 1, "train_loss": 0.5, "train_accuracy": 0.6, ...},
        {"epoch": 2, "train_loss": 0.4, "train_accuracy": 0.7, ...}
    ],
    "meta": {"timestamp": 1711411200.0, "version": "0.4.0"}
}
```

The `JuniperCascorClient._request()` method (`client.py:253-270`) returns
`response.json()` — the **full envelope** with no unwrapping.

**The bug**: `result.get("history", [])` looks for a top-level `"history"`
key. The envelope has `"status"`, `"data"`, and `"meta"` — no `"history"`.
Returns `[]` unconditionally.

**FakeCascorClient** (`fake_client.py:604-611`) returns:

```json
{
    "status": "ok",
    "data": {
        "history": [...],
        "total": 100,
        "returned": 100
    }
}
```

Note: `"history"` is nested inside `"data"` even in the fake client, so
`result.get("history", [])` also returns `[]` with the fake client. This
bug exists in both paths but was never caught because **no test exercises
`_ServiceTrainingMonitor.get_recent_metrics()` with either client**.

#### Data Flow (Broken)

```text
Dashboard polls GET /api/metrics/history?limit=100
  → main.py:649: return {"history": backend.get_metrics_history(count)}
    → service_backend.py:107: return self._adapter.training_monitor.get_recent_metrics(count)
      → cascor_service_adapter.py:76: result.get("history", [])
        → result = {"status": "success", "data": [...metrics...], "meta": {...}}
        → result.get("history", []) → []  ← DATA LOST HERE
      ← []
    ← []
  ← {"history": []}
Dashboard renders empty metrics panel
```

#### Fix

```python
def get_recent_metrics(self, count: int = 100) -> list:
    try:
        result = self._client.get_metrics_history(count=count)
        if isinstance(result, dict):
            # Unwrap ResponseEnvelope: data may be a list (real server)
            # or a dict with "history" key (FakeCascorClient)
            data = result.get("data", result)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("history", [])
        return result if isinstance(result, list) else []
    except JuniperCascorClientError:
        return []
```

---

### RC-2: `_ServiceTrainingMonitor.is_training` Always Returns `False` (MODERATE)

**File**: `canopy/src/backend/cascor_service_adapter.py:60-66`
**Impact**: Health endpoints report training as inactive. `is_training_active()`
on service backend is always False. Training controls may malfunction.

#### Code

```python
@property
def is_training(self) -> bool:
    try:
        status = self._client.get_training_status()
        return status.get("is_training", False)
    except JuniperCascorClientError:
        return False
```

#### Evidence

**Real cascor** `GET /v1/training/status` returns:

```json
{
    "status": "success",
    "data": {
        "state_machine": {"current_state": "STARTED", ...},
        "monitor": {...},
        "training_state": {...},
        "network_loaded": true,
        "training_active": true
    },
    "meta": {...}
}
```

`status.get("is_training", False)` → `False` because there is no top-level
`"is_training"` key. The training active flag is at `data.training_active`.

**FakeCascorClient** (`fake_client.py:484-495`) returns:

```json
{
    "status": "ok",
    "is_training": true,
    "data": {"state": "training", "epoch": 42, ...}
}
```

The fake client puts `"is_training"` at the top level — diverging from the
real server's envelope structure.

#### Fix

```python
@property
def is_training(self) -> bool:
    try:
        status = self._client.get_training_status()
        # Check top-level (FakeCascorClient) then unwrap envelope (real server)
        if "is_training" in status:
            return status["is_training"]
        data = status.get("data", {})
        if isinstance(data, dict):
            return data.get("training_active", False)
        return False
    except JuniperCascorClientError:
        return False
```

---

### RC-3: `_ServiceTrainingMonitor.get_current_metrics()` Returns Full Envelope (MODERATE)

**File**: `canopy/src/backend/cascor_service_adapter.py:68-72`
**Impact**: `GET /api/metrics` returns the ResponseEnvelope wrapper instead
of the metrics payload. Dashboard may fail to extract metric values.

#### Code

```python
def get_current_metrics(self) -> Dict[str, Any]:
    try:
        return self._client.get_metrics()
    except JuniperCascorClientError:
        return {}
```

#### Evidence

`self._client.get_metrics()` returns:

```json
{
    "status": "success",
    "data": {"epoch": 42, "train_loss": 0.05, ...},
    "meta": {...}
}
```

This envelope is returned directly. The caller (`ServiceBackend.get_metrics()`
→ `main.py GET /api/metrics`) passes it to the dashboard as-is. The dashboard
would need to unwrap `"data"` to access the actual metrics.

#### Fix

```python
def get_current_metrics(self) -> Dict[str, Any]:
    try:
        result = self._client.get_metrics()
        if isinstance(result, dict) and "data" in result:
            return result["data"] if isinstance(result["data"], dict) else result
        return result
    except JuniperCascorClientError:
        return {}
```

---

### RC-4: `CascorStateSync.sync()` Misreads Training Status (MODERATE)

**File**: `canopy/src/backend/state_sync.py:57-65`
**Impact**: Initial state hydration shows "Stopped" with epoch=0 even when
cascor is actively training. Dashboard starts with incorrect state.

#### Code

```python
status_response = self._client.get_training_status()
state.is_training = status_response.get("is_training", False)
data = status_response.get("data", {})
raw_state = data.get("state", "idle")
state.status = self._normalize_status(raw_state)
state.current_epoch = data.get("epoch", 0)
state.max_epochs = data.get("max_epochs", 0)
```

#### Evidence

With the real cascor, `status_response` is:

```json
{
    "status": "success",
    "data": {
        "state_machine": {"current_state": "STARTED", ...},
        "monitor": {"epoch": 42, ...},
        "training_state": {"status": "training", ...},
        "network_loaded": true,
        "training_active": true
    },
    "meta": {...}
}
```

Line-by-line evaluation against real response:

| Line | Expression | Expected | Actual | Correct? |
|------|-----------|----------|--------|----------|
| 59 | `status_response.get("is_training", False)` | `True` | `False` | No — `is_training` not at top level |
| 61 | `status_response.get("data", {})` | inner dict | `{"state_machine": ..., "training_active": ...}` | Partially — gets the data dict |
| 62 | `data.get("state", "idle")` | `"training"` | `"idle"` | No — no `"state"` key; it's `state_machine.current_state` |
| 63 | `_normalize_status("idle")` | `"Started"` | `"Stopped"` | No — wrong input |
| 64 | `data.get("epoch", 0)` | `42` | `0` | No — epoch is in `monitor` or `training_state`, not at top of `data` |
| 65 | `data.get("max_epochs", 0)` | `1000` | `0` | No — same nesting issue |

With FakeCascorClient (passes correctly):

| Line | Expression | Result | Correct? |
|------|-----------|--------|----------|
| 59 | `status_response.get("is_training", False)` | `True` | Yes — fake puts it at top level |
| 62 | `data.get("state", "idle")` | `"training"` | Yes — fake puts it in `data.state` |
| 64 | `data.get("epoch", 0)` | `42` | Yes — fake puts it in `data.epoch` |

#### Fix

```python
status_response = self._client.get_training_status()
# Unwrap ResponseEnvelope
data = status_response.get("data", {})
if isinstance(data, dict):
    # Real server: training_active is in data; state in state_machine
    state.is_training = (
        status_response.get("is_training")  # FakeCascorClient
        or data.get("training_active", False)  # Real server
    )
    # Extract state string
    raw_state = (
        data.get("state")  # FakeCascorClient
        or (data.get("state_machine", {}).get("current_state", "").lower()
            if isinstance(data.get("state_machine"), dict) else None)
        or "idle"
    )
    state.status = self._normalize_status(raw_state)
    # Extract epoch from training_state or monitor sub-dicts
    ts = data.get("training_state", {})
    monitor = data.get("monitor", {})
    state.current_epoch = (
        data.get("epoch")  # FakeCascorClient
        or (ts.get("epoch") if isinstance(ts, dict) else None)
        or (monitor.get("epoch") if isinstance(monitor, dict) else None)
        or 0
    )
    state.max_epochs = data.get("max_epochs", 0)
```

Also needs a status normalization update for `"started"` → `"Started"` to
handle the real server's `current_state: "STARTED"` (uppercase).

---

### RC-5: `FakeCascorClient` Response Format Diverges from Real Server (SYSTEMIC)

**File**: `juniper-cascor-client/juniper_cascor_client/testing/fake_client.py`
**Impact**: All tests pass against the fake client but fail against the real
cascor server. The fake gives a false sense of integration correctness.

#### Divergences

| Method | FakeCascorClient Format | Real CasCor Server Format |
|--------|------------------------|--------------------------|
| `get_training_status()` | `{"status": "ok", "is_training": bool, "data": {"state": str, "epoch": int, ...}}` | `{"status": "success", "data": {"state_machine": {...}, "monitor": {...}, "training_state": {...}, "training_active": bool, "network_loaded": bool}, "meta": {...}}` |
| `get_metrics_history()` | `{"status": "ok", "data": {"history": [...], "total": N, "returned": N}}` | `{"status": "success", "data": [...list of metrics...], "meta": {...}}` |
| `get_metrics()` | `{"status": "ok", "data": {"epoch": int, "train_loss": float, ...}}` | `{"status": "success", "data": {"epoch": int, "train_loss": float, ...}, "meta": {...}}` |
| `get_training_params()` | `{"status": "ok", "data": {"params": {...}, "epochs": int}}` | `{"status": "success", "data": {"learning_rate": float, "max_hidden_units": int, ...}, "meta": {...}}` |

Key structural differences:

1. **Top-level `"is_training"`**: Present in fake, absent in real
2. **`"status"` value**: `"ok"` in fake, `"success"` in real
3. **`"meta"` field**: Absent in fake, present in real
4. **Metrics history `"data"` shape**: Dict with `"history"` key in fake,
   bare list in real
5. **Training status `"data"` shape**: Flat fields (`state`, `epoch`) in fake,
   nested sub-objects (`state_machine`, `monitor`, `training_state`) in real
6. **Training params `"data"` shape**: Wrapped in `"params"` sub-key in fake,
   flat param dict in real

#### Recommended Fix

The `FakeCascorClient` should be updated to emit `ResponseEnvelope`-compatible
responses matching the real server's format. This ensures that any code
tested against the fake will also work against the real server.

Alternatively, the `JuniperCascorClient` could unwrap the `ResponseEnvelope`
internally, returning only the `"data"` payload from all methods. This would
make the real client's return type match the fake client's inner structure.
**This is the preferred approach** as it centralizes envelope handling in
one place.

---

## Severity Summary

| RC | Severity | Symptom | Blocks Display? |
|----|----------|---------|-----------------|
| RC-1 | **CRITICAL** | Metrics history always empty | **Yes** — primary display path broken |
| RC-2 | MODERATE | `is_training` always False | No — but breaks health/controls |
| RC-3 | MODERATE | Current metrics wrapped in envelope | Partial — depends on frontend handling |
| RC-4 | MODERATE | State sync shows Stopped/epoch=0 | No — but initial state incorrect |
| RC-5 | SYSTEMIC | Tests pass but real integration fails | N/A — root cause of RC-1 through RC-4 |

---

## Data Path Analysis Summary

### Path A: HTTP Polling (BROKEN — RC-1)

```text
Dashboard (1s interval)
  → GET /api/metrics/history
    → main.py:649 → backend.get_metrics_history(count)
      → service_backend.py:107 → adapter.training_monitor.get_recent_metrics(count)
        → _ServiceTrainingMonitor.get_recent_metrics(count)
          → client.get_metrics_history(count)
            → cascor GET /v1/metrics/history
              ← {"status":"success","data":[...metrics...],"meta":{...}}
          ← full envelope dict
        → result.get("history", [])  ← ██ FAILS: no "history" key ██
        ← []
      ← []
    ← {"history": []}
  → dashboard_manager.py:1696: payload["history"] → []
  → metrics_panel: renders nothing
```

### Path B: WebSocket Relay (FUNCTIONAL but not wired to display)

```text
cascor /ws/training broadcasts {"type":"metrics","data":{...}}
  → CascorTrainingStream reads message
    → _relay_loop() in cascor_service_adapter.py
      → websocket_manager.broadcast({"type":"metrics","data":{...}})
        → canopy /ws/training connected clients receive message
          → websocket_client.js adds to messageBuffer
            → Buffer is NOT read by any Dash callback
              → ██ Messages received but not rendered ██
```

The WebSocket relay correctly forwards metrics but the Dash dashboard
does not consume WebSocket messages for its metrics store. The `dcc.Store`
is populated exclusively via HTTP polling (Path A).

### Path C: State Hydration on Connect (DEGRADED — RC-4)

```text
ServiceBackend.initialize()
  → CascorStateSync(client).sync()
    → client.get_training_status()
      ← {"status":"success","data":{"state_machine":{...},"training_active":true,...}}
    → status_response.get("is_training", False) → False  ← ██ WRONG ██
    → data.get("state", "idle") → "idle"                 ← ██ WRONG ██
    → data.get("epoch", 0) → 0                           ← ██ WRONG ██
  ← SyncedState(is_training=False, status="Stopped", current_epoch=0)
→ training_state updated with incorrect values
```

---

## Dependency Chain

```text
RC-5 (FakeCascorClient divergence)
  ├── causes → RC-1 (metrics history empty)     ← BLOCKS ALL DISPLAY
  ├── causes → RC-2 (is_training always False)
  ├── causes → RC-3 (current metrics unwrapped)
  └── causes → RC-4 (state sync misreads)
```

**Fixing RC-5 at the `JuniperCascorClient` level (unwrap envelope in
client)** would resolve RC-1 through RC-4 simultaneously, as all consumer
code would receive the inner `"data"` payload directly.

---

## Recommended Fix Strategy

### Option A: Fix at Client Library Level (Preferred)

Add envelope unwrapping to `JuniperCascorClient._request()`:

```python
def _request(self, method, path, json=None, params=None):
    # ... existing request logic ...
    body = response.json()
    # Unwrap ResponseEnvelope if present
    if isinstance(body, dict) and "data" in body and "meta" in body:
        return body["data"]
    return body
```

**Pros**: Single fix, all consumers benefit, fake client already returns
unwrapped data (minus the "data" wrapper).
**Cons**: Breaking change for any code that reads `"status"` or `"meta"`.

### Option B: Fix at Canopy Adapter Level

Fix each method in `_ServiceTrainingMonitor` and `CascorStateSync` to
unwrap the envelope before reading fields.

**Pros**: No cross-repo changes needed.
**Cons**: Multiple fixes, easy to miss a method, doesn't fix the root
divergence.

### Option C: Fix FakeCascorClient + Canopy Adapter (Most Thorough)

1. Update `FakeCascorClient` to match real server's ResponseEnvelope format
2. Fix all canopy code that reads responses incorrectly
3. Tests will break → fix tests → confidence that real integration works

**Pros**: Tests become reliable integration indicators.
**Cons**: Most work, touches all three repos.

---

## Verification Commands

After fixes are applied:

```bash
# Unit tests (canopy)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
pytest tests/unit/ -v

# Integration tests (canopy)
pytest tests/integration/ -v

# Cascor regression
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
conda activate JuniperCascor
bash scripts/run_tests.bash

# Manual E2E: start cascor, start canopy, verify dashboard shows metrics
# Terminal 1:
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
python server.py

# Terminal 2:
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: verify metrics endpoint returns data
curl -s http://localhost:8050/api/metrics/history?limit=10 | python -m json.tool
```

---

## Files Requiring Changes

### Critical (RC-1 fix — unblocks metrics display)

| File | Change |
|------|--------|
| `canopy/src/backend/cascor_service_adapter.py:74-77` | Unwrap envelope in `get_recent_metrics()` |

### Important (RC-2, RC-3, RC-4 fixes)

| File | Change |
|------|--------|
| `canopy/src/backend/cascor_service_adapter.py:60-66` | Unwrap envelope in `is_training` |
| `canopy/src/backend/cascor_service_adapter.py:68-72` | Unwrap envelope in `get_current_metrics()` |
| `canopy/src/backend/state_sync.py:57-65` | Navigate real server's nested response structure |

### Systemic (RC-5 fix — prevent future divergence)

| File | Change |
|------|--------|
| `cascor-client/juniper_cascor_client/testing/fake_client.py` | Match ResponseEnvelope format OR |
| `cascor-client/juniper_cascor_client/client.py:253-270` | Unwrap envelope in `_request()` |

---

## Investigation Methodology

1. **Read all source files** in the data path across 3 codebases
2. **Traced HTTP polling path** end-to-end (dashboard → main.py → service_backend → adapter → client → cascor server → response envelope → adapter unwrap → main.py → dashboard)
3. **Traced WebSocket relay path** (cascor WS → CascorTrainingStream → relay loop → websocket_manager → dashboard JS)
4. **Compared response formats** between FakeCascorClient and real cascor ResponseEnvelope
5. **Identified key lookup mismatches** at each unwrap point
6. **Verified cascade**: all issues trace back to RC-5 (envelope format divergence)
