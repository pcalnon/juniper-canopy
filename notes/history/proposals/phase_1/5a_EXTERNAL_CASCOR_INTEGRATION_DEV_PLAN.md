# External CasCor Integration: Comprehensive Development Plan

**Version**: 2.0.0
**Date**: 2026-03-26
**Author**: Claude (AI Agent)
**Status**: Draft — Pending Review
**Supersedes**: `CANOPY_EXTERNAL_CASCOR_PLAN.md` (v1.0.0)
**Source Analysis**: Synthesized from `CANOPY_EXTERNAL_CASCOR_PLAN.md`,
`ROOT_CAUSE_EXTERNAL_CASCOR_METRICS_DISPLAY.md`, and
`CANOPY_CASCOR_DASHBOARD_DATA_FLOW_ANALYSIS.md`, validated against current
codebase state.

---

## 1. Executive Summary

When juniper-canopy connects to an externally running juniper-cascor instance,
the dashboard displays no training data — no metrics, no status, no topology
updates. The investigation across three analysis documents and codebase
validation identified **one systemic root cause** producing **8 distinct
integration failures**.

**Systemic root cause**: The `_ServiceTrainingMonitor` and `CascorStateSync`
classes were developed against `FakeCascorClient`, whose response format
structurally diverges from the real cascor server's `ResponseEnvelope`. Every
method that reads response fields uses the fake client's key layout, which
doesn't match the real server.

**Scope**: All fixes are in juniper-canopy except the systemic FakeCascorClient
alignment (juniper-cascor-client). No changes required in juniper-cascor.

**Estimated effort**: 6–10 hours across 5 phases.

> **Validation note**: This plan was validated against the current codebase by
> three independent review agents. Several items from the source documents were
> found to be **already implemented** (FIX-8, FIX-11, state callback wiring).
> One additional bug was discovered during validation (FIX-14). All corrections
> are incorporated below.

---

## 2. Problem Statement

The juniper-canopy dashboard has two backends: `DemoBackend` (local simulation)
and `ServiceBackend` (connects to real cascor via REST/WebSocket). The demo
backend works correctly. The service backend connects and attaches successfully,
but every data path from cascor to the dashboard is broken:

| Dashboard Element | Expected | Actual | Root Cause |
|---|---|---|---|
| Metrics charts (loss, accuracy) | Live curves | Empty | RC-1: wrong envelope key |
| Status bar (Running/Paused/etc.) | FSM state | Always "Stopped" | Issue-1: wrong response shape |
| Epoch counter | Current epoch | Always 0 | Issue-1: nested structure not flattened |
| Hidden units counter | Unit count | Always 0 | Issue-1: nested structure not flattened |
| Phase indicator | Output/Candidate | Always "Idle" | Issue-1: nested structure not flattened |
| Initial state on connect | Synced from cascor | Defaults | RC-4: sync reads wrong keys |
| `is_training` flag | True when active | Always False | RC-2: wrong envelope level |
| Current metrics snapshot | Metric values | Envelope wrapper | RC-3: no unwrapping |

---

## 3. Root Cause Chain

All failures trace to a single systemic issue:

```text
RC-SYS: FakeCascorClient response format diverges from real cascor ResponseEnvelope
  │
  ├── RC-1 (CRITICAL): _ServiceTrainingMonitor.get_recent_metrics() → always []
  │     result.get("history", []) but real response has {"data": [...]}
  │
  ├── RC-2 (MODERATE): _ServiceTrainingMonitor.is_training → always False
  │     status.get("is_training", False) but real response nests it at data.training_active
  │
  ├── RC-3 (MODERATE): _ServiceTrainingMonitor.get_current_metrics() → full envelope
  │     Returns raw client response without unwrapping
  │
  ├── RC-4 (MODERATE): CascorStateSync.sync() → wrong initial state
  │     Reads data.state, data.epoch — real has data.state_machine.current_state, data.monitor.epoch
  │
  └── Issue-1 (CRITICAL): ServiceBackend.get_status() → wrong response shape
        Returns nested cascor structure; dashboard expects flat keys (is_running, phase, etc.)
```

**Why `_ServiceTrainingMonitor` is particularly affected**: It wraps the raw
`JuniperCascorClient` directly and does NOT use `CascorServiceAdapter._unwrap_response()`.
The adapter's other methods DO unwrap, but the monitor class bypasses this entirely.

---

## 4. Response Format Divergence Reference

### 4.1 Training Status

| Aspect | FakeCascorClient | Real CasCor Server |
|---|---|---|
| Status field | `"status": "ok"` | `"status": "success"` |
| Training flag | Top-level `"is_training": bool` | `data.training_active: bool` |
| State string | `data.state: "training"` | `data.state_machine.status: "Started"` |
| Epoch | `data.epoch: int` | `data.monitor.current_epoch: int` |
| Max epochs | `data.max_epochs: int` | `data.training_state.max_epochs: int` |
| Meta field | Absent | `"meta": {"timestamp": float, "version": str}` |

### 4.2 Metrics History

| Aspect | FakeCascorClient | Real CasCor Server |
|---|---|---|
| Data shape | `data: {"history": [...], "total": N, "returned": N}` | `data: [...]` (bare list) |
| Meta field | Absent | Present |

### 4.3 Training Params

| Aspect | FakeCascorClient | Real CasCor Server |
|---|---|---|
| Data shape | `data: {"params": {...}, "epochs": int}` | `data: {"learning_rate": float, "max_hidden_units": int, ...}` (flat) |
| Meta field | Absent | Present |

### 4.4 Current Metrics

| Aspect | FakeCascorClient | Real CasCor Server |
|---|---|---|
| Extra fields | `correlation`, `phase` | `timestamp` |
| Meta field | Absent | Present |

---

## 5. Previously Identified Gaps — Current Status

Cross-referencing `CANOPY_EXTERNAL_CASCOR_PLAN.md` gaps against current codebase:

| Gap | Original Description | Current Status | Action |
|---|---|---|---|
| Gap 1 | Backend factory ignores settings system | **Resolved** — `create_backend()` accepts `service_url`/`demo_mode`, reads settings | Minor: verify API key env var |
| Gap 2 | State not hydrated on connect | **Partially resolved** — `initialize()` calls `CascorStateSync.sync()`, but sync reads wrong fields | Fix in Phase 2 |
| Gap 3 | `/api/state` returns defaults in service mode | **Resolved** — main.py:583-615 already fetches params via `get_canopy_params()` and merges with defaults | Verify `get_canopy_params()` envelope handling |
| Gap 4 | Discovery env var mutation | **Resolved** — lifespan passes `discovered_url` directly to `create_backend()` | No action needed |
| Gap 5 | Parameter mapping incomplete | **Resolved** — both forward and reverse maps now have 7 entries | Minor: fix reverse map inconsistency |
| Gap 6 | No topology refresh on cascade events | **Resolved** — relay loop handles `cascade_add`, fetches and broadcasts topology | No action needed |
| Gap 7 | Response normalization inconsistent | **Open** — `_ServiceTrainingMonitor` bypasses `_unwrap_response()` entirely | Fix in Phase 1 |
| Gap 8 | Local training_state drifts | **Resolved** — relay loop already calls `_state_update_callback` for `state` and `event` messages (lines 189-206); callback wired in lifespan (line 202) | No action needed |
| Gap 9 | Auth env var potentially miswired | **Needs verification** — `create_backend()` uses `JUNIPER_CASCOR_API_KEY` or `JUNIPER_DATA_API_KEY` | Verify in Phase 1 |

---

## 6. Fix Strategy

### Selected Approach: Canopy Adapter-Level Fixes (Option B) + FakeCascorClient Alignment (Option C partial)

**Rationale**:

- **Phase 1–3**: Fix at the canopy adapter/backend level. This is the fastest
  path to a working dashboard. The `_unwrap_response()` helper already exists —
  it just isn't used consistently. The `ServiceBackend` needs a response shape
  transformer for `/api/status`.

- **Phase 4**: Align `FakeCascorClient` with real server ResponseEnvelope
  format. This ensures tests are reliable integration indicators going forward.

**Why not fix at client library level** (`JuniperCascorClient._request()` unwrap):
While Option A (unwrap in client) would fix everything in one place, it's a
breaking change for any consumer that reads `"status"` or `"meta"` fields. The
`FakeCascorClient` would also need restructuring. This can be evaluated as a
follow-up but is not the right first move.

---

## 7. Consolidated Issue Registry

Every distinct issue requiring a code change, deduplicated and sequenced:

| ID | Severity | File | Description | Phase |
|---|---|---|---|---|
| FIX-1 | **CRITICAL** | `cascor_service_adapter.py:74-77` | `get_recent_metrics()` uses `result.get("history", [])` — must unwrap envelope and handle both list (`data`) and dict (`data.history`) | 1 |
| FIX-2 | **CRITICAL** | `cascor_service_adapter.py:60-66` | `is_training` reads top-level `is_training` — must unwrap and check `data.training_active` | 1 |
| FIX-3 | **CRITICAL** | `cascor_service_adapter.py:68-72` | `get_current_metrics()` returns raw client response — must unwrap envelope | 1 |
| FIX-4 | **CRITICAL** | `service_backend.py:100-101` | `get_status()` returns nested cascor structure — must transform to flat dashboard format | 1 |
| FIX-5 | **CRITICAL** | `state_sync.py:57-65` | `sync()` reads wrong keys from real server response structure; also never populates `SyncedState.phase` | 2 |
| FIX-6 | **CRITICAL** | `state_sync.py:88-95` | `sync()` metrics history extraction uses wrong nesting (`data.history` vs bare list in `data`) | 2 |
| FIX-7 | **CRITICAL** | `state_sync.py:70-75` | `sync()` params extraction uses wrong nesting (`data.params` vs flat `data`) | 2 |
| ~~FIX-8~~ | ~~IMPORTANT~~ | ~~`main.py:583-615`~~ | ~~`/api/state` in service mode~~ — **Already implemented.** Lines 583-615 populate defaults and call `get_canopy_params()`. Verify `get_canopy_params()` envelope handling works. | — |
| FIX-9 | **IMPORTANT** | `cascor_service_adapter.py:338` | Reverse param map: `patience` → `cn_training_convergence_threshold` should be `nn_growth_convergence_threshold` | 3 |
| FIX-10 | **IMPORTANT** | `service_backend.py` | Dataset response key mapping: cascor `train_samples`→`num_samples`, `input_features`→`num_features` | 3 |
| ~~FIX-11~~ | ~~MODERATE~~ | ~~`cascor_service_adapter.py:189-206`~~ | ~~Relay state callback~~ — **Already implemented.** Relay loop calls `_state_update_callback` for `state` and `event` messages. Callback wired in lifespan (line 202). | — |
| FIX-12 | **SYSTEMIC** | `fake_client.py` (cascor-client) | `FakeCascorClient` response format must match real server `ResponseEnvelope` | 4 |
| FIX-13 | **MODERATE** | `state_sync.py:100-116` | Status normalization missing `"started"` → `"Started"` mapping (real server uses title case) | 2 |
| FIX-14 | **IMPORTANT** | `cascor_service_adapter.py:281-286` | `is_training_in_progress()` reads `status.get("is_training", False)` — same envelope bug as FIX-2. Used by `ServiceBackend.is_training_active()` and as guard in `start_training()`. | 1 |
| FIX-15 | **MODERATE** | `service_backend.py` | Topology format verification: compare cascor `/v1/network/topology` shape against `network_visualizer.py` expectations before integration testing | 3 |

**Items confirmed already implemented (no action needed):**

- FIX-8: `/api/state` service mode handling (main.py:583-615)
- FIX-11: Relay state callback (cascor_service_adapter.py:189-206)
- Gap 4: Discovery env var — URL passed directly to `create_backend()`
- Gap 6: Topology refresh on `cascade_add` — relay loop handles this
- Gap 8: State callback wiring — lifespan registers callback at line 202

---

## 8. Phased Implementation Plan

### Phase 1: Fix Service Monitor & Status Response (CRITICAL — Unblocks All Display)

**Priority**: Critical — blocks all dashboard data in service mode
**Scope**: canopy only
**Estimated time**: 2 hours
**Dependencies**: None

#### 1.1 Fix `_ServiceTrainingMonitor` Response Handling

**File**: `canopy/src/backend/cascor_service_adapter.py`

The monitor class operates on raw client responses and never calls
`_unwrap_response()`. Four methods need fixing (three on the monitor,
one on the adapter):

**FIX-1: `get_recent_metrics()` (lines 74-77)**

Current:

```python
def get_recent_metrics(self, count: int = 100) -> list:
    try:
        result = self._client.get_metrics_history(count=count)
        return result.get("history", []) if isinstance(result, dict) else result
    except JuniperCascorClientError:
        return []
```

Fix:

```python
def get_recent_metrics(self, count: int = 100) -> list:
    try:
        result = self._client.get_metrics_history(count=count)
        if isinstance(result, dict):
            data = result.get("data", result)
            if isinstance(data, list):
                return data                        # Real server: data is the list
            if isinstance(data, dict):
                return data.get("history", [])     # FakeCascorClient: data.history
        return result if isinstance(result, list) else []
    except JuniperCascorClientError:
        return []
```

**FIX-2: `is_training` property (lines 60-66)**

Current:

```python
@property
def is_training(self) -> bool:
    try:
        status = self._client.get_training_status()
        return status.get("is_training", False)
    except JuniperCascorClientError:
        return False
```

Fix:

```python
@property
def is_training(self) -> bool:
    try:
        status = self._client.get_training_status()
        if "is_training" in status:
            return status["is_training"]               # FakeCascorClient
        data = status.get("data", {})
        if isinstance(data, dict):
            return data.get("training_active", False)  # Real server
        return False
    except JuniperCascorClientError:
        return False
```

**FIX-3: `get_current_metrics()` (lines 68-72)**

Current:

```python
def get_current_metrics(self) -> Dict[str, Any]:
    try:
        return self._client.get_metrics()
    except JuniperCascorClientError:
        return {}
```

Fix:

```python
def get_current_metrics(self) -> Dict[str, Any]:
    try:
        result = self._client.get_metrics()
        if isinstance(result, dict) and "data" in result:
            data = result["data"]
            return data if isinstance(data, dict) else result
        return result if isinstance(result, dict) else {}
    except JuniperCascorClientError:
        return {}
```

#### 1.2 Fix `ServiceBackend.get_status()` Response Shape

**File**: `canopy/src/backend/service_backend.py`

**FIX-4**: The `/api/status` endpoint returns `backend.get_status()` directly.
`ServiceBackend.get_status()` returns the unwrapped cascor training status, which
has nested sub-objects (`state_machine`, `monitor`, `training_state`). The
dashboard expects a flat dict with specific keys matching `DemoBackend.get_status()`.

Current:

```python
def get_status(self) -> Dict[str, Any]:
    return self._adapter.get_training_status()
```

Fix — add a transformation method:

```python
def get_status(self) -> Dict[str, Any]:
    raw = self._adapter.get_training_status()
    return self._normalize_status_response(raw)

@staticmethod
def _normalize_status_response(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Transform cascor's nested training status into the flat dict
    format that the dashboard frontend expects.

    The dashboard reads: is_running, is_paused, completed, failed,
    phase, current_epoch, hidden_units (matching DemoBackend.get_status()).
    """
    # Detect cascor's nested structure positively (safer than checking
    # for flat keys, which could misfire if cascor ever adds "is_running")
    if "state_machine" not in raw and "training_active" not in raw:
        return raw  # Already flat (demo-compatible)

    # Extract from cascor's nested structure
    sm = raw.get("state_machine", {}) if isinstance(raw.get("state_machine"), dict) else {}
    monitor = raw.get("monitor", {}) if isinstance(raw.get("monitor"), dict) else {}
    ts = raw.get("training_state", {}) if isinstance(raw.get("training_state"), dict) else {}

    fsm_status = sm.get("status", sm.get("current_state", "Stopped"))
    # Normalize to title case for comparison
    status_upper = fsm_status.upper() if isinstance(fsm_status, str) else "STOPPED"

    return {
        "is_training": raw.get("training_active", False),
        "is_running": status_upper == "STARTED",
        "is_paused": status_upper == "PAUSED",
        "completed": status_upper == "COMPLETED",
        "failed": status_upper == "FAILED",
        "fsm_status": fsm_status,
        "phase": sm.get("phase", ts.get("phase", "idle")).lower(),
        # Use `is not None` checks instead of `or` chains — epoch=0 and
        # hidden_units=0 are valid values but falsy, so `or` would skip them.
        "current_epoch": _first_defined(
            monitor.get("current_epoch"),
            monitor.get("epoch"),
            ts.get("current_epoch"),
            default=0,
        ),
        "hidden_units": _first_defined(
            monitor.get("current_hidden_units"),
            monitor.get("hidden_units"),
            default=0,
        ),
        "network_connected": raw.get("network_loaded", False),
        "monitoring_active": status_upper == "STARTED",
        "input_size": ts.get("input_size", 0),
        "output_size": ts.get("output_size", 0),
        # Pass through training_state fields for /api/state consumption
        "learning_rate": ts.get("learning_rate", 0.0),
        "max_hidden_units": ts.get("max_hidden_units", 0),
        "max_epochs": ts.get("max_epochs", 0),
    }
```

#### 1.3 Add `_first_defined()` Helper

**File**: `canopy/src/backend/service_backend.py`

Add a helper for safely extracting the first non-None value from a sequence.
This avoids the `or` chain pitfall where valid falsy values (0, False, "")
are skipped:

```python
def _first_defined(*values, default=None):
    """Return the first value that is not None, or default."""
    for v in values:
        if v is not None:
            return v
    return default
```

#### 1.4 Fix `CascorServiceAdapter.is_training_in_progress()` (FIX-14)

**File**: `canopy/src/backend/cascor_service_adapter.py`

**Discovered during plan validation.** This method has the exact same envelope
bug as `_ServiceTrainingMonitor.is_training` (FIX-2). It is used by
`ServiceBackend.is_training_active()` (protocol method) and as a guard in
`ServiceBackend.start_training()`.

Current (lines 281-286):

```python
def is_training_in_progress(self) -> bool:
    try:
        status = self._client.get_training_status()
        return status.get("is_training", False)
    except JuniperCascorClientError:
        return False
```

Fix (same pattern as FIX-2):

```python
def is_training_in_progress(self) -> bool:
    try:
        status = self._client.get_training_status()
        if "is_training" in status:
            return status["is_training"]               # FakeCascorClient
        data = status.get("data", {})
        if isinstance(data, dict):
            return data.get("training_active", False)  # Real server
        return False
    except JuniperCascorClientError:
        return False
```

#### 1.5 Verify API Key Environment Variable

**File**: `canopy/src/backend/__init__.py`

Verify that `create_backend()` uses `JUNIPER_CASCOR_API_KEY` (not
`JUNIPER_DATA_API_KEY`) for the cascor service connection. If it uses the
wrong one, update it. This is a quick check — no code change expected if
the factory already reads the correct variable.

#### Tests for Phase 1

| Test | File | Validates |
|---|---|---|
| `test_get_recent_metrics_real_envelope` | `tests/unit/test_service_monitor.py` | FIX-1: metrics history with real envelope format |
| `test_get_recent_metrics_fake_envelope` | `tests/unit/test_service_monitor.py` | FIX-1: metrics history with fake client format |
| `test_get_recent_metrics_empty_data` | `tests/unit/test_service_monitor.py` | FIX-1: handles `data: null` gracefully |
| `test_is_training_real_envelope` | `tests/unit/test_service_monitor.py` | FIX-2: is_training with real envelope |
| `test_is_training_false_not_fallthrough` | `tests/unit/test_service_monitor.py` | FIX-2: `is_training=False` doesn't fall through to real-server path |
| `test_get_current_metrics_unwraps` | `tests/unit/test_service_monitor.py` | FIX-3: current metrics unwrapping |
| `test_get_status_normalizes_cascor` | `tests/unit/test_service_backend.py` | FIX-4: nested → flat transformation |
| `test_get_status_passthrough_flat` | `tests/unit/test_service_backend.py` | FIX-4: already-flat dict passes through |
| `test_get_status_partial_nested` | `tests/unit/test_service_backend.py` | FIX-4: handles partial nested structure (missing monitor) |
| `test_get_status_epoch_zero_preserved` | `tests/unit/test_service_backend.py` | FIX-4: epoch=0 is not treated as missing |
| `test_is_training_in_progress_real` | `tests/unit/test_cascor_service_adapter.py` | FIX-14: envelope unwrap in adapter method |
| `test_is_training_active_service` | `tests/unit/test_service_backend.py` | FIX-14: protocol method works in service mode |

---

### Phase 2: Fix State Sync on Connect (CRITICAL — Correct Initial State)

**Priority**: Critical — dashboard shows wrong initial state
**Scope**: canopy only
**Estimated time**: 1.5 hours
**Dependencies**: None (can run in parallel with Phase 1)

#### 2.1 Fix `CascorStateSync.sync()` Training Status Parsing

**File**: `canopy/src/backend/state_sync.py`

**FIX-5, FIX-13**: The sync method reads training status using the fake
client's flat structure. With the real server, the data is nested in
`state_machine`, `monitor`, and `training_state` sub-objects.

Current (lines 57-65):

```python
status_response = self._client.get_training_status()
state.is_training = status_response.get("is_training", False)
data = status_response.get("data", {})
raw_state = data.get("state", "idle")
state.status = self._normalize_status(raw_state)
state.current_epoch = data.get("epoch", 0)
state.max_epochs = data.get("max_epochs", 0)
```

Fix:

```python
status_response = self._client.get_training_status()
data = status_response.get("data", {})

if isinstance(data, dict):
    # Determine is_training: explicit None check avoids False falling through
    is_training_top = status_response.get("is_training")  # FakeCascorClient
    if is_training_top is not None:
        state.is_training = is_training_top
    else:
        state.is_training = data.get("training_active", False)  # Real server

    # Extract state string from nested structure
    sm = data.get("state_machine", {})
    ts = data.get("training_state", {})
    raw_state = (
        data.get("state")                             # FakeCascorClient
        or (sm.get("status", "").lower() if isinstance(sm, dict) else None)
        or (sm.get("current_state", "").lower() if isinstance(sm, dict) else None)
        or "idle"
    )
    state.status = self._normalize_status(raw_state)

    # Extract phase (was never populated — FIX-5 addition)
    state.phase = (
        sm.get("phase") if isinstance(sm, dict) else None
    ) or (
        ts.get("phase") if isinstance(ts, dict) else None
    ) or "Idle"

    # Use _first_defined to avoid falsy-value (0) skipping with `or` chains
    monitor = data.get("monitor", {})
    state.current_epoch = _first_defined(
        data.get("epoch"),                             # FakeCascorClient
        monitor.get("current_epoch") if isinstance(monitor, dict) else None,
        ts.get("current_epoch") if isinstance(ts, dict) else None,
        default=0,
    )
    state.max_epochs = _first_defined(
        data.get("max_epochs"),                        # FakeCascorClient
        ts.get("max_epochs") if isinstance(ts, dict) else None,
        default=0,
    )
else:
    state.is_training = status_response.get("is_training", False)
    state.status = "Stopped"
    state.phase = "Idle"
    state.current_epoch = 0
    state.max_epochs = 0
```

> **Dual-path safety note**: The `is_training` extraction uses an explicit
> `is not None` check rather than `or`. This prevents `is_training=False`
> from the fake client from falling through to the real-server path. The
> epoch/max_epochs extraction uses `_first_defined()` to avoid `0` being
> treated as missing. The `_first_defined()` helper should be added to
> `state_sync.py` (same implementation as in Phase 1 section 1.3).

**FIX-13**: Add `"started"` to the status normalization mapping:

Current mapping in `_normalize_status()`:

```python
mapping = {
    "idle": "Stopped",
    "training": "Started",
    "paused": "Paused",
    "complete": "Completed",
    "failed": "Failed",
    ...
}
```

Add these entries:

```python
"started": "Started",       # Real server uses title case
"completed": "Completed",   # Real server state_machine.status
"stopped": "Stopped",       # Additional normalization
```

#### 2.2 Fix Metrics History Extraction

**File**: `canopy/src/backend/state_sync.py`

**FIX-6**: The sync extracts metrics history using `data.get("history", [])`,
but the real server returns the list directly in `data`.

Current (lines 89-93):

```python
history_response = self._client.get_metrics_history(count=metrics_limit)
if isinstance(history_response, dict):
    state.metrics_history = history_response.get("data", {}).get("history", [])
elif isinstance(history_response, list):
    state.metrics_history = history_response
```

Fix:

```python
history_response = self._client.get_metrics_history(count=metrics_limit)
if isinstance(history_response, dict):
    data = history_response.get("data", history_response)
    if isinstance(data, list):
        state.metrics_history = data               # Real server: data is the list
    elif isinstance(data, dict):
        state.metrics_history = data.get("history", [])  # FakeCascorClient
    else:
        state.metrics_history = []
elif isinstance(history_response, list):
    state.metrics_history = history_response
```

#### 2.3 Fix Training Params Extraction

**File**: `canopy/src/backend/state_sync.py`

**FIX-7**: The sync extracts params using `data.get("params", {})`, but the
real server returns params as flat fields directly in `data`.

Current (lines 68-72):

```python
params_response = self._client.get_training_params()
state.params = params_response.get("data", {}).get("params", {})
if not state.params and isinstance(params_response.get("data"), dict):
    state.params = {k: v for k, v in params_response.get("data", {}).items()
                    if k not in ("epochs", "dataset")}
```

This code's fallback actually handles the real server format correctly — if
`data.params` is missing, it falls back to the flat `data` dict minus
`epochs`/`dataset`. However, the fallback filter should be expanded:

Fix:

```python
params_response = self._client.get_training_params()
data = params_response.get("data", {})
if isinstance(data, dict):
    # Try FakeCascorClient format first (data.params sub-key)
    state.params = data.get("params", {})
    if not state.params:
        # Real server format: params are flat fields in data
        state.params = {
            k: v for k, v in data.items()
            if k not in ("epochs", "dataset", "status", "meta", "timestamp")
        }
```

#### Tests for Phase 2

| Test | File | Validates |
|---|---|---|
| `test_sync_real_training_status` | `tests/unit/test_state_sync.py` | FIX-5: real server nested status parsing |
| `test_sync_fake_training_status` | `tests/unit/test_state_sync.py` | FIX-5: fake client format still works |
| `test_sync_metrics_history_list` | `tests/unit/test_state_sync.py` | FIX-6: real server bare list format |
| `test_sync_metrics_history_dict` | `tests/unit/test_state_sync.py` | FIX-6: fake client dict format |
| `test_sync_params_flat` | `tests/unit/test_state_sync.py` | FIX-7: real server flat params |
| `test_sync_params_nested` | `tests/unit/test_state_sync.py` | FIX-7: fake client nested params |
| `test_normalize_status_title_case` | `tests/unit/test_state_sync.py` | FIX-13: "started"→"Started" mapping |

---

### Phase 3: Parameter Mapping, Dataset Normalization & Topology Verification (IMPORTANT)

**Priority**: Important — affects parameter display, dataset tab, and topology
**Scope**: canopy only
**Estimated time**: 1.5 hours
**Dependencies**: Phase 1 (uses normalized status), Phase 2 (uses synced params)

> **Note**: FIX-8 (`/api/state` service mode handling) was found to be
> **already implemented** at `main.py:583-615`. The existing code populates
> defaults and calls `get_canopy_params()`. Verify that `get_canopy_params()`
> correctly handles the real server's envelope format (it uses
> `result.get("data", {}).get("params", {})` with a flat-data fallback).

#### 3.1 Fix Reverse Parameter Mapping Inconsistency

**File**: `canopy/src/backend/cascor_service_adapter.py`

**FIX-9**: The reverse param map has an inconsistency:

```python
# Forward: "nn_growth_convergence_threshold" → "patience"
# Reverse: "patience" → "cn_training_convergence_threshold"  ← WRONG
```

The forward map says `nn_growth_convergence_threshold` maps to `patience`,
but the reverse maps `patience` back to `cn_training_convergence_threshold`.
These are different canopy parameter names. Fix the reverse mapping:

```python
_CASCOR_TO_CANOPY_PARAM_MAP = {
    ...
    "patience": "nn_growth_convergence_threshold",  # Was: cn_training_convergence_threshold
    ...
}
```

Validate which canopy param name is correct by checking what the dashboard
parameter panel uses. If both `nn_growth_convergence_threshold` AND
`cn_training_convergence_threshold` exist in the UI, they may map to
different cascor params. Verify before changing.

#### 3.3 Fix Dataset Response Key Mapping

**File**: `canopy/src/backend/service_backend.py`

**FIX-10**: The dataset endpoint returns different key names between demo and
service modes. The demo backend returns `num_samples`, `num_features`,
`num_classes`, `inputs`, `targets`. The cascor dataset endpoint returns
`loaded`, `train_samples`, `input_features`, `output_features` (metadata only).

Add a normalizer in `ServiceBackend.get_dataset()`:

```python
def get_dataset(self) -> Optional[Dict[str, Any]]:
    raw = self._adapter.get_dataset_info()
    if not raw or not raw.get("loaded", False):
        return None
    return {
        "num_samples": raw.get("train_samples", 0) + raw.get("test_samples", 0),
        "num_features": raw.get("input_features", 0),
        "num_classes": raw.get("output_features", 0),
        "loaded": True,
        "train_samples": raw.get("train_samples", 0),
        "test_samples": raw.get("test_samples", 0),
        # Note: actual data arrays (inputs, targets) not available from cascor
        # metadata endpoint. Dataset visualization will show metadata only.
    }
```

**Open question**: The cascor `/v1/dataset` endpoint returns metadata only —
no actual data arrays (`inputs`, `targets`). If the dataset scatter plot
requires these arrays, a new cascor endpoint would be needed, or canopy could
fetch data directly via `juniper-data-client`. This is a known limitation
documented in the data flow analysis. Recommend deferring data array retrieval
to a future enhancement.

#### 3.4 Verify Topology Response Format Compatibility (FIX-15)

**Files**: `canopy/src/backend/cascor_service_adapter.py` (extract_network_topology),
`canopy/src/frontend/network_visualizer.py` (or equivalent topology consumer)

Compare the cascor `/v1/network/topology` response shape (after `_unwrap_response()`)
against what the network visualizer component expects. Key questions:

- Does the cascor topology response have `nodes`, `connections` at the top level?
- Does the visualizer expect `layers` array? Node `id`, `type`, `layer` fields?
- Do connection keys match (`from`/`to` vs `source_id`/`target_id`)?

If a mismatch is found, add a key transformation in
`CascorServiceAdapter.extract_network_topology()`, similar to how
`get_decision_boundary()` transforms `grid_x`/`grid_y` → `xx`/`yy`.

#### Tests for Phase 3

| Test | File | Validates |
|---|---|---|
| `test_param_map_roundtrip` | `tests/unit/test_cascor_service_adapter.py` | FIX-9: all params round-trip correctly |
| `test_get_canopy_params_real_envelope` | `tests/unit/test_cascor_service_adapter.py` | Verify get_canopy_params() handles real server envelope |
| `test_dataset_key_normalization` | `tests/unit/test_service_backend.py` | FIX-10: cascor → canopy key mapping |
| `test_topology_format_compatibility` | `tests/unit/test_service_backend.py` | FIX-15: topology shape matches visualizer expectations |

---

### Phase 4: FakeCascorClient Alignment (SYSTEMIC — Prevents Future Divergence)

**Priority**: Important — prevents recurrence of all RC-1 through RC-4 class bugs
**Scope**: juniper-cascor-client
**Estimated time**: 2–3 hours
**Dependencies**: Phase 1 and 2 complete (canopy-side fixes validated first)

#### 4.1 Update FakeCascorClient Response Formats

**File**: `juniper-cascor-client/juniper_cascor_client/testing/fake_client.py`

**FIX-12**: Update all response methods to match the real server's
`ResponseEnvelope` structure:

| Method | Change |
|---|---|
| `get_training_status()` | Remove top-level `is_training`. Nest data in `state_machine`, `monitor`, `training_state` sub-objects. Add `training_active` field. Change `"ok"` → `"success"`. Add `"meta"`. |
| `get_metrics_history()` | Change `data` from `{"history": [...], "total": N, "returned": N}` to bare list. Add `"meta"`. |
| `get_metrics()` | Remove `correlation`, `phase`. Add `timestamp`. Change `"ok"` → `"success"`. Add `"meta"`. |
| `get_training_params()` | Change `data` from `{"params": {...}, "epochs": N}` to flat param dict. Add `"meta"`. |
| All methods | Change `"status": "ok"` → `"status": "success"`. Add `"meta": {"timestamp": time.time(), "version": "0.4.0"}`. |

#### 4.2 Add Response Envelope Helper

Add a helper to `FakeCascorClient` that mirrors `success_response()`:

```python
@staticmethod
def _success_envelope(data: Any) -> Dict[str, Any]:
    return {
        "status": "success",
        "data": data,
        "meta": {"timestamp": time.time(), "version": "0.4.0"},
    }
```

#### 4.3 Update Tests That Depend on Old Format

After changing `FakeCascorClient`, any test that asserts on the old response
structure will break. This is intentional — fix those tests to validate the
new (correct) format. This ensures test coverage reflects reality.

#### Tests for Phase 4

- Run full `juniper-cascor-client` test suite: `pytest tests/ -v`
- Run full `juniper-canopy` test suite: `cd src && pytest tests/ -v`
- All tests must pass with updated fake client

---

### Phase 5: Integration Testing & End-to-End Validation (CRITICAL)

**Priority**: Critical — validates all fixes work together
**Scope**: canopy + cascor (running)
**Estimated time**: 2 hours
**Dependencies**: Phases 1–3 (Phase 4 optional but recommended)

#### 5.1 New Integration Tests

> **CI note**: Tests marked `(mock)` use mocked cascor responses and run in
> CI without infrastructure. Tests marked `(live)` require a running cascor
> instance and should be gated behind `CASCOR_BACKEND_AVAILABLE=1`.

| Test | File | Purpose |
|---|---|---|
| `test_external_cascor_attach` | `tests/integration/test_external_cascor_attach.py` | (live) Verify non-destructive attach to running cascor; no `create_network` or `reset` calls; params/epoch/status populate correctly |
| `test_canopy_restart_during_training` | `tests/integration/test_canopy_restart.py` | (live) Start canopy → verify cascor continues → stop canopy → verify cascor keeps running → restart canopy → verify reattach and state restore |
| `test_param_apply_roundtrip` | `tests/integration/test_param_roundtrip.py` | (live) Apply each mappable param from canopy → verify cascor received update → verify canopy reflects new values |
| `test_service_mode_dashboard_data` | `tests/integration/test_dashboard_data.py` | (mock) Verify each `/api/*` endpoint returns dashboard-compatible shapes in service mode using mocked cascor responses |

#### 5.2 Regression Verification

```bash
# Canopy unit tests (demo mode, no cascor needed)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
pytest tests/unit/ -v

# Canopy integration tests
pytest tests/integration/ -v

# Canopy full suite with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Cascor regression (no changes expected, but verify)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src/tests
conda activate JuniperCascor
bash scripts/run_tests.bash

# Cascor-client tests (after Phase 4 only)
cd /home/pcalnon/Development/python/Juniper/juniper-cascor-client
pytest tests/ -v
```

#### 5.3 Manual End-to-End Verification

```bash
# Terminal 1: Start cascor
cd /home/pcalnon/Development/python/Juniper/juniper-cascor/src
conda activate JuniperCascor
python server.py

# Terminal 2: Start canopy (auto-discovers cascor)
cd /home/pcalnon/Development/python/Juniper/juniper-canopy/src
conda activate JuniperPython
uvicorn main:app --host 0.0.0.0 --port 8050

# Terminal 3: Verify API responses
curl -s http://localhost:8050/api/status | python -m json.tool
curl -s http://localhost:8050/api/metrics/history?limit=10 | python -m json.tool
curl -s http://localhost:8050/api/state | python -m json.tool
curl -s http://localhost:8050/api/dataset | python -m json.tool
```

Visual verification checklist:

- [ ] Status bar shows Running/Paused/Stopped correctly
- [ ] Epoch counter increments during training
- [ ] Hidden units count updates on cascade events
- [ ] Loss/accuracy charts display live data
- [ ] Phase indicator shows Output/Candidate transitions
- [ ] Network topology renders (topology tab)
- [ ] Decision boundary renders (boundaries tab)
- [ ] Dataset metadata displays (dataset tab)
- [ ] Parameter changes from canopy apply to cascor
- [ ] Stopping canopy does not stop cascor training
- [ ] Restarting canopy reconnects and shows correct state

---

## 9. Dependency Graph

```text
Phase 1 (Monitor + Status + FIX-14)     Phase 2 (State Sync)
    │                                        │
    ├────────────────────────────────────────┤
    │                                        │
    ▼                                        ▼
Phase 3 (Params, Dataset, Topology)     (independent)
    │
    ▼
Phase 4 (FakeCascorClient alignment)
    │
    ▼
Phase 5 (Integration testing)
```

- **Phases 1 and 2** can run in parallel (independent fixes)
- **Phase 3** depends on Phase 1 (uses normalized status) and Phase 2 (uses synced params)
- **Phase 4** should follow Phases 1–2 (validate canopy fixes before changing fake client)
- **Phase 5** should follow all other phases

> **Removed phases**: The original Phase 4 (live state sync via relay) was
> removed — validation confirmed it is already implemented at
> `cascor_service_adapter.py:189-206` and `main.py:202`.

---

## 10. Risk Mitigation

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Cascor response format changes in future versions | Fixes break again | Low | Phase 4 aligns FakeCascorClient; future tests catch divergence |
| Dual-path logic misfires (real response matches fake path) | Silent data corruption | Low | Positive detection of nested structure (`state_machine in raw`), `_first_defined()` for falsy values, explicit `is not None` checks |
| Parameter mapping has untested edge cases | Params silently fail to apply | Medium | Phase 3 round-trip tests cover all 7 mapped params |
| Dashboard callbacks have additional undocumented key dependencies | Some UI elements still blank | Medium | Phase 5 visual verification catches these |
| `_unwrap_response()` strips `meta` field that some code needs | Loss of timestamp/version info | Low | No current canopy code reads `meta` — verified |
| FakeCascorClient changes (Phase 4) break downstream test suites | Test failures in other repos | Medium | Run canopy + cascor-client test suites before merging Phase 4 |
| Demo mode regresses from shared code changes | Demo mode breaks | Low | All phases include demo-format compatibility in dual-path logic |
| Dataset visualization broken due to missing data arrays | Dataset tab empty | High (known) | Document as known limitation; defer array retrieval to future enhancement |
| WebSocket buffer not consumed by Dash callbacks | Real-time metrics only via polling | Low (known) | Architectural limitation noted; polling is the primary data path; future enhancement to wire WS buffer to Dash stores |

---

## 11. Success Criteria

All criteria must be met before the work is considered complete:

### Functional Criteria

- [ ] Canopy auto-discovers running cascor and enters service mode
- [ ] Dashboard displays current cascor status immediately on connect (not defaults)
- [ ] Status bar shows correct Running/Paused/Stopped/Completed state
- [ ] Epoch counter shows actual cascor epoch count
- [ ] Hidden units counter shows actual cascor hidden unit count
- [ ] Phase indicator shows Output/Candidate/Inference correctly
- [ ] Metrics charts (loss, accuracy) display live training data
- [ ] Parameters panel shows actual cascor parameters (not defaults)
- [ ] Parameter changes from canopy apply to running cascor
- [ ] Network topology updates after cascade events
- [ ] Training controls (start/stop/pause/resume/reset) work in service mode
- [ ] Stopping canopy does not affect cascor training
- [ ] Restarting canopy reconnects and restores current state

### Quality Criteria

- [ ] All existing demo-mode unit tests continue to pass
- [ ] All existing demo-mode integration tests continue to pass
- [ ] No regressions in cascor test suite
- [ ] New tests cover both real server and fake client response formats
- [ ] Test coverage does not decrease
- [ ] FakeCascorClient (Phase 4) matches real server ResponseEnvelope format

---

## 12. Files Modified (Summary)

### juniper-canopy

| File | Phase | Changes |
|---|---|---|
| `src/backend/cascor_service_adapter.py` | 1, 3 | Fix monitor methods (FIX-1,2,3), fix `is_training_in_progress` (FIX-14), fix reverse param map (FIX-9) |
| `src/backend/service_backend.py` | 1, 3 | Add `_normalize_status_response()` + `_first_defined()` (FIX-4), fix `get_dataset()` key mapping (FIX-10) |
| `src/backend/state_sync.py` | 2 | Fix `sync()` for real server response structure (FIX-5,6,7,13), add phase extraction, add `_first_defined()` |
| `src/main.py` | — | No changes needed (FIX-8 and state callback already implemented) |
| `src/tests/unit/test_service_monitor.py` | 1 | **NEW** — monitor response handling tests |
| `src/tests/unit/test_state_sync.py` | 2 | Updated sync tests with real envelope format |
| `src/tests/unit/test_service_backend.py` | 1, 3 | Status normalization + dataset key mapping + topology format tests |
| `src/tests/unit/test_cascor_service_adapter.py` | 1, 3 | FIX-14 (is_training_in_progress) + param roundtrip tests |
| `src/tests/integration/test_external_cascor_attach.py` | 5 | **NEW** — non-destructive attach integration (live) |
| `src/tests/integration/test_dashboard_data.py` | 5 | **NEW** — service mode dashboard data shapes (mock) |

### juniper-cascor-client

| File | Phase | Changes |
|---|---|---|
| `juniper_cascor_client/testing/fake_client.py` | 4 | Align response format with real server ResponseEnvelope (FIX-12) |

### juniper-cascor

No changes required. The cascor API already exposes all necessary endpoints
with correct response formats. Verify via existing test suite.

---

## 13. Appendix: Dashboard Data Contract

The dashboard frontend (`dashboard_manager.py`) expects these response shapes
from backend REST endpoints. Both `DemoBackend` and `ServiceBackend` must
produce these shapes.

### `/api/status` Response Contract

```python
{
    "is_running": bool,          # True when actively training
    "is_paused": bool,           # True when paused
    "completed": bool,           # True when training finished
    "failed": bool,              # True when training errored
    "phase": str,                # "idle" | "output" | "candidate" | "inference"
    "current_epoch": int,        # Current training epoch
    "hidden_units": int,         # Current cascade hidden unit count
    "fsm_status": str,           # Raw FSM status string
    "is_training": bool,         # Overall training active flag
    "network_connected": bool,   # Backend connection status
    "monitoring_active": bool,   # Monitoring active flag
}
```

### `/api/metrics/history` Response Contract

```python
{
    "history": [                 # List of metric snapshots
        {
            "epoch": int,
            "train_loss": float,
            "train_accuracy": float,
            "val_loss": float | None,
            "val_accuracy": float | None,
            "hidden_units": int,
            "phase": str,
        },
        ...
    ]
}
```

Note: The dashboard handler is resilient and accepts `{"history": [...]}`,
`{"data": [...]}`, or a bare list. The API endpoint wraps the backend
response in `{"history": backend.get_metrics_history(count)}`.

### `/api/state` Response Contract

```python
{
    "status": str,               # "Stopped" | "Started" | "Paused" | "Completed" | "Failed"
    "phase": str,                # "Idle" | "Output" | "Candidate" | "Inference"
    "nn_learning_rate": float,
    "nn_max_hidden_units": int,
    "nn_max_total_epochs": int,
    "nn_growth_convergence_threshold": float,
    "cn_pool_size": int,
    "cn_correlation_threshold": float,
    "cn_training_iterations": int,
    "cn_training_convergence_threshold": float,
    # ... additional nn_*/cn_* fields
    "current_epoch": int,
    "learning_rate": float,
    "max_hidden_units": int,
    "max_epochs": int,
}
```

### `/api/dataset` Response Contract

```python
{
    "num_samples": int,          # Total samples
    "num_features": int,         # Input dimensionality
    "num_classes": int,          # Output dimensionality
    # Optional (demo mode only):
    "inputs": [[float, ...]],    # Feature matrix
    "targets": [int, ...],       # Label array
}
```

---

## 14. Known Limitations & Future Enhancements

These items are documented for awareness but are **not addressed in this plan**:

### 14.1 WebSocket Buffer Not Consumed by Dash Callbacks

The `websocket_client.js` correctly receives and buffers messages from the
cascor relay (`/ws/training`), but no Dash callback consumes
`window.cascorWS.getBufferedMessages()`. All dashboard data display is driven
exclusively via HTTP polling (`dcc.Interval` → `/api/*` endpoints). The
WebSocket path is functional infrastructure for future real-time push
integration but does not currently contribute to dashboard rendering.

**Impact**: Dashboard updates are limited to polling frequency (1s fast, 5s
slow). Sub-second metrics updates from cascor are received but not rendered.

**Future enhancement**: Wire a Dash `clientside_callback` to consume the
WebSocket buffer and update `dcc.Store` components directly, bypassing
HTTP polling for real-time metrics.

### 14.2 Dataset Visualization Missing Data Arrays in Service Mode

The cascor `/v1/dataset` endpoint returns metadata only (`train_samples`,
`input_features`, etc.) — not the actual data arrays (`inputs`, `targets`).
In service mode, the dataset scatter plot tab will show metadata but cannot
render the scatter visualization.

**Impact**: Dataset tab shows metadata only; scatter plot is empty.

**Future enhancement**: Either add a cascor endpoint returning dataset arrays,
or use `juniper-data-client` to fetch training data directly from
juniper-data service.

### 14.3 `BackendProtocol` Does Not Define Response Shapes

The `BackendProtocol` specifies method signatures with `Dict[str, Any]`
return types but does not define the expected response schemas. This allowed
the `DemoBackend` and `ServiceBackend` to produce different shapes for the
same method, which is the root cause of the display failures.

**Future enhancement**: Define response schemas (dataclasses or TypedDicts)
in `protocol.py` and type-annotate return types accordingly. This makes the
contract explicit and catch mismatches at type-check time.

### 14.4 `main.py` Accesses `backend._adapter` Directly

Multiple places in `main.py` access `backend._adapter` (a `ServiceBackend`
implementation detail) rather than going through the `BackendProtocol`
interface. This couples the application layer to the service backend
implementation.

**Future enhancement**: Expose needed functionality through `BackendProtocol`
methods (e.g., `get_canopy_params()`, `apply_params()`) rather than reaching
through to the adapter.
